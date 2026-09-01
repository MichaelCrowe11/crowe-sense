#!/usr/bin/env bash
set +e
cd ~/mycelium-earth-intelligence/vendor/mycelium-ei || { echo NO_DIR; exit 2; }
PY=.venv/bin/python
ABS="$(pwd)/instance"; mkdir -p "$ABS"; chmod 777 "$ABS" 2>/dev/null
DBURL="sqlite:///$ABS/mycelium.db"   # $ABS is absolute -> yields sqlite:////... (absolute)
echo "DB: $DBURL"
export OPENAI_BASE_URL="http://localhost:11434/v1" OPENAI_API_KEY="ollama"
export DATABASE_URL="$DBURL"
pkill -f "vendor/mycelium-ei/.venv/bin/python main.py" 2>/dev/null; sleep 1
echo "=== boot (CroweLM via Ollama + absolute sqlite) ==="
DATABASE_URL="$DBURL" OPENAI_BASE_URL="http://localhost:11434/v1" OPENAI_API_KEY="ollama" \
  FLASK_ENV=development PORT=5055 nohup $PY main.py > /tmp/mei_run.log 2>&1 &
sleep 16
echo "=== run log ==="; tail -22 /tmp/mei_run.log
echo "=== probe + endpoints ==="
LIVE=""
for p in 5055 5050 8000 8080; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$p/" 2>/dev/null)
  if [ -n "$code" ] && [ "$code" != "000" ]; then echo "LIVE :$p HTTP $code"; LIVE="$p"; fi
done
if [ -n "$LIVE" ]; then
  echo "BACKEND_LIVE=http://100.75.26.39:$LIVE"
  for ep in / /health /api/health /api/dashboard /api/environmental /api/species /api/ai/mycelium; do
    echo -n "  $ep -> "; curl -s -o /dev/null -w "%{http_code}\n" "http://127.0.0.1:$LIVE$ep" 2>/dev/null
  done
fi
