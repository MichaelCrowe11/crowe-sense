#!/usr/bin/env bash
# Crowe Sense dashboard launcher: ensure the server is up, then open it fullscreen.
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"
export DISPLAY="${DISPLAY:-:0}"

# make sure the telemetry server is running
systemctl --user start crowe-sense-dashboard.service 2>/dev/null

# wait for it to answer (up to ~10s)
for i in $(seq 1 20); do
  if curl -s -m 2 -o /dev/null http://127.0.0.1:8078/; then break; fi
  sleep 0.5
done

exec chromium --app=http://localhost:8078/ \
  --start-fullscreen --no-first-run --password-store=basic \
  --disable-infobars --disable-session-crashed-bubble
