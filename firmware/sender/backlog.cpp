#include "backlog.h"

#include <string.h>

void Backlog::push(uint32_t counter, uint32_t at_ms, uint16_t level_mm) {
  if (n == PEGEL_BACKLOG_LEN) {
    memmove(&e[0], &e[1], sizeof(BacklogEntry) * (PEGEL_BACKLOG_LEN - 1));
    n--;
    dropped++;
  }
  e[n++] = { counter, at_ms, level_mm };
}

void Backlog::expire(uint32_t now_ms) {
  int k = 0;
  while (k < n && now_ms - e[k].at_ms > PEGEL_BACKLOG_MAX_AGE_MS) k++;
  if (k == 0) return;
  memmove(&e[0], &e[k], sizeof(BacklogEntry) * (n - k));
  n -= k;
  dropped += k;
}

int Backlog::build(uint32_t now_ms, uint16_t interval_s, PegelBlock& b) const {
  b.n = 0;
  if (n == 0) return 0;
  const BacklogEntry& newest = e[n - 1];
  b.counter = newest.counter;
  b.age_s = (now_ms - newest.at_ms) / 1000;
  b.interval_s = interval_s;
  b.level_mm[b.n++] = newest.level_mm;
  int32_t step = (int32_t)interval_s * 1000;
  for (int i = n - 2; i >= 0 && b.n < PGB_MAX_RECORDS; i--) {
    const BacklogEntry& newer = e[i + 1];
    const BacklogEntry& older = e[i];
    if (older.counter + 1 != newer.counter) break;
    int32_t gap = (int32_t)(newer.at_ms - older.at_ms) - step;
    if (gap > PEGEL_BACKLOG_JITTER_MS || gap < -PEGEL_BACKLOG_JITTER_MS) break;
    b.level_mm[b.n++] = older.level_mm;
  }
  return b.n;
}

void Backlog::remove(uint32_t counter, uint8_t n_records) {
  uint32_t lowest = counter - (n_records - 1);
  int w = 0;
  for (int i = 0; i < n; i++) {
    if (e[i].counter >= lowest && e[i].counter <= counter) continue;
    if (w != i) e[w] = e[i];
    w++;
  }
  n = w;
}
