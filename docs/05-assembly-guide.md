# 05 — Assembly Guide

Estimated build time: **90 minutes** for a tech who has done one before;
**~3 hours** the first time.

## You'll need

- Soldering iron with M3 / M2.5 insert tips
- M3 / M2.5 heat-set brass inserts (10 each)
- Phillips #1 driver
- 2.0 mm hex driver
- Multimeter (verify buck output before connecting Pi)
- Wire strippers, heat-shrink, helping hands

## Step 0 — Print check

1. Body, lid, sensor head, and storage tray come off the printer.
2. Clean all heat-set insert bosses with a 2.8 mm drill (light pass) —
   PETG can pull tight as it cools.
3. Dry-fit the lid to the body. It should drop in with ~0.2 mm slop on
   each side. If it doesn't, `slop` was too tight when you sliced —
   re-print or sand the rim.

## Step 1 — Install heat-set inserts

| Location               | Size | Quantity |
|------------------------|------|----------|
| Lid corners            | M3   | 4        |
| Storage tray clip      | M3   | 2        |
| Hotspot retention bar  | M3   | 1        |
| Pi 5 mounting deck     | M2.5 | 4        |
| Sensor backplane mount | M2.5 | 2        |
| Buck converter standoff| M2.5 | 4        |

Set the iron to 230 °C for PETG, 250 °C for ASA. Press the insert
square — wobble = ruined boss.

## Step 2 — Power subassembly

1. Solder leads to the barrel jack (red = center +, black = sleeve).
2. Insert the 3 A polyfuse in line on the red lead.
3. Connect to buck input `Vin+ / GND`.
4. **Before connecting anything else**: power the buck from 12 V and
   verify `5.05 ± 0.05 V` at the output with no load.
5. Solder a USB-A pigtail to the buck output for the hotspot power feed.
6. Solder a USB-C PD trigger module (set to 5 V) to the buck output for
   the Pi feed. Confirm `5.10 ± 0.10 V` at the trigger output before
   plugging in the Pi.
7. Mount the buck on its 4 standoffs in the power well.

## Step 3 — Compute deck

1. Mount the Pi 5 to the deck with 4 × M2.5 × 6 mm screws.
2. Install the active cooler per Pi Foundation instructions.
3. Plug in the USB-C PD feed. Boot to confirm — solid green = good.
4. Power down. Lay the deck into the body but **don't fasten yet**.

## Step 4 — Sensor backplane

1. Solder header pins to the SCD41, SHT45, BME688, VEML7700.
2. Wire the I2C harness:
   - All SDA → GPIO 2
   - All SCL → GPIO 3
   - All 3V3 → Pi 3V3 pin (1 or 17)
   - All GND → Pi GND
   - Add the 2.2 kΩ pull-ups (SDA→3V3, SCL→3V3) at one end of the bus.
3. Mount the backplane to the sensor head with M2.5 screws.
4. Plug the harness into the Pi GPIO header.
5. Boot the Pi, run `i2cdetect -y 1` — you should see four addresses:
   `0x10 0x44 0x62 0x76`. If any are missing, fix before continuing.

## Step 5 — Storage bay

1. Place a 3 mm closed-cell foam pad on the bay floor.
2. Slide the 1 TB drive in, USB port facing the divider wall.
3. Route the USB 3.0 cable through the 12 × 6 mm slot.
4. Clip the strain-relief into the entry slot.
5. Plug into the Pi's blue USB 3.0 port.
6. Lay a second 3 mm foam pad on top of the drive.
7. Snap the storage tray lid down — captive screws stay on the lid.
8. Boot and confirm `lsblk` shows `sda` with the expected capacity.

## Step 6 — Hotspot bay

1. Place a 2 mm silicone pad on the bay floor.
2. Drop the Nighthawk in, screen facing the top window.
3. Route the USB-C power cable from the buck pigtail to the hotspot's
   USB-C power port.
4. Route the USB-C data cable from the Pi's USB 2.0 port to the
   hotspot's USB-C data port.
5. Screw the TS-9 → SMA pigtails into the hotspot's antenna ports and
   route them out through the side passthroughs to the rear antennas.
6. Clip the retention bar across the top — single M3 captive screw.
7. Power on. Wait ~60 s for cellular lock. Confirm `nmcli` shows the
   tether interface up and routable.

## Step 7 — Status LEDs

1. Wire three LEDs (green/amber/red) with 470 Ω current-limit resistors
   to GPIO 17/27/22 and GND.
2. Mount in the front panel.
3. Boot — green should blink heartbeat, amber should flicker on each
   batch upload, red should be off.

## Step 8 — Final assembly

1. Fasten the compute deck with 4 × M2.5 × 8 mm screws.
2. Run the antenna SMA bulkheads through the rear panel holes; tighten
   with a 10 mm spanner.
3. Twist-lock the sensor head onto the top.
4. Drop the lid on and fasten the 4 corner M3 × 8 mm screws.
5. Apply a fleet inventory label to the rear.

## Step 9 — Provisioning

```bash
ssh crowe@<node-ip>
sudo crowe-provision \
  --node-id cs-7Q4F2A \
  --site mycology-lab-01 \
  --enroll-token "$ENROLL_TOKEN"
```

This generates the ed25519 keypair, registers the node with the cloud
fleet service, and pins the manifest URL. After this runs, the node
will reboot once and start streaming telemetry.

## Step 10 — Bench burn-in (4 h)

Let the node run on the bench for 4 hours before deployment. Verify:

- [ ] At least 3 successful uploads per hour
- [ ] No `STORAGE_DEGRADED` or `BACKHAUL_OFFLINE` events
- [ ] CO2 readings track when you breathe near the sensor head
- [ ] Cellular RSSI stays above -100 dBm
- [ ] No watchdog-initiated hotspot resets

If all checks pass, the node is ready to ship.
