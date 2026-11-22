"""Bauteilliste der Stapelplatinen: gemeinsame Bauteile (JLCPCB Basic/Preferred) und Netzliste."""

from dataclasses import dataclass, field

import stack


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
R0402 = "Resistor_SMD:R_0402_1005Metric"
R0603 = "Resistor_SMD:R_0603_1608Metric"
R1206 = "Resistor_SMD:R_1206_3216Metric"
C0402 = "Capacitor_SMD:C_0402_1005Metric"
C0603 = "Capacitor_SMD:C_0603_1608Metric"
C0805 = "Capacitor_SMD:C_0805_2012Metric"
C1206 = "Capacitor_SMD:C_1206_3216Metric"
SOT23 = "Package_TO_SOT_SMD:SOT-23"
SOT323 = "Package_TO_SOT_SMD:SOT-323_SC-70"
SOD123 = "Diode_SMD:D_SOD-123"
HOLES2 = "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical"
HOLES4 = "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical"
L_RADIAL = "Inductor_THT:L_Radial_D7.0mm_P3.00mm"   # Bourns RLB0712: Ø 7 mm, Rastermaß 3 mm

# Basic-Widerstände (UNI-ROYAL, 1 %)
RES_LCSC = {
    ("1k", "0603"): "C21190", ("2.2k", "0603"): "C4190", ("4.7k", "0603"): "C23162", ("5.1k", "0603"): "C23186",
    ("10k", "0603"): "C25804", ("24k", "0603"): "C23352", ("27k", "0603"): "C22967", ("30k", "0603"): "C22984",
    ("47k", "0603"): "C25819", ("39k", "0603"): "C23153", ("49.9k", "0603"): "C23184", ("51k", "0603"): "C23196", ("56k", "0603"): "C23206",
    ("100k", "0603"): "C25803", ("300k", "0603"): "C23024", ("510k", "0603"): "C23192", ("1M", "0603"): "C22935",
    ("2M", "0603"): "C22976", ("0.1", "1206"): "C25334", ("10k", "0402"): "C25744",
    ("56k", "0402"): "C25796", ("100k", "0402"): "C25741", ("510k", "0402"): "C11616",
    ("510", "0402"): "C25123", ("3.3k", "0402"): "C25890", ("15k", "0402"): "C25756", ("51k", "0402"): "C25794",
    ("120", "1206"): "C17909", ("300", "1206"): "C17887",
}
# Basic-Kondensatoren: Wert -> (Footprint, Bezeichnung, LCSC)
CAP = {
    "22pF": (C0603, "CAP 22pF 50V C0G 0603", "C1653"),
    "100pF": (C0603, "CAP 100pF 50V C0G 0603", "C14858"),
    "10nF": (C0603, "CAP 10nF 50V X7R 0603", "C57112"),
    "100nF": (C0603, "CAP 100nF 50V X7R 0603", "C14663"),
    "47pF 0402": (C0402, "CAP 47pF 50V C0G 0402", "C1567"),
    "150pF 0402": (C0402, "CAP 150pF 50V X7R 0402", "C1527"),
    "2.2nF 0402": (C0402, "CAP 2.2nF 50V X7R 0402", "C1531"),
    "4.7nF 0402": (C0402, "CAP 4.7nF 50V X7R 0402", "C1538"),
    "10nF 0402": (C0402, "CAP 10nF 50V X7R 0402", "C15195"),
    "100nF 50V 0402": (C0402, "CAP 100nF 50V X7R 0402", "C307331"),
    "22pF 0402": (C0402, "CAP 22pF 50V C0G 0402", "C1555"),
    "100nF 0402": (C0402, "CAP 100nF 16V X7R 0402", "C1525"),
    "220nF 0402": (C0402, "CAP 220nF 16V X7R 0402", "C16772"),
    "1uF 25V 0402": (C0402, "CAP 1uF 25V X5R 0402", "C52923"),
    "1uF": (C0603, "CAP 1uF 50V X5R 0603", "C15849"),
    "10uF 10V": (C0603, "CAP 10uF 10V X5R 0603", "C19702"),
    "10uF 25V 0603": (C0603, "CAP 10uF 25V X5R 0603", "C96446"),
    "10uF 25V": (C0805, "CAP 10uF 25V X5R 0805", "C15850"),
    "22uF 25V": (C0805, "CAP 22uF 25V X5R 0805", "C45783"),
    "10uF 50V": (C1206, "CAP 10uF 50V X5R 1206", "C13585"),
    "100uF 6.3V": (C1206, "CAP 100uF 6.3V X5R 1206", "C15008"),
}


class Netlist:
    def __init__(self):
        self.parts: list[Part] = []

    def add(self, *args, **kwargs) -> Part:
        p = Part(*args, **kwargs)
        self.parts.append(p)
        return p

    def r(self, ref, value, a, b, fp=R0603, group=""):
        size = fp.split(":")[1].split("_")[1]
        return self.add(ref, "Device:R", fp, value, f"RES {value} 1% {size}", {"1": a, "2": b}, group,
                        lcsc=RES_LCSC[(value, size)])

    def c(self, ref, value, a, b, group=""):
        fp, mpn, lcsc = CAP[value]
        return self.add(ref, "Device:C", fp, value, mpn, {"1": a, "2": b}, group, lcsc=lcsc)

    def nmos(self, ref, g, d, s, group, value="2N7002", lcsc="C8545", fp=SOT23):
        return self.add(ref, "Device:Q_NMOS", fp, value, value, {"1": g, "2": s, "3": d}, group, lcsc=lcsc)

    def pmos(self, ref, g, d, s, group):
        return self.add(ref, "Device:Q_PMOS", SOT23, "AO3401A", "AOS AO3401A", {"1": g, "2": s, "3": d}, group,
                        lcsc="C15127")

    def stack(self, j5: dict, j6: dict, top: bool = False):
        """XIAO-Leisten (stack.py)."""
        kind = "Stapel-Buchsenleiste 1×7 mit langen Stiften" if top else "Buchsenleiste 1×7, 8,5 mm"
        self.add("J5", "Connector_Generic:Conn_01x07", stack.XIAO_ROW_FP, "XIAO D0-D6", kind, j5, "xiao",
                 hand=True)
        self.add("J6", "Connector_Generic:Conn_01x07", stack.XIAO_ROW_FP, "XIAO 5V-D7", kind, j6, "xiao",
                 hand=True)

    def nets(self) -> dict[str, list[tuple[str, str]]]:
        out: dict[str, list[tuple[str, str]]] = {}
        for p in self.parts:
            for pad, net in p.pins.items():
                if net:
                    out.setdefault(net, []).append((p.ref, pad))
        return out

    def report(self):
        n = self.nets()
        print(f"{len(self.parts)} parts, {len(n)} nets")
        for name, pads in sorted(n.items()):
            if len(pads) < 2:
                print("single-pad net:", name, pads)
