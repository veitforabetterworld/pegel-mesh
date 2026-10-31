"""Lage der Bauteile im Schaltplan je Funktionsblock (Einheit 2,54 mm, y nach unten).

parts:  Ref (bei mehreren Einheiten "Ref:Einheit") -> (x, y, Drehung[, "m"]); "m" spiegelt links/rechts.
        Zweipole: R/C/L/Sicherung/NTC stehen bei 0° senkrecht (Pin 1 oben), Dioden liegen bei 0° waagrecht
        (Pin 1 = Kathode links); 90° dreht gegen den Uhrzeigersinn.
power:  (Netz, x, y) Versorgungs- bzw. GND-Symbol; alle Pins des Netzes werden dorthin verdrahtet.
        Ohne Eintrag bekommt jeder Pin ein eigenes Symbol.
labels: (Netz, x, y, Richtung des Texts L/R/U/D) für Netze, die das Blatt verlassen.
fields_left: Zweipole mit Bezeichnung links statt rechts.
"""

GROUPS = [
    ("solar", "Eingang"),
    ("charger", "Lader"),
    ("mppt", "Regelung"),
    ("battery", "Akku"),
    ("frost", "Frost"),
    ("12v", "Sonde 12 V"),
    ("rs485", "RS485"),
    ("xiao", "XIAO"),
]

LAYOUT = {
    # Klemme → TVS nach Masse → Verpolschutzdiode → VSOL mit Eingangskondensatoren
    "solar": {
        "parts": {
            "J1": (0, 0, 0, "m"),
            "D1": (6, 1.5, 270),
            "D2": (10.5, 0, 180),
            "C1": (15, 3.5, 0), "C2": (18, 3.5, 0), "C3": (21, 3.5, 0),
        },
        "power": [("VSOL", 23, 0), ("GND", 4, 5)],
    },
    # VSOL → TPS5430 → Schaltknoten (D3 nach Masse) → L1 → CHG_OUT → Q1 (Rückstromsperre) → VSYS.
    # VSENSE mit Teiler R1/R2, darüber speist die Regelung über R3 (CHG_LIM) ein.
    "charger": {
        "parts": {
            "C4": (1, 7, 0),
            "U1": (9, 6, 0),
            "C5": (16, 2, 90),
            "D3": (18.5, 9, 270),
            "L1": (22, 4, 90),
            "C6": (26, 7.5, 0), "C7": (29, 7.5, 0),
            "R1": (33, 7.5, 0), "R2": (33, 11, 0), "R3": (36, 12.5, 90),
            "Q1": (40.5, 4, 180, "m"),
            "R4": (44, 7, 0), "Q2": (44, 12, 0),
            "R5": (48.5, 9, 0), "R6": (48.5, 13, 0),
            "C8": (52, 7.5, 0),
        },
        "power": [("VSOL", 1, 3), ("VSYS", 52, 3), ("VSOL", 48.5, 6)],
        "labels": [("CHG_LIM", 39, 12.5, "R")],
        "fields_left": {"C4"},
    },
    # 5 V (HT7550) und 2,5 V (CJ431) aus VSOL. LM324: A Ladestrom (Shunt gegen VREF/25), B Panel-Arbeitspunkt,
    # C Ladesperre, D Heizung. A/B/C ziehen über D4/D5 den Lader zurück (CHG_LIM).
    "mppt": {
        "parts": {
            "C9": (0, 4.5, 0), "U3": (4, 2, 0), "C10": (9, 4.5, 0),
            "R7": (12.5, 4, 0), "U4": (12.5, 9, 0),
            "R8": (17, 4, 0), "R9": (17, 8, 0), "R10": (20.5, 6.5, 90), "R11": (20.5, 12.5, 90),
            "U2:1": (26, 9, 0), "C12": (25.5, 5, 90),
            "JP2": (11, 17, 0), "R14": (14.5, 17, 90), "R12": (17.5, 16, 0), "R13": (17.5, 20, 0),
            "U2:2": (26, 20, 0), "C13": (25.5, 16, 90), "R35": (29, 16, 90),
            "D4": (33, 14, 0), "D5": (33, 27, 0),
            "U2:3": (26, 28, 0), "U2:4": (26, 36, 0), "U2:5": (36, 36, 0), "C11": (40, 36, 0),
        },
        "power": [("VSOL", 0, 1), ("VSOL", 11, 14)],
        "labels": [("CHG_LIM", 37, 14, "R"), ("BAT_N", 20.5, 15.5, "D"), ("VREF", 15, 9, "L"),
                   ("T_NTC", 21, 27, "L"), ("T_REF0", 21, 29, "L"), ("T_REF2", 21, 35, "L"),
                   ("CHG_INH", 31, 30, "R"), ("HEAT_OFF", 31, 36, "R")],
    },
    # Akku an J2, Strommessung R15‖R16 im Minuspol
    "battery": {
        "parts": {
            "J2": (10, 0, 0),
            "R15": (4, 4, 0), "R16": (7, 4, 0),
        },
        "power": [("VSYS", 4, -1)],
        "labels": [("BAT_N", 2, 2, "L")],
        "fields_left": {"R15"},
    },
    # NTC an J4 gegen R17 aus VREF, Schwellenkette R18–R20, Mitkopplung R21/R22; Heizung über Q3 → Q4.
    "frost": {
        "parts": {
            "J4": (-6, 5, 0),
            "R17": (0, 3.5, 0), "C14": (3, 8, 0),
            "R18": (8, 3.5, 0), "R19": (8, 7, 0), "R20": (8, 10.5, 0),
            "R21": (13, 4.5, 90), "R22": (13, 10.5, 90),
            "Q3": (21, 11, 0),
            "R23": (25, 6, 0), "D6": (27.5, 12.5, 270),
            "Q4": (32, 11, 0),
        },
        "power": [("VSOL", 25, 2.5), ("VSOL", -2, 1)],
        "labels": [("VREF", 0, 0.5, "U"), ("VREF", 8, 0.5, "U"), ("T_NTC", 4.5, 5.5, "R"), ("CHG_INH", 16, 4.5, "R"),
                   ("HEAT_OFF", 16, 10.5, "R"), ("T_REF0", 10.5, 6, "R"), ("T_REF2", 10.5, 9, "R")],
        "fields_left": {"R17", "R18", "R19", "R20"},
    },
    # VSYS → L2 → Schaltknoten → D7 → V12_RAW; Q5 schaltet auf V12_PROBE, angesteuert über Q6 (SENS_EN).
    "12v": {
        "parts": {
            "C17": (4, 3.5, 0),
            "L2": (10.5, 2, 90),
            "U5": (10, 8, 0),
            "R26": (4, 10.5, 0),
            "D7": (16.5, 2, 180),
            "C16": (20, 3.5, 0),
            "R24": (25, 3.5, 0), "R25": (25, 6.5, 0), "C15": (28.5, 3.5, 0),
            "R27": (37.5, 3.5, 0), "R28": (37.5, 6.5, 0),
            "Q6": (36.5, 11, 0),
            "Q5": (41.5, 4, 180, "m"),
            "D8": (42.5, 7.5, 270),
        },
        "power": [("VSYS", 1, 2)],
        "labels": [("SENS_EN", 1, 9, "L"), ("SENS_EN", 32.5, 11, "L"), ("V12_PROBE", 44.5, 6, "R"),
                   ("PSW_PD", 39.5, 9, "R")],
        "fields_left": {"C17", "R27", "R28"},
    },
    # Q7 versorgt den SP3485 nur bei eingeschalteter Sonde. TX schaltet über Q8 den Treiber (DI fest auf GND),
    # danach Schutz, Ruhepegel, Abschluss und die Klemme zur Sonde.
    "rs485": {
        "parts": {
            "R29": (1, 3.5, 0), "Q7": (7, 3, 180, "m"), "C18": (10, 7, 0),
            "R31": (13, 7, 0), "R30": (16, 7, 0),
            "Q8": (8, 15, 0),
            "U6": (21, 12, 0),
            "R32": (29, 5, 0), "R33": (36, 16.5, 0),
            "D9": (32, 10.5, 270),
            "J3": (44, 6, 0),
        },
        "power": [("XIAO_3V3", 1, 0.5)],
        "labels": [("PSW_PD", -1, 3, "L"), ("UART_TX", 4, 15, "L"), ("UART_RX", 15, 10, "L"),
                   ("V12_PROBE", 42, 5, "L")],
    },
    # XIAO in zwei Buchsenleisten, Versorgung aus dem Akku über D10
    "xiao": {
        "parts": {
            "J5": (12, 6, 0), "J6": (12, 16, 0),
            "D10": (2, 15, 180), "C19": (6, 17.5, 0),
        },
        "power": [("VSYS", -2, 15), ("XIAO_3V3", 6, 12.5)],
        "wires": [("XIAO_3V3", 6, 15, 10, 15), ("XIAO_3V3", 6, 12.5, 6, 15)],
        "labels": [("SENS_EN", 10, 3, "L"), ("UART_TX", 9, 9, "L"), ("UART_RX", 9, 22, "L")],
        "fields_left": {"C19"},
    },
}
