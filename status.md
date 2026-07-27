# Personal Fintech — FinTrack
**Last updated:** 2026-07-27

---

## Current Status
In Progress

## What I'm Working On
Backend is hardened and tested. Now building out the frontend (Next.js) against the FastAPI API.

## Completed This Week
- Initialized git and pushed to a private GitHub repo (`odungaJr/ledgerflow`)
- Fixed a stale Claude model ID (`claude-sonnet-4-6` → `claude-sonnet-5`) in the insights generator
- Hardened CSV import against partial failures: a per-row SAVEPOINT so a duplicate fingerprint only skips that row, and malformed AI JSON responses no longer crash the whole import
- Added a pytest suite (31 tests) covering `importer.py` and `budget_engine.py`, using an in-memory SQLite fixture
- Found and fixed a real bug via testing: `_to_decimal()` returned `Decimal('NaN')` instead of `None` for blank/NaN CSV cells — this would have crashed on virtually every real bank statement import with separate Debit/Credit columns
- Upgraded `anthropic` 0.28.0 → 0.116.0 to fix an httpx incompatibility that broke app startup entirely
- Ran the app end-to-end locally for the first time: installed Python 3.11 (the code uses 3.10+ `X | None` syntax; the machine only had 3.9) and PostgreSQL 15 via Homebrew, added the missing `alembic.ini` (migrations couldn't run without it), and verified the import → categorise → budget → dashboard flow via curl and the Swagger UI
- Fixed import endpoints returning HTTP 500 even when the import itself succeeded — AI categorisation failures are now caught and reported via a `categorised` flag instead of crashing the request
- Removed the unused Redis service from `docker-compose.yml`
- Added an `/accounts` CRUD router (create/list/get/patch/delete) — previously the only way to get an account into the database was a direct SQL insert. 9 new router tests (40 total), verified end-to-end against real Postgres and the Swagger UI
- Added a `GET /categories` endpoint (needed for the frontend's category dropdowns; 2 more tests, 42 total)
- Built the frontend: `Personal finance/ledgerflow/frontend` (Next.js 16 + React 19 + TypeScript, plain responsive CSS, no framework). Dashboard, Accounts, Transactions (CSV import + inline categorisation), and Budgets pages, all wired to the real API. Responsive nav (hamburger below 720px), tables collapse to stacked cards on narrow screens. Verified end-to-end at 375px and 1280px against real Postgres data, including creating records through the actual forms
- Added a real `ANTHROPIC_API_KEY` to `backend/.env` and confirmed it authenticates correctly against the Claude API (uvicorn's `--env-file` flag loads it before the app imports, no code change needed). The reliability fix from earlier worked as intended under a real failure: import still returned HTTP 200 with `categorised: false` and the transactions were persisted correctly
- Made AI categorisation opt-in per import: `auto_categorise` form field on `/transactions/import/{csv,pdf}` (default `true`), plus an "Auto-categorise with AI" checkbox on the Transactions import form. When unchecked, the AI call is skipped entirely rather than attempted-and-caught. 2 new tests (44 total)
- Frontend polish on the Transactions page: PDF import now works from the same form (routes to `/import/pdf` vs `/import/csv` based on file extension), added a `search` query param to the backend list endpoint plus filter UI (search, category, type, date range, clear filters), made `notes` editable inline per row, and added "Load more" pagination (50/page). 4 new backend tests (48 total). Verified live: search filtering, note persistence across reload, and pagination all confirmed against a real 65-row dataset in the browser
- Deploy prep: added `Dockerfile` + `.dockerignore` for both `backend` (Python 3.11-slim, runs `alembic upgrade head` on startup before serving) and `frontend` (Next.js standalone output, multi-stage build), wired both into `docker-compose.yml` alongside `db` with healthchecks and `depends_on: condition: service_healthy`. Made CORS origins configurable via `CORS_ORIGINS` env var (was hardcoded to localhost:3000). Removed `pytesseract` from `requirements.txt` — declared but never actually imported/used anywhere, so it was dead weight that would've meant installing the tesseract-ocr system package for nothing. Installed Docker (via colima, no Docker Desktop needed) to actually build and run the full stack — verified end-to-end in the browser: `docker compose up` brings up db → backend (migrates automatically) → frontend, account creation through the real UI confirmed working against the fully containerised stack
- Clarified that `docker-compose.yml` already builds both images from source at the destination (`build: context:`) — deploying anywhere only means `git clone` + `docker compose up --build`, no manual image copying. Also shrank the backend image on request: rewrote `importer.py`'s CSV parsing from pandas to the stdlib `csv` module (was only ever used for `pd.read_csv` + date parsing) — cut the backend image from 688MB to 460MB (-33%). Rebuilt `_parse_date` on `datetime.strptime` with an expanded explicit format list instead of pandas' fuzzy `dayfirst` inference. Verified with a from-scratch venv (confirming pandas is fully gone from the dependency tree), the full test suite (48 passed), and a live CSV import through the rebuilt Docker image producing byte-for-byte identical parsed output to before
- Locked down Postgres in `docker-compose.yml`: bound to `127.0.0.1:5432` instead of all interfaces (`0.0.0.0`), so it's no longer reachable from outside the host machine on a remote deployment. Backend/frontend still reach it fine via the internal Docker network (`db:5432`); local `psql -h 127.0.0.1` debugging still works too. Verified live: full stack up, app functional, `docker port` confirms the loopback-only binding
- Backend port 8000 stays publicly exposed by design (unlike Postgres) — the frontend is client-rendered, so users' browsers call the backend directly via `NEXT_PUBLIC_API_URL`/CORS. Locking it to `127.0.0.1` would break the app for every real user
- Added HTTP Basic Auth in front of the whole stack via a new `caddy` service + `Caddyfile`. Backend and frontend no longer publish host ports at all (`expose` only) — Caddy is now the sole public entry point on port 80, gating everything behind one login before forwarding: `/api/*` (prefix stripped) → backend, everything else → frontend. Same origin from the browser's perspective, so one login covers both and there's no CORS complication. `NEXT_PUBLIC_API_URL` defaults to the relative `/api` for this stack.
- **Deployed to a real AWS EC2 test server** (Ubuntu 26.04, x86_64) via SSH — first genuine test of "build from source at the destination" on different hardware/architecture than the Mac this was developed on. Used a dedicated read-only GitHub deploy key (via `gh repo deploy-key add`) rather than sharing broader credentials. Found and fixed two real bugs that only a fresh clone/deploy could surface:
  - `frontend/public/` was empty and git never tracked it (git doesn't track empty directories) — every local Docker build in this session had silently reused the leftover directory on disk instead of what was actually in the repo. Fixed with a `.gitkeep` ([PR #1](https://github.com/odungaJr/ledgerflow/pull/1)).
  - Docker Compose's own `.env` interpolation mangles bcrypt hashes: it treats a bare `$word` inside any `.env` value as a variable reference and blanks it out if unset, which silently corrupted `BASIC_AUTH_PASSWORD_HASH` (bcrypt hashes are `$`-heavy, e.g. `$2a$14$...`). Fixed by switching the `caddy` service from `environment: ${VAR}` to `env_file: .env` and documenting that the hash must have every `$` doubled to `$$` in `.env.example` (with a `sed` one-liner that does it automatically). Trade-off: lost the `:?`-based fail-fast check for a missing hash in the process — Caddy will just reject an empty/invalid one at its own startup instead.
- Verified live against the real deployed site (not just local): no/wrong credentials → 401 on both the page and `/api/*`, correct credentials → dashboard loads and account creation works through the actual browser UI over the public internet
- **Fixed the PDF importer against real bank statements** (the user's actual statements from 2 different banks, 6 files total) — it extracted zero transactions from every one of them before this fix. Root causes were more fundamental than a single bug: the parser assumed a fixed column *position* (date, description, debit, credit, balance) rather than reading column *names*, so any bank with a different layout failed silently.
  - Rewrote PDF table parsing to be header-aware (`_map_pdf_columns`), reusing the same alias system the CSV importer already had — handles extra columns (SN, Channel ID), reordered columns (Deposit before Withdrawal), and differently-named date columns (Trans Date vs Value Date vs Book Balance).
  - Fixed `_parse_date` to strip embedded time components (`"2026-04-17\n23:10:53"` → just the date) and normalise embedded newlines in multi-line PDF cells.
  - Added a new **word-position-based fallback parser** (`_parse_pdf_words`) for PDFs where pdfplumber's table/line-text extraction scrambles reading order entirely (one bank's statement had descriptions wrapping around the date, with amounts landing on a separate physical line from either) — reconstructs each transaction from word bounding-box coordinates instead, which stay reliable even when line-grouping doesn't. This is a general capability, not a single-bank hack.
  - Fixed a related bug the investigation surfaced: a table whose *header* matched the expected columns but whose *data rows* were all misaligned/empty was being wrongly treated as "successfully parsed," which skipped the fallback tiers entirely for that page.
  - One PDF has malformed encryption metadata that crashes `pdfminer` outright (a real bug in that library, not fixable from here) — now fails gracefully (0 transactions, no crash) instead of a 500.
  - Result across the 6 real statements: 0 → 325 correctly-extracted transactions (131 + 48 + 56 + 56 + 34), spot-checked against the source text for correct dates/amounts/direction/balance. 8 new tests (56 total in the suite).

## Blockers
- Anthropic account has insufficient credit balance — API calls fail with `400: Your credit balance is too low to access the Anthropic API`. Needs billing/credits added at console.anthropic.com before the AI categorisation/insights happy path can be verified

## Next Steps
- Add credits/billing to the Anthropic account, then re-verify AI categorisation and insights generation end-to-end
- If using a real domain for the EC2 site, switch the `Caddyfile`'s `:80`/`auto_https off` to the domain name for automatic HTTPS
- `CORS_ORIGINS` and an absolute `NEXT_PUBLIC_API_URL` are only relevant if running frontend/backend directly without Caddy (e.g. local dev)

## Deployed instance
- Live test deployment on AWS EC2 (HTTP Basic Auth gated — IP and credentials kept out of the repo, known locally)
- Deploy key `ec2-testing-server` (read-only) is registered on the GitHub repo for this server's `git pull` access

## Notes
- Local dev now requires Python 3.10+, PostgreSQL, and Node.js — see `Personal finance/ledgerflow/backend/requirements-dev.txt`/`pytest.ini` (backend tests) and `Personal finance/ledgerflow/frontend/.env.example` (frontend API URL)
- To run the full stack via Docker: copy `Personal finance/ledgerflow/.env.example` to `.env` in that same directory, then `docker compose up --build` from `Personal finance/ledgerflow/`
- `fintrack-archive.json` (repo root) was removed — it was an empty, unreferenced stub from an earlier "FinTrack" naming pass, with no accounts/transactions and no code reading it
- **Security note:** `backend/.env.example` was briefly edited in the working tree to contain the real `ANTHROPIC_API_KEY` instead of a placeholder — caught before any commit, reverted to the placeholder. It was never in git history. Keep real secrets only in `backend/.env` (gitignored), never in the `.example` files
