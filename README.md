# pegel-mesh

Wasserstände von entfernten Pegeln per Funk ins Netz — ohne Mobilfunk und ohne Leitung an der Messstelle.

## Was das ist

Pegelsonde am Fluss, kleiner Sender daneben, Empfänger irgendwo mit WLAN. Der Sender liest den Pegel (RS485), funkt über [MeshCore](https://github.com/meshcore-dev/MeshCore) im 868-MHz-Band zum Empfänger; der schickt die Werte an die **hochwasserdienst**-API.

Mehrere Pegel können auf denselben Empfänger laufen. Zwei Sendermodi: Messung alle **60 s** (`pegel_sender_a`) oder alle **5 min** (`pegel_sender_b`).

Der Sender findet den Empfänger über eine geflutete Anfrage im Mesh und hält die Route per periodischer Direktanfrage aktuell. Pakete gehen als MeshCore-`RAW_CUSTOM`-Direktnachricht.

## Funk und Messwerte

Jedes Telegramm ist **13 Byte**: Pegel in mm (16 Bit), untere 16 Bit eines laufenden Zählers, Alter der Messung in Sekunden, plus 8 Byte HMAC (pro Sender eigener Schlüssel). Nicht verschlüsselt, aber fälschungssicher; der Empfänger erkennt den Sender am passenden Schlüssel. Zeitstempel für die API: Empfangszeit (UTC) minus `age_s`. Replay-Schutz über den 32-Bit-Zähler (nur 16 Bit im Funk). Implementierung: `firmware/common/pegel_packet.h`.

Statt eines Pegels kann ein Fehlercode kommen: 1 Sonde antwortet nicht, 2 Wert außerhalb des Bereichs, 3 RS485-Wandler tot (nur ältere Platine), 4 Akku fast leer (unter 2,8 V). Der Empfänger reicht den Code als `status` an die API durch. Die Akkuspannung selbst geht nicht über Funk.

## Geräte

| Rolle | Modul | PlatformIO-Umgebung |
|---|---|---|
| Sender, schnell | XIAO nRF52840 + Wio-SX1262 | `pegel_sender_a` |
| Sender, sparsam | XIAO nRF52840 + Wio-SX1262 | `pegel_sender_b` |
| Empfänger | XIAO ESP32-S3 + Wio-SX1262 | `pegel_receiver` |

**Prototyp ohne Platine:** RS485-Modul an `Serial1`, in `pegel.ini` `PEGEL_BOARD=0`.

**Mit Trägerplatine** (`PEGEL_BOARD=1`, Standard) — siehe [Sender aufbauen](#sender-aufbauen).

## Sender aufbauen

Der Sender besteht aus der Trägerplatine mit gestecktem XIAO, einem Solarpanel (oder Netzteil), LiFePO4-Akku, Pegelsonde und — für den Winter — Heizwiderstand und Temperaturfühler am Akku. Technik, Schaltpläne und Bilder der Platine: [`hardware/pegel-sender/`](hardware/pegel-sender/README.md) (Grafiken in [`preview/`](hardware/pegel-sender/preview/)).

### Was man braucht

| Teil | Anforderung | Beispiel |
|---|---|---|
| Solarpanel | „12-V-Panel“ (36 Zellen, Arbeitspunkt ~18 V), Leerlauf höchstens 25 V; Größe siehe [Auslegung](#panel-und-akku-auslegen) | 10 W im Flachland, 30 W im Mittelgebirge |
| *oder* Netzteil | 12 V Gleichspannung, mindestens 1 A, an dieselbe Klemme wie das Panel; Steckbrücke NETZTEIL setzen | Steckernetzteil 12 V / 1,5 A |
| Akku | LiFePO4, **1 Zelle** (3,2 V), mehrere Zellen parallel; Anzahl siehe Auslegung. Keine Li-Ion-Zellen (4,2 V)! | 32700-Zellen 6 Ah, 2–3 parallel |
| Sicherung | Kfz-Flachsicherung 5 A im Pluskabel des Akkus (die Platine hat keinen Kurzschlussschutz am Akku) | Mini-Flachsicherungshalter |
| Pegelsonde | RS485 Modbus RTU, 9600 Baud 8N1, Adresse 1, Pegel in cm im Holding-Register 4; Versorgung 12 V, höchstens 30 mA | Druck-Pegelsonde 4–20 mA/RS485, 12–24 V |
| Heizwiderstand | 68 Ω, 5 W, am bzw. um den Akku (nur bei Frost nötig) | Hochlastwiderstand 68 Ω 5 W |
| Temperaturfühler | NTC 10 kΩ, B ≈ 3950, mit Leitung, **auf den Akku** kleben | MF52A103J3950 |
| Gehäuse | IP65, innen ~115 × 90 mm für die Platine, besser gedämmt (z. B. 10–20 mm XPS) | |

Ohne Temperaturfühler gilt der Akku als zu kalt: der Sender lädt dann nie und heizt. Den NTC also immer anschließen, auch im Sommer.

### Anschlüsse und Jumper

| Klemme | Belegung |
|---|---|
| **SOLAR/12V** (links oben) | + / − des Panels **oder** des 12-V-Netzteils |
| **AKKU** (oben) | + / − der LiFePO4-Zelle(n), Sicherung im Pluskabel |
| **HEIZ/NTC** (links unten) | H+ / H−: Heizwiderstand; NTC / NTC: Temperaturfühler (beliebig gepolt) |
| **SONDE** (rechts) | V+ rot, V− schwarz, A weiß, B blau |

| Jumper | Bedeutung |
|---|---|
| **NETZTEIL** (Steckbrücke) | **gesteckt** bei 12-V-Netzteil, **offen** bei Solarpanel. Ohne Brücke lädt ein Netzteil nicht; mit Brücke am Panel lädt es, aber nicht im besten Arbeitspunkt |

XIAO mit Wio-SX1262 auf die beiden Buchsenleisten stecken (USB-Buchse zeigt nach rechts zum Platinenrand, „USB ->“). Den Akku-Anschluss (BAT) am XIAO nicht benutzen. Flashen per USB geht auch mit angeschlossenem Akku.

### Panel und Akku auslegen

Durch den Winter gerechnet (Oktober bis April, 18 Winter 2005–2023, stündliche Einstrahlung und Temperatur aus PVGIS), Panel 45° Süd, aber nur einen halben Tag in der Sonne, Akku gealtert auf 80 %. Den größten Teil des Verbrauchs macht der Funk, der dauernd empfängt; die Sonde und das Senden kommen dazu.

| Beispiel | Verbrauch | Panel | Akku (LiFePO4 6 Ah) | Tiefster Ladestand im schlechtesten Winter | Ohne jede Sonne |
|---|---|---|---|---|---|
| Flachland (Nürnberg, 320 m), Messung alle 15 min | 21 mW, 0,5 Wh/Tag | **10 W** | **2×** | 76 % (ungedämmt 75 %) | ~8 Wochen |
| Mittelgebirge (4 Orte um 600 m), Messung jede Minute | 38 mW, 0,9 Wh/Tag | **30 W** | **3×** | 77 % (ungedämmt 68 %) | ~7 Wochen |

Untergrenze ohne Reserve für Schnee auf dem Panel: im Flachland 10 W mit 1× 6 Ah (Ladestand fällt bis 55 %), im Mittelgebirge 20 W mit 2× 6 Ah (bis 53 %). 5 W mit 1× 6 Ah reichen auch im Flachland nicht sicher: bei kaltem Akku nimmt die Heizung (~4 W) den ganzen Strom eines 5-W-Panels. Mehr als 30 W bringt wenig, der Lader lädt mit höchstens 2 A.

Für den Winter: Gehäuse dämmen (halbiert die Heizenergie), Panel eher steil (≥ 60°) montieren, damit Schnee abrutscht. Rechnung: [`verify/winter_energy.py`](hardware/pegel-sender/verify/winter_energy.py).

### Verhalten

- **Laden** mit bis zu 2 A bis 3,50 V; bei Frost gesperrt (Sperre unter ~1,2 °C am Akku, frei ab ~2,7 °C).
- **Heizung** an unter ~3,8 °C, aus über ~5,2 °C, nur bei Sonne oder Netzteil — nie aus dem Akku.
- **Sonde** ist nur während der Messung eingeschaltet.
- **Akku fast leer:** unter 2,8 V bleibt die Sonde aus und der Sender meldet Fehlercode 4; ab 3,0 V wieder Pegel. Unter 2,6 V schaltet er Funk und Sonde ab und wartet, bis die Sonne den Akku wieder über 3,0 V geladen hat.
- **Ohne Akku** läuft der Sender direkt aus Panel oder Netzteil, solange genug Licht da ist.

### Platine bestellen

Fertigungsdaten für JLCPCB in [`hardware/pegel-sender/fab/`](hardware/pegel-sender/fab/): `pegel-sender-gerber.zip`, `pegel-sender-bom.csv`, `pegel-sender-cpl.csv`. Bestellung als „Economic PCBA“, einseitig bestückt, z. B. 2 Platinen. Alle SMD-Teile sind Basic- oder Preferred-Teile ohne Rüstgebühr; 2 bestückte Platinen kosten etwa **25–40 €** inklusive Versand und Steuer.

Selbst löten (Liste: `fab/pegel-sender-handbestueckung.csv`):

| Teil | Wert | Beispiel |
|---|---|---|
| SOLAR/12V, AKKU | Schraubklemme 2-pol., Raster 5,08 mm | Phoenix MKDS 1,5/2-5,08 |
| SONDE, HEIZ/NTC | Schraubklemme 4-pol., Raster 5,08 mm | Phoenix MKDS 1,5/4-5,08 |
| L1 | Spule 15 µH, ≥ 2,4 A, radial Ø 8,7 mm, Raster 5 mm | Bourns RLB0914-150KL |
| L2 | Spule 10 µH, ≥ 0,5 A, radial Ø 8,7 mm, Raster 5 mm | Bourns RLB0912-100KL |
| XIAO | 2× Buchsenleiste 1×7, 2,54 mm | |
| NETZTEIL | Stiftleiste 1×2, 2,54 mm + Steckbrücke | |

## Installation

**Voraussetzungen:** Git, Python 3.12+, USB-Treiber für die XIAO-Boards.

```bash
git clone <repo-url> pegel-mesh
cd pegel-mesh
git submodule update --init

python3 -m pip install platformio cryptography
python3 tools/genkeys.py
```

`tools/genkeys.py` legt `secrets/` an (nicht versioniert): Mesh-/WLAN-Daten, API-Zugang für den Empfänger, HMAC-Schlüssel pro Sender. **Sicher aufbewahren** — bei Verlust alle Geräte neu flashen.

```bash
python3 tools/pio.py run -e pegel_sender_a -t upload --upload-port /dev/ttyACM0
python3 tools/pio.py device monitor -b 115200 -p /dev/ttyACM0
```

Port anpassen (`COM5` unter Windows). Weitere Umgebungen: `pegel_sender_b`, `pegel_receiver`. Immer `tools/pio.py` nutzen — hängt `pegel.ini` in das MeshCore-Submodul ein.
