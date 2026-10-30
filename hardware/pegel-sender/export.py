"""Fertigungsdaten für PCBWay: Gerber + Bohrdaten (ZIP), Bestückungsliste (BOM) und Bestückungsdatei (CPL).

  python3 export.py
Ergebnis in fab/. Voraussetzung: kicad-cli (System oder AppImage in build/kicad-appimage/).
"""

import csv
import os
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


def main():
    os.makedirs(GERBER, exist_ok=True)
    kicad_env.run_kicad_cli(
        "pcb", "export", "gerbers",
        "--layers", "F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts",
        "--subtract-soldermask", "-o", GERBER + os.sep, PCB,
    )
    kicad_env.run_kicad_cli(
        "pcb", "export", "drill", "--format", "excellon", "--excellon-separate-th", "--generate-map",
        "--map-format", "gerberx2", "--drill-origin", "plot", "-o", GERBER + os.sep, PCB,
    )
    with zipfile.ZipFile(os.path.join(FAB, "pegel-sender-gerber.zip"), "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(os.listdir(GERBER)):
            z.write(os.path.join(GERBER, f), f)

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
            w.writerow([row["Ref"], f'{float(row["PosX"]):.3f}mm', f'{float(row["PosY"]):.3f}mm',
                        "Top" if row["Side"] == "top" else "Bottom", row["Rot"]])
    os.remove(pos)

    groups: "OrderedDict[tuple, list]" = OrderedDict()
    for p in design.PARTS:
        if p.dnp or not p.mpn:
            continue
        groups.setdefault((p.value, p.mpn, p.footprint.split(":")[1]), []).append(p.ref)
    with open(os.path.join(FAB, "pegel-sender-bom.csv"), "w", newline="", encoding="utf-8") as out:
        w = csv.writer(out)
        w.writerow(["Item", "Designator", "Qty", "Value", "Manufacturer Part Number", "Package"])
        for i, ((value, mpn, pkg), refs) in enumerate(groups.items(), 1):
            w.writerow([i, ",".join(refs), len(refs), value, mpn, pkg])
    print("fab data in", FAB)


if __name__ == "__main__":
    main()
