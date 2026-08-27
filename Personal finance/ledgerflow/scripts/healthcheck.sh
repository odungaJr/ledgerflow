#!/bin/zsh
# LedgerFlow health watchdog — run periodically via a LaunchAgent (see
# README.md in this directory for the template and setup steps). Checks
# the public front door (Caddy, http://localhost),
# tries a self-heal restart if it's down, and fires a native macOS
# notification on the transition into/out of a down state (not on every
# check, so a sustained outage doesn't spam notifications every run).
#
# State file tracks whether the last check was up or down, so the alert only
# fires once per incident, plus once more when it recovers.

set -u

PROJECT_DIR="/Users/mosesodunga/Documents/20_Projects/25_Personal_Fintech/Personal finance/ledgerflow"
STATE_FILE="/tmp/ledgerflow_healthcheck_state"
LOG_FILE="/tmp/ledgerflow_healthcheck.log"

notify() {
  local title="$1"
  local message="$2"
  osascript -e "display notification \"${message}\" with title \"${title}\" sound name \"Basso\"" >/dev/null 2>&1
}

log() {
  echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >> "$LOG_FILE"
}

http_code=$(curl -s -o /dev/null -m 5 -w "%{http_code}" http://localhost/ 2>/dev/null)
previous_state=$(cat "$STATE_FILE" 2>/dev/null || echo "up")

if [ "$http_code" = "200" ]; then
  if [ "$previous_state" = "down" ]; then
    log "RECOVERED (http $http_code)"
    notify "LedgerFlow is back up" "http://localhost is responding again."
  fi
  echo "up" > "$STATE_FILE"
else
  log "DOWN (http ${http_code:-no response}) — attempting self-heal restart of caddy"
  (cd "$PROJECT_DIR" && /usr/local/bin/docker compose restart caddy >> "$LOG_FILE" 2>&1)
  sleep 5
  retry_code=$(curl -s -o /dev/null -m 5 -w "%{http_code}" http://localhost/ 2>/dev/null)

  if [ "$retry_code" = "200" ]; then
    log "Self-heal succeeded after restart (http $retry_code)"
    if [ "$previous_state" != "down" ]; then
      notify "LedgerFlow briefly went down" "Caddy was unresponsive but restarted automatically and recovered."
    fi
    echo "up" > "$STATE_FILE"
  else
    log "Self-heal failed — still down (http ${retry_code:-no response})"
    if [ "$previous_state" != "down" ]; then
      notify "LedgerFlow is down" "http://localhost isn't responding and restarting Caddy didn't fix it. Check Docker Desktop."
    fi
    echo "down" > "$STATE_FILE"
  fi
fi
