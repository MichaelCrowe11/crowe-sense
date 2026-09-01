# Setup pipeline: from parts on the bench to readings on every surface

Every step ends with a check you can see. Do not move to the next step on a green exit
code alone; the artifact named in each check is the proof.

## 0. Before the parts arrive (one afternoon, Michael)

| Step | Command or place | Check |
|---|---|---|
| Create the relay's D1 and R2 | `cd relay && env -u CLOUDFLARE_API_TOKEN npx wrangler d1 create crowe-sense` then paste the id into `wrangler.jsonc`; `npm run schema`; `env -u CLOUDFLARE_API_TOKEN npx wrangler r2 bucket create crowe-sense-raw` | `wrangler d1 execute crowe-sense --remote --command "select name from sqlite_master"` lists `nodes` and `readings` |
| Deploy the relay | `env -u CLOUDFLARE_API_TOKEN npx wrangler deploy` | `curl https://sense.crowelogic.com/health` returns `{"ok":true,"service":"crowe-sense-relay"}` and `curl -i https://sense.crowelogic.com/v1/nodes` returns 401 JSON |
| DNS | Cloudflare dashboard, zone crowelogic.com, `sense` proxied to the Worker route | the two curls above resolve |
| Deploy the web edge patch | `cd ~/crowe-logic-web && env -u CLOUDFLARE_API_TOKEN npx wrangler deploy` (patch already applied, backup at `src/index.js.bak-pre-sense`) | signed in at crowelogic.com, `/app/sense/v1/nodes` returns `{"nodes":[]}` |
| Merge the three app branches | `feat/crowe-sense` in crowe-logic-foundry, crowe-logic-desktop, crowe-cortex (patches in `integrations/*/patches/`) | each repo's own suite as recorded in `integrations/*/README.md` |
| Release the CLI | the usual 0.9.x recipe from a worktree | `pip install crowe-logic==<new>` then `crowe sense --help` lists seven subcommands |

## 1. Print the enclosure (14 h of printer time, 20 min of yours)

1. Install OpenSCAD (`brew install --cask openscad` on the Mac; it is not installed today).
2. Indoor build: `openscad -o body.stl site/model/crowe-sense-enclosure.scad` (parameters at the top of the file are sized to the Pi 5 and the Adafruit breakouts).
   Field build: `hardware/enclosure/README.md` renders six parts with `-D build_part=...`.
3. Slice: PETG, 0.2 mm, 4 walls, 25% gyroid, rear face down, tree supports only on bay overhangs. Print settings table in `hardware/enclosure/README.md`.
4. Heat-set the M3 inserts (lid, head) and M2.5 inserts (Pi standoffs, breakout posts) with the iron at 230 C.

Check: the Pi 5 seats on its four standoffs with the USB-C and Ethernet ports clearing the rear wall; the louvered head snaps on with no light leak past the sensor stack.

## 2. Wire the head (no soldering)

Chain with STEMMA QT: Pi header jumper (4397) -> SHT45 -> SCD41 -> BME688 -> VEML7700.
Pi pins: 3V3 (pin 1), GND (pin 6), SDA GPIO 2 (pin 3), SCL GPIO 3 (pin 5).
Hood node: SDP810 on the same SDA/SCL with 2.2 k pull-ups, two tubing taps across the prefilter (`hardware/pinouts/sensor_pinout.md`).

Check, before closing the box: `sudo i2cdetect -y 1` shows `10 44 62 76` (and `25` on a hood node). A missing address is a cable, not a driver.

## 3. Flash and provision the Pi (15 min)

1. Raspberry Pi Imager: Raspberry Pi OS Lite 64-bit; in settings set hostname `crowe-<zone>`, user `crowe`, your Wi-Fi, SSH on. (Tailscale is optional for a customer node and required for nothing.)
2. First boot, over SSH:
   ```
   sudo raspi-config nonint do_i2c 0
   sudo apt update && sudo apt install -y python3-pip python3-venv i2c-tools git
   sudo mkdir -p /opt/crowe /var/lib/crowe && sudo chown -R crowe:crowe /opt/crowe /var/lib/crowe
   git clone https://github.com/MichaelCrowe11/crowe-sense /opt/crowe/src
   python3 -m venv /opt/crowe/venv && /opt/crowe/venv/bin/pip install /opt/crowe/src/firmware
   sudo ln -sf /opt/crowe/venv/bin/crowe-* /usr/local/bin/
   sudo usermod -aG i2c,gpio crowe
   ```
3. Provision (writes the keypair and `node.toml`, prints the pairing line):
   ```
   sudo crowe-provision --site "north-grow-room" --zone tent-1 --storage-mount /var/lib/crowe
   ```
   A hood node adds `--sensors sdp810,sht45,pi`.
4. Services:
   ```
   sudo cp /opt/crowe/src/firmware/systemd/crowe-{sampler,api,uploader,watchdog,health}.* /etc/systemd/system/
   sudo sed -i 's#Requires=mnt-crowe.mount##; s#/mnt/crowe#/var/lib/crowe#g' /etc/systemd/system/crowe-*.service
   sudo systemctl daemon-reload && sudo systemctl enable --now crowe-sampler crowe-api crowe-uploader crowe-watchdog crowe-health.timer
   ```

Check: `curl -s http://localhost:8078/health` shows `"ok": true` with a rising `readings` count, and `curl -s http://localhost:8078/v1/latest | python3 -m json.tool` shows `co2_ppm`, `temperature_c` from `sht45`, `humidity_pct`, `light_lux`, `vpd_kpa` marked `est`. Open `http://<pi>:8078/` in a browser: the dashboard renders tiles and three charts filling in.

## 4. Pair the node to a Crowe ID (2 min)

On any machine with the CLI: `crowe login`, then paste the line `crowe-provision` printed:
```
crowe sense pair cs-a1b2c3 <base64 public key> --zone tent-1 --label "North tent"
crowe sense use cloud cs-a1b2c3
crowe sense status
```
Check: `crowe sense status` shows `ok` with an age under 60 s (the uploader drains every 30 s), and `crowe sense nodes` lists the node with `last_seen_ts`. On the relay, `wrangler r2 object list crowe-sense-raw --prefix raw/cs-a1b2c3/` shows the first batch.

## 5. Light every surface (10 min)

| Surface | Do | See |
|---|---|---|
| Terminal | `crowe sense latest`; `crowe sense history --metric co2_ppm --hours 6` | a table per zone; a sparkline with min, mean, max |
| Desktop | Settings, Crowe Sense: source cloud, node id; open Cultivation | the Crowe Sense card shows the node and age; within the hour the Environment lane holds a row flagged measured |
| Web | sign in at crowelogic.com/app, same settings | the same card; the footnote names the node |
| Phone and Mac | open Crowe Sense 0.2.0, source, cloud, node id, token from `crowe whoami --token` | tiles and charts; the footer says "via relay" |
| Cortex | Sense in the left rail | the panel with tiles, sparklines, hood and controller sections |
| House or any page | `<crowe-sense-panel src="/app/sense/v1/nodes/cs-a1b2c3">` | the same panel inside the host page |
| Kiosk | install `integrations/house/kiosk/` on the node, reboot | the dashboard fullscreen on the room's screen |

## 6. Prove the data is real (day 7)

```
crowe sense check --hours 168          # conditions against the grower's documented practice
python3 analysis/provenance_check.py <pulled sense.db>     # exit 0 = measurement-shaped
```
Check: `provenance_check.py` exits 0. It was written to catch our own synthetic stream
(see `archive/PROVENANCE-CORRECTION.md`); a node whose data does not pass it is not
reported as a working node, however plausible the numbers look.

## 7. Log stages and harvests from day 1

`analysis/log_stage.py` records what each zone is doing (incubation, pin_set, fruiting) and
`analysis/log_harvest.py` records weight and quality per batch. Without these the loop is
open: the alerts can say a room drifted, not what it cost. Twenty labelled harvests is the
first milestone that makes the dataset worth more than the hardware.
