# Scripts

## healthcheck.sh

Watchdog for the local Docker stack's public front door (`http://localhost`,
served by Caddy). Runs on a schedule (see below), and on each run:

1. Checks `http://localhost` for a `200`.
2. If it's not up, runs `docker compose restart caddy` (the fix for the
   `resource deadlock avoided` Docker-Desktop-for-Mac mount glitch that
   originally took Caddy down — see `RECAP.md` for the story) and re-checks.
3. Fires a native macOS notification only on a state *transition* — going
   down, recovering after a self-heal restart, or still down after the
   restart attempt — not on every run, so a sustained outage doesn't spam
   notifications every 2 minutes.

Logs to `/tmp/ledgerflow_healthcheck.log`; state tracked in
`/tmp/ledgerflow_healthcheck_state`.

This is the second layer of defense — `docker-compose.yml` already sets
`restart: unless-stopped` on every service plus a real healthcheck on
Caddy, so most crashes self-heal via Docker alone within seconds. This
watchdog exists for the cases Docker's own restart policy doesn't cover
(e.g. Docker Desktop itself not running) and to actually *notify* someone,
which a silent restart doesn't do.

### Setup (one-time, per machine)

**The script that actually runs must NOT live under `~/Documents` (or
Desktop/Downloads).** macOS's TCC privacy protection blocks LaunchAgents
(and other launchd-spawned processes) from reading files in those folders
even when they're world-readable and Terminal.app can read them fine —
Terminal has its own separate, previously-granted access; a fresh launchd
child does not inherit it. The failure is silent and easy to miss: the job
"runs" (`launchctl list` shows a normal exit status) but every invocation
actually fails immediately with `zsh: can't open input file`, visible only
in the stderr log — nothing on screen suggests anything is wrong, and
`docker ps` still shows Caddy healthy because Docker's own `restart:
unless-stopped` was independently working. Hit exactly this the first time
this watchdog was set up (2026-08-27).

So: keep the tracked copy here in the repo (`healthcheck.sh`), but install
the copy that actually executes to `~/Library/Application Support/`
instead — not TCC-protected — and point the LaunchAgent at *that* copy.

```bash
mkdir -p ~/Library/Application\ Support/ledgerflow-healthcheck
cp scripts/healthcheck.sh ~/Library/Application\ Support/ledgerflow-healthcheck/healthcheck.sh
chmod +x ~/Library/Application\ Support/ledgerflow-healthcheck/healthcheck.sh

cp scripts/com.moxplosion.ledgerflow.healthcheck.plist.template \
   ~/Library/LaunchAgents/com.moxplosion.ledgerflow.healthcheck.plist
launchctl load ~/Library/LaunchAgents/com.moxplosion.ledgerflow.healthcheck.plist
```

If you ever edit `healthcheck.sh` in the repo, re-copy it to the Application
Support location afterward — that's the copy that actually runs, the repo
copy is just the tracked source.

To check it's running: `launchctl list | grep ledgerflow` (exit status `0`
after a run). To force an immediate run instead of waiting for the next
2-minute interval: `launchctl start com.moxplosion.ledgerflow.healthcheck`.

To uninstall:

```bash
launchctl unload ~/Library/LaunchAgents/com.moxplosion.ledgerflow.healthcheck.plist
rm ~/Library/LaunchAgents/com.moxplosion.ledgerflow.healthcheck.plist
rm -rf ~/Library/Application\ Support/ledgerflow-healthcheck
```
