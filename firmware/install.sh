#!/usr/bin/env bash
# Crowe Sense node installer for a fresh Raspberry Pi OS Lite (64-bit) install.
# Usage, as the login user on the Pi, from the kit directory copied to /boot/firmware/crowe-kit
# (or anywhere): sudo bash install.sh /path/to/kit
# The kit holds: firmware/ (this source tree), etc-crowe/ (node.toml, node.key, node.pub), and
# optionally wifi.txt. Everything the setup pipeline (docs/setup-pipeline.md, step 3) does by hand.
set -euo pipefail
KIT="${1:-$(cd "$(dirname "$0")/.." && pwd)}"
FW="$KIT/firmware"; ETC="$KIT/etc-crowe"
[ -f "$ETC/node.toml" ] || { echo "no $ETC/node.toml: run crowe-provision into the kit first"; exit 1; }
[ "$(id -u)" = 0 ] || { echo "run with sudo"; exit 1; }
RUNUSER="${SUDO_USER:-crowe}"
echo "== Crowe Sense install: kit $KIT, service user $RUNUSER"
echo "== 1. I2C on, packages"
raspi-config nonint do_i2c 0 || true
apt-get update -qq && apt-get install -y -qq python3-pip python3-venv i2c-tools >/dev/null
echo "== 2. users and directories"
id crowe >/dev/null 2>&1 || adduser --system --group --home /var/lib/crowe crowe
usermod -aG i2c,gpio crowe || true
mkdir -p /opt/crowe /var/lib/crowe /etc/crowe; chown -R crowe:crowe /opt/crowe /var/lib/crowe
echo "== 3. firmware into a venv"
rm -rf /opt/crowe/src && cp -r "$FW" /opt/crowe/src && chown -R crowe:crowe /opt/crowe/src
[ -x /opt/crowe/venv/bin/python ] || python3 -m venv /opt/crowe/venv
/opt/crowe/venv/bin/pip install -q --upgrade pip
/opt/crowe/venv/bin/pip install -q /opt/crowe/src
ln -sf /opt/crowe/venv/bin/crowe-* /usr/local/bin/
echo "== 4. node identity from the kit (pre-provisioned)"
install -m 600 -o crowe -g crowe "$ETC/node.key" /etc/crowe/node.key
install -m 644 -o crowe -g crowe "$ETC/node.pub" /etc/crowe/node.pub
install -m 644 -o crowe -g crowe "$ETC/node.toml" /etc/crowe/node.toml
sed -i 's#private_key_path = .*#private_key_path = "/etc/crowe/node.key"#' /etc/crowe/node.toml
echo "== 5. systemd units"
cp /opt/crowe/src/systemd/crowe-{sampler,api,uploader,watchdog,health}.* /etc/systemd/system/
sed -i 's#Requires=mnt-crowe.mount##; s#/mnt/crowe#/var/lib/crowe#g' /etc/systemd/system/crowe-*.service
systemctl daemon-reload
systemctl enable --now crowe-sampler crowe-api crowe-uploader crowe-watchdog crowe-health.timer
echo "== 6. checks (the artifact, not the exit code)"
sleep 8
echo "-- i2c bus (expect 10 44 62 76 on a room node):"; i2cdetect -y 1 || true
echo "-- local API health:"; curl -s http://localhost:8078/health || echo "(api not answering yet)"
echo; echo "-- latest:"; curl -s http://localhost:8078/v1/latest | head -c 600 || true; echo
echo "== done. Node id: $(grep node_id /etc/crowe/node.toml). If /health shows ok:true with a rising readings count, the node is sampling; the uploader drains to the relay every 30 s once the node is paired."
