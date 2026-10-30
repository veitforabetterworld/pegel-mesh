"""KiCad-Symbolbibliothek für den Schaltplan: Symbole finden, einbetten, Pins lesen, Kastensymbole bauen."""

import math
import os
import re
import uuid

import design
import kicad_env

GRID = 1.27


def uid() -> str:
    return str(uuid.uuid4())


def snap(v: float) -> float:
    return round(v / GRID) * GRID


def fmt(v: float) -> str:
    return f"{v:.2f}"


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


def extract_symbol(path: str, name: str, lib_id: str) -> str:
    text = open(path, encoding="utf-8").read()
    key = f'(symbol "{name}"'
    i = text.find(key)
    if i < 0:
        raise SystemExit(f"symbol {name} not in {path}")
    return sexp_from(text, i).replace(key, f'(symbol "{lib_id}"', 1)


def parse_pins(symbol_text: str) -> list[tuple[str, float, float, float]]:
    """(Nummer, x, y, Winkel) je Pin, Symbolkoordinaten (Y nach oben)."""
    pins = []
    idx = 0
    while True:
        i = symbol_text.find("(pin ", idx)
        if i < 0:
            break
        block = sexp_from(symbol_text, i)
        idx = i + len(block)
        at = re.search(r"\(at\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\)", block)
        num = re.search(r'\(number\s+"([^"]+)"', block)
        if at and num:
            pins.append((num.group(1), float(at.group(1)), float(at.group(2)), float(at.group(3))))
    return pins


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
        found = parse_pins(block)
        if unit and found:
            units.setdefault(unit, []).extend(found)
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
    parent_body = extract_symbol(parent_path, parent, lib_id)
    flat = parent_body.replace(f"{parent}_", f"{name}_")
    val = re.search(r'\(property "Value" "([^"]+)"', body)
    if val:
        flat = re.sub(r'\(property "Value" "[^"]+"', lambda m: f'(property "Value" "{val.group(1)}"', flat, count=1)
    return flat


def lib_field(symbol_text: str, name: str) -> tuple[float, float, str] | None:
    """Lage eines Feldes im Symbol (x, y, Ausrichtung), nur waagrechte Felder."""
    i = symbol_text.find(f'(property "{name}"')
    if i < 0:
        return None
    block = sexp_from(symbol_text, i)
    at = re.search(r"\(at\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\)", block)
    if not at or float(at.group(3)) % 180:
        return None
    just = re.search(r"\(justify\s+(left|right)", block)
    return float(at.group(1)), float(at.group(2)), just.group(1) if just else "center"


def world(ix, iy, irot, px, py):
    """Symbolpunkt aufs Blatt (90°-Schritte gegen den Uhrzeigersinn; Symbol-Y hoch, Blatt-Y runter)."""
    r = int(irot) % 360
    rx, ry = {0: (px, py), 90: (-py, px), 180: (-px, -py), 270: (py, -px)}[r]
    return ix + rx, iy - ry


def outward(irot, pang) -> tuple[int, int]:
    """Richtung, in der die Leitung den Pin verlässt (Blattkoordinaten)."""
    a = math.radians((pang + irot) % 360)
    return round(-math.cos(a)), round(math.sin(a))


def symbol_pin_of(part: design.Part, pad: str) -> str:
    """Footprint-Pad auf die Pinnummer des Schaltplansymbols. MOSFETs heißen G/D/S, nicht 1/2/3."""
    if part.symbol not in ("Device:Q_NMOS", "Device:Q_PMOS"):
        return pad
    table = {"1": "G", "2": "D", "3": "S"} if "TO-252" in part.footprint else {"1": "G", "2": "S", "3": "D"}
    return table.get(pad, pad)


# Kastensymbole für Bauteile ohne KiCad-Symbol: Pinname je Nummer, links und rechts von oben nach unten.
BOX_PINS = {
    "CN3795": ({"9": "VCC", "1": "VG", "4": "MPPT", "5": "COM", "2": "GND"},
               {"10": "DRV", "8": "CSP", "7": "BAT", "6": "FB", "3": "CHRG"}),
    "HY2112": ({"5": "VDD", "6": "VSS", "4": "NC"}, {"1": "OD", "3": "OC", "2": "CS"}),
    "FS8205A": ({"2": "S1", "3": "S1", "4": "G1"}, {"7": "S2", "6": "S2", "5": "G2", "1": "D", "8": "D"}),
    "TLV3401": ({"3": "IN+", "4": "IN-", "5": "V+", "2": "V-"}, {"1": "OUT"}),
    "LM66100": ({"1": "VIN", "3": "CE", "5": "ST"}, {"6": "VOUT", "2": "GND", "4": "NC"}),
}


def box_symbol(lib_id: str, numbers: list[str]) -> tuple[str, list[tuple[str, float, float, float]]]:
    name = lib_id.split(":")[-1]
    if name in BOX_PINS:
        left, right = BOX_PINS[name]
    else:
        nums = sorted(set(numbers), key=lambda n: (len(n), n))
        left = {n: n for n in nums[::2]}
        right = {n: n for n in nums[1::2]}
    rows = max(len(left), len(right), 1)
    longest = max([len(v) for v in list(left.values()) + list(right.values())] + [2])
    hw = snap(max(5.08, longest * 1.27 + 1.27))
    top = snap((rows - 1) * 2.54 / 2)
    pins = []
    for side, x, ang in ((left, -hw - 2.54, 0), (right, hw + 2.54, 180)):
        for i, num in enumerate(side):
            pins.append((num, x, top - i * 2.54, ang, side[num]))
    h = top + 2.54
    pin_txt = "\n".join(
        f'      (pin passive line (at {x} {y} {ang}) (length 2.54)'
        f' (name "{nm}" (effects (font (size 1.27 1.27)))) (number "{n}" (effects (font (size 1.27 1.27)))))'
        for n, x, y, ang, nm in pins
    )
    text = f'''    (symbol "{lib_id}"
      (pin_names (offset 0.508))
      (exclude_from_sim no) (in_bom yes) (on_board yes)
      (property "Reference" "U" (at {-hw} {h + 1.27} 0) (effects (font (size 1.27 1.27)) (justify left)))
      (property "Value" "{name}" (at {-hw} {-h - 1.27} 0) (effects (font (size 1.27 1.27)) (justify left)))
      (symbol "{name}_0_1"
        (rectangle (start {-hw} {h}) (end {hw} {-h})
          (stroke (width 0.254) (type default)) (fill (type background))))
      (symbol "{name}_1_1"
{pin_txt}
      )
    )'''
    return text, [(n, x, y, ang) for n, x, y, ang, _nm in pins]


def load_symbol(lib_id: str, numbers: list[str]) -> tuple[str, dict[int, list], bool]:
    """Eingebetteter Symboltext, Pins je Einheit, Kastensymbol ja/nein."""
    lib, name = lib_id.split(":", 1)
    path = None if lib == "pegel" else find_lib_file(lib, name)
    if not path:
        text, pins = box_symbol(lib_id, numbers)
        return text, {1: pins}, True
    body = flatten_extends(extract_symbol(path, name, lib_id), lib, name, lib_id)
    return body, parse_units(body, name), False
