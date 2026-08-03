#!/usr/bin/env bash
# Auto-resolve the backend's missing-module chain, then boot the REAL Mycelium-EI on 5055.
set +e
cd ~/mycelium-earth-intelligence/vendor/mycelium-ei || { echo NO_DIR; exit 2; }
PY=.venv/bin/python
pipname() {
  case "$1" in
    flask_compress) echo Flask-Compress;; flask_cors) echo Flask-Cors;;
    flask_caching) echo Flask-Caching;; flask_socketio) echo Flask-SocketIO;;
    flask_login) echo Flask-Login;; flask_migrate) echo Flask-Migrate;;
    flask_limiter) echo Flask-Limiter;; flask_wtf) echo Flask-WTF;;
    paho) echo paho-mqtt;; jwt) echo PyJWT;; jose) echo python-jose;;
    dotenv) echo python-dotenv;; yaml) echo pyyaml;; cv2) echo opencv-python;;
    dateutil) echo python-dateutil;; bs4) echo beautifulsoup4;;
    *) echo "${1//_/-}";;
  esac
}
for i in $(seq 1 25); do
  err=$($PY -c "from app import app" 2>&1)
  if [ -z "$err" ]; then echo "IMPORT_OK after $((i-1)) installs"; break; fi
  mod=$(echo "$err" | grep -oE "No module named '[^']+'" | head -1 | sed -E "s/No module named '([^.']+).*/\1/")
  if [ -z "$mod" ]; then echo "NON-IMPORT ERROR (not a missing module):"; echo "$err" | tail -18; break; fi
  pkg=$(pipname "$mod")
  echo "missing '$mod' -> installing $pkg"
  uv pip install --python $PY "$pkg" >/dev/null 2>&1 || { echo "INSTALL FAILED: $pkg"; break; }
done
mkdir -p instance
pkill -f "vendor/mycelium-ei/.venv/bin/python main.py" 2>/dev/null
echo "=== boot on 5055 ==="
FLASK_ENV=development PORT=5055 nohup $PY main.py > /tmp/mei_run.log 2>&1 &
sleep 15
echo "=== run log ==="; tail -22 /tmp/mei_run.log
echo "=== probe ==="
for p in 5055 5050 8000 8080 5001; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$p/" 2>/dev/null)
  [ -n "$code" ] && [ "$code" != "000" ] && echo "LIVE PORT $p -> HTTP $code"
done
