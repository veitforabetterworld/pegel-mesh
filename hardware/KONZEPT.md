# Pegel-Sender-Platine – Konzept (freigegeben, 3 A Ladestrom)

Trägerplatine für XIAO nRF52840 + Wio-SX1262: Solar-Laden, LiFePO4-Akku, Versorgung, 12-V-Sondenversorgung
(schaltbar) und RS485 zur Pegelsonde. SMD-Bestückung durch PCBWay, IP65-Gehäuse ca. 115 × 90 mm.

## Anforderungen (aus der Abstimmung)

| Thema | Festlegung |
|---|---|
| Solar | Panel 10–20 W, Leerlauf bis 25 V |
| Akku | LiFePO4 1S, 3× 32700 parallel (~18 Ah), Halter neben der Platine, Anschluss per Klemme |
| Frost | Laden erst ab 0 °C; darunter heizt die Platine aus Solarstrom (ca. 5 W), Gehäuse wärmeisoliert |
| XIAO-Stapel | Stiftleisten 2,54 mm auf der Unterseite → 2× 7-pol. Buchsenleiste auf der Trägerplatine |
| Sonde | 12–24 V, < 50 mA, RS485 (Modbus RTU), Adern: rot V+, schwarz V−, weiß 485A, blau 485B |
| Strom sparen | Sonde nur zur Messung eingeschaltet (MOSFET, Steuerung D0) |
| Telemetrie | Akkuspannung, Lade- und Verbrauchsstrom per I²C-Messchip |
| USB | Flashen im eingebauten Zustand bei angeschlossenem Akku muss sicher sein |
| Bestückung | SMD durch PCBWay, XIAO-Stapel steckbar, 5 Platinen |

## Blockschaltbild

```
Solar ─┬─ TVS ─ Verpolschutz ─► CN3795 MPPT-Lader (CV 3,61 V, 3 A) ─► Shunt (INA226) ─► 1S-Schutz ─► Akku 3× 32700
       │                                                                            │
       │                           ┌────────────────────────────────────────────────┤ VBAT 2,5–3,6 V
       │                           ▼                                                ▼
       │             TPS63900 Buck-Boost 3,3 V ─► XIAO 3V3          TPS61040 Boost 12 V ─► P-MOSFET ─► Sonde V+
       │                                                             (EN + MOSFET über D0)
       │  XIAO D6 = SCL, D7 = SDA ─┬─ INA226 (Akku V/I)
       │                           └─ SC16IS740 I²C→UART ─► MAX3485 (DE/RE über RTS) ─► SM712 TVS ─► Sonde A/B
```

## Pinbelegung XIAO

| Pin | Funktion |
|---|---|
| D1–D5, D8–D10 | Wio-SX1262 (unverändert) |
| D6 / D7 | I²C SCL / SDA (MeshCore-Standard), 4,7 kΩ Pull-ups |
| D0 | Sondenversorgung ein (HIGH) |
| 3V3 | Einspeisung 3,3 V vom Buck-Boost |
| BAT | **frei** – der Li-Ion-Lader des XIAO darf die LiFePO4-Zellen nie sehen |
| 5V | frei (USB) |

USB beim Flashen: Der XIAO-eigene Regler speist dann ebenfalls 3V3. Beide liefern 3,3 V, keiner kann zurückspeisen
(Buck-Boost mit Rückstromsperre im Abschaltfall prüfen, sonst Schottky/ideale Diode vorsehen).

## Bauteile (Vorauswahl, LCSC-Nummern werden beim Zeichnen festgelegt)

| Funktion | Bauteil | Begründung |
|---|---|---|
| Solar-Lader | CN3795 (SSOP-10), AOD4189 (P-MOSFET −40 V), B540C (40 V 5 A), 15 µH SRP1245A | 6,6–30 V Eingang, MPPT, CV per Teiler auf 3,60 V |
| Solar-Eingangsschutz | SMBJ26A TVS, Schottky gegen Verpolung | Leerlauf 25 V, Spitzen begrenzen |
| Akku-Schutz 1S | HY2112-Variante für LiFePO4 + Dual-N-MOSFET (z. B. FS8205A) | Über-/Tiefentladung, Kurzschluss – Schwellen noch prüfen |
| Temperatur | NTC 100 k (B 3950) auf der Platine (optional zweiter NTC an den Zellen per Lötbrücke), Komparator mit Hysterese | < 0 °C Laden sperren, < +2 °C Heizung ein (nur wenn Solarspannung anliegt) |
| Heizung | 6× 390 Ω 2512 parallel (65 Ω), SI2318CDS, aus dem Solareingang | ~5 W bei 18 V, Wärme über Kupferflächen; zieht nie aus dem Akku |
| 3,3 V | TPS63900 Buck-Boost | 1,8–5,5 V Eingang, 75 nA Ruhestrom, Ausgang per CFG1 = 36,5 kΩ auf 3,3 V |
| 12 V | TPS61040 Boost + AO3401 (P-MOSFET) + 2N7002 | EN und Lastschalter über D0; ohne Lastschalter läge VBAT an der Sonde |
| Akku-Messung | INA226 + 10 mΩ Shunt | Spannung, Lade-/Entladestrom, I²C |
| UART | SC16IS740IPW + Quarz 14,7456 MHz | I²C→UART, RTS steuert die RS485-Richtung |
| RS485 | MAX3485 (SOIC-8), SM712, 120 Ω per Lötbrücke, Fail-safe-Widerstände | 3,3 V, Leitungsschutz für lange Kabel draußen |
| Anschlüsse | Schraubklemmen 5,08 mm: Solar 2-pol., Akku 2-pol., Sonde 4-pol. | IP65-Gehäuse mit Kabelverschraubungen |
| XIAO | 2× 7-pol. Buchsenleiste | steckbar, Abstand nach Mechanik des Stapels |

## Auslegung

**CN3795** ([Datenblatt](https://mikrocontroller.net/attachment/576999/CN3795.pdf)): VCC max. 33 V, CSP/BAT max. 25 V.
- Ladeschlussspannung: V_REG = 1,205 V × (1 + R1/R2); R1 = 200 kΩ, R2 = 100 kΩ → 3,61 V.
  Vorladen unter 66,5 % (2,4 V) mit 17,5 % des Stroms; Überspannungsabschaltung bei +7 % (3,86 V).
- Ladestrom: I = 120 mV / R_CS; 40 mΩ (2512) → 3 A. Spule 15 µH, Sättigung > 6 A.
- MPPT: Pin regelt auf 1,205 V; Teiler 300 kΩ / 21,5 kΩ → Panel-Arbeitspunkt ≈ 18,0 V (typisches „12-V“-Panel).
- Kein Enable-Pin: Frostsperre zieht den MPPT-Pin per N-MOSFET auf GND → Lader regelt auf null.
- Schläft, wenn die Panelspannung unter die Akkuspannung fällt (nachts kein Rückstrom).

**Akku-Schutz HY2112-CB** ([Datenblatt](https://static.chipdip.ru/lib/671/DOC012671370.pdf)): Überladung 3,75 V (frei ab 3,60 V),
Tiefentladung 2,10 V (frei ab 2,30 V), Überstrom 200 mV über den Schutz-MOSFETs → mit FS8205A (~25 mΩ) ca. 4 A.

**Frost/Heizung:** Nanopower-Doppelkomparator (z. B. TLV3402/LPV7215) am Akku, NTC 10 k (B 3950) im Teiler:
- Komparator A: < 0 °C → MPPT-Pin auf GND (Laden aus), Hysterese ~1 K.
- Komparator B: < +2 °C → Heizung ein (aus dem Solareingang, nur wenn Panelspannung anliegt), Hysterese ~2 K.

**12 V für die Sonde:** TPS61040, V_OUT = 1,233 V × (1 + R1/R2), R1 = 820 kΩ, R2 = 91 kΩ → 12,3 V.
D0 HIGH: EN ein und 2N7002 zieht das Gate des AO3401 auf GND → Sonde an. D0 LOW: Boost aus, Gate über 100 kΩ
auf Source → Sonde stromlos (ohne Lastschalter läge sonst V_BAT − 0,3 V an der Sonde).

**3,3 V:** TPS63900, 75 nA Ruhestrom, 1,8–5,5 V Eingang, deckt LiFePO4 (2,1–3,65 V) ab; CFG1 36,5 kΩ, CFG2/CFG3 an GND, 2,2 µH.

**Ruhestrom-Budget (Ziel < 100 µA ohne Funk):** TPS63900 < 1 µA, HY2112 ~4 µA, Komparator ~2 µA, INA226 (Power-down)
~2 µA, SC16IS740 (Sleep) ~30 µA, MAX3485 (Shutdown über RTS/Software) ~1 µA, Teiler ~15 µA; dazu XIAO + SX1262 im Schlaf.

## Offene Punkte

1. ~~Mechanik XIAO-Stapel~~ – geklärt: Stiftleisten 2,54 mm auf der Unterseite.
2. ~~Schutzchip~~ – HY2112-CB passt (3,75 V / 2,10 V).
3. ~~Frost~~ – Komparator + Platinenheizung aus Solarstrom.
4. ~~Ladestrom~~ – 3 A (18 Ah in ~6 h volle Sonne).
5. MPPT-Arbeitspunkt 18 V passt zu üblichen „12-V“-Panels (Vmp 17–19 V); bei anderem Panel Teiler anpassen.

## Firmware-Änderungen

- RS485 über SC16IS740 (I²C) statt `Serial1`, Senderichtung automatisch über RTS.
- Sonde über D0 einschalten, Aufwärmzeit abwarten, messen, ausschalten.
- INA226 auslesen; Akkuspannung als Statuspaket mitfunken (stündlich).

## Platine (hardware/pegel-sender)

Generiert aus Python, `design.py` ist die einzige Quelle für Bauteile, Werte, Herstellernummern und Netze.

| Schritt | Aufruf (mit dem Python von KiCad 10) |
|---|---|
| Platzierung, Netze, Netzklassen | `gen_pcb.py` → `pegel-sender.kicad_pcb` (100 × 70 mm, 2 Lagen, 4× M3) |
| Routing + Kupferflächen | `route.py <freerouting.jar> [java.exe]` |
| Fertigungsdaten | `export.py` → `fab/` (Gerber-ZIP, BOM, CPL mit Nullpunkt unten links) |

- XIAO-Buchsenleisten mit 15,24 mm Reihenabstand, USB zur rechten Platinenkante. **Vor der Bestellung am Stapel nachmessen.**
- Klemmen mit Kabeleinführung zur Platinenkante: Solar und Akku links, Sonde rechts (1 V+, 2 V−, 3 A, 4 B).
- Netzklassen: 3-A-Pfade 0,8 mm plus Kupferflächen, 3,3 V/12 V/Schaltknoten 0,5 mm, Rest 0,3 mm.
- SC16IS740: RTS ist active-low; die Firmware setzt in EFCR RTSCON und RTSINVER, damit DE beim Senden HIGH ist.
