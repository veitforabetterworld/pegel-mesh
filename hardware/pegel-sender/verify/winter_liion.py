"""Winter-Energiebilanz mit Li-Ionen-Akku am Lader des XIAO, kleiner Akkuheizung und 3 cm Dämmung.

    py -3.12 -X utf8 winter_liion.py mittelgebirge 60
    py -3.12 -X utf8 winter_liion.py flachland 900 90

Argumente: Region, Messabstand in s, Leistung des Sondenzweigs aus dem Akku in mW (Vorgabe 100).
Wetter und Verschattung wie winter_energy.py (PVGIS stündlich 2005-2023, Okt-Apr).

Modell:
- Panel: 5-V-USB-Panel (12 Zellen, eingebauter Abwärtsregler 85 %, fällt unter 20 mA aus).
- Lader: BQ25101 im XIAO, 100 mA, linear. Firmware sperrt ihn (P0.13 HIGH) unter der Ladegrenze und über 45 °C,
  gemessen mit einem NTC am Akku (XIAO Plus, ±1 °C).
- Heizung: Widerstand am 5-V-Ausgang des Panels, per MOSFET unter Heizgrenze + 1 K (Hysterese 2 K), nur aus dem
  Panel (nachts aus). Die Heizung hat Vorrang vor dem Laden.
- Wärme: Akku und Platine in 3 cm EPS (λ 0,035 W/mK, Innenmaß ~10 x 8 x 5 cm): 0,04 W/K zur Luft. Keine
  Sonneneinstrahlung aufs Gehäuse (pessimistisch).
- Akku: Li-Ionen, gealtert auf 80 %. Selbstentladung 2 %/Monat bei 20 °C, halbiert je 10 K kälter, dazu 5 µA
  Schutzschaltung. Nutzbare Kapazität sinkt mit der Kälte (Restladung, die bei der Temperatur nicht mehr
  herauskommt): 25 °C 100 %, 0 °C 90 %, -10 °C 80 %, -20 °C 65 %.
"""
import sys

import numpy as np

from winter_energy import season_arrays
from winter_variants import panel_iv, i_at

INTERVAL = float(sys.argv[2]) if len(sys.argv) > 2 else 60
P_PROBE = (float(sys.argv[3]) if len(sys.argv) > 3 else 100) / 1000

# --- Verbraucher mit Deep-Sleep-Firmware (wie winter_variants.py) ---
P_SLEEP = 3.3 * 30e-6
E_MEAS = P_PROBE * 2.1 + 3.3 * 0.120 * 0.30 + 3.3 * 0.0085 * 3     # J je Messung: Sonde, Senden, wach
E_HOURLY = 3.3 * 0.120 * 0.30 + 3.3 * 0.0085 * 3                   # J je Stunde: Pfadprüfung
P_MEAN = P_SLEEP + E_MEAS / INTERVAL + E_HOURLY / 3600
P_LOW = P_SLEEP + (E_MEAS - P_PROBE * 2.1) / INTERVAL + E_HOURLY / 3600

V_BAT = 3.7
G_BOX = 0.04                       # W/K durch die Dämmung
SELF_DIS = 0.02 / (30 * 24)        # Anteil je Stunde bei 20 °C
P_PROT = 3.7 * 5e-6
COLD_T = np.array([-40, -20, -10, 0, 25])
COLD_F = np.array([0.40, 0.65, 0.80, 0.90, 1.00])

PANELS = [1, 2, 3]
CAPS = [1.0, 2.0, 3.0, 6.0]
HEATERS = [0.0, 0.25, 0.5]         # W aus dem Panel
CHG_MIN = [0.0, 2.0]               # °C Ladegrenze


def run(G, T):
    cfg = [(wp, ah, ph, tc) for wp in PANELS for ah in CAPS for ph in HEATERS for tc in CHG_MIN]
    K, (nsw, nh) = len(cfg), G.shape
    col = lambda i: np.array([c[i] for c in cfg], float)[:, None]   # noqa: E731
    wp, ah, p_heat, t_chg = col(0), col(1), col(2), col(3)
    cap = ah * V_BAT * 0.8
    cth = 40 + 15 * ah                   # J/K: Akku (~15 J/K je Ah), Platine, Luft
    soc = np.ones((K, nsw)) * cap
    temp = np.ones((K, nsw)) * T[:, :1][None, :, 0]
    heat = np.zeros((K, nsw), bool)
    probe_ok = np.ones((K, nsw), bool)
    avail_min = np.ones((K, nsw))
    h_dead = np.zeros((K, nsw))
    h_off = np.zeros((K, nsw))
    e_heat = np.zeros((K, nsw))
    t_min = temp.copy()

    sub, dt = 12, 300.0
    for h in range(nh):
        g = G[:, h][None, :]
        ta = T[:, h][None, :]
        isc, voc, c1, c2 = panel_iv(g, ta + 0.03 * g, wp, 12)
        p5 = i_at(5.6, isc, voc, c1, c2) * 5.6 * 0.85
        p5 = np.where(p5 / 5.0 < 0.020, 0, p5)                      # Regler im Panel fällt aus
        for _ in range(sub):
            heat = np.where(temp < t_chg + 1, True, np.where(temp > t_chg + 3, False, heat))
            ph = np.where(heat, np.minimum(p_heat, p5), 0)
            chg_ok = (temp >= t_chg) & (temp <= 45)
            pin = np.where(chg_ok, np.minimum((p5 - ph) / 5.0, 0.100) * V_BAT * 0.97, 0)
            pin = np.maximum(pin, 0)
            f = np.interp(temp, COLD_T, COLD_F)
            unusable = (1 - f) * cap
            avail = soc - unusable
            probe_ok = np.where(avail < 0.05 * cap, False, np.where(avail > 0.10 * cap, True, probe_ok))
            alive = avail > 0
            pl = np.where(alive, np.where(probe_ok, P_MEAN, P_LOW), 0)
            p_self = soc * SELF_DIS / 3600 * 2 ** ((temp - 20) / 10) + P_PROT
            net = pin - pl - p_self
            stored = np.where(net > 0, np.minimum(net * 0.96 * dt / 3600, cap - soc), net * dt / 3600)
            soc = np.maximum(soc + stored, 0)
            temp = temp + dt / cth * (ph + pl - G_BOX * (temp - ta))
            avail_min = np.minimum(avail_min, np.maximum(avail, 0) / cap)
            h_dead += (~alive) * dt / 3600
            h_off += (~probe_ok) * dt / 3600
            e_heat += ph * dt / 3600
            t_min = np.minimum(t_min, temp)
    return cfg, avail_min, h_dead, h_off, e_heat, t_min


if __name__ == "__main__":
    G, T, labels = season_arrays()
    print(f"Region {sys.argv[1] if len(sys.argv) > 1 else 'mittelgebirge'}, {len(labels)} Winter, Messung alle "
          f"{INTERVAL:.0f} s, Sonde {P_PROBE * 1000:.0f} mW, Verbrauch {P_MEAN * 1000:.2f} mW "
          f"({P_MEAN / 3.7 * 1000:.2f} mA bei 3,7 V)")
    cfg, avail_min, h_dead, h_off, e_heat, t_min = run(G, T)
    print("Panel  Akku   Heizung Laden ab | nutzbar min schlechtester / Median | Winter mit Ausfall | Std tot max "
          "| Heizung Wh/Winter | Akku min °C")
    for k, (wp, ah, ph, tc) in enumerate(cfg):
        a = avail_min[k]
        print(f"{wp:3d} W {ah:4.1f} Ah {ph:4.2f} W  {tc:3.0f} °C  | {a.min() * 100:5.1f} % / {np.median(a) * 100:5.1f} %"
              f"                  | {(h_dead[k] > 0).sum():3d}/{len(labels)}             | {h_dead[k].max():6.0f}      "
              f"| {e_heat[k].mean():6.1f}            | {t_min[k].min():6.1f}")
