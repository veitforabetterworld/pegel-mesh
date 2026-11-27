"""Erzeugt platine.stl (Ansicht) und platine_bauteile.scad (Hüllquader je Bauteil, für Kollisionsprüfungen)
aus ../pegel-sender-12v.step. Koordinaten: x nach rechts, y nach oben (KiCad-y gespiegelt), z = 0 Oberseite Platine.
Aufruf: ../build/step-venv/bin/python gen_platine.py  (Paket cascadio + trimesh)"""
import os
import cascadio
import numpy as np
import trimesh

HERE = os.path.dirname(os.path.abspath(__file__))
STEP = os.path.join(HERE, "..", "pegel-sender-12v.step")
GLB = os.path.join(HERE, "build", "platine.glb")
OFS = np.array([-50.0, 120.0, 0.0])   # STEP: x 50..150, y -120..-50 (m -> mm)

os.makedirs(os.path.dirname(GLB), exist_ok=True)
cascadio.step_to_glb(STEP, GLB)
scene = trimesh.load(GLB)
g = scene.graph

mesh = scene.to_geometry()
mesh.apply_scale(1000)
mesh.apply_translation(OFS)
mesh.export(os.path.join(HERE, "platine.stl"))

parents = g.transforms.parents
def under(node, top):
    while node in parents:
        if node == top:
            return True
        node = parents[node]
    return node == top

root = g.transforms.children[g.base_frame][0]
boxes = []
for child in g.transforms.children[root]:
    lo, hi = None, None
    for n in g.nodes_geometry:
        if not under(n, child):
            continue
        T, geo = g[n]
        m = scene.geometry[geo].copy()
        m.apply_transform(T)
        b = m.bounds * 1000 + OFS
        lo = b[0] if lo is None else np.minimum(lo, b[0])
        hi = b[1] if hi is None else np.maximum(hi, b[1])
    if lo is not None and child != "PCB":
        boxes.append((child, lo, hi))

with open(os.path.join(HERE, "platine_bauteile.scad"), "w") as f:
    f.write("// erzeugt von gen_platine.py aus pegel-sender-12v.step – nicht von Hand aendern\n")
    f.write("// [Name, [x0, y0, z0], [x1, y1, z1]], z = 0 Oberseite Platine\n")
    f.write("platine_bauteile = [\n")
    for name, lo, hi in boxes:
        f.write(f'    ["{name}", [{lo[0]:.2f}, {lo[1]:.2f}, {lo[2]:.2f}], [{hi[0]:.2f}, {hi[1]:.2f}, {hi[2]:.2f}]],\n')
    f.write("];\n")
print(len(boxes), "Bauteile, Hoehe max", max(b[2][2] for b in boxes), "min", min(b[1][2] for b in boxes))
