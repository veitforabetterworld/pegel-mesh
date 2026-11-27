// pegel-sender-12v – waermegedaemmtes Aussengehaeuse fuer die Platine 100 x 70 mm mit einer LiFePO4-Zelle IFR32700
// Aufbau (gleiches Prinzip wie das Funklicht-Gehaeuse):
//   - Gehaeuse: Haube mit fester Front, wird von hinten bestueckt
//   - Bodendeckel (Wandseite): traegt die Platine (4 Dome), die eingeklipste Zelle und die Wandlaschen,
//     mit 4 M3-Zylinderschrauben aus Taschen von hinten angeschraubt, rundum gedichtet (Nut im Gehaeuserand)
//   - je ein Schraubdeckel (gedaemmter Stopfen) ueber SOLAR (J1) und SONDE (J3), eigene Dichtung; ein Quersteg
//     ueber den Klemmen trennt den Klemmenraum ab. AKKU (J2) und HEIZ/NTC (J4) werden innen fest verdrahtet.
//   - Kabelverschraubungen: 2 x M16 Solar links neben J1, 1 x M20 Sonde rechts neben J3
//   - Antennendurchfuehrung (SMA-Einbaubuchse, Loch 7 mm) oben rechts ueber dem XIAO
// Waermedaemmung: Waende, Front, Bodendeckel und Klemmendeckel 25 mm stark mit k_n geschlossenen Luftkammern
// hintereinander (CAD-Geometrie, kein Slicer-Infill). Rechnung: daemmung.py / README.
// Koordinaten: Platine x 0..100, y 0..70 (y nach oben, AKKU-Klemme oben), z = 0 Wandseite
// Material: PETG (gehaeuse, bodendeckel, *_deckel), TPU 95A (dichtung, klemmdichtung_*, usb_dichtung)
// Export:  openscad -D 'part="gehaeuse"' -o stl/gehaeuse.stl pegel_sender_gehaeuse.scad
include <platine_bauteile.scad>
// Kabelverschraubungen: https://github.com/veitforabetterworld/printable-cable-gland (Git-Submodul unter lib/)
//   git submodule update --init  (im Repo-Root)
use <lib/printable-cable-gland/cable_gland.scad>
part = "baugruppe";
$fn = 64;
kammern = true;                  // false: massive Waende (schneller; Kammern sind innen geschlossen und
                                 // aendern keine Aussen-/Innenflaeche -> fuer die Kollisionspruefungen gleichwertig)

// ---------------- Hauptmasse (mm) ----------------
ix0 = -14;  ix1 = 114;           // Innenraum x: je 14 mm fuer Kabel neben den Klemmen
iy0 = -2;   iy1 = 112;           // Innenraum y: Platine unten, Zelle oben
id = 36;                         // Innentiefe (Zelle Oberkante + 2,3 mm)
iw = ix1 - ix0;  ih = iy1 - iy0;
t = 25;  tb = 25;  tl = 25;      // Wand, Bodendeckel, Front (gedaemmt)
ri = 1;  ro = ri + t;            // Aussenkontur = Innenkontur + t (ueberall gleich dicke Daemmung)
H = tb + id;                     // Innenseite Front; Dichtflaeche hinten bei Z = tb

ins_d = 4.0; ins_l = 6.4;        // Einschmelzmutter M3 (z. B. M3 x 5,7, Aussen-D 4,6)
gw = 2.0; gd = 2.0; g_in = 0.8;  // Dichtungsnut
sw = 1.8; sh = 2.6;              // TPU-Dichtschnur (0,6 mm Verpressung)
rb = 6;                          // Dichtbahn laeuft konzentrisch um jedes Schraubloch (Nut R 3,2 .. 5,2, 1,2 mm zum Loch D 4)
g_fillet = 1.5;                  // Uebergang Bogen <-> Wand/Steg gerundet

// ---------------- Luftkammern ----------------
// Schichtfolge von innen nach aussen: k_si | Kammer k_d | Trennwand k_s | ... | Kammer k_d | k_so
k_n = 7;                         // Kammern hintereinander
k_s = 0.6;                       // Trennwand (1 Linie bei Duese 0,4 / 3 Lagen a 0,2 mm)
k_si = 1.2;                      // Innenhaut
k_so = 1.6;                      // Aussenhaut (wasserdicht: 4 Linien / 8 Lagen)
k_d = (t - k_si - k_so - (k_n - 1) * k_s) / k_n;   // Kammertiefe in Waermestromrichtung (2,66 mm)
k_rib = 0.6;                     // Stege zwischen den Trennwaenden
k_pitch_f = 10;                  // Stegabstand in Front/Deckeln (waagrechte Kammerdecken = Bruecke 9,4 mm)
k_pitch_w = 30;                  // Stegabstand in den Seitenwaenden (senkrecht gedruckt, nur Steifigkeit)
k_sleeve = 1.2;                  // Massivmaterial um Bohrungen, Nuten, Taschen (schliesst die Kammern)
k_back = 1.2;                    // Massivschicht an der hinteren Dichtflaeche des Gehaeuses
k_min = 1.0;                     // Pruefmass: Mindestwand zwischen Kammer und Luft
function k_a(k) = k_si + k * (k_d + k_s);           // Abstand Kammer k von der Innenflaeche
assert(k_d >= 2, "Kammern zu duenn");

// ---------------- Platine (aus pegel-sender-12v.step / fixed_positions.py) ----------------
pcb_w = 100;  pcb_h = 70;  pcb_t = 1.6;
pcb_holes = [[4, 4], [96, 4], [4, 66], [96, 66]];   // H1..H4 (KiCad-y gespiegelt, symmetrisch)
standoff_h = 6;  standoff_d = 6.5;  // Pins stehen unten 3,0 mm ueber -> 1 mm Luft zum Deckel
pcb_z = tb + standoff_h;             // Unterseite Platine
pcb_top = pcb_z + pcb_t;
term_h = 13.8;                       // Phoenix MKDS 1,5 (aus dem STEP)
term_top = pcb_top + term_h;

// ---------------- Zelle IFR32700 ----------------
cell_d = 32.2;  cell_l = 71;     // inkl. Pluspol
cell_x0 = 16.5;                  // links frei vom Quersteg des Solar-Klemmenraums
cell_y = pcb_h + 6 + cell_d / 2; // 6 mm ueber der AKKU-Klemme (Kabel)
cradle_base = 1.5;               // Zelle liegt so weit ueber dem Bodendeckel
cell_z = tb + cradle_base + cell_d / 2;
cradle_x = [cell_x0 + 10, cell_x0 + cell_l - 10];
cradle_w = 10;  cradle_t = 2.5;  cradle_open = 0.4;   // Oeffnung oben bei 0,4 R ueber der Achse -> 2,7 mm Rastweg

// ---------------- Bodendeckel-Verschraubung ----------------
cb = 7;  cb_h = 7.5;             // Eckbloecke am hinteren Rand (ausserhalb der Platine)
deck_pts = [[ix0, iy0], [ix1, iy0], [ix0, iy1], [ix1, iy1]];
pocket_d = 6.2;  pocket_floor = 4;   // Schraubentaschen: M3-Zylinderkopf (D 5,5) sitzt auf 4 mm Boden -> kurze Schraube,
                                     // keine Stahlbruecke durch die Daemmung
lug_l = 16;  lug_w = 22;  lug_hole = 4.8;  lug_slot = 3;  lug_r = 3;  lug_fillet = 2;
lug_t = 5;                       // Wandlaschen (nur so dick, Schraubenkopf 8 mm neben dem Gehaeuse)
lug_x = (ix0 + ix1) / 2;
lug_slots = [[iy1 + t + lug_l / 2, 45], [iy0 - t - lug_l / 2, -45]];

// ---------------- Klemmenraeume (Schraubdeckel) ----------------
j1_screw_x = 6.33;               // Schraubenachse SOLAR (J1)
j3_screw_x = 93.67;              // Schraubenachse SONDE (J3)
// [x0, y0, x1, y1] Oeffnung; Kanten an den Waenden reichen bis in die Wand
klemm_regions = [
    [ix0, 26, j1_screw_x + 1.95, 80],      // SOLAR: Wand links bis 1,95 mm hinter die Schrauben (Schraubendreher D 3)
    [j3_screw_x - 1.95, iy0, ix1, 36]];    // SONDE
klemm_names = ["solar", "sonde"];
beam_w = 4.5;                    // Steg unter dem Klemmendeckel (Nut + Schraube)
shoulder_w = 3.0;                // Schulter unter der Frontkante
xiao_top = pcb_top + 19.1;       // XIAO + Wio-SX1262 (USB-C-Oberkante, aus dem STEP)
klemm_beam_z0 = [term_top + 1.0, xiao_top + 0.6];
kblk_z0 = H - 7;                 // Schraubbloecke an der Front
kgap = 0.3;                      // Fuge Klemmendeckel / Front (rundum, 25 mm tief)

// ---------------- Durchfuehrungen ----------------
// Kabelverschraubung: in der 25-mm-Wand eine Tasche von innen, aussen bleibt gland_wall massiv stehen
// (passt zu printable-cable-gland mit wall = 4 und zu Metall-Verschraubungen). Aussen ist die Wand plan
// (Bund-Eckmass + Rand), innen liegt die Kontermutter verdrehsicher im Sechskant auf der Aussenhaut.
gland_z = tb + 18;  gland_wall = 4;  // Wand an der Verschraubung = Auslegung der Verschraubung (wall = 4)
// Masse aus printable-cable-gland (Loch, Kontermutter SW/Hoehe, Huelle fuer Pruefungen)
function gland_d(g) = cable_gland_hole_d(g[2]);
function gland_af(g) = cable_gland_nut_af(g[2]);
function gland_nut_t(g) = cable_gland_nut_h(g[2]);
function gland_pocket(g) = gland_af(g) + 0.4;
glands = [["L", 39.5, "M16"], ["L", 65.5, "M16"], ["R", 18, "M20"]];   // Wand, y, Groesse (Solar 2 x M16, Sonde M20)
assert(glands[1][1] - glands[0][1] >= cable_gland_spacing("M16"), "Solar-Verschraubungen zu dicht");
assert(gland_wall <= cable_gland_wall_range("M16", 4)[1] && gland_wall >= cable_gland_wall_range("M16", 4)[0]);
ant_d = 7;  ant_x = 96;  ant_z = tb + 18;      // Antenne oben
ant_pocket = 8.4;  ant_wall = 3;               // SMA-Einbaubuchse: Sechskant SW 8 innen in der Tasche, Mutter aussen

// ---------------- USB-Deckel (rechte Wand, vor der USB-C-Buchse des XIAO) ----------------
// Buchse laut STEP: Steckseite x 98,37, y 47,9..56,9, z 15,9..19,1 ueber der Platine -> Mitte y 52,4, z +17,5
usb_c = [52.4, pcb_top + 17.5];  // [y, z] Mitte der Oeffnung
usb_open = [15, 10];  usb_r = 2;  // Tunnel durch die Wand fuer den Stecker-Umspritzling
usb_plate = [39, 20];  usb_plate_t = 4;  usb_plate_r = 3;
usb_screw_dy = 14.5;             // 2 x M3 Senkkopf, Einschmelzmuttern von aussen in der Wand

// lokale Koordinaten der rechten Wand: u = y, v = z, w = x (nach aussen)
module rechte_wand() { multmatrix([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0]]) children(); }
module usb_open2d() { translate(usb_c) offset(r = usb_r) square(usb_open - [2 * usb_r, 2 * usb_r], center = true); }
module usb_plate2d() { translate(usb_c) offset(r = usb_plate_r) square(usb_plate - [2 * usb_plate_r, 2 * usb_plate_r], center = true); }
function usb_screws() = [[usb_c[0] - usb_screw_dy, usb_c[1]], [usb_c[0] + usb_screw_dy, usb_c[1]]];
// Tunnel innerhalb der Wand mit 45-Grad-Dach zur Rueckseite (Druck: sonst 15 mm Bruecke ueber 25 mm Laenge);
// die aeusseren usb_flat mm (Dichtnut) behalten die Rechteckoeffnung
usb_flat = gd + 2;
module usb_tunnel2d() { hull() { usb_open2d(); translate([usb_c[0], usb_c[1] - usb_open[1] / 2 - usb_open[0] / 2 + usb_r]) circle(r = 0.01); } }
module usb_groove2d() { ring2d(gw, g_in + gw / 2) usb_open2d(); }

// ---------------- 2D-Formen ----------------
module rr(w, h, r) { translate([r, r]) offset(r = r) square([w - 2 * r, h - 2 * r]); }
module inner2d() { translate([ix0, iy0]) rr(iw, ih, ri); }
module outer2d() { offset(r = t) inner2d(); }
module rect2d(r) { translate([r[0], r[1]]) square([r[2] - r[0], r[3] - r[1]]); }
// Rechteck nach aussen erweitern: an Waenden bis ausserhalb des Gehaeuses, sonst um e
function grow(r, e) = [r[0] <= ix0 ? ix0 - t - 1 : r[0] - e, r[1] <= iy0 ? iy0 - t - 1 : r[1] - e,
                       r[2] >= ix1 ? ix1 + t + 1 : r[2] + e, r[3] >= iy1 ? iy1 + t + 1 : r[3] + e];
function corners(r) = [[r[0], r[1]], [r[2], r[1]], [r[0], r[3]], [r[2], r[3]]];

// Dichtbereich = Oeffnung minus Kreise um die Schraubloecher: Nut und Oeffnungskante laufen konzentrisch
// um jedes Loch; Uebergaenge Bogen <-> Wand/Steg mit R g_fillet
module seal_region2d() {
    difference() {
        translate([ix0, iy0]) square([iw, ih]);
        for (p = deck_pts) translate(p) circle(r = rb);
    }
}
module rund2d() { offset(r = g_fillet) offset(delta = -g_fillet) children(); }
module ring2d(w, c) {
    difference() {
        offset(r = c + w / 2) rund2d() children();
        offset(r = c - w / 2) rund2d() children();
    }
}
module groove2d(w) { ring2d(w, g_in + gw / 2) seal_region2d(); }
module klemm_region2d(r) {
    difference() {
        rect2d(r);
        for (p = corners(r)) translate(p) circle(r = rb);
    }
}
module kgroove2d(r, w) { ring2d(w, g_in + gw / 2) klemm_region2d(r); }
module klemmdeckel2d(r) { intersection() { outer2d(); rect2d(grow(r, beam_w - kgap)); } }
module front2d() { difference() { outer2d(); for (r = klemm_regions) rect2d(grow(r, beam_w)); } }
module bodendeckel2d() {
    offset(r = lug_r) offset(delta = -lug_r) offset(r = -lug_fillet) offset(delta = lug_fillet) {
        outer2d();
        for (y = [iy0 - t - lug_l, iy1 + t - 0.01]) translate([lug_x - lug_w / 2, y]) square([lug_w, lug_l + 0.01]);
    }
}
module langloch2d(d, l) { hull() for (s = [-1, 1]) translate([s * l / 2, 0]) circle(d = d); }

// ---------------- Luftkammern (2D-Hilfen) ----------------
// Stege in Front/Deckeln: Richtung wechselt von Lage zu Lage (x / y), jede zweite gleichgerichtete Lage um
// eine halbe Teilung versetzt -> Stege benachbarter Lagen kreuzen sich nur punktweise (keine durchgehende Bruecke)
module rippen2d(k) {
    off = (floor(k / 2) % 2) * k_pitch_f / 2;
    for (i = [-6 : 16]) {
        c = i * k_pitch_f + off;
        if (k % 2 == 0) translate([-100, c - k_rib / 2]) square([400, k_rib]);
        else translate([c - k_rib / 2, -100]) square([k_rib, 400]);
    }
}
// Stege in den Seitenwaenden: quer zur Wand, von Lage zu Lage um eine halbe Teilung versetzt
module wandrippen2d(k) {
    off = (k % 2) * k_pitch_w / 2;
    for (x = [ix0 + k_pitch_w / 2 + off : k_pitch_w : ix1 - 3]) translate([x - k_rib / 2, iy0 - t - 2]) square([k_rib, ih + 2 * t + 4]);
    for (y = [iy0 + k_pitch_w / 2 + off : k_pitch_w : iy1 - 3]) translate([ix0 - t - 2, y - k_rib / 2]) square([iw + 2 * t + 4, k_rib]);
}
module band2d(a, b) { difference() { offset(r = b) inner2d(); offset(r = a) inner2d(); } }
// Waagrechte Kammerlagen einer Platte (Front, Bodendeckel, Klemmendeckel); zi = Innenflaeche, dir = +1 nach +z
// children(0): Grundriss der Kammern, children(1): nur in Lage 0 zusaetzlich massiv (unter Dichtschnuren)
module plattenlagen(zi, dir) {
    for (k = [0 : k_n - 1]) {
        a = k_a(k);
        translate([0, 0, dir > 0 ? zi + a : zi - a - k_d]) linear_extrude(k_d) difference() {
            children(0);
            rippen2d(k);
            if (k == 0 && $children > 1) children(1);
        }
    }
}

// ---------------- Wandbohrungen ----------------
// lokaler Rahmen einer Wand: Ursprung auf der Innenflaeche, +z nach aussen, lokale x-Achse zeigt in Druck-Z
module wand_frame(wand, pos, z) {
    if (wand == "L") translate([ix0, pos, z]) rotate([0, -90, 0]) children();
    if (wand == "R") translate([ix1, pos, z]) rotate([0, 90, 0]) children();
    if (wand == "O") translate([pos, iy1, z]) rotate([-90, 0, 0]) rotate(90) children();
}
// Sechskant mit Spitze in lokal x (= senkrecht beim Druck -> 60-Grad-Dach, ohne Stuetzen)
module hex2d(af) { circle(d = af / cos(30), $fn = 6); }
// Durchfuehrung: Loch durch die Aussenhaut, Tasche von innen bis zur Aussenhaut (Wand dort wall dick)
module durchfuehrung(wand, pos, z, d, af, wall, e = 0) {
    wand_frame(wand, pos, z) {
        translate([0, 0, -1 - e]) cylinder(d = d + 2 * e, h = t + 2 + 2 * e);
        translate([0, 0, -1 - e]) linear_extrude(t - wall + 1 + 2 * e) offset(delta = e) hex2d(af);
    }
}

// ---------------- Eckbloecke hinten ----------------
// Grundriss = Viertelkreis-Dom um die Schraube + Hohlkehlen (Komplement des gerundeten Dichtbereichs im Eckquadrat,
// 0,5 mm in die Wand). Zur Front hin 45-Grad-Fase zur Seitenwand (Druck: Front aufs Bett -> Fase ist Unterseite).
module eckblock2d(links, unten) {
    s = cb + g_fillet;
    intersection() {
        translate([links ? ix0 - 0.5 : ix1 - s, unten ? iy0 - 0.5 : iy1 - s]) square(s + 0.5);
        difference() { translate([ix0 - 1, iy0 - 1]) square([iw + 2, ih + 2]); rund2d() seal_region2d(); }
    }
}
module eckbloecke() {
    s = cb + g_fillet;
    for (links = [true, false], unten = [true, false]) {
        translate([0, 0, tb]) linear_extrude(cb_h + 0.01) eckblock2d(links, unten);
        // Fase: Grundriss zur Seitenwand hin zusammenziehen (scale 0.02, nicht 0: sonst offenes Mesh in 2021.01)
        translate([0, 0, tb + cb_h]) {
            if (links) translate([ix0 - 0.5, 0, 0]) linear_extrude(s + 0.5, scale = [0.02, 1])
                translate([-(ix0 - 0.5), 0]) eckblock2d(links, unten);
            else translate([ix1 + 0.5, 0, 0]) mirror([1, 0, 0]) linear_extrude(s + 0.5, scale = [0.02, 1])
                mirror([1, 0]) translate([-ix1 - 0.5, 0]) eckblock2d(links, unten);
        }
    }
}

// ---------------- Gehaeuse ----------------
// Alle Hohlraeume des Gehaeuses (Nuten, Bohrungen, Taschen), um e vergroessert.
// e = 0: wird abgezogen; e = k_sleeve: Sperrbereich fuer die Kammern; e = k_min: Pruefkoerper
module gehaeuse_luft(e = 0) {
    translate([0, 0, tb - 1]) linear_extrude(gd + 1 + e) offset(r = e) groove2d(gw);
    for (p = deck_pts) translate([p[0], p[1], tb - 1]) cylinder(r = ins_d / 2 + e, h = ins_l + 1 + e);
    for (r = klemm_regions) {
        translate([0, 0, H - gd - e]) linear_extrude(gd + 1 + e) offset(r = e) kgroove2d(r, gw);
        for (p = corners(r)) translate([p[0], p[1], H - ins_l - e]) cylinder(r = ins_d / 2 + e, h = ins_l + 1 + e);
        // Aussparung fuer den Klemmendeckel (bei e = 0 schon in front2d)
        if (e > 0) translate([0, 0, H - e]) linear_extrude(tl + e + 1) offset(delta = e) rect2d(grow(r, beam_w));
    }
    for (g = glands) durchfuehrung(g[0], g[1], gland_z, gland_d(g), gland_pocket(g), gland_wall, e);
    durchfuehrung("O", ant_x, ant_z, ant_d, ant_pocket, ant_wall, e);
    rechte_wand() {
        translate([0, 0, ix1 - 1 - e]) linear_extrude(t + 2 + 2 * e) offset(r = e) usb_open2d();
        translate([0, 0, ix1 - 1 - e]) linear_extrude(t - usb_flat + 1 + e) offset(r = e) usb_tunnel2d();
        translate([0, 0, ix1 + t - gd - e]) linear_extrude(gd + 1 + e) offset(r = e) usb_groove2d();
        for (p = usb_screws()) translate([p[0], p[1], ix1 + t - ins_l - e]) cylinder(r = ins_d / 2 + e, h = ins_l + 1 + e);
    }
}
// Geschlossene Luftkammern in Waenden und Front: k_n verschachtelte Schalen um den Innenraum
module kammern_gehaeuse() {
    $fn = 32;
    difference() {
        union() for (k = [0 : k_n - 1]) {
            a = k_a(k);
            // Wandteil: senkrechter Spalt (beim Druck), oben am Dichtrand mit k_back geschlossen
            translate([0, 0, tb + k_back]) linear_extrude(H + a - tb - k_back) difference() { band2d(a, a + k_d); wandrippen2d(k); }
            // Frontteil: waagrechte Lage, Decke wird auf den Stegen gebrueckt
            translate([0, 0, H + a]) linear_extrude(k_d) difference() { offset(r = a + k_d) inner2d(); rippen2d(k); }
        }
        gehaeuse_luft(k_sleeve);
    }
}
module gehaeuse(mit_kammern = kammern) {
    difference() {
        union() {
            difference() {
                translate([0, 0, tb]) linear_extrude(H - tb) outer2d();
                translate([0, 0, tb - 1]) linear_extrude(H - tb + 2) inner2d();
            }
            translate([0, 0, H - 0.01]) linear_extrude(tl + 0.01) front2d();
            eckbloecke();
            for (i = [0 : len(klemm_regions) - 1]) {
                r = klemm_regions[i];  beam_z0 = klemm_beam_z0[i];
                // Quersteg (Nut + Schrauben) und Schulter unter der Frontkante, nur im Innenraum
                translate([0, 0, beam_z0]) linear_extrude(H - beam_z0) intersection() {
                    inner2d();
                    difference() { rect2d(grow(r, beam_w + shoulder_w)); rect2d(r); }
                }
                // Schraubdome in den Ecken der Oeffnung (Viertelkreis + Hohlkehlen), Kante folgt der Dichtbahn
                translate([0, 0, kblk_z0]) linear_extrude(H - kblk_z0) difference() { rect2d(r); rund2d() klemm_region2d(r); }
            }
        }
        gehaeuse_luft(0);
        if (mit_kammern) kammern_gehaeuse();
    }
}
module usb_deckel() {   // Einbaulage aussen an der rechten Wand; bleibt duenn (Tunnel 15 x 10 mm, siehe README)
    rechte_wand() difference() {
        translate([0, 0, ix1 + t]) linear_extrude(usb_plate_t) usb_plate2d();
        for (p = usb_screws()) translate([p[0], p[1], ix1 + t - 1]) {
            cylinder(d = 3.4, h = usb_plate_t + 2);
            translate([0, 0, 1 + usb_plate_t - 1.8]) cylinder(d1 = 3.4, d2 = 6.6, h = 1.81);
        }
    }
}
module usb_dichtung() { linear_extrude(sh) offset(r = -(gw - sw) / 2) usb_groove2d(); }

// ---------------- Klemmendeckel (gedaemmter Stopfen, fuellt die Aussparung in der Front) ----------------
module klemmdeckel_luft(r, e = 0) {   // Schraubentaschen (Kopf auf 4 mm Boden) + Durchgangsloch
    for (p = corners(r)) translate([p[0], p[1], H - 1 - e]) {
        cylinder(r = 1.7 + e, h = tl + 2 + 2 * e);
        translate([0, 0, 1 + pocket_floor]) cylinder(r = pocket_d / 2 + e, h = tl + 2 + e);
    }
}
module kammern_klemmdeckel(r) {
    $fn = 32;
    difference() {
        plattenlagen(H, 1) {
            offset(delta = -k_so) klemmdeckel2d(r);
            offset(r = 1.5) kgroove2d(r, gw);      // Lage 0 unter der Dichtschnur massiv
        }
        klemmdeckel_luft(r, k_sleeve);
    }
}
module klemmdeckel(r, mit_kammern = kammern) {
    difference() {
        translate([0, 0, H]) linear_extrude(tl) klemmdeckel2d(r);
        klemmdeckel_luft(r);
        if (mit_kammern) kammern_klemmdeckel(r);
    }
}
module klemmdichtung(r) { linear_extrude(sh) offset(r = -(gw - sw) / 2) kgroove2d(r, gw); }
module dichtung() { linear_extrude(sh) offset(r = -(gw - sw) / 2) groove2d(gw); }

// ---------------- Bodendeckel ----------------
module akkuhalter() {   // Sattel mit Rastoeffnung oben, Zelle wird eingedrueckt
    R = cell_d / 2;
    for (x = cradle_x) translate([x - cradle_w / 2, 0, 0]) {
        difference() {
            union() {
                translate([0, cell_y - R - cradle_t, tb - 0.01]) cube([cradle_w, cell_d + 2 * cradle_t, cell_z - tb]);
                translate([0, cell_y, cell_z]) rotate([0, 90, 0]) cylinder(r = R + cradle_t, h = cradle_w);
            }
            translate([-1, cell_y, cell_z]) rotate([0, 90, 0]) cylinder(r = R, h = cradle_w + 2);
            translate([-1, cell_y - (R + cradle_t + 1), cell_z + cradle_open * R]) cube([cradle_w + 2, 2 * (R + cradle_t + 1), R + cradle_t]);
        }
    }
}
module bodendeckel_luft(e = 0) {
    for (h = pcb_holes) translate([h[0], h[1], pcb_z - ins_l - e]) cylinder(r = ins_d / 2 + e, h = ins_l + 1 + e);
    for (p = deck_pts) translate([p[0], p[1], -1 - e]) {
        cylinder(r = 1.7 + e, h = tb + 2 + 2 * e);
        cylinder(r = pocket_d / 2 + e, h = 1 + tb - pocket_floor + e);
    }
}
module kammern_bodendeckel() {
    $fn = 32;
    difference() {
        plattenlagen(tb, -1) {
            offset(delta = -k_so) outer2d();
            offset(r = 1.5) groove2d(gw);           // Lage 0 unter der Dichtschnur massiv
        }
        bodendeckel_luft(k_sleeve);
    }
}
module bodendeckel(mit_kammern = kammern) {
    difference() {
        union() {
            linear_extrude(tb) outer2d();
            linear_extrude(lug_t) bodendeckel2d();
            // Zentrierkragen entlang der Waende zwischen den Eckbloecken
            translate([0, 0, tb - 0.01]) linear_extrude(2.01) intersection() {
                difference() { offset(r = -0.4) inner2d(); offset(r = -1.8) inner2d(); }
                union() {
                    translate([ix0, iy0 + cb + 0.5]) square([iw, ih - 2 * cb - 1]);
                    translate([ix0 + cb + 0.5, iy0]) square([iw - 2 * cb - 1, ih]);
                }
            }
            for (h = pcb_holes) translate([h[0], h[1], tb - 0.01]) cylinder(d = standoff_d, h = standoff_h + 0.01);
            akkuhalter();
        }
        bodendeckel_luft(0);
        for (sl = lug_slots) translate([lug_x, sl[0], -1]) linear_extrude(lug_t + 2) rotate(sl[1]) langloch2d(lug_hole, lug_slot);
        if (mit_kammern) kammern_bodendeckel();
    }
}

// ---------------- Platzhalter ----------------
module platine_dummy() {
    translate([0, 0, pcb_z]) cube([pcb_w, pcb_h, pcb_t]);
    for (b = platine_bauteile) translate([b[1][0], b[1][1], pcb_top + b[1][2]]) cube(b[2] - b[1]);
}
module platine_ansicht() { translate([0, 0, pcb_top]) import("platine.stl"); }
// Raum, den die bestueckte Platine beim Einsetzen von hinten ueberstreicht (0,3 mm Luft)
module platine_sweep() {
    translate([-0.3, -0.3, 0]) cube([pcb_w + 0.6, pcb_h + 0.6, pcb_top]);
    for (b = platine_bauteile) if (b[2][2] > 0) translate([b[1][0] - 0.3, b[1][1] - 0.3, 0]) cube([b[2][0] - b[1][0] + 0.6, b[2][1] - b[1][1] + 0.6, pcb_top + b[2][2]]);
}
module zelle() { translate([cell_x0, cell_y, cell_z]) rotate([0, 90, 0]) cylinder(d = cell_d, h = cell_l); }
// Schraubendreher D 3 senkrecht auf die Klemmenschrauben (J1: 2-polig, J3: 4-polig, Raster 5,08), bis vor die Front
module schraubendreher() {
    for (y = [59.0, 59.0 - 5.08]) translate([j1_screw_x, y, term_top]) cylinder(d = 3, h = H + tl + 10 - term_top);
    for (i = [0 : 3]) translate([j3_screw_x, 12.38 + i * 5.08, term_top]) cylinder(d = 3, h = H + tl + 10 - term_top);
}
// Kontermutter (Sechskant, eine Schluesselflaeche zum Nachbarn) in der Tasche an der Aussenhaut
module kontermutter_dummy() {
    for (g = glands) wand_frame(g[0], g[1], gland_z) translate([0, 0, t - gland_wall - gland_nut_t(g)]) linear_extrude(gland_nut_t(g)) hex2d(gland_af(g));
}
// Huelle der eingebauten Verschraubung aussen (Bibliothek, 1 mm Schluesselraum) muss frei von Deckeln und Laschen sitzen
// Bibliothek: z = 0 Wandaussenseite, +z nach aussen -> in wand_frame um t verschoben
module verschraubung_aussen() {
    for (g = glands) wand_frame(g[0], g[1], gland_z) translate([0, 0, t])
        cable_gland_envelope(g[2], wall_actual = gland_wall, side = "outside", wrench = 1);
}
// Gewindeschaft innen (ohne Kontermutter, die liegt im Sechskant): muss in der Tasche frei sein
module verschraubung_innen() {
    for (g = glands) wand_frame(g[0], g[1], gland_z) translate([0, 0, t - gland_wall]) {
        dep = cable_gland_inside_depth(g[2], wall = gland_wall);
        translate([0, 0, -dep]) cylinder(d = cg(cable_gland_cfg(size = g[2]), "D"), h = dep + 0.01, $fn = 48);
    }
}
// echte Teile in Einbaulage (Ansicht)
module verschraubungen() {
    for (g = glands) wand_frame(g[0], g[1], gland_z) translate([0, 0, t]) cable_gland_mounted(g[2], wall_actual = gland_wall, fn = 32);
}
// Pruefkoerper: alles, was bei einem Gehaeuse um k_min nicht Material ist (Innenraum, Aussenluft, Bohrungen)
module gehaeuse_nicht_material(e) {
    translate([0, 0, tb - 2]) linear_extrude(H - tb + 2 + e) offset(r = e) inner2d();
    difference() {
        translate([-200, -200, -10]) cube([600, 600, 200]);
        translate([0, 0, tb + e]) linear_extrude(H + tl - tb - 2 * e) offset(r = -e) outer2d();
    }
    gehaeuse_luft(e);
}
module klemmdeckel_nicht_material(r, e) {
    difference() {
        translate([-200, -200, -10]) cube([600, 600, 200]);
        translate([0, 0, H + e]) linear_extrude(tl - 2 * e) offset(delta = -e) klemmdeckel2d(r);
    }
    klemmdeckel_luft(r, e);
}
module bodendeckel_nicht_material(e) {
    difference() {
        translate([-200, -200, -10]) cube([600, 600, 200]);
        translate([0, 0, e]) linear_extrude(tb - 2 * e) offset(delta = -e) outer2d();
    }
    bodendeckel_luft(e);
}

// ---------------- Ausgabe ----------------
if (part == "gehaeuse") rotate([180, 0, 0]) translate([0, 0, -H - tl]) gehaeuse();      // Front aufs Bett
else if (part == "bodendeckel") bodendeckel();                                            // Wandseite aufs Bett
else if (part == "klemmdeckel_solar") rotate([180, 0, 0]) translate([0, 0, -H - tl]) klemmdeckel(klemm_regions[0]);
else if (part == "klemmdeckel_sonde") rotate([180, 0, 0]) translate([0, 0, -H - tl]) klemmdeckel(klemm_regions[1]);
else if (part == "usb_deckel") rotate([0, -90, 0]) translate([-(ix1 + t), 0, 0]) usb_deckel();   // Aussenseite aufs Bett
else if (part == "usb_dichtung") usb_dichtung();
else if (part == "dichtung") dichtung();
else if (part == "klemmdichtung_solar") klemmdichtung(klemm_regions[0]);
else if (part == "klemmdichtung_sonde") klemmdichtung(klemm_regions[1]);
else if (part == "none") { }
// Kollisionspruefungen (leer bzw. nur Flaechenkontakt = in Ordnung). Ohne Kammern gerechnet (gleiche Aussen-/
// Innenflaechen); dass die Kammern innen geschlossen sind, pruefen die kollision_kammern_*.
else if (part == "kollision") intersection() { union() { gehaeuse(false); bodendeckel(false); for (r = klemm_regions) klemmdeckel(r, false); } union() { platine_dummy(); zelle(); } }
else if (part == "kollision_einbau") intersection() { gehaeuse(false); platine_sweep(); }
else if (part == "kollision_schraubendreher") intersection() { gehaeuse(false); schraubendreher(); }   // Klemmendeckel abgenommen
else if (part == "kollision_kontermutter") intersection() { kontermutter_dummy(); union() { gehaeuse(false); bodendeckel(false); platine_dummy(); zelle(); } }
else if (part == "kollision_verschraubung_innen") intersection() { verschraubung_innen(); union() { gehaeuse(false); bodendeckel(false); platine_dummy(); zelle(); } }
else if (part == "kollision_verschraubung") intersection() { verschraubung_aussen(); union() { gehaeuse(false); bodendeckel(false); usb_deckel(); for (r = klemm_regions) klemmdeckel(r, false); } }
else if (part == "kollision_bodendeckel") intersection() { bodendeckel(false); gehaeuse(false); }
else if (part == "kollision_klemmdeckel") intersection() { union() { for (r = klemm_regions) klemmdeckel(r, false); usb_deckel(); } gehaeuse(false); }
else if (part == "kollision_usb_deckel") intersection() { usb_deckel(); union() { gehaeuse(false); bodendeckel(false); for (r = klemm_regions) klemmdeckel(r, false); } }
// USB-C-Stecker (Umspritzling 12,4 x 6,6 mm) muss durch den Tunnel bis an die Buchse reichen (Prisma bis vor die Wand)
else if (part == "kollision_usb_stecker") intersection() { gehaeuse(false); translate([98.4, usb_c[0] - 6.2, usb_c[1] - 3.3]) cube([ix1 + t + 10 - 98.4, 12.4, 6.6]); }
else if (part == "kollision_zelle") intersection() { zelle(); union() { gehaeuse(false); platine_dummy(); } }
// Dichtnuten muessen vollstaendig unter Klemmendeckel bzw. Bodendeckel liegen (Rest = leer)
else if (part == "kollision_nut_deckel") {
    for (r = klemm_regions) difference() { linear_extrude(1) kgroove2d(r, gw); translate([0, 0, -1]) linear_extrude(3) klemmdeckel2d(r); }
    difference() { linear_extrude(1) groove2d(gw); translate([0, 0, -1]) linear_extrude(3) outer2d(); }
    difference() { linear_extrude(1) usb_groove2d(); translate([0, 0, -1]) linear_extrude(3) usb_plate2d(); }
}
// Kammern: ueberall mindestens k_min Material zu Innenraum, Aussenluft, Nuten, Bohrungen, Taschen
else if (part == "kollision_kammern_gehaeuse") intersection() { kammern_gehaeuse(); gehaeuse_nicht_material(k_min); }
else if (part == "kollision_kammern_bodendeckel") intersection() { kammern_bodendeckel(); bodendeckel_nicht_material(k_min); }
else if (part == "kollision_kammern_klemmdeckel") for (r = klemm_regions) intersection() { kammern_klemmdeckel(r); klemmdeckel_nicht_material(r, k_min); }
else if (part == "kammern") { color("tomato") kammern_gehaeuse(); color("gold") kammern_bodendeckel(); for (r = klemm_regions) color("orange") kammern_klemmdeckel(r); }
else {
    color("lightgray") translate([0, 0, 40]) gehaeuse();
    color("dimgray") translate([0, 0, 40]) verschraubungen();
    color("orange", 0.9) translate([0, 0, 60]) for (r = klemm_regions) klemmdeckel(r);
    color("orange", 0.9) translate([15, 0, 40]) usb_deckel();
    color("black") translate([0, 0, 20]) dichtung();
    color("white") bodendeckel();
    color("green") platine_ansicht();
    color("royalblue") zelle();
}
