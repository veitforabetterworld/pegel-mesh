#pragma once
// Akkuspannung ohne eigenen Messchip: auf der Trägerplatine hängt der XIAO über die Schottky-Diode D10
// (B5819W) direkt am Akku. Die Firmware misst ihre eigene Versorgung VDD und rechnet die Durchlassspannung dazu.

#include <stdint.h>

// LiFePO4 1S: unter 2,8 V fast leer, Sonde bleibt aus, Funk läuft weiter.
// Einmal gemeldet, erst ab 3,0 V wieder Pegel — sonst flattert die Meldung an der Kennlinie.
#ifndef PEGEL_BATTERY_LOW_MV
#define PEGEL_BATTERY_LOW_MV  2800
#endif
#ifndef PEGEL_BATTERY_OK_MV
#define PEGEL_BATTERY_OK_MV   3000
#endif
// Tiefentladeschutz: darunter schalten Funk und Sonde ab, der Sender misst nur noch alle 30 min und startet neu,
// sobald der Akku wieder PEGEL_BATTERY_OK_MV erreicht (Sonne).
#ifndef PEGEL_BATTERY_CUTOFF_MV
#define PEGEL_BATTERY_CUTOFF_MV  2600
#endif
// Durchlassspannung von D10 bei ~6 mA (20 °C). Bei Kälte ist sie höher: die Messung liegt dann eher zu tief.
#ifndef PEGEL_VDD_DROP_MV
#define PEGEL_VDD_DROP_MV  200
#endif

// Neuer Zustand "fast leer" nach einer Messung: unter LOW wird er gesetzt, erst ab OK wieder gelöscht.
inline bool battery_low_update(bool low, uint16_t millivolt) {
  if (millivolt < PEGEL_BATTERY_LOW_MV) return true;
  if (millivolt >= PEGEL_BATTERY_OK_MV) return false;
  return low;
}

inline bool battery_cutoff(uint16_t millivolt) { return millivolt < PEGEL_BATTERY_CUTOFF_MV; }

// Akkuspannung in mV (8 Messungen gemittelt). false, wenn die Messung unplausibel ist.
bool battery_read(uint16_t& millivolt);
