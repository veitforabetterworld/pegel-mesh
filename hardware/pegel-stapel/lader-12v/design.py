"""12-V-Ladeplatine (Stapel, unten): Solarpanel 12-V-Klasse oder 12-V-Netzteil, LiFePO4 1S, Frostschutz mit Heizung.

Schaltung wie pegel-sender-12v ohne die Blöcke 12 V und RS485 (die liegen auf der RS485-Platine). Gleicher Umriss
und gleiche Bohrungen/Anschlüsse wie pegel-sender-12v (100 × 70 mm, gleiches Gehäuse); die XIAO-Leisten
liegen rechts unten. Der XIAO läuft wie bisher über D10 aus dem Akku (3V3-Pin); daraus speist die
RS485-Platine auch die 12 V der Sonde.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from parts import C0603, C0805, C1206, GND, R0603, R1206, SOD123, SOT23, Netlist  # noqa: E402,F401
from stack import j5_pins, j6_pins  # noqa: E402

TERM2 = "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal"
TERM4 = "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-4-5.08_1x04_P5.08mm_Horizontal"
L_RADIAL = "Inductor_THT:L_Radial_D7.0mm_P3.00mm"

N = Netlist()
r, c, add, nmos, pmos = N.r, N.c, N.add, N.nmos, N.pmos

# ---------------------------------------------------------------- Eingang: Solar oder 12-V-Netzteil an J1
g = "solar"
add("J1", "Connector:Screw_Terminal_01x02", TERM2, "SOLAR / 12V", "Klemme 2-pol. 5,08 mm",
    {"1": "IN_RAW", "2": GND}, g, hand=True)
add("D1", "Device:D_TVS", "Diode_SMD:D_SMB", "SMBJ28A", "SMBJ28A", {"1": "IN_RAW", "2": GND}, g, lcsc="C19077582")
# Verpolschutz; nachts fließt nichts aus VSOL ins Panel zurück
add("D2", "Device:D_Schottky", "Diode_SMD:D_SMA", "SS34", "SS34 (40 V 3 A)", {"1": "VSOL", "2": "IN_RAW"}, g,
    lcsc="C8678")
c("C1", "10uF 50V", "VSOL", GND, g)
c("C2", "10uF 50V", "VSOL", GND, g)
c("C3", "10uF 50V", "VSOL", GND, g)
# Puffer am Panel: bremst VSOL, damit die Panelregelung bei schwachem Licht nicht pendelt
add("C23", "Device:C_Polarized", "Capacitor_THT:CP_Radial_D10.0mm_P5.00mm", "220uF 50V",
    "Elko 220 µF 50 V low ESR, D10 mm RM 5 (z. B. Panasonic EEU-FR1H221)", {"1": "VSOL", "2": GND}, g, hand=True)

# ---------------------------------------------------------------- Lader: TPS5430 als Abwärtswandler, 3,50 V
# Konstantspannung über VSENSE (1,221 V · (1 + 56k/30k) = 3,50 V). Strombegrenzung, Panel-Arbeitspunkt und
# Frost-Ladesperre speisen über D4/D5 und R3 Strom in VSENSE und nehmen so den Ladestrom zurück.
g = "charger"
add("U1", "Regulator_Switching:TPS5430DDA", "Package_SO:TI_SO-PowerPAD-8_ThermalVias", "TPS5430", "TI TPS5430DDAR",
    {"1": "CHG_BOOT", "2": "", "3": "", "4": "CHG_FB", "5": "", "6": GND, "7": "VSOL", "8": "CHG_SW", "9": GND},
    g, lcsc="C9864")
c("C4", "100nF", "VSOL", GND, g)
c("C5", "10nF", "CHG_BOOT", "CHG_SW", g)
add("D3", "Device:D_Schottky", "Diode_SMD:D_SMA", "SS34", "SS34 (40 V 3 A)", {"1": "CHG_SW", "2": GND}, g,
    lcsc="C8678")
add("L1", "Device:L", L_RADIAL, "15uH", "Bourns RLB0712-150KL (15 µH, 0,9 A)", {"1": "CHG_SW", "2": "CHG_OUT"}, g,
    hand=True)
c("C6", "22uF 25V", "CHG_OUT", GND, g)
c("C7", "22uF 25V", "CHG_OUT", GND, g)
# Ausgangskondensator mit ESR wie im TI-Referenzdesign (220 µF, 20–100 mΩ): die interne Kompensation braucht
# dessen ESR-Nullstelle; mit nur Keramik am Ausgang hat der Regelkreis ohne Akku ~10° Phasenreserve, so ~45°.
add("C22", "Device:C_Polarized", "Capacitor_THT:CP_Radial_D8.0mm_P3.50mm", "220uF 16V",
    "Polymer- oder Low-ESR-Elko 220 µF 16 V, D8 mm RM 3,5 (z. B. Panasonic 16SEPF220M, EEU-FR1C221)",
    {"1": "CHG_OUT", "2": GND}, g, hand=True)
r("R1", "56k", "CHG_OUT", "CHG_FB", group=g)
r("R2", "30k", "CHG_FB", GND, group=g)
r("R3", "10k", "CHG_LIM", "CHG_FB", group=g)
# Rückstromsperre: nachts trennt Q1 den Akku vom Wandler, sonst speist er über die Body-Diode des Schalters
# im TPS5430 VSOL. Q2 schaltet Q1 ab VSOL ≈ 6,5 V ein (R5/R6); Ladestrom fließt vorher über die Body-Diode.
pmos("Q1", "CHG_PG", "CHG_OUT", "VSYS", g)
r("R4", "100k", "CHG_PG", "VSYS", group=g)
nmos("Q2", "CHG_PGD", "CHG_PG", GND, g)
r("R5", "100k", "VSOL", "CHG_PGD", group=g)
r("R6", "47k", "CHG_PGD", GND, group=g)
c("C8", "100uF 6.3V", "VSYS", GND, g)

# ---------------------------------------------------------------- Regelung: LM324 aus 5 V, Referenz 2,5 V
# A: Ladestrom 0,5 A (49 mV über R15 im Minuspol des Akkus), B: Panel-Arbeitspunkt ~17 V (mit
# Steckbrücke JP2 ~9,7 V für ein 12-V-Netzteil), C: Ladesperre bei Frost, D: Heizung. Alles läuft nur, wenn VSOL
# anliegt: nachts zieht die Regelung keinen Strom aus dem Akku.
g = "mppt"
add("U3", "Regulator_Linear:HT75xx-1-SOT89", "Package_TO_SOT_SMD:SOT-89-3", "HT7550-1", "Holtek HT7550-1",
    {"1": GND, "2": "VSOL", "3": "+5V"}, g, lcsc="C16106")
c("C9", "1uF", "VSOL", GND, g)
c("C10", "1uF", "+5V", GND, g)
add("U2", "Amplifier_Operational:LM324", "Package_SO:SOIC-14_3.9x8.7mm_P1.27mm", "LM324", "ST LM324DT",
    {"1": "CC_OUT", "2": "CC_INT", "3": "CC_SENSE", "4": "+5V", "5": "VREF", "6": "VIN_DIV", "7": "VIN_OUT",
     "8": "CHG_INH", "9": "T_REF0", "10": "T_NTC", "11": GND, "12": "T_REF2", "13": "T_NTC", "14": "HEAT_OFF"},
    g, lcsc="C71035")
c("C11", "100nF", "+5V", GND, g)
add("U4", "pegel:CJ431", SOT23, "CJ431", "JCET CJ431 (2,5 V)", {"1": "VREF", "2": "VREF", "3": GND}, g, lcsc="C3113")
r("R7", "1k", "+5V", "VREF", group=g)     # CJ431 braucht bis 1 mA, R7 liefert ~2,3 mA
# A: Integrator, VREF · 1k/50,9k = 49 mV Sollwert gegen den Spannungsabfall am Shunt. 0,5 A reichen: mit der
# Deep-Sleep-Firmware braucht der Sender im Mittel unter 10 mW (verify/winter_variants.py).
r("R8", "49.9k", "VREF", "CC_SET", group=g)
r("R9", "1k", "CC_SET", GND, group=g)
r("R10", "10k", "CC_SET", "CC_INT", group=g)
c("C12", "100nF", "CC_INT", "CC_OUT", g)
r("R11", "1k", "BAT_N", "CC_SENSE", group=g)
# B: Proportionalregler (Verstärkung 23, schnell genug, damit das Panel bei schwachem Licht nicht einbricht),
# VSOL über R12/R13 gegen 2,5 V. Ein Integrator schwingt hier: die Eingangskondensatoren entladen sich schneller,
# als er nachregelt, das Panel fällt bis zur Abschaltschwelle des TPS5430.
r("R12", "300k", "VSOL", "VIN_DIV", group=g)
r("R13", "51k", "VIN_DIV", GND, group=g)
r("R14", "300k", "VIN_J", "VIN_DIV", group=g)
r("R35", "1M", "VIN_DIV", "VIN_OUT", group=g)
add("JP2", "Connector_Generic:Conn_01x02", "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical", "NETZTEIL",
    "Stiftleiste 1x2 2,54 mm + Jumper", {"1": "VSOL", "2": "VIN_J"}, g, hand=True)
c("C13", "100pF", "VIN_DIV", "VIN_OUT", g)
add("D4", "Diode:BAV70", SOT23, "BAV70", "BAV70", {"1": "CC_OUT", "2": "VIN_OUT", "3": "CHG_LIM"}, g, lcsc="C68978")
add("D5", "Device:D", "Diode_SMD:D_SOD-323", "1N4148WS", "1N4148WS", {"1": "CHG_LIM", "2": "CHG_INH"}, g,
    lcsc="C2128")

# ---------------------------------------------------------------- Akku: J2, Strommessung im Minuspol
g = "battery"
# Klemme an der Oberkante, Pin 2 (+) zum Laderausgang
add("J2", "Connector:Screw_Terminal_01x02", TERM2, "AKKU 3,2V", "Klemme 2-pol. 5,08 mm",
    {"1": "BAT_N", "2": "VSYS"}, g, hand=True)
r("R15", "0.1", "BAT_N", GND, R1206, g)

# ---------------------------------------------------------------- Frost: NTC am Akku, Ladesperre und Heizung
# NTC 10k B3950 und Heizwiderstand (z. B. 68 Ω 5 W) sitzen am Akku und hängen an J4. Ohne NTC sieht die
# Schaltung "sehr kalt": kein Laden, Heizung an.
g = "frost"
add("J4", "Connector:Screw_Terminal_01x04", TERM4, "HEIZ NTC", "Klemme 4-pol. 5,08 mm",
    {"1": "VSOL", "2": "HEAT_N", "3": "T_NTC", "4": GND}, g, hand=True)
r("R17", "27k", "VREF", "T_NTC", group=g)
c("C14", "100nF", "T_NTC", GND, g)
r("R18", "47k", "VREF", "T_REF0", group=g)
r("R19", "5.1k", "T_REF0", "T_REF2", group=g)
r("R20", "49.9k", "T_REF2", GND, group=g)
r("R21", "1M", "CHG_INH", "T_NTC", group=g)    # Mitkopplung Ladesperre
r("R22", "2M", "HEAT_OFF", "T_REF2", group=g)  # Mitkopplung Heizung
nmos("Q3", "HEAT_OFF", "HEAT_G", GND, g)
r("R23", "100k", "VSOL", "HEAT_G", group=g)
add("D6", "Device:D_Zener", SOD123, "10V", "BZT52C10", {"1": "HEAT_G", "2": GND}, g, lcsc="C19077408")
nmos("Q4", "HEAT_G", "HEAT_N", GND, g, value="HL2310A", lcsc="C7420347")

# ---------------------------------------------------------------- XIAO-Versorgung und Stapel
# Versorgung direkt aus dem Akku über D10: der XIAO läuft von 1,7 bis 3,6 V, D10 sperrt die 3,3 V aus USB.
# Die Akkuspannung misst die Firmware an der eigenen Versorgung (VDD + Durchlassspannung von D10).
g = "xiao"
add("D10", "Device:D_Schottky", SOD123, "B5819W", "B5819W SL (40 V 1 A)", {"1": "XIAO_3V3", "2": "VSYS"}, g,
    lcsc="C8598")
c("C19", "10uF 10V", "XIAO_3V3", GND, g)
N.stack(j5_pins(), j6_pins(v33="XIAO_3V3"))
# Bohrungen wie pegel-sender-12v (Gehäuse), je eine in den Ecken
for ref in ("H4", "H5", "H6", "H7"):
    add(ref, "Mechanical:MountingHole", "MountingHole:MountingHole_3.2mm_M3", "M3", "", {}, "mech")

PARTS = N.parts
nets = N.nets

if __name__ == "__main__":
    N.report()
