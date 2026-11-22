"""Stapel: Belegung der XIAO-Leisten, auf allen Platinen an derselben Stelle.

Unten eine Ladeplatine, darüber die RS485-Platine, oben XIAO + Wio-SX1262. Zwischen den Platinen laufen nur die
14 Pins der XIAO-Leisten, Stapelbohrungen gibt es nicht. RS485-Platine und Thermolader haben den Umriss des XIAO
(20,955 × 17,78 mm), die 12-V-Ladeplatine nur Gehäusebohrungen in den Ecken.

Draufsicht, USB rechts: obere Leiste J5 = D0 (Pin 1, rechts) … D6, untere Leiste J6 = 5V (Pin 1, rechts), GND,
3V3, D10, D9, D8, D7. Reihen 15,24 mm auseinander, beide mit Drehung −90°: Pin 1 rechts, die übrigen nach links.
"""

XIAO_ROW_FP = "Connector_PinSocket_2.54mm:PinSocket_1x07_P2.54mm_Vertical"


def j5_pins(d0="", d6=""):
    """J5: D0 … D6 (Pin 1 … 7). D1–D5 gehen nur an den Wio-SX1262 und bleiben hier offen."""
    return {"1": d0, "2": "", "3": "", "4": "", "5": "", "6": "", "7": d6}


def j6_pins(v5="", gnd="GND", v33="", d7=""):
    """J6: 5V, GND, 3V3, D10, D9, D8, D7 (Pin 1 … 7). D8–D10 nur Wio-SX1262."""
    return {"1": v5, "2": gnd, "3": v33, "4": "", "5": "", "6": "", "7": d7}
