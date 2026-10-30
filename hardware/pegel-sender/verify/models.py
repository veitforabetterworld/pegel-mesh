"""SPICE-Modelle und Grenzwerte der Bauteile (Datenblattwerte; "≈" = typischer Wert ähnlicher Bauformen).

Halbleiter als Level-1-MOSFET bzw. Dioden-Modelle, ICs als Verhaltensmodelle ihrer Datenblattfunktion
(gemittelte Wandler, keine Schaltflanken). Schaltbelastung der Wandler rechnet stress.py analytisch.
"""

# ---------------------------------------------------------------- Dioden und MOSFETs
SPICE_MODELS = """
.model SS34 D(IS=8u RS=25m N=1.25 BV=42 IBV=1m CJO=250p)
.model B540C D(IS=25u RS=12m N=1.2 BV=42 IBV=1m CJO=400p)
.model MBR0540 D(IS=1.5u RS=0.15 N=1.05 BV=42 IBV=1m CJO=50p)
.model ZEN10 D(IS=1n RS=4 N=1 BV=10 IBV=5m)
.model ZEN5V6 D(IS=1n RS=10 N=1 BV=5.6 IBV=5m)
.model ZEN12 D(IS=1n RS=6 N=1 BV=12 IBV=5m)
.model TVS26 D(IS=1p RS=0.8 N=1 BV=29.5 IBV=1m)
.model TVS18 D(IS=1p RS=0.45 N=1 BV=21 IBV=1m)
.model TVS15 D(IS=1p RS=0.45 N=1 BV=17.5 IBV=1m)
.model TVS13 D(IS=1p RS=1 N=1 BV=13.8 IBV=1m)
.model TVS7 D(IS=1p RS=1 N=1 BV=7.8 IBV=1m)
.model LEDRED D(IS=1e-19 N=1.9 RS=8)
.model BODY D(IS=1n RS=20m N=1.1)
.model N2N7002 NMOS(LEVEL=1 VTO=1.9 KP=0.25 LAMBDA=0.01)
.model NSI2318 NMOS(LEVEL=1 VTO=1.5 KP=8 LAMBDA=0.01)
.model NFS8205 NMOS(LEVEL=1 VTO=0.8 KP=25 LAMBDA=0.01)
.model PAO3401 PMOS(LEVEL=1 VTO=-0.9 KP=12 LAMBDA=0.01)
.model PAOD4189 PMOS(LEVEL=1 VTO=-2.2 KP=20 LAMBDA=0.01)
.model SWHY SW(VT=0 VH=0.005 RON=1 ROFF=1e10)
"""

DIODE_MODEL = {
    "SS34": "SS34", "B540C": "B540C", "MBR0540": "MBR0540", "10V": "ZEN10", "12V": "ZEN12",
    "SMBJ26A": "TVS26", "5V6": "ZEN5V6", "SMBJ18A": "TVS18", "SMAJ15A": "TVS15", "rot": "LEDRED",
}
MOS_MODEL = {"2N7002": "N2N7002", "SI2318CDS": "NSI2318", "AO3401A": "PAO3401", "AOD4189": "PAOD4189"}

# ---------------------------------------------------------------- Grenzwerte
# Zweipole: V (Spannung), I (Strom), P (Leistung). MOSFET: Vds, Vgs, Id, P. Diode: Vr, If, P.
# ICs: Pin -> (min, max) gegenüber GND oder als (Pin, Bezugspin, min, max).
RES_P = {"0603": 0.1, "0805": 0.125, "2512": 2.0}
RES_V = {"0603": 75, "0805": 150, "2512": 200}

RATINGS = {
    # Dioden (Vr = Sperrspannung, If = Dauerstrom)
    "SS34": {"Vr": 40, "If": 3.0, "P": 1.5},
    "B540C": {"Vr": 40, "If": 5.0, "P": 3.0},
    "MBR0540": {"Vr": 40, "If": 0.5, "P": 0.5},
    "BZT52C10": {"P": 0.41},
    "BZT52C5V6": {"P": 0.41},
    "BZT52C12": {"P": 0.41},
    "SMBJ26A": {"Vwm": 26},
    "SMBJ18A": {"Vwm": 18},
    "SMAJ15A": {"Vwm": 15},
    "SM712": {"Vwm+": 12, "Vwm-": -7},
    "LED": {"If": 0.020, "Vr": 5},
    # MOSFETs
    "2N7002": {"Vds": 60, "Vgs": 20, "Id": 0.115, "P": 0.2},
    "AO3401A": {"Vds": 30, "Vgs": 12, "Id": 4.0, "P": 1.4},
    "AOD4189": {"Vds": 40, "Vgs": 20, "Id": 40, "P": 2.5},
    "SI2318CDS": {"Vds": 40, "Vgs": 20, "Id": 3.5, "P": 1.0},
    "FS8205A": {"Vds": 20, "Vgs": 12, "Id": 6.0, "P": 1.0},
    # Spulen (Irms Dauerstrom, Isat Sättigung) ≈ Herstellerangaben
    "SRP1245A-150M": {"Irms": 6.5, "Isat": 9.0, "DCR": 0.022},
    "NR3015T2R2M": {"Irms": 1.2, "Isat": 1.48, "DCR": 0.11},
    "SRN6045TA-4R7Y": {"Irms": 2.5, "Isat": 2.8, "DCR": 0.04},
    # Elkos (Rippelstrom ≈ Panasonic FK)
    "EEE-FK1V101P": {"V": 35, "Irip": 0.33},
    "EEE-FK1A101P": {"V": 10, "Irip": 0.23},
    # Sonstiges
    "0466002.NR": {"I": 1.5},          # 2-A-Sicherung: dauerhaft ≤ 75 % Nennstrom
    "MKDS": {"I": 17.5, "V": 250},
}

IC_PINS = {
    "U1": {"VSOL": (-0.3, 33), "CHG_LED": (-0.3, 33), "VSYS": (-0.3, 25), "CHG_CSP": (-0.3, 25),
           "MPPT": (-0.3, 6.5), "CHG_COM": (-0.3, 6.5), "CHG_FB": (-0.3, 6.5),
           ("CHG_VG", "VSOL"): (-8, 0.3), ("CHG_DRV", "VSOL"): (-8, 0.3)},
    "U2": {"+3V3": (-0.3, 6), "INA_P": (-0.3, 40), "INA_M": (-0.3, 40), ("INA_P", "INA_M"): (-40, 40)},
    "U3": {("PROT_VDD", "BAT_N"): (-0.3, 10), ("PROT_OD", "BAT_N"): (-0.3, 10)},
    "U4": {"VSYS": (-0.3, 6), "+3V3": (-0.3, 6)},
    "U5": {"VSYS": (-0.3, 6), "BST_SW": (-0.3, 25), "BST_FB": (-0.3, 6), "SENS_EN": (-0.3, 6)},
    "U6": {"+3V3": (-0.3, 4.6)},
    "U7": {"+3V3": (-0.3, 7), "RS485_A": (-7.5, 12.5), "RS485_B": (-7.5, 12.5)},
    "U8": {"VSYS": (-0.3, 17), "T_NTC": (-0.3, "VSYS+5"), "T_REF0": (-0.3, "VSYS+5"), "T_REF2": (-0.3, "VSYS+5"),
           "CHG_INHIBIT": (-0.3, 17), "HEAT_OFF": (-0.3, 17)},
    "U9": {"+3V3": (-0.3, 6), "XIAO_3V3": (-0.3, 6)},
    "U10": {"VSYS": (-0.3, 17), "DC_DIV": (-0.3, "VSYS+5"), "MPPT_REF": (-0.3, "VSYS+5"), "MPPT_EN": (-0.3, 17)},
    "J5": {"SENS_EN": (-0.3, 3.9), "I2C_SCL": (-0.3, 3.9)},
    "J6": {"XIAO_3V3": (-0.3, 3.6), "I2C_SDA": (-0.3, 3.9)},
}
