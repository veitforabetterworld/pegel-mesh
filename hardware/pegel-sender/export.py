"""Fertigungsdaten für JLCPCB: Gerber + Bohrdaten (ZIP), Stückliste (BOM) und Bestückungsdatei (CPL).

  python3 export.py
Ergebnis in fab/. Voraussetzung: kicad-cli (System oder AppImage in build/kicad-appimage/).
Gerber, Bohrdaten und CPL beziehen sich alle auf die linke untere Platinenecke (Hilfsursprung), sonst liegen
die Bauteile in der JLCPCB-Vorschau neben der Platine.
BOM und CPL enthalten nur die SMD-Teile mit LCSC-Nummer (Basic/Preferred). Die Durchsteckteile zum Selbstlöten
stehen in fab/pegel-sender-handbestueckung.csv.
"""

import csv
import os
import re
import sys
import zipfile
from collections import OrderedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import design  # noqa: E402
import kicad_env  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(HERE, "pegel-sender.kicad_pcb")
FAB = os.path.join(HERE, "fab")
GERBER = os.path.join(FAB, "gerber")

# JLCPCB zählt die Drehung mancher Gehäuse anders als KiCad (Pin 1 woanders). Korrektur in Grad, zur
# KiCad-Drehung addiert, erster Treffer gilt. Im JLCPCB-Bestückungsviewer an den hier verwendeten LCSC-Teilen
# geprüft (10/2026); SOT-23-5, SOD und SMA/SMB sowie TI PowerPAD (C9864) brauchen keine Korrektur.
ROTATION_FIX = [
    (r"^SOT-23-5", 0),
    (r"^SOT-23", 180),
    (r"^SOT-89", 180),
    (r"^SOIC-", 270),
]


def jlc_rotation(footprint: str, rot: float) -> float:
    for pattern, fix in ROTATION_FIX:
        if re.match(pattern, footprint):
            return (rot + fix) % 360
    return rot % 360


def main():
    os.makedirs(GERBER, exist_ok=True)
    kicad_env.run_kicad_cli(
        "pcb", "export", "gerbers",
        "--layers", "F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts",
        "--subtract-soldermask", "--use-drill-file-origin", "-o", GERBER + os.sep, PCB,
    )
    kicad_env.run_kicad_cli(
        "pcb", "export", "drill", "--format", "excellon", "--excellon-separate-th", "--generate-map",
        "--map-format", "gerberx2", "--drill-origin", "plot", "-o", GERBER + os.sep, PCB,
    )
    with zipfile.ZipFile(os.path.join(FAB, "pegel-sender-gerber.zip"), "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(os.listdir(GERBER)):
            z.write(os.path.join(GERBER, f), f)

    assembled = {p.ref: p for p in design.PARTS if p.lcsc and not p.hand and not p.dnp}
    pos = os.path.join(FAB, "pos-raw.csv")
    kicad_env.run_kicad_cli(
        "pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "both",
        "--exclude-dnp", "--use-drill-file-origin", "-o", pos, PCB,
    )
    with open(pos, newline="", encoding="utf-8") as f, \
            open(os.path.join(FAB, "pegel-sender-cpl.csv"), "w", newline="", encoding="utf-8") as out:
        w = csv.writer(out)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for row in csv.DictReader(f):
            if row["Ref"] not in assembled:
                continue
            rot = jlc_rotation(assembled[row["Ref"]].footprint.split(":")[1], float(row["Rot"]))
            w.writerow([row["Ref"], f'{float(row["PosX"]):.3f}mm', f'{float(row["PosY"]):.3f}mm',
                        "Top" if row["Side"] == "top" else "Bottom", f"{rot:g}"])
    os.remove(pos)

    groups: "OrderedDict[tuple, list]" = OrderedDict()
    for p in design.PARTS:
        if p.ref in assembled:
            groups.setdefault((p.value, p.footprint.split(":")[1], p.lcsc), []).append(p.ref)
    with open(os.path.join(FAB, "pegel-sender-bom.csv"), "w", newline="", encoding="utf-8") as out:
        w = csv.writer(out)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
        for (value, pkg, lcsc), refs in groups.items():
            w.writerow([value, ",".join(refs), pkg, lcsc])

    with open(os.path.join(FAB, "pegel-sender-handbestueckung.csv"), "w", newline="", encoding="utf-8") as out:
        w = csv.writer(out)
        w.writerow(["Designator", "Wert", "Teil", "Footprint"])
        for p in design.PARTS:
            if p.hand:
                w.writerow([p.ref, p.value, p.mpn, p.footprint.split(":")[1]])
    print("fab data in", FAB)


if __name__ == "__main__":
    main()
