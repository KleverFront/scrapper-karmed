# Karmed Export

Local web app to search and export patients and appointments (citas) from the
Karmed derma web app into Excel. It runs entirely on your machine
(`127.0.0.1`), stores credentials only in a local `.env`, and keeps all
exported data on disk — nothing is sent anywhere else.

## Features

- **Fast patient search** — queries the server's own name/cédula filter (~1s),
  no need to download the whole list first.
- **Export to Excel** — the current search result, or the full patient list.
- **Appointments (citas)** — export every appointment from the agenda to Excel.
- **Editable configuration** — set the base URL, user, password and branch from
  the UI; saved to `.env`.
- **Offline cache** — the full patient list is cached locally, so reopening is
  instant.
- **Background loading** — long fetches run in the background with live status.
- **Single-instance** launcher with a dynamic local port that auto-opens the
  browser.

## Requirements

- [uv](https://docs.astral.sh/uv/)

## Setup

```bash
uv sync
cp .env.example .env
```

Then edit `.env` (or use the **Configuración** panel in the app) and set:

```ini
KARMED_URL=https://your-server/derma/
KARMED_USER=your-user
KARMED_PASS=your-password
# KARMED_BRANCH=   # only if the login requires a branch
# KARMED_PORT=     # optional, defaults to 8771
```

## Run

```bash
uv run karmed-ui
```

Your browser opens at `http://127.0.0.1:8771`. Type a name to search, then
**Exportar a Excel**. Use **Cargar todos** only when you need the entire patient
list in one file. Use **Exportar todas las citas** for appointments.

## Standalone launcher

Build a single executable (no Python required on the target machine) for macOS
or Windows — see [`BUILD.md`](BUILD.md). A GitHub Actions workflow builds both.

## Privacy

This tool handles personal medical data. By design:

- Credentials live only in `.env` (gitignored, never committed).
- The target URL is provided via `KARMED_URL`, never hardcoded.
- Exported files (`exports/`), the cache (`data/`) and any raw dumps (`raw/`)
  are gitignored and stay on your machine.

You are responsible for using this only against systems you are authorized to
access, and for safeguarding the exported data.
