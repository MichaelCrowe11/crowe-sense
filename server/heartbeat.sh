#!/bin/bash
# Crowe Sense heartbeat monitor.
# Polls the Pi telemetry API and texts an alert when the rig goes down or the
# daemon stalls, so a silent multi-day outage (like the 81h gap in June 2026)
# cannot happen again. Runs every 10 min via launchd. Deduped: one text per
# outage, plus one when it recovers.

set -uo pipefail

API="http://100.123.229.57:8077/health"
DIR="$HOME/crowe-sense-monitor"
STATE="$DIR/state"
LOG="$DIR/heartbeat.log"
SENDER="$DIR/send-imessage.applescript"

# ---- WHO GETS THE ALERT ----------------------------------------------------
# Jordan (+16028739494) was removed on 2026-07-07: stop auto-texting him.
# Leave CONTACT empty to keep monitoring silently (alerts still land in the
# log below), or put your own number here to get the texts yourself.
CONTACT=""
# ---------------------------------------------------------------------------

STALL_POLLS=2   # consecutive no-new-reading polls (~20 min) before "stalled"
TS="$(date '+%Y-%m-%d %H:%M:%S')"

mkdir -p "$DIR"
prev_status=ok; prev_readings=0; stall_count=0; alerted=none
if [ -f "$STATE" ]; then
  read -r prev_status prev_readings stall_count alerted < "$STATE" 2>/dev/null || true
fi
[ -z "${prev_readings:-}" ] && prev_readings=0
[ -z "${stall_count:-}" ] && stall_count=0
[ -z "${alerted:-}" ] && alerted=none

send() { [ -n "$CONTACT" ] && osascript "$SENDER" "$CONTACT" "$1" >/dev/null 2>&1; }

resp="$(curl -s --max-time 12 "$API" 2>/dev/null)"
readings="$(printf '%s' "$resp" | python3 -c '
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get("readings", -1) if d.get("status") == "ok" else -1)
except Exception:
    print(-1)' 2>/dev/null)"
case "$readings" in ''|*[!0-9-]*) readings=-1;; esac

status=down
if [ "$readings" -ge 0 ]; then
  if [ "$readings" -gt "$prev_readings" ]; then
    status=ok; stall_count=0
  else
    stall_count=$((stall_count + 1))
    if [ "$stall_count" -ge "$STALL_POLLS" ]; then status=stalled; else status=ok; fi
  fi
fi

case "$status" in
  ok)
    if [ "$alerted" != none ]; then
      send "Crowe Sense recovered. Telemetry is logging again as of $TS. Total readings: $readings."
      alerted=none
    fi ;;
  down)
    if [ "$alerted" != down ]; then
      send "Crowe Sense ALERT: the grow sensor rig is unreachable as of $TS. The Raspberry Pi or the sense daemon is down and no data is being logged. Please power-cycle the Pi and confirm Tailscale is up."
      alerted=down
    fi ;;
  stalled)
    if [ "$alerted" != stalled ]; then
      send "Crowe Sense ALERT: the Pi is reachable but the sensor daemon stopped logging new readings as of $TS (stuck at $readings). The crowe-sense service likely needs a restart."
      alerted=stalled
    fi ;;
esac

# Keep the highest reading count as the baseline so an outage does not reset it.
[ "$readings" -lt "$prev_readings" ] && readings=$prev_readings
echo "$status $readings $stall_count $alerted" > "$STATE"
echo "$TS status=$status readings=$readings stall=$stall_count alerted=$alerted" >> "$LOG"
