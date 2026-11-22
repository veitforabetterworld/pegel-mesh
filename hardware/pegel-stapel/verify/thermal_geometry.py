"""Geometrie der 5-V-Ladeplatine für thermal.py: liest die .kicad_pcb (nur lesen) und gibt JSON auf stdout aus.

Aufruf mit KiCad-Python: python thermal_geometry.py <pegel-lader-5v.kicad_pcb>
"""

import json
import sys

import pcbnew

ORIGIN = 50.0
board = pcbnew.LoadBoard(sys.argv[1])
mm = pcbnew.ToMM


def xy(p):
    return [round(mm(p.x) - ORIGIN, 4), round(mm(p.y) - ORIGIN, 4)]


def box(bb):
    return xy(bb.GetOrigin()) + xy(bb.GetEnd())


out = {"thickness": mm(board.GetDesignSettings().GetBoardThickness()), "pads": [], "tracks": [], "vias": [],
       "bodies": [], "zones": []}

for fp in board.GetFootprints():
    ref = fp.GetReference()
    for pad in fp.Pads():
        out["pads"].append({
            "ref": ref, "num": pad.GetNumber(), "net": pad.GetNetname(), "at": xy(pad.GetPosition()),
            "box": box(pad.GetBoundingBox()), "round": pad.GetShape() == pcbnew.PAD_SHAPE_CIRCLE,
            "drill": mm(pad.GetDrillSize().x) if pad.HasHole() else 0.0,
            "front": pad.IsOnLayer(pcbnew.F_Cu), "back": pad.IsOnLayer(pcbnew.B_Cu),
        })
    fab = [box(g.GetBoundingBox()) for g in fp.GraphicalItems()
           if g.GetClass() == "PCB_SHAPE" and g.GetLayer() == pcbnew.F_Fab]
    if fab:
        out["bodies"].append({
            "ref": ref, "fp": str(fp.GetFPID().GetLibItemName()), "value": fp.GetValue(),
            "box": [min(b[0] for b in fab), min(b[1] for b in fab), max(b[2] for b in fab), max(b[3] for b in fab)],
        })

for t in board.GetTracks():
    if t.GetClass() == "PCB_VIA":
        out["vias"].append({"at": xy(t.GetPosition()), "d": mm(t.GetWidth(pcbnew.F_Cu)), "drill": mm(t.GetDrillValue())})
    else:
        out["tracks"].append({"a": xy(t.GetStart()), "b": xy(t.GetEnd()), "w": mm(t.GetWidth()),
                              "front": t.GetLayer() == pcbnew.F_Cu})

for z in board.Zones():    # gespeicherte Füllung, samt Wärmefallen
    if z.GetIsRuleArea():
        continue
    for layer in z.GetLayerSet().Seq():
        poly = z.GetFilledPolysList(layer)
        for i in range(poly.OutlineCount()):
            rings = [poly.Outline(i)] + [poly.Hole(i, h) for h in range(poly.HoleCount(i))]
            out["zones"].append({"front": layer == pcbnew.F_Cu,
                                 "rings": [[xy(c.CPoint(k)) for k in range(c.PointCount())] for c in rings]})

print("JSON" + json.dumps(out))
