"""Thermolader 12 V Solar (Stapel, unten): Panel der 12-V-Klasse (36 Zellen, Leerlauf bis 25 V), Li-Ionen am Lader des XIAO.

Hinter V5 ist alles der Thermolader 5 V (tools/thermolader12.py). Davor ein TPS5430 (bis 36 V, absolut 40 V) auf
4,92 V und die Panelregelung Q5. Nicht für 12-V-Netzteile: unter ~14 V am Eingang lädt der XIAO hier nicht.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from parts import GND, R0402, SOT23  # noqa: E402
from thermolader12 import base, diodes, inductor  # noqa: E402

N = base("12V SOLAR")
r, c, add = N.r, N.c, N.add

# --- Eingang: ein 25-V-Panel hat bei -25 C ~29 V, SMF28A bricht erst ab 31,1 V durch ---------------
diodes(N, "SMF28A", "C41376091")
c("C3", "10uF 50V 0805", "VIN", GND, "input")      # bei 25 V noch ~3 µF, die Panelregelung bleibt ab 2,5 µF ruhig
c("C5", "100nF 50V 0402", "VIN", GND, "input")

# --- Wandler: TI SLVS632L, nur Keramik am Ausgang ----------------------------------------------
g = "buck"
add("U2", "Regulator_Switching:TPS5430DDA", "Package_SO:TI_SO-PowerPAD-8_ThermalVias", "TPS5430", "TI TPS5430DDAR",
    {"1": "BUCK_BOOT", "2": "", "3": "", "4": "BUCK_FB", "5": "", "6": GND, "7": "VIN", "8": "BUCK_SW", "9": GND},
    g, lcsc="C9864")                              # ENA offen = an (kein Teiler erlaubt)
inductor(N)
c("C6", "10nF 0402", "BUCK_BOOT", "BUCK_SW", g)    # muss 10 nF sein
c("C7", "100uF 6.3V", "V5", GND, g)
c("C8", "100uF 6.3V", "V5", GND, g)
r("R10", "10k", "V5", "BUCK_FB", R0402, g)         # 1,221 V · (1 + 10k/3,3k) = 4,92 V
r("R11", "3.3k", "BUCK_FB", GND, R0402, g)
# Netz für Keramik (Abschnitt 7.2.3.2.2): 45–200 µF wirksam, L ±20 %: 6–33 kHz, Phasenreserve >= 49 Grad,
# auch solange die Panelregelung leitet
c("C9", "2.2nF 0402", "V5", "BUCK_FB", g)
r("R12", "510", "BUCK_FB", "FB_RC", R0402, g)
c("C10", "100nF 0402", "FB_RC", GND, g)
c("C11", "150pF 0402", "BUCK_FB", GND, g)

# --- Panelregelung: V5 folgt dem Panel ----------------------------------------------------------
# V5 ~ 2,77 V + 0,106 · VIN, höchstens 4,92 V. Sinkt das Panel auf ~15 V, ist V5 bei 4,31 V: dort nimmt der
# BQ25101 im XIAO den Ladestrom zurück (IN-DPM), das Panel bleibt nahe am besten Punkt. Kein Kondensator an die
# Basis: er kostet bis zu 20 Grad Phasenreserve.
g = "panel"
add("Q5", "Device:Q_PNP", SOT23, "MMBT5401", "MMBT5401", {"1": "PV_DIV", "2": "PV_E", "3": "BUCK_FB"}, g,
    lcsc="C8326")
r("R13", "56k", "VIN", "PV_DIV", R0402, g)
r("R14", "15k", "PV_DIV", GND, R0402, g)
r("R15", "10k", "V5", "PV_E", R0402, g)

PARTS = N.parts
nets = N.nets

if __name__ == "__main__":
    N.report()
