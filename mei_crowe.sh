#!/usr/bin/env bash
# Power Mycelium-EI with OUR local models (Ollama: crowelogic / CroweLM), not OpenAI. Boot on 5055.
set +e
cd ~/mycelium-earth-intelligence/vendor/mycelium-ei || { echo NO_DIR; exit 2; }
PY=.venv/bin/python

# ensure Ollama is serving
if ! curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
  echo "starting ollama serve..."; nohup ollama serve >/tmp/ollama.log 2>&1 & sleep 5
fi
NMODELS=$(curl -s http://localhost:11434/api/tags 2>/dev/null | python3 -c "import sys,json;print(len(json.load(sys.stdin).get('models',[])))" 2>/dev/null)
echo "ollama models available: ${NMODELS:-0}"

# alias the code's hardcoded 'gpt-4o' to OUR local CroweLM model so AI calls hit our stack
ollama cp crowelogic gpt-4o 2>&1 | tail -1

# route the OpenAI SDK at local Ollama (OpenAI-compatible) using OUR model
export OPENAI_BASE_URL="http://localhost:11434/v1"
export OPENAI_API_KEY="ollama"

# auto-resolve remaining missing modules
pipname(){ case "$1" in flask_compress) echo Flask-Compress;; flask_cors) echo Flask-Cors;; flask_caching) echo Flask-Caching;; flask_socketio) echo Flask-SocketIO;; flask_login) echo Flask-Login;; flask_migrate) echo Flask-Migrate;; paho) echo paho-mqtt;; jwt) echo PyJWT;; dotenv) echo python-dotenv;; yaml) echo pyyaml;; *) echo "${1//_/-}";; esac; }
for i in $(seq 1 20); do
  err=$($PY -c "from app import app" 2>&1)
  [ -z "$err" ] && { echo "IMPORT_OK"; break; }
  mod=$(echo "$err" | grep -oE "No module named '[^']+'" | head -1 | sed -E "s/No module named '([^.']+).*/\1/")
  [ -z "$mod" ] && { echo "NON-IMPORT ERROR:"; echo "$err" | tail -16; break; }
  echo "installing for '$mod' -> $(pipname $mod)"; uv pip install --python $PY "$(pipname $mod)" >/dev/null 2>&1
done

mkdir -p instance
pkill -f "vendor/mycelium-ei/.venv/bin/python main.py" 2>/dev/null; sleep 1
echo "=== boot (powered by local CroweLM via Ollama) ==="
OPENAI_BASE_URL="http://localhost:11434/v1" OPENAI_API_KEY="ollama" FLASK_ENV=development PORT=5055 nohup $PY main.py > /tmp/mei_run.log 2>&1 &
sleep 16
echo "=== run log ==="; tail -20 /tmp/mei_run.log
echo "=== probe ==="
for p in 5055 5050 8000 8080; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$p/" 2>/dev/null)
  [ -n "$code" ] && [ "$code" != "000" ] && echo "LIVE PORT $p -> HTTP $code  (backend http://100.75.26.39:$p)"
done
