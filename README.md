# pegel-mesh

Pegelsensoren an entfernten Flussstellen funken über das öffentliche MeshCore-Netz
(EU 869,618 MHz, 62,5 kHz, SF8) an einen Empfänger mit WLAN, der die Messwerte
an die hochwasserdienst-API weitergibt.

| Gerät | Hardware | Firmware-Umgebung |
|---|---|---|
| Sender A (60 s) | XIAO nRF52840 + Wio-SX1262 | `pegel_sender_a` |
| Sender B (300 s) | XIAO nRF52840 + Wio-SX1262 | `pegel_sender_b` |
| Empfänger | XIAO ESP32S3 + Wio-SX1262 | `pegel_receiver` |

## Messpaket (13 Byte)

`level_mm u16 | counter_lo u16 | age_s u8 | HMAC-SHA256[0..8]`, Details in
[firmware/common/pegel_packet.h](firmware/common/pegel_packet.h).

- Nicht verschlüsselt, aber authentisiert: jeder Sender hat einen eigenen HMAC-Schlüssel.
- Kein absoluter Zeitstempel: der Empfänger setzt `Empfangszeit (UTC) - age_s`.
- Replay-Schutz über einen 32-Bit-Zähler, von dem nur die unteren 16 Bit übertragen werden.
- Versand als MeshCore-`RAW_CUSTOM`-Direktpaket. Den Pfad zum Empfänger lernt der Sender über
  eine geflutete REQ, stündlich prüft er ihn mit einer direkten REQ.

## Bauen und Flashen

```
git submodule update --init
py -3.12 -m pip install platformio cryptography
py -3.12 tools/genkeys.py                 # einmalig, schreibt secrets/ (nicht im Git)
py -3.12 tools/pio.py run -e pegel_sender_a -t upload --upload-port COMx
py -3.12 tools/pio.py device monitor -b 115200 -p COMx
```

`secrets/keys.json` enthält alle Schlüssel. Geht die Datei verloren, müssen alle Geräte
neu geflasht werden. Sicher aufbewahren!
