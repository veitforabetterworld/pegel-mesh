"""Prüft die Stapelplatine in PEGEL_BOARD, ohne sie zu verändern: DRC (Fehler, offene Verbindungen) und Abgleich der
.kicad_pcb mit design.py (Bauteile, Werte, Netze). Aufruf mit KiCad-Python, fab.py setzt PEGEL_BOARD.
"""

import json
import os
import subprocess
import sys
import tempfile

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kicad_env  # noqa: E402
from stack_board import NAME, PCB  # noqa: E402
import design  # noqa: E402  (aus dem Platinenordner)


def drc_errors() -> list[str]:
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "drc.json")
        subprocess.run(kicad_env.kicad_cli_argv("pcb", "drc", "--refill-zones", "--format", "json",
                                                "-o", out, PCB),
                       check=True, stdout=subprocess.DEVNULL)
        with open(out, encoding="utf-8") as f:
            report = json.load(f)

    def items(entry):
        return " <-> ".join(i.get("description", "") for i in entry.get("items", []))

    bad = [f"{v['description']} | {items(v)}" for v in report.get("violations") or [] if v.get("severity") == "error"]
    return bad + [f"offen: {items(u)}" for u in report.get("unconnected_items") or []]


def design_differences() -> list[str]:
    board = pcbnew.LoadBoard(PCB)
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    parts = {p.ref: p for p in design.PARTS}
    bad = [f"{ref}: auf der Platine, aber nicht in design.py" for ref in sorted(set(fps) - set(parts))]
    for ref, p in parts.items():
        fp = fps.get(ref)
        if fp is None:
            bad.append(f"{ref}: fehlt auf der Platine")
            continue
        if fp.GetValue() != p.value:
            bad.append(f"{ref}: Wert {fp.GetValue()} statt {p.value}")
        for num, net in p.pins.items():
            if not net:
                continue
            pads = [pad for pad in fp.Pads() if pad.GetNumber() == num]
            if not pads or any(pad.GetNetname() != net for pad in pads):
                bad.append(f"{ref}.{num}: nicht an {net}")
    return bad


def main():
    bad = drc_errors() + design_differences()
    for line in bad:
        print("  " + line)
    if bad:
        raise SystemExit(f"{NAME}: {len(bad)} Fehler")
    print(f"{NAME}: DRC und Netzliste ohne Fehler")


if __name__ == "__main__":
    main()
