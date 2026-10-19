"""Local web UI to browse and export the karmed patient list.

Runs only on localhost. Search hits the server's own name filter (~1s) through a
reusable session, so browsing stays fast; the full 22k list is only pulled when
the user explicitly exports everything (the remote PHP server takes 30-80s for it).
"""
from __future__ import annotations

import os
import socket
import sys
import threading
from dataclasses import asdict
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from karmed.client import DEFAULT_BASE_URL, KarmedClient, LoginError, base_url
from karmed.citas import (
    default_citas_name,
    export_citas_to_excel,
    fetch_all_citas,
    get_agenda_context,
)
from karmed.patients import (
    LIST_ENDPOINT,
    Patient,
    default_export_name,
    diff_new,
    export_to_excel,
    fetch_patients,
    load_cache,
    save_cache,
)

def _data_dir() -> Path:
    """Where the user's files live: next to the executable when frozen, else cwd."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path.cwd()


def _static_dir() -> Path:
    """Bundled read-only assets: the PyInstaller temp dir when frozen, else the package."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "static"
    return Path(__file__).parent / "static"


EXPORT_DIR = _data_dir() / "exports"
CACHE_PATH = _data_dir() / "data" / "patients.json"
ENV_PATH = _data_dir() / ".env"
STATIC_DIR = _static_dir()
_ENV_KEYS = ("KARMED_URL", "KARMED_USER", "KARMED_PASS", "KARMED_BRANCH")

app = FastAPI(title="Karmed Export")


def _write_env(values: dict[str, str]) -> None:
    """Persist the given keys to .env, preserving any unrelated lines."""
    lines: list[str] = []
    seen: set[str] = set()
    if ENV_PATH.exists():
        for raw in ENV_PATH.read_text(encoding="utf-8").splitlines():
            key = raw.split("=", 1)[0].strip()
            if key in values:
                lines.append(f"{key}={values[key]}")
                seen.add(key)
            else:
                lines.append(raw)
    for key in _ENV_KEYS:
        if key in values and key not in seen:
            lines.append(f"{key}={values[key]}")
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    # apply immediately so the next client build uses the new values
    for key, value in values.items():
        os.environ[key] = value

_lock = threading.Lock()
_state: dict[str, object] = {
    "patients": None,
    "cliente": "3",
    "saved_at": None,
    "loading": False,   # a full load is running in the background
    "error": None,      # last background-load error, if any
    "new": 0,           # new patients detected by the last load
}

# Live search: the server filters by name/cédula in ~1s, so a reusable logged-in
# session plus a small per-term cache lets browsing stay instant without pulling
# all 22k patients (which takes 30-80s on the remote PHP server).
_client_lock = threading.Lock()
_shared_client: KarmedClient | None = None
_search_cache: dict[str, list[Patient]] = {}


@app.on_event("startup")
def _load_cache_on_startup() -> None:
    patients, saved_at = load_cache(CACHE_PATH)
    if patients:
        _state["patients"] = patients
        _state["saved_at"] = saved_at


def _reset_client() -> None:
    global _shared_client
    try:
        if _shared_client is not None:
            _shared_client.close()
    except Exception:  # noqa: BLE001
        pass
    _shared_client = None


def _get_client() -> KarmedClient:
    global _shared_client
    if _shared_client is None:
        client = KarmedClient()
        client.login()
        _shared_client = client
    return _shared_client


def _live_query(term: str) -> list[Patient]:
    """Filtered search straight against the server (fast), reusing the session.

    Cached per term for the session. Retries once with a fresh login if the
    shared session has expired.
    """
    key = term.strip().lower()
    with _client_lock:
        if key in _search_cache:
            return _search_cache[key]
        try:
            rows = fetch_patients(_get_client(), cliente=str(_state["cliente"]), query=term)
        except (httpx.HTTPError, LoginError):
            _reset_client()
            rows = fetch_patients(_get_client(), cliente=str(_state["cliente"]), query=term)
        _search_cache[key] = rows
        return rows


def _fetch_and_store(force: bool = False) -> dict:
    """Fetch the list from the server, detect new patients, and persist it."""
    with _lock:
        cached = _state.get("patients")
        if cached is not None and not force:
            return {"count": len(cached), "new": 0, "saved_at": _state.get("saved_at"), "cached": True}  # type: ignore[arg-type]
        previous: list[Patient] = list(cached) if cached else []  # type: ignore[arg-type]
        client = KarmedClient()
        client.login()
        try:
            patients = fetch_patients(client, cliente=str(_state["cliente"]))
        finally:
            client.close()
        new_ids = diff_new(previous, patients)
        saved_at = save_cache(patients, CACHE_PATH)
        _state["patients"] = patients
        _state["saved_at"] = saved_at
    with _client_lock:
        _search_cache.clear()  # fresh full list -> drop stale per-term results
    return {"count": len(patients), "new": len(new_ids), "saved_at": saved_at, "cached": False}


@app.get("/api/config")
def get_config() -> dict:
    """Report what the scraper consumes from .env, for display in the UI.

    This is a localhost-only tool showing the operator their own credentials;
    the password is sent so the UI can reveal and edit it.
    """
    load_dotenv(override=True)
    return {
        "url": base_url(),
        "endpoint": base_url() + LIST_ENDPOINT,
        "user": os.environ.get("KARMED_USER", ""),
        "password": os.environ.get("KARMED_PASS", ""),
        "branch": os.environ.get("KARMED_BRANCH", ""),
        "default_url": DEFAULT_BASE_URL,
    }


@app.post("/api/config")
def save_config(payload: dict = Body(...)) -> dict:
    """Save credentials from the UI into .env and drop the cached list."""
    user = str(payload.get("user", "")).strip()
    password = str(payload.get("password", "")).strip()
    if not user or not password:
        raise HTTPException(status_code=400, detail="Usuario y contraseña son obligatorios")
    values = {
        "KARMED_URL": str(payload.get("url", "")).strip(),
        "KARMED_USER": user,
        "KARMED_PASS": password,
        "KARMED_BRANCH": str(payload.get("branch", "")).strip(),
    }
    _write_env(values)
    with _lock:
        _state["patients"] = None  # force a reload with the new credentials
    with _client_lock:
        _search_cache.clear()
        _reset_client()  # next search logs in with the new credentials
    return {"saved": True, "url": base_url() + LIST_ENDPOINT}


APP_MARKER = "karmed-export"


@app.get("/api/health")
def health() -> dict:
    """Signature used by a second launch to detect an already-running instance."""
    return {"app": APP_MARKER}


@app.get("/api/status")
def status() -> dict:
    patients = _state.get("patients")
    return {
        "loaded": patients is not None,
        "count": len(patients) if patients else 0,  # type: ignore[arg-type]
        "saved_at": _state.get("saved_at"),
        "loading": bool(_state.get("loading")),
        "error": _state.get("error"),
        "new": _state.get("new", 0),
    }


def _run_background_load(force: bool) -> None:
    try:
        result = _fetch_and_store(force=force)
        _state["new"] = result["new"]
        _state["error"] = None
    except LoginError as exc:
        _state["error"] = str(exc)
    except Exception as exc:  # noqa: BLE001
        _state["error"] = f"No se pudo traer el listado: {exc}"
    finally:
        _state["loading"] = False


@app.post("/api/load")
def load(force: bool = False) -> dict:
    """Start a full load in the background and return immediately.

    The long (30-80s) fetch runs in a thread so the HTTP request never hangs;
    the UI polls /api/status to follow progress and get the result.
    """
    if _state.get("loading"):
        return {"started": False, "loading": True}
    _state["loading"] = True
    _state["error"] = None
    threading.Thread(target=_run_background_load, args=(force,), daemon=True).start()
    return {"started": True, "loading": True}


@app.get("/api/patients")
def list_patients(
    q: str = Query("", description="filter by name, historia or cédula"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> JSONResponse:
    term = q.strip()
    if term:
        try:
            rows = _live_query(term)  # ~1s server-side filter, no full load needed
        except LoginError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=502, detail=f"No se pudo buscar: {exc}") from exc
    else:
        patients = _state.get("patients")
        if patients is None:
            raise HTTPException(
                status_code=409,
                detail="Escribí un nombre o cédula para buscar, o cargá el listado completo.",
            )
        rows = list(patients)  # type: ignore[arg-type]

    total = len(rows)
    page = [asdict(p) for p in rows[offset : offset + limit]]
    return JSONResponse({"total": total, "offset": offset, "limit": limit, "rows": page})


@app.post("/api/export")
def export(q: str = Query("", description="export only rows matching this filter")) -> dict:
    term = q.strip()
    if term:
        try:
            rows = _live_query(term)  # export the search result directly (fast)
        except LoginError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=502, detail=f"No se pudo exportar: {exc}") from exc
    else:
        patients = _state.get("patients")
        if patients is None:
            raise HTTPException(
                status_code=409,
                detail="Para exportar TODOS, primero cargá el listado completo. O buscá un nombre y exportá ese resultado.",
            )
        rows = list(patients)  # type: ignore[arg-type]

    name = default_export_name()
    export_to_excel(rows, EXPORT_DIR / name)
    return {"file": name, "count": len(rows)}


@app.get("/api/citas/context")
def citas_context() -> dict:
    """Doctors and branch available in the agenda, for display before exporting."""
    try:
        with _client_lock:
            medicos, sucursal = get_agenda_context(_get_client())
        return {"medicos": [asdict(m) for m in medicos], "sucursal": sucursal}
    except LoginError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"No se pudo leer la agenda: {exc}") from exc


@app.post("/api/citas/export")
def citas_export() -> dict:
    """Fetch every appointment (all doctors, all years) and export it to Excel."""
    try:
        with _client_lock:
            medicos, sucursal = get_agenda_context(_get_client())
            citas = fetch_all_citas(_get_client(), medicos, sucursal)
    except LoginError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"No se pudieron traer las citas: {exc}") from exc
    name = default_citas_name()
    export_citas_to_excel(citas, EXPORT_DIR / name)
    return {"file": name, "count": len(citas)}


@app.get("/download/{name}")
def download(name: str) -> FileResponse:
    # guard against path traversal: only plain file names inside EXPORT_DIR
    safe = Path(name).name
    path = EXPORT_DIR / safe
    if safe != name or not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=safe,
    )


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")


# Uncommon default port to avoid clashing with other local apps (3000/5000/8000/8080…).
# KARMED_PORT overrides it; if the chosen port is busy, the next free one is used.
PREFERRED_PORT = 8771


def _is_our_app(port: int) -> bool:
    """True if a Karmed Export instance is already answering on this port."""
    import json
    import urllib.request

    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=0.6) as resp:
            return json.load(resp).get("app") == APP_MARKER
    except Exception:  # noqa: BLE001
        return False


def _resolve_port(preferred: int, span: int = 50) -> tuple[str, int]:
    """Decide what to do: ("serve", port) to start here, ("open", port) if we are
    already running there. Scans from `preferred`, skipping ports owned by other apps.
    """
    for port in range(preferred, preferred + span):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind(("127.0.0.1", port))
                return ("serve", port)  # free -> serve here
            except OSError:
                pass  # busy -> is it us, or another app?
        if _is_our_app(port):
            return ("open", port)  # already running -> just open the browser
    return ("serve", preferred)


def _banner(url: str) -> str:
    line = "=" * 56
    return (
        f"\n{line}\n"
        "  KARMED EXPORT\n\n"
        "  Si el navegador no se abrió solo, copiá esta\n"
        "  direccion y pegala en tu navegador:\n\n"
        f"      {url}\n\n"
        "  Deja esta ventana abierta mientras lo usas.\n"
        "  Para cerrar el programa, cerra esta ventana.\n"
        f"{line}\n"
    )


def _open_when_ready(url: str, port: int, timeout: float = 40.0) -> None:
    """Open the browser only once the server actually answers, so the user never
    lands on a 'cannot connect' page."""
    import time
    import webbrowser

    deadline = time.time() + timeout
    while time.time() < deadline:
        if _is_our_app(port):
            break
        time.sleep(0.3)
    try:
        webbrowser.open(url)
    except Exception:  # noqa: BLE001
        pass


def _set_console_title(title: str) -> None:
    try:
        if sys.platform == "win32":
            import ctypes

            ctypes.windll.kernel32.SetConsoleTitleW(title)  # type: ignore[attr-defined]
        else:
            sys.stdout.write(f"\33]0;{title}\a")
            sys.stdout.flush()
    except Exception:  # noqa: BLE001
        pass


def main() -> None:
    import multiprocessing
    import webbrowser

    import uvicorn

    multiprocessing.freeze_support()  # safe PyInstaller onefile startup
    _set_console_title("Karmed Export")
    # anchor .env / data / exports next to the executable
    if getattr(sys, "frozen", False):
        os.chdir(_data_dir())

    try:
        preferred = int(os.environ.get("KARMED_PORT", PREFERRED_PORT))
    except ValueError:
        preferred = PREFERRED_PORT

    action, port = _resolve_port(preferred)
    url = f"http://127.0.0.1:{port}"

    if action == "open":
        # Karmed Export is already running: reuse it, do not start a second server.
        print(_banner(url), flush=True)
        print("Ya estaba abierto: te llevo a la ventana que ya corre.", flush=True)
        webbrowser.open(url)
        return

    print(_banner(url), flush=True)
    threading.Thread(target=_open_when_ready, args=(url, port), daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
