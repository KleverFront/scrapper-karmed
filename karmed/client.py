"""HTTP client for the Karmed derma web app using its PHP session cookie.

The target URL is not hardcoded: set KARMED_URL (together with KARMED_USER and
KARMED_PASS) in the .env file or via the app's Configuración panel.
"""
import os

import httpx
from dotenv import load_dotenv

# No default target: the URL must be provided via KARMED_URL (.env or UI).
DEFAULT_BASE_URL = ""


def base_url() -> str:
    """Base URL for the target, taken from KARMED_URL (.env or UI)."""
    url = os.environ.get("KARMED_URL", "").strip() or DEFAULT_BASE_URL
    if not url:
        return ""
    return url if url.endswith("/") else url + "/"


class LoginError(RuntimeError):
    pass


class KarmedClient:
    def __init__(self, timeout: float = 60.0):
        load_dotenv(override=True)
        self.base_url = base_url()
        self.user = os.environ.get("KARMED_USER", "")
        self.password = os.environ.get("KARMED_PASS", "")
        self.branch = os.environ.get("KARMED_BRANCH", "")
        if not self.base_url:
            raise LoginError("Set KARMED_URL in .env (or in the Configuración panel)")
        if not self.user or not self.password:
            raise LoginError("Set KARMED_USER and KARMED_PASS in .env")
        self.http = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (karmed-export)"},
        )

    def login(self) -> None:
        self.http.get("index.php")  # obtain PHPSESSID
        resp = self.http.post(
            "modules/consulta_acceso.php",
            data={"clien": self.user, "clav": self.password, "sucu": self.branch},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        resp.raise_for_status()
        nick = resp.text.strip()
        if nick == "":
            raise LoginError("Access denied: wrong user or password")
        if nick == "Inactivo":
            raise LoginError("User is inactive")
        if nick == "REN":
            raise LoginError("This user requires a branch: set KARMED_BRANCH in .env")

    def get(self, path: str, **kwargs) -> httpx.Response:
        resp = self.http.get(path, **kwargs)
        resp.raise_for_status()
        return resp

    def post(self, path: str, data: dict | None = None, **kwargs) -> httpx.Response:
        resp = self.http.post(path, data=data, headers={"X-Requested-With": "XMLHttpRequest"}, **kwargs)
        resp.raise_for_status()
        return resp

    def close(self) -> None:
        self.http.close()
