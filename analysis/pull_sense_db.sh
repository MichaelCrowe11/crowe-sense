#!/bin/bash
# Pull the Crowe Sense raw archive off the Pi, the moment the Pi is reachable again.
#
# Why this exists: the raw stream (3.6M+ readings at sub-minute cadence) lives ONLY on
# the Pi's storage. The aggregated tables we hold locally and on Zenodo
# (10.5281/zenodo.20722953) are hourly means, which cannot validate a 15-minute-horizon
# forecast. So the raw file is the asset, and it currently has no second copy.
#
# Usage:  bash pull_sense_db.sh [user@host]
# Default host is the Pi's last known Tailscale address.
set -uo pipefail

TARGET="${1:-sergikdropz@100.123.229.57}"
REMOTE_DB="/home/sergikdropz/.crowe-logic/sense.db"
DEST="$HOME/crowe-sense-archive"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="$DEST/sense-$STAMP.db"

mkdir -p "$DEST"

echo "== reaching $TARGET =="
if ! ssh -o BatchMode=yes -o ConnectTimeout=10 "$TARGET" true 2>/dev/null; then
  echo "FAIL: cannot reach $TARGET over ssh."
  echo "  The Pi was last known at 100.123.229.57 but is not currently in the tailnet."
  echo "  Power it on, confirm 'tailscale status' lists it, then re-run."
  echo "  Or pass a LAN address:  bash pull_sense_db.sh sergikdropz@raspberrypi.local"
  exit 1
fi

# A live SQLite file must not be copied byte-for-byte while it is being written.
# .backup takes a consistent snapshot even with WAL active.
echo "== snapshotting on the Pi (consistent, WAL-safe) =="
if ssh -o BatchMode=yes "$TARGET" "command -v sqlite3 >/dev/null && sqlite3 '$REMOTE_DB' \".backup /tmp/sense-snapshot.db\"" 2>/dev/null; then
  REMOTE_SRC="/tmp/sense-snapshot.db"
  echo "   snapshot created"
else
  echo "   sqlite3 not available on the Pi; falling back to copying db + wal + shm"
  REMOTE_SRC="$REMOTE_DB"
fi

echo "== copying =="
scp -o BatchMode=yes "$TARGET:$REMOTE_SRC" "$OUT" || { echo "FAIL: copy failed"; exit 1; }
if [ "$REMOTE_SRC" = "$REMOTE_DB" ]; then
  scp -o BatchMode=yes "$TARGET:$REMOTE_DB-wal" "$OUT-wal" 2>/dev/null
  scp -o BatchMode=yes "$TARGET:$REMOTE_DB-shm" "$OUT-shm" 2>/dev/null
fi
[ "$REMOTE_SRC" = "/tmp/sense-snapshot.db" ] && ssh -o BatchMode=yes "$TARGET" "rm -f /tmp/sense-snapshot.db" 2>/dev/null

# Verify the artifact, do not trust the exit code of scp.
echo "== verifying the copy =="
command -v sqlite3 >/dev/null || { echo "WARN: no local sqlite3, skipping verification"; exit 0; }
INTEG="$(sqlite3 "$OUT" 'PRAGMA integrity_check;' 2>&1 | head -1)"
ROWS="$(sqlite3 "$OUT" 'SELECT COUNT(*) FROM readings;' 2>&1)"
SPAN="$(sqlite3 "$OUT" "SELECT ROUND((MAX(epoch)-MIN(epoch))/86400.0,2) FROM readings;" 2>&1)"
RANGE="$(sqlite3 "$OUT" "SELECT datetime(MIN(epoch),'unixepoch')||' .. '||datetime(MAX(epoch),'unixepoch') FROM readings;" 2>&1)"
SHA="$(shasum -a 256 "$OUT" | cut -d' ' -f1)"

{
  echo "file:      $(basename "$OUT")"
  echo "pulled:    $STAMP  from $TARGET:$REMOTE_DB"
  echo "integrity: $INTEG"
  echo "readings:  $ROWS"
  echo "span_days: $SPAN"
  echo "range_utc: $RANGE"
  echo "sha256:    $SHA"
  echo "bytes:     $(wc -c < "$OUT" | tr -d ' ')"
} | tee "$OUT.manifest.txt"

if [ "$INTEG" != "ok" ]; then
  echo
  echo "WARNING: integrity_check did not return ok. Do NOT delete the Pi's copy."
  exit 2
fi

echo
echo "OK. Raw archive now has a second copy at $OUT"
echo "Next: add it to the vault, and only then consider reusing the Pi's storage."
