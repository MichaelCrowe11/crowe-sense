#!/usr/bin/env bash
# Launch the REAL Mycelium-EI backend; supply OPENAI_API_KEY (real from secrets, else placeholder).
set +e
cd ~/mycelium-earth-intelligence/vendor/mycelium-ei || { echo NO_DIR; exit 2; }
[ -f ~/.env.secrets ] && source ~/.env.secrets 2>/dev/null
KEY="${OPENAI_API_KEY:-}"
if [ -z "$KEY" ]; then
  KEY="sk-mei-dev-placeholder-boot-only"
  echo "OPENAI_KEY: placeholder (no real key found; LLM features will 401, data endpoints work)"
else
  echo "OPENAI_KEY: real key found in env/secrets (LLM features active)"
fi
mkdir -p instance
pkill -f "vendor/mycelium-ei/.venv/bin/python main.py" 2>/dev/null; sleep 1
OPENAI_API_KEY="$KEY" FLASK_ENV=development PORT=5055 nohup .venv/bin/python main.py > /tmp/mei_run.log 2>&1 &
echo "booting (pid $!)..."; sleep 16
echo "=== run log ==="; tail -22 /tmp/mei_run.log
echo "=== probe + sample endpoints ==="
LIVE=""
for p in 5055 5050 8000 8080 5001; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$p/" 2>/dev/null)
  if [ -n "$code" ] && [ "$code" != "000" ]; then echo "LIVE PORT $p -> HTTP $code"; LIVE="$p"; fi
done
if [ -n "$LIVE" ]; then
  echo "BACKEND_LIVE=http://100.75.26.39:$LIVE"
  for ep in / /health /api/health /api/environmental/current /api/dashboard /api/species; do
    echo -n "  $ep -> "; curl -s -o /dev/null -w "%{http_code}\n" "http://127.0.0.1:$LIVE$ep" 2>/dev/null
  done
fi
