#include "backlog.h"

#include <string.h>

void Backlog::push(uint32_t counter, uint64_t t, uint16_t level_mm, uint8_t flags) {
  if (n == PEGEL_BACKLOG_LEN) {
    memmove(&e[0], &e[1], sizeof(BacklogEntry) * (PEGEL_BACKLOG_LEN - 1));
    n--;
    dropped++;
  }
  e[n++] = { counter, t, level_mm, flags };
}

void Backlog::insert(uint32_t counter, uint64_t t_unix_ms, uint16_t level_mm) {
  int pos = n;
  while (pos > 0 && e[pos - 1].counter > counter) pos--;
  if (pos > 0 && e[pos - 1].counter == counter) return;
  if (n == PEGEL_BACKLOG_LEN) {
    if (pos == 0) {   // älter als alles im vollen Stau
      dropped++;
      return;
    }
    memmove(&e[0], &e[1], sizeof(BacklogEntry) * (pos - 1));
    n--;
    pos--;
    dropped++;
  }
  memmove(&e[pos + 1], &e[pos], sizeof(BacklogEntry) * (n - pos));
  e[pos] = { counter, t_unix_ms, level_mm, BL_ABS | BL_PERSISTED };
  n++;
}

void Backlog::sync(uint64_t uptime_ms, uint64_t unix_ms) {
  for (int i = 0; i < n; i++) {
    if (e[i].flags & BL_ABS) continue;
    uint64_t age = uptime_ms >= e[i].t ? uptime_ms - e[i].t : 0;
    e[i].t = unix_ms >= age ? unix_ms - age : 0;
    e[i].flags |= BL_ABS;
  }
}

void Backlog::expire(uint64_t uptime_ms, uint64_t unix_ms) {
  const uint64_t max_ms = PEGEL_BACKLOG_MAX_AGE_S * 1000;
  int w = 0;
  for (int i = 0; i < n; i++) {
    bool old;
    if (e[i].flags & BL_ABS) old = unix_ms != 0 && unix_ms > e[i].t && unix_ms - e[i].t > max_ms;
    else old = uptime_ms > e[i].t && uptime_ms - e[i].t > max_ms;
    if (old) {
      dropped++;
      continue;
    }
    if (w != i) e[w] = e[i];
    w++;
  }
  n = w;
}

int Backlog::build(uint64_t uptime_ms, uint16_t interval_s, PegelBlock& b) const {
  b.n = 0;
  if (n == 0) return 0;
  const BacklogEntry& newest = e[n - 1];
  uint8_t abs = newest.flags & BL_ABS;
  b.flags = abs ? PGB_F_ABS : 0;
  b.counter = newest.counter;
  if (abs) b.time = newest.t / 1000;
  else b.time = uptime_ms > newest.t ? (uptime_ms - newest.t) / 1000 : 0;
  b.interval_s = interval_s;
  b.level_mm[b.n++] = newest.level_mm;
  int64_t step = (int64_t)interval_s * 1000;
  for (int i = n - 2; i >= 0 && b.n < PGB_MAX_RECORDS; i--) {
    const BacklogEntry& newer = e[i + 1];
    const BacklogEntry& older = e[i];
    if (older.counter + 1 != newer.counter) break;
    if ((older.flags & BL_ABS) != abs) break;
    int64_t gap = (int64_t)(newer.t - older.t) - step;
    if (gap > PEGEL_BACKLOG_JITTER_MS || gap < -PEGEL_BACKLOG_JITTER_MS) break;
    b.level_mm[b.n++] = older.level_mm;
  }
  return b.n;
}

bool Backlog::remove(uint32_t counter, uint8_t n_records) {
  uint32_t lowest = counter - (n_records - 1);
  bool persisted = false;
  int w = 0;
  for (int i = 0; i < n; i++) {
    if (e[i].counter >= lowest && e[i].counter <= counter) {
      persisted |= (e[i].flags & BL_PERSISTED) != 0;
      continue;
    }
    if (w != i) e[w] = e[i];
    w++;
  }
  n = w;
  return persisted;
}
