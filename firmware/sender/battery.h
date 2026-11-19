#pragma once
// Akkuspannung und Unterspannung. Eine Firmware für beide Trägerplatinen (gleiche Pinbelegung):
//
//   pegel-sender (alt): LiFePO4 speist den XIAO über D10 (B5819W) direkt an 3V3, BAT des XIAO bleibt offen. Die
//                       Firmware misst ihre eigene Versorgung VDD und rechnet die Durchlassspannung dazu.
//   pegel-sender-v2:    Li-Ionen am BAT des XIAO (Lader BQ25101 auf dem XIAO), dessen Regler macht 3,3 V.
//                       Akku über den Teiler 1 MΩ / 510 kΩ an P0.31 (P0.14 low).
//
// battery_read() erkennt die Art bei jeder Messung: liegen an BAT mehr als 2,5 V, ist es Li-Ionen. (Am alten Board
// misst es so nur, solange USB am XIAO steckt: dann sieht es die Laderspannung des XIAO, harmlos.)

#include <stdint.h>

// Durchlassspannung von D10 bei ~6 mA (20 °C). Bei Kälte ist sie höher: die Messung liegt dann eher zu tief.
#ifndef PEGEL_VDD_DROP_MV
#define PEGEL_VDD_DROP_MV  200
#endif
#define PEGEL_BAT_PIN_MIN_MV  2500   // darüber hängt ein Li-Ionen-Akku an BAT

enum BatteryKind : uint8_t { BAT_LIFEPO4 = 0, BAT_LIION = 1 };

// Unter low gilt der Akku als fast leer (Sonde bleibt aus, Funk läuft weiter), erst ab ok wieder Pegel (sonst flattert
// die Meldung an der Kennlinie). Unter cutoff schalten Funk und Sonde ab, der Sender misst nur noch alle 30 min und
// startet neu, sobald der Akku wieder ok erreicht.
struct BatteryLimits {
  uint16_t low, ok, cutoff;
};

// LiFePO4: flache Kennlinie um 3,2 V. Li-Ionen: 3,4 V sind bei kleinem Strom noch ~5 %, der Regler des XIAO braucht
// etwa 3,35 V für 3,3 V; unter 3,25 V schläft der Sender, bevor die Schutzschaltung des Akkus (2,5-3 V) trennt.
static const BatteryLimits BATTERY_LIMITS[2] = {
    {2800, 3000, 2600},   // BAT_LIFEPO4
    {3400, 3600, 3250},   // BAT_LIION
};

// Neuer Zustand "fast leer" nach einer Messung: unter low wird er gesetzt, erst ab ok wieder gelöscht.
inline bool battery_low_update(bool low, uint16_t millivolt, BatteryKind kind) {
  const BatteryLimits& l = BATTERY_LIMITS[kind];
  if (millivolt < l.low) return true;
  if (millivolt >= l.ok) return false;
  return low;
}

inline bool battery_cutoff(uint16_t millivolt, BatteryKind kind) { return millivolt < BATTERY_LIMITS[kind].cutoff; }

// Akkuspannung in mV (8 Messungen gemittelt) und Akkuart. false, wenn die Messung unplausibel ist (dann bleiben
// millivolt und kind unverändert).
bool battery_read(uint16_t& millivolt, BatteryKind& kind);

// Ladestrom des XIAO-Laders auf 100 mA (pegel-sender-v2); am alten Board ohne Wirkung.
void battery_charger_begin();
