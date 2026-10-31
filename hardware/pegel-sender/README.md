# pegel-sender — Trägerplatine (Technik)

Träger für XIAO nRF52840 + Wio-SX1262: Laden aus Solar oder 12-V-Netzteil, LiFePO4 1S, 12 V für die Pegelsonde (nur bei Messung), RS485 zur Sonde, Frostschutz mit Heizung am Akku. Platine 100 × 70 mm, 2 Lagen, für IP65-Gehäuse ~115 × 90 mm. Auslegung und Anschluss für Anwender: [README im Repo-Root](../../README.md).

Bilder: [`preview/`](preview/) — Blockschaltplan (`pegel-sender-schematic-blocks.png`), 3D-Ansichten (`pegel-sender-top.png`, `pegel-sender-bottom.png`) und Schaltplan je Funktionsblock (`schematic-*.png`). Simulation und Prüfung: [`verify/`](verify/README.md).

## Schaltung

| Block | Bauteile | Funktion |
|---|---|---|
| Eingang | J1, D1 SMBJ28A, D2 SS54, C1–C4 | Solar oder Netzteil, Überspannung, Verpolung, kein Rückstrom ins Panel |
| Lader | U1 TPS5430, L1 15 µH, D3, Q1 AO3401A | Abwärtswandler, Konstantspannung 3,50 V über VSENSE (R1/R2); C22 (220 µF mit ESR, wie im TI-Referenzdesign) hält den Regelkreis auch ohne Akku stabil, C23 puffert das Panel; Q1 trennt nachts den Akku vom Wandler |
| Regelung | U2 LM324, U3 HT7550 (5 V), U4 CJ431 (2,5 V) | A: Ladestrom 2,0 A (100 mV an R15‖R16 im Minuspol), B: Panel-Arbeitspunkt 17 V bzw. 9,7 V mit JP2, C: Frost-Ladesperre, D: Heizung. A–C ziehen den Lader über D4/D5 und R3 an VSENSE zurück. Läuft nur, wenn VSOL anliegt |
| Frost | NTC an J4, R17–R22, Q3, Q4 HL2310A | Ladesperre unter ~1,2 °C (frei über ~2,7 °C), Heizung unter ~3,8 °C (aus über ~5,2 °C), Heizung nur aus VSOL |
| Sonde 12 V | U5 TPS61040, L2 10 µH, Q5/Q6 | 12,46 V, nur bei SENS_EN (D0); Q5 trennt die Sonde, solange der Wandler aus ist |
| RS485 | U6 SP3485, Q7, Q8 | versorgt nur bei eingeschalteter Sonde; DI fest auf GND, TX schaltet über Q8 den Treiber (TX low → Leitung „0“), R32/R33 halten im Leerlauf „1“ |
| XIAO | D10 B5819W, J5/J6 | XIAO direkt am Akku über D10 (3V3-Pin), D10 sperrt die 3,3 V aus USB |

| XIAO-Pin | Funktion |
|---|---|
| D1–D5, D8–D10 | Wio-SX1262 |
| D6 / D7 | `Serial1` TX / RX zum SP3485 |
| D0 | Sonde und RS485 ein (HIGH) |
| 3V3 | Versorgung aus dem Akku über D10; die Firmware misst VDD und rechnet 0,2 V für D10 dazu |

BAT am XIAO bleibt unbenutzt: der eingebaute Li-Ion-Lader darf die LiFePO4-Zellen nicht sehen.

Alle SMD-Teile stammen aus der JLCPCB-Basic- bzw. Preferred-Bibliothek (LCSC-Nummern in `design.py`), Spulen, Klemmen und Buchsen sind Durchsteckteile zum Selbstlöten.

## Platine und Schaltplan erzeugen

**Software:** [KiCad 10](https://www.kicad.org/download/), **Java (JRE)** für [Freerouting 2.5](https://github.com/freerouting/freerouting/releases) (`build/freerouting.jar`, nicht versionieren).

| Plattform | KiCad |
|---|---|
| Linux (Arch/Manjaro) | `pacman -S kicad kicad-library jre-openjdk` |
| Linux (ohne root) | KiCad-AppImage nach `build/kicad-appimage/` ([Download](https://www.kicad.org/download/linux/)); beim ersten Lauf extrahiert [`kicad_env.py`](kicad_env.py) `squashfs-root` |
| Windows | KiCad-Installer; `kicad_env.py` findet KiCad-Python und `kicad-cli.exe` unter `%LOCALAPPDATA%\Programs\KiCad` bzw. `Program Files\KiCad`. Schaltplan-PNGs: `py -m pip install pymupdf` (statt `rsvg-convert`) |

In diesem Verzeichnis:

1. `python3 design.py` — Netzliste prüfen
2. KiCad-Python: `gen_pcb.py`
3. `route.py build/freerouting.jar` — DRC: 0 offen, 0 Kurzschluss/Kreuzung/Abstandsfehler, 0 Siebdruck-Verstöße
4. `export.py` — Gerber, JLCPCB-BOM/CPL (nur SMD mit LCSC-Nummer) und Liste der Handbestückung nach `fab/`
5. `render_preview.py` — 3D-Bilder nach `preview/`
6. `schematic_blocks.py` — Blockschaltplan; `schematic.py` — Schaltplan je Funktionsblock, gegen die KiCad-Netzliste geprüft

**Platine neu erzeugen:** `python3 relayout.py` (Schritte 2–5). Bauteilpositionen stehen in `fixed_positions.py`; nach manueller Verschiebung in KiCad: KiCad-Python `dump_fixed.py` → `fixed_positions.py` aktualisieren, dann `relayout.py`. Bahnbreiten und Abstände je Netz: `NET_WIDTH`/`HV_NETS` in `gen_pcb.py`; rechte Winkel werden nach dem Routen zu 45°-Schrägen (`route.py`).

**Nur Siebdruck** auf gültiger Platine: KiCad-Python `gen_pcb.layout_silk(board)` speichern, dann `render_preview.py`.

Schaltplan-Grafiken: [`schematic.py`](schematic.py) — Lage der Bauteile je Blatt in [`schematic_layout.py`](schematic_layout.py) (Signalfluss links → rechts, Versorgung oben, Masse unten), Leitungen verlegt ein rechtwinkliger Router; Labels nur für Netze, die das Blatt verlassen. Symbolzugriff in `sch_symbols.py`.

Vor der Bestellung den Abstand der XIAO-Buchsen am realen Stapel messen (Soll 15,24 mm Reihenabstand). In der JLCPCB-Vorschau die Drehung von U1 (TPS5430), U2 (LM324), U3 (HT7550) und den Dioden prüfen: KiCad und JLCPCB zählen Pin 1 nicht immer gleich.
