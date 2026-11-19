#include "battery.h"

#include <Arduino.h>

#define SAMPLES  8
#define BAT_DIVIDER_NUM  1510   // 1 MΩ + 510 kΩ
#define BAT_DIVIDER_DEN  510

// BAT des XIAO über den Teiler an P0.31, Referenz 3,0 V.
static uint32_t readBatPin() {
  pinMode(VBAT_ENABLE, OUTPUT);
  digitalWrite(VBAT_ENABLE, LOW);
  analogReference(AR_INTERNAL_3_0);
  analogReadResolution(12);
  uint32_t sum = 0;
  for (int i = 0; i < SAMPLES; i++) sum += analogRead(PIN_VBAT);
  return sum * 3000 / (SAMPLES * 4095UL) * BAT_DIVIDER_NUM / BAT_DIVIDER_DEN;
}

// SAADC an VDD, interne Referenz 0,6 V mit Verstärkung 1/6: 0–3,6 V auf 12 Bit.
static uint32_t readVdd() {
  analogReference(AR_INTERNAL);
  analogReadResolution(12);
  uint32_t sum = 0;
  for (int i = 0; i < SAMPLES; i++) sum += analogReadVDD();
  return sum * 3600 / (SAMPLES * 4095UL);
}

bool battery_read(uint16_t& millivolt, BatteryKind& kind) {
  uint32_t bat = readBatPin();
  if (bat > PEGEL_BAT_PIN_MIN_MV) {
    kind = BAT_LIION;
    millivolt = (uint16_t)bat;
    return true;
  }
  uint32_t vdd = readVdd();
  if (vdd <= 1500) return false;
  kind = BAT_LIFEPO4;
  millivolt = (uint16_t)(vdd + PEGEL_VDD_DROP_MV);
  return true;
}

void battery_charger_begin() {
  pinMode(PIN_CHARGING_CURRENT, OUTPUT);
  digitalWrite(PIN_CHARGING_CURRENT, LOW);   // P0.13 low: 100 mA statt 50 mA
}
