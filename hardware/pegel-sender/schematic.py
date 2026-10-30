"""KiCad-Schaltplan je Funktionsblock aus design.py, als .kicad_sch, SVG und PNG.

Aufruf: python3 schematic.py   (schreibt preview/schematic-<block>.png)

Aufbau jedes Blatts:
- ICs, Stecker und Transistoren in einer Reihe oben, Signalfluss von links (Stecker) nach rechts.
- Jeder Pin bekommt einen kurzen Stich mit Netzlabel oder Versorgungssymbol; benachbarte Pins
  am selben Netz teilen sich eines. Keine Leitungen quer übers Blatt.
- Passive Bauteile senkrecht im Raster darunter, sortiert nach dem IC, zu dem sie gehören.
  Ketten wie Spannungsteiler stehen als Stapel, der Abgriff hat links ein Label.
- Versorgung oben (Pfeil), Masse unten. Globale Labels für Netze, die das Blatt verlassen.

Jedes Blatt wird über die KiCad-Netzliste gegen design.py geprüft.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import design  # noqa: E402
import kicad_env  # noqa: E402
from sch_symbols import (  # noqa: E402
    fmt, lib_field, load_symbol, outward, snap, symbol_pin_of, uid, world,
)
from svg_png import svg_to_png  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PREVIEW = os.path.join(HERE, "preview")
SCH_DIR = os.path.join(PREVIEW, "schematic")

GROUPS = [
    ("solar", "Solar"),
    ("dc", "12 V"),
    ("charger", "Lader"),
    ("mppt", "MPPT"),
    ("battery", "Akku"),
    ("3v3", "3,3 V"),
    ("12v", "Sonde 12 V"),
    ("rs485", "RS485"),
    ("frost", "Frost"),
    ("xiao", "XIAO"),
]
GND = "GND"
# Versorgungsnetze als Symbol; power:VCC trägt den Netznamen im Wert.
SUPPLY = {"+3V3": "power:+3V3", "VSYS": "power:VCC", "VSOL": "power:VCC", "XIAO_3V3": "power:VCC"}
POWER_NETS = set(SUPPLY) | {GND}

STUB = 2.54
CHAR = 1.05            # Breite eines Zeichens bei 1,27-mm-Schrift
ROW_GAP = 10.16
COL_GAP = 7.62
MAX_W = 270.0


def text_w(text: str) -> float:
    return len(text) * CHAR


class Block:
    """Gruppe von Zeichenelementen in lokalen Koordinaten, wird als Ganzes platziert."""

    def __init__(self):
        self.items = []    # (art, daten)
        self.boxes = []    # belegte Rechtecke (x0, y0, x1, y1)

    def box(self, x0, y0, x1, y1):
        self.boxes.append((min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)))

    def bbox(self):
        xs0, ys0, xs1, ys1 = zip(*self.boxes)
        return min(xs0), min(ys0), max(xs1), max(ys1)

    def wire(self, x1, y1, x2, y2):
        self.items.append(("wire", (x1, y1, x2, y2)))
        self.box(x1, y1, x2, y2)

    def junction(self, x, y):
        self.items.append(("junction", (x, y)))

    def no_connect(self, x, y):
        self.items.append(("nc", (x, y)))
        self.box(x - 0.8, y - 0.8, x + 0.8, y + 0.8)

    def symbol(self, **kw):
        self.items.append(("symbol", kw))

    def text_box(self, x, y, text, just):
        w = text_w(text)
        x0 = x if just == "left" else x - w if just == "right" else x - w / 2
        self.box(x0, y - 0.8, x0 + w, y + 0.8)


def terminal(block: Block, net: str, x: float, y: float, dx: int, dy: int, outside: set[str]):
    """Versorgungssymbol oder Label am Leitungsende (x, y), Leitung kommt aus Richtung -(dx, dy)."""
    if net == GND or net in SUPPLY:
        lib = "power:GND" if net == GND else SUPPLY[net]
        # GND zeigt in Grundlage nach unten, Versorgung nach oben; Drehung gegen den Uhrzeigersinn.
        rot = ({(0, 1): 0, (1, 0): 90, (0, -1): 180, (-1, 0): 270} if net == GND
               else {(0, -1): 0, (-1, 0): 90, (0, 1): 180, (1, 0): 270})[(dx, dy)]
        reach = 3.3 if net == GND else 3.0
        tx, ty = x + dx * (reach + 1.0), y + dy * (reach + 1.0)
        just = "left" if dx > 0 else "right" if dx < 0 else "center"
        if dy:
            ty += 0.3 * dy
        block.symbol(lib=lib, x=x, y=y, rot=rot, ref="#PWR", value=net, unit=1, pins=["1"],
                     ref_f=(x, y, "center", True), val_f=(tx, ty, just, False), bom=False)
        block.box(x - 1.4 if dy else x, y - 1.4 if dx else y, x + dx * reach + (1.4 if dy else 0),
                  y + dy * reach + (1.4 if dx else 0))
        block.text_box(tx, ty, net, just)
        return
    glob = net in outside
    ang = {(1, 0): 0, (0, -1): 90, (-1, 0): 180, (0, 1): 270}[(dx, dy)]
    block.items.append(("label", (net, x, y, ang, glob)))
    length = text_w(net) + (2.6 if glob else 0.4)
    if dx:
        block.box(x, y - 1.0, x + dx * length, y + 1.0)
    else:
        block.box(x - 1.0, y, x + 1.0, y + dy * length)


# ---------------------------------------------------------------- Bauteilarten

def is_passive(part: design.Part) -> bool:
    return len(part.pins) == 2 and part.ref[:1] not in "UJQY"


def connected_pads(part):
    return {pad: net for pad, net in part.pins.items() if net}


def order_anchors(parts: list[design.Part]) -> list[design.Part]:
    """Von den Steckern aus breadth-first, damit verbundene Bauteile nebeneinander stehen."""
    adj = {p.ref: set() for p in parts}
    by_net: dict[str, list[str]] = {}
    for p in parts:
        for net in connected_pads(p).values():
            if net not in POWER_NETS:
                by_net.setdefault(net, []).append(p.ref)
    for refs in by_net.values():
        for a in refs:
            adj[a].update(r for r in refs if r != a)
    roots = [p.ref for p in parts if p.ref.startswith("J")] or [parts[0].ref]
    rank = {r: 0 for r in roots}
    wave = list(roots)
    while wave:
        nxt = []
        for ref in wave:
            for other in sorted(adj[ref]):
                if other not in rank:
                    rank[other] = rank[ref] + 1
                    nxt.append(other)
        wave = nxt
    return sorted(parts, key=lambda p: (rank.get(p.ref, 99), p.ref))


# ---------------------------------------------------------------- ICs, Stecker, Transistoren

def anchor_block(part, unit, pins_spec, sym_text, boxed, outside) -> Block:
    block = Block()
    net_of = {symbol_pin_of(part, pad): net for pad, net in connected_pads(part).items()}
    located = []
    for num, px, py, pa in pins_spec:
        x, y = world(0, 0, 0, px, py)
        dx, dy = outward(0, pa)
        located.append((num, x, y, dx, dy, net_of.get(num)))
    xs = [p[1] for p in located]
    ys = [p[2] for p in located]
    body = (min(xs) - 1.27, min(ys) - 1.27, max(xs) + 1.27, max(ys) + 1.27)
    if part.symbol.startswith("Device:Q_"):
        body = (body[0], body[1], body[2] + 2.0, body[3])   # Kreis rechts der D/S-Pins
    block.box(*body)

    # Pins einer Seite am selben Netz, die direkt untereinander liegen, teilen sich ein Label.
    side = {}
    for num, x, y, dx, dy, net in located:
        side.setdefault((dx, dy, x if dx else y), []).append((y if dx else x, num, net))
    shared = {}
    for key, row in side.items():
        row.sort()
        for i in range(1, len(row)):
            if row[i][2] and row[i][2] == row[i - 1][2]:
                shared[row[i][1]] = shared.get(row[i - 1][1], row[i - 1][1])
    for num, x, y, dx, dy, net in located:
        if not net:
            block.no_connect(x, y)
            continue
        ex, ey = x + dx * STUB, y + dy * STUB
        block.wire(x, y, ex, ey)
        lead = shared.get(num)
        if lead:
            lx, ly = next((lx + ldx * STUB, ly + ldy * STUB) for n, lx, ly, ldx, ldy, _ in located if n == lead)
            block.wire(ex, ey, lx, ly)
            block.junction(ex, ey)
            block.junction(lx, ly)
            continue
        terminal(block, net, ex, ey, dx, dy, outside)

    # Felder: Lage aus der Bibliothek, sonst über/unter dem Körper; nichts auf Labels oder Pinnummern.
    ref_lib = None if boxed else lib_field(sym_text, "Reference")
    val_lib = None if boxed else lib_field(sym_text, "Value")
    taken = list(block.boxes[1:])
    for _num, x, y, dx, dy, _net in located:
        ix, iy = x - dx * 2.54, y - dy * 2.54
        taken.append((min(x, ix) - 1.0, min(y, iy) - 1.0, max(x, ix) + 1.0, max(y, iy) + 1.0))
    x0, y0, x1, y1 = body
    fields = []
    for text, lib in ((part.ref, ref_lib), (part.value, val_lib)):
        options = []
        if lib:
            options.append((lib[0], -lib[1], lib[2]))
        options += [(x0, y0 - 1.6 - 2.54 * k, "left") for k in range(4)]
        options += [(x0, y1 + 1.6 + 2.54 * k, "left") for k in range(4)]
        for fx, fy, just in options:
            w = text_w(text)
            fx0 = fx if just == "left" else fx - w if just == "right" else fx - w / 2
            box = (fx0, fy - 0.8, fx0 + w, fy + 0.8)
            if not any(box[0] < b[2] and b[0] < box[2] and box[1] < b[3] and b[1] < box[3] for b in taken):
                break
        taken.append(box)
        block.box(*box)
        fields.append((fx, fy, just, False))
    block.symbol(lib=part.symbol, x=0.0, y=0.0, rot=0, ref=part.ref, value=part.value, unit=unit,
                 pins=[p[0] for p in pins_spec], ref_f=fields[0], val_f=fields[1], bom=True)
    return block


# ---------------------------------------------------------------- passive Bauteile

def chains(passives: list[design.Part], all_parts: list[design.Part]) -> list[list[design.Part]]:
    """Ketten aus Zweipolen, deren gemeinsames Netz nur diese beiden passiven Pins hat (Teiler, Filter)."""
    count = {}
    for p in passives:
        for net in connected_pads(p).values():
            count[net] = count.get(net, 0) + 1
    link: dict[str, list[tuple[str, str]]] = {p.ref: [] for p in passives}
    by_net: dict[str, list[str]] = {}
    for p in passives:
        for net in connected_pads(p).values():
            if net not in POWER_NETS and count[net] == 2:
                by_net.setdefault(net, []).append(p.ref)
    for net, refs in by_net.items():
        if len(refs) == 2 and refs[0] != refs[1]:
            link[refs[0]].append((refs[1], net))
            link[refs[1]].append((refs[0], net))
    parts = {p.ref: p for p in passives}
    seen, out = set(), []
    for p in passives:
        if p.ref in seen or len(link[p.ref]) > 1:
            continue
        chain, cur, prev = [p.ref], p.ref, None
        seen.add(p.ref)
        while len(chain) < 3:
            nxt = [r for r, _n in link[cur] if r != prev and r not in seen]
            if not nxt:
                break
            prev, cur = cur, nxt[0]
            chain.append(cur)
            seen.add(cur)
        out.append([parts[r] for r in chain])
    for p in passives:   # Ringe oder Reste
        if p.ref not in seen:
            seen.add(p.ref)
            out.append([p])
    return out


def rank_net(net: str) -> int:
    """Oben im Stapel: Versorgung, unten: Masse."""
    return 0 if net in SUPPLY else 2 if net == GND else 1


def orient_chain(chain: list[design.Part]) -> list[tuple[design.Part, str, str]]:
    """(Bauteil, oberes Netz, unteres Netz) von oben nach unten."""
    def pair(part, top_net):
        nets = list(connected_pads(part).values())
        other = nets[1] if nets[0] == top_net else nets[0]
        return part, top_net, other

    if len(chain) == 1:
        a, b = list(connected_pads(chain[0]).values())
        return [pair(chain[0], a if rank_net(a) <= rank_net(b) else b)]
    joints = []
    for i in range(len(chain) - 1):
        common = set(connected_pads(chain[i]).values()) & set(connected_pads(chain[i + 1]).values())
        joints.append(common.pop())
    first_outer = next(n for n in connected_pads(chain[0]).values() if n != joints[0])
    last_outer = next(n for n in connected_pads(chain[-1]).values() if n != joints[-1])
    if rank_net(last_outer) < rank_net(first_outer):
        chain = chain[::-1]
        joints = joints[::-1]
        first_outer = last_outer
    out, top = [], first_outer
    for part in chain:
        part, top, bottom = pair(part, top)
        out.append((part, top, bottom))
        top = bottom
    return out


def vertical(spec, top_pad_sym: str):
    """Drehung, bei der der Zweipol senkrecht steht und top_pad_sym oben liegt."""
    for rot in (0, 90, 180, 270):
        pts = {num: world(0, 0, rot, px, py) for num, px, py, _pa in spec}
        (n1, (x1, y1)), (n2, (x2, y2)) = list(pts.items())[:2]
        if abs(x1 - x2) < 0.01:
            top = n1 if y1 < y2 else n2
            if top == top_pad_sym:
                return rot, pts
    raise SystemExit(f"kein senkrechter Zweipol: {spec}")


def chain_block(chain, symbols, pin_count, outside) -> Block:
    """Stapel senkrechter Zweipole bei x = 0. Felder rechts, Abgriff-Labels links."""
    block = Block()
    y = 0.0
    oriented = orient_chain(chain)
    for i, (part, top_net, bottom_net) in enumerate(oriented):
        spec = symbols[part.symbol][1][1]
        pads = connected_pads(part)
        top_pad = next(p for p, n in pads.items() if n == top_net)
        if top_net == bottom_net:
            top_pad = sorted(pads)[0]
        rot, pts = vertical(spec, symbol_pin_of(part, top_pad))
        ys = sorted(py for _px, py in pts.values())
        half = (ys[-1] - ys[0]) / 2
        cy = y + half
        block.box(-1.6, y, 1.6, y + 2 * half)
        if i == 0:
            terminal(block, top_net, 0.0, y, 0, -1, outside)
        else:
            # Abgriff zwischen zwei Bauteilen: Label nur, wenn das Netz noch woanders hin geht.
            if pin_count.get(top_net, 0) > 2 or top_net in outside:
                block.wire(0.0, y, -STUB, y)
                block.junction(0.0, y)
                terminal(block, top_net, -STUB, y, -1, 0, outside)
        ref_f = (2.54, cy - 1.27, "left", False)
        val_f = (2.54, cy + 1.27, "left", False)
        block.text_box(2.54, cy - 1.27, part.ref, "left")
        block.text_box(2.54, cy + 1.27, part.value, "left")
        block.symbol(lib=part.symbol, x=0.0, y=cy, rot=rot, ref=part.ref, value=part.value, unit=1,
                     pins=[s[0] for s in spec], ref_f=ref_f, val_f=val_f, bom=True)
        y += 2 * half
        if i == len(oriented) - 1:
            terminal(block, bottom_net, 0.0, y, 0, 1, outside)
    return block


def parallel_block(group: list[design.Part], symbols, outside) -> Block:
    """Zweipole zwischen denselben zwei Netzen nebeneinander, oben und unten über eine Schiene verbunden."""
    block = Block()
    (part0, top_net, bottom_net), = orient_chain([group[0]])
    x = 0.0
    tops, bottoms = [], []
    for part in group:
        spec = symbols[part.symbol][1][1]
        pads = connected_pads(part)
        top_pad = next(p for p, n in pads.items() if n == top_net)
        rot, pts = vertical(spec, symbol_pin_of(part, top_pad))
        ys = sorted(py for _px, py in pts.values())
        half = (ys[-1] - ys[0]) / 2
        cy = half + 2.54
        tops.append((x, cy - half))
        bottoms.append((x, cy + half))
        block.box(x - 1.6, cy - half, x + 1.6, cy + half)
        block.text_box(x + 2.54, cy - 1.27, part.ref, "left")
        block.text_box(x + 2.54, cy + 1.27, part.value, "left")
        block.symbol(lib=part.symbol, x=x, y=cy, rot=rot, ref=part.ref, value=part.value, unit=1,
                     pins=[s[0] for s in spec], ref_f=(x + 2.54, cy - 1.27, "left", False),
                     val_f=(x + 2.54, cy + 1.27, "left", False), bom=True)
        x += snap(max(10.16, 2.54 + max(text_w(part.ref), text_w(part.value)) + 5.08))
    rail_top, rail_bottom = tops[0][1] - 2.54, bottoms[0][1] + 2.54
    for (tx, ty), (bx, by) in zip(tops, bottoms):
        block.wire(tx, ty, tx, rail_top)
        block.wire(bx, by, bx, rail_bottom)
    block.wire(tops[0][0], rail_top, tops[-1][0], rail_top)
    block.wire(bottoms[0][0], rail_bottom, bottoms[-1][0], rail_bottom)
    for px, _ in tops[1:-1]:
        block.junction(px, rail_top)
        block.junction(px, rail_bottom)
    terminal(block, top_net, 0.0, rail_top, 0, -1, outside)
    terminal(block, bottom_net, 0.0, rail_bottom, 0, 1, outside)
    return block


def split_parallel(groups: list[list[design.Part]]) -> tuple[list, list]:
    """Einzelne Zweipole mit gleichem Netzpaar zu Parallelgruppen zusammenfassen."""
    by_pair: dict[frozenset, list[design.Part]] = {}
    rest = []
    for chain in groups:
        if len(chain) == 1 and len(set(connected_pads(chain[0]).values())) == 2:
            by_pair.setdefault(frozenset(connected_pads(chain[0]).values()), []).append(chain[0])
        else:
            rest.append(chain)
    parallel = []
    for parts in by_pair.values():
        if len(parts) > 1:
            parallel.append(sorted(parts, key=lambda p: (len(p.ref), p.ref)))
        else:
            rest.append(parts)
    return rest, parallel


# ---------------------------------------------------------------- Blatt

def place(blocks: list[Block], x0: float, y0: float, max_w: float, gap: float):
    """Blöcke von links nach rechts, Zeilenumbruch bei max_w. Gibt (Versätze, rechte Kante, untere Kante)."""
    offsets = []
    x, y, row_h, right = x0, y0, 0.0, x0
    for block in blocks:
        bx0, by0, bx1, by1 = block.bbox()
        w, h = bx1 - bx0, by1 - by0
        if x > x0 and x + w > x0 + max_w:
            x, y, row_h = x0, y + row_h + ROW_GAP, 0.0
        offsets.append((snap(x - bx0), snap(y - by0)))
        x += w + gap
        right = max(right, x - gap)
        row_h = max(row_h, h)
    return offsets, right, y + row_h


def emit(block: Block, ox: float, oy: float, out: dict, pwr_counter: list):
    for kind, data in block.items:
        if kind == "wire":
            x1, y1, x2, y2 = data
            out["wires"].append(
                f'  (wire (pts (xy {fmt(x1 + ox)} {fmt(y1 + oy)}) (xy {fmt(x2 + ox)} {fmt(y2 + oy)}))'
                f' (stroke (width 0) (type default)) (uuid "{uid()}"))')
        elif kind == "junction":
            x, y = data
            out["junctions"].add((round(x + ox, 2), round(y + oy, 2)))
        elif kind == "nc":
            x, y = data
            out["other"].append(f'  (no_connect (at {fmt(x + ox)} {fmt(y + oy)}) (uuid "{uid()}"))')
        elif kind == "label":
            net, x, y, ang, glob = data
            just = "left" if ang in (0, 90) else "right"
            if glob:
                out["other"].append(
                    f'  (global_label "{net}" (shape bidirectional) (at {fmt(x + ox)} {fmt(y + oy)} {ang})'
                    f' (effects (font (size 1.27 1.27)) (justify {just})) (uuid "{uid()}"))')
            else:
                out["other"].append(
                    f'  (label "{net}" (at {fmt(x + ox)} {fmt(y + oy)} {ang})'
                    f' (effects (font (size 1.27 1.27)) (justify {just} bottom)) (uuid "{uid()}"))')
        elif kind == "symbol":
            s = data
            ref = s["ref"]
            if ref == "#PWR":
                pwr_counter[0] += 1
                ref = f"#PWR{pwr_counter[0]:03d}"
            out["symbols"].append(symbol_text(s, ref, ox, oy))


def field(name, value, f, rot, ox, oy) -> str:
    """Feld waagrecht mit der gewünschten Ausrichtung. KiCad dreht Feldwinkel und -ausrichtung mit dem
    Symbol: bei 90/270° muss 90° drinstehen, bei 90/180° ist links und rechts vertauscht."""
    x, y, just, hidden = f
    if rot in (90, 180):
        just = {"left": "right", "right": "left"}.get(just, just)
    angle = 90 if rot in (90, 270) else 0
    j = "" if just == "center" else f" (justify {just})"
    hide = " (hide yes)" if hidden else ""
    value = value.replace('"', "'")
    return (f'    (property "{name}" "{value}" (at {fmt(x + ox)} {fmt(y + oy)} {angle}){hide}\n'
            f'      (effects (font (size 1.27 1.27)){j}))')


def symbol_text(s, ref, ox, oy) -> str:
    bom = "yes" if s["bom"] else "no"
    pins = "\n".join(f'    (pin "{n}" (uuid "{uid()}"))' for n in s["pins"])
    return f'''  (symbol (lib_id "{s["lib"]}") (at {fmt(s["x"] + ox)} {fmt(s["y"] + oy)} {s["rot"]}) (unit {s["unit"]})
    (exclude_from_sim no) (in_bom {bom}) (on_board {bom}) (dnp no) (uuid "{uid()}")
{field("Reference", ref, s["ref_f"], s["rot"], ox, oy)}
{field("Value", s["value"], s["val_f"], s["rot"], ox, oy)}
{pins}
    (instances (project "pegel-sender" (path "/" (reference "{ref}") (unit {s["unit"]}))))
  )'''


def build_sheet(key: str, title: str, parts: list[design.Part], outside: set[str], symbols) -> str:
    anchors = order_anchors([p for p in parts if not is_passive(p)] or parts[:1])
    passives = [p for p in parts if is_passive(p) and p not in anchors]
    pin_count: dict[str, int] = {}
    for p in parts:
        for net in connected_pads(p).values():
            pin_count[net] = pin_count.get(net, 0) + 1

    anchor_blocks = []
    for part in anchors:
        text, units, boxed = symbols[part.symbol]
        for unit, spec in sorted(units.items()):
            anchor_blocks.append(anchor_block(part, unit, spec, text, boxed, outside))

    # Passive Stapel dem IC zuordnen, mit dem sie die meisten Signalnetze teilen.
    def home(chain) -> int:
        nets = {n for p in chain for n in connected_pads(p).values()}
        best = (0, len(anchors))
        for i, a in enumerate(anchors):
            shared = set(connected_pads(a).values()) & nets
            score = sum(3 if n not in POWER_NETS else 1 for n in shared)
            if score > best[0]:
                best = (score, i)
        return best[1]

    singles, parallel = split_parallel(chains(passives, parts))
    groups = [(c, False) for c in singles] + [(c, True) for c in parallel]
    groups.sort(key=lambda g: (home(g[0]), len(g[0][0].ref), g[0][0].ref))
    chain_blocks = [parallel_block(c, symbols, outside) if par else chain_block(c, symbols, pin_count, outside)
                    for c, par in groups]

    a_off, a_right, a_bottom = place(anchor_blocks, 12.7, 12.7, MAX_W, COL_GAP * 2)
    width = max(a_right - 12.7, 150.0)
    c_off, c_right, c_bottom = place(chain_blocks, 12.7, snap(a_bottom + ROW_GAP * 1.5), width, COL_GAP)

    out = {"symbols": [], "wires": [], "junctions": set(), "other": []}
    counter = [0]
    for block, (ox, oy) in zip(anchor_blocks, a_off):
        emit(block, ox, oy, out, counter)
    for block, (ox, oy) in zip(chain_blocks, c_off):
        emit(block, ox, oy, out, counter)

    libs = {p.symbol for p in parts} | {"power:GND"} | set(SUPPLY.values())
    page_w = snap(max(a_right, c_right) + 12.7)
    page_h = snap(c_bottom + 12.7)
    return "\n".join([
        "(kicad_sch",
        "  (version 20250610)",
        '  (generator "eeschema")',
        '  (generator_version "10.0")',
        f'  (uuid "{uid()}")',
        f'  (paper "User" {page_w:.0f} {page_h:.0f})',
        "  (title_block",
        f'    (title "pegel-sender — {title}")',
        '    (date "2026-10-30")',
        '    (rev "1")',
        '    (company "Veit Götz")',
        "  )",
        "  (lib_symbols",
        *(symbols[lib][0] for lib in sorted(libs)),
        "  )",
        *out["symbols"],
        *out["wires"],
        *(f'  (junction (at {fmt(x)} {fmt(y)}) (diameter 0) (color 0 0 0 0) (uuid "{uid()}"))'
          for x, y in sorted(out["junctions"])),
        *out["other"],
        ")",
    ]) + "\n"


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
    parts = [p for p in design.PARTS if p.group != "mech" and p.pins]
    symbols = {}
    for lib in {p.symbol for p in parts} | {"power:GND"} | set(SUPPLY.values()):
        numbers = [n for p in parts if p.symbol == lib for n in p.pins]
        text, units, boxed = load_symbol(lib, numbers)
        symbols[lib] = (text, units, boxed)
    os.makedirs(SCH_DIR, exist_ok=True)
    failed = []
    for key, title in GROUPS:
        group = [p for p in parts if (p.group or "xiao") == key]
        if not group:
            continue
        outside = {n for p in parts if p.group != key for n in p.pins.values() if n}
        sch = os.path.join(SCH_DIR, f"{key}.kicad_sch")
        with open(sch, "w", encoding="utf-8") as handle:
            handle.write(build_sheet(key, title, group, outside, symbols))
        errors = check_netlist(key, sch, group)
        for err in errors:
            print(err)
        failed += errors
        svg_dir = os.path.join(SCH_DIR, key)
        os.makedirs(svg_dir, exist_ok=True)
        kicad_env.run_kicad_cli("sch", "export", "svg", "--exclude-drawing-sheet", "-o", svg_dir + os.sep, sch)
        svg = next(os.path.join(svg_dir, n) for n in os.listdir(svg_dir) if n.endswith(".svg"))
        png = os.path.join(PREVIEW, f"schematic-{key}.png")
        svg_to_png(svg, png, 1800)
        print("wrote", png, len(group), "parts,", len(errors), "Fehler")
    if failed:
        raise SystemExit(f"{len(failed)} Fehler im Schaltplan")


if __name__ == "__main__":
    main()
