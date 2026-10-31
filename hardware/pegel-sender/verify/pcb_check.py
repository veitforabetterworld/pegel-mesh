"""Leiterbahnen der Hochstrompfade prüfen (mit KiCad-Python: kicad_env.pcbnew_python()).

Für jeden Pfad (Pad → Pad, Strom aus der Simulation) wird der breiteste durchgehende Kupferweg gesucht
(Bahnen, Vias, gefüllte Flächen) und seine Engstelle mit der nötigen Breite nach IPC-2221 verglichen:
außen, 35 µm Kupfer, 20 K Erwärmung. Vias zählen wie eine Bahn von Umfang × Hülsendicke (20 µm).
"""

import heapq
import math
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(os.path.dirname(HERE), "pegel-sender.kicad_pcb")
REPORT = os.path.join(HERE, "report")
ZONE_W = 10.0     # Fläche: als 10 mm breit gewertet

# (Pfad, von Ref.Pad, nach Ref.Pad, Strom [A] Dauer/Spitze laut Simulation)
PATHS = [
    ("Panel → Sicherung", "J1.1", "F1.1", 1.2),
    ("Sicherung → Verpolschutz D2", "F1.2", "D2.2", 1.2),
    ("Netzteil → Sicherung", "J7.1", "F2.1", 1.0),
    ("Sicherung → Diode D9", "F2.2", "D9.2", 1.0),
    ("Diode D9 → VSOL (Lader)", "D9.1", "Q1.3", 1.0),
    ("VSOL → Q1 (Lader-Eingang)", "D2.1", "Q1.3", 1.2),
    ("VSOL → Heizwiderstände", "D2.1", "R28.1", 0.4),
    ("Heizung → Q7", "R33.2", "Q7.3", 0.4),
    ("Schaltknoten Q1 → L1", "Q1.2", "L1.1", 3.3),
    ("Freilaufdiode D3 → L1", "D3.1", "L1.1", 3.0),
    ("L1 → Strommess-R1", "L1.2", "R1.1", 3.0),
    ("R1 → Shunt R8 (VSYS)", "R1.2", "R8.1", 3.0),
    ("Shunt R8 → Akku+", "R8.2", "J2.1", 3.0),
    ("Akku− → Schutz-FET Q2", "J2.2", "Q2.2", 1.5),
    ("Akku− → Schutz-FET Q3", "J2.2", "Q3.2", 1.5),
    ("Schutz-FET Q2 → GND (Lader)", "Q2.6", "D3.2", 1.5),
    ("Schutz-FET Q3 → GND (Lader)", "Q3.6", "D3.2", 1.5),
    ("VSYS → 12-V-Wandler L3", "R8.1", "L3.1", 1.2),
    ("L3 → U5 Schalter", "L3.2", "U5.1", 1.2),
    ("L3 → D5", "L3.2", "D5.2", 1.2),
    ("D5 → Q4 (12 V)", "D5.1", "Q4.2", 0.2),
    ("Q4 → Sonde", "Q4.3", "J3.1", 0.2),
    ("VSYS → 3,3-V-Wandler", "R8.1", "U4.10", 0.25),
    ("3,3 V → XIAO", "U9.6", "J6.3", 0.15),
]


def ipc_width_mm(current, dt=20.0, oz=1.0):
    """IPC-2221 außen: I = 0,048 · ΔT^0,44 · A^0,725 (A in mil²)."""
    area = (current / (0.048 * dt ** 0.44)) ** (1 / 0.725)
    return area / (1.378 * oz) * 0.0254


def build_graph(board):
    """Knoten: Pads, Bahnenden, Vias, Flächeninseln. Kanten mit Breite [mm]."""
    adj: dict[str, list] = {}

    def link(a, b, w):
        adj.setdefault(a, []).append((b, w))
        adj.setdefault(b, []).append((a, w))

    mm = pcbnew.ToMM
    pads = []
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            key = f"{fp.GetReference()}.{pad.GetNumber()}"
            pads.append((key, pad))
            adj.setdefault(key, [])
    tracks = [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK"]
    vias = [t for t in board.GetTracks() if t.GetClass() == "PCB_VIA"]

    def pkey(layer, p):
        return f"{layer}:{round(mm(p.x), 3)}:{round(mm(p.y), 3)}"

    points = []   # (key, layer, VECTOR2I, net)
    for t in tracks:
        a, b = pkey(t.GetLayer(), t.GetStart()), pkey(t.GetLayer(), t.GetEnd())
        link(a, b, mm(t.GetWidth()))
        points += [(a, t.GetLayer(), t.GetStart(), t.GetNetname()), (b, t.GetLayer(), t.GetEnd(), t.GetNetname())]
    for v in vias:
        w = math.pi * mm(v.GetDrillValue()) * 0.020 / 0.035   # Hülse 20 µm gegen Bahn 35 µm
        a, b = pkey(pcbnew.F_Cu, v.GetPosition()), pkey(pcbnew.B_Cu, v.GetPosition())
        link(a, b, w)
        points += [(a, pcbnew.F_Cu, v.GetPosition(), v.GetNetname()), (b, pcbnew.B_Cu, v.GetPosition(), v.GetNetname())]
    # Bahnende/Via in einem Pad
    for key, layer, pos, net in points:
        for pkey_, pad in pads:
            if pad.GetNetname() == net and pad.IsOnLayer(layer) and pad.HitTest(pos):
                link(key, pkey_, 10.0)
    # Bahnende auf einer anderen Bahn (T-Abzweig)
    for key, layer, pos, net in points:
        for t in tracks:
            if t.GetNetname() == net and t.GetLayer() == layer and t.HitTest(pos):
                link(key, pkey(layer, t.GetStart()), mm(t.GetWidth()))
                link(key, pkey(layer, t.GetEnd()), mm(t.GetWidth()))
    # Flächeninseln
    for zi, z in enumerate(board.Zones()):
        if z.GetIsRuleArea():
            continue
        for layer in z.GetLayerSet().Seq():   # Fläche kann auf beiden Lagen liegen
            polys = z.GetFilledPolysList(layer)
            for isl in range(polys.OutlineCount()):
                zkey = f"zone{zi}.{layer}.{isl}"
                for key, ly, pos, net in points:
                    if ly == layer and net == z.GetNetname() and polys.Contains(pos, isl):
                        link(key, zkey, ZONE_W)
                for pkey_, pad in pads:
                    if pad.GetNetname() != z.GetNetname() or not pad.IsOnLayer(layer):
                        continue
                    # Pad hängt an der Fläche, wenn sie das Pad irgendwo überdeckt (Mitte oder Randpunkte)
                    c, sz = pad.GetPosition(), pad.GetBoundingBox()
                    probes = [c] + [pcbnew.VECTOR2I(int(c.x + fx * sz.GetWidth() * 0.4), int(c.y + fy * sz.GetHeight() * 0.4))
                                    for fx, fy in ((-1, 0), (1, 0), (0, -1), (0, 1))]
                    if any(polys.Contains(pt, isl) for pt in probes):
                        link(pkey_, zkey, ZONE_W)
    return adj


def widest(adj, a, b):
    """Breitester Weg (größte Engstelle) von a nach b; gibt Engstelle in mm."""
    best = {a: float("inf")}
    heap = [(-float("inf"), a)]
    while heap:
        w, n = heapq.heappop(heap)
        w = -w
        if n == b:
            return w
        if w < best.get(n, 0):
            continue
        for m, ew in adj.get(n, []):
            nw = min(w, ew)
            if nw > best.get(m, 0):
                best[m] = nw
                heapq.heappush(heap, (-nw, m))
    return 0.0


def main():
    board = pcbnew.LoadBoard(PCB)
    adj = build_graph(board)
    rows, bad = [], 0
    for name, a, b, amps in PATHS:
        w = widest(adj, a, b)
        need = ipc_width_mm(amps)
        ok = w >= need
        bad += not ok
        rows.append((name, a, b, amps, w, need, ok))
        print(f"{'OK ' if ok else 'ZU SCHMAL'} {name:36s} {amps:4.1f} A  Engstelle {w:5.2f} mm  nötig {need:4.2f} mm")
    ds = board.GetDesignSettings()
    os.makedirs(REPORT, exist_ok=True)
    lines = ["# Leiterbahnen (Hochstrompfade)", "",
             "Breitester Kupferweg je Pfad (Bahnen, Vias, Flächen); nötige Breite nach IPC-2221, außen, "
             "35 µm, 20 K Erwärmung. Flächen zählen als 10 mm.", "",
             "| Pfad | von → nach | Strom | Engstelle | nötig | |", "|---|---|---:|---:|---:|---|"]
    for name, a, b, amps, w, need, ok in rows:
        lines.append(f"| {name} | {a} → {b} | {amps:.1f} A | {w:.2f} mm | {need:.2f} mm | {'✓' if ok else '✗'} |")
    lines += ["", f"Mindestabstand {pcbnew.ToMM(ds.m_MinClearance):.2f} mm; höchste Spannung zwischen Netzen ≈ 27 V "
              "(Panel-Leerlauf kalt): IPC-2221 B2 (außen, unbeschichtet) verlangt 0,10 mm bis 30 V. ✓"]
    with open(os.path.join(REPORT, "pcb.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
