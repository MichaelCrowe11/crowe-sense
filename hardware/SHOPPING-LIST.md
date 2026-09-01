# Crowe Sense v1 node: shopping list

Prices were read live on 2026-08-31 from the linked pages; the DRAM shortage has pushed
Raspberry Pi boards well above their 2024 list price, so check the Pi line again on the
day of the order. Everything else is stable. Amazon is used where it is not clearly worse;
Adafruit is the source for the sensor breakouts because the STEMMA QT connectors are what
make the build solder-free.

## One node (the indoor pilot build)

| # | Part | Buy from | Price | Note |
|---|---|---|---|---|
| 1 | Raspberry Pi 5, 4 GB | [PiShop.us](https://www.pishop.us/product/raspberry-pi-5-4gb/) | $110.00 | 4 GB is plenty for the sampler, API and uploader; the 8 GB is $175 and buys nothing here |
| 2 | Raspberry Pi Active Cooler | [Adafruit 5815](https://www.adafruit.com/product/5815) | $13.50 | required; a Pi 5 throttles without it |
| 3 | Raspberry Pi 27 W USB-C supply | [PiShop.us](https://www.pishop.us/product/raspberry-pi-27w-usb-c-power-supply-black-us/) | $12.95 | replaces the 12 V barrel-jack and buck converter of the field design for indoor use |
| 4 | SanDisk Extreme 64 GB microSD A2 | [Walmart](https://www.walmart.com/ip/906292559) or Amazon | $13.98 | model SDSQXA2-064G |
| 5 | SCD41 CO2 + T + RH breakout | [Adafruit 5190](https://www.adafruit.com/product/5190) | $49.95 | true NDIR CO2; I2C 0x62 |
| 6 | SHT45 precision T + RH breakout | [Adafruit 5665](https://www.adafruit.com/product/5665) | $12.50 | the reference climate sensor; I2C 0x44 |
| 7 | BME688 gas + pressure breakout | [Adafruit 5046](https://www.adafruit.com/product/5046) | $19.95 | VOC resistance and barometric pressure; I2C 0x76 |
| 8 | VEML7700 lux breakout | [Adafruit 4162](https://www.adafruit.com/product/4162) | $4.95 | I2C 0x10 |
| 9 | STEMMA QT cable 100 mm, x3 | [Adafruit 4210](https://www.adafruit.com/product/4210) | $2.85 | daisy chain between breakouts |
| 10 | STEMMA QT cable 200 mm | [Adafruit 4401](https://www.adafruit.com/product/4401) | $1.25 | head to board |
| 11 | STEMMA QT to female jumper | [Adafruit 4397](https://www.adafruit.com/product/4397) | $0.95 | lands the chain on the Pi's 3V3, GND, SDA (GPIO 2), SCL (GPIO 3) |
| 12 | Pi STEMMA QT breakout | [Adafruit 6365](https://www.adafruit.com/product/6365) | $2.50 | optional, tidier than the jumper; the SparkFun Qwiic pHAT is no longer stocked |
| 13 | M2.5 socket head screws + nuts, 20 pc | [Walmart](https://www.walmart.com/ip/48375401) or Amazon assortment B0116RIAO8 | $7.42 | Pi and breakout mounting |
| 14 | M3 brass heat-set inserts, 46 pc | [Walmart](https://www.walmart.com/ip/15680559787) | $9.89 | lid and head; one bag covers 6 nodes |
| 15 | M2.5 brass heat-set inserts | Amazon, search "M2.5 heat set insert brass" | about $10 | no single confirmed price on 2026-08-31; verify at order |
| 16 | PETG, 350 g per enclosure | [Overture PETG 1 kg](https://overture3d.com/products/overture-high-speed-petg) $14.99 | $5.25 | one spool prints about 2.8 enclosures |
| | **Node subtotal** | | **about $278** | with an 8 GB Pi: about $343 |

## Flow-hood node (adds prefilter loading)

| # | Part | Buy from | Price | Note |
|---|---|---|---|---|
| 17 | Sensirion SDP810-500Pa | [DigiKey](https://www.digikey.com/en/products/detail/sensirion-ag/SDP810-500PA/6605489) | $30.86 | differential pressure across the HEPA prefilter; I2C 0x25; needs a 2-wire I2C harness (no STEMMA QT) |
| 18 | Silicone tubing 4 mm ID, 4 m | [Walmart](https://www.walmart.com/ip/577921370) or Amazon | $14.99 | two taps, before and after the prefilter |
| 19 | 22 AWG silicone wire kit | [Binneker](https://binneker.com/collections/22-gauge-silicone-wire) or Amazon B07WYYDBZP | $11.96 | SDP810 harness and LED leads |

A hood node runs `sensors.enabled = ["sdp810", "sht45", "pi"]` and skips items 5, 7, 8.

## Optional

| Part | Buy from | Price | Why |
|---|---|---|---|
| Raspberry Pi Camera Module 3 | [Adafruit 5657](https://www.adafruit.com/product/5657) | $29.25 | the enclosure has a lens hole behind the `camera` flag; v2 vision |
| Adafruit QT Py ESP32-S3 | [Adafruit 5426](https://www.adafruit.com/product/5426) | $12.50 | a satellite node for a second tent on the same Pi (the 2026 rig used ESP32 tent nodes over MQTT) |

## The printer, once

| Printer | Price seen | Note |
|---|---|---|
| Bambu Lab A1 | $299 (list $349) | prints PETG cleanly; the body is a 14 h print, well inside its bed |
| Bambu Lab P1S | $499 | enclosed; pick this if ASA for an outdoor variant is ever wanted |
| Prusa MK4S assembled | $925 | the reference machine; kit about $729 |

## Ten-node pilot, all in

| Line | Qty | Cost |
|---|---|---|
| Room nodes (4 GB) | 8 | $2,224 |
| Hood nodes | 2 | $2 x ($278 - $75 + $58) = $522 |
| Printer (A1) + 4 spools PETG | 1 | $359 |
| Reference instruments for calibration (NDIR CO2 meter, aspirated psychrometer or SHT45 reference, digital manometer) | 1 set | about $400, verify |
| Spares (one of every sensor, two Pis) | | about $330 |
| **Pilot hardware** | | **about $3,850** |

## Wardrobe for the launch (Michael's line item)

Michael asked for the clothes to wear too. For the LinkedIn photo, the launch film and the
first investor calls, the brand reads as a working grower, not a founder in a blazer:

| Item | Buy from | Price | Note |
|---|---|---|---|
| Charcoal or ink crew tee, heavyweight (Carhartt K87 or Uniqlo U) | Amazon | about $20 | solid, no print; the gold mark goes on the enclosure, not the shirt |
| Chore jacket, olive or dark brown duck (Carhartt Detroit or Dickies) | Amazon | about $80 to $120 | reads as the grow room |
| Dark work pants (Dickies 874 or Carhartt Rugged Flex) | Amazon | about $35 | |
| Crowe Sense crew tee, print on demand | Printful or Printify, Bella+Canvas 3001 in black | about $18 each | double-C mark in gold on the left chest, "Crowe Sense" in Fraunces on the back; one for every pilot grower |

Prices in this section are ordinary retail ranges, not read live; they are here so the
order goes out in one pass.
