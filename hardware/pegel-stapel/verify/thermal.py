"""Erwärmung der 5-V-Ladeplatine mit Akku und Dämmung: alle Fälle rechnen, Bericht und Bilder nach report/.

    python thermal.py [pruefen] [betrieb] [fehler] [details] [empfindlich]   (ohne Argument alles, ~20 min; braucht numpy, scipy, numba, matplotlib und KiCad 10)

Modell und Annahmen: thermal_model.py. Die .kicad_pcb wird nur gelesen.
"""

from __future__ import annotations

import itertools
import json
import math
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace

import numpy as np

import thermal_model as tm

REPORT = os.path.join(tm.HERE, "report")
BASE = tm.Setup(h_step=0.20)
BONDS = {"Klebeband": BASE, "Wärmeleitpad": replace(BASE, k_gap=1.5), "Luftspalt": replace(BASE, k_gap=0.033)}
OPTION = "5 × 300 Ω"      # wie in der .kicad_pcb
OPTIONS = {OPTION: 1.0}
AMBIENT = (0, -10, -20, -30)
NTC_MAIN = "Akku oben, neben der Platine"
SPOTS = ("film", "board", "cell", "eps", "u1")


# ------------------------------------------------------------------------------------ Thermostat aus design.py
def thresholds():
    """Alle vier Schwellen: Nennwert und Grenzen über alle Toleranzecken."""
    sys.path[:0] = [os.path.join(tm.STAPEL, "lader-5v"), os.path.join(tm.STAPEL, "tools")]
    import design
    si = {"k": 1e3, "M": 1e6}
    val = {p.ref: float(p.value[:-1]) * si[p.value[-1]] for p in design.PARTS
           if p.symbol == "Device:R" and p.value[-1] in si}
    refs = ("R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8")

    def calc(R1, R2, R3, R4, R5, R6, R7, R8, R25, B, offset, bias, vsat, v):
        low = (v / R2 + vsat / R6 + 2 * bias) / (1 / R2 + 1 / R3 + 1 / R6)
        high = (v / R2 + v / (R6 + R8) + 2 * bias) / (1 / R2 + 1 / R3 + 1 / (R6 + R8))
        temp = lambda t, x: 1 / (1 / 298.15 + np.log(
            (v - t) / (t / R1 + (t - x) / R4 - bias) / R25) / B) - 273.15

        def cold(ref):
            t = ref + offset
            return temp(t, (t / R4 + vsat / R7 + bias) / (1 / R4 + 1 / R5 + 1 / R7))

        def hot(out, r):
            x = low + offset
            return temp(x + R4 * (x / R5 + (x - out) / r - bias), x)

        return cold(low), cold(high), hot(vsat, R7), hot(v, R7 + val["R9"])

    nom = calc(*(val[r] for r in refs), 10e3, 3950.0, 0.0, 25e-9, 0.08, 5.0)
    limits = [(val[r] * 0.99, val[r] * 1.01) for r in refs]
    limits += [(9.9e3, 10.1e3), (3910.5, 3989.5), (-0.005, 0.005), (0.0, 250e-9), (0.02, 0.2), (4.5, 5.25)]
    res = calc(*np.array(list(itertools.product(*limits))).T)
    return nom, [(float(x.min()), float(x.max())) for x in res]


# ------------------------------------------------------------------------------------ Prüfung des Lösers
def plain_model(edges, k, h):
    m = object.__new__(tm.Model)
    m.s = replace(tm.Setup(), h_out=h, wire_mm2=0.0)
    m.dx, m.dy, m.dz = (np.diff(e) * 1e-3 for e in edges)
    m.shape = (len(m.dx), len(m.dy), len(m.dz))
    m.vol = m.dx[:, None, None] * m.dy[None, :, None] * m.dz[None, None, :]
    m.kx = m.ky = m.kz = k
    m.rhoc = np.ones(m.shape)
    m._couple()
    return m


def validate(geo):
    out = {}
    # 1) Platte mit gleichmäßiger Quelle, beide Seiten gekühlt: T_max = qL²/8k + qL/2h
    e = np.linspace(0, 20, 201)
    k, h, L, q = 0.5, 50.0, 0.020, 1e4
    m = plain_model((e, np.array([0, 1e5]), np.array([0, 1e5])), np.full((200, 1, 1), k), h)
    x = m.solve(q * m.vol, tol=1e-9)
    out["Platte, Scheitel gegen Formel"] = (float(x.max()), q * L * L / (8 * k) + q * L / (2 * h))
    # 2) isothermer Würfel 60 mm in 30 mm Styropor, außen isotherm: Formfaktor nach Langmuir
    e = tm.axis([-60, -30, 30, 60], [1, 2, 1])
    c = (e[1:] + e[:-1]) / 2
    ins = np.abs(c) < 30
    inner = ins[:, None, None] & ins[None, :, None] & ins[None, None, :]
    m = plain_model((e, e, e), np.where(inner, 500.0, 0.035), 1e7)
    b = np.where(inner, m.vol, 0)
    x = m.solve(b / b.sum())
    a, w = 0.060, 0.030
    s = 6 * a * a / w + 0.54 * 12 * a + 0.15 * 8 * w
    out["Würfel in Styropor, K/W gegen Formfaktor"] = (float(x[inner].mean()), 1 / (0.035 * s))
    # 3) reduziertes gegen volles Modell, 300 s Heizen, gleicher Zeitschritt
    m = tm.Model(replace(BASE, h_step=0.5), geo)
    rom = tm.Reduced(m, ("heat",))
    dt, x, z = 5.0, np.zeros(m.shape), np.zeros(len(rom.A))
    M = np.eye(len(z)) / dt - rom.A
    for _ in range(60):
        x = m.solve(m.b["heat"] + m.cap / dt * x, 1 / dt, x0=x)
        z = np.linalg.solve(M, rom.B[:, 0] + z / dt)
    p = m.probes()
    for key in ("film", "cell"):
        out[f"reduziert gegen voll, {key} nach 300 s"] = (float((rom.out[key] @ z).max()), float(x[p[key]].max()))
    return out


# ------------------------------------------------------------------------------------ Thermostatbetrieb
def operate(rom, scale, ta, ntc, limits, hours=12.0, dt=1.0, lag=8.0):
    on_at, off_at, stop_at, resume_at = limits
    E, F = rom.step_matrices(dt)
    hi, ci = rom.names.index("heat"), rom.names.index("charge")
    n = int(hours * 3600 / dt)
    Z, sensed = np.zeros((n + 1, len(E))), np.full(n + 1, float(ta))
    on = np.zeros(n + 1, bool)
    cut = np.zeros(n + 1, bool)
    cut[0] = blocked = ta >= stop_at
    z, t_ntc, state = np.zeros(len(E)), float(ta), ta < on_at
    pos, a = rom.ntc[ntc], 1 - math.exp(-dt / lag)
    on[0] = state
    for k in range(1, n + 1):
        u = np.zeros(2)
        if state:
            u[hi] = scale
        elif not blocked:      # weder kalt noch heiß: es wird geladen
            u[ci] = 1.0
        z = E @ z + F @ u
        t_ntc += a * (ta + float(pos @ z) - t_ntc)
        if state and t_ntc > off_at:
            state = False
        elif not state and t_ntc < on_at:
            state = True
        if t_ntc > stop_at:
            blocked = True
        elif t_ntc < resume_at:
            blocked = False
        Z[k], sensed[k], on[k], cut[k] = z, t_ntc, state, blocked
    edges = np.flatnonzero(np.diff(on.astype(int)))
    tail = slice(n * 2 // 3, n + 1)
    pick = np.unique(np.concatenate([np.arange(0, min(n, 5400), 10), np.arange(0, n, 90),
                                     edges[:30], edges[:30] + 1, edges[-30:], edges[-30:] + 1, [n]]).astype(int))
    res = {}
    for key in SPOTS:
        hot = np.concatenate([(rom.out[key] @ Z[pick[i:i + 100]].T).max(axis=0) for i in range(0, len(pick), 100)])
        res[key] = float(ta + hot.max())
    switch = np.flatnonzero(np.diff(cut.astype(int)))
    pick = np.unique(np.concatenate([pick, switch[:30], switch[:30] + 1]).astype(int))
    charging = pick[~on[pick] & ~cut[pick]]
    res["cell_min_charge"] = float(ta + min(
        (rom.out["cell"] @ Z[charging[i:i + 100]].T).min() for i in range(0, len(charging), 100))
    ) if len(charging) else None
    res["cell_max_charge"] = float(ta + max(
        (rom.out["cell"] @ Z[charging[i:i + 100]].T).max() for i in range(0, len(charging), 100))
    ) if len(charging) else None
    res["charge_share"] = float((~on & ~cut)[tail].mean())
    res["cell_mean_end"] = float(ta + (Z[tail] @ rom.cell_mean).mean())
    res["first_off_min"] = float(np.argmin(on) * dt / 60) if not on.all() else None
    res["duty"] = float(on[tail].mean())
    starts = edges[on[edges + 1]] if len(edges) else np.array([])
    res["period_min"] = float(np.diff(starts[-5:]).mean() * dt / 60) if len(starts) > 1 else None
    return res, Z, sensed, on, cut


def bond_job(args):
    name, setup, geo, limits = args
    t0 = time.time()
    m = tm.Model(setup, geo)
    rom = tm.Reduced(m)
    cases = []
    for option, scale in OPTIONS.items():
        for ta in AMBIENT:
            for ntc in rom.ntc:
                res = operate(rom, scale, ta, ntc, limits)[0]
                cases.append(dict(res, bond=name, option=option, ta=ta, ntc=ntc))
    steady = {}
    probes = m.probes()
    for src in rom.names:
        x = rom.steady[src]
        steady[src] = {k: float(x[v].max()) for k, v in probes.items()}
        steady[src]["cell_mean"] = float(x[m.battery].mean())
        steady[src]["power"] = float(m.b[src].sum())
        steady[src]["balance"] = m.balance(x, m.b[src])
    series = None
    if name == "Klebeband":
        series = {}
        for ta, hours in ((-15, 4.0), (37, 6.0)):
            res, Z, sensed, on, cut = operate(rom, 1.0, ta, NTC_MAIN, limits, hours=hours)
            rows = np.arange(0, len(Z), 5)
            hot = {k: ta + np.concatenate([(rom.out[k] @ Z[rows[i:i + 100]].T).max(axis=0)
                                           for i in range(0, len(rows), 100)]) for k in ("film", "cell")}
            series[ta] = dict(hot, t=rows / 60, ntc=sensed[rows], on=on[rows], cut=cut[rows])
        slices = {
            "x": m.ex, "y": m.ey, "z": m.ez,
            "board": rom.steady["heat"][:, :, int(np.argmin(np.abs(m.zc - (m.pcb_t - 0.1))))],
            "cell": rom.steady["heat"][:, :, int(np.argmin(np.abs(m.zc - (m.bz[1] - 0.15))))],
            "cut": rom.steady["heat"][:, int(np.argmin(np.abs(m.yc - 5.34))), :],
        }
        series = {"lines": series, "slices": slices}
    print(f"  {name}: {len(rom.A)} Zustände, {m.vol.size / 1e6:.2f} Mio. Zellen, {time.time() - t0:.0f} s", flush=True)
    return name, cases, steady, series


# ------------------------------------------------------------------------------------ Fehlerfälle, nichtlinear
def nonlinear(m, sources, ta, rounds=12):
    """Strahlung (~T³) und Luft in den Hohlräumen sowie Styropor temperaturabhängig nachführen."""
    air = m.rhoc == 1.2e3
    eps = (m.rhoc == 20 * 1300.) & (m.kx == m.s.k_eps)
    b = sum(f * m.b[n] for n, f in sources.items())
    x = np.zeros(m.shape)
    last = None
    for _ in range(rounds):
        x = m.solve(b, tol=1e-5, x0=x)
        top = float(x.max())
        if last is not None and abs(top - last) < 0.3:
            break
        last = top
        tk = np.minimum(ta + x + 273.15, 600.0)
        ka = 0.026 * (tk / 283.15) ** 0.8 + 4 * 0.85 * 5.670e-8 * tk ** 3 * 0.006
        ke = m.s.k_eps * (1 + 0.0035 * (tk - 283.15))
        for k in (m.kx, m.ky, m.kz):
            k[air] = ka[air]
            k[eps] = ke[eps]
        m._couple()
    res = {k: float(ta + x[v].max()) for k, v in m.probes().items()}
    res["cell_mean"] = float(ta + x[m.battery].mean())
    return res


def fault_job(args):
    label, setup, geo, sources, ta = args
    return label, ta, nonlinear(tm.Model(setup, geo), sources, ta)


def sens_job(args):
    name, setup, geo = args
    m = tm.Model(setup, geo)
    x = m.solve(m.b["heat"])
    res = {k: float(x[v].max()) for k, v in m.probes().items()}
    res["cell_mean"] = float(x[m.battery].mean())
    res["cells"] = int(x.size)
    return name, res


def detail_job(args):
    """Genaue Bestückung je Option: LM393, Zeit bis 60 °C ohne NTC, tiefste Außentemperatur, Hitzeabschaltung."""
    option, geo, limits = args
    m = tm.Model(BASE, geo)
    scale = OPTIONS[option]
    rom = tm.Reduced(m)
    res = {"option": option, "power": float(m.b["heat"].sum() * scale)}
    res["u1_rise"] = float(rom.steady["heat"][m.probes()["u1"]].max() * scale)
    res["cell_rise"] = float(rom.steady["heat"][m.battery].max() * scale)
    res["p_film"] = float(m.p_film)
    res["hold_to"] = float(limits[1] - rom.steady["heat"][m.ntc_points()[NTC_MAIN]].mean() * scale)
    for ta in (-10, -15, -20):
        r = operate(rom, scale, ta, NTC_MAIN, limits)[0]
        res[f"op{ta}"] = r
    res["hot"] = []
    for ta in (25, 30, 35, 37, 40, 45):
        for ntc in rom.ntc:
            res["hot"].append(dict(operate(rom, scale, ta, ntc, limits)[0], ta=ta, ntc=ntc))
    E, F = rom.step_matrices(5.0)
    for ta in (20, 35):
        z, t = np.zeros(len(E)), None
        for k in range(1, 4321):
            z = E @ z + F[:, 0] * scale
            if k % 6 == 0 and ta + float((rom.out["cell"] @ z).max()) >= 60:
                t = k * 5 / 60
                break
        res[f"min_to_60_from_{ta}"] = t
    return res


SENSITIVITY = {
    "Basis": BASE,
    "Gitter 0,35 mm": replace(BASE, h_step=0.35),
    "Gitter 0,15 mm": replace(BASE, h_step=0.15),
    "Styropor 0,032 W/mK": replace(BASE, k_eps=0.032),
    "Styropor 0,040 W/mK": replace(BASE, k_eps=0.040),
    "Styropor bündig ausgeschnitten": replace(BASE, tight=True),
    "Luft im Hohlraum 0,035 W/mK": replace(BASE, k_air=0.035),
    "Luft im Hohlraum 0,090 W/mK": replace(BASE, k_air=0.090),
    "außen windstill, 6 W/m²K": replace(BASE, h_out=6.0),
    "außen Wind, 25 W/m²K": replace(BASE, h_out=25.0),
    "ohne 5-V-Leitung": replace(BASE, wire_mm2=0.0),
    "5-V-Leitung 2 × 0,5 mm²": replace(BASE, wire_mm2=0.5),
    "Zelle 602248 (schmal, lang)": replace(BASE, cell=(48.5, 22.5, 6.0), cell_mass=14.5),
    "Zelle quer 0,3 W/mK": replace(BASE, k_cell_thick=0.30),
    "FR4 0,4 W/mK": replace(BASE, k_fr4=0.4),
    "Stifte 40 W/mK": replace(BASE, k_pin=40.0),
    "Kupfer 70 µm": replace(BASE, cu_um=70.0),
}


def main():
    steps = sys.argv[1:] or ["pruefen", "betrieb", "fehler", "details", "empfindlich"]
    path = os.path.join(REPORT, "thermal.json")
    os.makedirs(REPORT, exist_ok=True)
    geo = tm.load_geometry()
    result = json.load(open(path, encoding="utf-8")) if os.path.isfile(path) else {}
    nom, band = thresholds()
    result["thresholds"] = {"nominal": [float(v) for v in nom], "band": band}
    print("Schwellen:", [round(float(v), 2) for v in nom], band, flush=True)

    def save():
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=1, ensure_ascii=False)

    if "pruefen" in steps:
        print("Löserprüfung", flush=True)
        result["validation"] = validate(geo)
        for k, (a, b) in result["validation"].items():
            print(f"  {k}: {a:.3f} / {b:.3f} ({(a / b - 1) * 100:+.2f} %)", flush=True)
        save()

    if "betrieb" in steps:
        print("Thermostatbetrieb", flush=True)
        result["cases"], result["steady"] = [], {}
        plots = None
        with ProcessPoolExecutor(3) as pool:
            for name, cases, steady, series in pool.map(bond_job, [(n, s, geo, nom) for n, s in BONDS.items()]):
                result["cases"] += cases
                result["steady"][name] = steady
                plots = series or plots
        np.save(os.path.join(tm.STAPEL, "build", "thermal_plots.npy"), np.array([plots], dtype=object),
                allow_pickle=True)
        save()

    if "fehler" in steps:
        print("Fehlerfälle und Laden", flush=True)
        jobs = [(opt, BASE, geo, {"heat": f}, ta) for opt, f in OPTIONS.items() for ta in (-20, 20, 35)]
        jobs += [("Laden", BASE, geo, {"charge": 1.0}, ta) for ta in (25, 30, 35, 37, 40, 45)]
        result["faults"] = []
        with ProcessPoolExecutor(5) as pool:
            for row in pool.map(fault_job, jobs):
                result["faults"].append(row)
                print("  ", row[0], row[1], {k: round(v, 1) for k, v in row[2].items()}, flush=True)
        save()

    if "empfindlich" in steps:
        print("Empfindlichkeit", flush=True)
        result["sensitivity"] = []
        with ProcessPoolExecutor(4) as pool:
            for row in pool.map(sens_job, [(n, s, geo) for n, s in SENSITIVITY.items()]):
                result["sensitivity"].append(row)
                print("  ", row[0], {k: round(v, 1) for k, v in row[1].items()}, flush=True)
        save()
    if "details" in steps:
        print("Details je Bestückung", flush=True)
        with ProcessPoolExecutor(3) as pool:
            result["details"] = list(pool.map(detail_job, [(o, geo, nom) for o in OPTIONS]))
        for row in result["details"]:
            print("  ", row, flush=True)
        save()
    print("fertig", flush=True)


if __name__ == "__main__":
    main()
