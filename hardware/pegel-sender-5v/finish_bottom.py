"""Offene Netze der bestehenden Platine auf B.Cu schließen. Footprints bleiben.

J3 Pad 4: GND → V12_PROBE. Signale per Via auf die Unterseite, GND per Via in die Fläche.
"""

import json
import math
import os
import subprocess
import tempfile

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(HERE, "pegel-sender-5v.kicad_pcb")

import route  # noqa: E402


def drc(board_path):
    out = tempfile.mktemp(suffix=".json")
    subprocess.run(
        __import__("kicad_env").kicad_cli_argv("pcb", "drc", "--format", "json", "-o", out, board_path),
        check=True,
    )
    data = json.load(open(out, encoding="utf-8"))
    os.remove(out)
    return data


def pad_on_layer(pad, layer):
    if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
        return False
    if pad.HasHole():
        return True
    return pad.GetLayerSet().Contains(layer)


def blocks(board, x, y, net, layer):
    if x < 0.6 or y < 0.6 or x > route.W - 0.6 or y > route.H - 0.6:
        return True
    if route.on_same_net_pad(board, x, y, net):
        return False
    gap = 0.25
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetname() == net or not pad_on_layer(pad, layer):
                continue
            bb = pad.GetBoundingBox()
            l, t = route.to_board(pcbnew.VECTOR2I(bb.GetLeft(), bb.GetTop()))
            r, b = route.to_board(pcbnew.VECTOR2I(bb.GetRight(), bb.GetBottom()))
            cx, cy = min(max(x, l), r), min(max(y, t), b)
            if math.hypot(x - cx, y - cy) < gap:
                return True
    for tr in board.GetTracks():
        if tr.GetNetname() == net:
            continue
        if tr.GetClass() == "PCB_VIA":
            vx, vy = route.to_board(tr.GetPosition())
            if math.hypot(x - vx, y - vy) < pcbnew.ToMM(tr.GetWidth(pcbnew.F_Cu)) / 2 + gap:
                return True
        elif tr.GetLayer() == layer:
            x1, y1 = route.to_board(tr.GetStart())
            x2, y2 = route.to_board(tr.GetEnd())
            if route.dist_point_seg(x, y, x1, y1, x2, y2) < pcbnew.ToMM(tr.GetWidth()) / 2 + gap:
                return True
    return False


def route_bottom(board, x1, y1, x2, y2, net, width=0.3):
    """A* auf B.Cu, Abstand inkl. Bahnbreite, dann lange freie Stücke statt Treppen."""
    step = 0.5
    keep = width / 2 + 0.3
    nx, ny = int(route.W / step) + 1, int(route.H / step) + 1
    blocked = bytearray(nx * ny)

    def mark_disk(x, y, rad):
        r = int(rad / step) + 1
        cx, cy = int(round(x / step)), int(round(y / step))
        for ix in range(cx - r, cx + r + 1):
            for iy in range(cy - r, cy + r + 1):
                if 0 <= ix < nx and 0 <= iy < ny and (ix * step - x) ** 2 + (iy * step - y) ** 2 <= rad * rad:
                    blocked[iy * nx + ix] = 1

    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetname() == net or not pad_on_layer(pad, pcbnew.B_Cu):
                continue
            bb = pad.GetBoundingBox()
            l, t = route.to_board(pcbnew.VECTOR2I(bb.GetLeft(), bb.GetTop()))
            r, b = route.to_board(pcbnew.VECTOR2I(bb.GetRight(), bb.GetBottom()))
            mark_disk((l + r) / 2, (t + b) / 2, max(r - l, b - t) / 2 + keep)
    for tr in board.GetTracks():
        if tr.GetNetname() == net:
            continue
        if tr.GetClass() == "PCB_VIA":
            vx, vy = route.to_board(tr.GetPosition())
            mark_disk(vx, vy, pcbnew.ToMM(tr.GetWidth(pcbnew.F_Cu)) / 2 + keep)
        elif tr.GetLayer() == pcbnew.B_Cu:
            x1t, y1t = route.to_board(tr.GetStart())
            x2t, y2t = route.to_board(tr.GetEnd())
            n = max(1, int(math.hypot(x2t - x1t, y2t - y1t) / 0.4))
            rad = pcbnew.ToMM(tr.GetWidth()) / 2 + keep
            for i in range(n + 1):
                u = i / n
                mark_disk(x1t + (x2t - x1t) * u, y1t + (y2t - y1t) * u, rad)
    for ix in range(nx):
        blocked[ix] = blocked[(ny - 1) * nx + ix] = 1
    for iy in range(ny):
        blocked[iy * nx] = blocked[iy * nx + nx - 1] = 1

    def nearest(x, y):
        sx, sy = int(round(x / step)), int(round(y / step))
        for rad in range(0, 10):
            for ix in range(sx - rad, sx + rad + 1):
                for iy in range(sy - rad, sy + rad + 1):
                    if 0 <= ix < nx and 0 <= iy < ny and not blocked[iy * nx + ix]:
                        if rad == 0 or max(abs(ix - sx), abs(iy - sy)) == rad:
                            return ix, iy
        return None

    start, goal = nearest(x1, y1), nearest(x2, y2)
    if not start or not goal:
        return False
    import heapq
    heap = [(0, start)]
    came = {start: None}
    cost = {start: 0}
    found = False
    while heap:
        _, cur = heapq.heappop(heap)
        if cur == goal:
            found = True
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
    if not found:
        return False
    pts = []
    cur = goal
    while cur is not None:
        pts.append((cur[0] * step, cur[1] * step))
        cur = came[cur]
    pts.reverse()
    pts[0] = (x1, y1)
    pts[-1] = (x2, y2)
    simplified = [pts[0]]
    for i in range(1, len(pts) - 1):
        ax, ay = simplified[-1]
        bx, by = pts[i]
        cx, cy = pts[i + 1]
        if (bx - ax) * (cy - by) != (by - ay) * (cx - bx):
            simplified.append(pts[i])
    simplified.append(pts[-1])
    for (ax, ay), (bx, by) in zip(simplified, simplified[1:]):
        route.add_track(board, ax, ay, bx, by, net, pcbnew.B_Cu, width)
    return True


def strip_bottom(board):
    """Unterseiten-Bahnen und Vias aus dem vorigen Durchgang entfernen (oben bleibt)."""
    for tr in list(board.GetTracks()):
        if tr.GetClass() == "PCB_VIA" or tr.GetLayer() == pcbnew.B_Cu:
            tr.thisown = 0
            board.Remove(tr)


def drop_via(board, x, y, net):
    for rad in (0.0, 0.7, 1.1, 1.6, 2.2):
        steps = 1 if rad == 0 else 10
        for k in range(steps):
            a = 2 * math.pi * k / steps
            vx, vy = x + rad * math.cos(a), y + rad * math.sin(a)
            if blocks(board, vx, vy, net, pcbnew.B_Cu) or blocks(board, vx, vy, net, pcbnew.F_Cu):
                continue
            if rad > 0.2 and not route.segment_clear(board, x, y, vx, vy, net, 0.3, pcbnew.F_Cu):
                continue
            if rad > 0.2:
                route.add_track(board, x, y, vx, vy, net, pcbnew.F_Cu, 0.3)
            route.add_via(board, vx, vy, net)
            return vx, vy
    return None


def item_point(board, item):
    desc = item.get("description", "")
    pos = item.get("pos") or {}
    x = float(pos.get("x", 0)) - route.ORIGIN[0]
    y = float(pos.get("y", 0)) - route.ORIGIN[1]
    if desc.startswith("PTH pad") or desc.startswith("Pad "):
        import re
        m = re.match(r"(?:PTH pad|Pad) (\S+) \[", desc)
        ref = desc.split(" of ")[-1].split(" ")[0]
        fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
        if m and ref in fps:
            pad = fps[ref].FindPadByNumber(m.group(1))
            if pad:
                return route.to_board(pad.GetPosition()) + (pad.HasHole(),)
    return x, y, False


def fix_j3(board):
    fp = board.FindFootprintByReference("J3")
    pad = fp.FindPadByNumber("4")
    net = board.FindNet("V12_PROBE")
    px, py = route.to_board(pad.GetPosition())
    # GND-Stummel, die nur an diesem Pad lagen, entfernen
    for tr in list(board.GetTracks()):
        if tr.GetClass() != "PCB_TRACK" or tr.GetNetname() != "GND":
            continue
        x1, y1 = route.to_board(tr.GetStart())
        x2, y2 = route.to_board(tr.GetEnd())
        if min(math.hypot(x1 - px, y1 - py), math.hypot(x2 - px, y2 - py)) < 0.9:
            tr.thisown = 0
            board.Remove(tr)
    pad.SetNet(net)
    fp.SetValue("SONDE")


def main():
    board = pcbnew.LoadBoard(PCB)
    fix_j3(board)
    pcbnew.SaveBoard(PCB, board)

    report = drc(PCB)
    opens = report.get("unconnected_items") or []
    print(f"open before: {len(opens)}")
    done = 0
    for item in opens:
        ends = item.get("items") or []
        if len(ends) < 2:
            continue
        net = None
        import re
        m = re.search(r"\[([^\]]+)\]", ends[0].get("description", ""))
        if m:
            net = m.group(1)
        if not net or board.FindNet(net) is None:
            continue
        x1, y1, hole1 = item_point(board, ends[0])
        x2, y2, hole2 = item_point(board, ends[1])
        print(f"link {net}", flush=True)
        if net == "GND":
            for x, y in ((x1, y1), (x2, y2)):
                drop_via(board, x, y, "GND")
            done += 1
            continue
        b1 = (x1, y1) if hole1 else drop_via(board, x1, y1, net)
        b2 = (x2, y2) if hole2 else drop_via(board, x2, y2, net)
        if not b1 or not b2:
            print(f"via fail {net}")
            continue
        width = 0.45 if net in {"V5", "VBAT", "V12_PROBE", "V12_RAW", "VIN_RAW"} else 0.3
        if route_bottom(board, b1[0], b1[1], b2[0], b2[1], net, width):
            print(f"bottom {net} {b1[0]:.1f},{b1[1]:.1f} -> {b2[0]:.1f},{b2[1]:.1f}")
            done += 1
        else:
            print(f"route fail {net}")
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(PCB, board)
    report = drc(PCB)
    left = report.get("unconnected_items") or []
    print(f"closed {done}, still open {len(left)}")
    for u in left:
        print(" -", " <-> ".join(i.get("description", "") for i in u.get("items", [])))


if __name__ == "__main__":
    main()
