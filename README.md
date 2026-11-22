# pegel-mesh

Wasserstände von entfernten Pegeln per Funk ins Netz, ohne Mobilfunk. Ein Sender am Fluss liest die Pegelsonde (RS485) und funkt über [MeshCore](https://github.com/meshcore-dev/MeshCore) (868 MHz) zu einem Empfänger mit WLAN, der die Werte an die **hochwasserdienst**-API schickt. Der Sender läuft mit Solarpanel und Akku.

![Trägerplatine](hardware/pegel-sender-12v/preview/pegel-sender-12v-top.png)

Zwei Trägerplatinen, eine Firmware (gleiche XIAO-Pins; die Firmware erkennt den Akku selbst):

| Platine | Akku | Versorgung |
|---|---|---|
| [`pegel-sender-12v`](hardware/pegel-sender-12v/README.md) (100 × 70 mm) | LiFePO4 oder ohne | Solarpanel 12-V-Klasse oder 12-V-Netzteil |
| [`pegel-sender-5v`](hardware/pegel-sender-5v/README.md) (58 × 46 mm) | Li-Ionen oder ohne | USB-C-Netzteil oder USB-C-Solarpanel (5 V), Heizung 1,7 W |
| [`pegel-stapel`](hardware/pegel-stapel/README.md) (Stapel) | wie oben | RS485-Platine auf Ladeplatine 5 V (beide 21 × 17,8 mm, wie der XIAO) oder 12 V (100 × 70 mm); Thermolader für 12-V-Netzteil und 12-V-Solar im Entwurf, noch unverdrahtet |

## Platine (12 V)

Die SMD-Teile bestückt JLCPCB (Dateien in [`hardware/pegel-sender-12v/fab/`](hardware/pegel-sender-12v/fab/)). Selbst löten:

| Teil | Wert | Beispiel |
|---|---|---|
| SOLAR/12V, AKKU | Schraubklemme 2-pol., Raster 5,08 mm | Phoenix MKDS 1,5/2-5,08 |
| SONDE, HEIZ/NTC | Schraubklemme 4-pol., Raster 5,08 mm | Phoenix MKDS 1,5/4-5,08 |
| L1 | Spule 15 µH, ≥ 0,9 A, radial Ø 7 mm, Raster 3 mm | Bourns RLB0712-150KL |
| L2 | Spule 10 µH, ≥ 0,5 A, radial Ø 7 mm, Raster 3 mm | Bourns RLB0712-100KL |
| C22 | Elko 220 µF 16 V, Polymer oder Low-ESR, Ø 8 mm, Raster 3,5 mm | Panasonic 16SEPF220M |
| C23 | Elko 220 µF 50 V, Low-ESR, Ø 10 mm, Raster 5 mm | Panasonic EEU-FR1H221 |
| XIAO | 2× Buchsenleiste 1×7, 2,54 mm | |
| NETZTEIL | Stiftleiste 1×2, 2,54 mm + Steckbrücke | |

Elkos: Plus an das Pad mit „+“.

Schaltplan: [`hardware/pegel-sender-12v/preview/`](hardware/pegel-sender-12v/preview/) (Blockschaltbild und ein Blatt je Funktionsblock), Technik in [`hardware/pegel-sender-12v/`](hardware/pegel-sender-12v/README.md).

## Anschlüsse

| Klemme | Was |
|---|---|
| **SOLAR/12V** | 12-V-Solarpanel (Leerlauf ≤ 25 V; 10 W Flachland, 30 W Mittelgebirge) **oder** 12-V-Netzteil |
| **AKKU** | LiFePO4, **1 Zelle** (3,2 V), z. B. 2–3 × 6 Ah parallel. Rückstellende Sicherung **RUEF300** (Littelfuse PolySwitch, hält 3 A, löst bei 6 A aus) im Pluskabel, direkt am Akku-Pluspol |
| **HEIZ/NTC** | H+ / H−: Heizwiderstand 68 Ω 10 W; NTC / NTC: Fühler 10 kΩ B3950, **auf den Akku** kleben |
| **SONDE** | V+ rot, V− schwarz, A weiß, B blau. RS485 Modbus RTU, 9600 8N1, Adresse 1, 12 V ≤ 30 mA |
| **NETZTEIL** (Brücke) | gesteckt bei Netzteil, offen bei Solarpanel |

Ohne NTC lädt der Sender nie (gilt als Frost). XIAO nRF52840 mit Wio-SX1262 aufstecken, USB zum Platinenrand („USB ->“); den BAT-Anschluss am XIAO nicht benutzen.

## Installation

Voraussetzungen: Git, Python 3.12+, USB-Treiber für die XIAO-Boards.

```bash
git clone https://github.com/veitforabetterworld/pegel-mesh.git
```

```bash
cd pegel-mesh && git submodule update --init
```

```bash
python3 -m pip install platformio cryptography
```

```bash
python3 tools/genkeys.py
```

`genkeys.py` legt `secrets/` an (nicht im Repo, sicher aufbewahren). Dort von Hand ausfüllen: **`secrets/receiver_wifi.h`** mit WLAN, API-Key (hochwasserdienst: Admin > API-Keys) und Name/Koordinaten der Stationen. Weitere Sender: `python3 tools/genkeys.py A B C`.

Flashen (Port anpassen, unter Windows z. B. `COM5`):

```bash
python3 tools/pio.py run -e pegel_sender_a -t upload --upload-port /dev/ttyACM0
```

| Umgebung | Gerät |
|---|---|
| `pegel_sender_a` | Sender, Messung jede Minute |
| `pegel_sender_b` | Sender, Messung alle 5 min |
| `pegel_receiver` | Empfänger, XIAO ESP32-S3 + Wio-SX1262 |

Immer `tools/pio.py` statt `pio` aufrufen; es hängt `pegel.ini` in das MeshCore-Submodul ein.

## Funkausfall und Nachsenden

Der Sender hält jede Messung, bis der Empfänger sie quittiert: 6144 Messungen, bei Sender A gut 4 Tage, bei Sender B gut 3 Wochen. Ist der Puffer voll, fällt die älteste Messung heraus; nach 30 Tagen verfällt eine Messung ebenfalls. Bei gestörter Verbindung stehen die Messungen zusätzlich im Flash und überstehen Stromausfall und Neustart; die Uhrzeit dafür kommt mit jeder Quittung vom Empfänger.

- Im Messtakt geht immer ein Block mit den neuesten Messungen raus (bis 75 je Paket). Bleibt die Quittung aus, versucht es der Sender erst im nächsten Messtakt wieder.
- Kam die Quittung, folgt der restliche Stau Block für Block, neueste zuerst, solange das Sendebudget von 1 % je Stunde reicht (MeshCore setzt es durch). Ein Tag Ausfall von Sender A ist so in knapp einer Stunde nachgeholt.
- Daten und Quittungen laufen nur auf dem bekannten Pfad oder ohne Hops, nie geflutet.

Fängt der Zähler eines Senders neu an (Tausch, Neuaufsetzen), übernimmt der Empfänger den neuen Stand nach etwa 30 Blöcken; sofort geht es am Empfänger über USB-Serial mit `creset <Sender>`, z. B. `creset A`.

## Langzeitbetrieb

Die Firmware ist für den Betrieb über viele Jahrzehnte ausgelegt (Watchdog, Überlauf- und Verschleißschutz). Der Empfänger nimmt die Uhrzeit vom Server. Zwischen den Messungen schlafen Funkchip und CPU. Bei gestörter Verbindung schreibt der Sender jede Messung mit Uhrzeit in den Flash: nach einem Stromausfall sendet er sie mit dem richtigen Zeitstempel nach.

Notfallwege testen: Builds `pegel_sender_a_test` und `pegel_receiver_test` (Serial-Befehle in `firmware/sender/main.cpp` bzw. `firmware/receiver/main.cpp`, `PEGEL_TEST_CMDS`).

## GPS-Tracker

Der Empfänger ist zugleich Gateway für GPS-Tracker: XIAO nRF54LM20A Sense + Wio-SX1262 + L76K-GNSS-Modul (Seeed 109100021). Der Tracker schläft zwischen den Ortungen in System OFF, meldet Position und Akkustand verschlüsselt über MeshCore, speichert nicht quittierte Meldungen zwischen und reicht sie nach. Bei eingeschaltetem Bewegungsalarm weckt ihn der Bewegungssensor. Der Empfänger lädt die Meldungen zu [tracker.plenivo.de](https://tracker.plenivo.de) hoch und gibt dem Tracker dessen Einstellungen (Intervall, Alarm) mit. Firmware in [`firmware/tracker/`](firmware/tracker/), Paketformat in [`firmware/common/tracker_packet.h`](firmware/common/tracker_packet.h).

Schlüssel für einen neuen Tracker (hier `T1`), danach den Empfänger neu flashen:

```bash
python3 tools/genkeys.py --tracker T1
```

In `secrets/receiver_wifi.h` `TRACKER_API_URL` (`https://tracker.plenivo.de/api`) und je Tracker den API-Key aus dem Tracker-Dialog der Webseite eintragen. Ohne URL gibt der Empfänger die Meldungen nur auf Serial aus; Einstellungen lassen sich dann mit `tset <tracker> <intervall 0..3> <alarm 0..3> <alarmintervall 0..3>` auf Serial setzen.

Der nRF54LM20A wird von MeshCore noch nicht offiziell unterstützt; der Tracker baut gegen das Submodul `MeshCore-nrf54` (MeshCore-PR #3530). `tools/pio.py` wählt es für alle Umgebungen `tracker_*` und hängt `tracker.ini` ein.

```bash
python3 tools/pio.py run -e tracker_t1 -t upload
```

Ein neues Board ist ab Werk gesperrt (APPROTECT): einmal mit OpenOCD über den CTRL-AP löschen und dann `-t bootloader` (Bootloader, SoftDevice, Firmware) flashen; danach reicht `-t upload`. Die USB-Seriell-Brücke des Boards bleibt nach System OFF oft hängen; das Log liegt deshalb zusätzlich im RAM und lässt sich per SWD lesen (weckt den Tracker dabei auf):

```bash
bash tools/tracker_log.sh
```
