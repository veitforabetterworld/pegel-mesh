"""Blockschaltplan als SVG/PNG nach preview/. Aufruf: python3 schematic_blocks.py"""

import os

from svg_png import svg_to_png

HERE = os.path.dirname(os.path.abspath(__file__))
PREVIEW = os.path.join(HERE, "preview")
SVG = os.path.join(PREVIEW, "pegel-sender-schematic-blocks.svg")
PNG = os.path.join(PREVIEW, "pegel-sender-schematic-blocks.png")

# name -> (x, y, w, h)
BOXES: dict[str, tuple[float, float, float, float]] = {}


def esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def box(name: str, x: float, y: float, w: float, h: float, title: str, lines: list[str]) -> str:
    BOXES[name] = (x, y, w, h)
    cx = x + w / 2
    parts = [
        f'<rect class="box" x="{x}" y="{y}" width="{w}" height="{h}"/>',
        f'<text class="title" x="{cx}" y="{y + 28}" text-anchor="middle">{esc(title)}</text>',
    ]
    for i, line in enumerate(lines):
        parts.append(
            f'<text class="sub" x="{cx}" y="{y + 50 + i * 18}" text-anchor="middle">{esc(line)}</text>'
        )
    return "\n".join(parts)


def pt(name: str, side: str, frac: float = 0.5) -> tuple[float, float]:
    x, y, w, h = BOXES[name]
    if side == "left":
        return x, y + h * frac
    if side == "right":
        return x + w, y + h * frac
    if side == "top":
        return x + w * frac, y
    if side == "bottom":
        return x + w * frac, y + h
    raise ValueError(side)


def arrow(a: tuple[float, float], b: tuple[float, float], via: list[tuple[float, float]] | None = None) -> str:
    pts = [a, *(via or []), b]
    d = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in pts)
    return f'<path class="arr" d="{d}"/>'


def build() -> str:
    parts = []
    parts.append(box("solar", 40, 68, 170, 168, "Eingang J1", ["Solar oder 12 V", "Steckbrücke JP2:", "Netzteil"]))
    parts.append(box("charger", 290, 68, 200, 168, "TPS5430", ["Lader 3,50 V, 2 A", "LM324 regelt Strom,", "Panel 17 V, Frost"]))
    parts.append(box("vsys", 570, 68, 160, 168, "VSYS", ["Akku 2,8–3,5 V", "nachts getrennt"]))
    parts.append(box("v33", 810, 48, 210, 88, "B5819W", ["Akku direkt", "zum XIAO"]))
    parts.append(box("v12", 810, 168, 210, 88, "TPS61040", ["12 V Sonde", "Schaltbar über D0"]))
    parts.append(box("xiao", 1100, 48, 230, 88, "XIAO nRF52840", ["Wio-SX1262", "misst Akku an VDD"]))
    parts.append(box("bat", 40, 360, 250, 110, "Akku J2", ["LiFePO4 1S", "Shunt im Minuspol"]))
    parts.append(box("frost", 360, 360, 270, 110, "Frost / Heizung J4", ["NTC und Heizwiderstand", "am Akku, aus VSOL"]))
    parts.append(box("rs485", 700, 360, 360, 110, "RS485 Sonde", ["SP3485, Richtung automatisch", "Klemme J3"]))

    parts.append(arrow(pt("solar", "right"), pt("charger", "left")))
    parts.append(arrow(pt("charger", "right"), pt("vsys", "left")))
    parts.append(arrow(pt("vsys", "right", 0.28), pt("v33", "left")))
    parts.append(arrow(pt("vsys", "right", 0.72), pt("v12", "left")))
    parts.append(arrow(pt("v33", "right"), pt("xiao", "left")))

    # VSYS nach unten zum Akku; Frost greift in den Lader ein
    vx, vy = pt("vsys", "bottom", 0.35)
    bx, by = pt("bat", "top", 0.72)
    parts.append(arrow((vx, vy), (bx, by), [(vx, 320), (bx, 320)]))
    fx, fy = pt("frost", "top", 0.35)
    cx, cy = pt("charger", "bottom", 0.5)
    parts.append(arrow((fx, fy), (cx, cy), [(fx, 300), (cx, 300)]))

    # Sonden-12 V zur RS485-Klemme
    sx, sy = pt("v12", "bottom")
    tx, ty = pt("rs485", "top", 0.7)
    parts.append(arrow((sx, sy), (tx, ty)))

    body = "\n".join(parts)
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1380" height="520" viewBox="0 0 1380 520">
  <style>
    .box {{ fill:#f7f7f7; stroke:#222; stroke-width:2; }}
    .title {{ font: 600 18px sans-serif; fill:#111; }}
    .sub {{ font: 14px sans-serif; fill:#333; }}
    .arr {{ stroke:#333; stroke-width:2; fill:none; marker-end:url(#m); }}
  </style>
  <defs>
    <marker id="m" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto">
      <path d="M0,0 L7,3 L0,6 z" fill="#333"/>
    </marker>
  </defs>
  <text x="690" y="28" text-anchor="middle" style="font:600 20px sans-serif;fill:#111">pegel-sender — Blockschaltplan</text>
  {body}
</svg>
'''


def main():
    os.makedirs(PREVIEW, exist_ok=True)
    with open(SVG, "w", encoding="utf-8") as f:
        f.write(build())
    svg_to_png(SVG, PNG)
    print("wrote", PNG)


if __name__ == "__main__":
    main()
