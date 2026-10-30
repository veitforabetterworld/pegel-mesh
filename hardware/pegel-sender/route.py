"""Routet pegel-sender.kicad_pcb mit Freerouting und legt die Kupferflächen an.

  "%LOCALAPPDATA%\\Programs\\KiCad\\10.0\\bin\\python.exe" route.py <pfad\\zu\\freerouting.jar> [java.exe]

1. Specctra-DSN exportieren, 2. Freerouting ohne Oberfläche laufen lassen, 3. SES zurückimportieren,
4. GND-Flächen oben und unten plus breite Flächen für die 3-A-Netze, 5. füllen und speichern.
"""

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
    ("VSOL", (19, 1.5, 41, 16), 3),
    ("CHG_SW", (31, 11, 42, 20), 4),
    ("VSYS", (43, 17, 66, 27), 3),
    ("BAT_P", (1, 26, 52, 36), 2),
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
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL if net == "GND" else pcbnew.ZONE_CONNECTION_FULL)
    o = z.Outline()
    o.NewOutline()
    x1, y1, x2, y2 = rect
    for x, y in ((x1, y1), (x2, y1), (x2, y2), (x1, y2)):
        o.Append(pt(x, y))
    board.Add(z)


def main():
    jar = sys.argv[1]
    java = sys.argv[2] if len(sys.argv) > 2 else "java"
    os.makedirs(os.path.dirname(DSN), exist_ok=True)

    board = pcbnew.LoadBoard(PCB)
    for t in list(board.GetTracks()):
        board.Remove(t)
    for z in list(board.Zones()):
        board.Remove(z)
    if not pcbnew.ExportSpecctraDSN(board, DSN):
        raise SystemExit("DSN export failed")

    subprocess.run([java, "-jar", jar, "-de", DSN, "-do", SES, "-mp", "40", "--gui.enabled=false"], check=True)

    if not pcbnew.ImportSpecctraSES(board, SES):
        raise SystemExit("SES import failed")
    for net, rect, prio in POWER_ZONES:
        zone(board, net, pcbnew.F_Cu, rect, prio)
    zone(board, "GND", pcbnew.F_Cu, (0.5, 0.5, W - 0.5, H - 0.5), 0)
    zone(board, "GND", pcbnew.B_Cu, (0.5, 0.5, W - 0.5, H - 0.5), 0)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(PCB, board)
    print("routed and saved", PCB)


if __name__ == "__main__":
    main()
