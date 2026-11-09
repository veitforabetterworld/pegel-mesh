#pragma once
// Warteschlange der noch nicht quittierten Einträge des Trackers (Ringpuffer, ohne Hardware, am PC testbar).
//
// Gesendet wird von hinten (die neuesten zuerst); nach einer Quittung fallen genau die gesendeten Einträge weg.
// Ist der Puffer voll, verdrängt ein neuer Eintrag den ältesten.

#include <stdint.h>
#include <string.h>

#define TRK_QUEUE_CAP 1024

struct QueuedRecord {
  uint32_t counter;
  uint32_t t_s;        // Zeitpunkt des Eintrags (Tracker-Uhr, s)
  int32_t lat_e7, lon_e7;
  int16_t alt_m;
  uint8_t sats;
  uint8_t hdop_x10;
  uint8_t flags;       // TRK_R_*
};

struct TrackerQueue {
  uint16_t head;       // Index des ältesten Eintrags
  uint16_t count;
  uint32_t dropped;    // durch Überlauf verdrängt (Diagnose)
  QueuedRecord rec[TRK_QUEUE_CAP];
};

static inline void trkq_clear(TrackerQueue& q) {
  q.head = 0;
  q.count = 0;
  q.dropped = 0;
}

static inline bool trkq_valid(const TrackerQueue& q) { return q.head < TRK_QUEUE_CAP && q.count <= TRK_QUEUE_CAP; }

static inline QueuedRecord& trkq_at(TrackerQueue& q, int i) { return q.rec[(q.head + i) % TRK_QUEUE_CAP]; }

/** Hängt einen Eintrag an; ist der Puffer voll, fällt der älteste weg. */
static inline void trkq_push(TrackerQueue& q, const QueuedRecord& r) {
  if (q.count == TRK_QUEUE_CAP) {
    q.head = (uint16_t)((q.head + 1) % TRK_QUEUE_CAP);
    q.count--;
    q.dropped++;
  }
  q.rec[(q.head + q.count) % TRK_QUEUE_CAP] = r;
  q.count++;
}

/** Zeiger auf den neuesten Eintrag oder nullptr. */
static inline QueuedRecord* trkq_newest(TrackerQueue& q) { return q.count ? &trkq_at(q, q.count - 1) : nullptr; }

/** Kopiert bis zu k der neuesten Einträge nach out, neuester zuerst; gibt die Anzahl zurück. */
static inline int trkq_take_newest(TrackerQueue& q, int k, QueuedRecord* out) {
  int n = k < q.count ? k : q.count;
  for (int i = 0; i < n; i++) out[i] = trkq_at(q, q.count - 1 - i);
  return n;
}

/** Entfernt die k neuesten Einträge (nach deren Quittung). */
static inline void trkq_drop_newest(TrackerQueue& q, int k) { q.count = (uint16_t)(k < q.count ? q.count - k : 0); }
