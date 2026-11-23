# Erwärmung der 12-V-Thermolader

Erzeugt mit `thermal12.py` (Modell aus `thermal_model.py`, Aufbau wie in [`thermal.md`](thermal.md): 700-mAh-Pouchzelle, 30 mm Styropor, ruhige Luft). Rechnung, keine Messung. Rohdaten: `thermal-12v.json`.

**Annahmen, die vom 5-V-Lader abweichen**
- Geometrie aus `lader-12v-solar` (31,5 mm lang, noch ohne Leiterbahnen: nur Flächen und GND-Vias). Die Netzteil-Variante ist mit derselben Geometrie und ihren eigenen Verlusten gerechnet.
- Heizung aus V5: 4,92 V Solar, 4,88 V Netzteil, ~0,40 W, je Widerstand 0,08 W.
- Wandlerverlust, abgeschätzt aus den TI-Datenblättern: Solar (TPS5430 aus ~22 V) 0,16 W beim Heizen, 0,18 W beim Laden; Netzteil (TPS54331 aus 12 V) 0,07 / 0,08 W. Diese Verluste fallen nur an, solange Sonne bzw. Netzteil Strom liefern.

## Fehlerfall: NTC ab, Heizung dauernd an

Akku max. / Heizwiderstand max.:

| | −20 °C Luft | 20 °C Luft | 35 °C Luft | Akku 60 °C ab | Widerstand über Lastminderung ab |
|---|---|---|---|---|---|
| 5-V-Lader, 1206 (Vergleich) | 14 / 38 °C | 50 / 73 °C | 64 / 87 °C | ~31 °C Luft | – |
| Solar, 1206 | 24 / 45 °C | 59 / 80 °C | 72 / 93 °C | ~21 °C Luft | ~75 °C Luft |
| **Solar, 0805** | 24 / 50 °C | 59 / 84 °C | 72 / 97 °C | **~21 °C Luft** | **~38 °C Luft** |
| **Netzteil, 0805** | 17 / 42 °C | 53 / 77 °C | 67 / 90 °C | **~28 °C Luft** | ~47 °C Luft |

Lastminderung: 0805 0,125 W bis 70 °C, 0 W bei 155 °C. Bei 0,08 W darf er bis ~100 °C. Akkugrenze laut Datenblatt: 60 °C.

- **0805 statt 1206:** Der Widerstand wird ~4,5 K wärmer, am Akku ändert sich nichts. Beim Netzteil bleibt Reserve. Beim Solar-Lader liegt der Widerstand im Fehlerfall ab ~38 °C Außenluft über seiner Lastminderung.
- **Unabhängig vom Gehäuse:** Wegen der Wandlerverluste wird der Akku im Fehlerfall wärmer als am 5-V-Lader. Beim Solar-Lader erreicht er 60 °C schon ab ~21 °C Außenluft, beim Netzteil ab ~28 °C.

## Normalbetrieb (NTC am Akku, Thermostat)

| | Heizung reicht bis | bei 25 °C Luft lädt er | 30 °C | 35 °C | 40 °C |
|---|---|---|---|---|---|
| Solar | ~−35 °C Luft | 71 % der Zeit | 43 % | 21 % | 0 % |
| Netzteil | ~−28 °C Luft | 100 % | 71 % | 30 % | 0 % |

Die Wandlerverluste heizen im Winter mit. Beim Solar-Lader gilt das nur, solange die Sonne scheint. Ohne Abschaltung käme der Akku beim Laden bei 35 °C Luft auf 54 °C (Solar) bzw. 47 °C (Netzteil). Die Hitzeabschaltung hält ihn bei 42 °C.
