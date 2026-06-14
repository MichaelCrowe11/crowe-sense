# 02 — Mechanical Design

The enclosure is a **bay-and-deck** design: a single printed shell with
discrete cavities ("bays") for each subsystem, and an internal deck that
carries the Pi above the storage bay.

All geometry is parametric — see
[`hardware/enclosure/crowe_sensor_enclosure.scad`](../hardware/enclosure/crowe_sensor_enclosure.scad).

## External envelope

```
                  ┌───────────────────────────────────────┐
                  │                                       │   ← vented lid
                  │  ┌─────────────┐    ┌──────────────┐  │     (sensor head)
                  │  │ SENSOR HEAD │    │ STATUS LEDs  │  │
                  │  └─────────────┘    └──────────────┘  │
              ┌──┴───────────────────────────────────────┴──┐
              │                                              │  ← main body
              │   ┌────────────┐      ┌──────────────┐      │
              │   │ COMPUTE    │      │  HOTSPOT     │      │
              │   │ DECK (Pi)  │      │  BAY         │      │
              │   └────────────┘      └──────────────┘      │
              │                                              │
              │   ┌────────────────────────────────┐         │
              │   │      STORAGE BAY (1 TB)        │         │
              │   └────────────────────────────────┘         │
              │                                              │
              │   [12V] [USB-C debug] [RJ45]                 │  ← rear I/O
              └──────────────────────────────────────────────┘
                              200 × 120 × 95 mm

```

| Dim         | Value      | Note                                          |
|-------------|------------|-----------------------------------------------|
| External W  | 220 mm     | Fits a 220 × 220 mm print bed (Bambu / Prusa) |
| External D  | 130 mm     |                                               |
| External H  | 95 mm      | Without sensor head; +25 mm with head         |
| Wall        | 3.0 mm     | 4 perimeters @ 0.4 mm nozzle                  |
| Internal corner radius | 2 mm | Reduces stress risers in PETG/ABS         |

## Bay specifications

### Storage bay (1 TB drive)

Designed around the **WD Elements 2.5" / Seagate One Touch class** envelope.
Slot is a side-loading tray with a foam pad cradling the drive.

| Dim         | Internal slot | Drive nominal | Slack |
|-------------|---------------|---------------|-------|
| Length      | 117.0 mm      | 111.0 mm      | +6.0  |
| Width       | 86.0 mm       | 82.0 mm       | +4.0  |
| Height      | 24.0 mm       | 21.0 mm       | +3.0  |

The slack is taken up by 3 mm closed-cell foam pads on the floor and lid of
the bay. This isolates the drive from print-noise vibration and from any
drop shock during transport.

USB-A cable enters the bay through a 12 × 6 mm slot in the divider wall
and lives on a short (150 mm) right-angle pigtail to the Pi's USB 3.0 port.
Strain relief is a printed clip at the entry slot.

Lid uses two M3 heat-set inserts + captive screws. A 30 × 8 mm finger
notch lets you withdraw the drive without tools.

### Hotspot bay (AT&T Nighthawk M6)

Designed around **Netgear MR6500 (AT&T Nighthawk M6)** dimensions, top-loading.

| Dim         | Internal slot | Hotspot nominal | Slack |
|-------------|---------------|-----------------|-------|
| Length      | 112.0 mm      | 106.0 mm        | +6.0  |
| Width       | 75.0 mm       | 69.0 mm         | +6.0  |
| Height      | 24.0 mm       | 19.0 mm         | +5.0  |

Cutouts:

- **Bottom edge**: 18 × 10 mm slot for the USB-C tether cable.
- **Side**: two 6 mm round passthroughs for TS-9 → SMA pigtails to
  external 4G/5G antennas mounted on the rear panel.
- **Top**: 30 × 15 mm window above the device's display + status LEDs so
  the screen is visible through the printed top.

The hotspot sits on a 2 mm silicone pad. A printed retention bar clips
across the top with a single M3 screw — no permanent fastening to the
device itself, so it can be removed for SIM service or firmware updates
on a different device.

### Compute deck

Standard Pi 5 mounting pattern (58 × 49 mm hole spacing, M2.5). Deck
includes:

- 4 × M2.5 brass inserts heat-set into the printed boss.
- Cutouts directly over the Pi 5's PCIe FFC connector (for future NVMe HAT).
- A 30 × 5 mm vent slot under the active cooler intake.
- A 12 mm round window on the side wall over the Pi 5's status LEDs.

### Sensor head

Removable cap printed in white PETG (low IR emission for thermal stability)
with:

- 4 × Ø3 mm vent holes per side (16 total) over the SCD41 / SHT45 / BME688
  manifold. Vents are baffled internally to keep direct sun off the
  sensors.
- 10 × 10 mm light pipe / window over the VEML7700.
- Centered Ø7 mm hole for the Pi Camera Module 3 lens (if equipped) with
  a slip-fit lens hood.
- Cap mates to the body via a 0.4 mm interference twist-lock — no
  fasteners.

## Material & process

| Property         | Recommended            | Why                                    |
|------------------|------------------------|----------------------------------------|
| Filament         | PETG (general) / ASA (outdoor) | UV stability for outdoor; PETG is easier indoor |
| Nozzle           | 0.4 mm                 | Best balance of speed and detail       |
| Layer height     | 0.2 mm                 |                                        |
| Walls / top / bottom | 4 / 5 / 5         | Strength for field handling             |
| Infill           | 25 % gyroid            | Vibration damping + weight             |
| Supports         | Tree, only on bay overhangs |                                   |

Total print time on a Bambu X1C with 0.2 mm layer / 25 % infill is
approximately **14–16 h** for the body and **2 h** for the lid + sensor
head. Print orientation is body-down on its rear face so the bay
openings don't need support roofs.

## Tolerances

The OpenSCAD file exposes a single `slop` variable (default `0.2 mm`)
applied to every slip-fit feature. Increase to `0.3` for printers that
run hot or have wider XY bow; decrease to `0.15` for tuned Bambu/Voron.

## Outdoor variant (future)

For weather-exposed deployments, the body file accepts an `outdoor=true`
flag that:

- Adds a 1.5 mm tongue-and-groove seal channel between body and lid for
  a closed-cell foam gasket.
- Replaces the open sensor vents with a Gore-Tex membrane retainer ring
  (M12 thread).
- Adds two M16 cable glands to the rear panel.
- Targets **IP54** — splash and dust resistant, not submersible.

This is parameter-stubbed only — geometry will be finalized once the
outdoor variant is on the roadmap.
