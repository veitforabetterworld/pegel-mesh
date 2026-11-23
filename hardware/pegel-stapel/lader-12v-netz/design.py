"""Thermolader 12 V Netzteil (Stapel, unten): 9–15 V vom Netzteil, Li-Ionen am Lader des XIAO.

Hinter V5 ist alles der Thermolader 5 V (tools/thermolader12.py). Davor ein TPS54331 (bis 28 V, absolut 30 V) auf
4,88 V (4,7 … 5,1 V). Nicht für Solarpanels: deren Leerlauf liegt bei Frost über seiner Grenze.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from parts import GND, R0402  # noqa: E402
from thermolader12 import base, diodes, inductor  # noqa: E402

N = base("12V NETZTEIL")
r, c, add = N.r, N.c, N.add

# --- Eingang: SMF15A klemmt bei 24,4 V --------------------------------------------------------
diodes(N, "SMF15A", "C19077509")
c("C3", "10uF 50V 0805", "VIN", GND, "input")
c("C5", "100nF 50V 0402", "VIN", GND, "input")

# --- Wandler: TI SLVS839H ---------------------------------------------------------------------
g = "buck"
add("U2", "Regulator_Switching:TPS54331D", "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", "TPS54331", "TI TPS54331DR",
    {"1": "BUCK_BOOT", "2": "VIN", "3": "", "4": "BUCK_SS", "5": "BUCK_FB", "6": "BUCK_COMP", "7": GND,
     "8": "BUCK_SW"}, g, lcsc="C9865")            # EN offen = an
inductor(N)
c("C6", "100nF 50V 0402", "BUCK_BOOT", "BUCK_SW", g)
c("C7", "47uF 6.3V 0805", "V5", GND, g)
c("C9", "10nF 0402", "BUCK_SS", GND, g)            # Sanftanlauf 4 ms
r("R10", "51k", "V5", "BUCK_FB", R0402, g)         # 0,8 V · (1 + 51k/10k) = 4,88 V
r("R11", "10k", "BUCK_FB", GND, R0402, g)
# Regelkreis (Gl. 16–28): C7 und C1 zusammen 10–30 µF wirksam, 1 mA … 0,6 A: 6–29 kHz, Phasenreserve >= 71 Grad
r("R12", "8.2k", "BUCK_COMP", "COMP_RC", R0402, g)
c("C10", "10nF 0402", "COMP_RC", GND, g)
c("C11", "47pF 0402", "BUCK_COMP", GND, g)

PARTS = N.parts
nets = N.nets

if __name__ == "__main__":
    N.report()
