# Leiterbahnen (Hochstrompfade)

Breitester Kupferweg je Pfad (Bahnen, Vias, Flächen); nötige Breite nach IPC-2221, außen, 35 µm, 20 K Erwärmung. Flächen zählen als 10 mm.

| Pfad | von → nach | Strom | Engstelle | nötig | |
|---|---|---:|---:|---:|---|
| Panel/Netzteil → Verpolschutz D2 | J1.1 → D2.2 | 1.2 A | 0.80 mm | 0.25 mm | ✓ |
| D2 → Lader-Eingang U1 | D2.1 → U1.7 | 0.8 A | 0.80 mm | 0.14 mm | ✓ |
| Schaltknoten U1 → L1 | U1.8 → L1.1 | 1.2 A | 0.60 mm | 0.25 mm | ✓ |
| Freilaufdiode D3 → L1 | D3.1 → L1.1 | 2.0 A | 2.00 mm | 0.51 mm | ✓ |
| L1 → Rückstromsperre Q1 | L1.2 → Q1.3 | 2.0 A | 2.00 mm | 0.51 mm | ✓ |
| Q1 → Akku+ | Q1.2 → J2.2 | 2.0 A | 1.20 mm | 0.51 mm | ✓ |
| Akku− → Shunt R15 | J2.1 → R15.1 | 1.0 A | 2.00 mm | 0.20 mm | ✓ |
| Akku− → Shunt R16 | J2.1 → R16.1 | 1.0 A | 2.00 mm | 0.20 mm | ✓ |
| Shunt → GND (Lader) | R15.2 → D3.2 | 2.0 A | 1.08 mm | 0.51 mm | ✓ |
| VSOL → Heizung (J4) | D2.1 → J4.1 | 0.4 A | 0.72 mm | 0.06 mm | ✓ |
| Heizung → Q4 | J4.2 → Q4.3 | 0.4 A | 0.80 mm | 0.06 mm | ✓ |
| Akku+ → 12-V-Wandler L2 | J2.2 → L2.1 | 0.5 A | 1.20 mm | 0.08 mm | ✓ |
| L2 → U5 Schalter | L2.2 → U5.1 | 0.5 A | 0.80 mm | 0.08 mm | ✓ |
| L2 → D7 | L2.2 → D7.2 | 0.5 A | 0.80 mm | 0.08 mm | ✓ |
| D7 → Q5 (12 V) | D7.1 → Q5.2 | 0.1 A | 0.54 mm | 0.00 mm | ✓ |
| Q5 → Sonde | Q5.3 → J3.1 | 0.1 A | 0.60 mm | 0.00 mm | ✓ |
| Akku+ → XIAO (D10) | J2.2 → D10.2 | 0.1 A | 0.72 mm | 0.01 mm | ✓ |
| D10 → XIAO 3V3 | D10.1 → J6.3 | 0.1 A | 0.60 mm | 0.01 mm | ✓ |

Mindestabstand 0.20 mm; höchste Spannung zwischen Netzen ≈ 27 V (Panel-Leerlauf kalt): IPC-2221 B2 (außen, unbeschichtet) verlangt 0,10 mm bis 30 V. ✓
