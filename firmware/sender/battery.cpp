#include "battery.h"

#include <Arduino.h>
#include <Wire.h>

#ifndef PEGEL_INA226_ADDR
  #define PEGEL_INA226_ADDR  0x40   // A0 = A1 = GND
#endif

#define REG_CONFIG   0x00
#define REG_BUS      0x02
#define REG_CURRENT  0x04
#define REG_MASK     0x06
#define REG_CAL      0x05

// Strom-LSB 100 µA bei 10 mΩ: CAL = 0,00512 / (100 µA · 10 mΩ) = 5120, Messbereich ±3,2 A.
#define CAL_VALUE        5120
// 16 Mittelungen, 1,1 ms je Wandlung, Shunt und Bus einmalig (getriggert): ~35 ms
#define CONFIG_TRIGGER   (0x4000 | (2 << 9) | (4 << 6) | (4 << 3) | 0x3)
#define CONFIG_OFF       (0x4000 | (2 << 9) | (4 << 6) | (4 << 3) | 0x0)
#define MASK_READY       0x0008

static bool writeReg(uint8_t reg, uint16_t value) {
  Wire.beginTransmission(PEGEL_INA226_ADDR);
  Wire.write(reg);
  Wire.write((uint8_t)(value >> 8));
  Wire.write((uint8_t)value);
  return Wire.endTransmission() == 0;
}

static bool readReg(uint8_t reg, uint16_t& value) {
  Wire.beginTransmission(PEGEL_INA226_ADDR);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom((uint8_t)PEGEL_INA226_ADDR, (uint8_t)2) != 2) return false;
  value = (uint16_t)Wire.read() << 8;
  value |= Wire.read();
  return true;
}

bool battery_begin() {
  Wire.begin();
  return writeReg(REG_CAL, CAL_VALUE) && writeReg(REG_CONFIG, CONFIG_OFF);
}

bool battery_read(uint16_t& millivolt, int16_t& milliamp) {
  if (!writeReg(REG_CONFIG, CONFIG_TRIGGER)) return false;
  uint16_t mask = 0;
  uint32_t start = millis();
  do {
    delay(5);
    if (!readReg(REG_MASK, mask)) return false;
  } while (!(mask & MASK_READY) && millis() - start < 100);

  uint16_t bus, current;
  if (!readReg(REG_BUS, bus) || !readReg(REG_CURRENT, current)) return false;
  millivolt = (uint16_t)(((uint32_t)bus * 125) / 100);   // 1,25 mV je LSB
  milliamp = (int16_t)((int16_t)current / 10);           // 100 µA je LSB
  writeReg(REG_CONFIG, CONFIG_OFF);
  return true;
}
