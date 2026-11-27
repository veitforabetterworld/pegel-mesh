#!/usr/bin/env python3
"""Waermedaemmung pegel-sender-Gehaeuse: Rechnung zum Kammeraufbau (Werte wie in pegel_sender_gehaeuse.scad).

Luftschichten nach ISO 6946 (ruhend, unbelueftet): R_a = 1 / (h_a + h_r)
  h_a = max(1,25; 0,025 / d)   Leitung der Luft (bei d < 6 mm unabhaengig von der Waermestromrichtung)
  h_r = E * 4 sigma Tm^3       Strahlung, E = 1/(1/e1 + 1/e2 - 1) = 0,82 fuer PETG (e = 0,9), Tm = 10 degC -> 4,2
  (ergibt die Tabellenwerte der Norm: 5 mm -> 0,11; 10 mm -> 0,15)
Stege als Waermebruecken: ISO-6946-Verfahren fuer inhomogene Schichten,
  R' (obere Grenze, parallele Pfade durch die ganze Wand; Stege benachbarter Lagen versetzt)
  R'' (untere Grenze, jede Lage fuer sich gemittelt), R = (R' + R'') / 2.
Alles hier ist Rechnung/Schaetzung, nichts davon ist gemessen.
"""
from math import comb

LAM = 0.20       # PETG massiv (Literatur 0,20-0,29; 0,20 guenstig, 0,25 siehe unten)
HR = 4.2         # Strahlungsanteil W/(m2K)
RSI, RSE = 0.13, 0.04

# Wandaufbau (wie im SCAD)
t, k_n, k_s, k_si, k_so, k_rib = 25.0, 7, 0.6, 1.2, 1.6, 0.6
k_d = (t - k_si - k_so - (k_n - 1) * k_s) / k_n


def r_air(d_mm):
    return 1 / (max(1.25, 0.025 / (d_mm / 1000)) + HR)


def section(pitch, lam=LAM):
    """Regelquerschnitt: gibt (R0 ohne Stege, R', R'', R) in m2K/W."""
    ra = r_air(k_d)
    r_solid = ((k_n - 1) * k_s + k_si + k_so) / 1000 / lam
    r0 = k_n * ra + r_solid
    f = k_rib / pitch                      # Flaechenanteil Stege je Lage
    r_rib = k_d / 1000 / lam
    # R'': jede Kammerlage homogenisiert
    r2 = k_n / ((1 - f) / ra + f / r_rib) + r_solid
    # R': Pfad trifft j Stege (Lagen unabhaengig versetzt)
    inv = sum(comb(k_n, j) * f**j * (1 - f)**(k_n - j) / (r0 - j * (ra - r_rib)) for j in range(k_n + 1))
    r1 = 1 / inv
    return r0, r1, r2, (r1 + r2) / 2


def main():
    print(f"Kammer k_d = {k_d:.2f} mm, R_Luft = {r_air(k_d):.4f} m2K/W  (ISO-Tabelle 5 mm: {r_air(5):.3f})")
    res = {}
    for name, pitch in (("Wand (Stege alle 30 mm)", 30), ("Front/Deckel (Stege alle 10 mm)", 10)):
        r0, r1, r2, r = section(pitch)
        res[name] = r
        print(f"{name}: R ohne Stege {r0:.3f} -> lam {t/1000/r0:.4f};  R' {r1:.3f}  R'' {r2:.3f}  "
              f"R {r:.3f} -> lam_eff {t/1000/r:.4f}  (obere Grenze lam {t/1000/r1:.4f})")
        _, _, _, rr = section(pitch, 0.25)
        print(f"   mit lam_PETG 0,25: lam_eff {t/1000/rr:.4f}")
    for lam_eps in (0.035, 0.040):
        print(f"2 cm EPS lam {lam_eps}: R = {0.02/lam_eps:.3f} m2K/W")

    # ---- ganzes Gehaeuse (Innenmass 128 x 114 x 36 mm) ----
    a, b, c = 0.128, 0.114, 0.036
    tm = t / 1000
    lw = tm / res["Wand (Stege alle 30 mm)"]
    lp = tm / res["Front/Deckel (Stege alle 10 mm)"]
    # Formfaktor dickwandiger Kasten (Langmuir): S = A/t + 0,54 * Kanten + 0,15 * t je Ecke
    a_wall, a_plate = 2 * (a + b) * c, 2 * a * b
    edges_plate = 2 * 2 * (a + b)          # Kanten Front/Wand und Bodendeckel/Wand
    edges_wall = 4 * c
    g_cond = (lw * a_wall + lp * a_plate) / tm + 0.54 * ((lw + lp) / 2 * edges_plate + lw * edges_wall) + 0.15 * tm * 8 * (lw + lp) / 2
    a_in = a_wall + a_plate
    a_out = 2 * ((a + 2 * tm) * (b + 2 * tm) + (a + 2 * tm) * (c + 2 * tm) + (b + 2 * tm) * (c + 2 * tm))
    ua_regel = 1 / (RSI / a_in + 1 / g_cond + RSE / a_out)
    # ---- Waermebruecken (Abschaetzung) ----
    p_mid = 2 * (a + b + 2 * tm)                                   # Umfang Wandmitte
    br = {
        "Fuge hinten (1,2 mm Dichtrand + 1,2 mm Deckelhaut + massive Lage 0 unter der Dichtung)": 0.020 * p_mid,
        "Aussparungen Klemmendeckel (Haut 1,2 + 1,6 mm ueber 25 mm, ca. 0,34 m)": LAM * 2.8e-3 / tm * 0.34,
        "3 Verschraubungstaschen (4 mm Wand + Huelse)": 3 * 0.0024,
        "USB-Tunnel mit duennem Deckel": 0.0006,
        "12 Schraubentaschen (Boden 4 mm)": 12 * 0.0003,
        "Antennentasche, Einschmelzhuelsen": 0.001,
    }
    ua = ua_regel + sum(br.values())
    print(f"\nGehaeuse: Formfaktor-Leitwert {g_cond:.3f} W/K, mit Rsi/Rse UA_regel = {ua_regel:.3f} W/K")
    for k, v in br.items():
        print(f"  + {v:.4f} W/K  {k}")
    print(f"UA gesamt ca. {ua:.3f} W/K  (R_ges = {1/ua:.1f} K/W)")
    for lam_eps in (0.035, 0.040):
        te = 0.020
        ge = lam_eps * ((a_in) / te + 0.54 * (edges_plate + edges_wall) + 0.15 * te * 8)
        ae = 2 * ((a + 2 * te) * (b + 2 * te) + (a + 2 * te) * (c + 2 * te) + (b + 2 * te) * (c + 2 * te))
        print(f"Vergleich 2 cm EPS lam {lam_eps}, ohne Bruecken: UA = {1/(RSI/a_in + 1/ge + RSE/ae):.3f} W/K")
    for p in (1.0, 2.1):
        print(f"Heizleistung {p} W -> Innen ca. {p/ua:.0f} K ueber aussen (stationaer)")


if __name__ == "__main__":
    main()
