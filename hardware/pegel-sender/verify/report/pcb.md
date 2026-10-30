# Leiterbahnen (Hochstrompfade)

Breitester Kupferweg je Pfad (Bahnen, Vias, Flächen); nötige Breite nach IPC-2221, außen, 35 µm, 20 K Erwärmung. Flächen zählen als 10 mm.

| Pfad | von → nach | Strom | Engstelle | nötig | |
|---|---|---:|---:|---:|---|
| Panel → Sicherung | J1.1 → F1.1 | 1.2 A | 1.20 mm | 0.25 mm | ✓ |
| Sicherung → Verpolschutz D2 | F1.2 → D2.2 | 1.2 A | 1.20 mm | 0.25 mm | ✓ |
| Netzteil → Sicherung | J7.1 → F2.1 | 1.0 A | 1.20 mm | 0.20 mm | ✓ |
| Sicherung → Diode D9 | F2.2 → D9.2 | 1.0 A | 10.00 mm | 0.20 mm | ✓ |
| Diode D9 → VSOL (Lader) | D9.1 → Q1.3 | 1.0 A | 0.51 mm | 0.20 mm | ✓ |
| VSOL → Q1 (Lader-Eingang) | D2.1 → Q1.3 | 1.2 A | 10.00 mm | 0.25 mm | ✓ |
| VSOL → Heizwiderstände | D2.1 → R28.1 | 0.4 A | 0.51 mm | 0.06 mm | ✓ |
| Heizung → Q7 | R33.2 → Q7.3 | 0.4 A | 1.20 mm | 0.06 mm | ✓ |
| Schaltknoten Q1 → L1 | Q1.2 → L1.1 | 3.3 A | 10.00 mm | 1.02 mm | ✓ |
| Freilaufdiode D3 → L1 | D3.1 → L1.1 | 3.0 A | 1.20 mm | 0.90 mm | ✓ |
| L1 → Strommess-R1 | L1.2 → R1.1 | 3.0 A | 10.00 mm | 0.90 mm | ✓ |
| R1 → Shunt R8 (VSYS) | R1.2 → R8.1 | 3.0 A | 10.00 mm | 0.90 mm | ✓ |
| Shunt R8 → Akku+ | R8.2 → J2.1 | 3.0 A | 1.08 mm | 0.90 mm | ✓ |
| Akku− → Schutz-FET Q2 | J2.2 → Q2.2 | 1.5 A | 10.00 mm | 0.35 mm | ✓ |
| Akku− → Schutz-FET Q3 | J2.2 → Q3.2 | 1.5 A | 10.00 mm | 0.35 mm | ✓ |
| Schutz-FET Q2 → GND (Lader) | Q2.6 → D3.2 | 1.5 A | 0.40 mm | 0.35 mm | ✓ |
| Schutz-FET Q3 → GND (Lader) | Q3.6 → D3.2 | 1.5 A | 0.40 mm | 0.35 mm | ✓ |
| VSYS → 12-V-Wandler L3 | R8.1 → L3.1 | 1.2 A | 0.30 mm | 0.25 mm | ✓ |
| L3 → U5 Schalter | L3.2 → U5.1 | 1.2 A | 0.60 mm | 0.25 mm | ✓ |
| L3 → D5 | L3.2 → D5.2 | 1.2 A | 0.60 mm | 0.25 mm | ✓ |
| D5 → Q4 (12 V) | D5.1 → Q4.2 | 0.2 A | 0.40 mm | 0.02 mm | ✓ |
| Q4 → Sonde | Q4.3 → J3.1 | 0.2 A | 0.40 mm | 0.02 mm | ✓ |
| VSYS → 3,3-V-Wandler | R8.1 → U4.10 | 0.2 A | 0.30 mm | 0.03 mm | ✓ |
| 3,3 V → XIAO | U9.6 → J6.3 | 0.1 A | 0.23 mm | 0.01 mm | ✓ |

Mindestabstand 0.20 mm; höchste Spannung zwischen Netzen ≈ 27 V (Panel-Leerlauf kalt): IPC-2221 B2 (außen, unbeschichtet) verlangt 0,10 mm bis 30 V. ✓
