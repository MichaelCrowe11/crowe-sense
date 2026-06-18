// ============================================================
//  CROWE SENSE  ·  cultivation sensor enclosure
//  Parametric, 3D-printable prototype
//
//  Houses:  Raspberry Pi 5  +  BME688 / SCD41 / SHT45 / SDP810
//  Author:  Crowe Logic
//  Units:   millimetres
// ------------------------------------------------------------
//  Render a single part with the `part` selector below, export
//  to STL, then slice. The sensor_head is a louvered radiation
//  shield so the environmental sensors read ambient air without
//  radiant-heat bias (a mini Stevenson screen).
// ============================================================

/* [Part to export] */
// "all" previews the assembly; pick one part to export an STL
part = "all"; // [all, base, lid, sensor_head]

/* [Quality] */
$fn = 64;

// ---------- Raspberry Pi 5 footprint (official) ----------
pi_l       = 85;     // board length
pi_w       = 56;     // board width
pi_th      = 1.4;    // board thickness
pi_hole_dx = 58;     // mounting-hole pitch, long axis
pi_hole_dy = 49;     // mounting-hole pitch, short axis
pi_hole_in = 3.5;    // hole centre inset from board edges
pi_hole_d  = 2.7;    // M2.5 self-tap pilot
pi_clear_h = 20;     // headroom above board (active cooler + GPIO)

// ---------- Enclosure shell ----------
wall   = 2.2;        // wall thickness
floor  = 2.4;        // floor thickness
stand  = 4.0;        // PCB standoff height (below board)
gap    = 1.2;        // clearance around board
lid_h  = pi_clear_h; // lid skirt height
post_d = 6.0;        // corner screw-post diameter
screw_d= 3.2;        // M3 clearance for lid screws

inner_l = pi_l + 2*gap;
inner_w = pi_w + 2*gap;
base_h  = floor + stand + pi_th + 6;   // base wall height
outer_l = inner_l + 2*wall;
outer_w = inner_w + 2*wall;
r       = 3.5;       // outer corner radius

// ---------- Sensor head (radiation shield) ----------
head_d     = 46;     // shield outer diameter
head_h     = 34;     // shield height
louvers    = 6;      // number of louver rings
slat_t     = 2.0;    // slat thickness
plate_w    = 30;     // inner sensor platform
head_off_x = 22;     // head sits over this point on the lid (from centre)

// ============================================================
//  helpers
// ============================================================
module rrect(l, w, h, rad) {
    hull() for (x=[-1,1], y=[-1,1])
        translate([x*(l/2-rad), y*(w/2-rad), 0])
            cylinder(h=h, r=rad);
}

module pi_hole_posts(h, d) {
    // four mounting bosses on the Pi hole pattern
    for (x=[-1,1], y=[-1,1])
        translate([x*pi_hole_dx/2, y*pi_hole_dy/2, 0])
            cylinder(h=h, d=d);
}

module corner_posts(h) {
    inset = post_d/2 + 1.2;
    for (x=[-1,1], y=[-1,1])
        translate([x*(inner_l/2-inset), y*(inner_w/2-inset), 0])
            cylinder(h=h, d=post_d);
}

// ============================================================
//  BASE  ·  PCB tray + I/O cutouts + floor venting
// ============================================================
module base() {
    difference() {
        union() {
            // shell
            difference() {
                rrect(outer_l, outer_w, base_h, r);
                translate([0,0,floor])
                    rrect(inner_l, inner_w, base_h, r-wall+0.4);
            }
            // PCB standoffs (with pilot bosses)
            translate([0,0,floor]) pi_hole_posts(stand, 6);
            // corner screw posts for the lid
            translate([0,0,floor]) corner_posts(base_h-floor);
        }
        // standoff pilot holes
        translate([0,0,floor]) pi_hole_posts(stand+0.1, pi_hole_d);
        // lid screw pilots in corner posts
        translate([0,0,floor]) corner_posts_holes(base_h);
        // I/O window on the long (+Y) side: USB-A, ethernet, USB-C
        translate([0, inner_w/2, floor+stand+pi_th+1.0])
            io_window();
        // floor vent slots
        floor_vents();
    }
}

module corner_posts_holes(h) {
    inset = post_d/2 + 1.2;
    for (x=[-1,1], y=[-1,1])
        translate([x*(inner_l/2-inset), y*(inner_w/2-inset), -0.1])
            cylinder(h=h, d=screw_d-0.6);   // self-tap into post
}

module io_window() {
    // generous slot covering the Pi 5 port edge
    translate([-2, 0, 0])
        cube([60, wall*3, 12], center=true);
}

module floor_vents() {
    n = 7;
    for (i=[0:n-1])
        translate([-inner_l/2+10 + i*((inner_l-20)/(n-1)), 0, floor/2])
            cube([2.4, inner_w*0.6, floor+0.6], center=true);
}

// ============================================================
//  LID  ·  closes the tray, carries the sensor head + branding
// ============================================================
module lid() {
    top_th = 2.2;
    difference() {
        union() {
            // top plate
            translate([0,0,0]) rrect(outer_l, outer_w, top_th, r);
            // inner skirt that drops into the base
            translate([0,0,-6])
                difference() {
                    rrect(inner_l-0.4, inner_w-0.4, 6, r-wall);
                    translate([0,0,-0.1])
                        rrect(inner_l-0.4-2*1.6, inner_w-0.4-2*1.6, 6.2, r-wall);
                }
            // chimney coupling for the sensor head
            translate([head_off_x, 0, top_th-0.1])
                cylinder(h=6, d=head_d-6);
        }
        // screw holes through to base posts
        inset = post_d/2 + 1.2;
        for (x=[-1,1], y=[-1,1])
            translate([x*(inner_l/2-inset), y*(inner_w/2-inset), -7])
                cylinder(h=12, d=screw_d);
        // airflow bore up into the sensor head
        translate([head_off_x,0,-0.1]) cylinder(h=12, d=head_d-14);
        // branding, embossed into the top, away from the head
        translate([-14, 0, top_th-0.6]) branding();
        // cable strain-relief notch on -Y wall
        translate([head_off_x-30, -outer_w/2, -3]) cube([10,wall*3,5], center=true);
    }
}

module branding() {
    // wordmark + cube glyph, debossed 0.6mm
    linear_extrude(1.0) {
        translate([0, 3.2, 0])
            text("CROWE SENSE", size=5.4, font="Helvetica:style=Bold",
                 halign="center", valign="center");
        translate([0, -4.4, 0])
            text("cultivation intelligence", size=2.6, font="Helvetica",
                 halign="center", valign="center");
    }
}

// ============================================================
//  SENSOR HEAD  ·  louvered radiation shield (Stevenson screen)
// ============================================================
module sensor_head() {
    // stacked, downward-sloping louver rings around a vented core,
    // capped by a solid hat. Environmental sensors sit on the plate.
    step = head_h / (louvers+1);
    union() {
        // central column with sensor platform
        difference() {
            cylinder(h=head_h, d=head_d-16);
            translate([0,0,floor]) cylinder(h=head_h, d=head_d-16-2*2.0);
        }
        // sensor mounting plate inside, near top
        translate([0,0,head_h*0.45])
            difference() {
                cylinder(h=2, d=plate_w);
                pi_hole_posts(4, 2.6); // generic breakout pilots (reuse pattern)
            }
        // louver rings
        for (i=[0:louvers-1])
            translate([0,0, step*(i+1)])
                louver_ring(head_d, step);
        // solid cap
        translate([0,0,head_h])
            hull() {
                cylinder(h=0.1, d=head_d);
                translate([0,0,5]) cylinder(h=0.1, d=head_d-14);
            }
        // coupling collar that plugs into the lid chimney
        difference() {
            cylinder(h=6, d=head_d-6.4);
            translate([0,0,-0.1]) cylinder(h=6.2, d=head_d-14);
        }
    }
}

module louver_ring(d, step) {
    // a sloped annular slat, leaving an air gap beneath it
    inner = d - 12;
    translate([0,0,step*0.35])
    difference() {
        cylinder(h=slat_t, d1=d, d2=d-6);     // sloped slat
        translate([0,0,-0.1]) cylinder(h=slat_t+0.2, d=inner);
    }
}

// ============================================================
//  Assembly / part selector
// ============================================================
module assembly() {
    color("#cdcac2") base();
    color("#e9e6df") translate([0,0,base_h+0.2]) lid();
    color("#d2ad62") translate([head_off_x,0,base_h+2.4]) sensor_head();
}

if (part == "all")          assembly();
else if (part == "base")    base();
else if (part == "lid")     translate([0,0,8]) rotate([180,0,0]) lid();   // flat for printing
else if (part == "sensor_head") sensor_head();
