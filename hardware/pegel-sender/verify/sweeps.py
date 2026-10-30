"""Verläufe: Temperatur, Netzteilspannung, Akkuspannung (langsame Rampen) und Einschalten der Sonde.

Schwellen werden beim Hoch- und Runterfahren gemessen, damit die Hysterese sichtbar ist. Bilder nach report/.
"""

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from board import Scenario, netlist  # noqa: E402
from ngspice import NgSpice  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPORT = os.path.join(HERE, "report")


def tri(lo, hi, t_half):
    """Dreieck lo → hi → lo über 2·t_half (Ausdruck in time)."""
    return f"({lo} + ({hi}-({lo}))*(1-abs(time/{t_half}-1)))"


def crossings(x, y, level):
    """x-Werte, an denen y die Schwelle steigend bzw. fallend kreuzt."""
    up, down = [], []
    for i in range(1, len(y)):
        if y[i - 1] < level <= y[i]:
            up.append(x[i])
        elif y[i - 1] >= level > y[i]:
            down.append(x[i])
    return up, down


SAVE = ["n_temp", "n_chg_csp", "n_vsys", "n_vsol", "n_chg_inhibit", "n_heat_off", "i:vam_q7", "n_dc_f",
        "n_mppt_en", "n_bat_p", "n_bat_n", "n_prot_od", "n_prot_oc", "n_p3v3", "n_v12_probe", "n_v12_raw",
        "n_sens_en", "n_psw_g", "i:vam_q4"]


def run(ng, sc, t_end, step, **kw):
    return ng.run(netlist(sc, f".tran {step} {t_end} 0 {step}", save=SAVE, **kw))


def main():
    ng = NgSpice()
    os.makedirs(REPORT, exist_ok=True)
    out = []

    # 1) Temperatur −25 → +10 → −25 °C bei Sonne
    sc = Scenario("Temperaturrampe", sun=1, temp=0, soc=0.5)
    r = run(ng, sc, 2.0, "2m", temp_expr=tri(-25, 10, 1.0), ramp="10m")
    t, time = r["n_temp"], r["time"]
    ichg = [(a - b) / 0.04 for a, b in zip(r["n_chg_csp"], r["n_vsys"])]
    iheat = r["vam_q7#branch"]
    # Zustände an den Strömen ablesen: Laden > 0,1 A, Heizen > 0,05 A. Anlauf (< 50 ms) auslassen.
    for name, sig, on_lbl, off_lbl in (("Laden", [i > 0.1 for i in ichg], "Laden frei", "Ladesperre"),
                                       ("Heizung", [abs(i) > 0.05 for i in iheat], "Heizung an", "Heizung aus")):
        warm = [(t[i], sig[i]) for i in range(1, len(t)) if 0.05 < time[i] <= 1.0 and sig[i] != sig[i - 1]]
        cold = [(t[i], sig[i]) for i in range(1, len(t)) if time[i] > 1.0 and sig[i] != sig[i - 1]]
        for phase, ev in (("beim Erwärmen", warm), ("beim Abkühlen", cold)):
            for temp, state in ev[:2]:
                out.append((f"{on_lbl if state else off_lbl} {phase} ab [°C]", [temp]))
    fig, ax = plt.subplots(3, 1, figsize=(9, 7), sharex=True)
    ax[0].plot(r["time"], t)
    ax[0].set_ylabel("Temperatur [°C]")
    ax[1].plot(r["time"], ichg, label="Ladestrom")
    ax[1].plot(r["time"], iheat, label="Heizstrom")
    ax[1].set_ylabel("Strom [A]")
    ax[1].legend()
    ax[2].plot(r["time"], r["n_chg_inhibit"], label="CHG_INHIBIT")
    ax[2].plot(r["time"], r["n_heat_off"], label="HEAT_OFF")
    ax[2].plot(r["time"], r["n_vsol"], label="VSOL")
    ax[2].set_ylabel("Spannung [V]")
    ax[2].legend()
    ax[2].set_xlabel("Simulationszeit (Rampe −25 → +10 → −25 °C)")
    fig.tight_layout()
    fig.savefig(os.path.join(REPORT, "temperatur.png"), dpi=110)
    plt.close(fig)

    # 2) Netzteil 0 → 15 → 0 V: Umschaltung MPPT-Arbeitspunkt
    sc = Scenario("Netzteilrampe", sun=0, temp=20, dc=tri(0, 15, 1.0), soc=0.5)
    r = run(ng, sc, 2.0, "2m")
    det = [v < 1.5 for v in r["n_mppt_en"]]   # MPPT_EN low: Netzteil erkannt
    up = [r["n_dc_f"][i] for i in range(1, len(det)) if 0.05 < r["time"][i] <= 1.0 and det[i] and not det[i - 1]]
    dn = [r["n_dc_f"][i] for i in range(1, len(det)) if r["time"][i] > 1.0 and det[i - 1] and not det[i]]
    out.append(("Netzteil erkannt ab DC_F [V]", up[:1]))
    out.append(("Netzteil nicht mehr erkannt unter DC_F [V]", dn[:1]))

    # 3) Zellspannung 3,9 → 1,9 → 3,4 V ohne Sonne
    sc = Scenario("Akkurampe", sun=0, temp=20, v_cell="(time<1 ? 3.9-2.0*time : 1.9+1.5*(time-1))")
    r = run(ng, sc, 2.0, "2m")
    cell = [a - b for a, b in zip(r["n_bat_p"], r["n_bat_n"])]
    od = [a - b for a, b in zip(r["n_prot_od"], r["n_bat_n"])]
    oc = [a - b for a, b in zip(r["n_prot_oc"], r["n_bat_n"])]
    tm = r["time"]
    # Zelle direkt aus der Rampe (BAT_N schwimmt, sobald der Entlade-FET sperrt)
    vc = [3.9 - 2.0 * x if x < 1 else 1.9 + 1.5 * (x - 1) for x in tm]
    oc_on = [vc[i] for i in range(1, len(tm)) if 0.02 < tm[i] <= 1 and oc[i - 1] < 1 <= oc[i]]
    od_off = [vc[i] for i in range(1, len(tm)) if 0.02 < tm[i] <= 1 and od[i - 1] >= 1 > od[i]]
    od_on = [vc[i] for i in range(1, len(tm)) if tm[i] > 1 and od[i - 1] < 1 <= od[i]]
    t_off = next((tm[i] for i in range(1, len(tm)) if 0.02 < tm[i] <= 1 and od[i - 1] >= 1 > od[i]), 1.0)
    v33_min = min(v for v, x in zip(r["n_p3v3"], tm) if 0.05 < x < t_off)
    out.append(("Lade-FET wieder an unter Zelle [V] (Überladeschutz)", oc_on[:1]))
    out.append(("Entlade-FET aus unter Zelle [V] (Tiefentladung)", od_off[:1]))
    out.append(("Entlade-FET wieder an über Zelle [V]", od_on[:1]))
    out.append(("+3V3 min. solange Akku verbunden [V]", [v33_min]))
    fig, ax = plt.subplots(2, 1, figsize=(9, 5.5), sharex=True)
    ax[0].plot(r["time"], cell, label="Zelle")
    ax[0].plot(r["time"], r["n_vsys"], label="VSYS")
    ax[0].plot(r["time"], r["n_p3v3"], label="+3V3")
    ax[0].legend()
    ax[0].set_ylabel("Spannung [V]")
    ax[1].plot(r["time"], od, label="OD (Entlade-FET)")
    ax[1].plot(r["time"], oc, label="OC (Lade-FET)")
    ax[1].legend()
    ax[1].set_ylabel("Gate [V]")
    ax[1].set_xlabel("Simulationszeit (Zelle 3,9 → 1,9 → 3,4 V)")
    fig.tight_layout()
    fig.savefig(os.path.join(REPORT, "akkuschutz.png"), dpi=110)
    plt.close(fig)

    # 4) Sonde einschalten: SENS_EN-Sprung nach 20 ms
    for ma in (30, 80, 200):   # Sonde: 30–80 mA je Messung, Spitze bis 200 mA
        sc = Scenario(f"Sonde {ma} mA", sun=0, temp=20, soc=0.5, probe_ma=ma)
        # SENS_EN-Treiber auf den Puls umhängen
        net = netlist(sc, ".tran 20u 0.12", save=SAVE).replace("Bsens N_SENSDRV 0 V = 0", "Bsens N_SENSDRV 0 V = (time>20m ? 3.3 : 0)")
        r = ng.run(net)
        tt, v = r["time"], r["n_v12_probe"]
        target = 0.9 * max(v)
        t90 = next((tt[i] - 0.02 for i in range(len(v)) if tt[i] > 0.02 and v[i] >= target), float("nan"))
        ipk = max(abs(x) for x in r["vam_q4#branch"])
        vgs = min(a - b for a, b in zip(r["n_psw_g"], r["n_v12_raw"]))
        out.append((f"Sonde {ma} mA: V12_PROBE Endwert [V]", [v[-1]]))
        out.append((f"Sonde {ma} mA: Anstieg auf 90 % [ms]", [t90 * 1000]))
        out.append((f"Sonde {ma} mA: Spitzenstrom Q4 [A]", [ipk]))
        out.append((f"Sonde {ma} mA: Ugs Q4 min [V]", [vgs]))
        if ma == 80:
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
    lines += ["", "![Temperatur](temperatur.png)", "", "![Akkuschutz](akkuschutz.png)", "", "![Sonde](sonde_ein.png)"]
    with open(os.path.join(REPORT, "sweeps.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    for name, vals in out:
        print(f"{name:55s} {', '.join(f'{v:.3g}' for v in vals) if vals else '—'}")


if __name__ == "__main__":
    main()
