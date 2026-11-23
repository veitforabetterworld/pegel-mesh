"""Gemeinsamer Teil der 12-V-Thermolader (lader-12v-netz, lader-12v-solar).

Alles hinter dem 5-V-Knoten ist der Thermolader 5 V: Thermostat, Hitzeabschaltung, Heizung und die Schalter vor dem
Lader des XIAO, mit denselben Nummern und Widerstandswerten, aber kleineren Gehäusen, wo es sie als Basic/Preferred
gibt. Davor sitzt je Variante ein Abwärtswandler statt Q1 und D1.
"""

import importlib.util
import os

from parts import C0402, GND, R0402, R0805, Netlist

PADS2_B = "pegel:SolderPads_1x02_B_1.8x1.8mm_P2.54mm"
WITHOUT = ("J1", "Q1", "D1")      # der 5-V-Eingang
TO_0402 = ("R1", "R3", "R4", "R5", "R6", "R8", "R9")    # R2 (30k) und R7 (2M) gibt es in 0402 nur als Extended
CAPS_0402 = {"C1": "10uF 6.3V 0402", "C2": "100nF 50V 0402", "C4": "10uF 6.3V 0402"}
HEATER = ("R19", "R20", "R21", "R22", "R23")             # 0805: je 0,08 W von 0,125 W


def base(label: str) -> Netlist:
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lader-5v", "design.py")
    spec = importlib.util.spec_from_file_location("lader5v_design", path)
    five = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(five)
    n = Netlist()
    for p in five.PARTS:
        if p.ref in WITHOUT:
            continue
        if p.ref in TO_0402 or p.ref in HEATER:
            n.r(p.ref, p.value, p.pins["1"], p.pins["2"], R0402 if p.ref in TO_0402 else R0805, p.group)
        elif p.ref in CAPS_0402:
            n.c(p.ref, CAPS_0402[p.ref], p.pins["1"], p.pins["2"], p.group)
        else:
            n.parts.append(p)
    assert all(q.footprint.split(":")[1].startswith(("C_0402", "R_0402", "R_0805")) for q in n.parts
               if q.ref in TO_0402 + HEATER + tuple(CAPS_0402))
    n.add("J1", "Connector_Generic:Conn_01x02", PADS2_B, label, "Lötpads unten: 12 V + GND",
          {"1": "VIN_RAW", "2": GND}, "input", hand=True)
    return n


def inductor(n: Netlist):
    n.add("L1", "Device:L", "pegel:L_4030_HandSolder", "22uH", "Sunlord SWPA4030S220MT (22 µH, LCSC C83472)",
          {"1": "BUCK_SW", "2": "V5"}, "buck", lcsc="C83472")


def diodes(n: Netlist, tvs: str, tvs_lcsc: str):
    # D2: Verpolschutz, nachts kein Strom ins Panel. AO3401A wie am 5-V-Lader ginge nicht, er hält nur 12 V am Gate.
    n.add("D2", "Device:D_Schottky", "Diode_SMD:D_SOD-323", "B5819WS", "B5819WS (40 V 1 A)",
          {"1": "VIN", "2": "VIN_RAW"}, "input", lcsc="C64886")
    n.add("D1", "Device:D_TVS", "Diode_SMD:D_SMF", tvs, tvs + " (200 W)", {"1": "VIN", "2": GND}, "input",
          lcsc=tvs_lcsc)
    n.add("D3", "Device:D_Schottky", "Diode_SMD:D_SOD-323", "B5819WS", "B5819WS (40 V 1 A)",
          {"1": "BUCK_SW", "2": GND}, "buck", lcsc="C64886")
