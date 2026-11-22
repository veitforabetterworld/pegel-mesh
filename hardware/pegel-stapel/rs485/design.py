"""RS485-Platine (Stapel, Mitte) im Umriss des XIAO: 12 V für die Pegelsonde und RS485.

Alles hängt an den XIAO-Leisten, gespeist aus dem 3V3-Pin. Auslegung: Sonde 13 mA bei 12 V (gemessen), das sind
~61 mA aus 3,3 V und nur während der Messung. Ein Schalter (Q7) speist Wandler und SP3485 gemeinsam; ist er aus,
kommt nichts an die Sonde.

Der Regler des XIAO (SGM2040) garantiert 280 mA und empfiehlt höchstens 10 µF am Ausgang. Deshalb kein Puffer am
3V3-Pin, sondern zwei Rampen: C9/C11 lassen V3_SW langsam steigen, C10/D7/R19 die 12 V (~65 ms). So bleibt 3V3 auch
mit bis zu 100 µF in der Sonde über 3,1 V (gerechnet, ungünstigste Grenzen).

Außen: J3 Sonde (A, B, GND, 12 V) als durchkontaktierte Lötstellen im 2,54-mm-Raster. Stapel: J5/J6 als Stapel-Buchsenleisten (lange Stifte nach
unten in die Ladeplatine, XIAO oben drauf). Umriss wie der XIAO, keine Bohrungen. Damit das ohne
überlappende Höfe passt: unkritische R und C in 0402, Q6/Q8 in SOT-323, D7 in SOD-523.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from parts import GND, R0402, SOT23, SOT323, Netlist  # noqa: E402
from stack import j5_pins, j6_pins  # noqa: E402

N = Netlist()
r, c, add, nmos, pmos = N.r, N.c, N.add, N.nmos, N.pmos
WIRE4 = "pegel:WirePads_1x04_P2.54mm_D1.0mm"
L3015 = "pegel:L_3015_HandSolder"

# --- Schalter: Q7 an, solange D0 high. Ein Schalter für Wandler und SP3485 ---------------------------
g = "switch"
pmos("Q7", "PSW_G", "V3_SW", "XIAO_3V3", g)
r("R14", "100k", "XIAO_3V3", "PSW_G", R0402, g)
c("C9", "220nF 0402", "PSW_G", "V3_SW", g)          # Gate-Drain: V3_SW steigt mit ~1 V/ms
c("C11", "1uF 25V 0402", "XIAO_3V3", "PSW_G", g)      # Gate-Source: bleibt beim Einstecken des XIAO aus
NFET = dict(value="BSS138W", lcsc="C28646265", fp=SOT323)      # Ugs(th) max. 1,5 V: schaltet auch bei 2,8 V
nmos("Q6", "SENS_EN", "PSW_PD", GND, g, **NFET)
r("R11", "10k", "SENS_EN", GND, R0402, g)      # beim Start des XIAO aus
r("R13", "10k", "PSW_G", "PSW_PD", R0402, g)

# --- 12 V ------------------------------------------------------------------------------------------
# EN an VIN: EN darf laut Datenblatt höchstens 0,3 V über VIN liegen.
g = "12v"
add("U2", "Regulator_Switching:TPS61040DBV", "Package_TO_SOT_SMD:SOT-23-5", "TPS61040", "TI TPS61040DBVR",
    {"1": "BST_SW", "2": GND, "3": "BST_FB", "4": "V3_SW", "5": "V3_SW"}, g, lcsc="C7722")
add("L1", "Device:L", L3015, "10uH", "Sunlord SWPA3015S100MT (10 µH, Isat 0,9 A, LCSC C45403)",
    {"1": "V3_SW", "2": "BST_SW"}, g, hand=True)      # Leistungsspulen gibt es nur als Extended
add("D4", "Device:D_Schottky", "Diode_SMD:D_SOD-323", "1N5819WS", "1N5819WS (40 V 1 A)",
    {"1": "V12_PROBE", "2": "BST_SW"}, g, lcsc="C191023")
c("C5", "10uF 10V", "V3_SW", GND, g)
c("C4", "10uF 25V 0603", "V12_PROBE", GND, g)     # ~2 µF bei 12 V, reicht für 13 mA
r("R9", "510k", "V12_PROBE", "BST_FB", R0402, g)
r("R10", "56k", "BST_FB", GND, R0402, g)         # 1,233 V · (1 + 510k/56k) = 12,46 V
c("C3", "22pF 0402", "V12_PROBE", "BST_FB", g)
# Sanftanlauf: solange die 12 V steigen, hebt C10 über D7 den FB-Pin; R19 entlädt C10
c("C10", "1uF 25V 0402", "V12_PROBE", "SS", g)      # bei 12 V noch ~0,17 µF wirksam
add("D7", "Device:D", "Diode_SMD:D_SOD-523", "1N4148WT", "1N4148WT",
    {"1": "BST_FB", "2": "SS"}, g, lcsc="C7420320")
r("R19", "100k", "SS", GND, R0402, g)
add("D5", "Device:D_TVS", "Diode_SMD:D_SOD-123F", "SMF15A", "SMF15A (15 V, 200 W, klemmt bei 24,4 V)",
    {"1": "V12_PROBE", "2": GND}, g, lcsc="C19077509")

# --- RS485: Richtung über TX (Q8). Eine 1 hält nur die Vorspannung R17/R18 --------------------------
g = "rs485"
add("U3", "Interface_UART:SP3485EN", "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", "SP3485EN", "MaxLinear SP3485EN-L/TR",
    {"1": "UART_RX", "2": "RS_DE", "3": "RS_DE", "4": GND, "5": GND, "6": "RS485_A", "7": "RS485_B", "8": "V3_SW"},
    g, lcsc="C8963")
c("C6", "100nF 0402", "V3_SW", GND, g)
nmos("Q8", "UART_TX", "RS_DE", GND, g, **NFET)
r("R15", "10k", "V3_SW", "RS_DE", R0402, g)
r("R16", "10k", "V3_SW", "UART_RX", R0402, g)
# R17/R18 bleiben 0603: bei 12 V auf A/B bis 0,14 W
r("R17", "1k", "V3_SW", "RS485_A", group=g)       # 1k: ~180 m Kabel bei 9600 Bd (10k: ~23 m)
r("R18", "1k", GND, "RS485_B", group=g)
add("D6", "Diode:SM712_SOT23", SOT23, "PSM712", "ProTek PSM712-LF-T7", {"1": "RS485_A", "2": "RS485_B", "3": GND},
    g, lcsc="C32677")
add("J3", "Connector_Generic:Conn_01x04", WIRE4, "SONDE", "Lötstellen durchkontaktiert, 2,54 mm: A, B, GND, 12 V",
    {"1": "RS485_A", "2": "RS485_B", "3": GND, "4": "V12_PROBE"}, g, hand=True)

# --- Stapel: XIAO oben, Ladeplatine unten ------------------------------------------------------------
N.stack(j5_pins(d0="SENS_EN", d6="UART_TX"), j6_pins(v33="XIAO_3V3", d7="UART_RX"), top=True)
PARTS = N.parts
nets = N.nets

if __name__ == "__main__":
    N.report()
