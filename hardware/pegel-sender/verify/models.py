"""SPICE-Modelle und Grenzwerte der Bauteile (Datenblattwerte; "≈" = typischer Wert ähnlicher Bauformen).

Halbleiter als Level-1-MOSFET bzw. Dioden-Modelle, ICs als Verhaltensmodelle ihrer Datenblattfunktion
(gemittelte Wandler, keine Schaltflanken). Schaltbelastung der Wandler rechnet stress.py analytisch.
"""

# ---------------------------------------------------------------- Dioden und MOSFETs
SPICE_MODELS = """
.model SS54 D(IS=25u RS=12m N=1.2 BV=42 IBV=1m CJO=400p)
.model B0540W D(IS=1.5u RS=0.15 N=1.05 BV=42 IBV=1m CJO=50p)
.model B5819W D(IS=3u RS=0.08 N=1.1 BV=42 IBV=1m CJO=110p)
.model D4148 D(IS=2.5n RS=0.6 N=1.9 BV=100 IBV=1u CJO=2p)
.model ZEN10 D(IS=1n RS=4 N=1 BV=10 IBV=5m)
.model TVS28 D(IS=1p RS=0.8 N=1 BV=32.7 IBV=1m)
.model TVS18A D(IS=1p RS=0.6 N=1 BV=21 IBV=1m)
.model TVS13 D(IS=1p RS=1 N=1 BV=13.8 IBV=1m)
.model TVS7 D(IS=1p RS=1 N=1 BV=7.8 IBV=1m)
.model BODY D(IS=1n RS=20m N=1.1)
.model N2N7002 NMOS(LEVEL=1 VTO=1.9 KP=0.25 LAMBDA=0.01)
.model NHL2310 NMOS(LEVEL=1 VTO=1.8 KP=6 LAMBDA=0.01)
.model PAO3401 PMOS(LEVEL=1 VTO=-0.9 KP=12 LAMBDA=0.01)
"""

DIODE_MODEL = {
    "SS54": "SS54", "B0540W": "B0540W", "B5819W": "B5819W", "1N4148WS": "D4148", "BAV70": "D4148",
    "10V": "ZEN10", "SMBJ28A": "TVS28", "SMAJ18A": "TVS18A",
}
MOS_MODEL = {"2N7002": "N2N7002", "HL2310A": "NHL2310", "AO3401A": "PAO3401"}

# ---------------------------------------------------------------- Grenzwerte
# Zweipole: V (Spannung), I (Strom), P (Leistung). MOSFET: Vds, Vgs, Id, P. Diode: Vr, If, P.
# ICs: Pin -> (min, max) gegenüber GND oder als (Pin, Bezugspin, min, max).
RES_P = {"0603": 0.1, "1206": 0.25}
RES_V = {"0603": 75, "1206": 200}

RATINGS = {
    # Dioden (Vr = Sperrspannung, If = Dauerstrom)
    "SS54": {"Vr": 40, "If": 5.0, "P": 1.5},
    "B0540W": {"Vr": 40, "If": 0.5, "P": 0.5},
    "B5819W": {"Vr": 40, "If": 1.0, "P": 0.5},
    "1N4148WS": {"Vr": 75, "If": 0.15, "P": 0.2},
    "BAV70": {"Vr": 70, "If": 0.2},
    "BZT52C10": {"P": 0.41},
    "SMBJ28A": {"Vwm": 28},
    "SMAJ18A": {"Vwm": 18},
    "SM712": {"Vwm+": 12, "Vwm-": -7},
    # MOSFETs
    "2N7002": {"Vds": 60, "Vgs": 20, "Id": 0.115, "P": 0.2},
    "AO3401A": {"Vds": 30, "Vgs": 12, "Id": 4.0, "P": 1.4},
    "HL2310A": {"Vds": 60, "Vgs": 20, "Id": 3.0, "P": 1.2},
    # Spulen (Irms Dauerstrom, Isat Sättigung, DCR) nach Bourns-Datenblatt
    "RLB0914-150KL": {"Irms": 2.4, "Isat": 5.3, "DCR": 0.060},
    "RLB0912-100KL": {"Irms": 2.5, "Isat": 3.6, "DCR": 0.043},
    # Sonstiges
    "MKDS": {"I": 17.5, "V": 250},
}

IC_PINS = {
    "U1": {"VSOL": (-0.3, 40), "CHG_FB": (-0.3, 6), "CHG_SW": (-1.2, 40), ("CHG_BOOT", "CHG_SW"): (-0.3, 8)},
    "U2": {"+5V": (-0.3, 32), "CC_SENSE": (-0.3, 32), "CC_INT": (-0.3, 32), "VIN_DIV": (-0.3, 32),
           "VREF": (-0.3, 32), "T_NTC": (-0.3, 32), "T_REF0": (-0.3, 32), "T_REF2": (-0.3, 32)},
    "U3": {"VSOL": (-0.3, 30), "+5V": (-0.3, 6)},
    "U4": {"VREF": (-0.3, 36)},
    "U5": {"VSYS": (-0.3, 7), "BST_SW": (-0.3, 30), "BST_FB": (-0.3, 7), "SENS_EN": (-0.3, 7)},
    "U6": {"RS_VCC": (-0.3, 6), "RS485_A": (-7, 12), "RS485_B": (-7, 12), "RS_DE": (-0.3, "RS_VCC+0.3"),
           "UART_RX": (-0.3, "RS_VCC+0.3")},
    "J5": {"SENS_EN": (-0.3, "XIAO_3V3+0.3"), "UART_TX": (-0.3, "XIAO_3V3+0.3")},
    "J6": {"XIAO_3V3": (-0.3, 3.6), "UART_RX": (-0.3, "XIAO_3V3+0.3")},
}
