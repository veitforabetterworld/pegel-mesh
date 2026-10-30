"""KiCad-Schaltplan je Funktionsblock: Symbole zweidimensional, Leitungen zwischen Pins.

Aufruf: python3 schematic_wired.py
Schreibt preview/schematic-<block>.png.
"""

import heapq
import math
import os
import re
import shutil
import subprocess
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import design  # noqa: E402
import kicad_env  # noqa: E402

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
POWER = {
    "GND": ("power:GND", 270),
    "+3V3": ("power:+3V3", 90),
}
STUB = 2.54
GAP = 12.70
LABEL_REACH = 10.16
INSET = 1.27


def uid() -> str:
    return str(uuid.uuid4())


def sym_roots() -> list[str]:
    roots = []
    for base in (
        os.path.join(kicad_env.BUILD, "AppDir", "share", "kicad", "symbols"),
        os.path.join(kicad_env.BUILD, "squashfs-root", "usr", "share", "kicad", "symbols"),
        "/usr/share/kicad/symbols",
        os.path.join(os.path.dirname(kicad_env.windows_bin() or ""), "share", "kicad", "symbols"),
    ):
        if os.path.isdir(base):
            roots.append(base)
    return roots


def find_lib_file(lib: str, name: str) -> str | None:
    for root in sym_roots():
        path = os.path.join(root, f"{lib}.kicad_symdir", f"{name}.kicad_sym")
        if os.path.isfile(path):
            return path
        path = os.path.join(root, f"{lib}.kicad_sym")   # ältere Installationen: eine Datei je Bibliothek
        if os.path.isfile(path) and f'(symbol "{name}"' in open(path, encoding="utf-8").read():
            return path
    return None


def extract_symbol(path: str, name: str, lib_id: str) -> str:
    text = open(path, encoding="utf-8").read()
    key = f'(symbol "{name}"'
    i = text.find(key)
    if i < 0:
        raise SystemExit(f"symbol {name} not in {path}")
    depth = 0
    for j in range(i, len(text)):
        if text[j] == "(":
            depth += 1
        elif text[j] == ")":
            depth -= 1
            if depth == 0:
                body = text[i : j + 1]
                return body.replace(key, f'(symbol "{lib_id}"', 1)
    raise SystemExit(f"unclosed symbol {name}")


def parse_pins(symbol_text: str) -> list[tuple[str, float, float, float]]:
    pins = []
    idx = 0
    while True:
        i = symbol_text.find("(pin ", idx)
        if i < 0:
            break
        depth = 0
        j = i
        while j < len(symbol_text):
            if symbol_text[j] == "(":
                depth += 1
            elif symbol_text[j] == ")":
                depth -= 1
                if depth == 0:
                    j += 1
                    break
            j += 1
        block = symbol_text[i:j]
        idx = j
        at = re.search(r"\(at\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\)", block)
        num = re.search(r'\(number\s+"([^"]+)"', block)
        if at and num:
            pins.append((num.group(1), float(at.group(1)), float(at.group(2)), float(at.group(3))))
    return pins


def box_symbol(lib_id: str, numbers: list[str]) -> tuple[str, list[tuple[str, float, float, float]]]:
    nums = sorted(set(numbers), key=lambda n: (len(n), n))
    left = nums[::2]
    right = nums[1::2]
    rows = max(len(left), len(right), 1)
    span = (rows - 1) * 2.54
    pins = []
    for i, n in enumerate(left):
        # Winkel zeigt in den Körper, Draht geht entgegen (wie KiCad-Lib).
        pins.append((n, -10.16, span / 2 - i * 2.54, 0))
    for i, n in enumerate(right):
        pins.append((n, 10.16, span / 2 - i * 2.54, 180))
    h = span / 2 + 2.54
    pin_txt = []
    for n, x, y, ang in pins:
        pin_txt.append(
            f'''    (pin passive line (at {x} {y} {ang}) (length 2.54)
      (name "{n}" (effects (font (size 1.27 1.27))))
      (number "{n}" (effects (font (size 1.27 1.27)))))'''
        )
    unit = lib_id.split(":")[-1]
    value = lib_id.split(":")[-1]
    text = f'''(symbol "{lib_id}"
  (pin_names (offset 0.254) (hide yes))
  (exclude_from_sim no) (in_bom yes) (on_board yes)
  (property "Reference" "U" (at 0 {h + 2.54} 0) (effects (font (size 1.27 1.27))))
  (property "Value" "{value}" (at 0 {-h - 2.54} 0) (effects (font (size 1.27 1.27))))
  (symbol "{unit}_0_1"
    (rectangle (start -10.16 {-h}) (end 10.16 {h})
      (stroke (width 0.254) (type default)) (fill (type background))))
  (symbol "{unit}_1_1"
{chr(10).join(pin_txt)}
  )
  (embedded_fonts no)
)'''
    return text, pins


def direction(angle: float) -> tuple[float, float]:
    rad = math.radians(angle)
    return math.cos(rad), math.sin(rad)


def world(ix, iy, irot, px, py, pang):
    """Pinposition wie KiCad eeschema (90°-Schritte), Symbol-Y hoch, Blatt-Y runter."""
    r = int(irot) % 360
    if r == 90:
        rx, ry = -py, px
    elif r == 180:
        rx, ry = -px, -py
    elif r == 270:
        rx, ry = py, -px
    else:
        rx, ry = px, py
    return snap(ix + rx), snap(iy - ry), (pang + r) % 360


def outward(ix, iy, wx, wy, pang):
    """Draht verlässt den Anschluss entgegen dem Pin-Winkel.
    pang kommt aus world() (Symbol-Y hoch). Blatt-Y ist gespiegelt."""
    rad = math.radians(float(pang) % 360)
    return -math.cos(rad), math.sin(rad)


def snap(v: float) -> float:
    return round(v / 1.27) * 1.27


def fmt(v: float) -> str:
    return f"{snap(v):.2f}"


def symbol_instance(
    lib_id, x, y, rot, ref, value, pin_numbers,
    ref_at, val_at, bom=True, unit=1, hide_ref=False, hide_val=False,
) -> str:
    pins = "\n".join(f'    (pin "{n}" (uuid "{uid()}"))' for n in pin_numbers)
    bom_s = "yes" if bom else "no"
    hide_r = " (hide yes)" if hide_ref else ""
    hide_v = " (hide yes)" if hide_val else ""
    rx, ry = ref_at
    vx, vy = val_at
    return f'''  (symbol
    (lib_id "{lib_id}")
    (at {fmt(x)} {fmt(y)} {rot})
    (unit {unit})
    (exclude_from_sim no)
    (in_bom {bom_s})
    (on_board {bom_s})
    (dnp no)
    (uuid "{uid()}")
    (property "Reference" "{ref}" (at {fmt(rx)} {fmt(ry)} 0){hide_r}
      (effects (font (size 1.27 1.27))))
    (property "Value" "{value}" (at {fmt(vx)} {fmt(vy)} 0){hide_v}
      (effects (font (size 1.27 1.27))))
    {pins}
    (instances
      (project "pegel-sender"
        (path "/" (reference "{ref}") (unit {unit}))))
  )'''


def wire(x1, y1, x2, y2) -> str:
    return (
        f'  (wire (pts (xy {fmt(x1)} {fmt(y1)}) (xy {fmt(x2)} {fmt(y2)})) '
        f'(stroke (width 0.1524) (type default)) (uuid "{uid()}"))'
    )


def junction(x, y) -> str:
    return f'  (junction (at {fmt(x)} {fmt(y)}) (uuid "{uid()}"))'


def label(net, x, y, angle) -> str:
    justify = "left" if angle in (0, 90) else "right"
    return f'''  (global_label "{net}"
    (shape bidirectional)
    (at {fmt(x)} {fmt(y)} {int(angle)})
    (effects (font (size 1.27 1.27)) (justify {justify}))
    (uuid "{uid()}"))'''


def sexp_from(text: str, start: int) -> str:
    depth = 0
    for j in range(start, len(text)):
        if text[j] == "(":
            depth += 1
        elif text[j] == ")":
            depth -= 1
            if depth == 0:
                return text[start : j + 1]
    raise SystemExit("unclosed s-expression")


def parse_units(symbol_text: str, local_name: str) -> dict[int, list]:
    """Pins je Einheit. Einheit 0 ist nur die gemeinsame Grafik."""
    units: dict[int, list] = {}
    token = f'(symbol "{local_name}_'
    idx = 0
    while True:
        i = symbol_text.find(token, idx)
        if i < 0:
            break
        match = re.match(rf'\(symbol "{re.escape(local_name)}_(\d+)_\d+"', symbol_text[i:])
        if not match:
            idx = i + len(token)
            continue
        block = sexp_from(symbol_text, i)
        idx = i + len(block)
        unit = int(match.group(1))
        if unit == 0:
            continue
        found = parse_pins(block)
        if found:
            units[unit] = found
    if not units:
        found = parse_pins(symbol_text)
        if found:
            units[1] = found
    return units


def flatten_extends(body: str, lib: str, name: str, lib_id: str) -> str:
    """KiCad-CLI rendert extends in eingebetteten Libs oft ohne Grafik — Parent einflachen."""
    match = re.search(r'\(extends "([^"]+)"\)', body)
    if not match:
        return body
    parent = match.group(1)
    parent_path = find_lib_file(lib, parent)
    if not parent_path:
        return body
    parent_id = f"{lib}:{parent}"
    parent_body = extract_symbol(parent_path, parent, parent_id)
    flat = parent_body.replace(f'(symbol "{parent_id}"', f'(symbol "{lib_id}"', 1)
    flat = flat.replace(f"{parent}_", f"{name}_")
    val = re.search(r'\(property "Value" "([^"]+)"', body)
    if val:
        flat = re.sub(
            r'\(property "Value" "[^"]+"',
            lambda m, v=val.group(1): f'(property "Value" "{v}"',
            flat,
            count=1,
        )
    return flat


def load_symbols(parts: list[design.Part]):
    texts = {}
    pins = {}
    units = {}
    boxed = set()
    for part in parts:
        lib_id = part.symbol
        if lib_id in texts:
            continue
        lib, name = lib_id.split(":", 1)
        path = None if lib == "pegel" else find_lib_file(lib, name)
        if path:
            body = extract_symbol(path, name, lib_id)
            if re.search(r'\(extends "([^"]+)"\)', body):
                parent = re.search(r'\(extends "([^"]+)"\)', body).group(1)
                parent_id = f"{lib}:{parent}"
                if parent_id not in texts:
                    texts[parent_id] = extract_symbol(find_lib_file(lib, parent), parent, parent_id)
                body = flatten_extends(body, lib, name, lib_id)
            units[lib_id] = parse_units(body, name)
            texts[lib_id] = body
            pins[lib_id] = [pin for group in units[lib_id].values() for pin in group]
        else:
            numbers = []
            for other in parts:
                if other.symbol == lib_id:
                    numbers.extend(other.pins)
            texts[lib_id], pins[lib_id] = box_symbol(lib_id, numbers)
            units[lib_id] = {1: pins[lib_id]}
            boxed.add(lib_id)
    for lib_id, _local_angle in POWER.values():
        if lib_id in texts:
            continue
        lib, name = lib_id.split(":", 1)
        path = find_lib_file(lib, name)
        texts[lib_id] = extract_symbol(path, name, lib_id)
        units[lib_id] = parse_units(texts[lib_id], name)
        pins[lib_id] = [pin for group in units[lib_id].values() for pin in group]
    return texts, pins, units, boxed


def axis_dir(dx: float, dy: float) -> tuple[float, float]:
    if abs(dx) >= abs(dy):
        return (1.0 if dx >= 0 else -1.0), 0.0
    return 0.0, (1.0 if dy >= 0 else -1.0)


def sheet_angle(dx: float, dy: float) -> int:
    """Richtung auf dem Blatt: 0 rechts, 90 oben, 180 links, 270 unten."""
    if abs(dx) >= abs(dy):
        return 0 if dx > 0 else 180
    return 90 if dy < 0 else 270


def power_rot(lib_id: str, dx: float, dy: float) -> int:
    """Drehung, damit die Symbolgrafik in Laufrichtung (dx, dy) zeigt."""
    if lib_id == "power:GND":
        ang = math.degrees(math.atan2(dx, dy))
    else:
        ang = math.degrees(math.atan2(-dx, -dy))
    return int(round(ang / 90.0) * 90) % 360


def overlaps(a, b, gap: float = 0.0) -> bool:
    return a[0] < b[2] + gap and a[2] > b[0] - gap and a[1] < b[3] + gap and a[3] > b[1] - gap


def point_on_seg(px, py, x1, y1, x2, y2, tol=0.06) -> bool:
    if abs(x1 - x2) <= tol:
        if abs(px - x1) > tol:
            return False
        return min(y1, y2) - tol <= py <= max(y1, y2) + tol
    if abs(y1 - y2) <= tol:
        if abs(py - y1) > tol:
            return False
        return min(x1, x2) - tol <= px <= max(x1, x2) + tol
    return False


def seg_hits_rect(x1, y1, x2, y2, rect) -> bool:
    """Achsenstück schneidet das offene Rechteck."""
    x0, y0, x3, y3 = rect
    if abs(x1 - x2) <= 0.06:
        x = x1
        if x <= x0 or x >= x3:
            return False
        ya, yb = sorted((y1, y2))
        return min(yb, y3) - max(ya, y0) > 0.08
    if abs(y1 - y2) <= 0.06:
        y = y1
        if y <= y0 or y >= y3:
            return False
        xa, xb = sorted((x1, x2))
        return min(xb, x3) - max(xa, x0) > 0.08
    return False


def segs_touch(a, b) -> bool:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    if point_on_seg(ax1, ay1, bx1, by1, bx2, by2) or point_on_seg(ax2, ay2, bx1, by1, bx2, by2):
        return True
    if point_on_seg(bx1, by1, ax1, ay1, ax2, ay2) or point_on_seg(bx2, by2, ax1, ay1, ax2, ay2):
        return True
    a_h, b_h = abs(ay1 - ay2) <= 0.06, abs(by1 - by2) <= 0.06
    a_v, b_v = abs(ax1 - ax2) <= 0.06, abs(bx1 - bx2) <= 0.06
    if a_h and b_v:
        return point_on_seg(bx1, ay1, ax1, ay1, ax2, ay2) and point_on_seg(bx1, ay1, bx1, by1, bx2, by2)
    if a_v and b_h:
        return point_on_seg(ax1, by1, bx1, by1, bx2, by2) and point_on_seg(ax1, by1, ax1, ay1, ax2, ay2)
    return False


def clean_segs(raw) -> list[tuple]:
    out = []
    for x1, y1, x2, y2 in raw:
        x1, y1, x2, y2 = round(x1, 2), round(y1, 2), round(x2, 2), round(y2, 2)
        if abs(x1 - x2) <= 0.02 and abs(y1 - y2) <= 0.02:
            continue
        if abs(x1 - x2) > 0.02 and abs(y1 - y2) > 0.02:
            out.append((x1, y1, x2, y1))
            out.append((x2, y1, x2, y2))
            continue
        out.append((x1, y1, x2, y2))
    return out


def merge_straight_joints(segs) -> list:
    """Nur kollineare Stücke an einem Grad-2-Punkt zusammenziehen. Lage bleibt."""
    out = [tuple(seg) for seg in segs]
    changed = True
    while changed:
        changed = False
        deg: dict[tuple, int] = {}
        for seg in out:
            for x, y in ((seg[0], seg[1]), (seg[2], seg[3])):
                key = (seg[4], round(x, 2), round(y, 2))
                deg[key] = deg.get(key, 0) + 1
        for i in range(len(out)):
            x1, y1, x2, y2, net = out[i]
            for j in range(i + 1, len(out)):
                u1, v1, u2, v2, net2 = out[j]
                if net2 != net:
                    continue
                horiz = (
                    abs(y1 - y2) <= 0.06
                    and abs(v1 - v2) <= 0.06
                    and abs(y1 - v1) <= 0.06
                )
                vert = (
                    abs(x1 - x2) <= 0.06
                    and abs(u1 - u2) <= 0.06
                    and abs(x1 - u1) <= 0.06
                )
                if not horiz and not vert:
                    continue
                shared = None
                for px, py in ((x1, y1), (x2, y2)):
                    if endpoint_at((u1, v1, u2, v2), px, py):
                        shared = (round(px, 2), round(py, 2))
                        break
                if shared is None or deg.get((net, shared[0], shared[1]), 0) != 2:
                    continue
                if horiz:
                    xs = sorted((x1, x2, u1, u2))
                    out[i] = (xs[0], y1, xs[-1], y1, net)
                else:
                    ys = sorted((y1, y2, v1, v2))
                    out[i] = (x1, ys[0], x1, ys[-1], net)
                out.pop(j)
                changed = True
                break
            if changed:
                break
    return out


def wire_junction_points(segs, geoms, powers) -> set[tuple[float, float]]:
    """Punkt mit mindestens drei Drahtenden, kein Bauteil- und kein Power-Pin."""
    skip = {(round(pin.x, 2), round(pin.y, 2)) for geom in geoms for pin in geom.pins}
    for pwr in powers:
        skip.add((round(pwr["x"], 2), round(pwr["y"], 2)))
    count: dict[tuple[float, float], int] = {}
    for seg in segs:
        for x, y in ((seg[0], seg[1]), (seg[2], seg[3])):
            key = (round(x, 2), round(y, 2))
            count[key] = count.get(key, 0) + 1
    return {pt for pt, n in count.items() if n >= 3 and pt not in skip}


def wires_overlap(a, b) -> bool:
    """Echte Überdeckung zweier kollinearer Strecken, nicht nur ein gemeinsamer Endpunkt."""
    ax1, ay1, ax2, ay2 = a[:4]
    bx1, by1, bx2, by2 = b[:4]
    if abs(ay1 - ay2) <= 0.06 and abs(by1 - by2) <= 0.06 and abs(ay1 - by1) <= 0.06:
        a0, a1 = sorted((ax1, ax2))
        b0, b1 = sorted((bx1, bx2))
        return min(a1, b1) - max(a0, b0) > 0.05
    if abs(ax1 - ax2) <= 0.06 and abs(bx1 - bx2) <= 0.06 and abs(ax1 - bx1) <= 0.06:
        a0, a1 = sorted((ay1, ay2))
        b0, b1 = sorted((by1, by2))
        return min(a1, b1) - max(a0, b0) > 0.05
    return False


def assert_wires(key, geoms, segs, labels, powers) -> list[str]:
    """Offene Enden, Überlappung, Pin ohne genau einen Endpunkt."""
    errors = []
    anchors = {(round(pin.x, 2), round(pin.y, 2)) for geom in geoms for pin in geom.pins}
    for pwr in powers:
        anchors.add((round(pwr["x"], 2), round(pwr["y"], 2)))
    for lab in labels:
        anchors.add((round(lab["x"], 2), round(lab["y"], 2)))
    deg: dict[tuple, int] = {}
    for seg in segs:
        for x, y in ((seg[0], seg[1]), (seg[2], seg[3])):
            key_pt = (round(x, 2), round(y, 2), seg[4])
            deg[key_pt] = deg.get(key_pt, 0) + 1
    for (x, y, net), n in deg.items():
        if n >= 2 or (x, y) in anchors:
            continue
        errors.append(f"{key}: offenes Ende {net} @ {x:.2f},{y:.2f}")
    for i, seg in enumerate(segs):
        for other in segs[i + 1 :]:
            if seg[4] == other[4] and wires_overlap(seg, other):
                errors.append(f"{key}: Überlappung {seg[4]}")
                break
    for geom in geoms:
        for pin in geom.pins:
            n = deg.get((round(pin.x, 2), round(pin.y, 2), pin.net), 0)
            if n != 1:
                errors.append(f"{key}: Pin {geom.part.ref}.{pin.sym} Endpunkte {n}")
    for pwr in powers:
        n = deg.get((round(pwr["x"], 2), round(pwr["y"], 2), pwr["name"]), 0)
        if n != 1:
            errors.append(f"{key}: Power {pwr['name']} Endpunkte {n}")
    uniq = []
    for err in errors:
        if err not in uniq:
            uniq.append(err)
    return uniq


def orth(ax, ay, bx, by) -> list[tuple]:
    return clean_segs([(ax, ay, bx, by)])


def text_size(text: str) -> tuple[float, float]:
    return max(3.8, len(text) * 1.08 + 1.4), 2.6


def center_box(cx, cy, w, h) -> tuple:
    return (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)


def label_box(x, y, angle, text) -> tuple:
    w = len(text) * 1.2 + 3.6
    h = 3.4
    if angle == 0:
        return (x + 2.0, y - h / 2, x + 2.0 + w, y + h / 2)
    if angle == 180:
        return (x - 2.0 - w, y - h / 2, x - 2.0, y + h / 2)
    if angle == 90:
        return (x - h / 2, y - 2.0 - w, x + h / 2, y - 2.0)
    return (x - h / 2, y + 2.0, x + h / 2, y + 2.0 + w)


def keepout(seg, margin=1.55) -> tuple:
    x1, y1, x2, y2 = seg
    if abs(y1 - y2) <= 0.06:
        return (min(x1, x2), y1 - margin, max(x1, x2), y1 + margin)
    return (x1 - margin, min(y1, y2), x1 + margin, max(y1, y2))


def spiral():
    yield 0.0, 0.0
    for radius in (2.54, 5.08, 7.62, 10.16, 12.70, 15.24, 17.78, 20.32, 25.40, 30.48):
        for sx in (0, 1, -1):
            for sy in (0, 1, -1):
                if sx or sy:
                    yield sx * radius, sy * radius


class Pin:
    def __init__(self, net, sym, x, y, dx, dy):
        self.net = net
        self.sym = sym
        self.x = x
        self.y = y
        self.dx = dx
        self.dy = dy


class Geom:
    def __init__(self, part, x, y, rot, spec, unit, pins, graphic):
        self.part = part
        self.x = x
        self.y = y
        self.rot = rot
        self.spec = spec
        self.unit = unit
        self.pins = pins
        self.graphic = graphic


def symbol_pin_of(part: design.Part, pad: str) -> str:
    """Footprint-Pad auf die Pinnummer des Schaltplansymbols. MOSFETs heißen G/D/S, nicht 1/2/3."""
    if part.symbol not in ("Device:Q_NMOS", "Device:Q_PMOS"):
        return pad
    if "TO-252" in part.footprint:
        table = {"1": "G", "2": "D", "3": "S"}
    else:
        table = {"1": "G", "2": "S", "3": "D"}
    return table.get(pad, pad)


def part_kind(part: design.Part) -> str:
    if part.symbol in ("Device:Q_NMOS", "Device:Q_PMOS"):
        return "anchor"
    nets = [n for n in part.pins.values() if n]
    if len(part.pins) > 2 or part.ref[:1] in "UJY":
        return "anchor"
    sig = [n for n in nets if n not in POWER]
    if len(nets) == 2 and not sig:
        return "bypass"
    if len(nets) == 2 and len(sig) == 1:
        return "shunt"
    if len(nets) == 2 and len(sig) == 2:
        return "series"
    return "anchor"


def rotation_towards(spec, sym_pin, want_dx, want_dy) -> int:
    local = next((px, py, pa) for n, px, py, pa in spec if n == sym_pin)
    best_rot, best_dot = 0, -2.0
    for rot in (0, 90, 180, 270):
        wx, wy, wa = world(0, 0, rot, *local)
        dx, dy = axis_dir(*outward(0, 0, wx, wy, wa))
        dot = dx * want_dx + dy * want_dy
        if dot > best_dot + 1e-6 or (abs(dot - best_dot) <= 1e-6 and rot < best_rot):
            best_dot, best_rot = dot, rot
    return best_rot


def make_pins(part, x, y, rot, spec) -> list[Pin]:
    located = {}
    for num, px, py, pa in spec:
        wx, wy, wa = world(x, y, rot, px, py, pa)
        wx, wy = snap(wx), snap(wy)
        dx, dy = axis_dir(*outward(x, y, wx, wy, wa))
        located[num] = (wx, wy, dx, dy)
    pins = []
    for pad, net in part.pins.items():
        if not net:
            continue
        sym = symbol_pin_of(part, pad)
        if sym not in located:
            continue
        wx, wy, dx, dy = located[sym]
        pins.append(Pin(net, sym, wx, wy, dx, dy))
    return pins


def make_graphic(x, y, rot, spec, boxed: bool, symbol: str = "") -> tuple:
    if not boxed and symbol in ("Device:Q_NMOS", "Device:Q_PMOS"):
        # Kreis (Mitte 1.651, r 2.794) plus Gate-Strich. Pinspitzen bleiben draußen.
        local = (-2.70, -3.15, 4.60, 3.15)
        pts = []
        for px, py in (
            (local[0], local[1]),
            (local[2], local[1]),
            (local[0], local[3]),
            (local[2], local[3]),
        ):
            wx, wy, _wa = world(x, y, rot, px, py, 0)
            pts.append((wx, wy))
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return (min(xs), min(ys), max(xs), max(ys))
    if boxed:
        ys = [abs(py) for _n, _px, py, _pa in spec] or [2.54]
        h = max(ys) + 2.54
        pts = []
        for cx in (-10.16, 10.16):
            for cy in (-h, h):
                wx, wy, _wa = world(x, y, rot, cx, cy, 0)
                pts.append((wx, wy))
        xs = [p[0] for p in pts]
        yss = [p[1] for p in pts]
        return (min(xs), min(yss), max(xs), max(yss))
    # Körper bleibt hinter den Pins, sonst gilt jede Stub-Leitung als Treffer.
    pts = [(x, y)]
    for _n, px, py, pa in spec:
        wx, wy, _wa = world(x, y, rot, px, py, pa)
        pts.append((x + (wx - x) * 0.58, y + (wy - y) * 0.58))
    xs = [p[0] for p in pts]
    yss = [p[1] for p in pts]
    return (min(xs), min(yss), max(xs), max(yss))


def half_extent(spec, rot) -> tuple[float, float]:
    xs, ys = [0.0], [0.0]
    for _n, px, py, pa in spec:
        wx, wy, _wa = world(0, 0, rot, px, py, pa)
        xs.append(abs(wx))
        ys.append(abs(wy))
    return max(xs) + 2.0, max(ys) + 2.0


def anchor_rot(part: design.Part) -> int:
    if part.symbol.startswith("Connector:Screw") or part.symbol.startswith("Connector_Generic:"):
        return 180
    return 0


def pin_axis(spec) -> str:
    if len(spec) < 2:
        return "x"
    xs = [px for _n, px, _py, _pa in spec]
    ys = [py for _n, _px, py, _pa in spec]
    return "y" if (max(ys) - min(ys)) >= (max(xs) - min(xs)) else "x"


def order_parts(parts: list[design.Part]) -> list[design.Part]:
    """Von Klemme oder IC aus breadth-first, damit Ketten nebeneinander landen."""
    nets: dict[str, list[str]] = {}
    for part in parts:
        for net in part.pins.values():
            if net and net not in POWER:
                nets.setdefault(net, []).append(part.ref)
    adj: dict[str, set[str]] = {p.ref: set() for p in parts}
    for refs in nets.values():
        for a in refs:
            for b in refs:
                if a != b and a in adj and b in adj:
                    adj[a].add(b)
    roots = [p.ref for p in parts if p.ref.startswith("J")]
    if not roots:
        roots = [p.ref for p in parts if p.ref.startswith("U")][:1]
    if not roots and parts:
        roots = [parts[0].ref]
    rank = {ref: 0 for ref in roots}
    wave = list(roots)
    while wave:
        nxt = []
        for ref in wave:
            for other in adj[ref]:
                if other not in rank:
                    rank[other] = rank[ref] + 1
                    nxt.append(other)
        wave = nxt
    for part in parts:
        rank.setdefault(part.ref, 99)
    return sorted(parts, key=lambda p: (rank[p.ref], p.ref))


def sym_for(part, spec, net) -> str | None:
    pad = next((num for num, n in part.pins.items() if n == net), None)
    if pad is None:
        return None
    sym = symbol_pin_of(part, pad)
    if any(n == sym for n, *_ in spec):
        return sym
    return None


def index_pins(geoms) -> dict[str, list[Pin]]:
    nets: dict[str, list[Pin]] = {}
    for geom in geoms:
        for pin in geom.pins:
            nets.setdefault(pin.net, []).append(pin)
    return nets


def fits(graphic, occupied, gap=1.27) -> bool:
    return not any(overlaps(graphic, old, gap) for old in occupied)


def stub_box(graphic, pins) -> tuple:
    """Kollisionsbox inklusive Stub, damit der nächste Körper nicht auf der Leitung landet."""
    x0, y0, x1, y1 = graphic
    reach = STUB + 1.27
    for pin in pins:
        sx = pin.x + pin.dx * reach
        sy = pin.y + pin.dy * reach
        x0, y0 = min(x0, sx), min(y0, sy)
        x1, y1 = max(x1, sx), max(y1, sy)
    return (x0 - 0.8, y0 - 0.8, x1 + 0.8, y1 + 0.8)


def pins_clash(pins, geoms) -> bool:
    for geom in geoms:
        for old in geom.pins:
            for pin in pins:
                if abs(old.x - pin.x) < 0.5 and abs(old.y - pin.y) < 0.5:
                    return True
    return False


def add_geom(part, cx, cy, rot, spec, unit, occupied, geoms, boxed, force=False):
    cx, cy = snap(cx), snap(cy)
    pins = make_pins(part, cx, cy, rot, spec)
    graphic = make_graphic(cx, cy, rot, spec, part.symbol in boxed, part.symbol)
    block = stub_box(graphic, pins)
    if not force and (not fits(block, occupied) or pins_clash(pins, geoms)):
        return None
    geom = Geom(part, cx, cy, rot, spec, unit, pins, graphic)
    geoms.append(geom)
    occupied.append(block)
    return geom


def try_pin_at(part, spec, unit, sym, tx, ty, want, occupied, geoms, boxed):
    rot = rotation_towards(spec, sym, want[0], want[1])
    _n, px, py, pa = next(p for p in spec if p[0] == sym)
    sx, sy, _sa = world(0, 0, rot, px, py, pa)
    cx, cy = snap(tx - sx), snap(ty - sy)
    return add_geom(part, cx, cy, rot, spec, unit, occupied, geoms, boxed)


def place_anchors(parts, pin_map, unit_map, occupied, geoms, boxed):
    cursor = 34.0
    for part in order_parts([p for p in parts if part_kind(p) == "anchor"]):
        units = unit_map.get(part.symbol) or {1: pin_map.get(part.symbol, [])}
        rot = anchor_rot(part)
        hx = 8.0
        for _unit, spec in units.items():
            hx = max(hx, half_extent(spec, rot)[0])
        cx = snap(cursor + hx)
        y_top = 32.0
        for unit, spec in sorted(units.items()):
            _hx, hy = half_extent(spec, rot)
            cy = snap(y_top + hy)
            placed = None
            for _try in range(6):
                placed = add_geom(part, cx, cy, rot, spec, unit, occupied, geoms, boxed)
                if placed:
                    break
                cy = snap(cy + 5.08)
            if not placed:
                add_geom(part, cx, cy, rot, spec, unit, occupied, geoms, boxed, force=True)
                print(part.ref, "unit", unit, "erzwungen")
            y_top = cy + hy + 14.0
        cursor = cx + hx + 32.0


def attach_passives(parts, pin_map, occupied, geoms, boxed):
    pending = order_parts([p for p in parts if part_kind(p) != "anchor"])
    progress = True
    while progress and pending:
        progress = False
        nxt = []
        nets = index_pins(geoms)
        for part in pending:
            spec = pin_map.get(part.symbol) or []
            if spec and attach_one(part, spec, nets, occupied, geoms, boxed):
                progress = True
                nets = index_pins(geoms)
            else:
                nxt.append(part)
        pending = nxt
    if not pending:
        return
    y = 40.0
    if geoms:
        y = max(g.graphic[3] for g in geoms) + 22.0
    x = 34.0
    print("ohne Kette:", " ".join(p.ref for p in pending))
    for part in pending:
        spec = pin_map.get(part.symbol) or []
        if not spec:
            print("kein Symbol", part.ref)
            continue
        kind = part_kind(part)
        if kind == "shunt":
            pwr = next(n for n in part.pins.values() if n in POWER)
            sym = sym_for(part, spec, pwr)
            rot = rotation_towards(spec, sym, 0, 1) if sym else 0
        elif kind == "bypass":
            sym = sym_for(part, spec, "GND")
            rot = rotation_towards(spec, sym, 0, 1) if sym else 0
        else:
            rot = 90 if pin_axis(spec) == "y" else 0
        placed = None
        for i in range(16):
            placed = add_geom(part, snap(x + i * 2.54), snap(y), rot, spec, 1, occupied, geoms, boxed)
            if placed:
                x = placed.graphic[2] + 16.0
                break
        if not placed:
            add_geom(part, snap(x), snap(y), rot, spec, 1, occupied, geoms, boxed, force=True)
            x += 24.0


def attach_one(part, spec, nets, occupied, geoms, boxed) -> bool:
    kind = part_kind(part)
    if kind == "series":
        return attach_series(part, spec, nets, occupied, geoms, boxed)
    if kind == "shunt":
        return attach_shunt(part, spec, nets, occupied, geoms, boxed)
    if kind == "bypass":
        return attach_bypass(part, spec, nets, occupied, geoms, boxed)
    return False


def attach_series(part, spec, nets, occupied, geoms, boxed) -> bool:
    options = [n for n in part.pins.values() if n and n not in POWER and n in nets]
    for net in options:
        sym = sym_for(part, spec, net)
        if not sym:
            continue
        for host in nets[net]:
            perp = (-host.dy, host.dx)
            for dist in (GAP, GAP + 5.08, GAP + 10.16, GAP + 15.24):
                for k in (0, 1, -1, 2, -2, 3, -3):
                    tx = host.x + host.dx * dist + perp[0] * k * 10.16
                    ty = host.y + host.dy * dist + perp[1] * k * 10.16
                    want = (-host.dx, -host.dy) if k == 0 else axis_dir(host.x - tx, host.y - ty)
                    if try_pin_at(part, spec, 1, sym, tx, ty, want, occupied, geoms, boxed):
                        return True
    return False


def attach_shunt(part, spec, nets, occupied, geoms, boxed) -> bool:
    sig = next(n for n in part.pins.values() if n and n not in POWER)
    pwr = next(n for n in part.pins.values() if n in POWER)
    if sig not in nets:
        return False
    sym = sym_for(part, spec, sig)
    if not sym:
        return False
    prefer = (0.0, 1.0) if pwr == "GND" else (0.0, -1.0)
    for host in nets[sig]:
        sides = []
        outward = (host.dx, host.dy)
        perp = ((-host.dy, host.dx), (host.dy, -host.dx))
        ordered = sorted(perp, key=lambda side: -(side[0] * prefer[0] + side[1] * prefer[1]))
        for side in (*ordered, outward):
            if side not in sides:
                sides.append(side)
        for side in sides:
            for dist in (GAP, GAP + 5.08, GAP + 10.16, GAP + 15.24):
                tx = host.x + host.dx * STUB + side[0] * dist
                ty = host.y + host.dy * STUB + side[1] * dist
                want = (-side[0], -side[1])
                if try_pin_at(part, spec, 1, sym, tx, ty, want, occupied, geoms, boxed):
                    return True
    return False


def attach_bypass(part, spec, nets, occupied, geoms, boxed) -> bool:
    pos = next(n for n in part.pins.values() if n and n != "GND")
    if pos not in nets:
        return False
    sym = sym_for(part, spec, pos)
    if not sym:
        return False
    for host in nets[pos]:
        for side in ((0.0, 1.0), (0.0, -1.0), (1.0, 0.0), (-1.0, 0.0)):
            for dist in (GAP, GAP + 5.08, GAP + 10.16):
                tx = host.x + side[0] * dist
                ty = host.y + side[1] * dist
                want = (-side[0], -side[1])
                if try_pin_at(part, spec, 1, sym, tx, ty, want, occupied, geoms, boxed):
                    return True
    return False


def translate(geoms, segs, labels, fields, powers, dx, dy):
    if not dx and not dy:
        return
    for geom in geoms:
        geom.x = round(geom.x + dx, 2)
        geom.y = round(geom.y + dy, 2)
        x0, y0, x1, y1 = geom.graphic
        geom.graphic = (x0 + dx, y0 + dy, x1 + dx, y1 + dy)
        for pin in geom.pins:
            pin.x = round(pin.x + dx, 2)
            pin.y = round(pin.y + dy, 2)
    for i, seg in enumerate(segs):
        x1, y1, x2, y2, net = seg
        segs[i] = (round(x1 + dx, 2), round(y1 + dy, 2), round(x2 + dx, 2), round(y2 + dy, 2), net)
    for lab in labels:
        lab["x"] = round(lab["x"] + dx, 2)
        lab["y"] = round(lab["y"] + dy, 2)
        box = lab["box"]
        lab["box"] = (box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy)
    for key, pair in list(fields.items()):
        (rx, ry), (vx, vy) = pair
        fields[key] = ((rx + dx, ry + dy), (vx + vx and 0 or 0, 0))
        fields[key] = ((rx + dx, ry + dy), (vx + dx, vy + dy))
    for pwr in powers:
        pwr["x"] = round(pwr["x"] + dx, 2)
        pwr["y"] = round(pwr["y"] + dy, 2)
        vx, vy = pwr["val"]
        pwr["val"] = (vx + dx, vy + dy)
        box = pwr["rect"]
        pwr["rect"] = (box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy)


def shift_into_sheet(geoms):
    if not geoms:
        return
    minx = min(min(g.graphic[0], *(p.x for p in g.pins)) for g in geoms)
    miny = min(min(g.graphic[1], *(p.y for p in g.pins)) for g in geoms)
    dx = snap(28 - minx) if minx < 28 else 0.0
    dy = snap(28 - miny) if miny < 28 else 0.0
    translate(geoms, [], [], {}, [], dx, dy)


def foreign_pts(geoms, net) -> list[tuple]:
    pts = []
    for geom in geoms:
        for pin in geom.pins:
            if pin.net != net:
                pts.append((pin.x, pin.y))
    return pts


def other_segs(segs, net) -> list[tuple]:
    return [seg[:4] for seg in segs if seg[4] != net]


def path_clear(raw, blocks, foreign, taken) -> bool:
    for x1, y1, x2, y2 in clean_segs(raw):
        for block in blocks:
            if seg_hits_rect(x1, y1, x2, y2, block):
                return False
        for px, py in foreign:
            if point_on_seg(px, py, x1, y1, x2, y2):
                return False
        for old in taken:
            if segs_touch((x1, y1, x2, y2), old):
                return False
    return True


def _seg_key(x1, y1, x2, y2, net):
    a = (round(x1, 2), round(y1, 2))
    b = (round(x2, 2), round(y2, 2))
    return (a, b, net) if a <= b else (b, a, net)


def _on_interior(px, py, x1, y1, x2, y2) -> bool:
    if not point_on_seg(px, py, x1, y1, x2, y2):
        return False
    if abs(px - x1) <= 0.06 and abs(py - y1) <= 0.06:
        return False
    if abs(px - x2) <= 0.06 and abs(py - y2) <= 0.06:
        return False
    return True


def _split_existing(segs, seen, net, px, py):
    px, py = round(px, 2), round(py, 2)
    i = 0
    while i < len(segs):
        x1, y1, x2, y2, n = segs[i]
        if n != net or not _on_interior(px, py, x1, y1, x2, y2):
            i += 1
            continue
        seen.discard(_seg_key(x1, y1, x2, y2, net))
        segs.pop(i)
        for a, b in (((x1, y1), (px, py)), ((px, py), (x2, y2))):
            key = _seg_key(a[0], a[1], b[0], b[1], net)
            if key in seen:
                continue
            seen.add(key)
            segs.insert(i, (round(a[0], 2), round(a[1], 2), round(b[0], 2), round(b[1], 2), net))
            i += 1


def add_path(segs, raw, net, seen):
    """Neue Strecke einfügen. Liegt ein Ende auf einer bestehenden Mitte, dort teilen."""
    for x1, y1, x2, y2 in clean_segs(raw):
        x1, y1, x2, y2 = round(x1, 2), round(y1, 2), round(x2, 2), round(y2, 2)
        if abs(x1 - x2) <= 0.02 and abs(y1 - y2) <= 0.02:
            continue
        _split_existing(segs, seen, net, x1, y1)
        _split_existing(segs, seen, net, x2, y2)
        cuts = []
        for ox1, oy1, ox2, oy2, onet in segs:
            if onet != net:
                continue
            for px, py in ((ox1, oy1), (ox2, oy2)):
                if _on_interior(px, py, x1, y1, x2, y2) and (px, py) not in cuts:
                    cuts.append((round(px, 2), round(py, 2)))
        pieces = [(x1, y1, x2, y2)]
        for px, py in cuts:
            nxt = []
            for a, b, c, d in pieces:
                if _on_interior(px, py, a, b, c, d):
                    nxt.append((a, b, px, py))
                    nxt.append((px, py, c, d))
                else:
                    nxt.append((a, b, c, d))
            pieces = nxt
        for a, b, c, d in pieces:
            key = _seg_key(a, b, c, d, net)
            if key in seen:
                continue
            seen.add(key)
            segs.append((round(a, 2), round(b, 2), round(c, 2), round(d, 2), net))


def two_point_paths(a, b):
    ax, ay = a
    bx, by = b
    paths = [orth(ax, ay, bx, by)]
    if abs(ax - bx) > 0.06 and abs(ay - by) > 0.06:
        paths.append(clean_segs([(ax, ay, bx, ay), (bx, ay, bx, by)]))
        paths.append(clean_segs([(ax, ay, ax, by), (ax, by, bx, by)]))
    for delta in (5.08, -5.08, 10.16, -10.16, 15.24, -15.24):
        paths.append(clean_segs([(ax, ay, ax, ay + delta), (ax, ay + delta, bx, ay + delta), (bx, ay + delta, bx, by)]))
        paths.append(clean_segs([(ax, ay, ax + delta, ay), (ax + delta, ay, ax + delta, by), (ax + delta, by, bx, by)]))
    return paths


def y_candidates(pts, blocks):
    med = snap(sum(p[1] for p in pts) / len(pts))
    found = []
    for step in range(0, 28):
        found.append(snap(med + step * 2.54))
        found.append(snap(med - step * 2.54))
    if blocks:
        top = min(b[1] for b in blocks)
        bot = max(b[3] for b in blocks)
        for step in range(2, 18):
            found.append(snap(top - step * 2.54))
            found.append(snap(bot + step * 2.54))
    out = []
    for y in found:
        if y not in out:
            out.append(y)
    return out


def x_candidates(pts, blocks):
    med = snap(sum(p[0] for p in pts) / len(pts))
    found = []
    for step in range(0, 28):
        found.append(snap(med + step * 2.54))
        found.append(snap(med - step * 2.54))
    if blocks:
        left = min(b[0] for b in blocks)
        right = max(b[2] for b in blocks)
        for step in range(2, 18):
            found.append(snap(left - step * 2.54))
            found.append(snap(right + step * 2.54))
    out = []
    for x in found:
        if x not in out:
            out.append(x)
    return out


def bus_clear(pts, fixed, horizontal, blocks, foreign, taken) -> list | None:
    segs = []
    coords = []
    for x, y in pts:
        if horizontal:
            segs.append((x, y, x, fixed))
            coords.append(x)
        else:
            segs.append((x, y, fixed, y))
            coords.append(y)
    lo, hi = min(coords), max(coords)
    if horizontal:
        segs.append((lo, fixed, hi, fixed))
    else:
        segs.append((fixed, lo, fixed, hi))
    segs = clean_segs(segs)
    if path_clear(segs, blocks, foreign, taken):
        return segs
    return None


def border_polyline(start, end, x0, y0, x1, y1):
    rect = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]

    def edge_of(pt):
        x, y = pt
        if abs(y - y0) <= 0.1 and x0 - 0.1 <= x <= x1 + 0.1:
            return 0
        if abs(x - x1) <= 0.1 and y0 - 0.1 <= y <= y1 + 0.1:
            return 1
        if abs(y - y1) <= 0.1 and x0 - 0.1 <= x <= x1 + 0.1:
            return 2
        return 3

    def on_way(ax, ay, ex, ey, cx, cy):
        if abs(ay - cy) <= 0.1:
            return abs(ey - ay) <= 0.1 and min(ax, cx) - 0.1 <= ex <= max(ax, cx) + 0.1
        return abs(ex - ax) <= 0.1 and min(ay, cy) - 0.1 <= ey <= max(ay, cy) + 0.1

    segs = []
    edge = edge_of(start)
    cx, cy = start
    for _ in range(6):
        if abs(cx - end[0]) <= 0.08 and abs(cy - end[1]) <= 0.08:
            break
        nx, ny = rect[(edge + 1) % 4]
        if edge_of(end) == edge and on_way(cx, cy, end[0], end[1], nx, ny):
            segs.append((cx, cy, end[0], end[1]))
            break
        segs.append((cx, cy, nx, ny))
        cx, cy = nx, ny
        edge = (edge + 1) % 4
    return clean_segs(segs)


def perimeter(terms, blocks, foreign, taken):
    if not blocks:
        return None
    base = (
        min(b[0] for b in blocks),
        min(b[1] for b in blocks),
        max(b[2] for b in blocks),
        max(b[3] for b in blocks),
    )
    for grow in range(3, 14):
        margin = grow * 2.54
        x0, y0 = snap(base[0] - margin), snap(base[1] - margin)
        x1, y1 = snap(base[2] + margin), snap(base[3] + margin)
        doors = []
        lead = []
        ok = True
        for x, y, dx, dy in terms:
            door = None
            trial = None
            for dist in (5.08, 7.62, 10.16, 12.70, 15.24, 20.32):
                for ddx, ddy in ((dx, dy), (-dy, dx), (dy, -dx), (-dx, -dy)):
                    ex, ey = round(x + ddx * dist, 2), round(y + ddy * dist, 2)
                    if ddx > 0:
                        bx, by = x1, ey
                    elif ddx < 0:
                        bx, by = x0, ey
                    elif ddy > 0:
                        bx, by = ex, y1
                    else:
                        bx, by = ex, y0
                    bx, by = round(bx, 2), round(by, 2)
                    # Tür muss auf dem Rand liegen
                    if min(abs(bx - x0), abs(bx - x1), abs(by - y0), abs(by - y1)) > 0.2:
                        continue
                    candidate = clean_segs([(x, y, ex, ey), (ex, ey, bx, by)])
                    if path_clear(candidate, blocks, foreign, taken):
                        door = (bx, by)
                        trial = candidate
                        break
                if door:
                    break
            if not door:
                ok = False
                break
            doors.append(door)
            lead.extend(trial)
        if not ok:
            continue
        def border_pos(pt):
            x, y = pt
            if abs(y - y0) <= 0.1:
                return x - x0
            if abs(x - x1) <= 0.1:
                return (x1 - x0) + (y - y0)
            if abs(y - y1) <= 0.1:
                return (x1 - x0) + (y1 - y0) + (x1 - x)
            return 2 * (x1 - x0) + (y1 - y0) + (y1 - y)
        ordered = sorted(doors, key=border_pos)
        ring = []
        for a, b in zip(ordered, ordered[1:]):
            ring.extend(border_polyline(a, b, x0, y0, x1, y1))
        if path_clear(ring, blocks, foreign, taken):
            return lead + ring
    return None


def route_signal(stub_pts, blocks, foreign, taken):
    pts = []
    seen = set()
    for x, y, _dx, _dy in stub_pts:
        key = (round(x, 2), round(y, 2))
        if key not in seen:
            seen.add(key)
            pts.append(key)
    if len(pts) < 2:
        return []
    if len(pts) == 2:
        for path in two_point_paths(pts[0], pts[1]):
            if path_clear(path, blocks, foreign, taken):
                return path
    for y in y_candidates(pts, blocks):
        path = bus_clear(pts, y, True, blocks, foreign, taken)
        if path is not None:
            return path
    for x in x_candidates(pts, blocks):
        path = bus_clear(pts, x, False, blocks, foreign, taken)
        if path is not None:
            return path
    return perimeter(stub_pts, blocks, foreign, taken)


def power_rect(x, y, dx, dy) -> tuple:
    """Nur die Grafik vor dem Anschluss, nicht die Leitung dahinter."""
    near, far, perp = 1.8, 9.4, 3.3
    x0, y0 = x + dx * near, y + dy * near
    x1, y1 = x + dx * far, y + dy * far
    return (
        min(x0, x1) - abs(dy) * perp,
        min(y0, y1) - abs(dx) * perp,
        max(x0, x1) + abs(dy) * perp,
        max(y0, y1) + abs(dx) * perp,
    )


def place_power(pin, blocks, foreign, taken):
    perps = [(-pin.dy, pin.dx), (pin.dy, -pin.dx)]
    options = [(pin.dx, pin.dy)] + perps
    for dist in (7.62, 10.16, 12.70, 15.24, 20.32, 25.40):
        for dx, dy in options:
            if (dx, dy) == (pin.dx, pin.dy):
                x = round(pin.x + dx * dist, 2)
                y = round(pin.y + dy * dist, 2)
                raw = [(pin.x, pin.y, x, y)]
            else:
                sx = round(pin.x + pin.dx * STUB, 2)
                sy = round(pin.y + pin.dy * STUB, 2)
                x = round(sx + dx * dist, 2)
                y = round(sy + dy * dist, 2)
                raw = [(pin.x, pin.y, sx, sy), (sx, sy, x, y)]
            rect = power_rect(x, y, dx, dy)
            if any(overlaps(rect, block, 0.4) for block in blocks):
                continue
            if any(rect[0] <= px <= rect[2] and rect[1] <= py <= rect[3] for px, py in foreign):
                continue
            if not path_clear(raw, blocks, foreign, taken):
                continue
            return raw, x, y, dx, dy, rect
    return None


def number_box(pin: Pin) -> tuple:
    cx = pin.x - pin.dx * 2.1
    cy = pin.y - pin.dy * 2.1
    return (cx - 1.8, cy - 1.35, cx + 1.8, cy + 1.35)


def nudge_text(cx, cy, text, obstacles):
    w, h = text_size(text)
    for ox, oy in spiral():
        box = center_box(cx + ox, cy + oy, w, h)
        if not any(overlaps(box, item, 0.35) for item in obstacles):
            return (cx + ox, cy + oy), box
    for oy in range(-48, 50, 4):
        for ox in range(-48, 50, 4):
            box = center_box(cx + ox, cy + oy, w, h)
            if not any(overlaps(box, item, 0.2) for item in obstacles):
                return (cx + ox, cy + oy), box
    return (cx, cy), center_box(cx, cy, w, h)


def field_prefs(geom: Geom):
    """Referenz und Wert über dem Symbol. Unten enden oft GND-Stubs."""
    x0, y0, _x1, _y1 = geom.graphic
    cx = (x0 + _x1) / 2
    return (cx, y0 - 7.0), (cx, y0 - 3.6)


class Maze:
    """Raster 1,27 mm. Volle Zellen sind Symbole, fremde Pins oder fremde Leitungen."""

    def __init__(self, geoms):
        xs, ys = [], []
        for geom in geoms:
            xs.extend((geom.graphic[0], geom.graphic[2]))
            ys.extend((geom.graphic[1], geom.graphic[3]))
            for pin in geom.pins:
                xs.append(pin.x)
                ys.append(pin.y)
        pad = 36.0
        self.x0 = snap(min(xs) - pad)
        self.y0 = snap(min(ys) - pad)
        self.nx = int(round((max(xs) + pad - self.x0) / 1.27)) + 2
        self.ny = int(round((max(ys) + pad - self.y0) / 1.27)) + 2
        self.solid: set[tuple[int, int]] = set()
        self.wires: dict[str, set[tuple[int, int]]] = {}
        for geom in geoms:
            self.fill_rect(geom.graphic, self.solid, grow=0.35)
            for pin in geom.pins:
                cell = self.cell(pin.x, pin.y)
                if self.inside(cell):
                    self.solid.add(cell)

    def cell(self, x, y) -> tuple[int, int]:
        return int(round((x - self.x0) / 1.27)), int(round((y - self.y0) / 1.27))

    def xy(self, cell) -> tuple[float, float]:
        ix, iy = cell
        return round(self.x0 + ix * 1.27, 2), round(self.y0 + iy * 1.27, 2)

    def inside(self, cell) -> bool:
        ix, iy = cell
        return 0 <= ix < self.nx and 0 <= iy < self.ny

    def fill_rect(self, rect, into: set, grow: float = 0.0):
        x0, y0, x1, y1 = rect
        ix0, iy0 = self.cell(x0 - grow, y0 - grow)
        ix1, iy1 = self.cell(x1 + grow, y1 + grow)
        for ix in range(min(ix0, ix1), max(ix0, ix1) + 1):
            for iy in range(min(iy0, iy1), max(iy0, iy1) + 1):
                if self.inside((ix, iy)):
                    into.add((ix, iy))

    def fill_seg(self, seg, into: set):
        x1, y1, x2, y2 = seg[:4]
        ix, iy = self.cell(x1, y1)
        ex, ey = self.cell(x2, y2)
        guard = 0
        while guard < 800:
            guard += 1
            if self.inside((ix, iy)):
                into.add((ix, iy))
            if (ix, iy) == (ex, ey):
                break
            if ix != ex:
                ix += 1 if ex > ix else -1
            elif iy != ey:
                iy += 1 if ey > iy else -1

    def blocked_for(self, net: str) -> set:
        blocked = set(self.solid)
        for name, cells in self.wires.items():
            if name != net:
                blocked |= cells
        return blocked

    def neighbors(self, cell):
        ix, iy = cell
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nxt = (ix + dx, iy + dy)
            if self.inside(nxt):
                yield nxt

    def bfs(self, sources: set, goals: set, blocked: set):
        from collections import deque

        goals = set(goals) - set(sources)
        if not goals:
            return []
        queue = deque(sources)
        seen = set(sources)
        prev = {}
        found = None
        while queue:
            cur = queue.popleft()
            for nxt in self.neighbors(cur):
                if nxt in seen or nxt in blocked:
                    continue
                seen.add(nxt)
                prev[nxt] = cur
                if nxt in goals:
                    found = nxt
                    queue.clear()
                    break
                queue.append(nxt)
        if found is None:
            return None
        path = [found]
        cur = found
        while cur not in sources:
            cur = prev[cur]
            path.append(cur)
        path.reverse()
        return path

    def cells_to_segs(self, cells) -> list:
        if not cells or len(cells) < 2:
            return []
        pts = [self.xy(c) for c in cells]
        sx, sy = pts[0]
        px, py = pts[0]
        horiz = None
        segs = []
        for x, y in pts[1:]:
            step_h = abs(y - py) <= 0.02
            if horiz is None:
                horiz = step_h
            elif step_h != horiz:
                segs.append((sx, sy, px, py))
                sx, sy = px, py
                horiz = step_h
            px, py = x, y
        segs.append((sx, sy, px, py))
        return clean_segs(segs)

    def remember(self, net: str, raw):
        cells = self.wires.setdefault(net, set())
        for seg in clean_segs(raw):
            self.fill_seg(seg, cells)

    def foreign_owner(self, net: str) -> dict:
        owner = {}
        for name, cells in self.wires.items():
            if name == net:
                continue
            for cell in cells:
                owner.setdefault(cell, name)
        return owner

    def route(self, sources: set, goals: set, net: str, pin_pts=(), extra_block=()):
        """Kürzester Weg. Vertikale Abschnitte bevorzugt auf Pin-Spalten."""
        owner = self.foreign_owner(net)
        blocked = set(self.solid)
        blocked.update(extra_block)
        pin_cols = set()
        pin_rows = set()
        for px, py in pin_pts:
            cell = self.cell(px, py)
            if self.inside(cell):
                pin_cols.add(cell[0])
                pin_rows.add(cell[1])
        sources = {cell for cell in sources if self.inside(cell)}
        goals = {cell for cell in goals if self.inside(cell)} - sources
        for cell in sources | goals:
            blocked.discard(cell)
        if not sources:
            return None
        if not goals:
            return []
        dist = {cell: 0 for cell in sources}
        prev = {cell: None for cell in sources}
        queue = [(0, cell) for cell in sources]
        heapq.heapify(queue)
        found = None
        while queue:
            cost, cur = heapq.heappop(queue)
            if cost != dist.get(cur):
                continue
            if cur in goals:
                found = cur
                break
            for nxt in self.neighbors(cur):
                if nxt in blocked:
                    continue
                if nxt in owner and cur in owner and owner[nxt] == owner[cur]:
                    continue
                step = 1 + (8 if nxt in owner else 0)
                if pin_cols and cur[0] == nxt[0] and nxt[0] not in pin_cols:
                    step += 6
                if pin_rows and cur[1] == nxt[1] and nxt[1] not in pin_rows:
                    step += 2
                new = cost + step
                if new < dist.get(nxt, 10**9):
                    dist[nxt] = new
                    prev[nxt] = cur
                    heapq.heappush(queue, (new, nxt))
        if found is None:
            return None
        path = [found]
        cur = found
        while prev[cur] is not None:
            cur = prev[cur]
            path.append(cur)
        path.reverse()
        return path

    def link(self, net: str, points, pin_pts=()) -> list | None:
        cells = []
        for x, y in points:
            cell = self.cell(x, y)
            if not self.inside(cell):
                continue
            if cell not in cells:
                cells.append(cell)
        if len(cells) <= 1:
            return []
        sources = {cells[0]}
        segs = []
        for goal in cells[1:]:
            path = self.route(sources, {goal}, net, pin_pts)
            if path is None:
                return None
            segs.extend(self.cells_to_segs(path))
            sources.update(path)
        return segs

    def rect_free(self, rect, blocked, ignore) -> bool:
        ix0, iy0 = self.cell(rect[0], rect[1])
        ix1, iy1 = self.cell(rect[2], rect[3])
        for ix in range(min(ix0, ix1), max(ix0, ix1) + 1):
            for iy in range(min(iy0, iy1), max(iy0, iy1) + 1):
                cell = (ix, iy)
                if cell == ignore:
                    continue
                if not self.inside(cell) or cell in blocked:
                    return False
        return True

    def seal_stub(self, x1, y1, x2, y2):
        """Zellen zwischen Pin und Landepunkt sperren. Der Landepunkt bleibt offen."""
        ix, iy = self.cell(x1, y1)
        ex, ey = self.cell(x2, y2)
        guard = 0
        while guard < 800:
            guard += 1
            if (ix, iy) != (ex, ey) and self.inside((ix, iy)):
                self.solid.add((ix, iy))
            if (ix, iy) == (ex, ey):
                break
            if ix != ex:
                ix += 1 if ex > ix else -1
            elif iy != ey:
                iy += 1 if ey > iy else -1

    def power_path(self, pin, graphic):
        """Ein Weg: Stub in Abgangsrichtung, dann zum Power-Pin. Kein zweiter Ast."""
        from collections import deque

        landed = None
        for steps in (2, 3, 4, 6, 8, 10, 12):
            x2 = snap(pin.x + pin.dx * 1.27 * steps)
            y2 = snap(pin.y + pin.dy * 1.27 * steps)
            cell = self.cell(x2, y2)
            blocked = self.blocked_for(pin.net)
            if (
                self.inside(cell)
                and cell not in blocked
                and not seg_hits_rect(pin.x, pin.y, x2, y2, graphic)
            ):
                landed = (self.xy(cell)[0], self.xy(cell)[1], cell, steps)
                break
        if landed is None:
            return None
        lx, ly, lcell, stub_steps = landed
        self.seal_stub(pin.x, pin.y, lx, ly)
        blocked = self.blocked_for(pin.net)
        blocked.discard(lcell)
        queue = deque([lcell])
        dist = {lcell: 0}
        prev = {lcell: None}
        best = None
        while queue:
            cur = queue.popleft()
            if dist[cur] >= 70:
                continue
            for nxt in self.neighbors(cur):
                if nxt in dist or nxt in blocked:
                    continue
                dist[nxt] = dist[cur] + 1
                prev[nxt] = cur
                queue.append(nxt)
                if stub_steps + dist[nxt] < 5:
                    continue
                x, y = self.xy(nxt)
                px, py = self.xy(prev[nxt])
                dx, dy = axis_dir(x - px, y - py)
                rect = power_rect(x, y, dx, dy)
                if not self.rect_free(rect, blocked, nxt):
                    continue
                score = dist[nxt] + (0 if (dx, dy) == (pin.dx, pin.dy) else 4)
                if best is None or score < best[0]:
                    best = (score, nxt, dx, dy, rect)
        if best is None:
            return None
        _score, goal, dx, dy, rect = best
        tail = []
        cur = goal
        while cur is not None:
            tail.append(cur)
            cur = prev[cur]
        tail.reverse()
        cells = []
        cx, cy = self.cell(pin.x, pin.y)
        ex, ey = lcell
        cells.append((cx, cy))
        guard = 0
        while (cx, cy) != (ex, ey) and guard < 800:
            guard += 1
            if cx != ex:
                cx += 1 if ex > cx else -1
            elif cy != ey:
                cy += 1 if ey > cy else -1
            cells.append((cx, cy))
        if tail and tail[0] == lcell:
            cells.extend(tail[1:])
        else:
            cells.extend(tail)
        segs = self.cells_to_segs(cells)
        gx, gy = self.xy(self.cell(pin.x, pin.y))
        if segs and (abs(gx - pin.x) > 0.05 or abs(gy - pin.y) > 0.05):
            segs = clean_segs([(pin.x, pin.y, gx, gy)]) + segs
        return segs, self.xy(goal), dx, dy, rect


def layout_sheet(parts, pin_map, unit_map, boxed, outside):
    geoms = []
    occupied = []
    place_anchors(parts, pin_map, unit_map, occupied, geoms, boxed)
    attach_passives(parts, pin_map, occupied, geoms, boxed)
    shift_into_sheet(geoms)
    maze = Maze(geoms)
    blocks = [g.graphic for g in geoms]
    segs = []
    seen = set()
    stubs: dict[str, list] = {}
    for geom in geoms:
        for pin in geom.pins:
            if pin.net in POWER:
                continue
            landed = None
            for steps in (2, 3, 4, 6, 8):
                x2 = pin.x + pin.dx * 1.27 * steps
                y2 = pin.y + pin.dy * 1.27 * steps
                cell = maze.cell(x2, y2)
                blocked = maze.blocked_for(pin.net)
                if maze.inside(cell) and cell not in blocked and not seg_hits_rect(
                    pin.x, pin.y, x2, y2, geom.graphic
                ):
                    landed = maze.xy(cell)
                    break
            if landed is None:
                print("kein Stub", geom.part.ref, pin.sym, pin.net)
                continue
            add_path(segs, [(pin.x, pin.y, landed[0], landed[1])], pin.net, seen)
            maze.remember(pin.net, [(pin.x, pin.y, landed[0], landed[1])])
            maze.seal_stub(pin.x, pin.y, landed[0], landed[1])
            stubs.setdefault(pin.net, []).append((landed[0], landed[1], pin.dx, pin.dy))

    powers = []
    powered = set()
    for geom in geoms:
        for pin in geom.pins:
            if pin.net not in POWER:
                continue
            key = (pin.net, round(pin.x, 2), round(pin.y, 2))
            if key in powered:
                continue
            powered.add(key)
            got = maze.power_path(pin, geom.graphic)
            if not got:
                print("kein Power-Symbol", geom.part.ref, pin.sym, pin.net)
                continue
            raw, (x, y), dx, dy, rect = got
            add_path(segs, raw, pin.net, seen)
            maze.remember(pin.net, raw)
            maze.fill_rect(rect, maze.solid, grow=0.2)
            blocks.append(rect)
            lib_id = POWER[pin.net][0]
            powers.append({
                "lib": lib_id,
                "x": x,
                "y": y,
                "rot": power_rot(lib_id, dx, dy),
                "val": (round(x + dx * 7.2, 2), round(y + dy * 7.2, 2)),
                "name": pin.net,
                "rect": rect,
            })

    for net, ends in list(stubs.items()):
        path = maze.link(net, [(x, y) for x, y, _dx, _dy in ends])
        if path is None:
            print("keine Trasse", net, len(ends))
            continue
        add_path(segs, path, net, seen)
        maze.remember(net, path)

    obstacles = list(blocks)
    obstacles.extend(keepout(seg[:4]) for seg in segs)
    for geom in geoms:
        for pin in geom.pins:
            obstacles.append(number_box(pin))
    for pwr in powers:
        (nx, ny), box = nudge_text(pwr["val"][0], pwr["val"][1], pwr["name"], obstacles)
        pwr["val"] = (nx, ny)
        obstacles.append(box)

    def fill_hot(rect, grow=0.45):
        maze.fill_rect(rect, hot, grow=grow)

    hot: set[tuple[int, int]] = set()
    reserved: set[tuple[int, int]] = set()
    for item in obstacles:
        fill_hot(item)
    for geom in geoms:
        for pin in geom.pins:
            maze.fill_rect(number_box(pin), reserved, grow=0.15)
    for pwr in powers:
        w, h = text_size(pwr["name"])
        maze.fill_rect(center_box(pwr["val"][0], pwr["val"][1], w, h), reserved, grow=0.4)

    def box_in_hot(box) -> bool:
        ix0, iy0 = maze.cell(box[0], box[1])
        ix1, iy1 = maze.cell(box[2], box[3])
        for ix in range(min(ix0, ix1), max(ix0, ix1) + 1):
            for iy in range(min(iy0, iy1), max(iy0, iy1) + 1):
                if (ix, iy) in hot:
                    return True
        return False

    labels = []
    missing = []
    for net, ends in stubs.items():
        if net not in outside and len(ends) != 1:
            continue
        sources = set()
        for x, y, _dx, _dy in ends:
            cell = maze.cell(x, y)
            if maze.inside(cell):
                sources.add(cell)
        if not sources:
            print("kein Label", net)
            missing.append(net)
            continue
        owner = maze.foreign_owner(net)
        blocked = set(maze.solid) | reserved | set(owner)
        for cell in sources:
            blocked.discard(cell)

        def label_clear(box) -> bool:
            for seg in segs:
                if seg_hits_rect(*seg[:4], box):
                    return False
            for geom in geoms:
                if overlaps(box, geom.graphic, 0.2):
                    return False
                for pin in geom.pins:
                    if overlaps(box, number_box(pin), 0.0):
                        return False
            for lab in labels:
                if overlaps(box, lab["box"], 0.3):
                    return False
            for pwr in powers:
                w, h = text_size(pwr["name"])
                if overlaps(box, center_box(pwr["val"][0], pwr["val"][1], w, h), 0.3):
                    return False
            return True
        cost = {cell: 0 for cell in sources}
        steps = {cell: 0 for cell in sources}
        prev = {cell: None for cell in sources}
        queue = [(0, cell) for cell in sources]
        heapq.heapify(queue)
        best = None
        while queue:
            cur_cost, cur = heapq.heappop(queue)
            if cur_cost != cost.get(cur):
                continue
            if best is not None and cur_cost > best[0]:
                break
            for nxt in maze.neighbors(cur):
                if nxt in blocked:
                    continue
                if nxt in owner and cur in owner and owner[nxt] == owner[cur]:
                    continue
                step = 1 + (8 if nxt in owner else 0)
                new = cur_cost + step
                if new >= cost.get(nxt, 10**9):
                    continue
                cost[nxt] = new
                steps[nxt] = steps[cur] + 1
                prev[nxt] = cur
                heapq.heappush(queue, (new, nxt))
                if steps[nxt] < 1:
                    continue
                gx, gy = maze.xy(nxt)
                px, py = maze.xy(cur)
                adx, ady = axis_dir(gx - px, gy - py)
                prefer = sheet_angle(adx, ady)
                chosen = None
                for ang in (prefer, 0, 90, 180, 270):
                    box = label_box(gx, gy, ang, net)
                    if label_clear(box):
                        chosen = (ang, box)
                        break
                if chosen is None:
                    continue
                ang, box = chosen
                score = new + (0 if ang == prefer else 2) + (0 if adx > 0 else 3)
                if best is None or score < best[0]:
                    best = (score, nxt, ang, box)
        if best is None:
            # Kurzer Fortsatz in Abgangsrichtung, bis der Label-Kasten frei ist.
            x0, y0, dx, dy = ends[0]
            placed = None
            for dist in (2.54, 5.08, 7.62, 10.16, 12.70, 15.24, 20.32):
                for ox, oy in ((dx, dy), (-dy, dx), (dy, -dx)):
                    gx, gy = snap(x0 + ox * dist), snap(y0 + oy * dist)
                    cell = maze.cell(gx, gy)
                    if not maze.inside(cell) or cell in maze.blocked_for(net):
                        continue
                    ang = sheet_angle(ox, oy)
                    box = label_box(gx, gy, ang, net)
                    if not label_clear(box):
                        continue
                    raw = clean_segs([(x0, y0, gx, gy)])
                    if any(
                        maze.cell(px, py) in maze.blocked_for(net)
                        for seg in raw
                        for px, py in ((seg[0], seg[1]), (seg[2], seg[3]))
                        if maze.cell(px, py) != maze.cell(x0, y0)
                    ):
                        continue
                    placed = (gx, gy, ang, box, raw)
                    break
                if placed:
                    break
            if placed is None:
                print("kein Label", net)
                missing.append(net)
                continue
            gx, gy, ang, box, raw = placed
            add_path(segs, raw, net, seen)
            maze.remember(net, raw)
            labels.append({"net": net, "x": gx, "y": gy, "ang": ang, "box": box})
            obstacles.append(box)
            fill_hot(box, 0.5)
            maze.fill_rect(box, reserved, grow=0.8)
            continue
        _score, goal, ang, box = best
        path = [goal]
        cur = goal
        while prev[cur] is not None:
            cur = prev[cur]
            path.append(cur)
        path.reverse()
        raw = maze.cells_to_segs(path)
        add_path(segs, raw, net, seen)
        maze.remember(net, raw)
        gx, gy = maze.xy(goal)
        labels.append({"net": net, "x": gx, "y": gy, "ang": ang, "box": box})
        obstacles.append(box)
        fill_hot(box, 0.5)
        maze.fill_rect(box, reserved, grow=0.8)
        for seg in raw:
            band = keepout(seg)
            obstacles.append(band)
            fill_hot(band, 0.2)

    fields = {}
    text_boxes = []
    seen_ref = set()
    for geom in geoms:
        ref_at, val_at = field_prefs(geom)
        if geom.unit != 1 and geom.part.ref in seen_ref:
            ref_xy, ref_box = ref_at, None
            hide_ref = True
        else:
            ref_xy, ref_box = nudge_text(ref_at[0], ref_at[1], geom.part.ref, obstacles)
            hide_ref = False
            seen_ref.add(geom.part.ref)
            obstacles.append(ref_box)
            text_boxes.append((f"{geom.part.ref}.ref", ref_box))
        if geom.unit != 1:
            val_xy, val_box = val_at, None
        else:
            val_xy, val_box = nudge_text(val_at[0], val_at[1], geom.part.value, obstacles)
            obstacles.append(val_box)
            text_boxes.append((f"{geom.part.ref}.val", val_box))
        fields[id(geom)] = (ref_xy, val_xy, hide_ref, geom.unit != 1)
    for lab in labels:
        text_boxes.append((lab["net"], lab["box"]))
    for pwr in powers:
        w, h = text_size(pwr["name"])
        text_boxes.append((pwr["name"], center_box(pwr["val"][0], pwr["val"][1], w, h)))
    return geoms, segs, labels, fields, powers, text_boxes, missing


def endpoint_at(seg, x, y) -> bool:
    return (abs(seg[0] - x) <= 0.06 and abs(seg[1] - y) <= 0.06) or (
        abs(seg[2] - x) <= 0.06 and abs(seg[3] - y) <= 0.06
    )


def check_sheet(key, geoms, segs, text_boxes) -> list[str]:
    errors = []
    for geom in geoms:
        for pin in geom.pins:
            if not any(seg[4] == pin.net and endpoint_at(seg, pin.x, pin.y) for seg in segs):
                errors.append(f"{key}: Pin {geom.part.ref}.{pin.sym} ({pin.net}) ohne Leitung")
    for seg in segs:
        x1, y1, x2, y2, net = seg
        for geom in geoms:
            if seg_hits_rect(x1, y1, x2, y2, geom.graphic):
                errors.append(f"{key}: Leitung {net} schneidet {geom.part.ref}")
            for pin in geom.pins:
                if net == pin.net or not point_on_seg(pin.x, pin.y, x1, y1, x2, y2):
                    continue
                errors.append(f"{key}: Leitung {net} trifft {geom.part.ref}.{pin.sym} ({pin.net})")
    for name, box in text_boxes:
        for seg in segs:
            if seg_hits_rect(*seg[:4], box):
                errors.append(f"{key}: Text {name} auf Leitung {seg[4]}")
                break
        for geom in geoms:
            if overlaps(box, geom.graphic, 0.0):
                errors.append(f"{key}: Text {name} auf {geom.part.ref}")
                break
        for geom in geoms:
            hit = False
            for pin in geom.pins:
                if overlaps(box, number_box(pin), 0.0):
                    errors.append(f"{key}: Text {name} auf Pinnummer {geom.part.ref}.{pin.sym}")
                    hit = True
                    break
            if hit:
                break
    for i, (name, box) in enumerate(text_boxes):
        for other, obox in text_boxes[i + 1 :]:
            if overlaps(box, obox, 0.3):
                errors.append(f"{key}: Text {name} über {other}")
    # gleiche Meldung nur einmal
    uniq = []
    for err in errors:
        if err not in uniq:
            uniq.append(err)
    return uniq


def extend_through_pins(segs, geoms) -> list[tuple]:
    """KiCad verbindet zuverlässiger, wenn der Pin auf der Strecke liegt, nicht am Ende."""
    pins = {(round(pin.x, 2), round(pin.y, 2)) for g in geoms for pin in g.pins}
    out = []
    for x1, y1, x2, y2, net in segs:
        x1, y1, x2, y2 = round(x1, 2), round(y1, 2), round(x2, 2), round(y2, 2)
        if (x1, y1) in pins:
            dx, dy = x2 - x1, y2 - y1
            if abs(dx) >= abs(dy) and abs(dx) > 0.02:
                x1 -= 2.54 if dx > 0 else -2.54
            elif abs(dy) > 0.02:
                y1 -= 2.54 if dy > 0 else -2.54
        if (x2, y2) in pins:
            dx, dy = x2 - x1, y2 - y1
            if abs(dx) >= abs(dy) and abs(dx) > 0.02:
                x2 += 2.54 if dx > 0 else -2.54
            elif abs(dy) > 0.02:
                y2 += 2.54 if dy > 0 else -2.54
        out.append((x1, y1, x2, y2, net))
    return out


def write_sheet(key, title, parts, outside, lib_text, pin_map, unit_map, boxed) -> list[str]:
    geoms, segs, labels, fields, powers, text_boxes, missing = layout_sheet(
        parts, pin_map, unit_map, boxed, outside,
    )
    errors = check_sheet(key, geoms, segs, text_boxes)
    for net in missing:
        errors.append(f"{key}: Label {net} fehlt")
    export_segs = merge_straight_joints(segs)
    errors.extend(assert_wires(key, geoms, export_segs, labels, powers))
    for err in errors[:24]:
        print(err)
    if len(errors) > 24:
        print(key, "weitere", len(errors) - 24)

    instances = []
    for geom in geoms:
        ref_xy, val_xy, hide_ref, hide_val = fields[id(geom)]
        instances.append(symbol_instance(
            geom.part.symbol, geom.x, geom.y, geom.rot, geom.part.ref,
            geom.part.value.replace('"', "'"),
            [n for n, *_ in geom.spec],
            ref_xy, val_xy, unit=geom.unit, hide_ref=hide_ref, hide_val=hide_val,
        ))
    pwr_n = 0
    for pwr in powers:
        pwr_n += 1
        instances.append(symbol_instance(
            pwr["lib"], pwr["x"], pwr["y"], pwr["rot"], f"#PWR{pwr_n:03d}", pwr["name"],
            ["1"], pwr["val"], pwr["val"], bom=False, hide_ref=True,
        ))
    wire_txt = [wire(x1, y1, x2, y2) for x1, y1, x2, y2, _net in export_segs]
    junc_pts = wire_junction_points(export_segs, geoms, powers)
    junc_txt = [junction(x, y) for x, y in sorted(junc_pts)]
    label_txt = [label(lab["net"], lab["x"], lab["y"], lab["ang"]) for lab in labels]

    xs = [g.graphic[0] for g in geoms] + [g.graphic[2] for g in geoms]
    ys = [g.graphic[1] for g in geoms] + [g.graphic[3] for g in geoms]
    for _name, box in text_boxes:
        xs.extend((box[0], box[2]))
        ys.extend((box[1], box[3]))
    for seg in export_segs:
        xs.extend((seg[0], seg[2]))
        ys.extend((seg[1], seg[3]))
    page_w = max(200.0, (max(xs) if xs else 40) + 36)
    page_h = max(150.0, (max(ys) if ys else 40) + 58)
    body = "\n".join([
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
        *lib_text.values(),
        "  )",
        *instances,
        *wire_txt,
        *junc_txt,
        *label_txt,
        ")",
    ])
    os.makedirs(SCH_DIR, exist_ok=True)
    sch = os.path.join(SCH_DIR, f"{key}.kicad_sch")
    with open(sch, "w", encoding="utf-8") as handle:
        handle.write(body + "\n")
    svg_dir = os.path.join(SCH_DIR, key)
    os.makedirs(svg_dir, exist_ok=True)
    kicad_env.run_kicad_cli("sch", "export", "svg", "-o", svg_dir + os.sep, sch)
    svgs = [os.path.join(svg_dir, name) for name in os.listdir(svg_dir) if name.endswith(".svg")]
    if not svgs:
        raise SystemExit(f"kein SVG für {key}")
    png = os.path.join(PREVIEW, f"schematic-{key}.png")
    if shutil.which("rsvg-convert"):
        subprocess.run(["rsvg-convert", "-w", "1800", "-o", png, svgs[0]], check=True)
    else:
        print("rsvg-convert fehlt: PNG nicht erneuert, SVG in", svg_dir)
    print("wrote", png, f"{page_w:.0f}x{page_h:.0f} mm,", len(parts), "parts", f"{len(errors)} Konflikte")
    return errors


def main():
    parts = [p for p in design.PARTS if p.group != "mech" and p.pins]
    by: dict[str, list[design.Part]] = {key: [] for key, _ in GROUPS}
    for part in parts:
        by.setdefault(part.group or "xiao", []).append(part)
    lib_text, pin_map, unit_map, boxed = load_symbols(parts)
    os.makedirs(PREVIEW, exist_ok=True)
    failed = []
    for key, title in GROUPS:
        group = by.get(key) or []
        if not group:
            continue
        outside = set()
        for part in parts:
            if part.group != key:
                outside.update(net for net in part.pins.values() if net)
        failed.extend(write_sheet(key, title, group, outside, lib_text, pin_map, unit_map, boxed))
    if failed:
        raise SystemExit(f"{len(failed)} Layout-Konflikte")


if __name__ == "__main__":
    main()
