"""Routet pegel-sender.kicad_pcb mit Freerouting und legt die Kupferflächen an.

  "%LOCALAPPDATA%\\Programs\\KiCad\\10.0\\bin\\python.exe" route.py <pfad\\zu\\freerouting.jar> [java.exe]

1. Specctra-DSN exportieren, 2. Freerouting ohne Oberfläche laufen lassen, 3. SES zurückimportieren,
4. GND-Flächen oben und unten plus breite Flächen für die 3-A-Netze, 5. füllen und speichern.
"""

import math
import os
import subprocess
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(HERE, "pegel-sender.kicad_pcb")
DSN = os.path.join(HERE, "build", "pegel-sender.dsn")
SES = os.path.join(HERE, "build", "pegel-sender.ses")
ORIGIN = (50.0, 50.0)
W, H = 100.0, 70.0

# 3-A-Pfade als Kupferflächen auf F.Cu: Netz -> Rechteck (x1, y1, x2, y2) in Platinenkoordinaten, Priorität.
POWER_ZONES = [
    ("VSOL", (17, 1.5, 33, 16), 3),
    ("CHG_SW", (33, 1.5, 44.5, 20), 4),
    ("CHG_CSP", (43.5, 13, 57, 19.6), 4),
    ("VSYS", (43, 19.8, 66, 32), 3),
    ("BAT_N", (10, 46, 23, 62), 3),
]


def mm(v):
    return pcbnew.FromMM(v)


def pt(x, y):
    return pcbnew.VECTOR2I(mm(ORIGIN[0] + x), mm(ORIGIN[1] + y))


def zone(board, net, layer, rect, priority):
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNetCode(board.FindNet(net).GetNetCode())
    z.SetAssignedPriority(priority)
    z.SetLocalClearance(mm(0.3))
    z.SetMinThickness(mm(0.25))
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    o = z.Outline()
    o.NewOutline()
    x1, y1, x2, y2 = rect
    for x, y in ((x1, y1), (x2, y1), (x2, y2), (x1, y2)):
        o.Append(pt(x, y))
    board.Add(z)


VIA_D, VIA_DRILL = 0.6, 0.3


def stitch(board):
    """GND-Vias überall, wo die gefüllten GND-Flächen oben und unten die ganze Via aufnehmen: verbindet die
    Inseln der oberen Fläche mit der unteren. Bauteile mit GND-Pads ohne Flächenanschluss bekommen eine Via daneben."""
    gnd = board.FindNet("GND")
    fills = [z.GetFilledPolysList(z.GetLayer()) for z in board.Zones() if z.GetNetname() == "GND"]
    holes = [(pcbnew.ToMM(p.GetPosition().x) - ORIGIN[0], pcbnew.ToMM(p.GetPosition().y) - ORIGIN[1])
             for fp in board.GetFootprints() for p in fp.Pads() if p.HasHole()]
    vias = [(pcbnew.ToMM(t.GetPosition().x) - ORIGIN[0], pcbnew.ToMM(t.GetPosition().y) - ORIGIN[1])
            for t in board.GetTracks() if t.GetClass() == "PCB_VIA"]
    routed = len(vias)

    def fits(x, y):
        r = VIA_D / 2 + 0.05
        ring = [(x + r * math.cos(a * math.pi / 4), y + r * math.sin(a * math.pi / 4)) for a in range(8)]
        if any(math.hypot(x - hx, y - hy) < 4.0 for hx, hy in holes):
            return False
        if any(math.hypot(x - vx, y - vy) < 1.5 for vx, vy in vias):
            return False
        return all(f.Contains(pt(px, py)) for f in fills for px, py in ring + [(x, y)])

    def add(x, y):
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(pt(x, y))
        v.SetWidth(mm(VIA_D))
        v.SetDrill(mm(VIA_DRILL))
        v.SetNet(gnd)
        board.Add(v)
        vias.append((x, y))

    step = 0.25
    for i in range(int(W / 6)):
        for j in range(int(H / 6)):
            x, y = 3 + i * 6, 3 + j * 6
            # im 6-mm-Raster die nächste freie Stelle suchen
            for k in range(0, 9):
                cand = [(x + dx * step, y + dy * step) for dx in range(-k, k + 1) for dy in range(-k, k + 1)
                        if max(abs(dx), abs(dy)) == k]
                hit = next(((cx, cy) for cx, cy in cand if fits(cx, cy)), None)
                if hit:
                    add(*hit)
                    break
    print("stitching vias:", len(vias) - routed)


def main():
    jar = sys.argv[1]
    java = sys.argv[2] if len(sys.argv) > 2 else "java"
    os.makedirs(os.path.dirname(DSN), exist_ok=True)

    board = pcbnew.LoadBoard(PCB)
    for t in list(board.GetTracks()):
        board.Remove(t)
    for z in list(board.Zones()):
        board.Remove(z)
    # GND-Fläche unten vor dem Export: Freerouting behandelt sie als Plane und bindet GND-Pads per Via an.
    zone(board, "GND", pcbnew.B_Cu, (0.5, 0.5, W - 0.5, H - 0.5), 0)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    if not pcbnew.ExportSpecctraDSN(board, DSN):
        raise SystemExit("DSN export failed")

    subprocess.run([java, "-jar", jar, "-de", DSN, "-do", SES, "-mp", "100", "--gui.enabled=false"], check=True)

    if not pcbnew.ImportSpecctraSES(board, SES):
        raise SystemExit("SES import failed")
    for net, rect, prio in POWER_ZONES:
        zone(board, net, pcbnew.F_Cu, rect, prio)
    zone(board, "GND", pcbnew.F_Cu, (0.5, 0.5, W - 0.5, H - 0.5), 0)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    stitch(board)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(PCB, board)
    print("routed and saved", PCB)


if __name__ == "__main__":
    main()
