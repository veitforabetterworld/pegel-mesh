"""Footprint-Mitten aus pegel-sender.kicad_pcb → FIXED-Zeilen (stdout)."""
import os
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import design  # noqa: E402

ORIGIN = (50.0, 50.0)
PCB = os.path.join(os.path.dirname(__file__), "pegel-sender.kicad_pcb")

b = pcbnew.LoadBoard(PCB)
refs = {fp.GetReference(): fp for fp in b.GetFootprints()}
rows = []
for p in design.PARTS:
    fp = refs.get(p.ref)
    if fp is None:
        raise SystemExit(f"missing {p.ref}")
    anchor = fp.GetPosition()
    cx = pcbnew.ToMM(anchor.x) - ORIGIN[0]
    cy = pcbnew.ToMM(anchor.y) - ORIGIN[1]
    rot = int(round(fp.GetOrientation().AsDegrees())) % 360
    if rot > 180:
        rot -= 360
    rows.append((p.ref, round(cx, 2), round(cy, 2), rot))

for ref, x, y, rot in sorted(rows, key=lambda r: r[0]):
    print(f'    "{ref}": ({x}, {y}, {rot}),')
