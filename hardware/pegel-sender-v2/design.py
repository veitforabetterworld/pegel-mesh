"""Pegel-Sender v2: Bauteile, Werte, Footprints, LCSC-Nummern und Netze.

Einzige Quelle für die Platine (gen_pcb.py). Pin-Nummern sind die der Footprint-Pads.

Gegenüber pegel-sender (v1, bleibt für bestehende Stationen): Li-Ionen-Akku am Lader des XIAO statt LiFePO4 mit
eigenem Lader, 5 V aus einem USB-C-Netzteil oder USB-C-Solarpanel, Akkuheizung aus SMD-Widerständen auf der Platine,
alle Anschlüsse als 2,54-mm-Löcher statt Schraubklemmen. Die Pinbelegung am XIAO ist dieselbe (D0 Sonde, D6/D7 RS485,
D1-D5 und D8-D10 Wio-SX1262): dieselbe Firmware läuft auf beiden Platinen und erkennt den Akku selbst.

Frost- und Hitzeschutz ohne Firmware: ein LM393 vergleicht den NTC am Akku mit zwei Schwellen. Unter ~2 °C trennt er
den Lader des XIAO vom 5-V-Eingang und schaltet die Heizung ein (nur aus dem Eingang, nachts nie aus dem Akku), über
~43 °C trennt er nur den Lader. Ohne NTC gilt "sehr kalt": kein Laden, Heizung an, solange 5 V anliegen.

Alle SMD-Teile aus der JLCPCB-Basic- oder Preferred-Bibliothek (verify: ../pegel-sender/verify/jlc_parts.py .).
Spule, NTC, Steck- und Lötanschlüsse sind Durchsteckteile zum Selbstlöten (hand=True).
"""

from dataclasses import dataclass, field


@dataclass
class Part:
    ref: str
    symbol: str          # "Lib:Name" (KiCad)
    footprint: str       # "Lib:Name"
    value: str
    mpn: str             # Hersteller-Teilenummer ("" = mechanisch)
    pins: dict = field(default_factory=dict)   # Pad -> Netz
    group: str = ""      # Funktionsblock
    dnp: bool = False
    lcsc: str = ""       # JLCPCB/LCSC-Teilenummer (Basic oder Preferred)
    hand: bool = False   # Durchsteckteil, nicht von JLCPCB bestückt


GND = "GND"
R0603 = "Resistor_SMD:R_0603_1608Metric"
R1206 = "Resistor_SMD:R_1206_3216Metric"
C0603 = "Capacitor_SMD:C_0603_1608Metric"
C0805 = "Capacitor_SMD:C_0805_2012Metric"
SOT23 = "Package_TO_SOT_SMD:SOT-23"
SOD123 = "Diode_SMD:D_SOD-123"
HOLES2 = "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical"
HOLES4 = "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical"
L_RADIAL = "Inductor_THT:L_Radial_D7.0mm_P3.00mm"   # Bourns RLB0712: Ø 7 mm, Rastermaß 3 mm

# LCSC-Nummern der Basic-Widerstände (UNI-ROYAL, 1 %)
RES_LCSC = {
    ("4.7k", "0603"): "C23162", ("10k", "0603"): "C25804", ("30k", "0603"): "C22984", ("56k", "0603"): "C23206",
    ("100k", "0603"): "C25803", ("510k", "0603"): "C23192", ("1M", "0603"): "C22935",
    ("300", "1206"): "C17887",
}
# Basic-Kondensatoren: Wert -> (Footprint, Herstellerbezeichnung, LCSC)
CAP = {
    "22pF": (C0603, "CAP 22pF 50V C0G 0603", "C1653"),
    "100nF": (C0603, "CAP 100nF 50V X7R 0603", "C14663"),
    "10uF 10V": (C0603, "CAP 10uF 10V X5R 0603", "C19702"),
    "10uF 25V": (C0805, "CAP 10uF 25V X5R 0805", "C15850"),
}

PARTS: list[Part] = []


def add(*args, **kwargs) -> Part:
    p = Part(*args, **kwargs)
    PARTS.append(p)
    return p


def r(ref, value, a, b, fp=R0603, group=""):
    size = fp.split(":")[1].split("_")[1]
    return add(ref, "Device:R", fp, value, f"RES {value} 1% {size}", {"1": a, "2": b}, group,
               lcsc=RES_LCSC[(value, size)])


def c(ref, value, a, b, group=""):
    fp, mpn, lcsc = CAP[value]
    return add(ref, "Device:C", fp, value, mpn, {"1": a, "2": b}, group, lcsc=lcsc)


def nmos(ref, g, d, s, group, value="2N7002", lcsc="C8545"):
    return add(ref, "Device:Q_NMOS", SOT23, value, value, {"1": g, "2": s, "3": d}, group, lcsc=lcsc)


def pmos(ref, g, d, s, group):
    return add(ref, "Device:Q_PMOS", SOT23, "AO3401A", "AOS AO3401A", {"1": g, "2": s, "3": d}, group, lcsc="C15127")


# ---------------------------------------------------------------- Eingang: 5 V aus USB-C-Netzteil oder -Panel an J1
g = "input"
add("J1", "Connector_Generic:Conn_01x02", HOLES2, "5V IN", "Lötanschluss 2 x 2,54 mm", {"1": "VIN_RAW", "2": GND}, g,
    hand=True)
# Verpolschutz ohne Spannungsverlust: die Body-Diode leitet zuerst, dann schaltet Ugs = -5 V den Kanal durch
pmos("Q1", GND, "VIN_RAW", "V5", g)
add("D1", "Device:D_TVS", "Diode_SMD:D_SMA", "SMAJ5.0A", "SMAJ5.0A (5 V, 400 W)", {"1": "V5", "2": GND}, g,
    lcsc="C19077523")
c("C1", "10uF 10V", "V5", GND, g)

# ---------------------------------------------------------------- Frost/Hitze: LM393 aus 5 V, NTC am Akku (J4)
# NTC oben, 4,7 kΩ unten: x = 4,7k/(R_NTC + 4,7k) bleibt unter 3,5 V (Eingangsbereich des LM393 bei 5 V).
# Kalt (A): T_NTC unter 4,7k/34,7k → unter ~2 °C (R_NTC 30 kΩ) Ausgang low. Heiß (B): T_NTC über 0,5 → über ~43 °C
# (R_NTC 4,7 kΩ) Ausgang low. Beide Schwellen verhältnisgleich zu V5, die Höhe der Eingangsspannung zählt nicht.
# 1 MΩ Mitkopplung je Kanal: ~1 K Hysterese.
g = "thermo"
add("U1", "Comparator:LM393", "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", "LM393", "onsemi LM393DR2G",
    {"1": "COLD_N", "2": "T_COLD", "3": "T_NTC", "4": GND, "5": "T_HOT", "6": "T_NTC", "7": "HOT_N", "8": "V5"},
    g, lcsc="C7955")
c("C2", "100nF", "V5", GND, g)
add("J4", "Connector_Generic:Conn_01x02", HOLES2, "NTC", "NTC 10 kΩ B3950 bedrahtet, am Akku",
    {"1": "V5", "2": "T_NTC"}, g, hand=True)
r("R1", "4.7k", "T_NTC", GND, group=g)
c("C3", "100nF", "T_NTC", GND, g)
r("R2", "30k", "V5", "T_COLD", group=g)
r("R3", "4.7k", "T_COLD", GND, group=g)
r("R4", "4.7k", "V5", "T_HOT", group=g)
r("R5", "4.7k", "T_HOT", GND, group=g)
r("R6", "1M", "COLD_N", "T_NTC", group=g)      # Mitkopplung kalt
r("R7", "1M", "HOT_N", "T_HOT", group=g)       # Mitkopplung heiß
r("R8", "100k", "V5", "COLD_N", group=g)
r("R9", "100k", "V5", "HOT_N", group=g)

# ---------------------------------------------------------------- Laden: 5 V zum XIAO nur bei 2-43 °C
# CHG_EN liegt über R10 auf 5 V; ist einer der Komparatorausgänge low, zieht ihn D2 bzw. D3 auf ~0,7 V, Q3 sperrt
# (2N7002 Ugs(th) ab 1 V), R11 hält Q2 aus. Der XIAO lädt dann nicht und läuft weiter aus dem Akku.
g = "charge"
r("R10", "100k", "V5", "CHG_EN", group=g)
add("D2", "Device:D", "Diode_SMD:D_SOD-323", "1N4148WS", "1N4148WS", {"1": "COLD_N", "2": "CHG_EN"}, g, lcsc="C2128")
add("D3", "Device:D", "Diode_SMD:D_SOD-323", "1N4148WS", "1N4148WS", {"1": "HOT_N", "2": "CHG_EN"}, g, lcsc="C2128")
nmos("Q3", "CHG_EN", "CHG_G", GND, g)
r("R11", "100k", "V5", "CHG_G", group=g)
pmos("Q2", "CHG_G", "XIAO_5V", "V5", g)
c("C4", "10uF 10V", "XIAO_5V", GND, g)

# ---------------------------------------------------------------- Heizung: 6 x 300 Ω = 50 Ω, 0,5 W aus 5 V
# Q4 schaltet bei COLD_N low ein (Ugs = -5 V). Die Widerstände liegen verteilt unter dem Akku, der auf der Unterseite
# der Platine aufliegt; je 83 mW (1206: 250 mW).
g = "heater"
pmos("Q4", "COLD_N", "HEAT", "V5", g)
for i in range(6):
    r(f"R{12 + i}", "300", "HEAT", GND, R1206, g)

# ---------------------------------------------------------------- Akku: Li-Ionen 1S an J2, BAT des XIAO an J7
# Den Akku lädt der XIAO (BQ25101, 100 mA); seine BAT-Pads sitzen auf der Unterseite und gehen mit zwei Drähten an J7.
# Akku mit eigener Schutzschaltung verwenden (Unter-/Überspannung, Kurzschluss).
g = "battery"
add("J2", "Connector_Generic:Conn_01x02", HOLES2, "AKKU Li-Ion", "Lötanschluss 2 x 2,54 mm", {"1": "VBAT", "2": GND},
    g, hand=True)
add("J7", "Connector_Generic:Conn_01x02", HOLES2, "XIAO BAT", "Lötanschluss 2 x 2,54 mm (Drähte zu BAT+/BAT- des XIAO)",
    {"1": "VBAT", "2": GND}, g, hand=True)
c("C5", "10uF 10V", "VBAT", GND, g)

# ---------------------------------------------------------------- 12 V für die Sonde: TPS61040 + Lastschalter
# Wie v1, Eingang ist hier der Akku (3,25-4,2 V). Ohne EN läuft VBAT über L1/D4 auf V12_RAW durch, Q5 trennt die
# Sonde dann ab.
g = "12v"
add("U2", "Regulator_Switching:TPS61040DBV", "Package_TO_SOT_SMD:SOT-23-5", "TPS61040", "TI TPS61040DBVR",
    {"1": "BST_SW", "2": GND, "3": "BST_FB", "4": "SENS_EN", "5": "VBAT"}, g, lcsc="C7722")
add("L1", "Device:L", L_RADIAL, "10uH", "Bourns RLB0712-100KL (10 µH, 1,1 A)", {"1": "VBAT", "2": "BST_SW"}, g,
    hand=True)
add("D4", "Device:D_Schottky", SOD123, "B0540W", "B0540W (40 V 0,5 A)", {"1": "V12_RAW", "2": "BST_SW"}, g,
    lcsc="C7420325")
r("R18", "510k", "V12_RAW", "BST_FB", group=g)
r("R19", "56k", "BST_FB", GND, group=g)        # 1,233 V · (1 + 510k/56k) = 12,46 V
c("C6", "22pF", "V12_RAW", "BST_FB", g)
c("C7", "10uF 25V", "V12_RAW", GND, g)
c("C8", "10uF 10V", "VBAT", GND, g)
r("R20", "100k", "SENS_EN", GND, group=g)
pmos("Q5", "PSW_G", "V12_PROBE", "V12_RAW", g)
r("R21", "100k", "V12_RAW", "PSW_G", group=g)
r("R22", "100k", "PSW_G", "PSW_PD", group=g)   # Teiler: Ugs ≈ −6,2 V statt −12,5 V (AO3401A: max. ±12 V)
nmos("Q6", "SENS_EN", "PSW_PD", GND, g)
add("D5", "Device:D_TVS", "Diode_SMD:D_SMA", "SMAJ18A", "SMAJ18A", {"1": "V12_PROBE", "2": GND}, g,
    lcsc="C19077538")

# ---------------------------------------------------------------- RS485: SP3485 mit automatischer Richtung (wie v1)
g = "rs485"
pmos("Q7", "PSW_PD", "RS_VCC", "XIAO_3V3", g)
r("R23", "100k", "XIAO_3V3", "PSW_PD", group=g)
c("C9", "100nF", "RS_VCC", GND, g)
add("U3", "Interface_UART:SP3485EN", "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", "SP3485EN", "MaxLinear SP3485EN-L/TR",
    {"1": "UART_RX", "2": "RS_DE", "3": "RS_DE", "4": GND, "5": GND, "6": "RS485_A", "7": "RS485_B", "8": "RS_VCC"},
    g, lcsc="C8963")
nmos("Q8", "UART_TX", "RS_DE", GND, g)
r("R24", "10k", "RS_VCC", "RS_DE", group=g)
r("R25", "100k", "RS_VCC", "UART_RX", group=g)   # RO ist beim Senden hochohmig
r("R26", "10k", "RS485_A", "RS_VCC", group=g)
r("R27", "10k", "RS485_B", GND, group=g)
add("D6", "Diode:SM712_SOT23", SOT23, "PSM712", "ProTek PSM712-LF-T7", {"1": "RS485_A", "2": "RS485_B", "3": GND},
    g, lcsc="C32677")
add("J3", "Connector_Generic:Conn_01x04", HOLES4, "SONDE", "Lötanschluss 4 x 2,54 mm",
    {"1": "V12_PROBE", "2": GND, "3": "RS485_A", "4": "RS485_B"}, g, hand=True)

# ---------------------------------------------------------------- XIAO nRF52840 + Wio-SX1262 (gesteckt, wie v1)
# Der XIAO läuft aus dem Akku über seinen eigenen Regler; 3V3 versorgt nur den SP3485 (über Q7). Sein 5V-Pin ist der
# Eingang des Laders.
g = "xiao"
add("J5", "Connector_Generic:Conn_01x07", "Connector_PinSocket_2.54mm:PinSocket_1x07_P2.54mm_Vertical", "XIAO D0-D6",
    "Buchsenleiste 1x7 2,54 mm",
    {"1": "SENS_EN", "2": "", "3": "", "4": "", "5": "", "6": "", "7": "UART_TX"}, g, hand=True)
add("J6", "Connector_Generic:Conn_01x07", "Connector_PinSocket_2.54mm:PinSocket_1x07_P2.54mm_Vertical", "XIAO 5V-D7",
    "Buchsenleiste 1x7 2,54 mm",
    {"1": "XIAO_5V", "2": GND, "3": "XIAO_3V3", "4": "", "5": "", "6": "", "7": "UART_RX"}, g, hand=True)
c("C10", "10uF 10V", "XIAO_3V3", GND, g)

# ---------------------------------------------------------------- Mechanik
for i in range(2):
    add(f"H{i + 1}", "Mechanical:MountingHole", "MountingHole:MountingHole_3.2mm_M3", "M3", "", {}, "mech")


def nets() -> dict[str, list[tuple[str, str]]]:
    out: dict[str, list[tuple[str, str]]] = {}
    for p in PARTS:
        for pad, net in p.pins.items():
            if net:
                out.setdefault(net, []).append((p.ref, pad))
    return out


if __name__ == "__main__":
    n = nets()
    print(f"{len(PARTS)} parts, {len(n)} nets")
    for name, pads in sorted(n.items()):
        if len(pads) < 2:
            print("single-pad net:", name, pads)
