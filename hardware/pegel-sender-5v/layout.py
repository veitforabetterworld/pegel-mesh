"""Platine neu erzeugen: Footprints, Regeln, GND-Fläche — ohne Leiterbahnen (Handrouting in KiCad oder manual_route.py)."""

from __future__ import annotations

import os
import subprocess
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(HERE, "pegel-sender-5v.kicad_pcb")


def main() -> None:
    sys.path.insert(0, HERE)
    import kicad_env  # noqa: E402
    import gen_pcb  # noqa: E402
    import route  # noqa: E402

    py = kicad_env.pcbnew_python()
    subprocess.run([py, os.path.join(HERE, "gen_pcb.py")], check=True)
    board = pcbnew.LoadBoard(PCB)
    route.prepare_manual_board(board)
    gen_pcb.layout_silk(board)
    pcbnew.SaveBoard(PCB, board)
    print("layout saved (unrouted):", PCB)


if __name__ == "__main__":
    main()