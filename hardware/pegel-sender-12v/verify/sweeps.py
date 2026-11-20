"""Verläufe: Temperatur und Netzteilspannung (langsame Rampen) und Einschalten der Sonde.

Schwellen werden beim Hoch- und Runterfahren gemessen, damit die Hysterese sichtbar ist. Bilder nach report/.
"""

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from board import R_SHUNT, Scenario, netlist  # noqa: E402
from ngspice import NgSpice  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPORT = os.path.join(HERE, "report")


def tri(lo, hi, t_half):
    """Dreieck lo → hi → lo über 2·t_half (Ausdruck in time)."""
    return f"({lo} + ({hi}-({lo}))*(1-abs(time/{t_half}-1)))"


SAVE = ["n_temp", "n_bat_n", "n_vsys", "n_vsol", "n_chg_inh", "n_heat_off", "i:vam_heat", "n_in_raw",
        "n_v12_probe", "n_v12_raw", "n_sens_en", "n_psw_g", "i:vam_q5", "n_xiao_3v3"]


def run(ng, sc, t_end, step, **kw):
    return ng.run(netlist(sc, f".tran {step} {t_end} 0 {step}", save=SAVE, **kw))


def edges(x, sig, t, t_from, t_to):
    """x-Werte, an denen sig zwischen t_from und t_to den Zustand wechselt: (x, neuer Zustand)."""
    return [(x[i], sig[i]) for i in range(1, len(t)) if t_from < t[i] <= t_to and sig[i] != sig[i - 1]]


def main():
    ng = NgSpice()
    os.makedirs(REPORT, exist_ok=True)
    out = []

    # 1) Temperatur −10 → +10 → −10 °C bei Sonne
    sc = Scenario("Temperaturrampe", sun=1, temp=0, soc=0.5)
    r = run(ng, sc, 4.0, "2m", temp_expr=tri(-10, 10, 2.0), ramp="10m")
    t, time = r["n_temp"], r["time"]
    ichg = [v / R_SHUNT for v in r["n_bat_n"]]
    iheat = r["vam_heat#branch"]
    # Zustände an den Strömen ablesen: Laden > 0,1 A, Heizen > 0,05 A. Anlauf (< 100 ms) auslassen.
    for sig, on_lbl, off_lbl in (([i > 0.1 for i in ichg], "Laden frei", "Ladesperre"),
                                 ([abs(i) > 0.05 for i in iheat], "Heizung an", "Heizung aus")):
        for phase, ev in (("beim Erwärmen", edges(t, sig, time, 0.1, 2.0)),
                          ("beim Abkühlen", edges(t, sig, time, 2.0, 4.0))):
            for temp, state in ev[:2]:
                out.append((f"{on_lbl if state else off_lbl} {phase} ab [°C]", [temp]))
    fig, ax = plt.subplots(3, 1, figsize=(9, 7), sharex=True)
    ax[0].plot(time, t)
    ax[0].set_ylabel("Temperatur [°C]")
    ax[1].plot(time, ichg, label="Ladestrom")
    ax[1].plot(time, iheat, label="Heizstrom")
    ax[1].set_ylabel("Strom [A]")
    ax[1].legend()
    ax[2].plot(time, r["n_chg_inh"], label="CHG_INH (Ladesperre)")
    ax[2].plot(time, r["n_heat_off"], label="HEAT_OFF")
    ax[2].set_ylabel("Spannung [V]")
    ax[2].legend()
    ax[2].set_xlabel("Simulationszeit (Rampe −10 → +10 → −10 °C)")
    fig.tight_layout()
    fig.savefig(os.path.join(REPORT, "temperatur.png"), dpi=110)
    plt.close(fig)

    # 2) Netzteil 0 → 15 → 0 V an J1, mit und ohne Steckbrücke JP2
    for jp2 in (True, False):
        sc = Scenario("Netzteilrampe", sun=0, temp=20, dc=tri(0, 15, 2.0), jp2=jp2, soc=0.3)
        r = run(ng, sc, 4.0, "2m")
        sig = [v / R_SHUNT > 0.1 for v in r["n_bat_n"]]
        up = [v for v, s in edges(r["n_in_raw"], sig, r["time"], 0.05, 2.0) if s]
        dn = [v for v, s in edges(r["n_in_raw"], sig, r["time"], 2.0, 4.0) if not s]
        imax = max(v / R_SHUNT for v in r["n_bat_n"])
        tag = "mit" if jp2 else "ohne"
        out.append((f"Netzteil {tag} Steckbrücke: Laden ab [V]", up[:1]))
        out.append((f"Netzteil {tag} Steckbrücke: Laden bis [V]", dn[:1]))
        out.append((f"Netzteil {tag} Steckbrücke: Ladestrom max. [A]", [imax]))

    # 3) Sonde einschalten: SENS_EN-Sprung nach 20 ms, bei voller und fast leerer Zelle
    for cell in (3.3, 2.9):
        sc = Scenario(f"Sonde, Zelle {cell} V", sun=0, temp=20, v_cell=cell, probe_ma=30)
        net = netlist(sc, ".tran 20u 0.12", save=SAVE).replace(
            "Bsens N_SENSDRV 0 V = 0", "Bsens N_SENSDRV 0 V = (time>20m ? V(N_XIAO_3V3) : 0)")
        r = ng.run(net)
        tt, v = r["time"], r["n_v12_probe"]
        t90 = next((tt[i] - 0.02 for i in range(len(v)) if tt[i] > 0.02 and v[i] >= 0.9 * 12.4), float("nan"))
        ipk = max(abs(x) for x in r["vam_q5#branch"])
        vgs = min(a - b for a, b in zip(r["n_psw_g"], r["n_v12_raw"]))
        out.append((f"Sonde 30 mA, Zelle {cell} V: V12_PROBE Endwert [V]", [v[-1]]))
        out.append((f"Sonde 30 mA, Zelle {cell} V: Anstieg auf 90 % [ms]", [t90 * 1000]))
        out.append((f"Sonde 30 mA, Zelle {cell} V: Spitzenstrom Q5 [A]", [ipk]))
        out.append((f"Sonde 30 mA, Zelle {cell} V: Ugs Q5 min [V]", [vgs]))
        if cell == 3.3:
            fig, ax = plt.subplots(figsize=(9, 3.5))
            ax.plot([x * 1000 for x in tt], v, label="V12_PROBE")
            ax.plot([x * 1000 for x in tt], r["n_v12_raw"], label="V12_RAW")
            ax.plot([x * 1000 for x in tt], r["n_sens_en"], label="SENS_EN")
            ax.set_xlabel("t [ms]")
            ax.set_ylabel("V")
            ax.legend()
            fig.tight_layout()
            fig.savefig(os.path.join(REPORT, "sonde_ein.png"), dpi=110)
            plt.close(fig)

    lines = ["# Schwellen und Verläufe (SPICE)", "", "| Größe | Wert |", "|---|---|"]
    for name, vals in out:
        lines.append(f"| {name} | {', '.join(f'{v:.3g}' for v in vals) if vals else '— (keine Schaltung)'} |")
    lines += ["", "![Temperatur](temperatur.png)", "", "![Sonde](sonde_ein.png)"]
    with open(os.path.join(REPORT, "sweeps.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    for name, vals in out:
        print(f"{name:55s} {', '.join(f'{v:.3g}' for v in vals) if vals else '—'}")


if __name__ == "__main__":
    main()
