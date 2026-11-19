# Bauteilbelastung und Funktion (SPICE)

Größte Auslastung je Bauteil über alle Betriebsfälle. ⚠ ab 80 %, ✗ über der Grenze.

| Bauteil | Größe | Wert | Grenze | Auslastung | Fall |
|---|---|---:|---:|---:|---|
| J6 | U XIAO_3V3 [V] | 3.38 | 3.6 | 94 % ⚠ | Panel offen −25 °C, Akku voll |
| J5 | U UART_TX [V] | 3.38 | 3.68 | 92 % ⚠ | Panel offen −25 °C, Akku voll |
| U6 | U UART_RX [V] | 3.18 | 3.48 | 91 % ⚠ | Sonne 20 °C, ohne Akku |
| J6 | U UART_RX [V] | 3.18 | 3.48 | 91 % ⚠ | Sonne 20 °C, ohne Akku |
| J5 | U SENS_EN [V] | 3.18 | 3.48 | 91 % ⚠ | Sonne 20 °C, ohne Akku |
| U6 | U RS_DE [V] | 3.06 | 3.36 | 91 % ⚠ | Sonde 30 mA, Senden |
| D1 | U Sperr [V] (≤ Vwm) | 25.4 | 28 | 91 % ⚠ | Panel offen −25 °C, Akku voll |
| U3 | U VSOL [V] | 25 | 30 | 83 % ⚠ | Panel offen −25 °C, Akku voll |
| U3 | U +5V [V] | 5 | 6 | 83 % ⚠ | Ohne NTC, Sonne 20 °C (gilt als Frost) |
| L1 | I Spitze [A] (Isat) | 0.735 | 0.9 | 82 % ⚠ | Schwaches Licht 10 % (Arbeitspunkt) |
| D8 | U Sperr [V] (≤ Vwm) | 12.4 | 18 | 69 %  | Sonne 20 °C, ohne Akku |
| U1 | U VSOL [V] | 25 | 40 | 63 %  | Panel offen −25 °C, Akku voll |
| L1 | I eff [A] | 0.548 | 0.9 | 61 %  | Schwaches Licht 10 % (Arbeitspunkt) |
| L1 | I DC [A] | 0.535 | 0.9 | 59 %  | Schwaches Licht 10 % (Arbeitspunkt) |
| C8 | U [V] | 3.6 | 6.3 | 57 %  | Panel offen −25 °C, Akku voll |
| U6 | U RS_VCC [V] | 3.18 | 6 | 53 %  | Sonne 20 °C, ohne Akku |
| Q5 | Ugs [V] | -6.22 | 12 | 52 %  | Sonne 20 °C, ohne Akku |
| U5 | U VSYS [V] | 3.6 | 7 | 51 %  | Panel offen −25 °C, Akku voll |
| C1 | U [V] | 25 | 50 | 50 %  | Panel offen −25 °C, Akku voll |
| C2 | U [V] | 25 | 50 | 50 %  | Panel offen −25 °C, Akku voll |
| C3 | U [V] | 25 | 50 | 50 %  | Panel offen −25 °C, Akku voll |
| C23 | U [V] | 25 | 50 | 50 %  | Panel offen −25 °C, Akku voll |
| C16 | U [V] | 12.4 | 25 | 50 %  | Sonne 20 °C, ohne Akku |
| Q4 | Ugs [V] | 9.91 | 20 | 50 %  | Panel offen −25 °C, Akku voll |
| U5 | U SW [V] | 12.8 | 28 | 46 %  | Sonne 20 °C, ohne Akku |
| U5 | U SENS_EN [V] | 3.18 | 7 | 45 %  | Sonne 20 °C, ohne Akku |
| L2 | I Spitze [A] (Isat) | 0.475 | 1.1 | 43 %  | Nacht −20 °C, Messung 30 mA + Funk |
| U1 | U CHG_FB [V] | 2.44 | 6 | 41 %  | Panel offen −25 °C, Akku voll |
| Q2 | Ugs [V] | 8.01 | 20 | 40 %  | Panel offen −25 °C, Akku voll |
| Q4 | Uds [V] | 23 | 60 | 38 %  | Sonne +7 °C (Laden frei, Heizung aus) |
| C17 | U [V] | 3.6 | 10 | 36 %  | Panel offen −25 °C, Akku voll |
| C19 | U [V] | 3.38 | 10 | 34 %  | Panel offen −25 °C, Akku voll |
| D7 | U Sperr [V] | 12.4 | 40 | 31 %  | Sonne 20 °C, ohne Akku |
| R23 | U [V] | 23 | 75 | 31 %  | Sonne +7 °C (Laden frei, Heizung aus) |
| Q1 | Ugs [V] | -3.6 | 12 | 30 %  | Panel offen −25 °C, Akku voll |
| R12 | U [V] | 21.6 | 75 | 29 %  | Panel offen −25 °C, Akku voll |
| Q7 | Ugs [V] | -3.18 | 12 | 27 %  | Sonne 20 °C, ohne Akku |
| U6 | U RS485_B [V] | 3.05 | 12 | 25 %  | Sonde 30 mA, Senden |
| D9 | U Pin 2 [V] | 3.05 | 12 | 25 %  | Sonde 30 mA, Senden |
| D7 | I Spitze [A] | 0.475 | 2 | 24 %  | Nacht −20 °C, Messung 30 mA + Funk |
| R5 | U [V] | 17 | 75 | 23 %  | Panel offen −25 °C, Akku voll |
| C22 | U [V] | 3.6 | 16 | 22 %  | Panel offen −25 °C, Akku voll |
| U6 | U RS485_A [V] | 2.47 | 12 | 21 %  | Sonne 20 °C, ohne Akku |
| D9 | U Pin 1 [V] | 2.47 | 12 | 21 %  | Sonne 20 °C, ohne Akku |
| D3 | P [W] | 0.19 | 1 | 19 %  | Schwaches Licht 10 % (Arbeitspunkt) |
| U1 | I Schalter Spitze [A] (Strombegrenzung min. 4 A) | 0.735 | 4 | 18 %  | Schwaches Licht 10 % (Arbeitspunkt) |
| Q3 | Ugs [V] | 3.55 | 20 | 18 %  | Sonne +7 °C (Laden frei, Heizung aus) |
| U5 | U BST_FB [V] | 1.23 | 7 | 18 %  | Akku 2,9 V, Sonde 30 mA + Funk |
| Q8 | Ugs [V] | 3.38 | 20 | 17 %  | Panel offen −25 °C, Akku voll |
| Q3 | Uds [V] | 9.91 | 60 | 17 %  | Panel offen −25 °C, Akku voll |
| Q6 | Ugs [V] | 3.18 | 20 | 16 %  | Sonne 20 °C, ohne Akku |
| U2 | U +5V [V] | 5 | 32 | 16 %  | Ohne NTC, Sonne 20 °C (gilt als Frost) |
| R24 | U [V] | 11.2 | 75 | 15 %  | Sonne 20 °C, ohne Akku |
| C6 | U [V] | 3.6 | 25 | 14 %  | Panel offen −25 °C, Akku voll |
| C7 | U [V] | 3.6 | 25 | 14 %  | Panel offen −25 °C, Akku voll |
| D3 | I Mittel [A] | 0.422 | 3 | 14 %  | Schwaches Licht 10 % (Arbeitspunkt) |
| Q1 | Id [A] | 0.535 | 4 | 13 %  | Schwaches Licht 10 % (Arbeitspunkt) |
| D2 | I [A] | 0.376 | 3 | 13 %  | Panel offen −25 °C, Akku voll |
| Q4 | Id [A] | 0.368 | 3 | 12 %  | Panel offen −25 °C, Akku voll |
| D10 | I [A] | 0.121 | 1 | 12 %  | Sonne 20 °C, ohne Akku |
| D2 | P [W] | 0.121 | 1 | 12 %  | Panel offen −25 °C, Akku voll |
| U5 | U BST_SW [V] | 3.6 | 30 | 12 %  | Panel offen −25 °C, Akku voll |
| Q5 | Uds [V] | -3.55 | 30 | 12 %  | Panel offen −25 °C, Akku voll |
| Q7 | Uds [V] | -3.38 | 30 | 11 %  | Panel offen −25 °C, Akku voll |
| R14 | U [V] | 8.44 | 75 | 11 %  | Netzteil 12 V mit Steckbrücke, Akku 30 % |
| R15 | P [W] | 0.028 | 0.25 | 11 %  | Schwaches Licht 10 % (Arbeitspunkt) |
| Q1 | Uds [V] | -3.3 | 30 | 11 %  | Nacht −20 °C, Ruhe |
| U2 | U VIN_DIV [V] | 3.49 | 32 | 11 %  | Panel offen −25 °C, Akku voll |
| R6 | U [V] | 8.01 | 75 | 11 %  | Panel offen −25 °C, Akku voll |
| U1 | U CHG_SW [V] | 3.6 | 40 | 9 %  | Panel offen −25 °C, Akku voll |
| D3 | U Sperr [V] | 3.6 | 40 | 9 %  | Panel offen −25 °C, Akku voll |
| R27 | U [V] | 6.22 | 75 | 8 %  | Sonne 20 °C, ohne Akku |
| R28 | U [V] | 6.22 | 75 | 8 %  | Sonne 20 °C, ohne Akku |
| U2 | U T_NTC [V] | 2.52 | 32 | 8 %  | Ohne NTC, Sonne 20 °C (gilt als Frost) |
| U2 | U VREF [V] | 2.5 | 32 | 8 %  | Ohne NTC, Sonne 20 °C (gilt als Frost) |
| D10 | P [W] | 0.0378 | 0.5 | 8 %  | Sonne 20 °C, ohne Akku |
| U4 | U VREF [V] | 2.5 | 36 | 7 %  | Ohne NTC, Sonne 20 °C (gilt als Frost) |
| R7 | P [W] | 0.00626 | 0.1 | 6 %  | Sonne +45 °C, Akku leer |
| D7 | I Mittel [A] | 0.03 | 0.5 | 6 %  | Nacht −20 °C, Messung 30 mA + Funk |
| Q6 | Uds [V] | 3.44 | 60 | 6 %  | Panel offen −25 °C, Akku voll |
| Q2 | Uds [V] | 3.3 | 60 | 5 %  | Nacht 20 °C, Ruhe |
| R23 | P [W] | 0.00529 | 0.1 | 5 %  | Sonne +7 °C (Laden frei, Heizung aus) |
| Q8 | Uds [V] | 3.06 | 60 | 5 %  | Sonde 30 mA, Senden |
| R4 | U [V] | -3.6 | 75 | 5 %  | Panel offen −25 °C, Akku voll |
| R35 | U [V] | 3.53 | 75 | 5 %  | Panel offen −25 °C, Akku voll |
| R13 | U [V] | 3.49 | 75 | 5 %  | Panel offen −25 °C, Akku voll |
| U2 | U T_REF0 [V] | 1.37 | 32 | 4 %  | Sonne +7 °C (Laden frei, Heizung aus) |
| R29 | U [V] | 3.18 | 75 | 4 %  | Sonne 20 °C, ohne Akku |
| R30 | U [V] | 3.18 | 75 | 4 %  | Sonne 20 °C, ohne Akku |
| R26 | U [V] | 3.18 | 75 | 4 %  | Sonne 20 °C, ohne Akku |
| D5 | U Sperr [V] | 3.09 | 75 | 4 %  | Netzteil 12 V ohne Steckbrücke (lädt nicht) |
| R33 | U [V] | 3.05 | 75 | 4 %  | Sonde 30 mA, Senden |
| R32 | U [V] | -3.05 | 75 | 4 %  | Sonde 30 mA, Senden |
| U2 | U T_REF2 [V] | 1.25 | 32 | 4 %  | Sonne +7 °C (Laden frei, Heizung aus) |
| C1–C3 | Rippelstrom je C [A] | 0.0778 | 2 | 4 %  | Netzteil 12 V mit Steckbrücke, Akku 30 % |
| R7 | U [V] | 2.5 | 75 | 3 %  | Sonne +45 °C, Akku leer |
| R8 | U [V] | 2.45 | 75 | 3 %  | Ohne NTC, Sonne 20 °C (gilt als Frost) |
| R2 | U [V] | 2.44 | 75 | 3 %  | Panel offen −25 °C, Akku voll |
| R22 | U [V] | 2.3 | 75 | 3 %  | Sonne +45 °C, Akku leer |
| R1 | U [V] | 2.28 | 75 | 3 %  | Sonne 20 °C, ohne Akku |
| R5 | P [W] | 0.0029 | 0.1 | 3 %  | Panel offen −25 °C, Akku voll |
| R17 | U [V] | 2.15 | 75 | 3 %  | Sonne +45 °C, Akku leer |
| R21 | U [V] | 2.15 | 75 | 3 %  | Sonne +0,5 °C (unter Ladeschwelle: Sperre, Heizung) |
| R20 | U [V] | 1.25 | 75 | 2 %  | Sonne +7 °C (Laden frei, Heizung aus) |
| R25 | U [V] | 1.23 | 75 | 2 %  | Akku 2,9 V, Sonde 30 mA + Funk |
| R18 | U [V] | 1.16 | 75 | 2 %  | Ohne NTC, Sonne 20 °C (gilt als Frost) |
| R12 | P [W] | 0.00155 | 0.1 | 2 %  | Panel offen −25 °C, Akku voll |
| R6 | P [W] | 0.00136 | 0.1 | 1 %  | Panel offen −25 °C, Akku voll |
| R30 | P [W] | 0.00101 | 0.1 | 1 %  | Sonne 20 °C, ohne Akku |
| R33 | P [W] | 0.000931 | 0.1 | 1 %  | Sonde 30 mA, Senden |
| R32 | P [W] | 0.000929 | 0.1 | 1 %  | Sonde 30 mA, Senden |
| R3 | U [V] | 0.645 | 75 | 1 %  | Netzteil 12 V ohne Steckbrücke (lädt nicht) |
| Q5 | Id [A] | -0.0301 | 4 | 1 %  | Sonne 20 °C, ohne Akku |
| Q1 | P [W] | 0.00978 | 1.4 | 1 %  | Schwaches Licht 10 % (Arbeitspunkt) |
| R27 | P [W] | 0.000387 | 0.1 | 0 %  | Sonne 20 °C, ohne Akku |
| R28 | P [W] | 0.000387 | 0.1 | 0 %  | Sonne 20 °C, ohne Akku |
| D6 | P [W] | 0.0015 | 0.41 | 0 %  | Panel offen −25 °C, Akku voll |
| Q8 | Id [A] | 0.000318 | 0.115 | 0 %  | Sonne 20 °C, ohne Akku |
| R24 | P [W] | 0.000247 | 0.1 | 0 %  | Sonne 20 °C, ohne Akku |
| R13 | P [W] | 0.000238 | 0.1 | 0 %  | Panel offen −25 °C, Akku voll |
| R14 | P [W] | 0.000237 | 0.1 | 0 %  | Netzteil 12 V mit Steckbrücke, Akku 30 % |
| Q4 | P [W] | 0.00279 | 1.2 | 0 %  | Panel offen −25 °C, Akku voll |
| Q3 | Id [A] | 0.00023 | 0.115 | 0 %  | Sonne +7 °C (Laden frei, Heizung aus) |
| R2 | P [W] | 0.000199 | 0.1 | 0 %  | Panel offen −25 °C, Akku voll |
| R17 | P [W] | 0.000171 | 0.1 | 0 %  | Sonne +45 °C, Akku leer |
| R19 | U [V] | 0.126 | 75 | 0 %  | Ohne NTC, Sonne 20 °C (gilt als Frost) |
| U2 | U CC_SENSE [V] | 0.0529 | 32 | 0 %  | Schwaches Licht 10 % (Arbeitspunkt) |
| U2 | U CC_INT [V] | 0.0528 | 32 | 0 %  | Schwaches Licht 10 % (Arbeitspunkt) |
| R4 | P [W] | 0.00013 | 0.1 | 0 %  | Panel offen −25 °C, Akku voll |
| R8 | P [W] | 0.00012 | 0.1 | 0 %  | Ohne NTC, Sonne 20 °C (gilt als Frost) |
| R29 | P [W] | 0.000101 | 0.1 | 0 %  | Sonne 20 °C, ohne Akku |
| R26 | P [W] | 0.000101 | 0.1 | 0 %  | Sonne 20 °C, ohne Akku |
| R1 | P [W] | 9.28e-05 | 0.1 | 0 %  | Sonne 20 °C, ohne Akku |
| Q6 | Id [A] | 9.4e-05 | 0.115 | 0 %  | Sonne 20 °C, ohne Akku |
| R9 | U [V] | 0.0494 | 75 | 0 %  | Schwaches Licht 10 % (Arbeitspunkt) |
| D5 | I [A] | 6.42e-05 | 0.15 | 0 %  | Ohne NTC, Sonne 20 °C (gilt als Frost) |
| R3 | P [W] | 4.16e-05 | 0.1 | 0 %  | Netzteil 12 V ohne Steckbrücke (lädt nicht) |
| Q7 | Id [A] | -0.00139 | 4 | 0 %  | Sonne 20 °C, ohne Akku |
| R20 | P [W] | 3.13e-05 | 0.1 | 0 %  | Sonne +7 °C (Laden frei, Heizung aus) |
| Q2 | Id [A] | 3.6e-05 | 0.115 | 0 %  | Panel offen −25 °C, Akku voll |
| R18 | P [W] | 2.88e-05 | 0.1 | 0 %  | Ohne NTC, Sonne 20 °C (gilt als Frost) |
| R25 | P [W] | 2.71e-05 | 0.1 | 0 %  | Akku 2,9 V, Sonde 30 mA + Funk |
| R15 | U [V] | 0.0529 | 200 | 0 %  | Schwaches Licht 10 % (Arbeitspunkt) |
| D5 | P [W] | 3.2e-05 | 0.2 | 0 %  | Ohne NTC, Sonne 20 °C (gilt als Frost) |
| R35 | P [W] | 1.25e-05 | 0.1 | 0 %  | Panel offen −25 °C, Akku voll |
| R21 | P [W] | 4.6e-06 | 0.1 | 0 %  | Sonne +0,5 °C (unter Ladeschwelle: Sperre, Heizung) |
| R10 | U [V] | -0.0034 | 75 | 0 %  | Schwaches Licht 10 % (Arbeitspunkt) |
| R19 | P [W] | 3.13e-06 | 0.1 | 0 %  | Ohne NTC, Sonne 20 °C (gilt als Frost) |
| D7 | P [W] | 1.44e-05 | 0.5 | 0 %  | Akku 2,9 V, Sonde 30 mA + Funk |
| R22 | P [W] | 2.64e-06 | 0.1 | 0 %  | Sonne +45 °C, Akku leer |
| R9 | P [W] | 2.44e-06 | 0.1 | 0 %  | Schwaches Licht 10 % (Arbeitspunkt) |
| D7 | I [A] | 6.85e-06 | 0.5 | 0 %  | Panel offen −25 °C, Akku voll |
| Q5 | P [W] | 1.42e-05 | 1.4 | 0 %  | Akku 2,9 V, Sonde 30 mA + Funk |
| L2 | I DC [A] | 6.88e-06 | 1.1 | 0 %  | Panel offen −25 °C, Akku voll |
| Q8 | P [W] | 3.23e-07 | 0.2 | 0 %  | Sonde 30 mA, Empfang |
| Q3 | P [W] | 1.28e-07 | 0.2 | 0 %  | Sonne +7 °C (Laden frei, Heizung aus) |
| R31 | U [V] | 3.06e-05 | 75 | 0 %  | Sonde 30 mA, Senden |
| Q6 | P [W] | 4.71e-08 | 0.2 | 0 %  | Akku 2,9 V, Sonde 30 mA + Funk |
| Q7 | P [W] | 7.92e-08 | 1.4 | 0 %  | Akku 2,9 V, Sonde 30 mA + Funk |
| Q2 | P [W] | 4.41e-09 | 0.2 | 0 %  | Nacht 20 °C, Ruhe |
| R10 | P [W] | 1.16e-09 | 0.1 | 0 %  | Schwaches Licht 10 % (Arbeitspunkt) |
| D2 | U Sperr [V] | 4.93e-08 | 40 | 0 %  | Nacht −20 °C, Messung 30 mA + Funk |
| R11 | U [V] | 5.29e-09 | 75 | 0 %  | Schwaches Licht 10 % (Arbeitspunkt) |
| R31 | P [W] | 9.37e-15 | 0.1 | 0 %  | Sonde 30 mA, Senden |
| R11 | P [W] | 2.8e-20 | 0.1 | 0 %  | Schwaches Licht 10 % (Arbeitspunkt) |
| D3 | I [A] | 0 | 3 | 0 %  | Nacht 20 °C, Ruhe |
| D10 | U Sperr [V] | 0 | 40 | 0 %  | Nacht 20 °C, Ruhe |
| U1 | U CHG_BOOT–CHG_SW [V] | -9.11e-11 | -0.3 | -0 %  | Akku 2,9 V, Sonde 30 mA + Funk |

## Funktion

| Fall | Größe | Wert | Soll | |
|---|---|---:|---|---|
| Nacht 20 °C, Ruhe | XIAO_3V3 | 3.08 | 2.9 … 3.3 | ✓ |
| Nacht 20 °C, Ruhe | VSOL | 2.21e-05 | -0.1 … 1 | ✓ |
| Nacht 20 °C, Ruhe | Iheat | 7.82e-13 | -0.001 … 0.001 | ✓ |
| Nacht 20 °C, Ruhe | Ibat | -0.00601 | -0.012 … 0 | ✓ |
| Nacht −20 °C, Ruhe | VSOL | 2.19e-05 | -0.1 … 1 | ✓ |
| Nacht −20 °C, Ruhe | Iheat | 7.72e-13 | -0.001 … 0.001 | ✓ |
| Nacht −20 °C, Ruhe | Ibat | -0.00601 | -0.012 … 0 | ✓ |
| Nacht −20 °C, Messung 30 mA + Funk | V12_PROBE | 12.4 | 11.8 … 12.8 | ✓ |
| Nacht −20 °C, Messung 30 mA + Funk | XIAO_3V3 | 2.96 | 2.8 … 3.3 | ✓ |
| Nacht −20 °C, Messung 30 mA + Funk | Iheat | 8.43e-13 | -0.001 … 0.001 | ✓ |
| Sonne 20 °C, Akku 30 % (Konstantstrom) | Ichg | 0.492 | 0.45 … 0.55 | ✓ |
| Sonne 20 °C, Akku 30 % (Konstantstrom) | Iheat | 5.44e-09 | -0.001 … 0.001 | ✓ |
| Sonne 20 °C, Akku 30 % (Konstantstrom) | VSOL | 22 | 16 … 23 | ✓ |
| Sonne 20 °C, Akku fast voll (Konstantspannung) | VSYS | 3.46 | 3.45 … 3.56 | ✓ |
| Sonne 20 °C, Akku fast voll (Konstantspannung) | Ichg | 0.492 | 0 … 0.55 | ✓ |
| Sonne 20 °C, ohne Akku | VSYS | 3.49 | 3.4 … 3.56 | ✓ |
| Sonne 20 °C, ohne Akku | V12_PROBE | 12.4 | 11.8 … 12.8 | ✓ |
| Sonne −10 °C (Frost: Ladesperre, Heizung) | Ichg | -0.00607 | -0.02 … 0.02 | ✓ |
| Sonne −10 °C (Frost: Ladesperre, Heizung) | Iheat | 0.351 | 0.15 … 0.4 | ✓ |
| Sonne +0,5 °C (unter Ladeschwelle: Sperre, Heizung) | Ichg | -0.00607 | -0.02 … 0.02 | ✓ |
| Sonne +0,5 °C (unter Ladeschwelle: Sperre, Heizung) | Iheat | 0.339 | 0.15 … 0.4 | ✓ |
| Sonne +7 °C (Laden frei, Heizung aus) | Ichg | 0.492 | 0.3 … 0.55 | ✓ |
| Sonne +7 °C (Laden frei, Heizung aus) | Iheat | 5.65e-09 | -0.001 … 0.001 | ✓ |
| Sonne +45 °C, Akku leer | Ichg | 0.492 | 0.3 … 0.55 | ✓ |
| Sonne +45 °C, Akku leer | Iheat | 5.05e-09 | -0.001 … 0.001 | ✓ |
| Ohne NTC, Sonne 20 °C (gilt als Frost) | Ichg | -0.00607 | -0.02 … 0.02 | ✓ |
| Ohne NTC, Sonne 20 °C (gilt als Frost) | Iheat | 0.318 | 0.15 … 0.4 | ✓ |
| 5-W-Panel +10 °C (Strombegrenzung) | VSOL | 22.5 | 16.5 … 23 | ✓ |
| 5-W-Panel +10 °C (Strombegrenzung) | Ichg | 0.492 | 0.45 … 0.55 | ✓ |
| Schwaches Licht 10 % (Arbeitspunkt) | VSOL | 17.5 | 16.5 … 18 | ✓ |
| Schwaches Licht 10 % (Arbeitspunkt) | Ichg | 0.529 | 0.05 … 1 | ✓ |
| Panel offen −25 °C, Akku voll | VSOL | 25 | 0 … 27 | ✓ |
| Netzteil 12 V mit Steckbrücke, Akku 30 % | Ichg | 0.492 | 0.45 … 0.55 | ✓ |
| Netzteil 12 V ohne Steckbrücke (lädt nicht) | Ichg | -0.00607 | -0.02 … 0.1 | ✓ |
| Netzteil 12 V mit Steckbrücke, −10 °C | Ichg | -0.00607 | -0.02 … 0.02 | ✓ |
| Netzteil 12 V mit Steckbrücke, −10 °C | Iheat | 0.164 | 0.1 … 0.25 | ✓ |
| Akku 2,9 V, Sonde 30 mA + Funk | V12_PROBE | 12.4 | 11.8 … 12.8 | ✓ |
| Akku 2,9 V, Sonde 30 mA + Funk | XIAO_3V3 | 2.56 | 2.5 … 3 | ✓ |
| Sonde 30 mA, Senden | V12_PROBE | 12.4 | 11.8 … 12.8 | ✓ |
| Sonde 30 mA, Empfang | V12_PROBE | 12.4 | 11.8 … 12.8 | ✓ |
| Sonde 30 mA, Empfang | UART_RX | 3.06 | 2.9 … 3.6 | ✓ |
