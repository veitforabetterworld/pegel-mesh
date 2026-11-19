#pragma once
// Messblock zwischen Pegel-Sender und Empfänger, mit Quittung.
//
// Der Sender hält jede Messung, bis der Empfänger sie quittiert hat (firmware/sender/backlog.h, bei gestörter
// Verbindung auch im Flash). Ein Block reist als MeshCore-REQ (mit dem gemeinsamen ECDH-Schlüssel verschlüsselt),
// der Empfänger antwortet mit einer RESPONSE, die den Tag wiederholt und seine Uhrzeit mitbringt. Ein Block trägt
// bis zu PGB_MAX_RECORDS aufeinanderfolgende Messungen, die neueste zuerst: Zähler und Messzeit der älteren ergeben
// sich aus dem ersten Eintrag und dem Messabstand.
//
// Die Messzeit steht absolut (Unix-Sekunden, sobald der Sender die Uhrzeit aus einer Quittung kennt; übersteht
// einen Stromausfall) oder relativ als Alter beim Senden (Messungen seit dem Start, bevor eine Quittung kam).
//
// Block (REQ-Daten), Sender -> Empfänger:
//   0..3    tag        Zufall: macht jede REQ einzigartig (sonst verwerfen Repeater sie als Duplikat),
//                      die Quittung wiederholt ihn
//   4       'L'
//   5       n          Anzahl der Pegel (1..PGB_MAX_RECORDS)
//   6..9    counter    uint32 LE, Zähler der neuesten Messung; jede ältere zählt eins weniger
//   10      flags      PGB_F_ABS: time ist absolut
//   11..15  time       uint40 LE, Unix-Sekunden der neuesten Messung (PGB_F_ABS) oder Sekunden seit ihr
//   16..17  interval   uint16 LE, Sekunden zwischen zwei Messungen des Blocks
//   18..19  batt_mv    uint16 LE, Akkuspannung beim Senden (0 = unbekannt)
//   n x     level_mm   uint16 LE, Pegel in mm oder ab PEGEL_STATUS_BASE ein Fehlercode (pegel_packet.h)
//
// Quittung (RESPONSE-Daten), Empfänger -> Sender:
//   0..3    tag        aus dem Block
//   4       'A'
//   5..9    now        uint40 LE, Unix-Sekunden beim Empfänger (0 = Uhr nicht gestellt)

#include <stdint.h>
#include <string.h>

#define PGB_TAG_LEN      4
#define PGB_TYPE         'L'
#define PGB_ACK_TYPE     'A'
#define PGB_HEAD_LEN     20
// Größte REQ, die MeshCore verschlüsselt verschickt (wie TRK_UP_MAX_LEN in tracker_packet.h).
#define PGB_MAX_LEN      167
#define PGB_MAX_RECORDS  ((PGB_MAX_LEN - PGB_HEAD_LEN) / 2)   // 73
#define PGB_TIME_MAX     0xFFFFFFFFFFULL                     // uint40: Unix-Sekunden bis ins Jahr 36812
#define PGB_ACK_LEN      10
#define PGB_F_ABS        0x01

struct PegelBlock {
  uint8_t  tag[PGB_TAG_LEN];
  uint8_t  n;
  uint8_t  flags;
  uint32_t counter;
  uint64_t time;        // PGB_F_ABS: Unix-Sekunden der neuesten Messung, sonst ihr Alter in Sekunden
  uint16_t interval_s;
  uint16_t batt_mv;
  uint16_t level_mm[PGB_MAX_RECORDS];   // neueste zuerst
};

static inline void pgb_put40(uint8_t* p, uint64_t v) {
  if (v > PGB_TIME_MAX) v = PGB_TIME_MAX;
  for (int k = 0; k < 5; k++) p[k] = (uint8_t)(v >> (8 * k));
}
static inline uint64_t pgb_get40(const uint8_t* p) {
  uint64_t v = 0;
  for (int k = 4; k >= 0; k--) v = (v << 8) | p[k];
  return v;
}

static inline int pgb_encode(const PegelBlock& b, uint8_t* out) {
  memcpy(out, b.tag, PGB_TAG_LEN);
  out[4] = PGB_TYPE;
  out[5] = b.n;
  for (int k = 0; k < 4; k++) out[6 + k] = (uint8_t)(b.counter >> (8 * k));
  out[10] = b.flags;
  pgb_put40(&out[11], b.time);
  out[16] = (uint8_t)b.interval_s;
  out[17] = (uint8_t)(b.interval_s >> 8);
  out[18] = (uint8_t)b.batt_mv;
  out[19] = (uint8_t)(b.batt_mv >> 8);
  for (int i = 0; i < b.n; i++) {
    out[PGB_HEAD_LEN + 2 * i] = (uint8_t)b.level_mm[i];
    out[PGB_HEAD_LEN + 2 * i + 1] = (uint8_t)(b.level_mm[i] >> 8);
  }
  return PGB_HEAD_LEN + 2 * b.n;
}

static inline bool pgb_decode(const uint8_t* data, int len, PegelBlock& b) {
  if (len < PGB_HEAD_LEN || data[4] != PGB_TYPE) return false;
  b.n = data[5];
  // MeshCore füllt auf ganze AES-Blöcke auf: hinten dürfen Nullbytes stehen.
  if (b.n < 1 || b.n > PGB_MAX_RECORDS || len < PGB_HEAD_LEN + 2 * b.n) return false;
  memcpy(b.tag, data, PGB_TAG_LEN);
  b.counter = (uint32_t)data[6] | ((uint32_t)data[7] << 8) | ((uint32_t)data[8] << 16) | ((uint32_t)data[9] << 24);
  b.flags = data[10];
  b.time = pgb_get40(&data[11]);
  b.interval_s = (uint16_t)(data[16] | (data[17] << 8));
  b.batt_mv = (uint16_t)(data[18] | (data[19] << 8));
  if (b.n > 1 && b.interval_s == 0) return false;
  if (b.counter < (uint32_t)(b.n - 1)) return false;   // Zähler der ältesten Messung wäre negativ
  for (int i = 0; i < b.n; i++) {
    b.level_mm[i] = (uint16_t)(data[PGB_HEAD_LEN + 2 * i] | (data[PGB_HEAD_LEN + 2 * i + 1] << 8));
  }
  return true;
}

static inline void pgb_encode_ack(const uint8_t tag[PGB_TAG_LEN], uint64_t now_s, uint8_t out[PGB_ACK_LEN]) {
  memcpy(out, tag, PGB_TAG_LEN);
  out[4] = PGB_ACK_TYPE;
  pgb_put40(&out[5], now_s);
}

/** true bei einer Quittung zu tag; now_s erhält die Uhrzeit des Empfängers (0 = unbekannt). */
static inline bool pgb_is_ack(const uint8_t* data, int len, const uint8_t tag[PGB_TAG_LEN], uint64_t& now_s) {
  if (len < PGB_ACK_LEN || data[4] != PGB_ACK_TYPE || memcmp(data, tag, PGB_TAG_LEN) != 0) return false;
  now_s = pgb_get40(&data[5]);
  return true;
}
