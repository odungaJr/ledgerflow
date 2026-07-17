# Personal Fintech — FinTrack
**Last updated:** 2026-07-16

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

## Blockers
- Anthropic account has insufficient credit balance — API calls fail with `400: Your credit balance is too low to access the Anthropic API`. Needs billing/credits added at console.anthropic.com before the AI categorisation/insights happy path can be verified

## Next Steps
- Add credits/billing to the Anthropic account, then re-verify AI categorisation and insights generation end-to-end

## Notes
- Local dev now requires Python 3.10+, PostgreSQL, and Node.js — see `Personal finance/ledgerflow/backend/requirements-dev.txt`/`pytest.ini` (backend tests) and `Personal finance/ledgerflow/frontend/.env.example` (frontend API URL)
- `fintrack-archive.json` (repo root) was removed — it was an empty, unreferenced stub from an earlier "FinTrack" naming pass, with no accounts/transactions and no code reading it
- **Security note:** `backend/.env.example` was briefly edited in the working tree to contain the real `ANTHROPIC_API_KEY` instead of a placeholder — caught before any commit, reverted to the placeholder. It was never in git history. Keep real secrets only in `backend/.env` (gitignored), never in the `.example` files
