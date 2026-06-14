// crowe_sensor_enclosure.scad
//
// Parametric Crowe Sensor enclosure with dedicated bays for
//   - 1 TB portable HDD (WD Elements 2.5" envelope, default)
//   - AT&T Nighthawk M6 / MR6500 cellular hotspot
//   - Raspberry Pi 5 compute deck
//   - I2C sensor head (SCD41, SHT45, BME688, VEML7700)
//
// Adjust the parameter block to fit your specific drive/hotspot.
// All dimensions in millimeters. Render with $fn = 64 for prototypes,
// 128 for final STLs.

$fn = 64;

// ============================================================
//   PARAMETERS
// ============================================================

// --- External envelope ---
ext_w = 220;   // width  (X) — fits 220×220 print beds
ext_d = 130;   // depth  (Y)
ext_h = 95;    // height (Z) without sensor head

wall   = 3.0;  // wall thickness
floor  = 3.0;
ceil   = 3.0;
slop   = 0.2;  // global slip-fit tolerance — bump to 0.3 for hot printers
fillet = 2.0;  // internal corner radius

// --- Storage bay (1 TB drive) ---
// Defaults size for WD Elements 2.5" envelope. Override these three
// numbers and the bay resizes automatically.
drive_l = 111.0;   // length (X)
drive_w =  82.0;   // width  (Y)
drive_h =  21.0;   // height (Z)
drive_slack = [6.0, 4.0, 3.0];  // [X, Y, Z] slack for foam pads

// --- Hotspot bay (AT&T Nighthawk M6) ---
hotspot_l = 106.0;  // length (X)
hotspot_w =  69.0;  // width  (Y)
hotspot_h =  19.0;  // height (Z)
hotspot_slack = [6.0, 6.0, 5.0];

hotspot_usb_slot   = [18, 10];  // USB-C entry on bottom edge of bay
hotspot_window     = [30, 15];  // screen view on top of bay
hotspot_ant_port_d = 6.0;       // side passthroughs for TS-9 pigtails

// --- Compute deck (Pi 5) ---
pi_hole_dx = 58.0;   // Pi 5 mounting hole spacing X
pi_hole_dy = 49.0;   // Pi 5 mounting hole spacing Y
pi_boss_h  = 8.0;    // deck standoff height
pi_boss_od = 6.0;    // standoff outer diameter
pi_boss_id = 2.5 + 2*slop;  // M2.5 clearance

// --- Internal divider floor ---
// Sits between the storage bay (below) and the compute+hotspot region
// (above). Carries the Pi mounting bosses and the hotspot bay floor.
divider_t = 3.0;     // thickness of the divider plate
divider_z = floor + drive_h + drive_slack[2] + 4;  // z of divider top face

// --- Sensor head ---
head_h    = 25;   // sensor head height above main body
head_vent_d  = 3.0;
head_vent_n  = 4;   // vents per side
head_lens_d  = 7.0; // camera lens hole

// --- Rear I/O panel cutouts ---
barrel_jack_d = 8.2;            // 2.1×5.5 panel jack
usb_c_debug   = [9.0, 4.0];     // service USB-C window
rj45          = [16.5, 14.5];   // RJ45 service jack

// --- Print-time choices ---
build_part = "body";   // one of: "body", "lid", "sensor_head",
                       //         "storage_tray", "hotspot_bar",
                       //         "exploded"  (preview only)
outdoor = false;       // future IP54 variant — stub only

// ============================================================
//   HELPERS
// ============================================================

module rounded_box(size, r) {
    // Filleted box. Uses minkowski for true rounded corners on the
    // XY footprint; Z faces stay flat to print without supports.
    hull() {
        for (x = [r, size[0] - r])
            for (y = [r, size[1] - r])
                translate([x, y, 0])
                    cylinder(h = size[2], r = r);
    }
}

module slot(size, r = 1.5) {
    // Rounded rectangular slot for cable cutouts.
    hull() {
        translate([r, size[1]/2, 0])  cylinder(h = size[2], r = r);
        translate([size[0]-r, size[1]/2, 0]) cylinder(h = size[2], r = r);
    }
}

module vent_array(n, spacing, d, depth) {
    for (i = [0:n-1])
        translate([i * spacing, 0, 0])
            cylinder(h = depth, d = d, center = false);
}

// ============================================================
//   STORAGE BAY (1 TB HDD)
// ============================================================

// Internal slot dimensions = drive + slack.
storage_slot = [
    drive_l + drive_slack[0],
    drive_w + drive_slack[1],
    drive_h + drive_slack[2]
];

// Position bay near the bottom-front of the body. The pocket spans the
// region between floor and the underside of the divider, so the drive
// can be slid in from the front under the upper deck.
storage_bay_origin = [
    (ext_w - storage_slot[0]) / 2,
    wall + 3,
    floor
];

module storage_bay_pocket() {
    // Cap the pocket height at the divider underside (independent of
    // the slot's nominal height) so the bay never punches through.
    pocket_h = divider_z - divider_t - floor;
    translate(storage_bay_origin)
        cube([storage_slot[0], storage_slot[1], pocket_h]);
}

module storage_cable_slot() {
    // 12 × 6 mm slot in the divider wall (rear of bay) for USB 3.0
    translate([
        ext_w/2 - 6,
        wall + 3 + storage_slot[1] - 0.1,
        floor + storage_slot[2]/2 - 3
    ])
        cube([12, wall + 6, 6]);
}

module storage_finger_notch() {
    // 30 × 8 mm finger notch in the front lip to extract drive
    translate([
        ext_w/2 - 15,
        -0.1,
        floor + storage_slot[2] - 2
    ])
        cube([30, wall + 0.2, 8]);
}

// ============================================================
//   HOTSPOT BAY
// ============================================================

hotspot_slot = [
    hotspot_l + hotspot_slack[0],
    hotspot_w + hotspot_slack[1],
    hotspot_h + hotspot_slack[2]
];

// Position bay in the upper-right quadrant, sitting on the divider.
hotspot_bay_origin = [
    ext_w - wall - hotspot_slot[0] - 4,
    ext_d - wall - hotspot_slot[1] - 4,
    divider_z      // sits on the divider's top face
];

module hotspot_bay_pocket() {
    translate(hotspot_bay_origin)
        cube(hotspot_slot);
}

module hotspot_usb_slot_cut() {
    // USB-C entry on bottom (Y-) edge of bay
    translate([
        hotspot_bay_origin[0] + (hotspot_slot[0] - hotspot_usb_slot[0])/2,
        hotspot_bay_origin[1] - wall - 0.1,
        hotspot_bay_origin[2] + 4
    ])
        cube([hotspot_usb_slot[0], wall + 0.2, hotspot_usb_slot[1]]);
}

// Screen-view window is in the LID, not the body — see lid().
module hotspot_window_cut() { }

module hotspot_antenna_ports() {
    // Two Ø6 mm passthroughs on the right (X+) wall
    for (z_off = [4, hotspot_slot[2] - 8])
        translate([
            hotspot_bay_origin[0] + hotspot_slot[0] - 0.1,
            hotspot_bay_origin[1] + hotspot_slot[1]/2,
            hotspot_bay_origin[2] + z_off
        ])
            rotate([0, 90, 0])
                cylinder(h = wall + 0.2, d = hotspot_ant_port_d);
}

// ============================================================
//   INTERNAL DIVIDER + COMPUTE DECK
// ============================================================
//
// The divider is a horizontal plate that sits at z = divider_z, spans
// the full interior footprint, and carries the Pi 5 mounting bosses on
// its top face. It's union'd into the body shell so the whole thing
// prints as one manifold solid.

module divider_plate() {
    translate([wall, wall, divider_z - divider_t])
        cube([ext_w - 2*wall, ext_d - 2*wall, divider_t]);
}

// Pi 5 mounting bosses sit on the divider's top face, in the
// front-left quadrant of the upper region.
pi_origin = [wall + 6, wall + 6];

module pi_bosses() {
    for (x = [pi_origin[0] + 3.5, pi_origin[0] + 3.5 + pi_hole_dx])
        for (y = [pi_origin[1] + 3.5, pi_origin[1] + 3.5 + pi_hole_dy])
            translate([x, y, divider_z])
                cylinder(h = pi_boss_h, d = pi_boss_od);
}

module pi_boss_holes() {
    // Pilot holes for M2.5 heat-set inserts — drilled into the bosses
    for (x = [pi_origin[0] + 3.5, pi_origin[0] + 3.5 + pi_hole_dx])
        for (y = [pi_origin[1] + 3.5, pi_origin[1] + 3.5 + pi_hole_dy])
            translate([x, y, divider_z + 1])
                cylinder(h = pi_boss_h, d = pi_boss_id);
}

// Vent slot in the divider, under where the Pi 5's active cooler sits,
// so intake air can pull up from the storage bay region.
module divider_vent() {
    translate([
        pi_origin[0] + 30,
        pi_origin[1] + 32,
        divider_z - divider_t - 0.1
    ])
        cube([30, 5, divider_t + 0.2]);
}

// ============================================================
//   SENSOR HEAD (removable cap)
// ============================================================

module sensor_head() {
    translate([0, 0, ext_h]) {
        difference() {
            // Outer cap
            rounded_box([ext_w, ext_d, head_h], fillet + wall);
            // Inner cavity
            translate([wall, wall, -0.1])
                rounded_box([ext_w - 2*wall, ext_d - 2*wall, head_h], fillet);
            // Side vents (4 per side, both X faces)
            for (side = [0, ext_d - wall + 0.1])
                translate([20, side, head_h * 0.4])
                    rotate([90, 0, 0])
                        vent_array(head_vent_n, 8, head_vent_d, wall + 0.2);
            // Camera lens hole, centered
            translate([ext_w/2, ext_d/2, head_h - ceil - 0.1])
                cylinder(h = ceil + 0.2, d = head_lens_d);
            // VEML7700 light window
            translate([ext_w/2 + 25, ext_d/2 - 5, head_h - ceil - 0.1])
                cube([10, 10, ceil + 0.2]);
        }
    }
}

// ============================================================
//   REAR I/O PANEL
// ============================================================

module rear_panel_cuts() {
    // Cuts go through the back wall (Y = ext_d direction)
    y = ext_d - wall - 0.1;
    z = floor + 6;

    // Barrel jack
    translate([20, y, z + 8])
        rotate([-90, 0, 0])
            cylinder(h = wall + 0.2, d = barrel_jack_d);

    // USB-C debug window
    translate([45, y, z])
        cube([usb_c_debug[0], wall + 0.2, usb_c_debug[1]]);

    // RJ45
    translate([65, y, z - 2])
        cube([rj45[0], wall + 0.2, rj45[1]]);

    // Two SMA antenna bulkhead holes for the hotspot
    for (x_off = [110, 130])
        translate([x_off, y, z + 30])
            rotate([-90, 0, 0])
                cylinder(h = wall + 0.2, d = 6.5);
}

// ============================================================
//   ASSEMBLED BODY
// ============================================================

module body() {
    difference() {
        union() {
            // Outer shell minus the hollow interior
            difference() {
                rounded_box([ext_w, ext_d, ext_h], fillet + wall);
                translate([wall, wall, floor])
                    rounded_box([ext_w - 2*wall, ext_d - 2*wall, ext_h], fillet);
            }
            // Internal divider + Pi mounting bosses (fused to the walls)
            divider_plate();
            pi_bosses();
        }

        // Storage bay (carved out below the divider)
        storage_bay_pocket();
        storage_cable_slot();
        storage_finger_notch();

        // Hotspot bay (carved out above the divider)
        hotspot_bay_pocket();
        hotspot_usb_slot_cut();
        hotspot_window_cut();
        hotspot_antenna_ports();

        // Vent through the divider under the Pi cooler intake
        divider_vent();

        // Pilot holes for Pi-mount inserts
        pi_boss_holes();

        // Rear I/O
        rear_panel_cuts();

        // Front status LED holes (3 × Ø5 mm)
        for (i = [0:2])
            translate([
                ext_w - 30 + i*8,
                -0.1,
                ext_h - 15
            ])
                rotate([-90, 0, 0])
                    cylinder(h = wall + 0.2, d = 5.5);
    }
}

// ============================================================
//   LID
// ============================================================

module lid() {
    difference() {
        rounded_box([ext_w, ext_d, ceil + 4], fillet + wall);
        // Lip that drops into the body
        translate([wall + slop, wall + slop, -0.1])
            rounded_box([
                ext_w - 2*(wall + slop),
                ext_d - 2*(wall + slop),
                4
            ], fillet);
        // M3 corner holes
        for (x = [10, ext_w - 10])
            for (y = [10, ext_d - 10])
                translate([x, y, -0.1])
                    cylinder(h = ceil + 4.2, d = 3.4);
        // Hotspot screen window, positioned over the hotspot bay
        translate([
            hotspot_bay_origin[0] + (hotspot_slot[0] - hotspot_window[0])/2,
            hotspot_bay_origin[1] + (hotspot_slot[1] - hotspot_window[1])/2,
            -0.1
        ])
            cube([hotspot_window[0], hotspot_window[1], ceil + 4.2]);
    }
}

// ============================================================
//   STORAGE TRAY (lid for the storage bay)
// ============================================================

module storage_tray() {
    tray_size = [storage_slot[0] + 8, storage_slot[1] + 8, 6];
    difference() {
        rounded_box(tray_size, fillet);
        // Finger pull
        translate([tray_size[0]/2 - 15, -0.1, 2])
            cube([30, 6, 5]);
        // 2 × M3 captive screw holes
        for (x = [10, tray_size[0] - 10])
            translate([x, tray_size[1]/2, -0.1])
                cylinder(h = 6.2, d = 3.4);
    }
}

// ============================================================
//   HOTSPOT RETENTION BAR
// ============================================================

module hotspot_bar() {
    bar = [hotspot_slot[0] + 6, 12, 4];
    difference() {
        rounded_box(bar, 2);
        translate([bar[0]/2, bar[1]/2, -0.1])
            cylinder(h = bar[2] + 0.2, d = 3.4);
    }
}

// ============================================================
//   PART SELECTION
// ============================================================

if (build_part == "body")          body();
else if (build_part == "lid")            lid();
else if (build_part == "sensor_head")    sensor_head();
else if (build_part == "storage_tray")   storage_tray();
else if (build_part == "hotspot_bar")    hotspot_bar();
else if (build_part == "exploded") {
    body();
    translate([0, 0, ext_h + 20]) lid();
    translate([0, 0, ext_h + 60]) sensor_head();
    translate([ext_w + 20, 0, 0]) storage_tray();
    translate([ext_w + 20, 80, 0]) hotspot_bar();
}
else {
    echo(str("Unknown build_part: ", build_part,
             ". Use one of: body, lid, sensor_head, storage_tray, hotspot_bar, exploded"));
}
