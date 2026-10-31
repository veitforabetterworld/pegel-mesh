# Bauteilbelastung und Funktion (SPICE)

Größte Auslastung je Bauteil über alle Betriebsfälle. ⚠ ab 80 %, ✗ über der Grenze.

| Bauteil | Größe | Wert | Grenze | Auslastung | Fall |
|---|---|---:|---:|---:|---|
| J6 | U XIAO_3V3 [V] | 3.3 | 3.6 | 92 % ⚠ | Sonde 200 mA, Abschluss gesetzt, Sendebetrieb |
| D1 | U Sperr [V] (≤ Vwm) | 25.3 | 28 | 90 % ⚠ | Panel offen −25 °C, Akku voll |
| J5 | U I2C_SCL [V] | 3.3 | 3.9 | 85 % ⚠ | Sonde 200 mA, Abschluss gesetzt, Sendebetrieb |
| J6 | U I2C_SDA [V] | 3.3 | 3.9 | 85 % ⚠ | Sonde 200 mA, Abschluss gesetzt, Sendebetrieb |
| J5 | U SENS_EN [V] | 3.3 | 3.9 | 85 % ⚠ | Nacht −20 °C, Messung 80 mA + Funk |
| R28 | P [W] | 1.6 | 2 | 80 %  | Panel offen −25 °C, Akku voll |
| R29 | P [W] | 1.6 | 2 | 80 %  | Panel offen −25 °C, Akku voll |
| R30 | P [W] | 1.6 | 2 | 80 %  | Panel offen −25 °C, Akku voll |
| R31 | P [W] | 1.6 | 2 | 80 %  | Panel offen −25 °C, Akku voll |
| R32 | P [W] | 1.6 | 2 | 80 %  | Panel offen −25 °C, Akku voll |
| R33 | P [W] | 1.6 | 2 | 80 %  | Panel offen −25 °C, Akku voll |
| D8 | U Sperr [V] (≤ Vwm) | 13.8 | 18 | 77 %  | Netzteil 13,8 V + Sonne, 20 °C |
| U1 | U VSOL [V] | 25 | 33 | 76 %  | Panel offen −25 °C, Akku voll |
| U5 | I Schalter Spitze [A] (Grenze min 1,6) | 1.19 | 1.6 | 75 %  | Akku 2,8 V, Sondenspitze 200 mA + Funk |
| U1 | U CHG_LED [V] | 24 | 33 | 73 %  | Panel offen −25 °C, Akku voll |
| U6 | U +3V3 [V] | 3.3 | 4.6 | 72 %  | Sonde 200 mA, Abschluss gesetzt, Sendebetrieb |
| C2 | U [V] | 25 | 35 | 71 %  | Panel offen −25 °C, Akku voll |
| D12 | U Sperr [V] (≤ Vwm) | 12.3 | 18 | 68 %  | Nacht −20 °C, Messung 80 mA + Funk |
| F2 | I [A] | 1 | 1.5 | 67 %  | Netzteil 12 V, 20 °C, Akku 30 % |
| Q9 | Uds [V] | -25 | 40 | 62 %  | Panel offen −25 °C, Akku voll |
| D9 | U Sperr [V] | 24.6 | 40 | 62 %  | Panel offen −25 °C, Akku voll |
| U4 | U VSYS [V] | 3.61 | 6 | 60 %  | Akku 3,8 V (Überladeschutz) |
| U5 | U VSYS [V] | 3.61 | 6 | 60 %  | Akku 3,8 V (Überladeschutz) |
| C2 | Rippelstrom [A] | 0.197 | 0.33 | 60 %  | Netzteil 12 V, 20 °C, Akku 30 % |
| Q7 | Ugs [V] | 11.9 | 20 | 59 %  | Panel offen −25 °C, Akku voll |
| F1 | I [A] | 0.871 | 1.5 | 58 %  | Sonne +4 °C (über der Ladeschwelle) |
| Q7 | Uds [V] | 22.2 | 40 | 55 %  | Akku 3,8 V (Überladeschutz) |
| U2 | U +3V3 [V] | 3.3 | 6 | 55 %  | Sonde 200 mA, Abschluss gesetzt, Sendebetrieb |
| U4 | U +3V3 [V] | 3.3 | 6 | 55 %  | Sonde 200 mA, Abschluss gesetzt, Sendebetrieb |
| U9 | U +3V3 [V] | 3.3 | 6 | 55 %  | Sonde 200 mA, Abschluss gesetzt, Sendebetrieb |
| U9 | U XIAO_3V3 [V] | 3.3 | 6 | 55 %  | Sonde 200 mA, Abschluss gesetzt, Sendebetrieb |
| U5 | U SENS_EN [V] | 3.3 | 6 | 55 %  | Nacht −20 °C, Messung 80 mA + Funk |
| Q1 | Uds [V] | -21.4 | 40 | 53 %  | Panel offen −25 °C, Akku voll |
| C11 | U [V] | 3.3 | 6.3 | 52 %  | Sonde 200 mA, Abschluss gesetzt, Sendebetrieb |
| Q4 | Ugs [V] | -6.13 | 12 | 51 %  | Nacht −20 °C, Messung 80 mA + Funk |
| U5 | U SW [V] | 12.7 | 25 | 51 %  | Nacht −20 °C, Messung 80 mA + Funk |
| C3 | U [V] | 25 | 50 | 50 %  | Panel offen −25 °C, Akku voll |
| C4 | U [V] | 25 | 50 | 50 %  | Panel offen −25 °C, Akku voll |
| C22 | U [V] | 25 | 50 | 50 %  | Panel offen −25 °C, Akku voll |
| Q9 | Ugs [V] | -9.96 | 20 | 50 %  | Netzteil 13,8 V + Sonne, 20 °C |
| D3 | I Mittel [A] | 2.47 | 5 | 49 %  | Sonne +4 °C (über der Ladeschwelle) |
| Q8 | Ugs [V] | 9.84 | 20 | 49 %  | Netzteil 13,8 V + Sonne, 20 °C |
| C13 | U [V] | 12.3 | 25 | 49 %  | Nacht −20 °C, Messung 80 mA + Funk |
| U7 | U +3V3 [V] | 3.3 | 7 | 47 %  | Sonde 200 mA, Abschluss gesetzt, Sendebetrieb |
| L1 | I eff [A] | 3.01 | 6.5 | 46 %  | Sonne +4 °C (über der Ladeschwelle) |
| L3 | I Spitze [A] (Isat) | 1.19 | 2.8 | 43 %  | Akku 2,8 V, Sondenspitze 200 mA + Funk |
| L3 | I eff [A] | 1.05 | 2.5 | 42 %  | Akku 2,8 V, Sondenspitze 200 mA + Funk |
| Q8 | Uds [V] | 25 | 60 | 42 %  | Panel offen −25 °C, Akku voll |
| R19 | P [W] | 0.0508 | 0.125 | 41 %  | Sonde 200 mA, Abschluss gesetzt, Sendebetrieb |
| D5 | I Mittel [A] | 0.2 | 0.5 | 40 %  | Akku 2,8 V, Sondenspitze 200 mA + Funk |
| U1 | U MPPT [V] | 2.54 | 6.5 | 39 %  | Netzteil 13,8 V + Sonne, 20 °C |
| U10 | U DC_DIV [V] | 3.21 | 8.39 | 38 %  | Netzteil 13,8 V + Sonne, 20 °C |
| U3 | U PROT_VDD–BAT_N [V] | 3.8 | 10 | 38 %  | Akku 3,8 V (Überladeschutz) |
| U3 | U PROT_OD–BAT_N [V] | 3.79 | 10 | 38 %  | Akku 3,8 V (Überladeschutz) |
| L1 | I Spitze [A] (Isat) | 3.34 | 9 | 37 %  | Sonne +4 °C (über der Ladeschwelle) |
| D3 | P [W] | 1.11 | 3 | 37 %  | Sonne +4 °C (über der Ladeschwelle) |
| C6 | U [V] | 3.61 | 10 | 36 %  | Akku 3,8 V (Überladeschutz) |
| C10 | U [V] | 3.61 | 10 | 36 %  | Akku 3,8 V (Überladeschutz) |
| C14 | U [V] | 3.61 | 10 | 36 %  | Akku 3,8 V (Überladeschutz) |
| U8 | U T_NTC [V] | 3.06 | 8.6 | 36 %  | Panel offen −25 °C, Akku voll |
| D9 | I [A] | 1 | 3 | 33 %  | Netzteil 12 V, 20 °C, Akku 30 % |
| R50 | U [V] | 25 | 75 | 33 %  | Panel offen −25 °C, Akku voll |
| R4 | U [V] | 25 | 75 | 33 %  | Panel offen −25 °C, Akku voll |
| C20 | U [V] | 3.3 | 10 | 33 %  | Sonde 200 mA, Abschluss gesetzt, Sendebetrieb |
| Q2.1 | Ugs [V] | 3.79 | 12 | 32 %  | Akku 3,8 V (Überladeschutz) |
| Q3.1 | Ugs [V] | 3.79 | 12 | 32 %  | Akku 3,8 V (Überladeschutz) |
| D5 | U Sperr [V] | 12.3 | 40 | 31 %  | Nacht −20 °C, Messung 80 mA + Funk |
| R7 | P [W] | 0.0377 | 0.125 | 30 %  | Sonne +4 °C (über der Ladeschwelle) |
| Q2.2 | Ugs [V] | 3.6 | 12 | 30 %  | Sonne 20 °C, Akku voll (Konstantspannung) |
| Q3.2 | Ugs [V] | 3.6 | 12 | 30 %  | Sonne 20 °C, Akku voll (Konstantspannung) |
| D2 | I [A] | 0.871 | 3 | 29 %  | Sonne +4 °C (über der Ladeschwelle) |
| D6 | U Pin 1 [V] | 3.29 | 12 | 27 %  | Nacht −20 °C, Messung 80 mA + Funk |
| D9 | P [W] | 0.405 | 1.5 | 27 %  | Netzteil 12 V, 20 °C, Akku 30 % |
| U7 | U RS485_A [V] | 3.29 | 12.5 | 26 %  | Nacht −20 °C, Messung 80 mA + Funk |
| Q1 | P Schalt+Leit [W] | 0.655 | 2.5 | 26 %  | Sonne +4 °C (über der Ladeschwelle) |
| Q2.1 | Id [A] | 1.5 | 6 | 25 %  | Sonne +4 °C (über der Ladeschwelle) |
| Q2.2 | Id [A] | -1.5 | 6 | 25 %  | Sonne +4 °C (über der Ladeschwelle) |
| Q3.2 | Id [A] | -1.5 | 6 | 25 %  | Sonne +4 °C (über der Ladeschwelle) |
| Q3.1 | Id [A] | 1.5 | 6 | 25 %  | Sonne +4 °C (über der Ladeschwelle) |
| R47 | U [V] | 18.6 | 75 | 25 %  | Netzteil 13,8 V + Sonne, 20 °C |
| U10 | U MPPT_REF [V] | 1.88 | 7.74 | 24 %  | Akku 2,8 V, Sondenspitze 200 mA + Funk |
| C9 | U [V] | 3.8 | 16 | 24 %  | Akku 3,8 V (Überladeschutz) |
| D2 | P [W] | 0.346 | 1.5 | 23 %  | Sonne +4 °C (über der Ladeschwelle) |
| C21 | U [V] | 3.61 | 16 | 23 %  | Akku 3,8 V (Überladeschutz) |
| C7 | U [V] | 3.61 | 16 | 23 %  | Akku 3,8 V (Überladeschutz) |
| C19 | U [V] | 3.61 | 16 | 23 %  | Akku 3,8 V (Überladeschutz) |
| R27 | U [V] | 16.7 | 75 | 22 %  | Akku 3,8 V (Überladeschutz) |
| C12 | U [V] | 11 | 50 | 22 %  | Nacht −20 °C, Messung 80 mA + Funk |
| U8 | U T_REF0 [V] | 1.86 | 8.61 | 22 %  | Akku 3,8 V (Überladeschutz) |
| U10 | U VSYS [V] | 3.61 | 17 | 21 %  | Akku 3,8 V (Überladeschutz) |
| U8 | U VSYS [V] | 3.61 | 17 | 21 %  | Akku 3,8 V (Überladeschutz) |
| U5 | U BST_FB [V] | 1.25 | 6 | 21 %  | Nacht −20 °C, Messung 80 mA + Funk |
| C8 | U [V] | 3.3 | 16 | 21 %  | Sonde 200 mA, Abschluss gesetzt, Sendebetrieb |
| C15 | U [V] | 3.3 | 16 | 21 %  | Sonde 200 mA, Abschluss gesetzt, Sendebetrieb |
| C18 | U [V] | 3.3 | 16 | 21 %  | Sonde 200 mA, Abschluss gesetzt, Sendebetrieb |
| U8 | U CHG_INHIBIT [V] | 3.5 | 17 | 21 %  | Panel offen −25 °C, Akku voll |
| U8 | U HEAT_OFF [V] | 3.44 | 17 | 20 %  | Akku 3,8 V (Überladeschutz) |
| Q6 | Uds [V] | 11.9 | 60 | 20 %  | Panel offen −25 °C, Akku voll |
| U8 | U T_REF2 [V] | 1.67 | 8.61 | 19 %  | Akku 3,8 V (Überladeschutz) |
| U1 | U CHG_FB [V] | 1.2 | 6.5 | 19 %  | Akku 3,8 V (Überladeschutz) |
| R1 | P [W] | 0.36 | 2 | 18 %  | Sonne +4 °C (über der Ladeschwelle) |
| Q10 | Ugs [V] | 3.5 | 20 | 18 %  | Panel offen −25 °C, Akku voll |
| Q6 | Ugs [V] | 3.44 | 20 | 17 %  | Akku 3,8 V (Überladeschutz) |
| U10 | U MPPT_EN [V] | 2.84 | 17 | 17 %  | Akku 3,8 V (Überladeschutz) |
| Q5 | Ugs [V] | 3.3 | 20 | 16 %  | Nacht −20 °C, Messung 80 mA + Funk |
| Q11 | Uds [V] | 9.84 | 60 | 16 %  | Netzteil 13,8 V + Sonne, 20 °C |
| R51 | U [V] | 11.1 | 75 | 15 %  | Netzteil 13,8 V + Sonne, 20 °C |
| R12 | U [V] | 11 | 75 | 15 %  | Nacht −20 °C, Messung 80 mA + Funk |
| U1 | U CHG_CSP [V] | 3.63 | 25 | 15 %  | Sonne 20 °C, Akku voll (Konstantspannung) |
| U1 | U VSYS [V] | 3.61 | 25 | 14 %  | Akku 3,8 V (Überladeschutz) |
| U5 | U BST_SW [V] | 3.61 | 25 | 14 %  | Akku 3,8 V (Überladeschutz) |
| Q4 | Uds [V] | -4.26 | 30 | 14 %  | Akku 3,8 V (Überladeschutz) |
| Q11 | Ugs [V] | 2.84 | 20 | 14 %  | Akku 3,8 V (Überladeschutz) |
| R40 | U [V] | 10.6 | 75 | 14 %  | Netzteil 13,8 V + Sonne, 20 °C |
| C1 | U [V] | -7 | 50 | 14 %  | Panel offen −25 °C, Akku voll |
| C3/C4/C22 | Rippelstrom je C [A] | 0.402 | 3 | 13 %  | Netzteil 12 V, 20 °C, Akku 30 % |
| R46 | U [V] | 9.96 | 75 | 13 %  | Netzteil 13,8 V + Sonne, 20 °C |
| R7 | U [V] | -19.4 | 150 | 13 %  | Sonne +4 °C (über der Ladeschwelle) |
| D2 | U Sperr [V] | 5.06 | 40 | 13 %  | Netzteil 12 V, 20 °C, Akku 30 % |
| R28 | U [V] | 25 | 200 | 12 %  | Panel offen −25 °C, Akku voll |
| R29 | U [V] | 25 | 200 | 12 %  | Panel offen −25 °C, Akku voll |
| R30 | U [V] | 25 | 200 | 12 %  | Panel offen −25 °C, Akku voll |
| R31 | U [V] | 25 | 200 | 12 %  | Panel offen −25 °C, Akku voll |
| R32 | U [V] | 25 | 200 | 12 %  | Panel offen −25 °C, Akku voll |
| R33 | U [V] | 25 | 200 | 12 %  | Panel offen −25 °C, Akku voll |
| R51 | P [W] | 0.0124 | 0.1 | 12 %  | Netzteil 13,8 V + Sonne, 20 °C |
| Q7 | Id [A] | 0.384 | 3.5 | 11 %  | Panel offen −25 °C, Akku voll |
| Q2.1 | Uds [V] | 2.15 | 20 | 11 %  | Akku 2,0 V (Tiefentladeschutz) |
| Q3.1 | Uds [V] | 2.15 | 20 | 11 %  | Akku 2,0 V (Tiefentladeschutz) |
| D4 | I [A] | 0.00194 | 0.02 | 10 %  | Sonne +4 °C (über der Ladeschwelle) |
| D3 | U Sperr [V] | 3.63 | 40 | 9 %  | Sonne 20 °C, Akku voll (Konstantspannung) |
| U2 | U INA_P [V] | 3.61 | 40 | 9 %  | Akku 3,8 V (Überladeschutz) |
| U2 | U INA_M [V] | 3.61 | 40 | 9 %  | Akku 3,8 V (Überladeschutz) |
| Q1 | I Spitze [A] | 3.34 | 40 | 8 %  | Sonne +4 °C (über der Ladeschwelle) |
| R15 | U [V] | 6.13 | 75 | 8 %  | Nacht −20 °C, Messung 80 mA + Funk |
| R53 | U [V] | 6.13 | 75 | 8 %  | Nacht −20 °C, Messung 80 mA + Funk |
| Q5 | Uds [V] | 4.26 | 60 | 7 %  | Akku 3,8 V (Überladeschutz) |
| Q4 | Id [A] | -0.2 | 4 | 5 %  | Akku 2,8 V, Sondenspitze 200 mA + Funk |
| R48 | U [V] | -3.61 | 75 | 5 %  | Akku 3,8 V (Überladeschutz) |
| R25 | U [V] | -3.6 | 75 | 5 %  | Panel offen −25 °C, Akku voll |
| R45 | U [V] | -3.39 | 75 | 5 %  | Netzteil 13,8 V + Sonne, 20 °C |
| R8 | P [W] | 0.0894 | 2 | 4 %  | Sonne +4 °C (über der Ladeschwelle) |
| R14 | U [V] | 3.3 | 75 | 4 %  | Nacht −20 °C, Messung 80 mA + Funk |
| D6 | U Pin 2 [V] | 0.516 | 12 | 4 %  | Akku 3,8 V (Überladeschutz) |
| R41 | U [V] | 3.21 | 75 | 4 %  | Netzteil 13,8 V + Sonne, 20 °C |
| Q10 | Uds [V] | 2.54 | 60 | 4 %  | Netzteil 13,8 V + Sonne, 20 °C |
| U7 | U RS485_B [V] | 0.516 | 12.5 | 4 %  | Akku 3,8 V (Überladeschutz) |
| R20 | U [V] | 2.87 | 75 | 4 %  | Sonne +45 °C, Akku leer |
| R40 | P [W] | 0.0034 | 0.1 | 3 %  | Netzteil 13,8 V + Sonne, 20 °C |
| R5 | U [V] | 2.54 | 75 | 3 %  | Netzteil 13,8 V + Sonne, 20 °C |
| R2 | U [V] | 2.41 | 75 | 3 %  | Akku 3,8 V (Überladeschutz) |
| R42 | U [V] | 2.18 | 75 | 3 %  | Netzteil 12 V, −10 °C |
| R49 | U [V] | -2.17 | 75 | 3 %  | Akku 2,0 V (Tiefentladeschutz) |
| R27 | P [W] | 0.00278 | 0.1 | 3 %  | Akku 3,8 V (Überladeschutz) |
| R43 | U [V] | 2.06 | 75 | 3 %  | Akku 3,8 V (Überladeschutz) |
| D10 | P [W] | 0.0101 | 0.41 | 2 %  | Netzteil 13,8 V + Sonne, 20 °C |
| R21 | U [V] | 1.82 | 75 | 2 %  | Panel offen −25 °C, Akku voll |
| R26 | U [V] | 1.77 | 75 | 2 %  | Akku 3,8 V (Überladeschutz) |
| R23 | U [V] | 1.67 | 75 | 2 %  | Akku 3,8 V (Überladeschutz) |
| R24 | U [V] | -1.56 | 75 | 2 %  | Sonne +4 °C (über der Ladeschwelle) |
| R4 | P [W] | 0.00208 | 0.1 | 2 %  | Panel offen −25 °C, Akku voll |
| R17 | U [V] | -1.55 | 75 | 2 %  | Sonne +45 °C, Akku leer |
| R13 | U [V] | 1.25 | 75 | 2 %  | Nacht −20 °C, Messung 80 mA + Funk |
| R19 | U [V] | 2.47 | 150 | 2 %  | Sonde 200 mA, Abschluss gesetzt, Sendebetrieb |
| R3 | U [V] | 1.2 | 75 | 2 %  | Akku 3,8 V (Überladeschutz) |
| R44 | U [V] | -1.12 | 75 | 1 %  | Netzteil 12 V, −10 °C |
| R47 | P [W] | 0.00104 | 0.1 | 1 %  | Netzteil 13,8 V + Sonne, 20 °C |
| R41 | P [W] | 0.00103 | 0.1 | 1 %  | Netzteil 13,8 V + Sonne, 20 °C |
| R46 | P [W] | 0.000993 | 0.1 | 1 %  | Netzteil 13,8 V + Sonne, 20 °C |
| Q8 | Id [A] | 0.00111 | 0.115 | 1 %  | Netzteil 13,8 V + Sonne, 20 °C |
| Q2.2 | Uds [V] | -0.185 | 20 | 1 %  | Akku 3,8 V (Überladeschutz) |
| Q3.2 | Uds [V] | -0.185 | 20 | 1 %  | Akku 3,8 V (Überladeschutz) |
| R18 | U [V] | 0.516 | 75 | 1 %  | Akku 3,8 V (Überladeschutz) |
| R50 | P [W] | 0.000624 | 0.1 | 1 %  | Panel offen −25 °C, Akku voll |
| R15 | P [W] | 0.000376 | 0.1 | 0 %  | Nacht −20 °C, Messung 80 mA + Funk |
| R53 | P [W] | 0.000376 | 0.1 | 0 %  | Nacht −20 °C, Messung 80 mA + Funk |
| R5 | P [W] | 0.0003 | 0.1 | 0 %  | Netzteil 13,8 V + Sonne, 20 °C |
| R22 | U [V] | 0.196 | 75 | 0 %  | Panel offen −25 °C, Akku voll |
| R17 | P [W] | 0.000239 | 0.1 | 0 %  | Sonne +45 °C, Akku leer |
| D14 | P [W] | 0.00092 | 0.41 | 0 %  | Akku 3,8 V (Überladeschutz) |
| D7 | P [W] | 0.000903 | 0.41 | 0 %  | Panel offen −25 °C, Akku voll |
| Q7 | P [W] | 0.00178 | 1 | 0 %  | Panel offen −25 °C, Akku voll |
| R12 | P [W] | 0.000148 | 0.1 | 0 %  | Nacht −20 °C, Messung 80 mA + Funk |
| Q6 | Id [A] | 0.000167 | 0.115 | 0 %  | Akku 3,8 V (Überladeschutz) |
| D3 | I [A] | 0.00595 | 5 | 0 %  | Akku 2,0 V (Tiefentladeschutz) |
| R14 | P [W] | 0.000109 | 0.1 | 0 %  | Nacht −20 °C, Messung 80 mA + Funk |
| L1 | I DC [A] | 0.00595 | 6.5 | 0 %  | Akku 2,0 V (Tiefentladeschutz) |
| U2 | U INA_P–INA_M [V] | 0.0299 | 40 | 0 %  | Sonne +4 °C (über der Ladeschwelle) |
| Q10 | Id [A] | 8.32e-05 | 0.115 | 0 %  | Panel offen −25 °C, Akku voll |
| R1 | U [V] | 0.12 | 200 | 0 %  | Sonne +4 °C (über der Ladeschwelle) |
| Q5 | Id [A] | 6.13e-05 | 0.115 | 0 %  | Nacht −20 °C, Messung 80 mA + Funk |
| R49 | P [W] | 4.71e-05 | 0.1 | 0 %  | Akku 2,0 V (Tiefentladeschutz) |
| Q4 | P [W] | 0.000641 | 1.4 | 0 %  | Sonde 200 mA, Abschluss gesetzt, Sendebetrieb |
| R2 | P [W] | 2.9e-05 | 0.1 | 0 %  | Akku 3,8 V (Überladeschutz) |
| D11 | P [W] | 0.000111 | 0.41 | 0 %  | Netzteil 13,8 V + Sonne, 20 °C |
| R18 | P [W] | 2.66e-05 | 0.1 | 0 %  | Akku 3,8 V (Überladeschutz) |
| R20 | P [W] | 2.5e-05 | 0.1 | 0 %  | Sonne +45 °C, Akku leer |
| Q11 | Id [A] | 2.5e-05 | 0.115 | 0 %  | Panel offen −25 °C, Akku voll |
| R13 | P [W] | 1.68e-05 | 0.1 | 0 %  | Nacht −20 °C, Messung 80 mA + Funk |
| R8 | U [V] | 0.0299 | 200 | 0 %  | Sonne +4 °C (über der Ladeschwelle) |
| R3 | P [W] | 1.45e-05 | 0.1 | 0 %  | Akku 3,8 V (Überladeschutz) |
| R48 | P [W] | 1.31e-05 | 0.1 | 0 %  | Akku 3,8 V (Überladeschutz) |
| R25 | P [W] | 1.3e-05 | 0.1 | 0 %  | Panel offen −25 °C, Akku voll |
| R45 | P [W] | 1.15e-05 | 0.1 | 0 %  | Netzteil 13,8 V + Sonne, 20 °C |
| R21 | P [W] | 6.65e-06 | 0.1 | 0 %  | Panel offen −25 °C, Akku voll |
| R23 | P [W] | 6.17e-06 | 0.1 | 0 %  | Akku 3,8 V (Überladeschutz) |
| R9 | U [V] | 0.00369 | 75 | 0 %  | Sonne 20 °C, Akku voll (Konstantspannung) |
| R42 | P [W] | 4.88e-06 | 0.1 | 0 %  | Netzteil 12 V, −10 °C |
| R43 | P [W] | 4.22e-06 | 0.1 | 0 %  | Akku 3,8 V (Überladeschutz) |
| D5 | P [W] | 1.42e-05 | 0.5 | 0 %  | Akku 2,8 V, Sondenspitze 200 mA + Funk |
| R34 | U [V] | -0.00155 | 75 | 0 %  | Sonde 200 mA, Abschluss gesetzt, Sendebetrieb |
| R35 | U [V] | -0.00155 | 75 | 0 %  | Sonde 200 mA, Abschluss gesetzt, Sendebetrieb |
| Q9 | Id [A] | -5.63e-05 | 4.4 | 0 %  | Netzteil 13,8 V + Sonne, 20 °C |
| R44 | P [W] | 1.25e-06 | 0.1 | 0 %  | Netzteil 12 V, −10 °C |
| D5 | I [A] | 4.98e-06 | 0.5 | 0 %  | Sonne +45 °C, Akku leer |
| R22 | P [W] | 7.14e-07 | 0.1 | 0 %  | Panel offen −25 °C, Akku voll |
| R24 | P [W] | 5.19e-07 | 0.1 | 0 %  | Sonne +4 °C (über der Ladeschwelle) |
| R16 | U [V] | -0.00033 | 75 | 0 %  | Sonde 200 mA, Abschluss gesetzt, Sendebetrieb |
| R36 | U [V] | -0.00033 | 75 | 0 %  | Sonde 200 mA, Abschluss gesetzt, Sendebetrieb |
| Q8 | P [W] | 6.25e-07 | 0.2 | 0 %  | Netzteil 13,8 V + Sonne, 20 °C |
| R26 | P [W] | 3.12e-07 | 0.1 | 0 %  | Akku 3,8 V (Überladeschutz) |
| U1 | U CHG_VG–VSOL [V] | 6.02e-07 | 0.3 | 0 %  | Akku 2,0 V (Tiefentladeschutz) |
| L3 | I DC [A] | 4.98e-06 | 2.5 | 0 %  | Sonne +45 °C, Akku leer |
| R38 | U [V] | 0.000144 | 75 | 0 %  | Akku 3,8 V (Überladeschutz) |
| R37 | U [V] | 0.0001 | 75 | 0 %  | Akku 3,8 V (Überladeschutz) |
| R9 | P [W] | 4.13e-08 | 0.1 | 0 %  | Sonne 20 °C, Akku voll (Konstantspannung) |
| Q6 | P [W] | 7.34e-08 | 0.2 | 0 %  | Sonne 20 °C, Akku 30 % (Konstantstrom) |
| Q1 | P [W] | 3.17e-07 | 2.5 | 0 %  | Akku 2,8 V, Sondenspitze 200 mA + Funk |
| Q10 | P [W] | 2.08e-08 | 0.2 | 0 %  | Sonne +1 °C (unter Ladeschwelle: Sperre, Heizung) |
| D4 | U Sperr [V] | 3.01e-07 | 5 | 0 %  | Akku 2,0 V (Tiefentladeschutz) |
| Q5 | P [W] | 1.08e-08 | 0.2 | 0 %  | Nacht −20 °C, Messung 80 mA + Funk |
| Q11 | P [W] | 1.01e-08 | 0.2 | 0 %  | Netzteil 13,8 V + Sonne, 20 °C |
| Q1 | Id [A] | 1.52e-06 | 40 | 0 %  | Akku 2,8 V, Sondenspitze 200 mA + Funk |
| Q9 | P [W] | 2.62e-08 | 1.25 | 0 %  | Panel offen −25 °C, Akku voll |
| R38 | P [W] | 2.06e-09 | 0.1 | 0 %  | Akku 3,8 V (Überladeschutz) |
| R37 | P [W] | 1e-09 | 0.1 | 0 %  | Akku 3,8 V (Überladeschutz) |
| R34 | P [W] | 5.11e-10 | 0.1 | 0 %  | Sonde 200 mA, Abschluss gesetzt, Sendebetrieb |
| R35 | P [W] | 5.11e-10 | 0.1 | 0 %  | Sonde 200 mA, Abschluss gesetzt, Sendebetrieb |
| R16 | P [W] | 1.09e-11 | 0.1 | 0 %  | Sonde 200 mA, Abschluss gesetzt, Sendebetrieb |
| R36 | P [W] | 1.09e-11 | 0.1 | 0 %  | Sonde 200 mA, Abschluss gesetzt, Sendebetrieb |
| Q1 | Ugs [V] | -2.5e-10 | 20 | 0 %  | Panel offen −25 °C, Akku voll |
| U1 | U CHG_DRV–VSOL [V] | 6.02e-18 | 0.3 | 0 %  | Akku 2,0 V (Tiefentladeschutz) |
| U1 | U CHG_COM [V] | 0 | 6.5 | 0 %  | Nacht 20 °C, Ruhe |
| R6 | P [W] | 0 | 0.1 | 0 %  | Nacht 20 °C, Ruhe |
| R6 | U [V] | 0 | 75 | 0 %  | Nacht 20 °C, Ruhe |
| C5 | U [V] | 0 | 16 | 0 %  | Nacht 20 °C, Ruhe |
| R10 | P [W] | 0 | 0.1 | 0 %  | Nacht 20 °C, Ruhe |
| R10 | U [V] | 0 | 75 | 0 %  | Nacht 20 °C, Ruhe |
| R11 | P [W] | 0 | 0.1 | 0 %  | Nacht 20 °C, Ruhe |
| R11 | U [V] | 0 | 75 | 0 %  | Nacht 20 °C, Ruhe |
| L2 | I DC [A] | 0 | 1.2 | 0 %  | Nacht 20 °C, Ruhe |
| C16 | U [V] | 0 | 50 | 0 %  | Nacht 20 °C, Ruhe |
| C17 | U [V] | 0 | 50 | 0 %  | Nacht 20 °C, Ruhe |

## Funktion

| Fall | Größe | Wert | Soll | |
|---|---|---:|---|---|
| Nacht 20 °C, Ruhe | P3V3 | 3.3 | 3.2 … 3.4 | ✓ |
| Nacht 20 °C, Ruhe | XIAO_3V3 | 3.3 | 3.1 … 3.4 | ✓ |
| Nacht 20 °C, Ruhe | Iheat | 1.01e-09 | 0 … 0.001 | ✓ |
| Nacht 20 °C, Ruhe | Ibat | -0.00964 | -0.02 … 0 | ✓ |
| Nacht −20 °C, Ruhe | Iheat | 1.01e-09 | 0 … 0.001 | ✓ |
| Nacht −20 °C, Ruhe | Ibat | -0.00964 | -0.02 … 0 | ✓ |
| Nacht −20 °C, Messung 80 mA + Funk | V12_PROBE | 12.3 | 11 … 12.6 | ✓ |
| Nacht −20 °C, Messung 80 mA + Funk | XIAO_3V3 | 3.28 | 3.1 … 3.4 | ✓ |
| Nacht −20 °C, Messung 80 mA + Funk | Iheat | 1.01e-09 | 0 … 0.001 | ✓ |
| Sonne 20 °C, Akku 30 % (Konstantstrom) | Ichg | 3 | 2.7 … 3.3 | ✓ |
| Sonne 20 °C, Akku 30 % (Konstantstrom) | Iheat | 1.04e-09 | 0 … 0.001 | ✓ |
| Sonne 20 °C, Akku voll (Konstantspannung) | VSYS | 3.61 | 3.5 … 3.66 | ✓ |
| Sonne −10 °C (Frost: Ladesperre, Heizung) | Ichg | -2.52e-05 | -0.01 … 0.01 | ✓ |
| Sonne −10 °C (Frost: Ladesperre, Heizung) | Iheat | 0.366 | 0.1 … 1 | ✓ |
| Sonne +1 °C (unter Ladeschwelle: Sperre, Heizung) | Ichg | -2.52e-05 | -0.01 … 0.01 | ✓ |
| Sonne +1 °C (unter Ladeschwelle: Sperre, Heizung) | Iheat | 0.354 | 0.1 … 1 | ✓ |
| Sonne +4 °C (über der Ladeschwelle) | Ichg | 3 | 0.1 … 3.3 | ✓ |
| Sonne +45 °C, Akku leer | Ichg | 3 | 0.3 … 3.3 | ✓ |
| Sonne +45 °C, Akku leer | Iheat | 1.04e-09 | 0 … 0.001 | ✓ |
| 10-W-Panel +10 °C (MPPT begrenzt) | VSOL | 18.4 | 15 … 21 | ✓ |
| Panel offen −25 °C, Akku voll | VSOL | 25 | 0 … 27 | ✓ |
| Netzteil 12 V, 20 °C, Akku 30 % | Ichg | 3 | 0.3 … 3.3 | ✓ |
| Netzteil 12 V, −10 °C | Ichg | -2.5e-05 | -0.01 … 0.01 | ✓ |
| Netzteil 12 V, −10 °C | Iheat | 0.179 | 0.05 … 1 | ✓ |
| Netzteil 13,8 V + Sonne, 20 °C | Ichg | 3 | 2.7 … 3.3 | ✓ |
| Akku 2,8 V, Sondenspitze 200 mA + Funk | P3V3 | 3.29 | 3.2 … 3.4 | ✓ |
| Akku 2,8 V, Sondenspitze 200 mA + Funk | V12_PROBE | 12.2 | 11 … 12.6 | ✓ |
| Akku 2,0 V (Tiefentladeschutz) | OD | 0.000204 | -0.1 … 0.5 | ✓ |
| Akku 3,8 V (Überladeschutz) | OC | 0.00038 | -0.1 … 0.5 | ✓ |
| Sonde 200 mA, Abschluss gesetzt, Sendebetrieb | V12_PROBE | 12.2 | 11 … 12.6 | ✓ |
