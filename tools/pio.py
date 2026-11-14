"""Ruft PlatformIO im passenden MeshCore-Submodul mit den pegel-mesh-Umgebungen auf.

    py tools/pio.py run -e pegel_sender_a
    py tools/pio.py run -e pegel_sender_a -t upload --upload-port COM5
    py tools/pio.py run -e tracker_t1 -t upload
    py tools/pio.py device monitor -b 115200 -p COM5

Umgebungen tracker_* (XIAO nRF54LM20A) laufen in MeshCore-nrf54 (MeshCore mit nRF54-Unterstützung aus
PR #3530) mit tracker.ini, alle anderen in MeshCore mit pegel.ini.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def find_pio():
    found = shutil.which("pio")
    if found:
        return found
    venv_bin = Path.home() / ".pio-venv" / ("Scripts" if os.name == "nt" else "bin")
    found = shutil.which("pio", path=str(venv_bin))
    if found:
        return found
    sys.exit("PlatformIO nicht gefunden (pip install platformio)")


def env_names(args):
    names = []
    for i, a in enumerate(args):
        if a in ("-e", "--environment") and i + 1 < len(args):
            names.append(args[i + 1])
        elif a.startswith("--environment="):
            names.append(a.split("=", 1)[1])
    return names


def main():
    args = sys.argv[1:]
    envs = env_names(args)
    tracker = bool(envs) and all(e.startswith("tracker") for e in envs)
    if envs and not tracker and any(e.startswith("tracker") for e in envs):
        sys.exit("tracker_* und andere Umgebungen bitte getrennt bauen (verschiedene MeshCore-Stände)")
    meshcore = ROOT / ("MeshCore-nrf54" if tracker else "MeshCore")
    ini = ROOT / ("tracker.ini" if tracker else "pegel.ini")
    if not (meshcore / "platformio.ini").exists():
        sys.exit(f"Submodul {meshcore.name} fehlt: git submodule update --init")
    shutil.copyfile(ini, meshcore / "platformio.local.ini")
    if args and args[0] == "run":
        args = ["run", "-d", str(meshcore)] + args[1:]
    sys.exit(subprocess.call([find_pio()] + args))


if __name__ == "__main__":
    main()
