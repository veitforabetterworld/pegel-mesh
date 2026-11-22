"""Thermolader 5 V, die 5-V-Ladeplatine (Stapel, unten): 5 V aus USB-C-Netzteil oder -Solarpanel, Frostschutz ohne Firmware.

Den Li-Ionen-Akku an den BAT-Pads des XIAO lädt dessen BQ25101. Diese Platine legt die 5 V an den 5V-Pin des XIAO,
solange der Akku zwischen ~2,5 und ~42 °C hat. Darunter trennt sie den Lader und heizt mit 5 × 300 Ω (0,42 W, nur
aus dem 5-V-Eingang, nachts nie aus dem Akku), bis der Akku wieder ~4,6 °C hat. Eine Hälfte eines LM393 vergleicht dafür den
NTC am Akku (J4) mit einer Schwelle; der XIAO weiß von der Temperaturregelung nichts. Ohne NTC gilt "sehr kalt": kein
Laden, Heizung an, solange 5 V anliegen. Die zweite Hälfte trennt über ~42 °C den Lader bis ~37 °C (Q3).

Umriss wie der XIAO, keine Bohrungen, 5 V und NTC an Lötpads auf der Unterseite. Akku unter die Platine,
zu Stiftenden und Pads isoliert; NTC an den Akku.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from parts import GND, R0603, R1206, Netlist  # noqa: E402
from stack import j5_pins, j6_pins  # noqa: E402

N = Netlist()
r, c, add, nmos, pmos = N.r, N.c, N.add, N.nmos, N.pmos
PADS2_B = "pegel:SolderPads_1x02_B_1.8x1.8mm_P2.54mm"

# --- 5 V Eingang ----------------------------------------------------------------
g = "input"
add("J1", "Connector_Generic:Conn_01x02", PADS2_B, "5V IN", "Lötpads unten: 5 V + GND",
    {"1": "VIN_RAW", "2": GND}, g, hand=True)
pmos("Q1", GND, "VIN_RAW", "V5", g)               # Verpolschutz ohne Spannungsverlust
add("D1", "Device:D_TVS", "Diode_SMD:D_SMA", "SMAJ5.0A", "SMAJ5.0A (5 V, 400 W)", {"1": "V5", "2": GND}, g,
    lcsc="C19077523")
c("C1", "10uF 10V", "V5", GND, g)

# --- Thermostat: LM393 aus 5 V, NTC 10 kΩ B3950 am Akku ----------------------------
# NTC oben, 4,7 kΩ unten: T_NTC = 5 V · 4,7k/(R_NTC + 4,7k) bleibt unter 3,5 V (Eingangsbereich des LM393).
# T_NTC gegen T_COLD = 4,7k/(30k + 4,7k); 300 kΩ Mitkopplung (R6) auf die Schwelle. Unter ~2,5 °C sperrt der
# offene Kollektor, R8 zieht COLD auf 5 V: Q4 heizt, Q2 trennt den Lader. Über ~4,6 °C zieht er COLD auf GND.
# Die Schwelle ist verhältnisgleich zu V5: die Höhe der Eingangsspannung zählt nicht.
# Zweite Hälfte: Hitzeabschaltung, siehe unten.
g = "thermo"
add("U1", "Comparator:LM393", "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", "LM393", "onsemi LM393DR2G",
    {"1": "COLD", "2": "T_NTC", "3": "T_COLD", "4": GND, "5": "T_HOT", "6": "T_COLD", "7": "HOT", "8": "V5"},
    g, lcsc="C7955")
c("C2", "100nF", "V5", GND, g)
add("J4", "Connector_Generic:Conn_01x02", PADS2_B, "NTC", "Lötpads unten: NTC 10 kΩ B3950, am Akku",
    {"1": "V5", "2": "T_NTC"}, g, hand=True)
r("R1", "4.7k", "T_NTC", GND, group=g)
r("R2", "30k", "V5", "T_COLD", group=g)
r("R3", "4.7k", "T_COLD", GND, group=g)
r("R6", "300k", "COLD", "T_COLD", group=g)      # Mitkopplung, ~2 K Hysterese
# R8 muss klein gegen R6 sein: sonst bleibt COLD bei Frost unter V5 und Q2 sperrt nicht
# (100 kΩ: Ugs = −1,07 V, der AO3401A leitet dann schon; 10 kΩ: −0,14 V).
r("R8", "10k", "V5", "COLD", group=g)

# --- Hitzeabschaltung: Q3 vor Q2, unabhängig vom Frostschutz ----------------------------------
# T_HOT = 0,28 · T_NTC (R4/R5) gegen dieselbe Schwelle T_COLD. Über ~42 °C (Toleranz 39,2 … 44,8) sperrt der offene
# Kollektor, R9 zieht HOT auf 5 V: Q3 trennt. R7 hält das bis ~37 °C. NTC-Kurzschluss gilt als heiß: kein Laden.
# R4 + R5 belasten T_NTC und heben die Frostschwellen um ~0,6 K (2,5 / 4,6 statt 1,9 / 3,9 °C).
g = "hot"
r("R4", "100k", "T_NTC", "T_HOT", group=g)
r("R5", "39k", GND, "T_HOT", group=g)
r("R7", "2M", "HOT", "T_HOT", group=g)
r("R9", "10k", "V5", "HOT", group=g)
pmos("Q3", "HOT", "V5_CHG", "V5", g)

# --- Laden: Q2 vor dem 5V-Pin des XIAO, an solange COLD low ------------------------------
g = "charge"
pmos("Q2", "COLD", "XIAO_5V", "V5_CHG", g)
c("C4", "10uF 10V", "XIAO_5V", GND, g)

# --- Heizung: Q4 (Low-Side) an, solange COLD high ----------------------------------------
g = "heat"
nmos("Q4", "COLD", "HEAT_N", GND, g, value="AO3400A", lcsc="C20917")
for ref in ("R19", "R20", "R21", "R22", "R23"):
    r(ref, "300", "V5", "HEAT_N", fp=R1206, group="heater")   # je 0,08 W, zusammen 0,42 W

# --- Stapel: nur 5V und GND --------------------------------------------------------------
N.stack(j5_pins(), j6_pins(v5="XIAO_5V"))
for part in N.parts:
    if part.symbol == "Device:C":
        part.footprint = R0603    # gleiche Baugröße, größere Padlücke: Platz für die Nummer unter dem Teil

PARTS = N.parts
nets = N.nets

if __name__ == "__main__":
    N.report()
