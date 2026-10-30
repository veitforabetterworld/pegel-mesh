#pragma once
// Nur für pegel_packet.h im PC-Test (die Treiber nutzen kein HMAC).
#include <stddef.h>
#include <stdint.h>
class SHA256 {
 public:
  void resetHMAC(const void*, size_t) {}
  void update(const void*, size_t) {}
  void finalizeHMAC(const void*, size_t, void*, size_t) {}
};
