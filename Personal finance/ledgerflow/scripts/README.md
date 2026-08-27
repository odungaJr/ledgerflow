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

`com.moxplosion.ledgerflow.healthcheck.plist.template` is the LaunchAgent
definition. The live copy lives outside this repo (`~/Library/LaunchAgents/`
is a personal machine path, not project source) and needs the absolute path
inside it to match wherever this repo is checked out. To install:

```bash
cp scripts/com.moxplosion.ledgerflow.healthcheck.plist.template \
   ~/Library/LaunchAgents/com.moxplosion.ledgerflow.healthcheck.plist
# edit the ProgramArguments path inside if this repo isn't at the same
# location as when the template was generated
chmod +x scripts/healthcheck.sh
launchctl load ~/Library/LaunchAgents/com.moxplosion.ledgerflow.healthcheck.plist
```

To check it's running: `launchctl list | grep ledgerflow`.

To uninstall:

```bash
launchctl unload ~/Library/LaunchAgents/com.moxplosion.ledgerflow.healthcheck.plist
rm ~/Library/LaunchAgents/com.moxplosion.ledgerflow.healthcheck.plist
```
