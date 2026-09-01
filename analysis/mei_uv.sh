#!/usr/bin/env bash
# Build backend env with uv + Python 3.12 (reliable wheels), boot real Mycelium-EI on 5055.
set +e
cd ~/mycelium-earth-intelligence/vendor/mycelium-ei || { echo NO_DIR; exit 2; }
rm -rf .venv
uv venv --python 3.12 .venv 2>&1 | tail -2
echo "venv py: $(.venv/bin/python --version 2>&1)"
echo "=== uv install deps (fast) ==="
uv pip install --python .venv/bin/python -r requirements.txt openai 2>&1 | tail -6
echo "installed:"; uv pip list --python .venv/bin/python 2>/dev/null | grep -iE "^(flask|sqlalchemy|numpy|pandas|scikit-learn|openai|structlog)" | head
echo "=== port main.py binds (grep) ==="; grep -nE "app.run|\.run\(|PORT|port=" main.py | head -5
mkdir -p instance
pkill -f "vendor/mycelium-ei/.venv/bin/python main.py" 2>/dev/null
echo "=== boot ==="
FLASK_ENV=development PORT=5055 FLASK_RUN_PORT=5055 nohup .venv/bin/python main.py > /tmp/mei_run.log 2>&1 &
sleep 15
echo "=== run log ==="; tail -25 /tmp/mei_run.log
echo "=== probe ==="
for p in 5055 5050 8000 8080 5001 5500 8001; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$p/" 2>/dev/null)
  [ -n "$code" ] && [ "$code" != "000" ] && echo "LIVE PORT $p -> HTTP $code"
done
