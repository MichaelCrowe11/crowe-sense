# Enclosure — Print & Tune Guide

The enclosure is a single parametric OpenSCAD source,
[`crowe_sensor_enclosure.scad`](crowe_sensor_enclosure.scad), that
renders six STLs by changing the `build_part` variable at the top.

## Parts list

| `build_part`     | Description                         | Print time (Bambu X1C, 0.2 mm) |
|------------------|-------------------------------------|--------------------------------|
| `"body"`         | Main shell with all bays + deck     | ~14 h                          |
| `"lid"`          | Top cover with vent panel          | ~1.5 h                         |
| `"sensor_head"`  | Vented cap with camera lens hole    | ~2 h                           |
| `"storage_tray"` | Lid for the 1 TB drive bay          | ~25 min                        |
| `"hotspot_bar"`  | Retention bar for the Nighthawk     | ~10 min                        |
| `"exploded"`     | Preview-only — do not print         | —                              |

## How to render

From the command line:

```bash
# Install OpenSCAD (any 2021.01 or newer; 2024 dev snapshots work great)
openscad -D 'build_part="body"'         -o body.stl         crowe_sensor_enclosure.scad
openscad -D 'build_part="lid"'          -o lid.stl          crowe_sensor_enclosure.scad
openscad -D 'build_part="sensor_head"'  -o sensor_head.stl  crowe_sensor_enclosure.scad
openscad -D 'build_part="storage_tray"' -o storage_tray.stl crowe_sensor_enclosure.scad
openscad -D 'build_part="hotspot_bar"'  -o hotspot_bar.stl  crowe_sensor_enclosure.scad
```

Or open the file in the OpenSCAD GUI, edit `build_part` in the parameter
block, and `F6` → Export STL.

## Print settings

| Setting               | Value                          |
|-----------------------|--------------------------------|
| Material              | PETG (indoor) / ASA (outdoor)  |
| Nozzle                | 0.4 mm                         |
| Layer height          | 0.2 mm                         |
| Perimeters / walls    | 4                              |
| Top / bottom layers   | 5 / 5                          |
| Infill                | 25 % gyroid                    |
| Print temp (PETG)     | 240 / bed 80                   |
| Print temp (ASA)      | 255 / bed 100, enclosed chamber|
| Cooling               | 30 % part fan after layer 3    |
| Supports              | Tree, only on bay overhangs    |

Orient the body **rear face down** so the bay openings (top of cavity)
print as bridges rather than support-roofed overhangs. The longest
bridge is the storage-bay opening at 117 mm — well within PETG's
capability with proper cooling.

## Resizing for a different drive or hotspot

Open the file and edit the parameter block:

```scad
// --- Storage bay (1 TB drive) ---
drive_l = 111.0;     // measure your drive's length
drive_w =  82.0;     // measure your drive's width
drive_h =  21.0;     // measure your drive's height

// --- Hotspot bay ---
hotspot_l = 106.0;   // your hotspot's length
hotspot_w =  69.0;   // your hotspot's width
hotspot_h =  19.0;   // your hotspot's height
```

The `*_slack` arrays give 3 – 6 mm of clearance on each axis for foam
pads. If you raise the slack to 8 mm or more, also bump `ext_w` /
`ext_d` so the body doesn't lose wall thickness.

## Tolerance tuning

The `slop` variable (default `0.2 mm`) is applied to every slip-fit
feature:

- Lid-to-body lip
- Storage tray drop-in
- Standoff pilot holes for heat-set inserts

If your first print binds, raise to `0.25` or `0.30`. If parts rattle,
drop to `0.15`. Don't go below `0.10` even on a tuned Voron — heat-set
inserts need that wiggle for the brass to seat square.

## Post-processing

1. Knock down brims with a deburring tool, not a knife (PETG splinters).
2. Run a 2.8 mm drill through each heat-set boss for a gentle clean-up.
3. Lightly sand the lid rim if it binds.
4. Hit the sensor-head vents with compressed air to clear any stringing.

## Outdoor variant

`outdoor = true` is stubbed in the source but not yet wired to geometry.
Don't enable it for production prints — it currently no-ops. Target for
the IP54 release is documented in
[`docs/02-mechanical-design.md`](../../docs/02-mechanical-design.md).
