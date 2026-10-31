"""Erzeugt pegel-sender.kicad_pcb aus design.py: Umriss, Footprints mit Netzen, Netzklassen, Platzierung.

Aufruf mit Python, das pcbnew lädt (KiCad-Paket oder build/kicad-appimage/squashfs-root):
  python3 gen_pcb.py
Danach routen (route.py) – das Routing wird nicht hier erzeugt.
"""

import math
import os
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import design  # noqa: E402
import kicad_env  # noqa: E402
from fixed_positions import FIXED  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "pegel-sender.kicad_pcb")
FP_ROOT = kicad_env.footprint_root()

W, H = 100.0, 70.0          # Platinengröße in mm (IP65-Gehäuse ca. 115 × 90 mm)
ORIGIN = (50.0, 50.0)       # Lage der Platine im KiCad-Blatt

# Bahnbreite je Netz mit Reserve (IPC-2221, 35 µm außen, ≤ 10 K Erwärmung): 2,0 mm trägt ~4 A, 0,8 mm ~2 A,
# 0,6 mm ~1,6 A, 0,3 mm ~0,9 A. Die 3-A-Pfade liegen zusätzlich als Kupferflächen (route.py).
NET_WIDTH = [
    (2.0, {"CHG_SW", "CHG_OUT", "BAT_N"}),                                   # Ladestrom 2 A
    (1.2, {"VSYS"}),                                                          # Ladestrom und Lasten
    (0.8, {"IN_RAW", "VSOL", "HEAT_N", "BST_SW"}),                           # bis 1,2 A
    (0.6, {"V12_RAW", "V12_PROBE", "XIAO_3V3"}),                             # bis 0,15 A
    (0.5, {"RS_VCC", "+5V"}),
    (0.4, {"GND"}),                                                           # sonst Fläche
]
DEFAULT_WIDTH = 0.3
# Abstand: 0,3 mm für Netze über 12 V und die Leistungsnetze, sonst 0,25 mm. An Bauteilen mit engerem Pinabstand
# (0,5-mm-Raster) gilt für deren Netze der Abstand zwischen den Pads, mindestens 0,2 mm.
HV_NETS = {"IN_RAW", "VSOL", "CHG_SW", "CHG_BOOT", "BST_SW", "V12_RAW", "V12_PROBE", "HEAT_N", "HEAT_G", "VIN_J",
           "CHG_PGD"}
CLEARANCE, CLEARANCE_HV, CLEARANCE_MIN = 0.25, 0.3, 0.2

# Feste Lage aller Bauteile: fixed_positions.py (dump_fixed.py aus gerouteter Platine).

KEEPOUT_XIAO = (76.5, 7.0, 99.0, 28.5)   # unter dem XIAO-Stapel: kein Siebdruck
MARGIN = 0.4

# KiCad L_Bourns_SRP2313AA.step native ~23.5×22×12.6 mm → SRP1245A 13.5×12.5×4.8 mm
PROJECT_MODELS = {}


def apply_project_models(fps):
    for ref, (relpath, scale) in PROJECT_MODELS.items():
        fp = fps[ref]
        fp.Models().clear()
        md = pcbnew.FP_3DMODEL()
        md.m_Filename = "${KIPRJMOD}/" + relpath
        md.m_Scale = pcbnew.VECTOR3D(scale[0], scale[1], scale[2])
        md.m_Offset = pcbnew.VECTOR3D(0, 0, 0)
        md.m_Rotation = pcbnew.VECTOR3D(0, 0, 0)
        md.m_Show = True
        fp.Models().append(md)


def mm(v):
    return pcbnew.FromMM(v)


def pos(x, y):
    return pcbnew.VECTOR2I(mm(ORIGIN[0] + x), mm(ORIGIN[1] + y))


def bbox_mm(fp):
    try:
        bb = fp.GetBoundingBox(False)
    except TypeError:
        bb = fp.GetBoundingBox()
    return (pcbnew.ToMM(bb.GetLeft()) - ORIGIN[0], pcbnew.ToMM(bb.GetTop()) - ORIGIN[1],
            pcbnew.ToMM(bb.GetRight()) - ORIGIN[0], pcbnew.ToMM(bb.GetBottom()) - ORIGIN[1])


def place_at(fp, x, y, rot):
    """Footprint-Anker (KiCad Position) setzen — exakt wie in .kicad_pcb."""
    fp.SetOrientationDegrees(rot)
    fp.SetPosition(pos(x, y))


def center_at(fp, x, y, rot):
    fp.SetOrientationDegrees(rot)
    fp.SetPosition(pos(0, 0))
    l, t, r, b = bbox_mm(fp)
    fp.SetPosition(pos(x - (l + r) / 2, y - (t + b) / 2))


def overlaps(a, boxes):
    return any(not (a[2] + MARGIN <= b[0] or b[2] + MARGIN <= a[0] or a[3] + MARGIN <= b[1] or b[3] + MARGIN <= a[1])
               for b in boxes)


def inside(a):
    return a[0] >= 1.0 and a[1] >= 1.0 and a[2] <= W - 1.0 and a[3] <= H - 1.0


def item_box(item):
    bb = item.GetBoundingBox()
    return (pcbnew.ToMM(bb.GetLeft()) - ORIGIN[0], pcbnew.ToMM(bb.GetTop()) - ORIGIN[1],
            pcbnew.ToMM(bb.GetRight()) - ORIGIN[0], pcbnew.ToMM(bb.GetBottom()) - ORIGIN[1])


def boxes_hit(a, b, gap=0.0):
    return not (a[2] + gap <= b[0] or b[2] + gap <= a[0] or a[3] + gap <= b[1] or b[3] + gap <= a[1])


def silk_obstacles(board):
    """Pads und Bohrungen, auf denen kein Siebdruck liegen darf."""
    pads, holes = [], []
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            pads.append(item_box(pad))
            drill = pad.GetDrillSize()
            if drill.x > 0:
                p = pad.GetPosition()
                holes.append((pcbnew.ToMM(p.x) - ORIGIN[0], pcbnew.ToMM(p.y) - ORIGIN[1],
                              pcbnew.ToMM(max(drill.x, drill.y)) / 2))
    return pads, holes


def component_bodies(board):
    """Fab-Umriss der Bauteile plus die Fläche unter dem XIAO. Siebdruck darf darauf nicht liegen."""
    bodies = [KEEPOUT_XIAO]
    for fp in board.GetFootprints():
        fab = [item_box(gi) for gi in fp.GraphicalItems()
               if gi.GetLayer() == pcbnew.F_Fab and gi.GetClass() == "PCB_SHAPE"]
        silk = [item_box(gi) for gi in fp.GraphicalItems()
                if gi.GetLayer() == pcbnew.F_SilkS and gi.GetClass() == "PCB_SHAPE"]
        shapes = fab or silk
        if shapes:
            box = (min(b[0] for b in shapes) - 0.25, min(b[1] for b in shapes) - 0.25,
                   max(b[2] for b in shapes) + 0.25, max(b[3] for b in shapes) + 0.25)
        else:
            pads = [item_box(p) for p in fp.Pads()]
            if not pads:
                continue
            box = (min(b[0] for b in pads) - 0.55, min(b[1] for b in pads) - 0.55,
                   max(b[2] for b in pads) + 0.55, max(b[3] for b in pads) + 0.55)
        bodies.append(box)
    return bodies


def _set_text_angle(text, degrees):
    text.SetTextAngle(pcbnew.EDA_ANGLE(degrees, pcbnew.DEGREES_T))


def silk_reserve(bb):
    """Platz für Ref-Designator oberhalb des Footprints bei Auto-Platzierung."""
    l, t, r, b = bb
    return (l - 0.35, t - 2.0, r + 0.35, b + 0.35)


def field_ok(box, pads, holes, taken, bodies):
    if box[0] < 0.5 or box[1] < 0.5 or box[2] > W - 0.5 or box[3] > H - 0.5:
        return False
    if any(boxes_hit(box, p, 0.28) for p in pads):
        return False
    if any(boxes_hit(box, t, 0.15) for t in taken):
        return False
    if any(boxes_hit(box, b, 0.12) for b in bodies):
        return False
    for hx, hy, hr in holes:
        if boxes_hit(box, (hx - hr, hy - hr, hx + hr, hy + hr), 0.2):
            return False
    return True


def place_field_text(text, starts, pads, holes, taken, bodies, angle=0):
    """Text knapp neben Startpunkt oder Footprint — kein Spiral-Wandern über die Platine."""
    if not isinstance(starts, list):
        starts = [starts]
    for x0, y0 in starts:
        for dx, dy in ((0, 0), (0.55, 0), (-0.55, 0), (0, 0.55), (0, -0.55), (1.1, 0), (0, 1.1)):
            _set_text_angle(text, angle)
            text.SetPosition(pos(x0 + dx, y0 + dy))
            box = item_box(text)
            if field_ok(box, pads, holes, taken, bodies):
                taken.append(box)
                return True
    x0, y0 = starts[0]
    _set_text_angle(text, 0)
    text.SetPosition(pos(x0, y0))
    taken.append(item_box(text))
    return False


def ref_label_starts(fp):
    l, t, r, b = bbox_mm(fp)
    cx, cy = (l + r) / 2, (t + b) / 2
    return [
        (cx, t - 1.05),
        (cx, b + 1.05),
        (l - 1.05, cy),
        (r + 1.05, cy),
    ]


def shove_text(text, start, pads, holes, taken, bodies=(), max_radius=13.0):
    """Schiebt Text von Pads, Löchern, Körpern, anderem Text und dem Rand. Kein Fallback auf ein Bauteil."""
    def ok(box):
        return field_ok(box, pads, holes, taken, bodies)

    x0, y0 = start
    height = pcbnew.ToMM(text.GetTextHeight())
    radii = [i * 0.55 for i in range(0, 24) if i * 0.55 <= max_radius + 0.01]
    if not radii:
        radii = [0.0]
    for scale in (1.0, 0.6 / height if height > 0.6 else 1.0):
        h = max(0.6, height * scale)
        text.SetTextSize(pcbnew.VECTOR2I(mm(h), mm(h)))
        text.SetTextThickness(mm(max(0.08, h * 0.12)))
        for angle in (0, 90):
            _set_text_angle(text, angle)
            for radius in radii:
                steps = 1 if radius == 0 else max(8, int(radius * 6))
                for k in range(steps):
                    a = 2 * math.pi * k / steps
                    text.SetPosition(pos(x0 + radius * math.cos(a), y0 + radius * math.sin(a)))
                    box = item_box(text)
                    if ok(box):
                        taken.append(box)
                        return True
    _set_text_angle(text, 0)
    text.SetPosition(pos(x0, y0))
    try:
        shown = text.GetShownText(True)
    except TypeError:
        shown = text.GetText()
    print("silk has no free spot:", shown)
    return False


# (Text, x, y, Höhe mm, Ausrichtung wie label(): 0 Mitte, -1 links, 1 rechts[, Winkel])
BOARD_LABELS = [
    ("SOLAR/12V max 25V", 16.5, 2.3, 0.7, 0),
    ("AKKU LiFePO4", 50.0, 2.2, 0.7, 0),
    ("HEIZUNG / NTC", 12.6, 50.1, 0.7, 0, 90),
    ("SONDE 12V RS485", 79.8, 45.6, 0.75, 0, 90),   # senkrecht links neben den J3-Pin-Texten
    ("XIAO + Wio-SX1262", 74.0, 3.4, 0.75, 0),
    ("USB ->", 88.0, 5.2, 0.7, 0),
    ("pegel-sender v2", 30.0, 68.4, 0.8, 0),
    ("(c) Veit Götz", 52.0, 68.4, 0.8, 0),
]


def layout_silk(board):
    labels = {text for text, *_ in BOARD_LABELS}
    for drawing in list(board.GetDrawings()):
        if drawing.GetClass() != "PCB_TEXT":
            continue
        if drawing.GetText() in labels or drawing.GetText() in PIN_TEXTS:
            drawing.thisown = 0
            board.Delete(drawing)
    for fp in board.GetFootprints():
        ref = fp.Reference()
        ref.SetLayer(pcbnew.F_SilkS)
        ref.SetTextSize(pcbnew.VECTOR2I(mm(0.7), mm(0.7)))
        ref.SetTextThickness(mm(0.1))
        if fp.GetReference() in {"H1", "H2", "H3", "H4"}:
            ref.SetVisible(False)
        if fp.GetReference() in SHOW_VALUE:
            val = fp.Value()
            val.SetLayer(pcbnew.F_SilkS)
            val.SetVisible(True)
            val.SetTextSize(pcbnew.VECTOR2I(mm(0.6), mm(0.6)))
            val.SetTextThickness(mm(0.1))
        else:
            fp.Value().SetVisible(False)

    pads, holes = silk_obstacles(board)
    for fp in board.GetFootprints():
        for gi in fp.GraphicalItems():
            if gi.GetLayer() == pcbnew.F_SilkS and gi.GetClass() == "PCB_SHAPE":
                pads.append(item_box(gi))
    bodies = component_bodies(board)
    taken = []
    for text, x, y, size, align, *angle in BOARD_LABELS:
        t = label(board, text, x, y, size, align)
        if not place_field_text(t, (x, y), pads, holes, taken, bodies, *angle):
            shove_text(t, (x, y), pads, holes, taken, bodies, max_radius=3.5)
    for fp in board.GetFootprints():
        if not fp.Reference().IsVisible():
            continue
        ref = fp.Reference()
        spec = REF_FIELDS.get(fp.GetReference())
        if spec:
            x, y, size, align = spec
            ref.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
            ref.SetTextThickness(mm(max(0.08, size * 0.12)))
            if align:
                ref.SetHorizJustify(
                    pcbnew.GR_TEXT_H_ALIGN_LEFT if align < 0 else pcbnew.GR_TEXT_H_ALIGN_RIGHT
                )
            if not place_field_text(ref, (x, y), pads, holes, taken, bodies):
                shove_text(ref, (x, y), pads, holes, taken, bodies, max_radius=8.0)
        else:
            starts = ref_label_starts(fp)
            if not place_field_text(ref, starts, pads, holes, taken, bodies):
                shove_text(ref, starts[0], pads, holes, taken, bodies, max_radius=7.0)
        if fp.GetReference() in SHOW_VALUE and fp.Value().IsVisible():
            val = fp.Value()
            spec = VALUE_FIELDS.get(fp.GetReference())
            if spec:
                x, y, size, align = spec
                val.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
                val.SetTextThickness(mm(max(0.08, size * 0.12)))
                if align:
                    val.SetHorizJustify(
                        pcbnew.GR_TEXT_H_ALIGN_LEFT if align < 0 else pcbnew.GR_TEXT_H_ALIGN_RIGHT
                    )
                if not place_field_text(val, (x, y), pads, holes, taken, bodies):
                    shove_text(val, (x, y), pads, holes, taken, bodies, max_radius=8.0)
            else:
                l, t, r, b = bbox_mm(fp)
                cx = (l + r) / 2
                if not place_field_text(val, [(cx, b + 1.05)], pads, holes, taken, bodies):
                    shove_text(val, (cx, b + 1.05), pads, holes, taken, bodies, max_radius=5.0)
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    pin_labels(board, fps, pads, holes, taken, bodies)


def setup_board(board):
    ds = board.GetDesignSettings()
    ds.SetCopperLayerCount(2)
    ds.SetAuxOrigin(pos(0, H))   # Nullpunkt für Bohr- und Bestückungsdaten: Ecke unten links
    ds.m_TrackMinWidth = mm(0.15)
    ds.m_MinClearance = mm(0.2)
    ds.m_MinSilkTextHeight = mm(0.6)
    ds.m_MinSilkTextThickness = mm(0.08)
    ds.m_SilkClearance = mm(0.1)
    ds.m_ViasMinSize = mm(0.6)
    ds.m_MinThroughDrill = mm(0.2)
    ns = ds.m_NetSettings
    default = ns.GetDefaultNetclass()
    default.SetTrackWidth(mm(0.3))
    default.SetClearance(mm(0.2))
    default.SetViaDiameter(mm(0.6))
    default.SetViaDrill(mm(0.3))


def _pad_gap_limits(board):
    """Kleinster Abstand jedes Netzes zu einem fremden Pad im selben Bauteil."""
    limit = {}
    for fp in board.GetFootprints():
        pads = [(p.GetNetname(), item_box(p)) for p in fp.Pads()]
        for i, (na, a) in enumerate(pads):
            for nb, b in pads[i + 1:]:
                if na == nb and na:
                    continue
                gap = max(b[0] - a[2], a[0] - b[2], b[1] - a[3], a[1] - b[3])
                for n in (na, nb):
                    if n:
                        limit[n] = min(limit.get(n, 99.0), gap)
    return limit


def assign_netclasses(board):
    """Netzklasse je (Breite, Abstand). Breite aus NET_WIDTH, Abstand durch die engsten Pads des Netzes begrenzt."""
    ns = board.GetDesignSettings().m_NetSettings
    limit = _pad_gap_limits(board)
    width_of = {n: w for w, members in NET_WIDTH for n in members}
    classes = {}
    for net in sorted(design.nets()):
        want = CLEARANCE_HV if net in HV_NETS else CLEARANCE
        clr = max(CLEARANCE_MIN, min(want, math.floor(limit.get(net, 99.0) * 20 + 1e-6) / 20))
        classes.setdefault((width_of.get(net, DEFAULT_WIDTH), clr), []).append(net)
    for (width, clr), members in sorted(classes.items()):
        name = f"W{width:g}_C{clr:g}"
        nc = pcbnew.NETCLASS(name)
        nc.SetTrackWidth(mm(width))
        nc.SetClearance(mm(clr))
        via = 1.2 if width >= 1.5 else 0.8 if width >= 0.8 else 0.6
        nc.SetViaDiameter(mm(via))
        # Via-Hülse 20 µm: 0,6 mm Bohrung trägt wie ~1,1 mm Bahn, zwei davon reichen für 3 A
        nc.SetViaDrill(mm(0.6 if via >= 1.2 else 0.4 if via > 0.6 else 0.3))
        ns.SetNetclass(name, nc)
        for net in members:
            ns.SetNetclassPatternAssignment(net, name)
        print(f"netclass {name}: {len(members)} nets")


def outline(board):
    pts = [(0, 0), (W, 0), (W, H), (0, H)]
    for i in range(4):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(pos(*pts[i]))
        s.SetEnd(pos(*pts[(i + 1) % 4]))
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(mm(0.1))
        board.Add(s)


def label(board, text, x, y, size=1.2, align=0):
    """Text auf F.SilkS; align -1 linksbündig ab x, 1 rechtsbündig bis x. Gibt die belegte Fläche zurück."""
    t = pcbnew.PCB_TEXT(board)
    t.SetText(text)
    t.SetPosition(pos(x, y))
    t.SetLayer(pcbnew.F_SilkS)
    t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
    t.SetTextThickness(mm(size * 0.15))
    if align:
        t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT if align < 0 else pcbnew.GR_TEXT_H_ALIGN_RIGHT)
    board.Add(t)
    return t


# Beschriftung der Klemmen: Ref -> Text je Pin, steht neben dem Pin auf der Platinenseite der Klemme.
PIN_LABELS = {
    "J1": {"1": "+", "2": "-"},
    "J2": {"1": "-", "2": "+"},
    "J4": {"1": "H+", "2": "H-", "3": "NTC", "4": "NTC"},
    "J3": {"1": "V+ rot", "2": "V- schwarz", "3": "A weiss", "4": "B blau"},
}
PIN_TEXTS = {v for m in PIN_LABELS.values() for v in m.values()}
# Bauteile, deren Wert auf dem Bestückungsdruck steht (Lötbrücke, Steckbrücke).
SHOW_VALUE = {"JP2"}
# (x, y, Höhe mm, align) — Werte weg von Nachbar-Silk (DRC)
VALUE_FIELDS = {
    "JP2": (25.5, 42.3, 0.6, 0),
}
# Ref-Designator abseits dichtem Nachbar-Silk
REF_FIELDS = {
    "J6": (82.8, 26.2, 0.55, 0),
}


def pin_labels(board, fps, pads=None, holes=None, taken=None, bodies=None):
    """Klemmen-Pin-Texte. Ohne pads/taken: nur Reservierung für Platzierung (boxes)."""
    boxes = []
    for ref, texts in PIN_LABELS.items():
        fp = fps[ref]
        l, _, r, _ = bbox_mm(fp)
        right_side = (l + r) / 2 < W / 2
        for pad in fp.Pads():
            text = texts.get(pad.GetNumber())
            if not text:
                continue
            y = pcbnew.ToMM(pad.GetPosition().y) - ORIGIN[1]
            if ref == "J2":   # Klemme an der Oberkante: Text unter dem Pin
                t = label(board, text, pcbnew.ToMM(pad.GetPosition().x) - ORIGIN[0], bbox_mm(fp)[3] + 0.9, 0.75, 0)
                anchor, y = pcbnew.ToMM(pad.GetPosition().x) - ORIGIN[0], bbox_mm(fp)[3] + 0.9
            else:
                if ref == "J3":
                    anchor = l - 1.4
                else:
                    anchor = r + 1.2 if right_side else l - 1.2
                align = -1 if right_side else 1
                t = label(board, text, anchor, y, 0.75, align)
            if pads is not None:
                if not place_field_text(t, (anchor, y), pads, holes, taken, bodies):
                    shove_text(t, (anchor, y), pads, holes, taken, bodies, max_radius=6.0)
            else:
                boxes.append(silk_reserve(item_box(t)))
    return boxes


def main():
    board = pcbnew.BOARD()
    setup_board(board)
    outline(board)

    nets = {}
    for name in sorted(design.nets()):
        n = pcbnew.NETINFO_ITEM(board, name)
        board.Add(n)
        nets[name] = n

    fps = {}
    for p in design.PARTS:
        lib, name = p.footprint.split(":")
        fp = pcbnew.FootprintLoad(os.path.join(FP_ROOT, lib + ".pretty"), name)
        if fp is None:
            raise SystemExit(f"footprint not found: {p.footprint}")
        fp.SetReference(p.ref)
        fp.SetValue(p.value)
        fp.SetFPIDAsString(p.footprint)
        if p.mpn:
            fp.SetField("MPN", p.mpn)
            fp.GetField("MPN").SetVisible(False)
        if p.dnp or not p.mpn:
            fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
        if p.dnp:
            fp.SetDNP(True)
        for pad in fp.Pads():
            net = p.pins.get(pad.GetNumber())
            if net:
                pad.SetNet(nets[net])
        board.Add(fp)
        fps[p.ref] = fp

    boxes = []
    placed = set()
    for ref, (x, y, rot) in FIXED.items():
        place_at(fps[ref], x, y, rot)
        boxes.append(silk_reserve(bbox_mm(fps[ref])))
        placed.add(ref)
    boxes.append(KEEPOUT_XIAO)
    boxes += pin_labels(board, fps)

    missing = [p.ref for p in design.PARTS if p.ref not in placed]
    if missing:
        raise SystemExit(f"FIXED fehlt für: {', '.join(sorted(missing))}")

    assign_netclasses(board)
    apply_project_models(fps)
    layout_silk(board)

    pcbnew.SaveBoard(OUT, board)
    print("saved", OUT, len(fps), "footprints,", len(nets), "nets")


if __name__ == "__main__":
    main()
