#!/usr/bin/env bash
# Wait for deps, then boot the REAL Mycelium-EI Flask backend (SQLite, dev) and verify.
set +e
LOG=/tmp/mei_pip.log
cd ~/mycelium-earth-intelligence/vendor/mycelium-ei || exit 2

echo "waiting for pip install to finish..."
for i in $(seq 1 180); do
  grep -q MEI_PIP_DONE "$LOG" 2>/dev/null && break
  # also detect a hard pip failure
  grep -qiE "ERROR: Could not|No matching distribution|error: subprocess" "$LOG" 2>/dev/null && { echo "PIP_FAILED"; tail -8 "$LOG"; exit 3; }
  sleep 5
done
if ! grep -q MEI_PIP_DONE "$LOG" 2>/dev/null; then
  echo "PIP_STILL_RUNNING after wait"; tail -5 "$LOG"; exit 4
fi
echo "PIP_OK. installed packages (key):"
.venv/bin/pip list 2>/dev/null | grep -iE "flask|sqlalchemy|numpy|pandas|scikit|openai|structlog" | head

# boot the backend (SQLite default), capture log so we learn the port / any import error
mkdir -p instance
FLASK_ENV=development PORT=5050 nohup .venv/bin/python main.py > /tmp/mei_run.log 2>&1 &
echo "booting (pid $!)..."
sleep 10
echo "=== run log (shows port or import error) ==="
tail -25 /tmp/mei_run.log
# probe common ports
for p in 5050 5000 8000 3000; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$p/" 2>/dev/null)
  [ "$code" != "000" ] && [ -n "$code" ] && echo "PORT $p -> HTTP $code"
done
