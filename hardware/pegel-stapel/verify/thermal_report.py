"""Bericht und Bilder aus report/thermal.json und build/thermal_plots.npy (beides schreibt thermal.py).

    python thermal_report.py
"""

import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

import thermal_model as tm  # noqa: E402

REPORT = os.path.join(tm.HERE, "report")
NTC = "Akku oben, neben der Platine"
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
HEAT = LinearSegmentedColormap.from_list("heat", ["#fff4ec", "#f8c3a4", "#eb6834", "#a33a12", "#4a1605"])
plt.rcParams.update({
    "font.family": "Segoe UI", "font.size": 10, "text.color": INK, "axes.labelcolor": INK2,
    "xtick.color": INK2, "ytick.color": INK2, "axes.edgecolor": GRID, "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE, "axes.titlelocation": "left",
})


def de(v, digits=0):
    return "–" if v is None else f"{v:.{digits}f}".replace(".", ",").replace("-", "−")


def lines_figure(lines):
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.0))
    title = {-15: "Kaltstart bei −15 °C (grau: Heizung an)", 37: "Laden bei 37 °C (grau: Hitzeabschaltung)"}
    for ax, (ta, d) in zip(axes, lines.items()):
        ax.set_title(title[ta], fontsize=11, color=INK)
        low, high = (-20, 60) if ta < 0 else (35, 50)
        ax.fill_between(d["t"], low, high, where=d["on" if ta < 0 else "cut"], color="#efeeea", linewidth=0,
                        step="post")
        for key, color in (("film", ORANGE), ("cell", BLUE), ("ntc", AQUA)):
            ax.plot(d["t"], d[key], color=color, linewidth=2,
                    label={"film": "heißester Widerstand", "cell": "heißeste Stelle im Akku", "ntc": "NTC"}[key])
        ax.axhline(0 if ta < 0 else 45, color=INK2, linewidth=0.6)
        if ta > 0:
            ax.text(2, 45.2, "Ladegrenze 45 °C", color=INK2)
        ax.set_xlim(0, d["t"][-1])
        ax.set_ylim(low, high)
        ax.set_xlabel("Minuten seit 5 V anliegen")
        ax.set_ylabel("°C")
        ax.grid(axis="y", color=GRID, linewidth=0.8)
        ax.spines[["top", "right"]].set_visible(False)
    h, lab = axes[0].get_legend_handles_labels()
    fig.legend(h, lab, loc="lower center", ncol=3, frameon=False)
    fig.suptitle("5 × 300 Ω und Hitzeabschaltung, NTC am Akku neben der Platine", x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0.07, 1, 0.95))
    fig.savefig(os.path.join(REPORT, "thermal-betrieb.png"), dpi=110)
    plt.close(fig)


def map_figure(s):
    fig = plt.figure(figsize=(13, 7.2))
    grid = fig.add_gridspec(2, 3, height_ratios=(1.15, 1), width_ratios=(1, 1, 0.04))
    top = float(s["board"].max())
    x, y, z = s["x"], s["y"], s["z"]
    panels = (
        (grid[0, 0], s["board"], x, y, "Platine oben", (0, tm.W), (tm.H, 0), (0, 0, tm.W, tm.H)),
        (grid[0, 1], s["cell"], x, y, "Akku oben (Umriss: Platine)", (-9.27, 30.23), (24.64, -6.86),
         (0, 0, tm.W, tm.H)),
        (grid[1, :2], s["cut"], x, z, "Schnitt durch die Heizreihe: Styropor, Akku, Platine, XIAO, Wio",
         (x[0], x[-1]), (z[0], z[-1]), (0, 0, tm.W, 1.6)),
    )
    for cell, data, a, b, title, xl, yl, (rx, ry, rw, rh) in panels:
        ax = fig.add_subplot(cell)
        im = ax.pcolormesh(a, b, data.T, cmap=HEAT, vmin=0, vmax=top, shading="flat", rasterized=True)
        ax.add_patch(Rectangle((rx, ry), rw, rh, fill=False, edgecolor=INK2, linewidth=0.8))
        ax.set_xlim(*xl)
        ax.set_ylim(*yl)
        ax.set_aspect("equal")
        ax.set_title(title, fontsize=11)
        ax.set_xlabel("mm")
        vis = data[np.ix_((a[:-1] >= xl[0]) & (a[1:] <= xl[1]), (b[:-1] >= min(yl)) & (b[1:] <= max(yl)))]
        ax.text(0.02, 0.04, f"max +{vis.max():.0f} K", transform=ax.transAxes, color=INK,
                bbox=dict(facecolor=SURFACE, edgecolor="none", alpha=0.85))
    fig.colorbar(im, cax=fig.add_subplot(grid[:, 2]), label="K über Außenluft")
    fig.suptitle("Fehlerfall Dauerheizen (NTC ab), 5 × 300 Ω: Übertemperatur, linearisiert", x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(os.path.join(REPORT, "thermal-karte.png"), dpi=110)
    plt.close(fig)


def table(head, rows):
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    return "\n".join(out + ["| " + " | ".join(str(c) for c in row) + " |" for row in rows])


def report(r):
    case = lambda bond, opt, ta, ntc=NTC: next(
        c for c in r["cases"] if (c["bond"], c["option"], c["ta"], c["ntc"]) == (bond, opt, ta, ntc))
    fault = lambda opt, ta: next(f[2] for f in r["faults"] if f[0] == opt and f[1] == ta)
    detail = {d["option"]: d for d in r["details"]}
    options = list(detail)
    th = r["thresholds"]
    d = detail[options[0]]
    base = dict(r["sensitivity"])["Basis"]["cell"]
    rel = [v["cell"] / base - 1 for _, v in r["sensitivity"]]
    rise = fault(options[0], 35)["cell"] - 35
    span = [35 + rise * (1 + f) for f in (min(rel), max(rel))]
    cell20, cell35 = (fault(options[0], ta)["cell"] for ta in (20, 35))
    limit = 20 + (60 - cell20) * 15 / (cell35 - cell20)
    limit_low = 60 - (60 - limit) * (1 + max(rel))
    names = ("Heizung an, Laden aus unter", "Heizung aus, Laden ab", "Hitze: Laden aus über",
             "Hitze: Laden wieder unter")
    levels = [[n, de(v, 1) + " °C", f"{de(lo, 1)} bis {de(hi, 1)} °C"]
              for n, v, (lo, hi) in zip(names, th["nominal"], th["band"])]

    operation = []
    for ta in (-10, -15, -20):
        c = d[f"op{ta}"]
        operation.append([de(ta) + " °C", de(c["film"]) + " °C", de(c["board"]) + " °C", de(c["u1"]) + " °C",
                          de(c["cell"], 1) + " °C",
                          "lädt nie" if c["first_off_min"] is None else de(c["first_off_min"]) + " min"])
    faults = []
    for opt in options:
        mins = lambda t: "nie" if t is None else de(t) + " min"
        faults.append([opt, *(de(fault(opt, ta)["cell"]) + " °C" for ta in (-20, 20, 35)),
                       de(fault(opt, 20)["film"]) + " °C", mins(d["min_to_60_from_20"]),
                       mins(d["min_to_60_from_35"])])
    places = []
    for ntc in dict.fromkeys(c["ntc"] for c in r["cases"]):
        c = case("Klebeband", options[0], -10, ntc)
        places.append([ntc, de(c["film"]) + " °C", de(c["cell"], 1) + " °C",
                       de(c["cell_min_charge"], 1) + " °C"])
    bonds = []
    for bond in r["steady"]:
        c = case(bond, options[0], -10)
        bonds.append([bond, de(c["film"]) + " °C", de(c["board"]) + " °C", de(c["cell"], 1) + " °C"])
    sens = [[name, "+" + de(v["cell"], 1) + " K", de((v["cell"] / base - 1) * 100, 1) + " %",
             "+" + de(v["film"]) + " K"] for name, v in r["sensitivity"]]
    charge = []
    for ta in dict.fromkeys(c["ta"] for c in d["hot"]):
        c = next(c for c in d["hot"] if c["ta"] == ta and c["ntc"] == NTC)
        charge.append([f"{ta} °C", de(ta + r["steady"]["Klebeband"]["charge"]["cell"], 1) + " °C",
                       "–" if c["cell_max_charge"] is None else de(c["cell_max_charge"], 1) + " °C",
                       de(c["charge_share"] * 100) + " %"])
    val = [[k, de(a, 3), de(b, 3), de((a / b - 1) * 100, 2) + " %"] for k, (a, b) in r["validation"].items()]

    text = f"""# Erwärmung der 5-V-Ladeplatine

Erzeugt von `thermal.py` und `thermal_report.py`. Rechnung, keine Messung. 3D-Finite-Volumen mit 1,5 Mio. Zellen, Kupfer samt GND-Flächen, Vias und Bauteile aus der `.kicad_pcb`.

**Aufbau:** Ladeplatine + XIAO + Wio-SX1262 ohne RS485-Platine, Pouchzelle 700 mAh (39,5 × 31,5 × 5,9 mm, 15 g) mit 1,2 mm Schaumklebeband darunter, rechteckiger Hohlraum, rundum 30 mm Styropor, zwei 5-V-Adern AWG 24 nach außen, 5,0 V am Eingang, keine Sonne. Die Zelle ist größer als der XIAO und steht über.

**Bestückung:** {options[0]}, {de(d["power"], 2)} W, fünf Widerstände links in der Heizreihe. Rechts die Hitzeabschaltung.

## Schwellen aus `design.py`

{table(["Schwelle", "Nennwert", "ungünstigste Toleranzen"], levels)}

Toleranzen: R 1 %, NTC 1 %, B 1 %, 5 mV Offset, 0–250 nA Eingangsstrom, 0,02–0,2 V Sättigung, 4,5–5,25 V.

## Normalbetrieb im Frost, NTC am Akku neben der Platine

{table(["Außenluft", "Widerstand", "Platine", "LM393", "Akku max.", "bis Laden"], operation)}

Die Heizung reicht bei 5 V bis {de(d["hold_to"], 1)} °C Außenluft.

![Kaltstart](thermal-betrieb.png)

## Fehlerfall NTC ab oder gebrochen: Dauerheizen

Strahlung und Leitwerte temperaturabhängig. Grenze des Akkus laut Datenblatt: 60 °C. Unsicherheit der Übertemperatur {de(min(rel) * 100)}/+{de(max(rel) * 100)} % (Empfindlichkeit unten): bei {options[0]} und 35 °C Außenluft also {de(span[0])} bis {de(span[1])} °C.

{table(["Bestückung", "Akku bei −20 °C", "bei 20 °C", "bei 35 °C", "Widerstand bei 20 °C", "60 °C im Akku ab 20 °C nach", "ab 35 °C nach"], faults)}

Im Dauerheizen erreicht der Akku 60 °C ab {de(limit)} °C Außenluft, im ungünstigsten Fall ab {de(limit_low)} °C. Die Hitzeabschaltung hilft dagegen nicht: sie hängt am selben NTC und schaltet nur das Laden.

![Karte](thermal-karte.png)

## Lage des NTC (−10 °C)

{table(["NTC", "Widerstand", "Akku max.", "kälteste Stelle im Akku beim Laden"], places)}

## Verklebung (−10 °C)

{table(["Spalt 1,2 mm", "Widerstand", "Platine", "Akku max."], bonds)}

Der 1206 hat {de(d["p_film"], 3)} W. Nach der üblichen Lastminderung (0,25 W bis 70 °C, 0 W bei 155 °C) darf er das bis {de(155 - 85 * d["p_film"] / 0.25)} °C.

## Laden bei Wärme (100 mA, Linearlader im XIAO, NTC neben der Platine)

{table(["Außenluft", "Akku ohne Abschaltung", "Akku beim Laden, mit Abschaltung", "lädt in der Zeit"], charge)}

Ladegrenze des Akkus: 45 °C.

## Empfindlichkeit (Dauerheizen mit {de(d["power"], 2)} W, linear, über Außenluft)

{table(["Änderung", "Akku max.", "gegen Basis", "Widerstand"], sens)}

## Prüfung des Lösers

{table(["Fall", "Modell", "Soll", "Abweichung"], val)}

Energiebilanz der Dauerzustände je Verklebung: Wärme nach außen = eingespeiste Leistung auf 10⁻⁵.

## Grenzen

Keine Konvektionsströmung in den Hohlräumen (wirksamer Leitwert), XIAO und Wio als Blöcke, kein Wärmewiderstand an Steckkontakten, keine Fugen im Styropor, keine Eigenerwärmung des NTC, Panel liefert immer 5 V. Bei 4,5 V sinkt die Heizleistung auf 81 %. Die Zellwerte für die Wärmeleitung stammen von einer LFP-Pouchzelle.
"""
    with open(os.path.join(REPORT, "thermal.md"), "w", encoding="utf-8") as f:
        f.write(text)
    return text


if __name__ == "__main__":
    with open(os.path.join(REPORT, "thermal.json"), encoding="utf-8") as f:
        r = json.load(f)
    plots = np.load(os.path.join(tm.STAPEL, "build", "thermal_plots.npy"), allow_pickle=True)[0]
    lines_figure(plots["lines"])
    map_figure(plots["slices"])
    print(report(r))
