# Prüfung der Trägerplatine (Simulation, Belastung, Leiterbahnen)

Alles läuft auf Windows mit dem ngspice aus KiCad (`ngspice.dll` über ctypes), Python 3.12 und KiCad-Python.

| Skript | Was | Bericht |
|---|---|---|
| `run_stress.py` | 19 Betriebsfälle (Tag/Nacht, Frost, Netzteil, Sondenspitze, Akku leer/voll), Funktion und Belastung jedes Bauteils gegen sein Datenblatt | `report/stress.md` |
| `sweeps.py` | Temperatur-, Netzteil- und Akkurampen (Hysterese in beide Richtungen), Einschalten der Sonde bei 30/80/200 mA | `report/sweeps.md` + Bilder |
| `longterm.py` | Mehrere Tage Winter und Sommer, quasistatisch alle 20 min, Ladezustand integriert | `report/longterm.md` + Bilder |
| `pcb_check.py` | Breitester Kupferweg jedes Hochstrompfads gegen IPC-2221 (KiCad-Python) | `report/pcb.md` |
| `../../../firmware/test` | Firmware gegen nachgebildeten SC16IS740, Modbus-Sonde und INA226 (g++) | Konsole |

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

Die Netzliste entsteht direkt aus `design.py`. Passive Bauteile, Dioden und MOSFETs sind echte SPICE-Modelle;
die ICs sind Verhaltensmodelle mit den Datenblattwerten (Lader CN3795 und Aufwärtswandler LM2735 gemittelt,
Schaltbelastung von Q1, D3, L1, C2–C4/C22, L3, U5, D5 analytisch aus Tastgrad und Rippel). Umgebung: Panel
(Isc 1,2 A, Voc 22 V bei 25 °C, kalt höher), Netzteil, LiFePO4 18 Ah mit OCV-Kennlinie, XIAO-Last, Sonde
30–80 mA, Spitze 200 mA bei 12 V.

## Ergebnis

Alle 19 Betriebsfälle erfüllen ihre Funktion, kein Bauteil liegt über seiner Grenze.

| Funktion | Simuliert |
|---|---|
| Laden Konstantstrom | 3,0 A (Sonne und Netzteil 12 V / 13,8 V), Konstantspannung 3,60 V |
| MPPT, 10-W-Panel | VSOL 18,4 V, 2,8 A in den Akku |
| Netzteil erkannt | ab DC_F 8,6 V, nicht mehr unter 4,8 V |
| Ladesperre (Frost) | an beim Abkühlen unter 1,15 °C, frei beim Erwärmen über 3,3 °C |
| Heizung aus Solar | an unter 3,55 °C, aus über 5,3 °C, 0,35–0,38 A; nachts 0 mA (kein Rückstrom aus dem Akku) |
| Akkuschutz HY2112-CB | Laden gesperrt über 3,75 V, wieder frei unter 3,60 V; Entladen aus unter 2,1 V, an über 2,3 V |
| 3,3 V | 3,30 V bis zur Abschaltung des Akkuschutzes |
| Sonde 12 V | 12,3 V bei 30/80 mA, 12,2 V bei 200 mA; bei 2,8 V Zelle und 200 mA zieht der Wandler 1,2 A aus dem Akku (L3 und U5 bei 43 % / 75 %) |
| Firmware | Pegel lesen, Fehlercodes ohne Antwort / außer Bereich / ohne Schnittstelle, INA226-Strom und -Spannung, Unterspannung mit Hysterese 2,8 / 3,0 V |

Knapp, aber innerhalb der Grenzen (≥ 80 %):

- **D1 (SMBJ26A am Panel) 97 % der Sperrspannung** bei −25 °C Leerlauf (25,3 V). Leckstrom steigt nahe Vwm, Durchbruch erst ab 28,9 V. Ein größerer TVS würde im Ernstfall über die 33 V des CN3795 klemmen.
- **Q9 83 %** (Uds −25 V von 30 V, Ugs −10 V von 12 V; D10 begrenzt).
- **D12 (SMAJ15A an der Sonde) 82 %** bei 12,3 V.
- Logikpegel 3,3 V an XIAO-Pins (85–92 % der Absolutgrenze, das ist Normalbetrieb).

Bei der Prüfung gefundene und behobene Fehler:

1. Nachts floss Akkustrom über die Bodydiode von Q1 nach VSOL und betrieb die Heizung (43 mA). Abhilfe: Z-Diode D14 (5,6 V) vor dem Heizungs-Gate, jetzt 0 mA.
2. Der MPPT-Komparator rastete bei schwacher Sonne auf den Netzteil-Arbeitspunkt (10 V) ein. Abhilfe: Erkennung an DC_F statt VSOL (R40/R41, R44 Hysterese).
3. Eingangsrippel 140 % von C2. Abhilfe: zusätzlich C4 (1210) und C22, Elko jetzt 60 %.
4. D8 sah ohne Netzteil Sperrstrom-Spannung über Vwm. Abhilfe: R41 zieht DC_F herunter.
5. Frostschwellen neu gelegt (R21–R26, R48), siehe oben.
6. Der 12-V-Wandler TPS61040 schaffte nur ~35 mA. Ersetzt durch LM2735 mit 4,7-µH-SRN6045TA: 200 mA auch bei 2,8 V Zelle.
7. Platine: L1→R1→R8 (3 A) lief über 0,3–0,6-mm-Bahnen, D3 hatte keine Via zur Massefläche, die Masse der Schutz-FETs hing an einer Insel. Abhilfe: feste 1,2-mm-Bahnen, Vias 0,6 mm, Sperrfläche für Signalbahnen unter den FETs. Alle Pfade jetzt über IPC-2221.

Grenzen der Simulation: Verhaltensmodelle bilden keine Regelschleifen-Stabilität, keine EMV und keine
Bauteiltoleranzen ab. Der Einschaltstrom der Sonde ist nur so groß wie ihr Modell (keine Eingangskapazität
bekannt). Die Langzeitsimulation rechnet in 20-min-Schritten, jeder Schritt startet ohne gespeicherte
Komparator-Hysterese.
