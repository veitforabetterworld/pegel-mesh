"""Lage der Anschlüsse, XIAO-Buchsen, Spule und Bohrungen (Anker, Drehung). Alles andere platziert gen_pcb.auto_place
in den Bereichen der Funktionsblöcke."""

FIXED = {
    # Anschlüsse am linken Rand, Pins übereinander: 5 V oben, Akku, Sonde
    "J1": (2.0, 3.0, 0), "J2": (2.0, 11.0, 0), "J3": (2.0, 19.0, 0),
    # BAT des XIAO (Drähte von der Unterseite des XIAO) unter dem XIAO, NTC daneben (Draht zum Akku)
    "J7": (52.5, 29.0, 0), "J4": (60.0, 29.0, 0),
    # XIAO + Wio-SX1262 rechts, USB zum rechten Rand (wie v1: Pin 1 von J5 = D0, von J6 = 5V am USB-Ende)
    "J5": (67.5, 6.0, -90), "J6": (67.5, 21.24, -90),
    "L1": (17.0, 18.5, 0),
    "H1": (65.5, 36.0, 0), "H2": (6.5, 36.0, 0),
}
