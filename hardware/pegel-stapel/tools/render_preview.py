"""3D-Raytrace-Vorschau der Stapelplatine in PEGEL_BOARD nach <Platinenordner>/preview/."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kicad_env  # noqa: E402

from stack_board import BOARD_DIR, NAME, PCB, cfg  # noqa: E402

PREVIEW = os.path.join(BOARD_DIR, "preview")

COMMON = [
    "--quality", "high",
    "--width", "2400",
    "--height", "1600",
    "--floor",
    "--perspective",
    "--use-board-stackup-colors",
]


def render(args: list[str], out_name: str) -> None:
    out = os.path.join(PREVIEW, out_name)
    kicad_env.run_kicad_cli("pcb", "render", *args, "-o", out, PCB)
    print("wrote", out)


def main() -> None:
    os.makedirs(PREVIEW, exist_ok=True)
    # kleine Platinen füllen sonst das Bild über den Rand
    zoom = ["--zoom", "0.8"] if min(cfg.W, cfg.H) < 25 else []
    render(["--side", "top", *COMMON, *zoom], NAME + "-top.png")
    render(["--side", "bottom", *COMMON, *zoom], NAME + "-bottom.png")
    # Schrägansicht
    render([
        "--side", "top",
        *COMMON,
        "--rotate", "-35,0,25",
        "--zoom", "0.7" if min(cfg.W, cfg.H) < 25 else "0.9",
    ], NAME + "-iso.png")


if __name__ == "__main__":
    main()