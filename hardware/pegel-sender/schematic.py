"""KiCad-Schaltplan je Funktionsblock aus design.py, als .kicad_sch, SVG und PNG.

Aufruf: python3 schematic.py [block ...]   (schreibt preview/schematic-<block>.png)

- Lage der Bauteile je Blatt aus schematic_layout.py (Signalfluss links → rechts, Versorgung oben,
  Masse unten), wie fixed_positions.py für die Platine.
- Leitungen verlegt ein Router rechtwinklig im 1,27-mm-Raster: kurze Wege, wenig Knicke, nie durch
  Bauteile oder Texte, Kreuzungen nur gerade und teuer.
- Versorgung (+3V3, VSYS, VSOL, XIAO_3V3) und GND als Symbol; Labels nur für Netze, die das Blatt
  verlassen.
- Jedes Blatt wird über die KiCad-Netzliste gegen design.py geprüft.
"""

import heapq
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import design  # noqa: E402
import kicad_env  # noqa: E402
from sch_symbols import lib_field, load_symbol, outward, sexp_from, symbol_pin_of, uid, world  # noqa: E402
from schematic_layout import GROUPS, LAYOUT  # noqa: E402
from svg_png import svg_to_png  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PREVIEW = os.path.join(HERE, "preview")
SCH_DIR = os.path.join(PREVIEW, "schematic")

G = 2.54          # Layout-Einheit in schematic_layout.py
STEP = 1.27       # Routing-Raster
GND = "GND"
SUPPLY = {"+3V3": "power:+3V3", "VSYS": "power:VCC", "VSOL": "power:VCC", "XIAO_3V3": "power:VCC"}
POWER_NETS = set(SUPPLY) | {GND}
CHAR = 1.05
DIRS = {"R": (1, 0), "L": (-1, 0), "U": (0, -1), "D": (0, 1)}


def text_w(text: str) -> float:
    return len(text) * CHAR


def cell(x: float, y: float) -> tuple[int, int]:
    return round(x / STEP), round(y / STEP)


def pos(c) -> tuple[float, float]:
    return c[0] * STEP, c[1] * STEP


def fmt(v: float) -> str:
    return f"{v:.2f}"


def connected_pads(part):
    return {pad: net for pad, net in part.pins.items() if net}


def place_point(x, y, rot, mirror, px, py):
    """Symbolpunkt aufs Blatt; mirror spiegelt nach dem Drehen links/rechts (KiCad: mirror y)."""
    wx, wy = world(x, y, rot, px, py)
    return (2 * x - wx if mirror else wx), wy


def body_box(sym_text: str, name: str, unit: int):
    """Umriss der Grafik (Einheit 0 und diese Einheit), Symbolkoordinaten."""
    xs, ys = [], []
    for u in (0, unit):
        token = f'(symbol "{name}_{u}_'
        idx = 0
        while True:
            i = sym_text.find(token, idx)
            if i < 0:
                break
            block = sexp_from(sym_text, i)
            idx = i + len(block)
            block = re.sub(r"\(pin\s.*?\n\s*\)\s*\)", "", block, flags=re.S)
            for a, b in re.findall(r"\((?:xy|start|end|mid)\s+([-\d.]+)\s+([-\d.]+)\)", block):
                xs.append(float(a))
                ys.append(float(b))
            for a, b, r in re.findall(r"\(center\s+([-\d.]+)\s+([-\d.]+)\)\s*\(radius\s+([-\d.]+)\)", block):
                xs += [float(a) - float(r), float(a) + float(r)]
                ys += [float(b) - float(r), float(b) + float(r)]
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


class Sheet:
    def __init__(self, key, parts, outside, symbols):
        self.key = key
        self.parts = parts
        self.outside = outside
        self.symbols = symbols
        self.items = []          # Symbole, Labels, No-Connects (fertiger Text)
        self.blocked = set()     # Zellen, durch die keine Leitung darf
        self.soft = {}           # Zelle -> Zusatzkosten (Nähe zu Körpern/Texten)
        self.occ = {}            # Zelle -> (Netz, Art): Art "h"/"v" = durchgehend, "n" = Knoten
        self.links = {}          # Netz -> Menge von Kanten (Zelle, Zelle)
        self.pin_cells = {}      # Zelle -> Netz (Pinenden, Symbolanschlüsse, Labelanschlüsse)
        self.pin_dir = {}        # Zelle -> Richtung, aus der eine Leitung an den Pin kommen muss
        self.bounds = []         # alle Rechtecke für die Blattgröße
        self.cross = set()       # Kreuzungen: dort darf kein Netz abzweigen
        self.pwr = 0

    # ---------------------------------------------------------------- Belegung
    def block_box(self, x0, y0, x1, y1, margin=0.4, soft=True):
        x0, x1 = min(x0, x1), max(x0, x1)
        y0, y1 = min(y0, y1), max(y0, y1)
        self.bounds.append((x0, y0, x1, y1))
        c0 = cell(x0 - margin, y0 - margin)
        c1 = cell(x1 + margin, y1 + margin)
        for cx in range(c0[0], c1[0] + 1):
            for cy in range(c0[1], c1[1] + 1):
                self.blocked.add((cx, cy))
        if soft:
            for cx in range(c0[0] - 1, c1[0] + 2):
                for cy in range(c0[1] - 1, c1[1] + 2):
                    self.soft[(cx, cy)] = self.soft.get((cx, cy), 0) + 1.5

    def text(self, x, y, text, just):
        w = text_w(text)
        x0 = x if just == "left" else x - w if just == "right" else x - w / 2
        self.block_box(x0, y - 0.7, x0 + w, y + 0.7, margin=0.2, soft=False)

    # ---------------------------------------------------------------- Bauteile
    def place_part(self, part, unit, spec, x, y, rot, mirror, sym_text, boxed):
        net_of = {symbol_pin_of(part, pad): net for pad, net in connected_pads(part).items()}
        name = part.symbol.split(":")[-1]
        bb = body_box(sym_text, name, unit)
        pins = []
        for num, px, py, pa in spec:
            wx, wy = place_point(x, y, rot, mirror, px, py)
            dx, dy = outward(rot, pa)
            if mirror:
                dx = -dx
            pins.append((num, wx, wy, dx, dy, net_of.get(num)))
        if bb:
            pts = [place_point(x, y, rot, mirror, bx, by) for bx in (bb[0], bb[2]) for by in (bb[1], bb[3])]
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            body = (min(xs), min(ys), max(xs), max(ys))
        else:
            xs, ys = [p[1] for p in pins], [p[2] for p in pins]
            body = (min(xs) + 1, min(ys) + 1, max(xs) - 1, max(ys) - 1)
        self.block_box(*body, margin=0.0)   # Rand nur weich (siehe soft), sonst sperren gestapelte Körper ihre Abgriffe ein
        for num, wx, wy, dx, dy, net in pins:
            # Pinlinie bis zum Körper sperren, Pinende ist Anschluss.
            ix, iy = wx - dx * 2.54, wy - dy * 2.54
            c0, c1 = cell(min(wx, ix), min(wy, iy)), cell(max(wx, ix), max(wy, iy))
            for cx in range(c0[0], c1[0] + 1):
                for cy in range(c0[1], c1[1] + 1):
                    if (cx, cy) != cell(wx, wy):
                        self.blocked.add((cx, cy))
            if not net:
                self.items.append(f'  (no_connect (at {fmt(wx)} {fmt(wy)}) (uuid "{uid()}"))')
        for num, wx, wy, dx, dy, net in pins:
            if net:
                c = cell(wx, wy)
                for k in (1, 2):
                    self.blocked.discard((c[0] + dx * k, c[1] + dy * k))
                # auch seitlich: an gestapelten Zweipolen ist das Pinende sonst von der Grafik umschlossen
                self.blocked.discard((c[0] + dy, c[1] + dx))
                self.blocked.discard((c[0] - dy, c[1] - dx))
        fields = self.place_fields(part, sym_text, boxed, x, y, rot, mirror, body, pins)
        self.items.append(symbol_text(part.symbol, x, y, rot, mirror, part.ref, part.value, unit,
                                      [p[0] for p in spec], fields, bom=True))
        return pins

    def place_fields(self, part, sym_text, boxed, x, y, rot, mirror, body, pins):
        two = len(pins) == 2 and not part.ref.startswith(("J", "U", "Q", "Y"))
        x0, y0, x1, y1 = body
        vertical = two and abs(pins[0][1] - pins[1][1]) < 0.01
        if two and vertical:
            side = LAYOUT[self.key].get("fields_left", set())
            if part.ref in side:
                ref_f = (x0 - 1.0, y - 1.27, "right")
                val_f = (x0 - 1.0, y + 1.27, "right")
            else:
                ref_f = (x1 + 1.0, y - 1.27, "left")
                val_f = (x1 + 1.0, y + 1.27, "left")
        elif two:
            if part.ref in LAYOUT[self.key].get("fields_above", set()):
                ref_f = ((x0 + x1) / 2, y0 - 2.6, "center")
                val_f = ((x0 + x1) / 2, y0 - 1.0, "center")
            else:
                ref_f = ((x0 + x1) / 2, y1 + 1.3, "center")
                val_f = ((x0 + x1) / 2, y1 + 2.9, "center")
        else:
            ref_lib = None if boxed or rot or mirror else lib_field(sym_text, "Reference")
            val_lib = None if boxed or rot or mirror else lib_field(sym_text, "Value")
            up = any(p[4] == -1 for p in pins)
            down = any(p[4] == 1 for p in pins)
            if part.ref in LAYOUT[self.key].get("fields_below", set()):
                ref_f, val_f = (x0, y1 + 1.3, "left"), (x0, y1 + 2.9, "left")
            elif ref_lib and val_lib:
                ref_f = (x + ref_lib[0], y - ref_lib[1], ref_lib[2])
                val_f = (x + val_lib[0], y - val_lib[1], val_lib[2])
            elif down and not up:
                ref_f, val_f = (x0, y0 - 2.6, "left"), (x0, y0 - 1.0, "left")
            elif up and not down:
                ref_f, val_f = (x0, y1 + 1.3, "left"), (x0, y1 + 2.9, "left")
            elif up and down:
                ref_f, val_f = (x1 + 1.0, y0 + 0.6, "left"), (x1 + 1.0, y0 + 2.2, "left")
            else:
                ref_f, val_f = (x0, y0 - 1.0, "left"), (x0, y1 + 1.3, "left")
        for (fx, fy, just), text in ((ref_f, part.ref), (val_f, part.value)):
            self.text(fx, fy, text, just)
        return (ref_f + (False,), val_f + (False,))

    # ---------------------------------------------------------------- Versorgung und Labels
    def power_symbol(self, net, x, y, dx, dy):
        lib = "power:GND" if net == GND else SUPPLY[net]
        rot = ({(0, 1): 0, (1, 0): 90, (0, -1): 180, (-1, 0): 270} if net == GND
               else {(0, -1): 0, (-1, 0): 90, (0, 1): 180, (1, 0): 270})[(dx, dy)]
        reach = 3.3 if net == GND else 3.0
        tx, ty = x + dx * (reach + 1.0), y + dy * (reach + 1.0) + (0.3 * dy if dy else 0)
        just = "left" if dx > 0 else "right" if dx < 0 else "center"
        self.pwr += 1
        self.items.append(symbol_text(lib, x, y, rot, False, f"#PWR{self.pwr:03d}", net, 1, ["1"],
                                      ((x, y, "center", True), (tx, ty, just, False)), bom=False))
        near, far = 0.9, reach
        self.block_box(x + dx * near - (1.4 if dy else 0), y + dy * near - (1.4 if dx else 0),
                       x + dx * far + (1.4 if dy else 0), y + dy * far + (1.4 if dx else 0), margin=0.2)
        self.text(tx, ty, net, just)
        self.add_anchor(cell(x, y), net, (-dx, -dy))

    def add_anchor(self, c, net, wire_dir):
        """Anschlusspunkt; wire_dir: Richtung, in der die Leitung ihn verlässt. Teilen sich mehrere
        Anschlüsse eine Zelle (gestapelte Bauteile), gibt es keine Vorgabe."""
        self.blocked.discard(c)
        if c in self.pin_cells:
            self.pin_dir[c] = None
        else:
            self.pin_cells[c] = net
            self.pin_dir[c] = wire_dir

    def label(self, net, x, y, dx, dy):
        glob = net in self.outside
        ang = {(1, 0): 0, (0, -1): 90, (-1, 0): 180, (0, 1): 270}[(dx, dy)]
        just = "left" if ang in (0, 90) else "right"
        if glob:
            self.items.append(f'  (global_label "{net}" (shape bidirectional) (at {fmt(x)} {fmt(y)} {ang})'
                              f' (effects (font (size 1.27 1.27)) (justify {just})) (uuid "{uid()}"))')
        else:
            self.items.append(f'  (label "{net}" (at {fmt(x)} {fmt(y)} {ang})'
                              f' (effects (font (size 1.27 1.27)) (justify {just} bottom)) (uuid "{uid()}"))')
        length = text_w(net) + (2.6 if glob else 0.5)
        if dx:
            self.block_box(x + dx * 0.6, y - 1.0, x + dx * length, y + 1.0, margin=0.2)
        else:
            self.block_box(x - 1.0, y + dy * 0.6, x + 1.0, y + dy * length, margin=0.2)
        self.add_anchor(cell(x, y), net, (-dx, -dy))

    # ---------------------------------------------------------------- Router
    def free_for(self, net, c, d, prev_d):
        """Darf das Netz die Zelle c in Richtung d betreten? Gibt Zusatzkosten oder None."""
        if c in self.blocked and self.pin_cells.get(c) != net:
            return None
        if c in self.pin_cells:
            # Pinlinien und Symbolkörper sind gesperrt; eine Leitung darf durch das Pinende laufen (Abzweig).
            return 0.0 if self.pin_cells[c] == net else None
        occ = self.occ.get(c)
        if occ:
            other, kind = occ
            if other == net:
                return 0.0
            # Kreuzen nur gerade und senkrecht zur anderen Leitung.
            if kind == "n" or (kind == "h" and d[1] == 0) or (kind == "v" and d[0] == 0):
                return None
            return 6.0
        extra = self.soft.get(c, 0.0)
        for nb in ((c[0] + 1, c[1]), (c[0] - 1, c[1]), (c[0], c[1] + 1), (c[0], c[1] - 1)):
            o = self.occ.get(nb)
            if o and o[0] != net:
                extra += 0.8
            if nb in self.pin_cells and self.pin_cells[nb] != net:
                extra += 1.5
        return extra

    def route(self, net, start, targets, start_dir):
        """A* von start bis zu einer Zelle aus targets. start_dir: erzwungene erste Richtung oder None."""
        tx = [t[0] for t in targets]
        ty = [t[1] for t in targets]

        def h(c):
            return max(0, min(tx) - c[0], c[0] - max(tx)) + max(0, min(ty) - c[1], c[1] - max(ty))

        best = {}
        heap = []
        dirs = [start_dir] if start_dir else list(DIRS.values())
        for d in dirs:
            heapq.heappush(heap, (h(start), 0.0, start, d, None))
        came = {}
        limit = 60000
        while heap and limit:
            limit -= 1
            _f, g, c, d, parent = heapq.heappop(heap)
            key = (c, d)
            if key in best and best[key] <= g:
                continue
            best[key] = g
            came[key] = parent
            if c != start and c in targets:
                path = [c]
                k = parent
                while k is not None:
                    path.append(k[0])
                    k = came[k]
                return path[::-1]
            for nd in DIRS.values():
                if nd == (-d[0], -d[1]):
                    continue
                if c == start and start_dir and nd != start_dir:
                    continue
                if c in self.occ and self.occ[c][0] != net and nd != d:
                    continue   # auf einer fremden Leitung nicht abbiegen
                n = (c[0] + nd[0], c[1] + nd[1])
                extra = self.free_for(net, n, nd, d)
                if extra is None:
                    continue
                off_grid = (nd[0] and n[1] % 2) or (nd[1] and n[0] % 2)
                cost = g + 1.0 + extra + (3.0 if nd != d else 0.0) + (0.6 if off_grid else 0.0)
                heapq.heappush(heap, (cost + h(n), cost, n, nd, key))
        return None

    def commit(self, net, path):
        links = self.links.setdefault(net, set())
        for a, b in zip(path, path[1:]):
            links.add((a, b) if a < b else (b, a))
        for i, c in enumerate(path):
            if c in self.pin_cells:
                continue
            if 0 < i < len(path) - 1:
                a, b = path[i - 1], path[i + 1]
                kind = "h" if a[1] == b[1] == c[1] else "v" if a[0] == b[0] == c[0] else "n"
            else:
                kind = "n"
            old = self.occ.get(c)
            if old and old[0] == net:
                kind = "n"
            if old and old[0] != net:
                kind = "x"   # Kreuzung: bleibt für beide gerade
            if kind == "x":
                self.cross.add(c)
            else:
                self.occ[c] = (net, kind)

    def tree_cells(self, net):
        cells = set()
        for a, b in self.links.get(net, ()):
            cells.add(a)
            cells.add(b)
        return cells

    def route_net(self, net, terminals, seeds=()):
        """terminals: Liste (Zelle, Abgangsrichtung). seeds: Zellen, die schon zum Baum gehören."""
        tree = set(seeds)
        todo = list(terminals)

        def dist(a, b):
            return abs(a[0] - b[0]) + abs(a[1] - b[1])

        if not tree:
            # Hauptleitung zuerst: die beiden am weitesten auseinanderliegenden Anschlüsse.
            a = max(todo, key=lambda t: max(dist(t[0], u[0]) for u in todo))
            todo.remove(a)
            tree.add(a[0])
            if todo:
                todo.sort(key=lambda t: -dist(t[0], a[0]))
        first = not seeds   # ohne Symbol: zuerst die Hauptleitung zum entferntesten Anschluss
        failed = []
        while todo:
            if not first:
                todo.sort(key=lambda t: min(dist(t[0], c) for c in tree))
            first = False
            c, d = todo.pop(0)
            if c in tree:
                continue
            d = None
            path = self.route(net, c, (tree | self.tree_cells(net)) - self.cross, d)
            if path is None:
                failed.append(c)
                continue
            self.commit(net, path)
            tree |= set(path)
        return failed

    # ---------------------------------------------------------------- Ausgabe der Leitungen
    def wires(self):
        out = []
        junctions = []
        for net, links in self.links.items():
            adj = {}
            for a, b in links:
                adj.setdefault(a, set()).add(b)
                adj.setdefault(b, set()).add(a)
            for c, nbs in adj.items():
                deg = len(nbs) + (1 if self.pin_cells.get(c) == net else 0)
                if deg >= 3:
                    junctions.append(c)
            # gerade Stücke zusammenfassen, Knoten (Grad != 2 oder Knick) trennen
            def is_node(c):
                nbs = adj[c]
                if len(nbs) != 2 or self.pin_cells.get(c) == net:
                    return True
                a, b = list(nbs)
                return not (a[0] == b[0] == c[0] or a[1] == b[1] == c[1])

            done = set()
            for a, b in links:
                e = (a, b)
                if e in done:
                    continue
                # nach beiden Seiten verlängern
                run = [a, b]
                while not is_node(run[-1]):
                    nxt = [n for n in adj[run[-1]] if n != run[-2]][0]
                    run.append(nxt)
                while not is_node(run[0]):
                    nxt = [n for n in adj[run[0]] if n != run[1]][0]
                    run.insert(0, nxt)
                for p, q in zip(run, run[1:]):
                    done.add((p, q) if p < q else (q, p))
                (x1, y1), (x2, y2) = pos(run[0]), pos(run[-1])
                out.append(f'  (wire (pts (xy {fmt(x1)} {fmt(y1)}) (xy {fmt(x2)} {fmt(y2)}))'
                           f' (stroke (width 0) (type default)) (uuid "{uid()}"))')
        for c in junctions:
            x, y = pos(c)
            out.append(f'  (junction (at {fmt(x)} {fmt(y)}) (diameter 0) (color 0 0 0 0) (uuid "{uid()}"))')
        return out


def symbol_text(lib, x, y, rot, mirror, ref, value, unit, pins, fields, bom) -> str:
    def field(name, val, f):
        fx, fy, just, hidden = f
        if rot in (90, 180):
            just = {"left": "right", "right": "left"}.get(just, just)
        if mirror:
            just = {"left": "right", "right": "left"}.get(just, just)
        angle = 90 if rot in (90, 270) else 0
        j = "" if just == "center" else f" (justify {just})"
        hide = " (hide yes)" if hidden else ""
        val = val.replace('"', "'")
        return (f'    (property "{name}" "{val}" (at {fmt(fx)} {fmt(fy)} {angle}){hide}\n'
                f'      (effects (font (size 1.27 1.27)){j}))')

    b = "yes" if bom else "no"
    m = " (mirror y)" if mirror else ""
    pin_txt = "\n".join(f'    (pin "{n}" (uuid "{uid()}"))' for n in pins)
    return f'''  (symbol (lib_id "{lib}") (at {fmt(x)} {fmt(y)} {rot}){m} (unit {unit})
    (exclude_from_sim no) (in_bom {b}) (on_board {b}) (dnp no) (uuid "{uid()}")
{field("Reference", ref, fields[0])}
{field("Value", value, fields[1])}
{pin_txt}
    (instances (project "pegel-sender" (path "/" (reference "{ref}") (unit {unit}))))
  )'''


def pin_points(part, spec, x, y, rot, mirror):
    """(Netz, x, y, dx, dy) je angeschlossenem Pin, ohne etwas zu zeichnen."""
    net_of = {symbol_pin_of(part, pad): net for pad, net in connected_pads(part).items()}
    out = []
    for num, px, py, pa in spec:
        if num in net_of:
            wx, wy = place_point(x, y, rot, mirror, px, py)
            dx, dy = outward(rot, pa)
            out.append((net_of[num], wx, wy, -dx if mirror else dx, dy))
    return out


def orient_two_pins(placed, layout):
    """Zweipole um 180° drehen, wenn dann Versorgung oben, Masse unten und die Signalpins näher an ihren
    Partnern liegen. Das Layout gibt nur waagrecht/senkrecht und die Lage vor."""
    anchors: dict[str, list] = {}
    for net, gx, gy in layout.get("power", []):
        anchors.setdefault(net, []).append((gx * G, gy * G))
    for net, gx, gy, _s in layout.get("labels", []):
        anchors.setdefault(net, []).append((gx * G, gy * G))
    for net, x1, y1, x2, y2 in layout.get("wires", []):
        anchors.setdefault(net, []).extend([(x1 * G, y1 * G), (x2 * G, y2 * G)])
    explicit = {net for net, *_ in layout.get("power", [])}
    for _round in range(2):
        points: dict[str, list] = {}
        for i, (part, unit, spec, x, y, rot, mirror, _t, _b) in enumerate(placed):
            for net, wx, wy, _dx, _dy in pin_points(part, spec, x, y, rot, mirror):
                points.setdefault(net, []).append((i, wx, wy))
        for i, entry in enumerate(placed):
            part, unit, spec, x, y, rot, mirror, _t, _b = entry
            if len(spec) != 2 or part.ref.startswith(("J", "U", "Q", "Y")):
                continue

            def cost(r):
                total = 0.0
                for net, wx, wy, dx, dy in pin_points(part, spec, x, y, r, mirror):
                    if net in POWER_NETS and net not in explicit:
                        natural = (0, 1) if net == GND else (0, -1)
                        total += 0 if (dx, dy) == natural else 20
                        continue
                    others = [(px, py) for j, px, py in points.get(net, []) if j != i] + anchors.get(net, [])
                    if others:
                        total += min(abs(px - wx) + abs(py - wy) for px, py in others)
                return total

            flipped = (rot + 180) % 360
            if cost(flipped) < cost(rot) - 0.01:
                entry[5] = flipped


def build_sheet(key, title, parts, outside, symbols):
    layout = LAYOUT[key]
    sheet = Sheet(key, parts, outside, symbols)
    placed = []
    missing = []
    for part in parts:
        text, units, boxed = symbols[part.symbol]
        for unit, spec in sorted(units.items()):
            k = part.ref if len(units) == 1 else f"{part.ref}:{unit}"
            if k not in layout["parts"]:
                missing.append(k)
                continue
            gx, gy, rot, *flags = layout["parts"][k]
            placed.append([part, unit, spec, gx * G, gy * G, rot, "m" in flags, text, boxed])
    if missing:
        raise SystemExit(f"{key}: Lage fehlt für {', '.join(missing)}")
    orient_two_pins(placed, layout)
    all_pins = []
    for part, unit, spec, x, y, rot, mirror, text, boxed in placed:
        all_pins += sheet.place_part(part, unit, spec, x, y, rot, mirror, text, boxed)

    explicit_pwr: dict[str, list] = {}
    for net, gx, gy in layout.get("power", []):
        d = (0, 1) if net == GND else (0, -1)
        sheet.power_symbol(net, gx * G, gy * G, *d)
        explicit_pwr.setdefault(net, []).append(cell(gx * G, gy * G))
    labelled = set()
    for net, gx, gy, side in layout.get("labels", []):
        sheet.label(net, gx * G, gy * G, *DIRS[side])
        labelled.add(net)

    # Pinenden als Anschlüsse eintragen.
    # Versorgungspins verdrahten nur, wenn ein Symbol oder eine Schiene des Netzes in der Nähe ist.
    near = {}
    for net, x1, y1, x2, y2 in layout.get("wires", []):
        near.setdefault(net, []).extend([(x1 * G, y1 * G), (x2 * G, y2 * G)])
    for net, gx, gy in layout.get("power", []):
        near.setdefault(net, []).append((gx * G, gy * G))

    def wired(net, x, y):
        pts = near.get(net, [])
        return net in explicit_pwr and any(abs(px - x) + abs(py - y) <= 8 * G for px, py in pts)

    for num, x, y, dx, dy, net in all_pins:
        if net and not (net in POWER_NETS and not wired(net, x, y)):
            sheet.add_anchor(cell(x, y), net, (dx, dy))

    terminals: dict[str, list] = {}
    for num, x, y, dx, dy, net in all_pins:
        if not net:
            continue
        if net in POWER_NETS and not wired(net, x, y):
            # Versorgung ohne Symbol im Layout: Symbol direkt am Pin. Seitlicher Pin ganz unten (GND)
            # bzw. ganz oben (Versorgung): kurzer Stich, Symbol in Grundrichtung; sonst in Pinrichtung.
            natural = (0, 1) if net == GND else (0, -1)
            same_side = [p for p in all_pins if p[3:5] == (dx, dy) and abs(p[1] - x) < 0.01]
            extreme = (max(p[2] for p in same_side) == y) if net == GND else (min(p[2] for p in same_side) == y)
            if dx and extreme:
                ex = x + dx * G
                sheet.power_symbol(net, ex, y, *natural)
                a, b = cell(x, y), cell(ex, y)
                del sheet.pin_cells[b]
                sheet.pin_dir.pop(b, None)
                sheet.links.setdefault(net, set()).update(
                    ((a[0] + i * dx, a[1]), (a[0] + (i + 1) * dx, a[1])) if dx > 0 else
                    ((a[0] + (i + 1) * dx, a[1]), (a[0] + i * dx, a[1])) for i in range(abs(b[0] - a[0])))
                for cx in range(min(a[0], b[0]), max(a[0], b[0]) + 1):
                    sheet.blocked.add((cx, a[1]))
                continue
            sheet.power_symbol(net, x, y, dx, dy)
            c = cell(x, y)
            del sheet.pin_cells[c]
            sheet.pin_dir.pop(c, None)
            sheet.blocked.add(c)
            continue
        terminals.setdefault(net, []).append((cell(x, y), (dx, dy)))
    for net, cells in explicit_pwr.items():
        for c in cells:
            terminals.setdefault(net, [])
    # Netze, die das Blatt verlassen, ohne Label im Layout: Label am Pin.
    for net in list(terminals):
        if net in outside and net not in POWER_NETS and net not in labelled:
            raise SystemExit(f"{key}: Label für {net} fehlt im Layout")

    failed = []
    # Vorgegebene gerade Leitungen (Schienen), an die die Pins andocken.
    rails: dict[str, list] = {}
    for net, x1, y1, x2, y2 in layout.get("wires", []):
        a, b = cell(x1 * G, y1 * G), cell(x2 * G, y2 * G)
        path = []
        n = max(abs(b[0] - a[0]), abs(b[1] - a[1]))
        for i in range(n + 1):
            path.append((a[0] + (b[0] - a[0]) * i // n, a[1] + (b[1] - a[1]) * i // n))
        sheet.commit(net, path)
        rails.setdefault(net, []).extend(path)
        terminals.setdefault(net, [])

    order = sorted(terminals, key=lambda n: (n in POWER_NETS, len(terminals[n]), n))
    for net in order:
        terms = list(terminals[net])
        # Versorgungssymbole, Labels und Schienen sind Anker: jeder Pin verbindet sich mit dem nächsten.
        seeds = list(explicit_pwr.get(net, [])) + rails.get(net, [])
        seeds += [cell(gx * G, gy * G) for n, gx, gy, _s in layout.get("labels", []) if n == net]
        if not seeds and len(terms) < 2:
            continue
        bad = sheet.route_net(net, terms, seeds)
        failed += [f"{key}: {net} bei {pos(c)} nicht verlegt" for c in bad]

    body = "\n".join([
        "(kicad_sch",
        "  (version 20250610)",
        '  (generator "eeschema")',
        '  (generator_version "10.0")',
        f'  (uuid "{uid()}")',
        "PAPER",
        "  (title_block",
        f'    (title "pegel-sender — {title}")',
        '    (company "Veit Götz")',
        "  )",
        "  (lib_symbols",
        *(symbols[lib][0] for lib in sorted({p.symbol for p in parts} | {"power:GND"} | set(SUPPLY.values()))),
        "  )",
        *sheet.items,
        *sheet.wires(),
        ")",
    ]) + "\n"
    return body, sheet.bounds, failed


def shift(body: str, bounds) -> str:
    """Inhalt mit Rand an den Blattanfang schieben und Blattgröße setzen."""
    x0 = min(b[0] for b in bounds)
    y0 = min(b[1] for b in bounds)
    x1 = max(b[2] for b in bounds)
    y1 = max(b[3] for b in bounds)
    dx = round((10.16 - x0) / G) * G
    dy = round((10.16 - y0) / G) * G

    def move(m):
        return f"(at {float(m.group(1)) + dx:.2f} {float(m.group(2)) + dy:.2f}"

    def move_xy(m):
        return f"(xy {float(m.group(1)) + dx:.2f} {float(m.group(2)) + dy:.2f})"

    body = re.sub(r"\(at ([-\d.]+) ([-\d.]+)", move, body)
    body = re.sub(r"\(xy ([-\d.]+) ([-\d.]+)\)", move_xy, body)
    # Pins im eingebetteten Bibliothekssymbol dürfen nicht mitwandern.
    head, sep, rest = body.partition("  (lib_symbols")
    lib, sep2, tail = rest.partition("\n  )\n")
    lib = re.sub(r"\(at ([-\d.]+) ([-\d.]+)", lambda m: f"(at {float(m.group(1)) - dx:.2f} {float(m.group(2)) - dy:.2f}", lib)
    lib = re.sub(r"\(xy ([-\d.]+) ([-\d.]+)\)", lambda m: f"(xy {float(m.group(1)) - dx:.2f} {float(m.group(2)) - dy:.2f})", lib)
    body = head + sep + lib + sep2 + tail
    w = x1 - x0 + 20.32
    h = y1 - y0 + 20.32
    return body.replace("PAPER", f'  (paper "User" {w:.0f} {h:.0f})')


# ---------------------------------------------------------------- Prüfung über die KiCad-Netzliste

def check_netlist(key: str, sch: str, parts: list[design.Part]) -> list[str]:
    net_file = os.path.join(SCH_DIR, f"{key}.net")
    kicad_env.run_kicad_cli("sch", "export", "netlist", "--format", "kicadsexpr", "-o", net_file, sch)
    text = open(net_file, encoding="utf-8").read()
    node_net = {}
    for block in re.split(r"\(net\s", text)[1:]:
        name = re.search(r'\(name\s+"([^"]*)"', block).group(1)
        for ref, pin in re.findall(r'\(node\s+\(ref\s+"([^"]+)"\)\s+\(pin\s+"([^"]+)"\)', block):
            node_net[(ref, pin)] = name
    errors = []
    design_to_sch: dict[str, set[str]] = {}
    sch_to_design: dict[str, set[str]] = {}
    for part in parts:
        for pad, net in connected_pads(part).items():
            got = node_net.get((part.ref, symbol_pin_of(part, pad)))
            if got is None or got.startswith("unconnected-"):
                errors.append(f"{key}: {part.ref}.{pad} ({net}) nicht verbunden")
                continue
            design_to_sch.setdefault(net, set()).add(got)
            sch_to_design.setdefault(got, set()).add(net)
    for net, got in design_to_sch.items():
        if len(got) > 1:
            errors.append(f"{key}: {net} zerfällt in {sorted(got)}")
    for got, nets in sch_to_design.items():
        if len(nets) > 1:
            errors.append(f"{key}: {sorted(nets)} kurzgeschlossen ({got})")
    return errors


def main():
    only = set(sys.argv[1:])
    parts = [p for p in design.PARTS if p.group != "mech" and p.pins]
    symbols = {}
    for lib in {p.symbol for p in parts} | {"power:GND"} | set(SUPPLY.values()):
        numbers = [n for p in parts if p.symbol == lib for n in p.pins]
        symbols[lib] = load_symbol(lib, numbers)
    os.makedirs(SCH_DIR, exist_ok=True)
    failed = []
    for key, title in GROUPS:
        if only and key not in only:
            continue
        group = [p for p in parts if (p.group or "xiao") == key]
        outside = {n for p in parts if p.group != key for n in p.pins.values() if n}
        body, bounds, errors = build_sheet(key, title, group, outside, symbols)
        sch = os.path.join(SCH_DIR, f"{key}.kicad_sch")
        with open(sch, "w", encoding="utf-8") as handle:
            handle.write(shift(body, bounds))
        errors += check_netlist(key, sch, group)
        for err in errors:
            print(err)
        failed += errors
        svg_dir = os.path.join(SCH_DIR, key)
        os.makedirs(svg_dir, exist_ok=True)
        kicad_env.run_kicad_cli("sch", "export", "svg", "--exclude-drawing-sheet", "-o", svg_dir + os.sep, sch)
        svg = next(os.path.join(svg_dir, n) for n in os.listdir(svg_dir) if n.endswith(".svg"))
        svg_to_png(svg, os.path.join(PREVIEW, f"schematic-{key}.png"), 1800)
        print("wrote", key, len(group), "parts,", len(errors), "Fehler")
    if failed:
        raise SystemExit(f"{len(failed)} Fehler im Schaltplan")


if __name__ == "__main__":
    main()
