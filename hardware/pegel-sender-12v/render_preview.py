"""3D-Raytrace-Vorschau (oben/unten) nach preview/. Aufruf: python3 render_preview.py"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kicad_env  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(HERE, "pegel-sender-12v.kicad_pcb")
PREVIEW = os.path.join(HERE, "preview")


def render(side: str, out_name: str) -> None:
    out = os.path.join(PREVIEW, out_name)
    kicad_env.run_kicad_cli(
        "pcb", "render", "--side", side, "--quality", "high",
        "--width", "2400", "--height", "1600", "-o", out, PCB,
    )
    print("wrote", out)


def main() -> None:
    os.makedirs(PREVIEW, exist_ok=True)
    render("top", "pegel-sender-12v-top.png")
    render("bottom", "pegel-sender-12v-bottom.png")


if __name__ == "__main__":
    main()
