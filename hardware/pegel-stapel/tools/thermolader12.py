"""Gemeinsamer Teil der 12-V-Thermolader (lader-12v-netz, lader-12v-solar).

Alles hinter dem 5-V-Knoten ist der Thermolader 5 V: Thermostat, Hitzeabschaltung, Heizung und die Schalter vor dem
Lader des XIAO, mit denselben Nummern und Werten. Davor sitzt je Variante ein Abwärtswandler statt Q1 und D1.
"""

import importlib.util
import os

from parts import GND, Netlist

PADS2_B = "pegel:SolderPads_1x02_B_1.8x1.8mm_P2.54mm"
WITHOUT = ("J1", "Q1", "D1")      # der 5-V-Eingang


def base(label: str) -> Netlist:
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lader-5v", "design.py")
    spec = importlib.util.spec_from_file_location("lader5v_design", path)
    five = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(five)
    n = Netlist()
    n.parts = [p for p in five.PARTS if p.ref not in WITHOUT]
    n.add("J1", "Connector_Generic:Conn_01x02", PADS2_B, label, "Lötpads unten: 12 V + GND",
          {"1": "VIN_RAW", "2": GND}, "input", hand=True)
    return n


def inductor(n: Netlist):
    n.add("L1", "Device:L", "pegel:L_4030_HandSolder", "22uH", "Sunlord SWPA4030S220MT (22 µH, LCSC C83472)",
          {"1": "BUCK_SW", "2": "V5"}, "buck", hand=True)


def diodes(n: Netlist, tvs: str, tvs_lcsc: str):
    # D2: Verpolschutz, nachts kein Strom ins Panel. AO3401A wie am 5-V-Lader ginge nicht, er hält nur 12 V am Gate.
    n.add("D2", "Device:D_Schottky", "Diode_SMD:D_SOD-323", "B5819WS", "B5819WS (40 V 1 A)",
          {"1": "VIN", "2": "VIN_RAW"}, "input", lcsc="C64886")
    n.add("D1", "Device:D_TVS", "Diode_SMD:D_SMF", tvs, tvs + " (200 W)", {"1": "VIN", "2": GND}, "input",
          lcsc=tvs_lcsc)
    n.add("D3", "Device:D_Schottky", "Diode_SMD:D_SOD-323", "B5819WS", "B5819WS (40 V 1 A)",
          {"1": "BUCK_SW", "2": GND}, "buck", lcsc="C64886")
