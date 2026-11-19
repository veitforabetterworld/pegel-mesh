#include "flashlog.h"

#include <string.h>

#define T_PAGE   0x5A
#define T_ENTRY  0xE1
#define T_ACK    0xA1
#define T_CLEAR  0xC1
#define T_FREE   0xFF
#define MAGIC    0x474C4750UL   // "PGLG"
#define SLOTS    (FLASHLOG_PAGE / FLASHLOG_REC)

static uint16_t crc16(const uint8_t* rec) {
  uint16_t crc = 0xFFFF;
  for (int i = 0; i < FLASHLOG_REC; i++) {
    if (i == 2 || i == 3) continue;   // Platz der CRC
    crc ^= (uint16_t)rec[i] << 8;
    for (int b = 0; b < 8; b++) crc = (crc & 0x8000) ? (uint16_t)((crc << 1) ^ 0x1021) : (uint16_t)(crc << 1);
  }
  return crc;
}

static void put32(uint8_t* p, uint32_t v) { for (int k = 0; k < 4; k++) p[k] = (uint8_t)(v >> (8 * k)); }
static uint32_t get32(const uint8_t* p) {
  return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

static bool valid(const uint8_t* rec) {
  return rec[0] != T_FREE && crc16(rec) == (uint16_t)(rec[2] | (rec[3] << 8));
}

static bool isFree(const uint8_t* rec) {
  for (int i = 0; i < FLASHLOG_REC; i++) if (rec[i] != 0xFF) return false;
  return true;
}

bool FlashLog::writeRecord(uint8_t* rec) {
  if (cur_page < 0 || cur_slot >= SLOTS) {
    if (!newPage()) return false;
  }
  uint16_t c = crc16(rec);
  rec[2] = (uint8_t)c;
  rec[3] = (uint8_t)(c >> 8);
  uint32_t addr = base + (uint32_t)cur_page * FLASHLOG_PAGE + (uint32_t)cur_slot * FLASHLOG_REC;
  cur_slot++;
  return io.write(addr, rec, FLASHLOG_REC);
}

bool FlashLog::newPage() {
  cur_page = cur_page < 0 ? 0 : (cur_page + 1) % pages;
  cur_seq++;
  uint32_t addr = base + (uint32_t)cur_page * FLASHLOG_PAGE;
  if (!io.erase(addr)) return false;
  uint8_t rec[FLASHLOG_REC];
  memset(rec, 0, sizeof(rec));
  rec[0] = T_PAGE;
  put32(&rec[4], cur_seq);
  put32(&rec[8], MAGIC);
  uint16_t c = crc16(rec);
  rec[2] = (uint8_t)c;
  rec[3] = (uint8_t)(c >> 8);
  cur_slot = 1;
  return io.write(addr, rec, FLASHLOG_REC);
}

int FlashLog::begin(Backlog& bl) {
  // Seiten mit gültigem Kopf nach Nummer ordnen (der Ring hat höchstens `pages` Seiten).
  int order[64];
  uint32_t seqs[64];
  int found = 0;
  for (int p = 0; p < pages && p < 64; p++) {
    const uint8_t* h = io.ptr(base + (uint32_t)p * FLASHLOG_PAGE);
    if (h[0] != T_PAGE || !valid(h) || get32(&h[8]) != MAGIC) continue;
    uint32_t s = get32(&h[4]);
    int i = found++;
    while (i > 0 && seqs[i - 1] > s) {
      seqs[i] = seqs[i - 1];
      order[i] = order[i - 1];
      i--;
    }
    seqs[i] = s;
    order[i] = p;
  }
  if (found == 0) {
    cur_page = -1;
    cur_seq = 0;
    return 0;
  }

  for (int k = 0; k < found; k++) {
    int p = order[k];
    int last_used = 0;
    for (int s = 1; s < SLOTS; s++) {
      const uint8_t* r = io.ptr(base + (uint32_t)p * FLASHLOG_PAGE + (uint32_t)s * FLASHLOG_REC);
      if (isFree(r)) continue;
      last_used = s;
      if (!valid(r)) continue;
      if (r[0] == T_ENTRY) {
        uint64_t sec = 0;
        for (int b = 4; b >= 0; b--) sec = (sec << 8) | r[8 + b];
        bl.insert(get32(&r[4]), sec * 1000, (uint16_t)(r[13] | (r[14] << 8)));
        dirty = true;
      } else if (r[0] == T_ACK) {
        bl.remove(get32(&r[4]), r[8]);
      } else if (r[0] == T_CLEAR) {
        bl.clear();   // beim Start stehen im Stau nur Messungen aus dem Log
        dirty = false;
      }
    }
    if (k == found - 1) {
      cur_page = p;
      cur_seq = seqs[k];
      cur_slot = last_used + 1;
    }
  }
  int restored = 0;
  for (int i = 0; i < bl.size(); i++) restored += (bl.at(i).flags & BL_PERSISTED) ? 1 : 0;
  return restored;
}

bool FlashLog::append(const BacklogEntry& e) {
  if (!(e.flags & BL_ABS)) return false;
  uint8_t rec[FLASHLOG_REC];
  memset(rec, 0, sizeof(rec));
  rec[0] = T_ENTRY;
  put32(&rec[4], e.counter);
  uint64_t sec = e.t / 1000;
  for (int b = 0; b < 5; b++) rec[8 + b] = (uint8_t)(sec >> (8 * b));
  rec[13] = (uint8_t)e.level_mm;
  rec[14] = (uint8_t)(e.level_mm >> 8);
  dirty = true;
  return writeRecord(rec);
}

bool FlashLog::ack(uint32_t counter, uint8_t n) {
  uint8_t rec[FLASHLOG_REC];
  memset(rec, 0, sizeof(rec));
  rec[0] = T_ACK;
  put32(&rec[4], counter);
  rec[8] = n;
  return writeRecord(rec);
}

bool FlashLog::clear() {
  if (!dirty) return true;
  uint8_t rec[FLASHLOG_REC];
  memset(rec, 0, sizeof(rec));
  rec[0] = T_CLEAR;
  dirty = false;
  return writeRecord(rec);
}
