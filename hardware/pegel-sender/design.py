"""Pegel-Sender-Platine: Bauteile, Werte, Footprints, LCSC-Nummern und Netze.

Einzige Quelle für Schaltplan (schematic.py) und Platine (gen_pcb.py). Pin-Nummern sind die der Footprint-Pads.
Platinenbeschreibung: README.md im Repo-Root.

Ausgelegt auf die günstigste JLCPCB-Bestückung: alle SMD-Teile aus der Basic- oder Preferred-Bibliothek (keine
Rüstgebühr). Spulen, Klemmen und XIAO-Buchsen sind Durchsteckteile zum Selbstlöten (hand=True).
"""

from dataclasses import dataclass, field


@dataclass
class Part:
    ref: str
    symbol: str          # "Lib:Name" (KiCad) oder "pegel:Name" (Kastensymbol aus sch_symbols.py)
    footprint: str       # "Lib:Name"
    value: str
    mpn: str             # Hersteller-Teilenummer ("" = mechanisch / Lötbrücke)
    pins: dict = field(default_factory=dict)   # Pad -> Netz
    group: str = ""      # Funktionsblock (Platzierung, Schaltplanblatt)
    dnp: bool = False
    lcsc: str = ""       # JLCPCB/LCSC-Teilenummer (Basic oder Preferred)
    hand: bool = False   # Durchsteckteil, nicht von JLCPCB bestückt


GND = "GND"
R0603 = "Resistor_SMD:R_0603_1608Metric"
R1206 = "Resistor_SMD:R_1206_3216Metric"
C0603 = "Capacitor_SMD:C_0603_1608Metric"
C0805 = "Capacitor_SMD:C_0805_2012Metric"
C1206 = "Capacitor_SMD:C_1206_3216Metric"
SOT23 = "Package_TO_SOT_SMD:SOT-23"
SOD123 = "Diode_SMD:D_SOD-123"
TERM2 = "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal"
TERM4 = "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-4-5.08_1x04_P5.08mm_Horizontal"
L_RADIAL = "Inductor_THT:L_Radial_D8.7mm_P5.00mm_Fastron_07HCP"

# LCSC-Nummern der Basic-Widerstände (UNI-ROYAL, 1 %)
RES_LCSC = {
    ("1k", "0603"): "C21190", ("2.2k", "0603"): "C4190", ("5.1k", "0603"): "C23186", ("10k", "0603"): "C25804",
    ("24k", "0603"): "C23352", ("27k", "0603"): "C22967", ("30k", "0603"): "C22984", ("47k", "0603"): "C25819",
    ("49.9k", "0603"): "C23184", ("51k", "0603"): "C23196", ("56k", "0603"): "C23206", ("100k", "0603"): "C25803",
    ("300k", "0603"): "C23024", ("510k", "0603"): "C23192", ("1M", "0603"): "C22935", ("2M", "0603"): "C22976",
    ("0.1", "1206"): "C25334",
}
# Basic-Kondensatoren: Wert -> (Footprint, Herstellerbezeichnung, LCSC)
CAP = {
    "22pF": (C0603, "CAP 22pF 50V C0G 0603", "C1653"),
    "100pF": (C0603, "CAP 100pF 50V C0G 0603", "C14858"),
    "10nF": (C0603, "CAP 10nF 50V X7R 0603", "C57112"),
    "100nF": (C0603, "CAP 100nF 50V X7R 0603", "C14663"),
    "1uF": (C0603, "CAP 1uF 50V X5R 0603", "C15849"),
    "10uF 10V": (C0603, "CAP 10uF 10V X5R 0603", "C19702"),
    "10uF 25V": (C0805, "CAP 10uF 25V X5R 0805", "C15850"),
    "22uF 25V": (C0805, "CAP 22uF 25V X5R 0805", "C45783"),
    "10uF 50V": (C1206, "CAP 10uF 50V X5R 1206", "C13585"),
    "100uF 6.3V": (C1206, "CAP 100uF 6.3V X5R 1206", "C15008"),
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


# ---------------------------------------------------------------- Eingang: Solar oder 12-V-Netzteil an J1
g = "solar"
add("J1", "Connector:Screw_Terminal_01x02", TERM2, "SOLAR / 12V", "Klemme 2-pol. 5,08 mm",
    {"1": "IN_RAW", "2": GND}, g, hand=True)
add("D1", "Device:D_TVS", "Diode_SMD:D_SMB", "SMBJ28A", "SMBJ28A", {"1": "IN_RAW", "2": GND}, g, lcsc="C19077582")
# Verpolschutz; nachts fließt nichts aus VSOL ins Panel zurück
add("D2", "Device:D_Schottky", "Diode_SMD:D_SMA", "SS54", "SS54 (40 V 5 A)", {"1": "VSOL", "2": "IN_RAW"}, g,
    lcsc="C22452")
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
add("D3", "Device:D_Schottky", "Diode_SMD:D_SMA", "SS54", "SS54 (40 V 5 A)", {"1": "CHG_SW", "2": GND}, g,
    lcsc="C22452")
add("L1", "Device:L", L_RADIAL, "15uH", "Bourns RLB0914-150KL (15 µH, 2,4 A)", {"1": "CHG_SW", "2": "CHG_OUT"}, g,
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
# A: Ladestrom 2,0 A (100 mV über R15‖R16 im Minuspol des Akkus), B: Panel-Arbeitspunkt ~17 V (mit
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
# A: Integrator, VREF/25 = 100 mV Sollwert gegen den Spannungsabfall am Shunt
r("R8", "24k", "VREF", "CC_SET", group=g)
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
r("R16", "0.1", "BAT_N", GND, R1206, g)

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

# ---------------------------------------------------------------- 12 V für die Sonde: TPS61040 + Lastschalter
# Sonde 30 mA bei 12 V. Ohne EN läuft VSYS über L2/D7 auf V12_RAW durch, Q5 trennt die Sonde dann ab.
g = "12v"
add("U5", "Regulator_Switching:TPS61040DBV", "Package_TO_SOT_SMD:SOT-23-5", "TPS61040", "TI TPS61040DBVR",
    {"1": "BST_SW", "2": GND, "3": "BST_FB", "4": "SENS_EN", "5": "VSYS"}, g, lcsc="C7722")
add("L2", "Device:L", L_RADIAL, "10uH", "Bourns RLB0912-100KL (10 µH, 2,5 A)", {"1": "VSYS", "2": "BST_SW"}, g,
    hand=True)
add("D7", "Device:D_Schottky", SOD123, "B0540W", "B0540W (40 V 0,5 A)", {"1": "V12_RAW", "2": "BST_SW"}, g,
    lcsc="C7420325")
r("R24", "510k", "V12_RAW", "BST_FB", group=g)
r("R25", "56k", "BST_FB", GND, group=g)        # 1,233 V · (1 + 510k/56k) = 12,46 V
c("C15", "22pF", "V12_RAW", "BST_FB", g)
c("C16", "10uF 25V", "V12_RAW", GND, g)
c("C17", "10uF 10V", "VSYS", GND, g)
r("R26", "100k", "SENS_EN", GND, group=g)
pmos("Q5", "PSW_G", "V12_PROBE", "V12_RAW", g)
r("R27", "100k", "V12_RAW", "PSW_G", group=g)
r("R28", "100k", "PSW_G", "PSW_PD", group=g)   # Teiler: Ugs ≈ −6,2 V statt −12,5 V (AO3401A: max. ±12 V)
nmos("Q6", "SENS_EN", "PSW_PD", GND, g)
add("D8", "Device:D_TVS", "Diode_SMD:D_SMA", "SMAJ18A", "SMAJ18A", {"1": "V12_PROBE", "2": GND}, g,
    lcsc="C19077538")

# ---------------------------------------------------------------- RS485: SP3485 mit automatischer Richtung
# Versorgung aus XIAO_3V3 nur bei eingeschalteter Sonde (Q7 an PSW_PD): gleiche Pegel wie der XIAO, RO kann
# den RX-Pin nicht über dessen Versorgung heben. DI liegt fest auf GND, TX schaltet über Q8 den
# Treiber: TX low → DE high → Leitung "0"; TX high → Empfang, R32/R33 halten die Leitung auf "1". Kein
# Abschlusswiderstand: er drückte diesen Ruhepegel unter die Schwelle; bei 9600 Baud ist er nicht nötig.
g = "rs485"
pmos("Q7", "PSW_PD", "RS_VCC", "XIAO_3V3", g)
r("R29", "100k", "XIAO_3V3", "PSW_PD", group=g)
c("C18", "100nF", "RS_VCC", GND, g)
add("U6", "Interface_UART:SP3485EN", "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", "SP3485EN", "MaxLinear SP3485EN-L/TR",
    {"1": "UART_RX", "2": "RS_DE", "3": "RS_DE", "4": GND, "5": GND, "6": "RS485_A", "7": "RS485_B", "8": "RS_VCC"},
    g, lcsc="C8963")
nmos("Q8", "UART_TX", "RS_DE", GND, g)
r("R30", "10k", "RS_VCC", "RS_DE", group=g)
r("R31", "100k", "RS_VCC", "UART_RX", group=g)   # RO ist beim Senden hochohmig
r("R32", "10k", "RS485_A", "RS_VCC", group=g)
r("R33", "10k", "RS485_B", GND, group=g)
add("D9", "Diode:SM712_SOT23", SOT23, "PSM712", "ProTek PSM712-LF-T7", {"1": "RS485_A", "2": "RS485_B", "3": GND},
    g, lcsc="C32677")
add("J3", "Connector:Screw_Terminal_01x04", TERM4, "SONDE V+ V- A B", "Klemme 4-pol. 5,08 mm",
    {"1": "V12_PROBE", "2": GND, "3": "RS485_A", "4": "RS485_B"}, g, hand=True)

# ---------------------------------------------------------------- XIAO nRF52840 + Wio-SX1262 (gesteckt)
# Versorgung direkt aus dem Akku über D10: der XIAO läuft von 1,7 bis 3,6 V, D10 sperrt die 3,3 V aus USB.
# Die Akkuspannung misst die Firmware an der eigenen Versorgung (VDD + Durchlassspannung von D10).
g = "xiao"
add("J5", "Connector_Generic:Conn_01x07", "Connector_PinSocket_2.54mm:PinSocket_1x07_P2.54mm_Vertical", "XIAO D0-D6",
    "Buchsenleiste 1x7 2,54 mm",
    {"1": "SENS_EN", "2": "", "3": "", "4": "", "5": "", "6": "", "7": "UART_TX"}, g, hand=True)
add("J6", "Connector_Generic:Conn_01x07", "Connector_PinSocket_2.54mm:PinSocket_1x07_P2.54mm_Vertical", "XIAO 5V-D7",
    "Buchsenleiste 1x7 2,54 mm",
    {"1": "", "2": GND, "3": "XIAO_3V3", "4": "", "5": "", "6": "", "7": "UART_RX"}, g, hand=True)
add("D10", "Device:D_Schottky", SOD123, "B5819W", "B5819W (40 V 1 A)", {"1": "XIAO_3V3", "2": "VSYS"}, g,
    lcsc="C64885")
c("C19", "10uF 10V", "XIAO_3V3", GND, g)

# ---------------------------------------------------------------- Mechanik
for i in range(4):
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
