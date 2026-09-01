#!/usr/bin/env bash
# Upgrade + launch the REAL Mycelium-EI backend: install deps, boot (SQLite dev), verify.
set +e
cd ~/mycelium-earth-intelligence/vendor/mycelium-ei || { echo "no backend dir"; exit 2; }
[ -d .venv ] || python3 -m venv .venv
echo "=== installing deps (numpy/pandas/sklearn/matplotlib + openai; takes a few min) ==="
.venv/bin/pip install -q --upgrade pip >/dev/null 2>&1
.venv/bin/pip install -r requirements.txt openai 2>&1 | tail -4
echo "PIP_DONE"
.venv/bin/pip list 2>/dev/null | grep -iE "^(flask|Flask-SQLAlchemy|SQLAlchemy|numpy|pandas|scikit-learn|openai|structlog) " | head

mkdir -p instance
pkill -f "vendor/mycelium-ei/.venv/bin/python main.py" 2>/dev/null
echo "=== booting real backend ==="
FLASK_ENV=development nohup .venv/bin/python main.py > /tmp/mei_run.log 2>&1 &
sleep 14
echo "=== backend run log ==="
tail -30 /tmp/mei_run.log
echo "=== port probe ==="
LIVE=""
for p in 5050 5000 8000 3000 8080 8081; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$p/" 2>/dev/null)
  if [ -n "$code" ] && [ "$code" != "000" ]; then echo "PORT $p -> HTTP $code"; LIVE="$p"; fi
done
if [ -n "$LIVE" ]; then
  echo "=== sample real endpoints on :$LIVE ==="
  for ep in / /health /api/health /api/environmental /api/ai/mycelium; do
    echo -n "  $ep -> "; curl -s -o /dev/null -w "%{http_code}\n" "http://127.0.0.1:$LIVE$ep" 2>/dev/null
  done
  echo "BACKEND_LIVE_PORT=$LIVE"
else
  echo "BACKEND_NOT_LIVE (see run log above for the import/boot error)"
fi
