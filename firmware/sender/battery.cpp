#include "battery.h"

#include <Arduino.h>

#define SAMPLES  8

// SAADC an VDD, interne Referenz 0,6 V mit Verstärkung 1/6: 0–3,6 V auf 12 Bit.
bool battery_read(uint16_t& millivolt) {
  analogReference(AR_INTERNAL);
  analogReadResolution(12);
  uint32_t sum = 0;
  for (int i = 0; i < SAMPLES; i++) sum += analogReadVDD();
  uint32_t vdd_mv = sum * 3600 / (SAMPLES * 4095UL);
  millivolt = (uint16_t)(vdd_mv + PEGEL_VDD_DROP_MV);
  return vdd_mv > 1500;
}
