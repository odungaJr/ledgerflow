# Personal Fintech — FinTrack
**Last updated:** 2026-07-15

---

## Current Status
In Progress

## What I'm Working On
Hardening the LedgerFlow backend (FastAPI + PostgreSQL + Claude-powered categorisation) — fixing reliability gaps found through testing and getting the project onto solid engineering footing (git, tests, a working local dev setup) before starting the frontend.

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

## Blockers
- No `ANTHROPIC_API_KEY` configured locally, so AI categorisation/insights are untested against the real Claude API (only the failure path is verified so far)

## Next Steps
- Decide on a frontend approach (CORS is already configured for a Next.js dev server on `localhost:3000`, but no frontend exists yet)
- Set a real `ANTHROPIC_API_KEY` locally and verify the AI categorisation/insights happy path

## Notes
- Local dev now requires Python 3.10+ and PostgreSQL — see `Personal finance/ledgerflow/backend/requirements-dev.txt` and `pytest.ini` for the test setup
- `fintrack-archive.json` (repo root) was removed — it was an empty, unreferenced stub from an earlier "FinTrack" naming pass, with no accounts/transactions and no code reading it
