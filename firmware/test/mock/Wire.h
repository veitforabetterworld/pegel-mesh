#pragma once
// I²C-Nachbildung: Geräte melden sich mit Adresse an und bekommen Schreib-/Lesezugriffe.
#include <stdint.h>
#include <stddef.h>
#include <vector>

struct I2CDevice {
  virtual ~I2CDevice() {}
  virtual void write(const std::vector<uint8_t>& bytes) = 0;          // komplette Schreibtransaktion
  virtual std::vector<uint8_t> read(size_t n) = 0;                     // Lesen nach (wiederholtem) Start
};

class TwoWire {
 public:
  void begin() {}
  void end() {}
  void setClock(uint32_t) {}
  void beginTransmission(uint8_t addr) { addr_ = addr; buf_.clear(); }
  size_t write(uint8_t b) { buf_.push_back(b); return 1; }
  size_t write(const uint8_t* d, size_t n) { buf_.insert(buf_.end(), d, d + n); return n; }
  uint8_t endTransmission(bool = true);
  uint8_t requestFrom(uint8_t addr, uint8_t n);
  int read() { if (pos_ >= rx_.size()) return -1; return rx_[pos_++]; }
  int available() { return (int)(rx_.size() - pos_); }

  void attach(uint8_t addr, I2CDevice* dev);
  void detach(uint8_t addr);

 private:
  uint8_t addr_ = 0;
  std::vector<uint8_t> buf_, rx_;
  size_t pos_ = 0;
};
extern TwoWire Wire;
