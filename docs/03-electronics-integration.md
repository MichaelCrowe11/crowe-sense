# 03 — Electronics Integration

## Power tree

```
                                  ┌────────────────────┐
   12 V / 3 A DC barrel ─► [F1] ─►│ MP2307 buck 5V/5A  │─┬─► Pi 5 USB-C PD
   (2.1 × 5.5 mm, +center)        └────────────────────┘ │
                                                         ├─► Sensor 3V3
                                                         │   via Pi's 3V3 pin
                                                         │   (≤ 500 mA)
                                                         │
                                                         └─► Hotspot USB-C
                                                             (5 V / 3 A max)
```

- **F1**: 3 A polyfuse, resettable, on the +12 V input.
- **Buck**: MP2307-based module (Pololu D24V50F5 or equivalent). Must be
  rated for **5 A continuous** because the Pi + hotspot together can pull
  ~4 A during cellular transmit bursts.
- **Pi 5 USB-C PD**: powered via the PD trigger module set to 5 V / 5 A
  (the Pi 5 demands PD negotiation, so a plain 5 V feed will throttle).
- **Hotspot**: powered from a dedicated USB-A → USB-C cable off the buck,
  **not** off the Pi's USB ports. The Pi connects to the hotspot for data
  via a second USB-C cable in USB-tether mode (no power negotiation
  required on that link).

## USB topology

| Pi 5 port    | Connected to              | Mode                |
|--------------|---------------------------|---------------------|
| USB 3.0 #1   | 1 TB drive                | UAS / mass storage  |
| USB 3.0 #2   | (reserved — NVMe future)  | —                   |
| USB 2.0 #1   | Hotspot (USB tether)      | RNDIS / NCM         |
| USB 2.0 #2   | Service / keyboard        | —                   |

The two USB cables to the hotspot are intentional — one is **power only**
(off the buck) and the other is **data only** (off the Pi). Trying to do
both on one cable from the Pi caused brownouts in bench testing because
the Pi can't simultaneously source 3 A to the hotspot and run its own
load on a single PD lane.

## I2C bus

All sensors share `i2c-1` (GPIO 2 SDA / GPIO 3 SCL) with 2.2 kΩ pull-ups
to 3.3 V (one set on the sensor backplane; the Pi's onboard pull-ups stay
populated since they coexist fine at this bus length).

| Sensor    | Address | Function                       |
|-----------|---------|--------------------------------|
| SCD41     | 0x62    | CO2 / T / RH                   |
| SHT45     | 0x44    | Precision T / RH               |
| BME688    | 0x76    | T / RH / pressure / gas / IAQ  |
| VEML7700  | 0x10    | Ambient light (lux)            |

Bus speed: **100 kHz** standard mode. The SCD41 specifically does not
like fast-mode, so we stay conservative.

Total trace length on the sensor backplane stays under 80 mm. The flex
cable from backplane to Pi GPIO header is 100 mm twisted pair + ground —
no issues observed up to 200 mm in bench testing but keep it short.

## GPIO assignments

| GPIO | Pin | Function                          |
|------|-----|-----------------------------------|
| 2    | 3   | I2C1 SDA                          |
| 3    | 5   | I2C1 SCL                          |
| 4    | 7   | 1-wire (optional DS18B20 probes)  |
| 17   | 11  | Status LED — green (heartbeat)    |
| 27   | 13  | Status LED — amber (sync activity)|
| 22   | 15  | Status LED — red (fault)          |
| 23   | 16  | Hotspot reset (open-collector)    |
| 24   | 18  | Drive activity LED (input)        |

Full pinout including unused pins: [`hardware/pinouts/sensor_pinout.md`](../hardware/pinouts/sensor_pinout.md).

## Hotspot reset GPIO

GPIO 23 drives an opto-isolated FET that pulls the Nighthawk's power
button line for 3 seconds when asserted. The Pi only fires this on a
watchdog-triggered cellular reset, which happens at most once per hour
after three consecutive backhaul failures.

This is the only modification to the hotspot itself, and it lives on a
sub-board that plugs into the device's USB-C — no soldering to the
hotspot.

## Antenna pigtails

Two TS-9 → SMA-female pigtails (15 cm) route from the hotspot inside the
bay out to two panel-mount 4G/5G antennas on the rear of the enclosure.
Pigtails should be **routed away from the Pi** and away from the buck
converter to avoid switching noise coupling into the cellular RF.

## Grounding

Single-point ground at the buck output negative terminal. The Pi's
ground, the sensor backplane ground, and the hotspot's USB shield all
tie there. The barrel jack shell is **not** tied to chassis ground (the
enclosure is plastic, so it's floating anyway, but this matters if a
metal variant ever ships).
