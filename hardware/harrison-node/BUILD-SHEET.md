# Harrison node: build sheet (kit harrison-lf-01)

One room node for Harrison Mushrooms' fruiting space in Lake Forest. The purpose is a real
node in a real room before any lender or the FSA office hears "farm management system"
(scope r0, action 5.2), and the first environment record against a real harvest.

## Parts to order (no-print variant; prices read 2026-08-31, check the Pi line on the day)

| # | Part | Buy from | Price |
|---|---|---|---|
| 1 | Raspberry Pi 5, 4 GB | PiShop.us | $110.00 |
| 2 | Raspberry Pi Active Cooler | Adafruit 5815 | $13.50 |
| 3 | Raspberry Pi 27 W USB-C supply | PiShop.us | $12.95 |
| 4 | Official Raspberry Pi 5 case (red/white or black) | PiShop.us or Adafruit | about $10 |
| 5 | SanDisk Extreme 64 GB microSD A2 | Walmart or Amazon | $13.98 |
| 6 | SCD41 CO2 + T + RH breakout | Adafruit 5190 | $49.95 |
| 7 | SHT45 precision T + RH breakout | Adafruit 5665 | $12.50 |
| 8 | BME688 gas + pressure breakout | Adafruit 5046 | $19.95 |
| 9 | VEML7700 lux breakout | Adafruit 4162 | $4.95 |
| 10 | STEMMA QT cable 100 mm, x3 | Adafruit 4210 | $2.85 |
| 11 | STEMMA QT cable 200 mm | Adafruit 4401 | $1.25 |
| 12 | STEMMA QT to female jumper | Adafruit 4397 | $0.95 |
| 13 | Small ABS project box or a 3D-printed sensor head later; for the pilot, a ventilated card-stock hood keeps mist off the breakouts | Amazon | about $8 |
| | **Total** | | **about $260** |

The printed enclosure (site/model/crowe-sense-enclosure.scad) needs a printer the company
does not own yet; the official case plus a ventilated sensor hood is the pilot build and
loses nothing the data needs.

## Wire the head (no soldering)

STEMMA QT chain: Pi jumper (4397) -> SHT45 -> SCD41 -> BME688 -> VEML7700.
Pi pins: 3V3 (pin 1), GND (pin 6), SDA GPIO 2 (pin 3), SCL GPIO 3 (pin 5).
Check before closing: `sudo i2cdetect -y 1` shows 10 44 62 76. A missing address is a cable.

## Flash and install (Michael, in Phoenix, before the node travels)

1. Raspberry Pi Imager: Raspberry Pi OS Lite 64-bit. Settings: hostname `crowe-harrison-lf-01`,
   user `crowe`, Wi-Fi = Harrison's grow-room network (ask him for SSID and password by text),
   SSH on. If his Wi-Fi does not reach the room, use the AT&T Nighthawk hotspot already on hand
   (USB tether; the firmware's routing module prefers it when present).
2. Copy the kit onto the boot partition: `kits/harrison-lf-01/` (this repo's `firmware/` tree,
   `etc-crowe/` with node.toml, node.key, node.pub, and `install.sh`).
3. First boot on the bench in Phoenix, over SSH: `sudo bash /boot/firmware/crowe-kit/firmware/install.sh /boot/firmware/crowe-kit`.
4. Check on the bench: `curl -s http://crowe-harrison-lf-01.local:8078/health` shows ok:true and a
   rising readings count; `curl -s https://sense.crowelogic.com/v1/nodes/<node>/health` with a
   Crowe ID bearer shows the same node from the cloud. Leave it running an hour, then
   `analysis/provenance_check.py` against a pulled `sense.db` must exit 0.
5. Label the case with the node id and "Crowe Sense, do not unplug", and hand-carry or ship.

## Place it (Harrison, five minutes)

- Mount at canopy height, mid-room, out of direct mist and away from the humidifier outlet and
  the door; the sensor hood faces down.
- Power from a wall outlet that is not on a timer. Nothing else to do; it joins Wi-Fi and
  starts pushing within a minute of power.
- If the green light stops blinking for an hour, unplug and plug back in; if it stays dark,
  text Michael.

## What it produces, and when

- Day 1: temperature, humidity, CO2, VPD, dew point and light in his fruiting room, on his
  phone and Michael's, every few seconds locally and every 30 s in the cloud.
- Day 7: the first week of real room data through the provenance check, which is the first
  time the company can say "a Crowe Sense node has run in a commercial growing room."
- With `analysis/log_harvest.py` at each pick: the first environment-to-harvest rows, the
  dataset the scope calls the unbuyable asset.
