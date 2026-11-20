"""Platine neu erzeugen: standardmäßig Handrouting (ohne Freerouting).

  python3 relayout.py                    → layout (unrouted) + export + preview
  python3 relayout.py --manual-tracks      → layout + feste Bahnen aus manual_route.py
  python3 relayout.py --auto-route [jar]   → Freerouting (veraltet)

Positionen: fixed_positions.py (dump_fixed.py aus KiCad-Platzierung).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

DEFAULT_JAR = os.path.join(HERE, "build", "freerouting.jar")
ROUTE = os.path.join(HERE, "route.py")
LAYOUT = os.path.join(HERE, "layout.py")
MANUAL = os.path.join(HERE, "manual_route.py")
EXPORT = os.path.join(HERE, "export.py")
RENDER = os.path.join(HERE, "render_preview.py")


def find_jar(cli_arg: str | None) -> str:
    if cli_arg:
        if not os.path.isfile(cli_arg):
            raise SystemExit(f"freerouting.jar not found: {cli_arg}")
        return os.path.abspath(cli_arg)
    env = os.environ.get("FREEROUTING_JAR")
    if env and os.path.isfile(env):
        return os.path.abspath(env)
    if os.path.isfile(DEFAULT_JAR):
        return DEFAULT_JAR
    raise SystemExit(
        "freerouting.jar missing: pass path, set FREEROUTING_JAR, or put JAR in build/freerouting.jar"
    )


def java_cmd() -> str:
    return os.environ.get("JAVA") or shutil.which("java") or "java"


def main() -> None:
    import kicad_env  # noqa: E402

    py = kicad_env.pcbnew_python()
    auto = "--auto-route" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--auto-route"]

    if auto:
        jar = find_jar(args[0] if args else None)
        java = java_cmd()
        print("=== auto-route (Freerouting) ===", flush=True)
        subprocess.run([py, ROUTE, jar, java], cwd=HERE, check=True)
    else:
        manual = "--manual-tracks" in sys.argv
        if manual:
            print("=== manual_route (MANUAL_TRACKS in manual_route.py) ===", flush=True)
            subprocess.run([py, MANUAL], cwd=HERE, check=True)
        else:
            print("=== layout (nur Footprints + GND-Fläche, offen für KiCad) ===", flush=True)
            subprocess.run([py, LAYOUT], cwd=HERE, check=True)

    print("=== export fab ===", flush=True)
    subprocess.run([sys.executable, EXPORT], cwd=HERE, check=True)

    print("=== 3D preview ===", flush=True)
    subprocess.run([sys.executable, RENDER], cwd=HERE, check=True)

    print("done:", os.path.join(HERE, "pegel-sender-5v.kicad_pcb"))


if __name__ == "__main__":
    main()