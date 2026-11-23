"""Erwärmung der 12-V-Thermolader: das Modell des 5-V-Laders (thermal_model.py) auf die längere Platine übertragen.

    python thermal12.py <netz|solar> <.kicad_pcb> [weitere <name> <.kicad_pcb> ...]   Ergebnis: report/thermal-12v.json

Unterschiede zum 5-V-Lader:
- Platine W12 lang. XIAO und Wio sitzen nur über dem Teil, der dem 5-V-Lader entspricht (rechts).
- Heizung aus V5 des Wandlers (4,88 bzw. 4,92 V), ohne Q1 im Pfad. Heizwiderstände sind R19–R23, ob 1206 oder 0805.
- Wandlerverluste als eigene Quelle in U2 (70 %), D3 (20 %), D2 und L1 (je 5 %), beim Heizen und beim Laden.
- Thermische Vias unter dem TPS5430 sind Vias, keine Stifte zum XIAO.
Die Platine ist noch unverdrahtet: Flächen und GND-Vias zählen, Bahnen fehlen (wenig Kupfer, eher zu warm).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

import thermal as th
import thermal_model as tm

W5 = 20.955
HEATERS = ("R19", "R20", "R21", "R22", "R23")
# Wandlerverlust in W, (Heizen 0,41 W am Ausgang, Laden ~0,5 W am Ausgang). Abgeschätzt aus den TI-Datenblättern:
# TPS5430 Ruhestrom 3–4,4 mA aus ~22 V, Schalt- und Diodenverluste; TPS54331 Eco-mode, aus 12 V.
LOSS = {"solar": (0.16, 0.18), "netz": (0.07, 0.08)}
VOUT = {"solar": 4.92, "netz": 4.88}


def geometry(pcb: str) -> dict:
    sys.path.insert(0, os.path.join(tm.STAPEL, "tools"))
    import kicad_env
    out = subprocess.run([kicad_env.pcbnew_python(), os.path.join(tm.HERE, "thermal_geometry.py"), pcb],
                         check=True, capture_output=True, text=True).stdout
    geo = json.loads(next(line for line in out.splitlines() if line.startswith("JSON"))[4:])
    edge = subprocess.run([kicad_env.pcbnew_python(), "-c",
                           "import sys,pcbnew;b=pcbnew.LoadBoard(sys.argv[1]);"
                           "print(pcbnew.ToMM(b.GetBoardEdgesBoundingBox().GetLeft())-50)", pcb],
                          check=True, capture_output=True, text=True).stdout.split()[-1]
    ext = round(-float(edge), 3)                    # Umriss links von x = 0
    sh = lambda v: [v[0] + ext, v[1]]                # noqa: E731
    for p in geo["pads"]:
        p["at"] = sh(p["at"])
        p["box"] = sh(p["box"][:2]) + sh(p["box"][2:])
    for v in geo["vias"]:
        v["at"] = sh(v["at"])
    for t in geo["tracks"]:
        t["a"], t["b"] = sh(t["a"]), sh(t["b"])
    for b in geo["bodies"]:
        b["box"] = sh(b["box"][:2]) + sh(b["box"][2:])
    for z in geo["zones"]:
        z["rings"] = [[sh(pt) for pt in ring] for ring in z["rings"]]
    # Bohrungen im Wärmepad des TPS5430: Vias, keine Stifte
    for p in [p for p in geo["pads"] if p["drill"] and p["ref"] not in ("J5", "J6")]:
        geo["vias"].append({"at": p["at"], "d": p["box"][2] - p["box"][0], "drill": p["drill"]})
        p["drill"] = 0.0
    geo["ext"] = ext
    return geo


class Model12(tm.Model):
    """tm.Model mit 12-V-Platine. cfg: variant, loss (heat, charge), vout."""

    cfg: dict = {}

    def _materials(self, copper):
        super()._materials(copper)
        e, t = self.geo["ext"], self.pcb_t
        # XIAO und Wio nicht über der Verlängerung: dort nur Luft
        self.fill(self.idx(0, 0, t + 0.1, e, tm.H, t + 17.5), self.s.k_air, None, 1.2e3)
        for b in self.geo["bodies"]:
            if b["box"][0] < e:
                self._component(b)

    def _component(self, b):
        fp = b["fp"]
        if "0805" in fp or "0402" in fp:
            t, (x0, y0, x1, y1) = self.pcb_t, b["box"]
            h = 0.5 if "0805" in fp else 0.35
            k = 3.0 if b["ref"].startswith("C") else 25.0
            self.fill(self.idx(x0, y0, t + 0.1, x1, y1, t + h), k, None, 3.0e6)
            self.fill(self.idx(x0, y0, t, x1, y1, t + 0.1), 0.3, None, 1.5e6)
            for p in [p for p in self.geo["pads"] if p["ref"] == b["ref"]]:
                a, c, d, e = p["box"]
                self.fill(self.idx(max(a, x0), max(c, y0), t, min(d, x1), min(e, y1), t + 0.1), 50.0, None, 2.0e6)
                self.fill(self.idx(max(a, x0), max(c, y0), t + 0.1, min(d, x1), min(e, y1), t + h), 40.0, None,
                          3.0e6)
        else:
            super()._component(b)

    def _sources(self):
        c, t = self.cfg, self.pcb_t
        body = {b["ref"]: b for b in self.geo["bodies"]}
        self.heaters = {r: body[r] for r in HEATERS}
        n = len(self.heaters)
        ohm = float(body["R19"]["value"])
        r_q4 = 0.030
        i = c["vout"] / (ohm / n + r_q4)
        heat = np.zeros(self.shape)
        self.film = {}
        for ref, b in self.heaters.items():
            x0, y0, x1, y1 = b["box"]
            # Widerstandsschicht: Körper ohne Endkappen. 1206: 3,2 × 1,6 mm, 0805: 2,0 × 1,25 mm
            cap = 0.55 if "1206" in b["fp"] else 0.35
            side = 0.2 if "1206" in b["fp"] else 0.15
            long_y = (y1 - y0) > (x1 - x0)
            mx, my = (side, cap) if long_y else (cap, side)
            top = 0.65 if "1206" in b["fp"] else 0.5
            self.film[ref] = self.idx(x0 + mx, y0 + my, t + top - 0.15, x1 - mx, y1 - my, t + top)
            heat += self.source(self.film[ref], (i / n) ** 2 * ohm)
        mid = lambda ref: self.idx(*body[ref]["box"][:2], t + .1, *body[ref]["box"][2:], t + .9)   # noqa: E731

        def conv(p):
            return (self.source(mid("U2"), 0.70 * p) + self.source(mid("D3"), 0.20 * p)
                    + self.source(mid("D2"), 0.05 * p) + self.source(mid("L1"), 0.05 * p))

        heat += self.source(mid("Q4"), i * i * r_q4)
        ctrl = self.source(mid("U1"), c["vout"] * 1.2e-3)
        self.p_film = (i / n) ** 2 * ohm
        self.p_heat = n * self.p_film
        self.b = {
            "heat": heat + ctrl + conv(c["loss"][0]),
            "charge": ctrl + conv(c["loss"][1])
            + self.source(self.idx(tm.W - 8, 6, t + 11, tm.W - 4, 11, t + 12), (c["vout"] - 3.7) * 0.100 + 0.005),
        }


def setup(cfg):
    tm.W = W5 + cfg["geo"]["ext"]
    Model12.cfg = cfg


def fault_job(args):
    cfg, sources, ta = args
    setup(cfg)
    return cfg["name"], ta, th.nonlinear(Model12(th.BASE, cfg["geo"]), sources, ta)


def detail_job(args):
    cfg, limits = args
    setup(cfg)
    m = Model12(th.BASE, cfg["geo"])
    rom = tm.Reduced(m)
    res = {"name": cfg["name"], "p_heat": float(m.p_heat), "p_film": float(m.p_film),
           "loss": cfg["loss"], "length": float(tm.W)}
    res["hold_to"] = float(limits[1] - rom.steady["heat"][m.ntc_points()[th.NTC_MAIN]].mean())
    res["film_rise"] = float(rom.steady["heat"][m.probes()["film"]].max())
    res["cell_rise"] = float(rom.steady["heat"][m.battery].max())
    E, F = rom.step_matrices(5.0)
    for ta in (20, 35):
        z, hit = np.zeros(len(E)), None
        for k in range(1, 4321):
            z = E @ z + F[:, 0]
            if k % 6 == 0 and ta + float((rom.out["cell"] @ z).max()) >= 60:
                hit = k * 5 / 60
                break
        res[f"min_to_60_from_{ta}"] = hit
    for ta in (-10, -20):
        res[f"op{ta}"] = th.operate(rom, 1.0, ta, th.NTC_MAIN, limits)[0]
    res["hot"] = [dict(th.operate(rom, 1.0, ta, th.NTC_MAIN, limits)[0], ta=ta) for ta in (25, 30, 35, 40)]
    return res


def main():
    args = sys.argv[1:]
    runs = []
    for k in range(0, len(args), 3):
        name, variant, pcb = args[k:k + 3]
        runs.append({"name": name, "variant": variant, "loss": LOSS[variant], "vout": VOUT[variant],
                     "geo": geometry(pcb)})
    nom, band = th.thresholds()
    path = os.path.join(th.REPORT, "thermal-12v.json")
    out = {"thresholds": [float(v) for v in nom], "runs": [{k: v for k, v in r.items() if k != "geo"} for r in runs],
           "faults": [], "details": []}
    t0 = time.time()
    jobs = [(r, {"heat": 1.0}, ta) for r in runs for ta in (-20, 20, 35)]
    jobs += [(r, {"charge": 1.0}, ta) for r in runs for ta in (30, 35, 40)]
    with ProcessPoolExecutor(5) as pool:
        for row in pool.map(fault_job, jobs):
            out["faults"].append(row)
            print("  ", row[0], row[1], {k: round(v, 1) for k, v in row[2].items()}, f"{time.time() - t0:.0f} s",
                  flush=True)
    with ProcessPoolExecutor(3) as pool:
        for row in pool.map(detail_job, [(r, nom) for r in runs]):
            out["details"].append(row)
            print("  ", {k: (round(v, 2) if isinstance(v, float) else v) for k, v in row.items() if k != "hot"},
                  flush=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print("fertig", f"{time.time() - t0:.0f} s", flush=True)


if __name__ == "__main__":
    main()
