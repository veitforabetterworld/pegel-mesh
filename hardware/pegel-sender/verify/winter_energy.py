"""Winter-Energiebilanz des Pegel-Senders mit stündlichen PVGIS-Daten (SARAH3/ERA5, 2005-2023).

    py -3.12 -X utf8 winter_energy.py mittelgebirge 60
    py -3.12 -X utf8 winter_energy.py flachland 900

Zweites Argument: Messabstand in Sekunden (je Messung ein Paket). Die PVGIS-Daten (~18 MB je Ort) werden
beim ersten Lauf nach build/pvgis geladen.

Je Ort und Winter (1. Okt - 30. Apr), 5-min-Schritte: Panel (I-U-Kennlinie, Temperatur, Schwachlicht),
halber Tag verschattet, Heizung 65 Ohm parallel am Panel, Ladesperre/Heizung per NTC am Akku,
Wärmeknoten Akku+Platine in der Box, Lader CN3795 (MPPT 18 V, max. 3 A), LiFePO4 gealtert auf 80 %.
"""
import json
import sys
import urllib.request
from pathlib import Path

import numpy as np

DATA = Path(__file__).resolve().parent.parent / "build" / "pvgis"
POS = {"winterberg": (51.194, 8.532), "clausthal": (51.806, 10.336), "annaberg": (50.580, 13.003),
       "zwiesel": (49.016, 13.233), "nuernberg": (49.452, 11.077)}
REGIONS = {"mittelgebirge": ["winterberg", "clausthal", "annaberg", "zwiesel"], "flachland": ["nuernberg"]}
SITES = REGIONS[sys.argv[1] if len(sys.argv) > 1 else "mittelgebirge"]
INTERVAL = float(sys.argv[2]) if len(sys.argv) > 2 else 60

# --- Verbraucher (W aus dem Akku) ---
P_BASE = 3.3 * 0.006 + 3.3 * 0.00002                 # XIAO + SX1262 in RX direkt aus dem Akku, Teiler
P_TX = 3.3 * 0.120 * 0.38 / INTERVAL + 0.0002         # 1 Paket je Messung, 0,38 s Airtime bei 22 dBm, + Pfadprüfung
P_PROBE = 12.46 * 0.030 / 0.85 + 3.3 * 0.0013         # Sonde 30 mA an 12,46 V, TPS61040 85 %, SP3485
LOADS = {"Sonde 2,1 s je Messung": 2.1 / INTERVAL}
P_LOW = P_BASE + P_TX                                 # unter 2,8 V: Sonde aus, nur Fehlercode

# --- Panel (36 Zellen, 12-V-Klasse) ---
VMP, VOC = 18.0, 22.0
IMP_PER_W = 1 / VMP
ISC_RATIO = 1.08
C2 = (VMP / VOC - 1) / np.log(1 - 1 / ISC_RATIO)
C1 = (1 - 1 / ISC_RATIO) * np.exp(-VMP / (C2 * VOC))
N_VT = 36 * 1.3 * 0.0257
SYS_LOSS = 0.90            # Verschmutzung, Fehlanpassung, Leitungen
V_MPPT = 17.2              # Panel-Arbeitspunkt der Regelung (LM324, Kanal B)
R_HEAT = 68.0              # Heizwiderstand am Akku (J4)
ETA_CHG = 0.85             # TPS5430 mit Rückstromsperre und Shunt
P_CHG_MAX_OUT = 2.0 * 3.4  # Ladestrom 2 A
P_CTRL = 17.2 * 0.004      # Regelung (HT7550, LM324, CJ431) aus dem Panel, nur bei Sonne
ETA_BAT = 0.96

# --- Wärme ---
T_HEAT_ON, T_HEAT_OFF = 3.75, 5.16
T_INH_ON, T_INH_OFF = 1.15, 2.69

PANELS = [5, 10, 15, 20, 30]
CELLS = [1, 2, 3]
G_TH = {"gedämmt (0,15 W/K)": 0.15, "ungedämmt (0,4 W/K)": 0.4}
SHADE_DIFFUSE = 0.5


def load_site(name):
    path = DATA / f"{name}.json"
    if not path.exists():
        DATA.mkdir(parents=True, exist_ok=True)
        lat, lon = POS[name]
        url = (f"https://re.jrc.ec.europa.eu/api/v5_3/seriescalc?lat={lat}&lon={lon}&startyear=2005&endyear=2023"
               "&angle=45&aspect=0&components=1&outputformat=json&raddatabase=PVGIS-SARAH3")
        path.write_bytes(urllib.request.urlopen(url, timeout=300).read())
    rows = json.loads(path.read_text())["outputs"]["hourly"]
    t = np.array([np.datetime64(f"{r['time'][:4]}-{r['time'][4:6]}-{r['time'][6:8]}T{r['time'][9:11]}:00")
                  for r in rows])
    g = np.array([[r["Gb(i)"], r["Gd(i)"], r["Gr(i)"], r["T2m"]] for r in rows])
    return t, g


def season_arrays():
    """(Ort*Winter, Stunden) für Strahlung mit Verschattung und Lufttemperatur."""
    G, T, labels = [], [], []
    for s in SITES:
        t, g = load_site(s)
        hour_utc = (t - t.astype("datetime64[D]")).astype("timedelta64[h]").astype(int)
        solar = (hour_utc + 0.5 + POS[s][1] / 15) % 24
        shaded = solar < 12.0   # vormittags im Schatten
        gb, gd, gr, ta = g.T
        gtot = np.where(shaded, (gd + gr) * SHADE_DIFFUSE, gb + gd + gr)
        for y in range(2005, 2023):
            start = np.datetime64(f"{y}-10-01T00:00")
            i0 = int(np.searchsorted(t, start))
            n = 212 * 24
            G.append(gtot[i0:i0 + n])
            T.append(ta[i0:i0 + n])
            labels.append((s, y))
    return np.array(G), np.array(T), labels


def panel(G, Tc, wp):
    """Isc und Voc bei Einstrahlung G und Zelltemperatur Tc; Strom bei U: I(U)."""
    g = np.maximum(G, 0) / 1000
    isc = wp * IMP_PER_W * ISC_RATIO * g * (1 + 0.0005 * (Tc - 25)) * SYS_LOSS
    voc = np.where(g > 1e-3, VOC * (1 - 0.0032 * (Tc - 25)) + N_VT * np.log(np.maximum(g, 1e-3)), 0)
    return isc, np.maximum(voc, 0)


def i_at(v, isc, voc):
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        i = isc * (1 - C1 * (np.exp(v / (C2 * np.where(voc > 0, voc, 1))) - 1))
    return np.where((voc > v) & (isc > 0), np.maximum(i, 0), 0)


def heater_only_voltage(isc, voc):
    lo, hi = np.zeros_like(isc), voc.copy()
    for _ in range(25):
        mid = (lo + hi) / 2
        f = i_at(mid, isc, voc) - mid / R_HEAT
        lo, hi = np.where(f > 0, mid, lo), np.where(f > 0, hi, mid)
    return lo


def run():
    G, T, labels = season_arrays()
    nsw, nh = G.shape
    cfg = [(wp, n, load, gth) for wp in PANELS for n in CELLS for load in LOADS for gth in G_TH]
    K = len(cfg)
    wp = np.array([c[0] for c in cfg], float)[:, None]
    cells = np.array([c[1] for c in cfg], float)[:, None]
    duty = np.array([LOADS[c[2]] for c in cfg])[:, None]
    gth = np.array([G_TH[c[3]] for c in cfg])[:, None]

    cap = cells * 6.0 * 3.2 * 0.8                   # Wh, gealtert
    cth = 300 + 150 * cells                         # J/K
    p_on = P_BASE + P_TX + duty * P_PROBE
    p_loss_in = 0.03 + duty * (P_PROBE - 12.3 * 0.05)   # Abwärme in der Box

    soc = np.ones((K, nsw)) * cap
    temp = np.ones((K, nsw)) * T[:, :1][None, :, 0]
    heat = np.zeros((K, nsw), bool)
    inh = np.zeros((K, nsw), bool)
    probe_ok = np.ones((K, nsw), bool)
    soc_min = soc.copy()
    h_probe_off = np.zeros((K, nsw))
    h_dead = np.zeros((K, nsw))
    e_heat = np.zeros((K, nsw))
    e_chg = np.zeros((K, nsw))
    e_load = np.zeros((K, nsw))

    sub, dt = 12, 300.0
    for h in range(nh):
        g = G[:, h][None, :]
        ta = T[:, h][None, :]
        tc = ta + 0.03 * g
        isc, voc = panel(g, tc, wp)
        i18 = i_at(V_MPPT, isc, voc)
        p_free = np.maximum(i18 * V_MPPT - P_CTRL, 0)                      # Heizung aus
        p_shared = np.maximum((i18 - V_MPPT / R_HEAT) * V_MPPT - P_CTRL, 0)  # Heizung an und Panel trägt V_MPPT
        v_h = np.where(i18 >= V_MPPT / R_HEAT, V_MPPT, heater_only_voltage(isc, voc))
        p_h = np.where(v_h > 8.0, v_h ** 2 / R_HEAT, 0)          # Q7 schaltet erst ab ~8 V
        for _ in range(sub):
            heat = np.where(temp < T_HEAT_ON, True, np.where(temp > T_HEAT_OFF, False, heat))
            inh = np.where(temp < T_INH_ON, True, np.where(temp > T_INH_OFF, False, inh))
            ph = np.where(heat, p_h, 0)
            pin = np.where(inh, 0, np.where(heat, p_shared, p_free))
            pout = np.minimum(pin * ETA_CHG, P_CHG_MAX_OUT)
            probe_ok = np.where(soc < 0.05 * cap, False, np.where(soc > 0.10 * cap, True, probe_ok))
            pl = np.where(soc <= 0, 0, np.where(probe_ok, p_on, P_LOW))
            net = pout - pl
            room = cap - soc
            stored = np.where(net > 0, np.minimum(net * ETA_BAT * dt / 3600, room), net * dt / 3600)
            soc = np.maximum(soc + stored, 0)
            e_chg += np.where(net > 0, stored / ETA_BAT, 0)
            e_heat += ph * dt / 3600
            e_load += pl * dt / 3600
            temp = temp + dt / cth * (ph + p_loss_in - gth * (temp - ta))
            soc_min = np.minimum(soc_min, soc)
            h_probe_off += (~probe_ok) * dt / 3600
            h_dead += (soc <= 0) * dt / 3600
    return cfg, labels, cap, soc_min, h_probe_off, h_dead, e_heat, e_chg, e_load, G, T


def stats(G, T, labels):
    """Mittlere Tagesernte je Wp (18 V, ohne Heizung) und Temperatur je Monat."""
    out = []
    days = np.arange(212 * 24) // 24
    month_start = [0, 31, 61, 92, 123, 151, 182, 212]  # Okt..Apr (Feb mit 28 Tagen)
    names = ["Okt", "Nov", "Dez", "Jan", "Feb", "Mär", "Apr"]
    tc = T + 0.03 * G
    isc, voc = panel(G, tc, 1.0)
    p = i_at(V_MPPT, isc, voc) * V_MPPT * ETA_CHG       # Wh/h je Wp in den Akku
    for m, name in enumerate(names):
        sel = (days >= month_start[m]) & (days < month_start[m + 1])
        nd = month_start[m + 1] - month_start[m]
        per_day = p[:, sel].sum(1) / nd
        out.append((name, per_day.mean(), np.percentile(per_day, 10), T[:, sel].mean(), T[:, sel].min()))
    # schlechtestes 14-Tage-Fenster Nov-Feb
    daily = p.reshape(p.shape[0], 212, 24).sum(2)
    win = np.array([[daily[i, d:d + 14].mean() for d in range(31, 151 - 14)] for i in range(len(labels))])
    return out, win


if __name__ == "__main__":
    cfg, labels, cap, soc_min, h_off, h_dead, e_heat, e_chg, e_load, G, T = run()
    st, win = stats(G, T, labels)
    print(f"Verbrauch: {(P_BASE + P_TX + P_PROBE * 2.1 / INTERVAL) * 1000:.0f} mW")
    print("Monat  Wh/Wp/Tag (Mittel, 10%-Jahr)  T mittel  T min")
    for name, mean, p10, tm, tmin in st:
        print(f"{name}   {mean:.3f}  {p10:.3f}   {tm:5.1f}  {tmin:6.1f}")
    print("schlechteste 14 Tage (Wh/Wp/Tag):", round(win.min(), 3), "Median der Winter-Minima:",
          round(np.median(win.min(1)), 3))
    print()
    print("Panel Akku  Box  | min SoC worst / median | Winter mit Sonde aus | Std Sonde aus max | Std tot max | Heiz Wh | Lade Wh")
    for k, (wp, n, load, g) in enumerate(cfg):
        sm = soc_min[k] / cap[k]
        print(f"{wp:3d} W {n}x6Ah {g[:9]:9s} | {sm.min()*100:5.1f} % / {np.median(sm)*100:5.1f} % "
              f"| {(h_off[k] > 0).sum():2d}/{len(labels)} | {h_off[k].max():6.0f} | {h_dead[k].max():5.0f} "
              f"| {e_heat[k].mean():6.0f} | {e_chg[k].mean():6.0f}")
