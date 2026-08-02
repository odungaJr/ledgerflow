# LedgerFlow — Status

**Last updated:** 2026-08-02 (fix: clear-all-transactions leftover dedupe bug)

For the full "why" behind any of these — architecture decisions, tradeoffs,
things fixed and why they broke — that detail lives in `RECAP.md` (kept
local, not in this repo).

---

## Current status

Live locally via Docker (`http://localhost`), multi-tenant (open
registration, every account's data is fully private), 187 backend tests
passing. Actively developed.

## Known blockers

- No public hosting yet — local only, no domain/HTTPS

## Changelog

- Fixed a real bug hit live: "Clear all transactions" only deleted
  `transactions`, not the new `imported_statements` records — so re-uploading
  a statement after a full wipe was wrongly rejected as a duplicate. The wipe
  now clears both; also cleaned up the stale leftover records this had
  already created on the real account
- Transactions table now shows which account each row belongs to; statement
  import accepts multiple files at once with a live progress meter (file X
  of N, per-file Imported/Duplicate/Failed status); re-uploading the exact
  same statement file to the same account is now detected and skipped
  before it's even parsed (new `imported_statements` table, migration 008);
  the P&L report can now be exported as a formatted PDF (via reportlab) in
  addition to the existing CSV export, generated only when the button is
  clicked
- Added a "Scan & categorise" button on the Transactions page — runs AI
  categorisation on demand over every currently-uncategorised transaction
  across all accounts (`POST /transactions/categorise-pending`), not just
  newly-imported ones. Auto-categorise-on-import already existed and needed
  no change. Live-verified end-to-end against the real local Ollama model.
- Replaced Anthropic Claude with a free, local Ollama model
  (`qwen2.5:7b-instruct`) for all AI features — categorisation, anomaly
  detection, and insights. Removes the Anthropic billing blocker entirely
  (no API key, no cost) and verified live end-to-end for the first time
  (categorisation, anomaly detection, and the trends/insights narrative all
  producing correct real output, not just the graceful-failure path)
- Added per-IP rate limiting on `/auth/login` (10/min) and `/auth/register`
  (5/min), on top of the existing per-account lockout; added a GitHub
  Actions workflow that runs the backend test suite on every push/PR
- Re-verified multi-tenant isolation with a second live test account
  (created, checked, deleted cleanly — cascade delete left no orphaned rows)
- Compacted this changelog from a dense per-change log into short bullets;
  the detailed version now lives only in `RECAP.md`
- Added a project `README.md`; scrubbed a stray personal reference from a
  migration docstring and fixed a stale `docker-compose.yml` comment
- Multi-tenant data isolation — every registered user now gets fully
  private accounts, transactions, budgets, income, assets, liabilities, and
  categories, instead of one shared dataset. Verified live with a real
  second test account.
- Added a Liabilities/debts tracker, folded into a Net Worth section on the
  Dashboard (assets, liabilities, and the combined trend)
- Added Dashboard charts (income vs. expenses, category spend) and a
  login-page/nav-bar logo
- Removed the unused `SECRET_KEY` env var
- Added a Settings page (theme, account security, category management) and
  a custom-date-range P&L statement with CSV export
- Login hardening: lockout after repeated failed attempts, idle session
  timeout, change-password
- Added account balances (from imports or keyed in manually) and a "clear
  all transactions" reset
- Moved the active deployment off EC2 to a local Docker stack (cost); real
  data backed up and restored
- Fixed the Dashboard defaulting to an empty period in certain cases;
  grouped the nav bar's planning links into a dropdown
- Fixed all-time income totals counting not-yet-due future occurrences
- Fixed a timezone bug in "today's date" that misfired east of UTC
- Added all-time income totals to the Income page and Dashboard
- Added real app-level authentication (replacing Caddy Basic Auth):
  users/sessions, bcrypt, session cookies
- Added bulk transaction categorisation and clickable Dashboard drill-downs
- Added an Income tracker (one-off and recurring entries) and an Assets
  tracker (dated value history, net worth)
- Deployed to a real AWS EC2 test server over SSH; fixed two bugs only a
  fresh deploy could surface (an empty `public/` dir git didn't track, and
  Docker Compose's `.env` interpolation corrupting bcrypt hashes)
- Fixed the PDF importer against real bank statements (was 0-for-6);
  rewrote it to be header-aware with a word-position fallback tier
- Locked down Postgres to loopback-only; added HTTP Basic Auth in front of
  the whole stack via Caddy (later replaced by app-level auth above)
- Built the frontend (Next.js): Dashboard, Accounts, Transactions, Budgets
  pages wired to the real API
- Added deploy prep: Dockerfiles for backend/frontend, `docker-compose.yml`
  wiring db + backend + frontend
- Shrank the backend Docker image ~33% by dropping pandas from the CSV
  importer
- Added an `/accounts` CRUD router and a `/categories` endpoint
- Hardened CSV import against partial failures (per-row rollback,
  graceful AI-response handling); added the first pytest suite
- Initialized git, pushed to a private GitHub repo
