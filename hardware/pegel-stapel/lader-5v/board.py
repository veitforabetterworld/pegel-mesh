"""Thermolader 5 V, die 5-V-Ladeplatine im Umriss des XIAO nRF52840: Name und Größe für tools/fab.py.

Lagen, Bahnen und Beschriftung stehen nur in der .kicad_pcb: sie ist das Original, bearbeitet in KiCad.
Umriss aus Seeeds Footprint XIAO-nRF52840-DIP (OPL_Kicad_Library): Ecken R 1,905 mm, Pinreihen 15,24 mm auseinander,
Pin 7 liegt 2,794 mm vom hinteren, Pin 1 2,921 mm vom USB-seitigen Rand.
"""

NAME = "pegel-lader-5v"
W, H = 20.955, 17.78
ASSEMBLY_PLAN = True    # Nummern sitzen unter den Bauteilen: lesbar im Bestückungsplan (fab/)
