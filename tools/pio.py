"""Ruft PlatformIO im MeshCore-Submodul mit den pegel-mesh-Umgebungen auf.

    py tools/pio.py run -e pegel_sender_a
    py tools/pio.py run -e pegel_sender_a -t upload --upload-port COM5
    py tools/pio.py device monitor -b 115200 -p COM5
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MESHCORE = ROOT / "MeshCore"


def find_pio():
    found = shutil.which("pio")
    if found:
        return found
    venv_bin = Path.home() / ".pio-venv" / ("Scripts" if os.name == "nt" else "bin")
    found = shutil.which("pio", path=str(venv_bin))
    if found:
        return found
    sys.exit("PlatformIO nicht gefunden (pip install platformio)")


def main():
    if not (MESHCORE / "platformio.ini").exists():
        sys.exit("MeshCore-Submodul fehlt: git submodule update --init")
    shutil.copyfile(ROOT / "pegel.ini", MESHCORE / "platformio.local.ini")
    args = sys.argv[1:]
    if args and args[0] == "run":
        args = ["run", "-d", str(MESHCORE)] + args[1:]
    sys.exit(subprocess.call([find_pio()] + args))


if __name__ == "__main__":
    main()
