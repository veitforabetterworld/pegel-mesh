"""Stapelplatinen prüfen und Fertigungsdaten schreiben. Platziert und routet nichts, die .kicad_pcb sind die Originale
und werden von Hand in KiCad bearbeitet.

  python3 tools/fab.py                    alle: prüfen, fab/ und preview/ schreiben
  python3 tools/fab.py lader-5v           nur diese
  python3 tools/fab.py --check [Platine]  nur prüfen, nichts schreiben
"""

from __future__ import annotations

import os
import subprocess
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
BOARDS = ["rs485", "lader-5v", "lader-12v", "lader-12v-netz", "lader-12v-solar"]

sys.path.insert(0, TOOLS)
import kicad_env  # noqa: E402


def main() -> None:
    args = sys.argv[1:]
    check_only = "--check" in args
    boards = [a for a in args if a != "--check"] or BOARDS
    unknown = set(boards) - set(BOARDS)
    if unknown:
        raise SystemExit(f"unbekannt: {' '.join(sorted(unknown))} (möglich: {' '.join(BOARDS)})")
    py = kicad_env.pcbnew_python()
    failed = []
    for name in boards:
        env = dict(os.environ, PEGEL_BOARD=os.path.join(ROOT, name))
        print(f"=== {name} ===", flush=True)
        if subprocess.run([py, os.path.join(TOOLS, "check.py")], env=env).returncode:
            failed.append(name)    # fehlerhafte Platine: keine Fertigungsdaten
            continue
        if not check_only:
            subprocess.run([sys.executable, os.path.join(TOOLS, "export.py")], env=env, check=True)
            subprocess.run([sys.executable, os.path.join(TOOLS, "render_preview.py")], env=env, check=True)
    if failed:
        raise SystemExit("Fehler in: " + " ".join(failed))


if __name__ == "__main__":
    main()
