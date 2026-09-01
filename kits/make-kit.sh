#!/usr/bin/env bash
# Assemble a Crowe Sense SD-card kit: kits/<name>/ -> kits/<name>-kit.zip
# The zip unpacks to crowe-kit/{firmware,etc-crowe,install.sh,BUILD-SHEET.md}; copy crowe-kit/ onto the
# Pi's boot partition (shows as /boot/firmware on the Pi) and run:
#   sudo bash /boot/firmware/crowe-kit/install.sh /boot/firmware/crowe-kit
set -euo pipefail
NAME="${1:?kit name, e.g. harrison-lf-01}"; ROOT="$(cd "$(dirname "$0")/.." && pwd)"; KIT="$ROOT/kits/$NAME"
[ -f "$KIT/etc-crowe/node.toml" ] || { echo "no $KIT/etc-crowe/node.toml"; exit 1; }
STAGE="$(mktemp -d)/crowe-kit"; mkdir -p "$STAGE"
rsync -a --exclude '.venv' --exclude '__pycache__' --exclude '.pytest_cache' --exclude '.ruff_cache' --exclude '*.egg-info' "$ROOT/firmware/" "$STAGE/firmware/"
cp -r "$KIT/etc-crowe" "$STAGE/etc-crowe"; cp "$ROOT/firmware/install.sh" "$STAGE/install.sh"
[ -f "$ROOT/hardware/harrison-node/BUILD-SHEET.md" ] && cp "$ROOT/hardware/harrison-node/BUILD-SHEET.md" "$STAGE/BUILD-SHEET.md"
( cd "$(dirname "$STAGE")" && rm -f "$ROOT/kits/$NAME-kit.zip" && zip -qr "$ROOT/kits/$NAME-kit.zip" crowe-kit )
echo "kit: $ROOT/kits/$NAME-kit.zip ($(du -h "$ROOT/kits/$NAME-kit.zip" | cut -f1)); node: $(grep node_id "$KIT/etc-crowe/node.toml")"
