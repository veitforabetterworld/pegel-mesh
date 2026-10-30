"""Routet pegel-sender.kicad_pcb mit Freerouting und legt die Kupferflächen an.

  KiCad-Python route.py <pfad/zu/freerouting.jar> [java]

Kompletter Neuaufbau inkl. Fab/3D: python3 relayout.py (ruft dieses Skript auf).
Voraussetzung: gen_pcb.py lief zuvor oder wird hier zu Beginn jedes Versuchs erneut gestartet.

1. Specctra-DSN exportieren, 2. Freerouting ohne Oberfläche laufen lassen, 3. SES zurückimportieren,
4. GND-Flächen oben und unten plus breite Flächen für die 3-A-Netze, 5. füllen und speichern.
"""

import heapq
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile

import pcbnew

sys.path.insert(0, HERE := os.path.dirname(os.path.abspath(__file__)))
import kicad_env  # noqa: E402
PCB = os.path.join(HERE, "pegel-sender.kicad_pcb")
DSN = os.path.join(HERE, "build", "pegel-sender.dsn")
SES = os.path.join(HERE, "build", "pegel-sender.ses")
ORIGIN = (50.0, 50.0)
W, H = 100.0, 70.0

# 3-A-Pfade als Kupferflächen auf F.Cu: Netz -> Rechteck (x1, y1, x2, y2) in Platinenkoordinaten, Priorität.
POWER_ZONES = [
    ("VSOL", (17, 1.5, 33, 16), 3),
    ("DC_F", (14, 26, 22, 44), 3),
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
    fills = [z.GetFilledPolysList(z.GetLayer())
             for z in board.Zones() if z.GetNetname() == "GND" and z.GetLayer() == pcbnew.B_Cu]
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
    # dichteres Raster im XIAO-/3V3-Bereich (GND-Inseln durch Power-Zonen)
    for x in range(72, 99, 3):
        for y in range(8, 34, 3):
            for k in range(0, 6):
                cand = [(x + dx * step, y + dy * step) for dx in range(-k, k + 1) for dy in range(-k, k + 1)
                        if max(abs(dx), abs(dy)) == k]
                hit = next(((cx, cy) for cx, cy in cand if fits(cx, cy)), None)
                if hit:
                    add(*hit)
                    break
    print("stitching vias:", len(vias) - routed)


def link_pads(board, ref_a, pad_a, ref_b, pad_b, width_mm=0.4):
    """Kurzverbindung, wenn der Autorouter ein Nachbar-Paar nicht schafft."""
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    a = fps[ref_a].FindPadByNumber(str(pad_a))
    b = fps[ref_b].FindPadByNumber(str(pad_b))
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(a.GetPosition())
    t.SetEnd(b.GetPosition())
    t.SetWidth(mm(width_mm))
    t.SetLayer(pcbnew.F_Cu)
    t.SetNet(a.GetNet())
    board.Add(t)


def gnd_track(board, x1, y1, x2, y2, width_mm=0.5):
    gnd = board.FindNet("GND")
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(pt(x1, y1))
    t.SetEnd(pt(x2, y2))
    t.SetWidth(mm(width_mm))
    t.SetLayer(pcbnew.F_Cu)
    t.SetNet(gnd)
    board.Add(t)


def gnd_via(board, x, y):
    gnd = board.FindNet("GND")
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(pt(x, y))
    v.SetWidth(mm(VIA_D))
    v.SetDrill(mm(VIA_DRILL))
    v.SetNet(gnd)
    board.Add(v)


def connect_open_pads(board, max_mm=5.0):
    """Deaktiviert — erzeugte falsche Verbindungen im DRC."""
    del board, max_mm


def connect_gnd_pad(board, ref, pad_num):
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    pad = fps[ref].FindPadByNumber(str(pad_num))
    if pad.GetNetname() != "GND":
        return
    gnd = board.FindNet("GND")
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(pad.GetPosition())
    v.SetWidth(mm(VIA_D))
    v.SetDrill(mm(VIA_DRILL))
    v.SetNet(gnd)
    board.Add(v)


def merge_net_track_ends(board, netname, max_mm=2.5):
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        tracks = [t for t in board.GetTracks()
                  if t.GetClass() == "PCB_TRACK" and t.GetNet() and t.GetNet().GetNetname() == netname
                  and t.GetLayer() == layer]
        if len(tracks) < 2:
            continue
        ends = []
        for t in tracks:
            for p in (t.GetStart(), t.GetEnd()):
                ends.append((pcbnew.ToMM(p.x) - ORIGIN[0], pcbnew.ToMM(p.y) - ORIGIN[1], p, t.GetNet()))
        used = set()
        for i, (x1, y1, p1, net) in enumerate(ends):
            if i in used:
                continue
            best = None
            for j, (x2, y2, p2, _) in enumerate(ends):
                if j <= i or j in used:
                    continue
                d = math.hypot(x1 - x2, y1 - y2)
                if 0.05 < d <= max_mm and (best is None or d < best[0]):
                    best = (d, j, p2)
            if best:
                _, j, p2 = best
                t = pcbnew.PCB_TRACK(board)
                t.SetStart(p1)
                t.SetEnd(p2)
                t.SetWidth(mm(0.25))
                t.SetLayer(layer)
                t.SetNet(net)
                board.Add(t)
                used.update({i, j})


def merge_gnd_track_ends(board, max_mm=2.5):
    merge_net_track_ends(board, "GND", max_mm)


def gnd_fcu_bridges(board):
    """Reserviert — frühere F.Cu-Brücken erzeugten schwebende Leiterbahnen im DRC."""
    return


def connect_orphan_gnd_pads(board):
    """GND-Pads, die Freerouting oft offen lässt, an die B.Cu-Fläche anbinden."""
    for ref, pad in (("U2", 7), ("U4", 8), ("U10", 2), ("D11", 2)):
        connect_gnd_pad(board, ref, pad)
    link_pads(board, "D11", 2, "R41", 2, 0.35)


def drc_report(pcb_path: str) -> dict:
    out = tempfile.mktemp(suffix=".json")
    subprocess.run(kicad_env.kicad_cli_argv("pcb", "drc", "--format", "json", "-o", out, pcb_path), check=True)
    data = json.load(open(out, encoding="utf-8"))
    os.remove(out)
    return data


def dist_point_seg(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    l2 = dx * dx + dy * dy
    if l2 == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / l2))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def to_board(vec):
    return pcbnew.ToMM(vec.x) - ORIGIN[0], pcbnew.ToMM(vec.y) - ORIGIN[1]


def on_same_net_pad(board, x, y, net):
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetname() != net:
                continue
            bb = pad.GetBoundingBox()
            l, t = to_board(pcbnew.VECTOR2I(bb.GetLeft(), bb.GetTop()))
            r, b = to_board(pcbnew.VECTOR2I(bb.GetRight(), bb.GetBottom()))
            if l - 0.05 <= x <= r + 0.05 and t - 0.05 <= y <= b + 0.05:
                return True
    return False


def foreign_clear(board, x, y, net, gap, layer=None):
    """Punkt in Platinen-mm liegt `gap` neben fremdem Kupfer. `layer` blendet Bahnen der anderen Lage aus; Vias zählen immer."""
    if on_same_net_pad(board, x, y, net):
        return True
    if x < 0.4 or y < 0.4 or x > W - 0.4 or y > H - 0.4:
        return False
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetname() == net:
                continue
            bb = pad.GetBoundingBox()
            l, t = to_board(pcbnew.VECTOR2I(bb.GetLeft(), bb.GetTop()))
            r, b = to_board(pcbnew.VECTOR2I(bb.GetRight(), bb.GetBottom()))
            cx, cy = min(max(x, l), r), min(max(y, t), b)
            if math.hypot(x - cx, y - cy) < gap:
                return False
    for tr in board.GetTracks():
        if tr.GetNetname() == net:
            continue
        if tr.GetClass() == "PCB_VIA":
            vx, vy = to_board(tr.GetPosition())
            rad = pcbnew.ToMM(tr.GetWidth(pcbnew.F_Cu)) / 2
            if math.hypot(x - vx, y - vy) < rad + gap:
                return False
        elif layer is not None and tr.GetLayer() != layer:
            continue
        elif tr.GetLayer() in (pcbnew.F_Cu, pcbnew.B_Cu):
            x1, y1 = to_board(tr.GetStart())
            x2, y2 = to_board(tr.GetEnd())
            if dist_point_seg(x, y, x1, y1, x2, y2) < pcbnew.ToMM(tr.GetWidth()) / 2 + gap:
                return False
    p = pt(x, y)
    for z in board.Zones():
        if z.GetLayer() != pcbnew.F_Cu or z.GetNetname() == net:
            continue
        if z.GetFilledPolysList(pcbnew.F_Cu).Contains(p):
            return False
    return True


def segment_clear(board, x1, y1, x2, y2, net, gap, layer=None):
    length = math.hypot(x2 - x1, y2 - y1)
    steps = max(1, int(length / 0.2))
    for i in range(steps + 1):
        t = i / steps
        if not foreign_clear(board, x1 + (x2 - x1) * t, y1 + (y2 - y1) * t, net, gap, layer):
            return False
    return True


def add_track(board, x1, y1, x2, y2, net, layer, width):
    if math.hypot(x2 - x1, y2 - y1) < 0.05:
        return
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(pt(x1, y1))
    t.SetEnd(pt(x2, y2))
    t.SetWidth(mm(width))
    t.SetLayer(layer)
    t.SetNet(board.FindNet(net))
    board.Add(t)


def add_via(board, x, y, net, diameter=0.6, drill=0.3):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(pt(x, y))
    v.SetWidth(mm(diameter))
    v.SetDrill(mm(drill))
    v.SetNet(board.FindNet(net))
    board.Add(v)


def gnd_main_chain(board):
    z = next((z for z in board.Zones() if z.GetNetname() == "GND" and z.GetLayer() == pcbnew.B_Cu), None)
    if z is None:
        return None
    poly = z.GetFilledPolysList(pcbnew.B_Cu)
    if poly.OutlineCount() == 0:
        return None
    idx = max(range(poly.OutlineCount()), key=lambda i: abs(poly.Outline(i).Area()))
    return poly.Outline(idx)


def tie_gnd(board, x, y):
    """Hängt einen GND-Punkt per kurzer Bahn und Via an die untere GND-Fläche."""
    chain = gnd_main_chain(board)
    if chain is None:
        return False

    def site(vx, vy):
        if not (1.0 < vx < W - 1.0 and 1.0 < vy < H - 1.0):
            return False
        if not foreign_clear(board, vx, vy, "GND", 0.55):
            return False
        return _in_outline(chain, vx, vy, 0.45)

    for radius in [i * 0.45 for i in range(0, 18)]:
        steps = 1 if radius == 0 else max(8, int(radius * 8))
        for k in range(steps):
            a = 2 * math.pi * k / steps
            vx, vy = x + radius * math.cos(a), y + radius * math.sin(a)
            if not site(vx, vy):
                continue
            if radius > 0.2 and not segment_clear(board, x, y, vx, vy, "GND", 0.35, pcbnew.F_Cu):
                continue
            if radius > 0.2:
                add_track(board, x, y, vx, vy, "GND", pcbnew.F_Cu, 0.35)
            add_via(board, vx, vy, "GND")
            return True
    return False


def route_points(board, x1, y1, x2, y2, net, width=0.3):
    """Orthogonaler Weg auf F.Cu, der fremdes Kupfer um 0,2 mm meidet."""
    step = 0.4
    gap = width / 2 + 0.22
    nx, ny = int(W / step) + 1, int(H / step) + 1
    blocked = bytearray(nx * ny)

    def mark(x, y, rad):
        r = int(rad / step) + 1
        cx, cy = int(round(x / step)), int(round(y / step))
        rr = rad * rad
        for ix in range(cx - r, cx + r + 1):
            for iy in range(cy - r, cy + r + 1):
                if 0 <= ix < nx and 0 <= iy < ny and (ix * step - x) ** 2 + (iy * step - y) ** 2 <= rr:
                    blocked[iy * nx + ix] = 1

    for ix in range(nx):
        for iy in (0, 1, ny - 2, ny - 1):
            if 0 <= iy < ny:
                blocked[iy * nx + ix] = 1
    for iy in range(ny):
        blocked[iy * nx] = blocked[iy * nx + nx - 1] = 1
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetname() == net:
                continue
            bb = pad.GetBoundingBox()
            l, t = to_board(pcbnew.VECTOR2I(bb.GetLeft(), bb.GetTop()))
            r, b = to_board(pcbnew.VECTOR2I(bb.GetRight(), bb.GetBottom()))
            rad = gap
            for x in (l, r):
                y = t
                while y <= b:
                    mark(x, y, rad)
                    y += step
            x = l
            while x <= r:
                mark(x, t, rad)
                mark(x, b, rad)
                x += step
            # Fläche des Pads selbst
            x = l
            while x <= r:
                y = t
                while y <= b:
                    mark(x, y, gap)
                    y += step
                x += step
    for tr in board.GetTracks():
        if tr.GetNetname() == net:
            continue
        if tr.GetClass() == "PCB_VIA":
            mark(*to_board(tr.GetPosition()), pcbnew.ToMM(tr.GetWidth(pcbnew.F_Cu)) / 2 + gap)
        elif tr.GetLayer() == pcbnew.F_Cu:
            x1t, y1t = to_board(tr.GetStart())
            x2t, y2t = to_board(tr.GetEnd())
            rad = pcbnew.ToMM(tr.GetWidth()) / 2 + gap
            n = max(1, int(math.hypot(x2t - x1t, y2t - y1t) / 0.25))
            for i in range(n + 1):
                u = i / n
                mark(x1t + (x2t - x1t) * u, y1t + (y2t - y1t) * u, rad)
    for z in board.Zones():
        if z.GetLayer() != pcbnew.F_Cu or z.GetNetname() == net:
            continue
        poly = z.GetFilledPolysList(pcbnew.F_Cu)
        for ix in range(nx):
            for iy in range(ny):
                if poly.Contains(pt(ix * step, iy * step)):
                    blocked[iy * nx + ix] = 1

    def cell(x, y):
        return int(round(x / step)), int(round(y / step))

    def nearest(x, y):
        sx, sy = cell(x, y)
        for rad in range(0, 12):
            for ix in range(sx - rad, sx + rad + 1):
                for iy in range(sy - rad, sy + rad + 1):
                    if 0 <= ix < nx and 0 <= iy < ny and not blocked[iy * nx + ix]:
                        if rad == 0 or max(abs(ix - sx), abs(iy - sy)) == rad:
                            return ix, iy
        return None

    start, goal = nearest(x1, y1), nearest(x2, y2)
    if not start or not goal:
        return False
    if start == goal:
        if segment_clear(board, x1, y1, x2, y2, net, gap, pcbnew.F_Cu):
            add_track(board, x1, y1, x2, y2, net, pcbnew.F_Cu, width)
            return True
        return False
    heap = [(0, start)]
    came = {start: None}
    cost = {start: 0}
    while heap:
        _, cur = heapq.heappop(heap)
        if cur == goal:
            break
        cx, cy = cur
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nxt = (cx + dx, cy + dy)
            if not (0 <= nxt[0] < nx and 0 <= nxt[1] < ny) or blocked[nxt[1] * nx + nxt[0]]:
                continue
            nc = cost[cur] + 1
            if nc < cost.get(nxt, 1e9):
                cost[nxt] = nc
                came[nxt] = cur
                heapq.heappush(heap, (nc + abs(nxt[0] - goal[0]) + abs(nxt[1] - goal[1]), nxt))
    if goal not in came:
        return False
    pts = []
    cur = goal
    while cur is not None:
        pts.append((cur[0] * step, cur[1] * step))
        cur = came[cur]
    pts.reverse()
    pts[0] = (x1, y1)
    pts[-1] = (x2, y2)
    # lange freie Stücke statt Treppen; sonst die freien Rasterschritte
    pulled = [pts[0]]
    i = 0
    ok = True
    while i < len(pts) - 1:
        j = len(pts) - 1
        while j > i + 1 and not segment_clear(board, pts[i][0], pts[i][1], pts[j][0], pts[j][1], net, gap, pcbnew.F_Cu):
            j -= 1
        if not segment_clear(board, pts[i][0], pts[i][1], pts[j][0], pts[j][1], net, gap, pcbnew.F_Cu):
            ok = False
            break
        pulled.append(pts[j])
        i = j
    if not ok:
        pulled = pts
    for (ax, ay), (bx, by) in zip(pulled, pulled[1:]):
        add_track(board, ax, ay, bx, by, net, pcbnew.F_Cu, width)
    return True


def parse_item(board, item):
    desc = item.get("description", "")
    pos = item.get("pos") or {}
    x = float(pos.get("x", 0)) - ORIGIN[0]
    y = float(pos.get("y", 0)) - ORIGIN[1]
    m = re.match(r"Pad (\S+) \[([^\]]+)\] of (\S+)", desc)
    if m:
        fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
        pad = fps[m.group(3)].FindPadByNumber(m.group(1))
        x, y = to_board(pad.GetPosition())
        return x, y, m.group(2), "pad"
    kind = "via" if desc.startswith("Via") else "zone" if desc.startswith("Zone") else "track"
    net = re.search(r"\[([^\]]+)\]", desc)
    return x, y, net.group(1) if net else "", kind


def _in_outline(chain, x, y, margin=0.0):
    if margin <= 0:
        return chain.PointInside(pt(x, y))
    if not chain.PointInside(pt(x, y)):
        return False
    for k in range(8):
        a = k * math.pi / 4
        if not chain.PointInside(pt(x + margin * math.cos(a), y + margin * math.sin(a))):
            return False
    return True


def via_near(board, x, y, net, tol=0.5):
    for tr in board.GetTracks():
        if tr.GetClass() == "PCB_VIA" and tr.GetNetname() == net:
            vx, vy = to_board(tr.GetPosition())
            if math.hypot(vx - x, vy - y) < tol:
                return True
    return False


def bridge_gnd_islands(board, depth=0):
    """Verbindet abgetrennte GND-Flächen auf B.Cu per Via und kurzer F.Cu-Bahn mit der größten Fläche."""
    if depth > 6:
        return 0
    z = next((z for z in board.Zones() if z.GetNetname() == "GND" and z.GetLayer() == pcbnew.B_Cu), None)
    if z is None:
        return 0
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    poly = z.GetFilledPolysList(pcbnew.B_Cu)
    before = poly.OutlineCount()
    if before < 2:
        return 0
    main = max(range(before), key=lambda i: abs(poly.Outline(i).Area()))
    for idx in range(before):
        if idx == main:
            continue
        chain = poly.Outline(idx)
        step = max(1, chain.PointCount() // 40)
        for pi in range(0, chain.PointCount(), step):
            vx, vy = to_board(chain.CPoint(pi))
            for k in range(16):
                a = k * math.pi / 8
                dx, dy = math.cos(a), math.sin(a)
                ix, iy = vx + 0.9 * dx, vy + 0.9 * dy
                if via_near(board, ix, iy, "GND") or not _in_outline(chain, ix, iy, 0.35):
                    continue
                for dist in (1.4, 2.2, 3.2, 4.5):
                    mx, my = vx - dist * dx, vy - dist * dy
                    if not _in_outline(poly.Outline(main), mx, my, 0.45):
                        continue
                    if not (foreign_clear(board, ix, iy, "GND", 0.55) and foreign_clear(board, mx, my, "GND", 0.55)):
                        continue
                    if not segment_clear(board, ix, iy, mx, my, "GND", 0.35, pcbnew.F_Cu):
                        continue
                    add_via(board, ix, iy, "GND")
                    add_via(board, mx, my, "GND")
                    add_track(board, ix, iy, mx, my, "GND", pcbnew.F_Cu, 0.4)
                    print(f"bridge GND island {ix:.1f},{iy:.1f} -> {mx:.1f},{my:.1f}")
                    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
                    after = z.GetFilledPolysList(pcbnew.B_Cu).OutlineCount()
                    extra = bridge_gnd_islands(board, depth + 1) if after < before else 0
                    return 1 + extra
    return 0


def repair_opens(board, unconn):
    """Schließt offene Paare. GND-Inseln an die große Fläche, sonst eine freie Bahn. Keine Gerade quer über fremde Netze."""
    fixed = bridge_gnd_islands(board)
    for item in unconn:
        ends = [parse_item(board, i) for i in item.get("items", [])]
        if len(ends) < 2 or not ends[0][2] or ends[0][2] != ends[1][2]:
            continue
        net = ends[0][2]
        if any(e[3] == "zone" for e in ends):
            continue
        x1, y1, _, _ = ends[0]
        x2, y2, _, _ = ends[1]
        if route_points(board, x1, y1, x2, y2, net):
            fixed += 1
            print(f"repair {net} {x1:.1f},{y1:.1f} -> {x2:.1f},{y2:.1f}")
        elif net == "GND" and all(tie_gnd(board, x, y) for x, y, _net, kind in ends if kind != "zone"):
            fixed += 1
            print(f"repair GND via {x1:.1f},{y1:.1f}")
        else:
            print(f"repair {net} FAILED {x1:.1f},{y1:.1f} -> {x2:.1f},{y2:.1f}")
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    return fixed


def _track_angle(x1, y1, x2, y2):
    return abs(math.degrees(math.atan2(y2 - y1, x2 - x1))) % 180


def _is_diagonal(x1, y1, x2, y2, length_min=3.0):
    length = math.hypot(x2 - x1, y2 - y1)
    if length < length_min:
        return False
    ang = _track_angle(x1, y1, x2, y2)
    return min(abs(ang - 45), abs(ang - 135)) < 10


def _crosses_foreign_power(x1, y1, x2, y2, net):
    steps = max(2, int(math.hypot(x2 - x1, y2 - y1) / 0.25))
    for name, rect, _prio in POWER_ZONES:
        if name == net:
            continue
        l, t, r, b = rect
        for i in range(steps + 1):
            u = i / steps
            x, y = x1 + (x2 - x1) * u, y1 + (y2 - y1) * u
            if l <= x <= r and t <= y <= b:
                return True
    return False


def _in_bcu_gnd_fill(board, x, y):
    p = pt(x, y)
    for z in board.Zones():
        if z.GetLayer() == pcbnew.B_Cu and z.GetNetname() == "GND":
            if z.GetFilledPolysList(pcbnew.B_Cu).Contains(p):
                return True
    return False


class _UnionFind:
    def __init__(self):
        self.parent = {}

    def add(self, key):
        self.parent.setdefault(key, key)

    def find(self, key):
        self.add(key)
        while self.parent[key] != key:
            self.parent[key] = self.parent[self.parent[key]]
            key = self.parent[key]
        return key

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def _gnd_track_redundant(board, skip):
    """True, wenn beide Enden der GND-Bahn ohne sie an derselben Masse hängen (Fläche oder andere Bahn)."""
    uf = _UnionFind()
    plane = ("plane",)

    def endpoint_key(x, y):
        return ("pt", round(x, 2), round(y, 2))

    points = []
    for tr in board.GetTracks():
        tr.thisown = 0
        if tr is skip or tr.GetNetname() != "GND":
            continue
        if tr.GetClass() == "PCB_VIA":
            x, y = to_board(tr.GetPosition())
            key = ("via", round(x, 2), round(y, 2))
            uf.add(key)
            points.append((key, x, y))
            if _in_bcu_gnd_fill(board, x, y):
                uf.union(key, plane)
        elif tr.GetClass() == "PCB_TRACK":
            x1, y1 = to_board(tr.GetStart())
            x2, y2 = to_board(tr.GetEnd())
            uf.union(endpoint_key(x1, y1), endpoint_key(x2, y2))
            points.append((endpoint_key(x1, y1), x1, y1))
            points.append((endpoint_key(x2, y2), x2, y2))
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetname() != "GND" or not pad.IsOnLayer(pcbnew.B_Cu):
                continue
            px, py = to_board(pad.GetPosition())
            pad_key = ("pad", fp.GetReference(), pad.GetNumber())
            uf.add(pad_key)
            if _in_bcu_gnd_fill(board, px, py):
                uf.union(pad_key, plane)
            rad = min(pcbnew.ToMM(pad.GetSize().x), pcbnew.ToMM(pad.GetSize().y)) / 2 + 0.02
            for key, x, y in points:
                if math.hypot(x - px, y - py) <= rad:
                    uf.union(pad_key, key)
    vias = [item for item in points if item[0][0] == "via"]
    ends = [item for item in points if item[0][0] == "pt"]
    for vkey, vx, vy in vias:
        for ekey, ex, ey in ends:
            if math.hypot(ex - vx, ey - vy) <= 0.32:
                uf.union(vkey, ekey)
    x1, y1 = to_board(skip.GetStart())
    x2, y2 = to_board(skip.GetEnd())
    a, b = endpoint_key(x1, y1), endpoint_key(x2, y2)
    return a != b and uf.find(a) == uf.find(b)


def _has_mid_junction(board, track):
    """Andere Bahn oder Via desselben Netzes trifft die Strecke, nicht nur die Endpunkte."""
    x1, y1 = to_board(track.GetStart())
    x2, y2 = to_board(track.GetEnd())
    reach = pcbnew.ToMM(track.GetWidth()) / 2 + 0.05
    net = track.GetNetname()
    for other in board.GetTracks():
        other.thisown = 0
        if other is track or other.GetNetname() != net:
            continue
        if other.GetClass() == "PCB_VIA":
            pts = [(other.GetPosition(), reach + pcbnew.ToMM(other.GetWidth(pcbnew.F_Cu)) / 2)]
        else:
            extra = pcbnew.ToMM(other.GetWidth()) / 2
            pts = [(other.GetStart(), reach + extra), (other.GetEnd(), reach + extra)]
        for vec, limit in pts:
            x, y = to_board(vec)
            if dist_point_seg(x, y, x1, y1, x2, y2) > limit:
                continue
            if min(math.hypot(x - x1, y - y1), math.hypot(x - x2, y - y2)) > reach + 0.15:
                return True
    return False


def drop_redundant_gnd(board):
    """Nicht aus dem Ablauf aufrufen: löscht nötige GND-Bahnen und öffnet Netze."""
    removed = 0
    while True:
        victim = None
        # list() vor dem Löschen: Remove macht den laufenden GetTracks()-Iterator ungültig.
        tracks = []
        for tr in list(board.GetTracks()):
            tr.thisown = 0
            if tr.GetClass() == "PCB_TRACK" and tr.GetLayer() == pcbnew.F_Cu and tr.GetNetname() == "GND":
                tracks.append(tr)
        for tr in tracks:
            x1, y1 = to_board(tr.GetStart())
            x2, y2 = to_board(tr.GetEnd())
            if not (_is_diagonal(x1, y1, x2, y2, 2.5) or _crosses_foreign_power(x1, y1, x2, y2, "GND")):
                continue
            if _has_mid_junction(board, tr):
                continue
            if _gnd_track_redundant(board, tr):
                victim = tr
                break
        if victim is None:
            break
        x1, y1 = to_board(victim.GetStart())
        x2, y2 = to_board(victim.GetEnd())
        print(f"drop redundant GND ({x1:.1f},{y1:.1f})->({x2:.1f},{y2:.1f})")
        board.Delete(victim)
        removed += 1
    return removed


def _leg_clear(board, x1, y1, x2, y2, net, layer, width):
    gap = width / 2 + 0.2
    if not segment_clear(board, x1, y1, x2, y2, net, gap, layer):
        return False
    if layer != pcbnew.B_Cu or net == "GND":
        return True
    steps = max(1, int(math.hypot(x2 - x1, y2 - y1) / 0.2))
    for i in range(steps + 1):
        u = i / steps
        if _in_bcu_gnd_fill(board, x1 + (x2 - x1) * u, y1 + (y2 - y1) * u):
            return False
    return True


def orthogonalize_diagonals(board):
    """Ersetzt eine schräge Bahn durch einen rechten Winkel, wenn beide Schenkel frei bleiben."""
    changed = 0
    pending = list(board.GetTracks())
    for tr in pending:
        tr.thisown = 0
    for tr in pending:
        if tr.GetClass() != "PCB_TRACK":
            continue
        x1, y1 = to_board(tr.GetStart())
        x2, y2 = to_board(tr.GetEnd())
        if not _is_diagonal(x1, y1, x2, y2, 2.0):
            continue
        if _has_mid_junction(board, tr):
            continue
        net = tr.GetNetname()
        layer = tr.GetLayer()
        width = pcbnew.ToMM(tr.GetWidth())
        elbows = (
            (x2, y1),
            (x1, y2),
        )
        placed = False
        for mx, my in elbows:
            if math.hypot(mx - x1, my - y1) < 0.2 or math.hypot(x2 - mx, y2 - my) < 0.2:
                continue
            if _leg_clear(board, x1, y1, mx, my, net, layer, width) and _leg_clear(board, mx, my, x2, y2, net, layer, width):
                board.Delete(tr)
                add_track(board, x1, y1, mx, my, net, layer, width)
                add_track(board, mx, my, x2, y2, net, layer, width)
                changed += 1
                placed = True
                break
        if not placed:
            continue
    return changed


def reroute_remaining_diagonals(board):
    """Schräge Bahn ohne Abzweig, die kein rechter Winkel freilässt, orthogonal neu legen."""
    moved = 0
    for tr in list(board.GetTracks()):
        tr.thisown = 0
        if tr.GetClass() != "PCB_TRACK" or tr.GetLayer() != pcbnew.F_Cu:
            continue
        x1, y1 = to_board(tr.GetStart())
        x2, y2 = to_board(tr.GetEnd())
        if not _is_diagonal(x1, y1, x2, y2, 3.0) or _has_mid_junction(board, tr):
            continue
        net = tr.GetNetname()
        if route_points(board, x1, y1, x2, y2, net, pcbnew.ToMM(tr.GetWidth())):
            board.Delete(tr)
            moved += 1
            print(f"reroute {net} ({x1:.1f},{y1:.1f})->({x2:.1f},{y2:.1f})")
    return moved


def cleanup_copper(board):
    """Schräge Bahnen ohne Abzweig in einen rechten Winkel legen. GND-Bahnen nicht löschen: das öffnet Netze."""
    squared = orthogonalize_diagonals(board)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    print(f"copper cleanup: squared {squared}")
    return squared


def electrical_errors(report: dict) -> list[str]:
    bad = []
    for item in report.get("unconnected_items") or []:
        parts = [i.get("description", "") for i in item.get("items", [])]
        bad.append("open: " + " <-> ".join(parts))
    for v in report.get("violations") or []:
        desc = v.get("description", "")
        if desc.startswith("Items shorting") or desc.startswith("Tracks crossing"):
            parts = [i.get("description", "") for i in v.get("items", [])]
            bad.append(desc + " | " + " <-> ".join(parts))
    return bad


def silk_errors(report: dict) -> list[str]:
    bad = []
    for v in report.get("violations") or []:
        desc = v.get("description", "")
        if "Silkscreen" in desc:
            parts = [i.get("description", "") for i in v.get("items", [])]
            bad.append(desc.split(";")[0] + " | " + " <-> ".join(parts[:2]))
    return bad


def route_board(board, jar, java):
    for t in list(board.GetTracks()):
        board.Remove(t)
    for z in list(board.Zones()):
        board.Remove(z)
    # GND nicht vorher als Fläche: sonst lässt Freerouting die Masse-Pins offen, sobald die Fläche zerrissen ist.
    if not pcbnew.ExportSpecctraDSN(board, DSN):
        raise SystemExit("DSN export failed")
    subprocess.run([java, "-jar", jar, "-de", DSN, "-do", SES, "-mp", "500", "--gui.enabled=false"], check=True)
    if not pcbnew.ImportSpecctraSES(board, SES):
        raise SystemExit("SES import failed")
    zone(board, "GND", pcbnew.B_Cu, (0.5, 0.5, W - 0.5, H - 0.5), 0)
    for net, rect, prio in POWER_ZONES:
        zone(board, net, pcbnew.F_Cu, rect, prio)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    # SES-Import setzt die Designregeln zurück. 0,6 mm ist die kleinste verwendete Siebdruckhöhe.
    ds = board.GetDesignSettings()
    ds.m_MinSilkTextHeight = mm(0.6)
    ds.m_MinSilkTextThickness = mm(0.08)
    ds.m_SilkClearance = mm(0.1)


def signal_opens(unconn) -> int:
    n = 0
    for item in unconn:
        desc = " ".join(i.get("description", "") for i in item.get("items", []))
        nets = re.findall(r"\[([^\]]+)\]", desc)
        if any(net != "GND" for net in nets):
            n += 1
    return n


def main():
    jar = sys.argv[1]
    java = sys.argv[2] if len(sys.argv) > 2 else "java"
    os.makedirs(os.path.dirname(DSN), exist_ok=True)
    py = kicad_env.pcbnew_python()
    best_file = PCB + ".best"
    best_key = (999, 999)
    for attempt in range(2):
        print(f"route attempt {attempt + 1}/2", flush=True)
        subprocess.run([py, os.path.join(HERE, "gen_pcb.py")], check=True)
        board = pcbnew.LoadBoard(PCB)
        route_board(board, jar, java)
        pcbnew.SaveBoard(PCB, board)
        unconn = drc_report(os.path.abspath(PCB)).get("unconnected_items") or []
        key = (signal_opens(unconn), len(unconn))
        print(f"attempt {attempt + 1}: signal opens {key[0]}, total {key[1]}", flush=True)
        if key < best_key:
            shutil.copy(PCB, best_file)
            best_key = key
        if key[0] == 0:
            break
    shutil.copy(best_file, PCB)
    os.remove(best_file)
    board = pcbnew.LoadBoard(PCB)
    for _ in range(4):
        pcbnew.SaveBoard(PCB, board)
        report = drc_report(os.path.abspath(PCB))
        unconn = report.get("unconnected_items") or []
        if not unconn:
            break
        for item in unconn:
            parts = [i.get("description", "") for i in item.get("items", [])]
            print("DRC unconnected:", " <-> ".join(parts))
        if repair_opens(board, unconn) == 0:
            break
    squared = orthogonalize_diagonals(board)
    moved = reroute_remaining_diagonals(board)
    print(f"squared {squared} diagonals, rerouted {moved}")
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    import gen_pcb
    gen_pcb.layout_silk(board)
    pcbnew.SaveBoard(PCB, board)
    report = drc_report(os.path.abspath(PCB))
    bad = electrical_errors(report)
    if bad:
        for line in bad:
            print(line)
        raise SystemExit(f"DRC: {len(bad)} elektrische Fehler — Platine nicht freigegeben")
    silk = silk_errors(report)
    if silk:
        for line in silk[:12]:
            print(line)
        if len(silk) > 12:
            print(f"... {len(silk) - 12} weitere Silk-Verstöße")
        raise SystemExit(f"DRC: {len(silk)} Siebdruck-Verstöße — Platine nicht freigegeben")
    print("DRC: keine offenen Verbindungen, keine Kurzschlüsse, keine Kreuzungen, kein Siebdruck-Fehler")
    print("routed and saved", PCB)


if __name__ == "__main__":
    main()
