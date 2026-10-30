#include <map>

#include "Arduino.h"
#include "Wire.h"

namespace sim {
uint32_t now_ms = 0;
int pin_state[16] = {};
void tick() { now_ms += 1; }
}

SerialStub Serial1;
TwoWire Wire;
static std::map<uint8_t, I2CDevice*> devices;

void TwoWire::attach(uint8_t addr, I2CDevice* dev) { devices[addr] = dev; }
void TwoWire::detach(uint8_t addr) { devices.erase(addr); }

uint8_t TwoWire::endTransmission(bool) {
  auto it = devices.find(addr_);
  if (it == devices.end()) return 2;   // Adresse nicht bestätigt
  it->second->write(buf_);
  return 0;
}

uint8_t TwoWire::requestFrom(uint8_t addr, uint8_t n) {
  rx_.clear();
  pos_ = 0;
  auto it = devices.find(addr);
  if (it == devices.end()) return 0;
  rx_ = it->second->read(n);
  return (uint8_t)rx_.size();
}
