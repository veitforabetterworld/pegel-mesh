"""Winter-Energiebilanz kleinerer Ladetechnik mit Deep-Sleep-Firmware (PVGIS stündlich, 2005-2023).

    py -3.12 -X utf8 winter_variants.py mittelgebirge 60
    py -3.12 -X utf8 winter_variants.py flachland 900 90

Argumente: Region, Messabstand in s, Leistung des Sondenzweigs aus dem Akku in mW (Vorgabe 100).
Wetter, Verschattung und Wärmeknoten wie winter_energy.py; keine Heizung.

Varianten:
  lfp6v   LiFePO4, 6-V-Modul (12 Zellen), linearer LiFePO4-Lader mit Eingangsspannungsregelung (4,6 V) und NTC
          (lädt erst ab 0 °C), Ladestrom max. 0,5 A
  xiao5v  Li-Ionen, 5-V-USB-Panel (6-V-Zellen mit eingebautem 5-V-Regler), Lader des XIAO (BQ25101, 100 mA, kein
          NTC: lädt auch unter 0 °C). Der Regler des Panels fällt unter ~20 mA Ausgangsstrom aus.
  xiao5v_sw  wie xiao5v, Laden per Firmware gesperrt (P0.13 HIGH) unter +5 °C und über 40 °C, gemessen mit dem
          Temperatursensor im nRF52840 (±5 °C, daher 5 °C Abstand zur 0-°C-Grenze)
  xiao5v_ntc wie xiao5v_sw, aber mit eigenem NTC am Akku (braucht einen freien Analog-Pin, z. B. XIAO Plus):
          Sperre unter 0 °C
"""
import sys

import numpy as np

from winter_energy import SHADE_DIFFUSE, SYS_LOSS, G_TH, season_arrays, LOADS  # noqa: F401  (Wetterdaten)

INTERVAL = float(sys.argv[2]) if len(sys.argv) > 2 else 60
P_PROBE = (float(sys.argv[3]) if len(sys.argv) > 3 else 100) / 1000   # W aus dem Akku, solange die Sonde an ist

# --- Verbraucher mit Deep-Sleep-Firmware (Schätzung, nach dem Umbau messen) ---
P_SLEEP = 3.3 * 30e-6                 # nRF52 im Schlaf, SX1262 Sleep, QSPI-Flash, Leckströme
T_PROBE = 2.1                         # s Sonde an je Messung (Vorlauf 2 s + Abfrage)
E_TX = 3.3 * 0.120 * 0.30             # J: ein Block, ~0,3 s Airtime bei 22 dBm
E_AWAKE = 3.3 * (0.0055 + 0.003) * 3  # J: ~3 s Funk auf Empfang (Quittung) und CPU wach
E_HOURLY = E_TX + E_AWAKE             # J je Stunde: Pfadprüfung
P_MEAN = P_SLEEP + (P_PROBE * T_PROBE + E_TX + E_AWAKE) / INTERVAL + E_HOURLY / 3600
P_LOW = P_SLEEP + (E_TX + E_AWAKE) / INTERVAL + E_HOURLY / 3600   # Akku fast leer: Sonde aus, nur Fehlercode


def panel_iv(G, Tc, wp, ncell, vmp_cell=0.5, voc_cell=0.6):
    """Isc, Voc und Kennlinienparameter eines Moduls mit ncell Zellen."""
    vmp, voc0 = ncell * vmp_cell, ncell * voc_cell
    isc_ratio = 1.08
    c2 = (vmp / voc0 - 1) / np.log(1 - 1 / isc_ratio)
    c1 = (1 - 1 / isc_ratio) * np.exp(-vmp / (c2 * voc0))
    n_vt = ncell * 1.3 * 0.0257
    g = np.maximum(G, 0) / 1000
    isc = wp / vmp * isc_ratio * g * (1 + 0.0005 * (Tc - 25)) * SYS_LOSS
    voc = np.where(g > 1e-3, voc0 * (1 - 0.0032 * (Tc - 25)) + n_vt * np.log(np.maximum(g, 1e-3)), 0)
    return isc, np.maximum(voc, 0), c1, c2


def i_at(v, isc, voc, c1, c2):
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        i = isc * (1 - c1 * (np.exp(v / (c2 * np.where(voc > 0, voc, 1))) - 1))
    return np.where((voc > v) & (isc > 0), np.maximum(i, 0), 0)


VARIANTS = {
    # Name: (Zellen im Modul, Akku-Nennspannung, Ah je Akku-Option, Ladefunktion)
    "lfp6v": dict(ncell=12, v_bat=3.2, caps=[1.5, 3.0, 6.0], panels=[1, 2, 3, 5]),
    "xiao5v": dict(ncell=12, v_bat=3.7, caps=[1.0, 2.0, 3.0], panels=[1, 2, 3, 5]),
    "xiao5v_sw": dict(ncell=12, v_bat=3.7, caps=[1.0, 2.0, 3.0, 6.0], panels=[1, 2, 3, 5]),
    "xiao5v_ntc": dict(ncell=12, v_bat=3.7, caps=[1.0, 2.0, 3.0, 6.0], panels=[1, 2, 3, 5]),
}


def charge_power(name, isc, voc, c1, c2, v_bat, t_bat):
    """Leistung in den Akku (W) und ob gerade unter 0 °C geladen wird."""
    if name == "lfp6v":
        # Linearer Lader: Panel wird auf mind. 4,6 V gehalten, Strom = Panelstrom dort, max. 0,5 A
        i = np.minimum(i_at(4.6, isc, voc, c1, c2), 0.5)
        i = np.where(t_bat < 0, 0, i)                   # NTC: Ladesperre unter 0 °C
        return i * v_bat * 0.97, np.zeros_like(i, bool)
    # xiao5v: Regler im Panel (Abwärtswandler, 85 %) aus dem Arbeitspunkt bei 5,6 V, dann BQ25101 linear 100 mA
    p_out = i_at(5.6, isc, voc, c1, c2) * 5.6 * 0.85
    i5 = p_out / 5.0
    i = np.where(i5 < 0.020, 0, np.minimum(i5, 0.100))   # Regler fällt bei schwachem Licht aus
    if name == "xiao5v_sw":
        i = np.where((t_bat < 5) | (t_bat > 40), 0, i)
    if name == "xiao5v_ntc":
        i = np.where((t_bat < 0) | (t_bat > 45), 0, i)
    return i * v_bat * 0.97, (i > 0) & (t_bat < 0)


def run(name, G, T):
    v = VARIANTS[name]
    cfg = [(wp, ah, gname) for wp in v["panels"] for ah in v["caps"] for gname in G_TH]
    K, (nsw, nh) = len(cfg), G.shape
    wp = np.array([c[0] for c in cfg], float)[:, None]
    cap = np.array([c[1] for c in cfg], float)[:, None] * v["v_bat"] * 0.8      # Wh, gealtert auf 80 %
    gth = np.array([G_TH[c[2]] for c in cfg])[:, None]
    cth = 200 + 60 * np.array([c[1] for c in cfg], float)[:, None]              # J/K, Box und Akku

    soc = np.ones((K, nsw)) * cap
    temp = np.ones((K, nsw)) * T[:, :1][None, :, 0]
    probe_ok = np.ones((K, nsw), bool)
    soc_min = soc.copy()
    h_probe_off = np.zeros((K, nsw))
    h_dead = np.zeros((K, nsw))
    h_cold_chg = np.zeros((K, nsw))
    e_chg = np.zeros((K, nsw))

    sub, dt = 12, 300.0
    for h in range(nh):
        g = G[:, h][None, :]
        ta = T[:, h][None, :]
        isc, voc, c1, c2 = panel_iv(g, ta + 0.03 * g, wp, v["ncell"])
        for _ in range(sub):
            pin, cold = charge_power(name, isc, voc, c1, c2, v["v_bat"], temp)
            probe_ok = np.where(soc < 0.05 * cap, False, np.where(soc > 0.10 * cap, True, probe_ok))
            pl = np.where(soc <= 0, 0, np.where(probe_ok, P_MEAN, P_LOW))
            net = pin - pl
            stored = np.where(net > 0, np.minimum(net * 0.96 * dt / 3600, cap - soc), net * dt / 3600)
            soc = np.maximum(soc + stored, 0)
            e_chg += np.where(net > 0, stored, 0)
            temp = temp + dt / cth * (pl - gth * (temp - ta))
            soc_min = np.minimum(soc_min, soc)
            h_probe_off += (~probe_ok) * dt / 3600
            h_dead += (soc <= 0) * dt / 3600
            h_cold_chg += cold * dt / 3600
    return cfg, cap, soc_min, h_probe_off, h_dead, h_cold_chg, e_chg


if __name__ == "__main__":
    G, T, labels = season_arrays()
    print(f"Region {sys.argv[1] if len(sys.argv) > 1 else 'mittelgebirge'}, {len(labels)} Winter (Ort x Jahr), "
          f"Messung alle {INTERVAL:.0f} s, Sonde {P_PROBE * 1000:.0f} mW")
    print(f"Mittlerer Verbrauch {P_MEAN * 1000:.2f} mW = {P_MEAN / 3.3 * 1000:.2f} mA bei 3,3 V "
          f"({P_MEAN * 24:.3f} Wh/Tag); Akku fast leer {P_LOW * 1000:.2f} mW")
    for name in VARIANTS:
        cfg, cap, soc_min, h_off, h_dead, h_cold, e_chg = run(name, G, T)
        print()
        print(f"[{name}]  Panel  Akku    Box        | min SoC schlechtester / Median | Winter mit Ausfall | "
              f"Std tot max | Std Sonde aus max | Std Laden < 0 °C")
        for k, (wp, ah, gname) in enumerate(cfg):
            sm = soc_min[k] / cap[k]
            print(f"{'':8s}{wp:3d} W {ah:4.1f} Ah {gname.split()[0]:9s} | {sm.min() * 100:5.1f} % / {np.median(sm) * 100:5.1f} %"
                  f"           | {(h_dead[k] > 0).sum():3d}/{len(labels)}           | {h_dead[k].max():6.0f}      "
                  f"| {h_off[k].max():6.0f}            | {h_cold[k].mean():6.0f}")
