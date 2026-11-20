"""Pegel-Sender 5 V: Netzliste für gen_pcb.py (kein KiCad-Schaltplan).

Außen nur 6 Lötstellen: J1 5 V (+/−), J3 Sonde (A, B, GND, 12 V).
Laden per BQ25101 auf dem XIAO. V5 geht über Q10 an J6-1 (XIAO-5V); Q9 schaltet
8×120 Ω (1,7 W) dagegen. Ein GPIO (HEAT_EN, Draht an XIAO-Pad P0.09): high = heizen
und Lader aus, low = laden und Heizung aus.
Akku nur an XIAO-BAT (keine Extra-Pads/Buchsen). 12 V der Sonde an J3 Pin 4 (V12_PROBE).

Build Firmware: -DPEGEL_5V_BOARD=1.
"""

from dataclasses import dataclass, field


@dataclass
class Part:
    ref: str
    symbol: str
    footprint: str
    value: str
    mpn: str
    pins: dict = field(default_factory=dict)
    group: str = ""
    dnp: bool = False
    lcsc: str = ""
    hand: bool = False


GND = "GND"
R0603 = "Resistor_SMD:R_0603_1608Metric"
R1206 = "Resistor_SMD:R_1206_3216Metric"
C0603 = "Capacitor_SMD:C_0603_1608Metric"
C0805 = "Capacitor_SMD:C_0805_2012Metric"
SOT23 = "Package_TO_SOT_SMD:SOT-23"
SOD123 = "Diode_SMD:D_SOD-123"
HOLES2 = "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical"
HOLES4 = "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical"
L_RADIAL = "Inductor_THT:L_Radial_D7.0mm_P3.00mm"
XIAO_ROW = "Connector_PinSocket_2.54mm:PinSocket_1x07_P2.54mm_Vertical"

RES_LCSC = {
    ("4.7k", "0603"): "C23162", ("10k", "0603"): "C25804", ("56k", "0603"): "C23206",
    ("100k", "0603"): "C25803", ("510k", "0603"): "C23192",
}
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


def r(ref, value, a, b, group=""):
    return add(ref, "Device:R", R0603, value, f"RES {value} 1% 0603", {"1": a, "2": b}, group,
               lcsc=RES_LCSC[(value, "0603")])


def r1206(ref, a, b, group=""):
    # 8× parallel an 5 V: je 0,21 W, zusammen 1,67 W. Basic, eine Sorte.
    return add(ref, "Device:R", R1206, "120", "RES 120 1% 250mW 1206", {"1": a, "2": b}, group,
               lcsc="C17909")


def c(ref, value, a, b, group=""):
    fp, mpn, lcsc = CAP[value]
    return add(ref, "Device:C", fp, value, mpn, {"1": a, "2": b}, group, lcsc=lcsc)


def nmos(ref, g, d, s, group, value="2N7002", lcsc="C8545"):
    return add(ref, "Device:Q_NMOS", SOT23, value, value, {"1": g, "2": s, "3": d}, group, lcsc=lcsc)


def pmos(ref, g, d, s, group):
    return add(ref, "Device:Q_PMOS", SOT23, "AO3401A", "AOS AO3401A", {"1": g, "2": s, "3": d}, group, lcsc="C15127")


# --- 5 V Eingang → XIAO (Lader auf dem Modul) ---------------------------------
g = "input"
add("J1", "Connector_Generic:Conn_01x02", HOLES2, "5V IN", "5 V + GND", {"1": "VIN_RAW", "2": GND}, g, hand=True)
pmos("Q1", GND, "VIN_RAW", "V5", g)
add("D1", "Device:D_TVS", "Diode_SMD:D_SMA", "SMAJ5.0A", "SMAJ5.0A (5 V, 400 W)", {"1": "V5", "2": GND}, g,
    lcsc="C19077523")
c("C1", "10uF 10V", "V5", GND, g)

# --- Heizung gegen Laden (Default: HEAT_EN low = laden) ------------------------
# Q9/Q10 AO3401A High-Side. Q11 zieht das Heiz-Gate, dadurch fällt Q12 ab und
# der Lader geht aus. Q12 ist an, wenn das Heiz-Gate an 5 V liegt.
g = "heat"
pmos("Q9", "QH_GATE", "HEAT", "V5", g)
pmos("Q10", "QC_GATE", "XIAO_5V", "V5", g)
nmos("Q11", "HEAT_GATE", "QH_GATE", GND, g)
nmos("Q12", "QH_GATE", "QC_GATE", GND, g)
r("R27", "100k", "QH_GATE", "V5", g)
r("R28", "100k", "QC_GATE", "V5", g)
r("R29", "100k", "HEAT_EN", GND, g)
r("R30", "10k", "HEAT_EN", "HEAT_GATE", g)
for ref in ("R19", "R20", "R21", "R22", "R23", "R24", "R25", "R26"):
    r1206(ref, "HEAT", GND, g)
add("TP1", "Connector_Generic:Conn_01x01",
    "Connector_PinHeader_2.54mm:PinHeader_1x01_P2.54mm_Vertical",
    "P0.09", "Draht an XIAO NFC1 / P0.09", {"1": "HEAT_EN"}, g, hand=True)

# --- 12 V Sonde (VBAT vom XIAO-BAT+, L1 an BAT+ des Moduls löten) --------------
g = "12v"
add("U2", "Regulator_Switching:TPS61040DBV", "Package_TO_SOT_SMD:SOT-23-5", "TPS61040", "TI TPS61040DBVR",
    {"1": "BST_SW", "2": GND, "3": "BST_FB", "4": "SENS_EN", "5": "VBAT"}, g, lcsc="C7722")
add("L1", "Device:L", L_RADIAL, "10uH", "Bourns RLB0712-100KL", {"1": "VBAT", "2": "BST_SW"}, g, hand=True)
add("D4", "Device:D_Schottky", SOD123, "B0540W", "B0540W", {"1": "V12_RAW", "2": "BST_SW"}, g, lcsc="C7420325")
r("R9", "510k", "V12_RAW", "BST_FB", group=g)
r("R10", "56k", "BST_FB", GND, group=g)
c("C3", "22pF", "V12_RAW", "BST_FB", g)
c("C4", "10uF 25V", "V12_RAW", GND, g)
c("C5", "10uF 10V", "VBAT", GND, g)
r("R11", "100k", "SENS_EN", GND, group=g)
pmos("Q5", "PSW_G", "V12_PROBE", "V12_RAW", g)
r("R12", "100k", "V12_RAW", "PSW_G", group=g)
r("R13", "100k", "PSW_G", "PSW_PD", group=g)
nmos("Q6", "SENS_EN", "PSW_PD", GND, g)
add("D5", "Device:D_TVS", "Diode_SMD:D_SMA", "SMAJ18A", "SMAJ18A", {"1": "V12_PROBE", "2": GND}, g,
    lcsc="C19077538")

# --- RS485 (4 Pins nach außen) -------------------------------------------------
g = "rs485"
pmos("Q7", "PSW_PD", "RS_VCC", "XIAO_3V3", g)
r("R14", "100k", "XIAO_3V3", "PSW_PD", group=g)
c("C6", "100nF", "RS_VCC", GND, g)
add("U3", "Interface_UART:SP3485EN", "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", "SP3485EN", "MaxLinear SP3485EN-L/TR",
    {"1": "UART_RX", "2": "RS_DE", "3": "RS_DE", "4": GND, "5": GND, "6": "RS485_A", "7": "RS485_B", "8": "RS_VCC"},
    g, lcsc="C8963")
nmos("Q8", "UART_TX", "RS_DE", GND, g)
r("R15", "10k", "RS_VCC", "RS_DE", group=g)
r("R16", "100k", "RS_VCC", "UART_RX", group=g)
r("R17", "10k", "RS485_A", "RS_VCC", group=g)
r("R18", "10k", "RS485_B", GND, group=g)
add("D6", "Diode:SM712_SOT23", SOT23, "PSM712", "ProTek PSM712-LF-T7", {"1": "RS485_A", "2": "RS485_B", "3": GND},
    g, lcsc="C32677")
add("J3", "Connector_Generic:Conn_01x04", HOLES4, "SONDE", "A B GND 12V",
    {"1": "RS485_A", "2": "RS485_B", "3": GND, "4": "V12_PROBE"}, g, hand=True)

# --- XIAO + Wio (Sockel; 5 V Platine → XIAO 5V-Pin) ---------------------------
g = "xiao"
add("J5", "Connector_Generic:Conn_01x07", XIAO_ROW, "XIAO D0-D6",
    "Buchsen 1×7; Abstand zu J6 = 15,24 mm",
    {"1": "SENS_EN", "2": "XIAO_D1", "3": "XIAO_D2", "4": "XIAO_D3", "5": "XIAO_D4", "6": "XIAO_D5",
     "7": "UART_TX"}, g, hand=True)
add("J6", "Connector_Generic:Conn_01x07", XIAO_ROW, "XIAO 5V-D10",
    "Buchsen 1×7",
    {"1": "XIAO_5V", "2": GND, "3": "XIAO_3V3", "4": "XIAO_D8", "5": "XIAO_D9", "6": "XIAO_D10",
     "7": "UART_RX"}, g, hand=True)
c("C2", "10uF 10V", "V5", GND, g)
c("C7", "10uF 10V", "XIAO_3V3", GND, g)

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