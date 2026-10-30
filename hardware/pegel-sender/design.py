"""Pegel-Sender-Platine: Bauteile, Werte, Footprints, Herstellernummern und Netze.

Einzige Quelle für Schaltplan (schematic_wired.py) und Platine (gen_pcb.py). Pin-Nummern sind die der Footprint-Pads.
Platinenbeschreibung: README.md im Repo-Root.
"""

from dataclasses import dataclass, field


@dataclass
class Part:
    ref: str
    symbol: str          # "Lib:Name" (KiCad) oder "pegel:Name" (Box-Symbol in schematic_wired.py)
    footprint: str       # "Lib:Name"
    value: str
    mpn: str             # Herstellernummer für die PCBWay-Bestückung ("" = nicht bestückt / mechanisch)
    pins: dict = field(default_factory=dict)   # Pad -> Netz
    group: str = ""      # Funktionsblock (Platzierung, Schaltplanblatt)
    dnp: bool = False


GND = "GND"
R0603 = "Resistor_SMD:R_0603_1608Metric"
R0805 = "Resistor_SMD:R_0805_2012Metric"
R2512 = "Resistor_SMD:R_2512_6332Metric"
C0603 = "Capacitor_SMD:C_0603_1608Metric"
C0805 = "Capacitor_SMD:C_0805_2012Metric"
C1206 = "Capacitor_SMD:C_1206_3216Metric"
C1210 = "Capacitor_SMD:C_1210_3225Metric"

PARTS: list[Part] = []


def add(*args, **kwargs) -> Part:
    p = Part(*args, **kwargs)
    PARTS.append(p)
    return p


def r(ref, value, a, b, fp=R0603, mpn="", group=""):
    return add(ref, "Device:R", fp, value, mpn or f"RES {value} 1% {fp.split('_')[1]}", {"1": a, "2": b}, group)


def c(ref, value, a, b, fp=C0603, mpn="", group=""):
    return add(ref, "Device:C", fp, value, mpn or f"CAP {value} X7R {fp.split('_')[1]}", {"1": a, "2": b}, group)


# ---------------------------------------------------------------- Solar-Eingang
g = "solar"
add("J1", "Connector:Screw_Terminal_01x02", "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal",
    "SOLAR", "Phoenix MKDS 1,5/2-5,08 (1715721)", {"1": "SOLAR_RAW", "2": GND}, g)
add("F1", "Device:Fuse", "Fuse:Fuse_1206_3216Metric", "2A", "Littelfuse 0466002.NR", {"1": "SOLAR_RAW", "2": "SOLAR_F"}, g)
add("D1", "Device:D_TVS", "Diode_SMD:D_SMB", "SMBJ26A", "SMBJ26A", {"1": "SOLAR_F", "2": GND}, g)
add("D2", "Device:D_Schottky", "Diode_SMD:D_SMA", "SS34", "SS34 (40 V 3 A)", {"1": "VSOL", "2": "SOLAR_F"}, g)

# 12-V-Netzteil, mit Solar diodenverodert. Die höhere Quelle speist VSOL.
g = "dc"
add("J7", "Connector:Screw_Terminal_01x02", "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal",
    "12V", "Phoenix MKDS 1,5/2-5,08 (1715721)", {"1": "DC_RAW", "2": GND}, g)
add("F2", "Device:Fuse", "Fuse:Fuse_1206_3216Metric", "2A", "Littelfuse 0466002.NR", {"1": "DC_RAW", "2": "DC_F"}, g)
add("D8", "Device:D_TVS", "Diode_SMD:D_SMB", "SMBJ18A", "SMBJ18A", {"1": "DC_F", "2": GND}, g)
add("D9", "Device:D_Schottky", "Diode_SMD:D_SMA", "SS34", "SS34 (40 V 3 A)", {"1": "VSOL", "2": "DC_F"}, g)

# ---------------------------------------------------------------- MPPT-Lader CN3795 (3 A, 3,61 V)
g = "charger"
add("U1", "pegel:CN3795", "Package_SO:SSOP-10_3.9x4.9mm_P1.00mm", "CN3795", "Consonance CN3795",
    {"1": "CHG_VG", "2": GND, "3": "CHG_LED", "4": "MPPT", "5": "CHG_COM", "6": "CHG_FB", "7": "VSYS",
     "8": "CHG_CSP", "9": "VSOL", "10": "CHG_DRV"}, g)
c("C1", "100nF", "CHG_VG", "VSOL", C0603, "CAP 100nF 50V X7R 0603", g)
add("C2", "Device:C_Polarized", "Capacitor_SMD:CP_Elec_8x10", "100uF 35V", "Panasonic EEE-FK1V101P", {"1": "VSOL", "2": GND}, g)
c("C3", "10uF", "VSOL", GND, C1210, "CAP 10uF 50V X7R 1210", g)
c("C4", "100nF", "VSOL", GND, C0603, "CAP 100nF 50V X7R 0603", g)
add("Q1", "Device:Q_PMOS", "Package_TO_SOT_SMD:TO-252-2", "AOD4189", "AOS AOD4189 (-40 V)",
    {"1": "CHG_DRV", "2": "CHG_SW", "3": "VSOL"}, g)
add("D3", "Device:D_Schottky", "Diode_SMD:D_SMC", "B540C", "Diodes B540C-13-F (40 V 5 A)", {"1": "CHG_SW", "2": GND}, g)
add("L1", "Device:L", "Inductor_SMD:L_Bourns_SRP1245A", "15uH", "Bourns SRP1245A-150M", {"1": "CHG_SW", "2": "CHG_CSP"}, g)
r("R1", "40m", "CHG_CSP", "VSYS", R2512, "RES 40mOhm 1% 2W 2512", g)
r("R2", "200k", "VSYS", "CHG_FB", group=g)
r("R3", "100k", "CHG_FB", GND, group=g)
r("R4", "300k", "VSOL", "MPPT", group=g)
r("R5", "21.5k", "MPPT", GND, group=g)
r("R6", "120", "CHG_COM", "CHG_COMC", group=g)
c("C5", "220nF", "CHG_COMC", GND, group=g)
# Unter ~14 V (Netzteil) liegt 330k parallel zu R4, damit der MPPT-Pin bei 12 V über 1,205 V bleibt.
# Q9 ist ohne Versorgung an (Teiler entspannt), sonst startet der Lader aus 12 V nicht.
# U10 zieht nur bei hoher Panelspannung Q11 auf und schaltet Q9 ab. Hysterese etwa 13–15 V.
g = "mppt"
r("R40", "470k", "VSOL", "VSOL_DIV", group=g)
r("R41", "68.1k", "VSOL_DIV", GND, group=g)
# Referenz aus +3V3: an VSYS hinge die Schwelle an der Akkuspannung (2,8 V: 11,2 V), ein 12-V-Netzteil
# gälte bei leerem Akku als Panel und könnte nicht laden. 3,3 V · 1M/1,976M = 1,67 V → 13,2 V an VSOL.
r("R42", "976k", "+3V3", "MPPT_REF", group=g)
r("R43", "1M", "MPPT_REF", GND, group=g)
add("U10", "Comparator:TLV3401", "Package_TO_SOT_SMD:SOT-23-5", "TLV3401", "TI TLV3401IDBVR",
    {"1": "MPPT_EN", "2": GND, "3": "VSOL_DIV", "4": "MPPT_REF", "5": "VSYS"}, g)
r("R44", "1M", "MPPT_EN", "VSOL_DIV", group=g)
r("R45", "1M", "MPPT_EN", "VSYS", group=g)
c("C21", "100nF", "VSYS", GND, group=g)
add("Q11", "Device:Q_NMOS", "Package_TO_SOT_SMD:SOT-23", "2N7002", "2N7002",
    {"1": "MPPT_EN", "2": GND, "3": "MPPT_NG"}, g)
r("R50", "1M", "VSOL", "MPPT_NG", group=g)
add("D11", "Device:D_Zener", "Diode_SMD:D_SOD-123", "10V", "BZT52C10", {"1": "MPPT_NG", "2": GND}, g)
add("Q8", "Device:Q_NMOS", "Package_TO_SOT_SMD:SOT-23", "2N7002", "2N7002",
    {"1": "MPPT_NG", "2": GND, "3": "MPPT_PD"}, g)
r("R51", "10k", "MPPT_GATE", "MPPT_PD", group=g)
add("Q9", "Device:Q_PMOS", "Package_TO_SOT_SMD:SOT-23", "AO3401A", "AOS AO3401A",
    {"1": "MPPT_GATE", "2": "VSOL", "3": "MPPT_PULL"}, g)
r("R46", "100k", "VSOL", "MPPT_GATE", group=g)
add("D10", "Device:D_Zener", "Diode_SMD:D_SOD-123", "10V", "BZT52C10", {"1": "VSOL", "2": "MPPT_GATE"}, g)
r("R47", "330k", "MPPT_PULL", "MPPT", group=g)
add("C6", "Device:C_Polarized", "Capacitor_SMD:CP_Elec_6.3x7.7", "100uF 10V", "Panasonic EEE-FK1A101P", {"1": "VSYS", "2": GND}, g)
c("C7", "10uF", "VSYS", GND, C1206, "CAP 10uF 16V X7R 1206", g)
add("D4", "Device:LED", "LED_SMD:LED_0805_2012Metric", "rot", "LED rot 0805", {"1": "CHG_LED", "2": "CHG_LEDA"}, g)
r("R7", "10k", "CHG_LEDA", "VSOL", R0805, "RES 10k 1% 0805", g)

# ---------------------------------------------------------------- Akku: Messung (INA226) und Schutz (HY2112 + 2× FS8205A)
g = "battery"
r("R8", "10m", "VSYS", "BAT_P", R2512, "RES 10mOhm 1% 2W 2512", g)
add("U2", "Sensor_Energy:INA226", "Package_SO:TSSOP-10_3x3mm_P0.5mm", "INA226", "TI INA226AIDGSR",
    {"1": GND, "2": GND, "3": "", "4": "I2C_SDA", "5": "I2C_SCL", "6": "+3V3", "7": GND, "8": "INA_M",
     "9": "INA_M", "10": "INA_P"}, g)
c("C8", "100nF", "+3V3", GND, group=g)
# Kelvin-Messleitungen vom Shunt; 10 Ω begrenzen den Strom bei Fehlern (Verstärkungsfehler < 0,1 %).
r("R37", "10", "VSYS", "INA_P", group=g)
r("R38", "10", "BAT_P", "INA_M", group=g)
add("J2", "Connector:Screw_Terminal_01x02", "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal",
    "AKKU 3,2V", "Phoenix MKDS 1,5/2-5,08 (1715721)", {"1": "BAT_P", "2": "BAT_N"}, g)
add("U3", "pegel:HY2112", "Package_TO_SOT_SMD:SOT-23-6", "HY2112-CB", "HYCON HY2112-CB",
    {"1": "PROT_OD", "2": "PROT_CS", "3": "PROT_OC", "4": "", "5": "PROT_VDD", "6": "BAT_N"}, g)
r("R9", "330", "BAT_P", "PROT_VDD", group=g)
c("C9", "100nF", "PROT_VDD", "BAT_N", group=g)
r("R10", "2k", "PROT_CS", GND, group=g)
r("R49", "100k", "BAT_N", GND, group=g)   # ohne Zelle liegt VSS nicht offen an VSYS
for i, ref in enumerate(("Q2", "Q3")):
    add(ref, "pegel:FS8205A", "Package_SO:TSSOP-8_4.4x3mm_P0.65mm", "FS8205A", "Fortune FS8205A",
        {"1": "PROT_D", "2": "BAT_N", "3": "BAT_N", "4": "PROT_OD", "5": "PROT_OC", "6": GND, "7": GND, "8": "PROT_D"}, g)

# ---------------------------------------------------------------- 3,3 V: TPS63900 (Buck-Boost, 75 nA)
g = "3v3"
add("U4", "Regulator_Switching:TPS63900", "Package_SON:WSON-10-1EP_2.5x2.5mm_P0.5mm_EP1.2x2mm_ThermalVias",
    "TPS63900", "TI TPS63900DSKR",
    {"1": "VSYS", "2": "VSYS", "3": "BB_CFG1", "4": GND, "5": GND, "6": "+3V3", "7": "BB_LX2", "8": GND,
     "9": "BB_LX1", "10": "VSYS", "11": GND}, g)
r("R11", "36.5k", "BB_CFG1", GND, group=g)
add("L2", "Device:L", "Inductor_SMD:L_Taiyo-Yuden_NR-30xx", "2.2uH", "Taiyo Yuden NR3015T2R2M", {"1": "BB_LX1", "2": "BB_LX2"}, g)
c("C10", "10uF", "VSYS", GND, C0805, "CAP 10uF 10V X5R 0805", g)
c("C11", "22uF", "+3V3", GND, C0805, "CAP 22uF 6.3V X5R 0805", g)
# Ideale Diode: Wandler speist den XIAO, USB-3,3 V kann nicht auf +3V3 und den Akku zurück.
# CE an VOUT: steigt der XIAO-Pin über die Wandlerseite, sperrt der Schalter.
add("U9", "Power_Protection:LM66100", "Package_TO_SOT_SMD:SOT-363_SC-70-6", "LM66100", "TI LM66100DCKR",
    {"1": "+3V3", "2": GND, "3": "XIAO_3V3", "4": "", "5": GND, "6": "XIAO_3V3"}, g)
c("C20", "1uF", "XIAO_3V3", GND, C0603, "CAP 1uF 10V X5R 0603", g)

# ---------------------------------------------------------------- 12 V für die Sonde: TPS61040 + Lastschalter
g = "12v"
add("U5", "Regulator_Switching:TPS61040DBV", "Package_TO_SOT_SMD:SOT-23-5", "TPS61040", "TI TPS61040DBVR",
    {"1": "BST_SW", "2": GND, "3": "BST_FB", "4": "SENS_EN", "5": "VSYS"}, g)
add("L3", "Device:L", "Inductor_SMD:L_Taiyo-Yuden_NR-30xx", "10uH", "Taiyo Yuden NR3015T100M", {"1": "VSYS", "2": "BST_SW"}, g)
add("D5", "Device:D_Schottky", "Diode_SMD:D_SOD-123", "MBR0540", "onsemi MBR0540T1G (40 V)", {"1": "V12_RAW", "2": "BST_SW"}, g)
r("R12", "820k", "V12_RAW", "BST_FB", group=g)
r("R13", "91k", "BST_FB", GND, group=g)
c("C12", "22pF", "V12_RAW", "BST_FB", group=g)
c("C13", "4.7uF", "V12_RAW", GND, C1206, "CAP 4.7uF 25V X7R 1206", g)
c("C14", "4.7uF", "VSYS", GND, C0805, "CAP 4.7uF 10V X5R 0805", g)
r("R14", "100k", "SENS_EN", GND, group=g)
add("Q4", "Device:Q_PMOS", "Package_TO_SOT_SMD:SOT-23", "AO3401A", "AOS AO3401A",
    {"1": "PSW_G", "2": "V12_RAW", "3": "V12_PROBE"}, g)
r("R15", "100k", "V12_RAW", "PSW_G", group=g)
# Teiler 100k/100k: Vgs ≈ −6,2 V statt −12,3 V (AO3401A: max. ±12 V)
r("R53", "100k", "PSW_G", "PSW_PD", group=g)
add("Q5", "Device:Q_NMOS", "Package_TO_SOT_SMD:SOT-23", "2N7002", "2N7002", {"1": "SENS_EN", "2": GND, "3": "PSW_PD"}, g)

# ---------------------------------------------------------------- RS485: SC16IS740 (I²C→UART) + MAX3485
g = "rs485"
add("U6", "Interface_UART:SC16IS740", "Package_SO:TSSOP-16_4.4x5mm_P0.65mm", "SC16IS740", "NXP SC16IS740IPW",
    {"1": "+3V3", "2": "+3V3", "3": "+3V3", "4": "", "5": "I2C_SCL", "6": "I2C_SDA", "7": "", "8": "+3V3",
     "9": GND, "10": "UART_RTS", "11": GND, "12": "UART_TX", "13": "UART_RX", "14": "UART_RST", "15": "XTAL1",
     "16": "XTAL2"}, g)
c("C15", "100nF", "+3V3", GND, group=g)
r("R16", "10k", "UART_RST", "+3V3", group=g)
r("R36", "10k", "UART_RX", "+3V3", group=g)   # RO ist beim Senden hochohmig
add("Y1", "Device:Crystal_GND24", "Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm", "14.7456MHz", "Crystal 14.7456 MHz 3225 18pF",
    {"1": "XTAL1", "2": GND, "3": "XTAL2", "4": GND}, g)
c("C16", "27pF", "XTAL1", GND, group=g)   # 18-pF-Quarz, Streuung ~4,5 pF: 2*(18-4,5)
c("C17", "27pF", "XTAL2", GND, group=g)
add("U7", "Interface_UART:MAX3485", "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", "MAX3485", "MAX3485ESA+T",
    {"1": "UART_RX", "2": "UART_RTS", "3": "UART_RTS", "4": "UART_TX", "5": GND, "6": "RS485_A", "7": "RS485_B",
     "8": "+3V3"}, g)
c("C18", "100nF", "+3V3", GND, group=g)
r("R17", "10k", "RS485_A", "+3V3", group=g)
r("R18", "10k", "RS485_B", GND, group=g)
add("JP1", "Jumper:SolderJumper_2_Open", "Jumper:SolderJumper-2_P1.3mm_Open_RoundedPad1.0x1.5mm", "120R ein", "",
    {"1": "RS485_A", "2": "RS485_TERM"}, g)
r("R19", "120", "RS485_TERM", "RS485_B", R0805, "RES 120R 1% 0805", g)
add("D6", "Diode:SM712_SOT23", "Package_TO_SOT_SMD:SOT-23", "SM712", "Semtech SM712.TCT",
    {"1": "RS485_A", "2": "RS485_B", "3": GND}, g)
add("D12", "Device:D_TVS", "Diode_SMD:D_SMA", "SMAJ15A", "SMAJ15A", {"1": "V12_PROBE", "2": GND}, "12v")
add("J3", "Connector:Screw_Terminal_01x04", "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-4-5.08_1x04_P5.08mm_Horizontal",
    "SONDE V+ V- A B", "Phoenix MKDS 1,5/4-5,08 (1715747)",
    {"1": "V12_PROBE", "2": GND, "3": "RS485_A", "4": "RS485_B"}, g)

# ---------------------------------------------------------------- Frost: NTC, Komparator, Ladesperre, Heizung
g = "frost"
r("R20", "330k", "VSYS", "T_NTC", group=g)
add("TH1", "Device:Thermistor_NTC", "Resistor_SMD:R_0603_1608Metric", "100k B4250", "Murata NCP18WF104F03RC",
    {"1": "T_NTC", "2": "NTC_SEL1"}, g)
add("JP2", "Jumper:SolderJumper_3_Bridged12", "Jumper:SolderJumper-3_P1.3mm_Bridged12_RoundedPad1.0x1.5mm", "NTC intern/extern", "",
    {"1": "NTC_SEL1", "2": GND, "3": "NTC_SEL3"}, g)
add("J4", "Connector:Conn_01x02_Pin", "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical", "NTC extern", "",
    {"1": "T_NTC", "2": "NTC_SEL3"}, g, dnp=True)
r("R21", "470k", "VSYS", "T_REF0", group=g)   # B4250: Ladestopp ~0 °C, Heizung ~+2 °C
r("R22", "28.7k", "T_REF0", "T_REF2", group=g)
r("R23", "499k", "T_REF2", GND, group=g)
# Kanal A: bei Kälte Ausgang hoch, Q10 zieht den MPPT-Pin auf GND, der CN3795 lädt nicht mehr.
# Nicht über den Lade-FET des Akkuschutzes: dessen Body-Diode läge dann im Entladepfad, ~0,6 V über
# den FETs löst beim HY2112 den Entlade-Überstrom (100–200 mV) aus und trennt den Akku.
add("U8", "Comparator:LM393", "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", "TLV3402", "TI TLV3402IDR",
    {"1": "CHG_INHIBIT", "2": "T_REF0", "3": "T_NTC", "4": GND, "5": "T_REF2", "6": "T_NTC", "7": "HEAT_OFF", "8": "VSYS"}, g)
c("C19", "100nF", "VSYS", GND, group=g)
r("R48", "1M", "CHG_INHIBIT", "VSYS", group=g)
add("Q10", "Device:Q_NMOS", "Package_TO_SOT_SMD:SOT-23", "2N7002", "2N7002",
    {"1": "CHG_INHIBIT", "2": GND, "3": "MPPT"}, g)
r("R24", "4.7M", "CHG_INHIBIT", "T_NTC", group=g)   # Mitkopplung: bei Kälte hebt der Ausgang T_NTC, ~1 K Hysterese
r("R25", "1M", "HEAT_OFF", "VSYS", group=g)
r("R26", "10M", "HEAT_OFF", "T_REF2", group=g)
add("Q6", "Device:Q_NMOS", "Package_TO_SOT_SMD:SOT-23", "2N7002", "2N7002", {"1": "HEAT_OFF", "2": GND, "3": "HEAT_G"}, g)
r("R27", "100k", "VSOL", "HEAT_G", group=g)
add("D7", "Device:D_Zener", "Diode_SMD:D_SOD-123", "12V", "BZT52C12", {"1": "HEAT_G", "2": GND}, g)
add("Q7", "Device:Q_NMOS", "Package_TO_SOT_SMD:SOT-23", "SI2318CDS", "Vishay SI2318CDS (40 V)",
    {"1": "HEAT_G", "2": GND, "3": "HEAT_N"}, g)
for i in range(6):
    r(f"R{28 + i}", "390", "VSOL", "HEAT_N", R2512, "RES 390R 1% 2W 2512", g)

# ---------------------------------------------------------------- XIAO nRF52840 + Wio-SX1262 (gesteckt)
g = "xiao"
add("J5", "Connector_Generic:Conn_01x07", "Connector_PinSocket_2.54mm:PinSocket_1x07_P2.54mm_Vertical", "XIAO D0-D6",
    "Buchsenleiste 1x7 2,54 mm",
    {"1": "SENS_EN", "2": "", "3": "", "4": "", "5": "", "6": "", "7": "I2C_SCL"}, g)
add("J6", "Connector_Generic:Conn_01x07", "Connector_PinSocket_2.54mm:PinSocket_1x07_P2.54mm_Vertical", "XIAO 5V-D7",
    "Buchsenleiste 1x7 2,54 mm",
    {"1": "", "2": GND, "3": "XIAO_3V3", "4": "", "5": "", "6": "", "7": "I2C_SDA"}, g)
r("R34", "4.7k", "I2C_SCL", "+3V3", group=g)
r("R35", "4.7k", "I2C_SDA", "+3V3", group=g)

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
