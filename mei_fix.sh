#!/usr/bin/env bash
# Rebuild the backend venv cleanly and boot the REAL Mycelium-EI platform (avoid port 5000 / AirPlay).
set +e
cd ~/mycelium-earth-intelligence/vendor/mycelium-ei || { echo NO_DIR; exit 2; }
rm -rf .venv
python3 -m venv .venv || { echo VENV_FAIL; exit 3; }
echo "venv python: $(.venv/bin/python --version 2>&1)"
.venv/bin/python -m pip install -q --upgrade pip >/dev/null 2>&1
echo "=== installing deps (few min) ==="
.venv/bin/python -m pip install -r requirements.txt openai 2>&1 | tail -4
echo "PIP_RESULT=$?"
.venv/bin/python -m pip list 2>/dev/null | grep -iE "^(Flask|Flask-SQLAlchemy|SQLAlchemy|numpy|pandas|scikit-learn|openai|structlog) " | head
mkdir -p instance
pkill -f "vendor/mycelium-ei/.venv/bin/python main.py" 2>/dev/null
echo "=== booting on PORT 5055 ==="
FLASK_ENV=development PORT=5055 FLASK_RUN_PORT=5055 nohup .venv/bin/python main.py > /tmp/mei_run.log 2>&1 &
sleep 14
echo "=== run log ==="; tail -25 /tmp/mei_run.log
for p in 5055 5050 8000 8080 5001; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$p/" 2>/dev/null)
  [ -n "$code" ] && [ "$code" != "000" ] && echo "LIVE PORT $p -> HTTP $code"
done
