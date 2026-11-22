"""Lädt die Platine, die die Werkzeuge gerade bearbeiten: Ordner aus PEGEL_BOARD (fab.py setzt ihn).

Im Platinenordner liegen design.py (Netzliste) und board.py (Name, Größe).
"""

import os
import sys

BOARD_DIR = os.path.abspath(os.environ.get("PEGEL_BOARD", ""))
if not os.path.isfile(os.path.join(BOARD_DIR, "board.py")):
    raise SystemExit("PEGEL_BOARD zeigt auf keinen Platinenordner (board.py fehlt): " + BOARD_DIR)
sys.path.insert(0, BOARD_DIR)

import board as cfg  # noqa: E402

NAME = cfg.NAME
PCB = os.path.join(BOARD_DIR, NAME + ".kicad_pcb")
