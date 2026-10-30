#pragma once
// Akkumessung mit dem INA226 der Trägerplatine (Adresse 0x40, Shunt 10 mΩ zwischen VSYS und Akku+).
// Strom positiv = Akku wird geladen. Zwischen den Messungen ist der INA226 abgeschaltet (~2 µA).

#include <stdint.h>

bool battery_begin();
// Eine Messung (~20 ms). false, wenn der Chip nicht antwortet.
bool battery_read(uint16_t& millivolt, int16_t& milliamp);
