# Karmed derma export — working notes

Goal: export every patient's appointments and full clinical history from the
Karmed derma web app (`modules/pacientes`) into Excel, shaped like the
dermatology record model that the billing system imports. The target URL is
configured via `KARMED_URL` (see `.env.example`), never committed.

## Findings
- PHP + jQuery app. Login is `POST modules/consulta_acceso.php` with
  `clien`, `clav`, `sucu` (PHP session cookie). Response `""` = bad credentials,
  `Inactivo` = inactive user, `REN` = branch required (`KARMED_BRANCH`).
- After login the site redirects to `modules/agenda`.
- Patient search needs a term; typing `1` returns results.
- No browser needed so far: `httpx` with the session cookie.

## Status
- [x] Project scaffold (uv, httpx, pandas, openpyxl, playwright)
- [x] `karmed/client.py` login/session client
- [x] `recon.py` written, NOT run yet (needs `.env` credentials)
- [ ] Run `uv run python recon.py`, map patient list / appointment / history endpoints
- [ ] Full patient ID list (pagination, not dependent on the "1" search)
- [ ] Per-patient extraction with resume (raw JSON/HTML under `raw/`)
- [ ] Excel output matching the billing import format (format still pending)
- [ ] Reconciliation: counts on site vs exported, error log

## Rules
- Patient data stays local only (`raw/`, `output/` are gitignored).
- Credentials only in `.env`, never in chat or commits.
