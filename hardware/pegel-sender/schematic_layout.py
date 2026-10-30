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
    ("solar", "Solar"),
    ("dc", "12 V"),
    ("charger", "Lader"),
    ("mppt", "MPPT"),
    ("battery", "Akku"),
    ("3v3", "3,3 V"),
    ("12v", "Sonde 12 V"),
    ("rs485", "RS485"),
    ("frost", "Frost"),
    ("xiao", "XIAO"),
]

LAYOUT = {
    # Klemme → Sicherung → Verpolschutzdiode → VSOL, TVS nach Masse
    "solar": {
        "parts": {
            "J1": (0, 0, 0, "m"),
            "F1": (4.5, 0, 90),
            "D1": (8, 1.5, 270),
            "D2": (11.5, 0, 180),
        },
        "power": [("VSOL", 15, 0), ("GND", 4, 4)],
    },
    "dc": {
        "parts": {
            "J7": (0, 0, 0, "m"),
            "F2": (4.5, 0, 90),
            "D8": (8, 1.5, 270),
            "D9": (11.5, 0, 180),
        },
        "power": [("VSOL", 15, 0), ("GND", 4, 4)],
    },
    # Leistungspfad oben: VSOL → Eingangs-C → Q1 → Schaltknoten (D3) → L1 → R1 (Strommessung) → VSYS.
    # CN3795 darunter, Gate- und Messleitungen nach oben.
    "charger": {
        "parts": {
            "C2": (4, 2.5, 0), "C3": (11, 2.5, 0), "C4": (14, 2.5, 0),
            "Q1": (19, 1, 90, "m"),
            "D3": (23, 1.5, 270),
            "L1": (26.5, 0, 90),
            "R1": (31.5, 0, 90),
            "C6": (40, 2.5, 0), "C7": (47, 2.5, 0),
            "U1": (27, 10, 0),
            "C1": (20, 8.5, 180),
            "R4": (12, 9.5, 0), "R5": (12, 12.5, 0),
            "R6": (20.5, 12, 270), "C5": (18, 14.5, 0),
            "D4": (33.5, 10, 0), "R7": (35, 8.5, 180),
            "R2": (38, 9.5, 0), "R3": (38, 12.5, 0),
        },
        "power": [("VSOL", 2, 0), ("VSYS", 50, 0), ("VSOL", 12, 8), ("VSOL", 20, 7), ("VSOL", 35, 7)],
        "wires": [("VSOL", 2, 0, 17, 0), ("VSYS", 33, 0, 50, 0)],
        "labels": [("MPPT", 10, 11, "L")],
        "fields_above": {"D4"},
        "fields_left": {"C1", "C5"},
    },
    # Komparator U10 vergleicht VSOL/7,9 mit 1,67 V (aus +3V3). Darunter (Netzteil) zieht die Kette
    # Q11 → Q8 → Q9 den MPPT-Teiler über R47 herunter.
    "mppt": {
        "parts": {
            "R40": (2, 3.5, 0), "R41": (2, 6.5, 0),
            "R42": (2.5, 13, 90), "R43": (4, 14.5, 0),
            "U10": (8, 6, 0),
            "R44": (8.5, 1, 270),
            "R45": (14, 4.5, 0), "C21": (11, 14.5, 0),
            "Q11": (18, 6, 0),
            "R50": (19, 2.5, 0), "D11": (22.5, 5.5, 270),
            "Q8": (28, 6, 0),
            "R51": (30.5, 4, 90),
            "R46": (33, 2.5, 0), "D10": (37, 2.5, 270),
            "Q9": (41, 4, 180, "m"),
            "R47": (42, 7.5, 0),
        },
        "power": [("+3V3", 1, 13)],
        "labels": [("MPPT", 42, 9, "D")],
        "fields_above": {"R44", "R51"},
        "fields_left": {"R40", "R41"},
    },


    # Shunt R8 zwischen VSYS und Akku+, INA226 misst über Kelvin-Leitungen (R37/R38).
    # Darunter der Akkuschutz: HY2112 steuert die beiden FS8205A im Minuspfad.
    "battery": {
        "parts": {
            "R8": (6.5, -2, 90),
            "J2": (26, -2, 0), "R49": (22, 1.5, 0),
            "R37": (4, 8.5, 0), "R38": (7.5, 11, 90),
            "U2": (14, 9, 0), "C8": (7, 3.5, 0),
            "Q2": (30, 7, 0), "Q3": (30, 15, 0),
            "U3": (30, 23, 0),
            "R9": (21, 20.5, 0), "C9": (24, 23.5, 0),
            "R10": (36, 24.5, 0),
        },
        "power": [("VSYS", 2, -2), ("GND", 34, 9), ("GND", 34, 17)],
        "wires": [("VSYS", 2, -2, 5, -2), ("BAT_P", 8, -2, 24, -2)],
        "labels": [("I2C_SDA", 18, 9, "R"), ("I2C_SCL", 18, 10, "R")],
        "fields_above": {"R8"},
        "fields_left": {"R37", "C9", "C8", "R49"},
    },


    "3v3": {
        "parts": {
            "C10": (3, 3.5, 0),
            "U4": (10, 6, 0),
            "L2": (4, 7.5, 0),
            "R11": (17, 7.5, 0),
            "C11": (21, 3.5, 0),
            "U9": (28.5, 3, 0),
            "C20": (36, 3.5, 0),
        },
        "power": [("VSYS", 0, 2), ("+3V3", 18, 2), ("XIAO_3V3", 38, 2)],
        "wires": [("VSYS", 0, 2, 6, 2), ("+3V3", 14, 2, 25, 2), ("XIAO_3V3", 32, 2, 38, 2)],
        "fields_left": {"C10", "C11"},
    },

    # VSYS → L3 → Schaltknoten → D5 → V12_RAW; Q4 schaltet auf V12_PROBE, angesteuert über Q5 (SENS_EN).
    "12v": {
        "parts": {
            "C14": (4, 3.5, 0),
            "L3": (10.5, 2, 90),
            "U5": (10, 8, 0),
            "R14": (5, 9.5, 0),
            "D5": (16.5, 2, 180),
            "C13": (20, 3.5, 0),
            "R12": (25, 3.5, 0), "R13": (25, 6.5, 0), "C12": (28.5, 3.5, 0),
            "R15": (34, 3.5, 0), "R53": (34, 6.5, 0),
            "Q5": (33, 11, 0),
            "Q4": (38, 4, 180, "m"),
            "D12": (39, 7.5, 270),
        },
        "power": [("VSYS", 1, 2)],
        "wires": [("VSYS", 1, 2, 9, 2), ("V12_RAW", 18, 2, 39, 2)],
        "labels": [("SENS_EN", 3, 8, "L"), ("SENS_EN", 29, 11, "L"), ("V12_PROBE", 41, 6, "R")],
        "fields_left": {"C14", "R15", "R53"},
    },


    # SC16IS740 (I²C → UART) → MAX3485 → Schutz, Abschluss, Ruhepegel → Klemme zur Sonde.
    "rs485": {
        "parts": {
            "R16": (5, 3.5, 0),
            "U6": (12, 10, 0), "C15": (16, 20.5, 0),
            "Y1": (3.5, 18, 0), "C16": (0, 19.5, 0), "C17": (7, 19.5, 0),
            "R36": (19, 6.5, 0),
            "U7": (27, 10, 0), "C18": (30, 19.5, 0),
            "R17": (33, 3.5, 180),
            "D6": (36, 8.5, 270),
            "JP1": (39, 7, 270), "R19": (39, 10.5, 0),
            "R18": (42, 13.5, 0),
            "J3": (48, 4, 0),
        },
        "labels": [("I2C_SCL", 7, 11, "L"), ("I2C_SDA", 7, 12, "L"), ("V12_PROBE", 46, 3, "L")],
        "fields_left": {"C16"},
    },

    # NTC-Teiler und Referenzleiter links, zwei Komparatoren, rechts Ladesperre (Q10 → MPPT) und Heizung.
    "frost": {
        "parts": {
            "J4": (-6, 5, 0),
            "R20": (0, 3.5, 0), "TH1": (0, 6.5, 0), "JP2": (0, 10, 270),
            "R21": (8, 5.5, 0), "R22": (8, 8.5, 0), "R23": (8, 11.5, 0),
            "U8:1": (14, 6, 0), "U8:2": (14, 13, 0), "U8:3": (23, 21, 0), "C19": (28, 21.5, 0),
            "R24": (14.5, 2, 270), "R26": (14.5, 17, 270),
            "R48": (19, 4.5, 0), "Q10": (23, 6, 0),
            "R25": (19, 11.5, 0), "Q6": (23, 13, 0),
            "R27": (27, 9.5, 0), "D7": (29, 12.5, 270),
            "Q7": (33, 11, 0),
            "R28": (36, 5.5, 0), "R29": (40, 5.5, 0), "R30": (44, 5.5, 0),
            "R31": (48, 5.5, 0), "R32": (52, 5.5, 0), "R33": (56, 5.5, 0),
        },
        "power": [("VSOL", 35, 4), ("VSOL", 27, 8)],
        "wires": [("VSOL", 35, 4, 56, 4), ("HEAT_N", 34, 7, 56, 7)],
        "labels": [("MPPT", 24, 4, "U")],
        "fields_above": {"R24"},
        "fields_left": {"R21", "R22", "R23"},
    },



    "xiao": {
        "parts": {
            "J5": (12, 6, 0), "J6": (12, 16, 0),
            "R34": (4, 7.5, 0), "R35": (4, 17.5, 0),
        },
        "labels": [("SENS_EN", 10, 3, "L"), ("I2C_SCL", 1, 9, "L"), ("I2C_SDA", 1, 19, "L")],
    },

}
