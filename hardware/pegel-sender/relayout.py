"""Platine end-to-end neu erzeugen nach Änderungen an design.py oder fixed_positions.py.

Ablauf: gen_pcb → Freerouting → DRC/Repair → Siebdruck → Gerber/BOM/CPL → 3D-Vorschau.

Positionen: fixed_positions.py (KiCad-Python dump_fixed.py aus gerouteter Platine).

Aufruf (im Verzeichnis hardware/pegel-sender/):
  python3 relayout.py
  python3 relayout.py /pfad/freerouting.jar

Freerouting-JAR: Umgebungsvariable FREEROUTING_JAR oder build/freerouting.jar.
Java: JAVA oder java im PATH.

Nicht auf einer bereits gerouteten Platine nur Footprints verschieben — das öffnet
Dutzende Netze; repair_opens ersetzt keinen Autorouter. FIXED-Positionen in gen_pcb.py
anpassen, dann dieses Skript.

Nur Siebdruck auf bestehender, gültiger Platine (ohne Neu-Route):
  KiCad-Python -c \"import pcbnew, gen_pcb; b=pcbnew.LoadBoard('pegel-sender.kicad_pcb'); gen_pcb.layout_silk(b); pcbnew.SaveBoard('pegel-sender.kicad_pcb', b)\"
  python3 render_preview.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

DEFAULT_JAR = os.path.join(HERE, "build", "freerouting.jar")
ROUTE = os.path.join(HERE, "route.py")
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
    jar = find_jar(sys.argv[1] if len(sys.argv) > 1 else None)
    java = java_cmd()

    import kicad_env  # noqa: E402

    py = kicad_env.pcbnew_python()
    print("=== route (gen_pcb + freerouting + silk) ===", flush=True)
    subprocess.run([py, ROUTE, jar, java], cwd=HERE, check=True)

    print("=== export fab ===", flush=True)
    subprocess.run([sys.executable, EXPORT], cwd=HERE, check=True)

    print("=== 3D preview ===", flush=True)
    subprocess.run([sys.executable, RENDER], cwd=HERE, check=True)

    print("done:", os.path.join(HERE, "pegel-sender.kicad_pcb"))


if __name__ == "__main__":
    main()
