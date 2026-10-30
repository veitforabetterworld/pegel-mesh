"""Erzeugt pegel-sender.kicad_pcb aus design.py: Umriss, Footprints mit Netzen, Netzklassen, Platzierung.

Aufruf mit dem Python von KiCad:
  "%LOCALAPPDATA%\\Programs\\KiCad\\10.0\\bin\\python.exe" gen_pcb.py
Danach routen (route.py) – das Routing wird nicht hier erzeugt.
"""

import math
import os
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import design  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "pegel-sender.kicad_pcb")
FP_ROOT = os.path.join(os.path.dirname(os.path.dirname(sys.executable)), "share", "kicad", "footprints")

W, H = 100.0, 70.0          # Platinengröße in mm (IP65-Gehäuse ca. 115 × 90 mm)
ORIGIN = (50.0, 50.0)       # Lage der Platine im KiCad-Blatt

# Netzklassen: (Name, Bahnbreite, Via-Durchmesser, Netze). Die Breite muss an die engsten Pins des Netzes passen
# (VSYS und +3V3 liegen an 0,5-mm-Pins, bleiben schmal); die 3 A tragen dort Kupferflächen (route.py), GND ist Fläche.
NETCLASSES = [
    ("Power3A", 1.2, 0.8, {"SOLAR_RAW", "SOLAR_F", "CHG_SW", "BAT_P", "HEAT_N"}),
    ("Power1A", 0.6, 0.8, {"VSOL", "CHG_CSP"}),
    ("Power", 0.4, 0.6, {"BAT_N", "PROT_D", "V12_RAW", "V12_PROBE", "BST_SW"}),
]

# Feste Lage wichtiger Bauteile: Ref -> (x, y, Drehung in Grad), Mitte des Bauteils in Platinenkoordinaten.
# Klemmen: +y des Footprints ist die Kabeleinführung, -90° zeigt sie nach links, 90° nach rechts.
FIXED = {
    "H1": (4, 4, 0), "H2": (96, 4, 0), "H3": (4, 66, 0), "H4": (96, 66, 0),
    "J1": (6.5, 15, -90),
    "J2": (6.5, 53, -90),
    "J3": (93.5, 50, 90),
    # XIAO: USB-Buchse zeigt nach rechts zur Platinenkante, D0 bzw. 5V an Pin 1 (x = 94).
    "J5": (86.38, 10, -90),
    "J6": (86.38, 25.24, -90),
    # Lader
    "F1": (16, 4.5, 0), "D2": (16, 11, 90), "D1": (16, 20, 90),
    "C2": (24, 7, 0), "C3": (24, 14, 0), "C4": (28, 14, 90),
    "Q1": (35, 7, 0),
    "L1": (48, 10, 0),
    "D3": (35, 16, 0),
    "R1": (48, 21, 0),
    "U1": (28, 23, 0),
    "C6": (60, 20, 0),
    # Akku
    "R8": (48, 29, 0),
    "U2": (40, 33, 0),
    "Q2": (17, 50, 0), "Q3": (17, 57, 0), "U3": (25, 52, 0),
    # Versorgungen
    "U4": (72, 33, 0), "L2": (72, 38, 0),
    "U5": (79, 45, 0), "L3": (73, 45, 0), "Q4": (85, 45, 0),
    # RS485
    "U6": (70, 55, 0), "Y1": (63, 55, 0), "U7": (82, 56, 0), "D6": (85, 63, 0),
    # Frost/Heizung
    "U8": (38, 46, 0), "TH1": (28, 41, 0), "Q6": (47, 50, 0), "Q7": (56, 63, 0),
    "R28": (22, 63, 90), "R29": (26, 63, 90), "R30": (30, 63, 90),
    "R31": (34, 63, 90), "R32": (38, 63, 90), "R33": (42, 63, 90),
}

KEEPOUT_XIAO = (77.0, 7.0, 99.0, 28.5)   # unter dem XIAO-Stapel nichts automatisch platzieren
MARGIN = 0.4


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


def setup_board(board):
    ds = board.GetDesignSettings()
    ds.SetCopperLayerCount(2)
    ds.SetAuxOrigin(pos(0, H))   # Nullpunkt für Bohr- und Bestückungsdaten: Ecke unten links
    ds.m_TrackMinWidth = mm(0.15)
    ds.m_MinClearance = mm(0.2)
    ds.m_ViasMinSize = mm(0.6)
    ds.m_MinThroughDrill = mm(0.2)
    ns = ds.m_NetSettings
    default = ns.GetDefaultNetclass()
    default.SetTrackWidth(mm(0.3))
    default.SetClearance(mm(0.2))
    default.SetViaDiameter(mm(0.6))
    default.SetViaDrill(mm(0.3))
    for name, width, via, members in NETCLASSES:
        nc = pcbnew.NETCLASS(name)
        nc.SetTrackWidth(mm(width))
        nc.SetClearance(mm(0.2))
        nc.SetViaDiameter(mm(via))
        nc.SetViaDrill(mm(0.4 if via > 0.6 else 0.3))
        ns.SetNetclass(name, nc)
        for net in members:
            ns.SetNetclassPatternAssignment(net, name)


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


def label(board, text, x, y, size=1.2):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(text)
    t.SetPosition(pos(x, y))
    t.SetLayer(pcbnew.F_SilkS)
    t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
    t.SetTextThickness(mm(size * 0.15))
    board.Add(t)


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
        center_at(fps[ref], x, y, rot)
        boxes.append(bbox_mm(fps[ref]))
        placed.add(ref)
    boxes.append(KEEPOUT_XIAO)

    def pad_xy(pad):
        p = pad.GetPosition()
        return pcbnew.ToMM(p.x) - ORIGIN[0], pcbnew.ToMM(p.y) - ORIGIN[1]

    # Restliche Bauteile nahe an die schon platzierten Pads ihrer Netze (ohne GND), dichteste Bindung zuerst.
    rest = [p for p in design.PARTS if p.ref not in placed]
    while rest:
        def anchors(p):
            pts = []
            for pad in fps[p.ref].Pads():
                net = p.pins.get(pad.GetNumber())
                if not net or net == design.GND:
                    continue
                for q in design.PARTS:
                    if q.ref in placed:
                        for qpad in fps[q.ref].Pads():
                            if q.pins.get(qpad.GetNumber()) == net:
                                pts.append(pad_xy(qpad))
            return pts

        rest.sort(key=lambda p: -len(anchors(p)))
        p = rest.pop(0)
        pts = anchors(p) or [(W / 2, H / 2)]
        cx = sum(a for a, _ in pts) / len(pts)
        cy = sum(b for _, b in pts) / len(pts)
        fp = fps[p.ref]
        best = None
        for rot in (0, 90):
            for ring in range(0, 120):
                r = ring * 0.5
                steps = max(1, int(2 * math.pi * r / 0.5))
                for k in range(steps):
                    a = 2 * math.pi * k / steps
                    x, y = cx + r * math.cos(a), cy + r * math.sin(a)
                    center_at(fp, x, y, rot)
                    bb = bbox_mm(fp)
                    if inside(bb) and not overlaps(bb, boxes):
                        if best is None or r < best[0]:
                            best = (r, x, y, rot)
                        break
                if best and best[0] <= r:
                    break
        if best is None:
            raise SystemExit(f"no place for {p.ref}")
        _, x, y, rot = best
        center_at(fp, x, y, rot)
        boxes.append(bbox_mm(fp))
        placed.add(p.ref)

    for fp in fps.values():
        fp.Reference().SetTextSize(pcbnew.VECTOR2I(mm(0.8), mm(0.8)))
        fp.Reference().SetTextThickness(mm(0.12))
        fp.Value().SetVisible(False)

    label(board, "SOLAR", 6.5, 7.5)
    label(board, "AKKU LiFePO4", 9, 46.5)
    label(board, "SONDE", 93, 37.5)
    label(board, "XIAO nRF52840 + Wio-SX1262 (USB ->)", 86, 30.5, 0.9)
    label(board, "pegel-sender v1", 70, 67.5)

    pcbnew.SaveBoard(OUT, board)
    print("saved", OUT, len(fps), "footprints,", len(nets), "nets")


if __name__ == "__main__":
    main()
