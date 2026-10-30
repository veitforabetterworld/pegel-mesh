"""Schaltplan als KiCad-Blatt (Symbole, Leitungen, Labels). Aufruf: python3 export_schematic.py"""

import os
import runpy

HERE = os.path.dirname(os.path.abspath(__file__))

if __name__ == "__main__":
    runpy.run_path(os.path.join(HERE, "schematic_wired.py"), run_name="__main__")
