# Prüfung der Trägerplatine (Simulation, Belastung, Leiterbahnen)

Alles läuft auf Windows mit dem ngspice aus KiCad (`ngspice.dll` über ctypes), Python 3.12 und KiCad-Python.

| Skript | Was | Bericht |
|---|---|---|
| `run_stress.py` | 20 Betriebsfälle (Tag/Nacht, Frost, ohne NTC, schwaches Licht, Netzteil mit/ohne Steckbrücke, ohne Akku, Sonde), Funktion und Belastung jedes Bauteils gegen sein Datenblatt | `report/stress.md` |
| `sweeps.py` | Temperatur- und Netzteilrampen (Hysterese in beide Richtungen), Einschalten der Sonde bei voller und fast leerer Zelle | `report/sweeps.md` + Bilder |
| `longterm.py` | Mehrere Tage Winter und Sommer, quasistatisch alle 20 min, Ladezustand integriert | `report/longterm.md` + Bilder |
| `winter_energy.py` | Panel- und Akkugröße über 18 Winter (PVGIS stündlich), Verschattung, Heizung, Ladesperre; Argumente `mittelgebirge`/`flachland` und Messabstand in s | Konsole |
| `pcb_check.py` | Breitester Kupferweg jedes Hochstrompfads gegen IPC-2221 (KiCad-Python) | `report/pcb.md` |
| `../../../firmware/test` | Firmware gegen nachgebildete Modbus-Sonde an `Serial1` und den SAADC an VDD (g++) | Konsole |

```bash
py -3.12 -X utf8 run_stress.py
```

```bash
py -3.12 -X utf8 sweeps.py
```

```bash
"C:/Users/<user>/AppData/Local/Programs/KiCad/10.0/bin/python.exe" -X utf8 pcb_check.py
```

## Modell

Die Netzliste entsteht direkt aus `design.py`. Passive Bauteile, Dioden und MOSFETs sind echte SPICE-Modelle; die ICs sind Verhaltensmodelle mit den Datenblattwerten: TPS5430 gemittelt im Spannungsmodus mit der internen Typ-III-Kompensation aus dem Datenblatt (Gl. 15: Integrator 2165 Hz, Nullstellen 2,17/2,59 kHz, Pole 24/54 kHz, Vorwärtsverstärkung 25; Einschaltschwelle 5,3 V, Tastgrad max. 87 %, Strombegrenzung 4 A, Überspannungsschutz 112,5 %), LM324 mit Verstärkung 1e4, 1 MHz Verstärkungs-Bandbreite und 0,4 V/µs Anstiegsrate, Ausgang bis VCC − 1,5 V, HT7550, CJ431, TPS61040 im Lückbetrieb (Spitzenstrom 0,4 A, 10 µH, max. 1 MHz), SP3485 mit Treiber und Empfänger. Schaltbelastung von U1, D3, L1, C1–C3, L2, D7 analytisch aus Tastgrad und Rippel. Umgebung: Panel (Isc 1,2 A, Voc 22 V bei 25 °C, kalt höher) oder Netzteil an J1, LiFePO4 18 Ah mit OCV-Kennlinie, NTC 10 kΩ B3950 und Heizwiderstand 68 Ω an J4, XIAO-Last, Sonde 30 mA bei 12 V.

## Ergebnis

Alle 20 Betriebsfälle erfüllen ihre Funktion, kein Bauteil liegt über seiner Grenze.

| Funktion | Simuliert |
|---|---|
| Laden | Konstantstrom 2,00 A (Shunt 100 mV), Konstantspannung 3,50 V; ohne Akku hält der Lader VSYS auf 3,49 V |
| Panel-Arbeitspunkt | 17,4 V bei 5-W-Panel und bei 10 % Licht (lädt dann 1,3 A bzw. 0,48 A); volle Sonne am 20-W-Panel: Strombegrenzung, Panel bei ~21 V |
| Netzteil 12 V | mit Steckbrücke JP2 Laden ab 10,4 V Netzteilspannung, 2 A; ohne Steckbrücke lädt es nicht |
| Ladesperre (Frost) | an beim Abkühlen unter 0,98 °C, frei beim Erwärmen über 3,1 °C; ohne NTC gesperrt |
| Heizung | an unter 3,6 °C, aus über 5,1 °C, 0,35 A aus dem Panel bzw. 0,16 A aus 12 V; nachts 0 A |
| Nacht | VSOL 0 V (Q1 sperrt den Rückweg über den Wandler), Akkustrom 6 mA (nur XIAO) |
| Sonde 12 V | 12,4 V bei 30 mA, auch bei 2,9-V-Zelle; Anstieg auf 90 % in 1,4–1,8 ms, Ugs Q5 −6,2 V |
| RS485 | Pegel an RO/TX/RX innerhalb der XIAO-Versorgung + 0,3 V (SP3485 aus XIAO_3V3 versorgt) |
| Firmware | Pegel lesen über `Serial1`, Fehlercodes ohne Antwort / außer Bereich, Akkuspannung aus VDD, Unterspannung 2,8 / 3,0 V, Abschaltung unter 2,6 V |

Knapp, aber innerhalb der Grenzen (≥ 80 %):

- D1 (SMBJ28A) 91 % der Sperrspannung bei −25 °C Panel-Leerlauf (25,4 V).
- U3 (HT7550) 84 % der Eingangsspannung (25,1 V von 30 V) im selben Fall.
- L1 84 % des Dauerstroms bei 2 A Ladestrom.
- Logikpegel am XIAO 91–94 % der Absolutgrenze (Normalbetrieb).

Bei der Auslegung gefundene und behobene Fehler:

1. Die Panelregelung mit Integrator (C13 100 nF) schwang bei schwachem Licht: der Lader zog die Eingangskondensatoren leer, das Panel fiel bis zur Abschaltschwelle (6 V), lud kurz und fiel wieder. Abhilfe: Proportionalregler mit Verstärkung 23 (R35 1 MΩ, C13 100 pF); das Panel bleibt bei 17,4 V.
2. Ein 120-Ω-Abschluss am RS485 drückte den Ruhepegel aus R32/R33 auf ~20 mV, die automatische Richtungsumschaltung hätte die „1“-Bits verloren. Abschluss gestrichen (bei 9600 Baud nicht nötig).
3. Der SP3485 an VSYS hob den RX-Pin des XIAO bis 0,3 V über dessen Versorgung (D10 dazwischen). Abhilfe: SP3485 über Q7 aus XIAO_3V3.
4. Platine: Schaltknoten und Masse von Shunt und Freilaufdiode hingen an zu schmalen Bahnen. Abhilfe: feste Masse-Vias an R15, R16, D3 (`GND_TIES` in `route.py`). Alle 18 Pfade jetzt über IPC-2221.
5. Mit dem echten Typ-III-Modell des TPS5430 (vorher PI-Regler) zeigte sich: mit nur Keramik am Ausgang hat sein Regelkreis ohne Akku ~10° Phasenreserve (mit Akku ~36°), und die Panelregelung pendelte bei 5–10 % Licht zwischen ~16 und 22 V. Abhilfe: C22 220 µF mit 20–100 mΩ ESR am Laderausgang wie im TI-Referenzdesign (Phasenreserve ~45–50° ohne, ~63° mit Akku) und C23 220 µF am Panel (Panelregelung bei 10 % Licht ruhig; bei 5 % lädt sie stoßweise, ohne Schaden). Das Kompensationsnetz aus dem TI-Beispiel für reine Keramik macht den Wandler zu langsam für die Panelregelung, die dann schon am 5-W-Panel schwingt; deshalb nicht verwendet.
6. R7 2,2 kΩ → 1 kΩ: der CJ431 braucht bis 1 mA (Datenblatt max.), vorher blieben im ungünstigsten Fall 0,87 mA.

Langzeit (quasistatisch, 20-min-Schritte, Start bei 30 %, Details in `report/longterm.md`):

| | Winter, 3 Tage (−12 … 0 °C) | Sommer, 2 Tage |
|---|---|---|
| Ladezustand | 30 % → 25,4 % (Ladesperre die ganze Zeit) | 30 % → 98,3 %, 12,6 Ah geladen |
| Heizung aus dem Panel | 98 Wh | 0 Wh |
| Akkustrom nachts | −11,5 mA (XIAO, Funk, Messung je Minute) | −11,3 mA |

Ohne Sonne reicht ein voller Akku (18 Ah) etwa 65 Tage. Das Modell erwärmt den Akku nicht durch die Heizung (NTC sieht die Lufttemperatur); in echt gibt die Ladesperre an sonnigen Wintertagen früher frei.

Grenzen der Simulation: gemittelte Modelle bilden keine Effekte im Schaltbetrieb (lückender Betrieb nur grob), keine EMV und keine Bauteiltoleranzen ab. Die Regelkreise sind mit der Datenblatt-Kompensation des TPS5430 gemittelt geprüft; beim ersten Aufbau Ladestrom und Panelspannung bei schwachem Licht mit dem Oszilloskop ansehen.
