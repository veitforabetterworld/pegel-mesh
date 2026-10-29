#pragma once
// Pegel-Messpaket: 13 Byte, per HMAC-SHA256 (gekürzt) authentisiert, nicht verschlüsselt.
//
//   Byte  0..1   level_mm   uint16 LE   Pegel in mm
//   Byte  2..3   ctr_lo     uint16 LE   untere 16 Bit des 32-Bit-Zählers
//   Byte  4      age_s      uint8       Sekunden zwischen Messung und Senden
//   Byte  5..12  mac        8 Byte      HMAC-SHA256(key, "PGL1" | ctr32 | level | age)[0..8]
//
// Der Sender ist nicht im Paket kodiert: der Empfänger probiert die Schlüssel der
// bekannten Sender durch. Der volle Zähler fließt in den MAC ein, der Empfänger
// rekonstruiert die oberen 16 Bit aus dem zuletzt akzeptierten Zähler.

#include <stdint.h>
#include <string.h>
#include <SHA256.h>

#define PEGEL_PKT_LEN  13
#define PEGEL_MAC_LEN  8
#define PEGEL_KEY_LEN  32

struct PegelReading {
  uint16_t level_mm;
  uint32_t counter;
  uint8_t  age_s;
};

static inline void pegel_mac(const uint8_t key[PEGEL_KEY_LEN], uint32_t counter, uint16_t level_mm, uint8_t age_s,
                             uint8_t out[PEGEL_MAC_LEN]) {
  uint8_t msg[11] = { 'P', 'G', 'L', '1',
                      (uint8_t)counter, (uint8_t)(counter >> 8), (uint8_t)(counter >> 16), (uint8_t)(counter >> 24),
                      (uint8_t)level_mm, (uint8_t)(level_mm >> 8),
                      age_s };
  uint8_t full[32];
  SHA256 sha;
  sha.resetHMAC(key, PEGEL_KEY_LEN);
  sha.update(msg, sizeof(msg));
  sha.finalizeHMAC(key, PEGEL_KEY_LEN, full, sizeof(full));
  memcpy(out, full, PEGEL_MAC_LEN);
}

static inline void pegel_encode(const uint8_t key[PEGEL_KEY_LEN], const PegelReading& r, uint8_t out[PEGEL_PKT_LEN]) {
  out[0] = (uint8_t)r.level_mm;
  out[1] = (uint8_t)(r.level_mm >> 8);
  out[2] = (uint8_t)r.counter;
  out[3] = (uint8_t)(r.counter >> 8);
  out[4] = r.age_s;
  pegel_mac(key, r.counter, r.level_mm, r.age_s, &out[5]);
}

// Prüft das Paket gegen einen Schlüssel. last_counter: zuletzt akzeptierter Zähler dieses
// Senders (has_last=false, wenn unbekannt). Akzeptiert nur Zähler > last_counter (Replay-Schutz).
static inline bool pegel_verify(const uint8_t key[PEGEL_KEY_LEN], const uint8_t pkt[PEGEL_PKT_LEN],
                                bool has_last, uint32_t last_counter, PegelReading& r) {
  r.level_mm = (uint16_t)pkt[0] | ((uint16_t)pkt[1] << 8);
  uint16_t lo = (uint16_t)pkt[2] | ((uint16_t)pkt[3] << 8);
  r.age_s = pkt[4];

  // Kandidaten für die oberen 16 Bit: ohne Vorwissen die ersten 256 Bereiche,
  // sonst der aktuelle und der nächste (ein Überlauf zwischen zwei Paketen).
  uint32_t first_hi = has_last ? (last_counter >> 16) : 0;
  uint32_t n = has_last ? 2 : 256;
  uint8_t mac[PEGEL_MAC_LEN];
  for (uint32_t i = 0; i < n; i++) {
    uint32_t ctr = ((first_hi + i) << 16) | lo;
    if (has_last && ctr <= last_counter) continue;
    pegel_mac(key, ctr, r.level_mm, r.age_s, mac);
    uint8_t diff = 0;
    for (int k = 0; k < PEGEL_MAC_LEN; k++) diff |= mac[k] ^ pkt[5 + k];
    if (diff == 0) {
      r.counter = ctr;
      return true;
    }
  }
  return false;
}
