"""Mehrtägige Simulation: Sonne/Nacht, Temperaturverlauf, Laden, Entladen, Ladesperre, Heizung.

Ein durchgehender Transient (Hysterese der Komparatoren bleibt erhalten). Messung und Funk als Mittelwert:
Sonde 80 mA für 2,3 s je Minute aus VSYS über den 12-V-Wandler, Funk 120 mA für 0,3 s je Minute.
"""

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from board import CAPACITY_AS, Scenario, settle  # noqa: E402
from ngspice import NgSpice  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPORT = os.path.join(HERE, "report")
DAY = 86400.0

# Mittlere Zusatzlast an VSYS: Sonde 80 mA · 12,3 V / (VSYS · 0,85) · 2,3/60 + 3 mA Wandler
SENS_AVG = "(0.080*12.3/(max(V(N_VSYS),2.5)*0.85) + 0.003)*2.3/60"
XIAO_AVG_MA = 6.0 + 120 * 0.3 / 60

HOUR = f"(time/3600 - 24*floor(time/{DAY}))"
CASES = {
    "winter": dict(days=3, soc=0.30, temp=f"(-6 + 6*sin(2*pi*({HOUR}-9)/24))",
                   sun=f"(0.35*max(0, sin(pi*({HOUR}-8)/8)) * ({HOUR} > 8) * ({HOUR} < 16))"),
    "sommer": dict(days=2, soc=0.30, temp=f"(20 + 8*sin(2*pi*({HOUR}-9)/24))",
                   sun=f"(1.0*max(0, sin(pi*({HOUR}-5)/15)) * ({HOUR} > 5) * ({HOUR} < 20))"),
}
SAVE = ["n_temp", "n_vsys", "n_vsol", "n_soc", "i:vam_bat", "i:vam_q7", "n_chg_csp", "n_chg_inhibit",
        "n_heat_off", "n_p3v3"]


def profile(expr: str, t: float) -> float:
    """Ausdruck in time (wie für SPICE geschrieben) in Python auswerten."""
    import math
    py = expr.replace("time", f"({t})").replace("floor", "math.floor").replace("sin", "math.sin").replace("pi", "math.pi")
    py = py.replace("max(", "max(").replace(">", ">").replace("<", "<")
    return float(eval(py, {"math": math}))


def run(ng, name, cfg, step=1200.0):
    """Quasistatisch: alle 20 min eingeschwungener Zustand, Ladezustand in Python integriert."""
    soc = cfg["soc"]
    keys = ["time", "n_temp", "n_vsys", "n_vsol", "n_soc", "vam_bat#branch", "vam_q7#branch", "n_chg_csp",
            "n_chg_inhibit", "n_heat_off", "n_p3v3"]
    r = {k: [] for k in keys}
    t = 0.0
    while t <= cfg["days"] * DAY:
        sun = profile(cfg["sun"], t)
        temp = profile(cfg["temp"], t)
        sc = Scenario(name, sun=sun, temp=temp, soc=soc, xiao_ma=XIAO_AVG_MA)
        v = settle(ng, sc, extra_lines=[f"Bsens_avg N_VSYS 0 I = {SENS_AVG}*min(1,time/10m)"])
        v["time"] = t
        v["n_soc"] = soc
        for k in keys:
            r[k].append(v.get(k, 0.0))
        soc = min(1.0, max(0.0, soc + v["vam_bat#branch"] * step / CAPACITY_AS))
        t += step
    return r


def main():
    ng = NgSpice()
    os.makedirs(REPORT, exist_ok=True)
    lines = ["# Langzeitsimulation", ""]
    for name, cfg in CASES.items():
        r = run(ng, name, cfg)
        h = [t / 3600 for t in r["time"]]
        ichg = [(a - b) / 0.04 for a, b in zip(r["n_chg_csp"], r["n_vsys"])]
        heat_w = [i * v for i, v in zip(r["vam_q7#branch"], r["n_vsol"])]
        soc = r["n_soc"]
        # Energie: Ladung ins Akku, Heizenergie (Trapez)
        dt = [b - a for a, b in zip(r["time"], r["time"][1:])]
        ah_in = sum(max(i, 0) * d for i, d in zip(r["vam_bat#branch"], dt)) / 3600
        ah_out = sum(-min(i, 0) * d for i, d in zip(r["vam_bat#branch"], dt)) / 3600
        wh_heat = sum(p * d for p, d in zip(heat_w, dt)) / 3600
        lines += [f"## {name.capitalize()} ({cfg['days']} Tage)", "",
                  f"- Ladezustand: {cfg['soc'] * 100:.0f} % → {soc[-1] * 100:.1f} % (min {min(soc) * 100:.1f} %, max {max(soc) * 100:.1f} %)",
                  f"- Geladen: {ah_in:.2f} Ah, entnommen: {ah_out:.2f} Ah",
                  f"- Heizenergie aus dem Panel: {wh_heat:.1f} Wh",
                  f"- VSYS min/max: {min(r['n_vsys']):.2f} / {max(r['n_vsys']):.2f} V, +3V3 min: {min(r['n_p3v3']):.2f} V",
                  f"- Ladestrom bei Ladesperre (CHG_INHIBIT hoch) max: "
                  f"{max([c for c, s in zip(ichg, r['n_chg_inhibit']) if s > 1.5] or [0]):.3f} A",
                  f"- Akkustrom nachts (Sonne aus) im Mittel: "
                  f"{sum(i for i, v in zip(r['vam_bat#branch'], r['n_vsol']) if v < 5) / max(1, sum(1 for v in r['n_vsol'] if v < 5)) * 1000:.1f} mA",
                  "", f"![{name}](longterm_{name}.png)", ""]
        fig, ax = plt.subplots(4, 1, figsize=(10, 9), sharex=True)
        ax[0].plot(h, r["n_temp"], label="Temperatur [°C]")
        ax[0].plot(h, r["n_vsol"], label="VSOL [V]")
        ax[0].legend(loc="upper right")
        ax[1].plot(h, ichg, label="Ladestrom [A]")
        ax[1].plot(h, r["vam_q7#branch"], label="Heizstrom [A]")
        ax[1].legend(loc="upper right")
        ax[2].plot(h, [s * 100 for s in soc], label="Ladezustand [%]")
        ax[2].legend(loc="upper right")
        ax[3].plot(h, r["n_vsys"], label="VSYS [V]")
        ax[3].plot(h, r["n_chg_inhibit"], label="Ladesperre", alpha=0.6)
        ax[3].plot(h, r["n_heat_off"], label="HEAT_OFF (hoch = Heizung aus)", alpha=0.6)
        ax[3].legend(loc="upper right")
        ax[3].set_xlabel("Stunden")
        fig.suptitle(f"Langzeit {name}")
        fig.tight_layout()
        fig.savefig(os.path.join(REPORT, f"longterm_{name}.png"), dpi=100)
        plt.close(fig)
        print("\n".join(lines[-9:-3]))
    # Dunkelflaute: Laufzeit ohne Sonne ab voll
    night = (XIAO_AVG_MA * 3.3 / (3.25 * 0.9) + 0.6 + 13.4 + 0.1)
    lines += [f"## Dunkelflaute", "",
              f"- Mittlerer Akkustrom ohne Sonne ≈ {night:.1f} mA → {CAPACITY_AS / 3600 / night * 1000 / 24:.0f} Tage "
              f"von voll bis leer (18 Ah)", ""]
    with open(os.path.join(REPORT, "longterm.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
