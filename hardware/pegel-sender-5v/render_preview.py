"""3D-Raytrace-Vorschau nach preview/ — inkl. XIAO/Wio-Modelle auf der Unterseite."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kicad_env  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(HERE, "pegel-sender-5v.kicad_pcb")
PREVIEW = os.path.join(HERE, "preview")

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
    render(["--side", "top", *COMMON], "pegel-sender-5v-top.png")
    render(["--side", "bottom", *COMMON], "pegel-sender-5v-bottom.png")
    # Schrägansicht: Unterseite mit XIAO-Stapel sichtbar
    render([
        "--side", "top",
        *COMMON,
        "--rotate", "-35,0,25",
        "--zoom", "1.15",
        "--pan", "0,-8,0",
    ], "pegel-sender-5v-iso.png")


if __name__ == "__main__":
    main()