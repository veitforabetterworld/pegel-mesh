#pragma once
// Akkumessung mit dem INA226 der Trägerplatine (Adresse 0x40, Shunt 10 mΩ zwischen VSYS und Akku+).
// Strom positiv = Akku wird geladen. Zwischen den Messungen ist der INA226 abgeschaltet (~2 µA).

#include <stdint.h>

// LiFePO4 1S: unter 2,8 V fast leer, Funk und 3,3 V laufen noch (Schutz trennt bei 2,1 V).
// Einmal gemeldet, erst ab 3,0 V wieder Pegel — sonst flattert die Meldung an der Kennlinie.
#ifndef PEGEL_BATTERY_LOW_MV
#define PEGEL_BATTERY_LOW_MV  2800
#endif
#ifndef PEGEL_BATTERY_OK_MV
#define PEGEL_BATTERY_OK_MV   3000
#endif

// Neuer Zustand "fast leer" nach einer Messung: unter LOW wird er gesetzt, erst ab OK wieder gelöscht.
inline bool battery_low_update(bool low, uint16_t millivolt) {
  if (millivolt < PEGEL_BATTERY_LOW_MV) return true;
  if (millivolt >= PEGEL_BATTERY_OK_MV) return false;
  return low;
}

bool battery_begin();
// Eine Messung (~20 ms). false, wenn der Chip nicht antwortet.
bool battery_read(uint16_t& millivolt, int16_t& milliamp);
