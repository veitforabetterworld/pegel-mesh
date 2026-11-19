#pragma once
// Messungen, die der Empfänger noch nicht quittiert hat (Blockformat: common/pegel_block.h).
//
// Jede Messung trägt ihre Zeit: absolut in Unix-Millisekunden, sobald der Sender die Uhrzeit aus einer Quittung
// kennt, sonst als Laufzeit seit dem Start (uptime_ms, 64 Bit). Kommt die Uhrzeit, rechnet sync() die Laufzeiten
// in absolute Zeiten um. Absolute Messungen überstehen einen Stromausfall im Flash (flashlog.h).
// Ist der Stau voll, fällt die älteste Messung heraus; nach PEGEL_BACKLOG_MAX_AGE_S verfällt eine Messung. Ein Block
// nimmt immer die neuesten Messungen: nach einer Störung kommt zuerst der aktuelle Pegel an.

#include <stdint.h>
#include "pegel_block.h"

#ifndef PEGEL_BACKLOG_LEN
  #define PEGEL_BACKLOG_LEN  6144   // 92 KB; Sender A (60 s) gut 4 Tage, Sender B (300 s) gut 3 Wochen
#endif

#define PEGEL_BACKLOG_MAX_AGE_S  (30ULL * 24 * 3600)

// Spielraum beim Messabstand innerhalb eines Blocks (der Abstand im Block ist für alle Einträge gleich).
#define PEGEL_BACKLOG_JITTER_MS  2000

#define BL_ABS        0x01   // t ist Unix-Zeit in ms, sonst Laufzeit in ms
#define BL_PERSISTED  0x02   // steht im Flash

struct BacklogEntry {
  uint32_t counter;
  uint64_t t;          // ms, siehe BL_ABS
  uint16_t level_mm;   // Pegel oder Fehlercode
  uint8_t flags;
} __attribute__((packed));

class Backlog {
  BacklogEntry e[PEGEL_BACKLOG_LEN];
  int n = 0;

public:
  uint32_t dropped = 0;

  int size() const { return n; }
  void clear() { n = 0; }
  const BacklogEntry& at(int i) const { return e[i]; }
  BacklogEntry& at(int i) { return e[i]; }

  // Hängt eine Messung an (Zähler aufsteigend); bei vollem Stau fällt die älteste heraus.
  void push(uint32_t counter, uint64_t t, uint16_t level_mm, uint8_t flags);
  // Fügt eine Messung aus dem Flash nach Zähler sortiert ein (beim Start); Doppelte werden übergangen.
  void insert(uint32_t counter, uint64_t t_unix_ms, uint16_t level_mm);
  // Rechnet Laufzeiten in Unix-Zeit um, sobald die Uhrzeit bekannt ist.
  void sync(uint64_t uptime_ms, uint64_t unix_ms);
  // Verwirft zu alte Messungen; unix_ms = 0, solange die Uhrzeit unbekannt ist.
  void expire(uint64_t uptime_ms, uint64_t unix_ms);
  // Füllt b (ohne tag und batt_mv) mit den neuesten Messungen, solange Zähler lückenlos, Zeitart gleich und
  // Abstände gleich sind. Gibt die Anzahl zurück (0 bei leerem Stau).
  int build(uint64_t uptime_ms, uint16_t interval_s, PegelBlock& b) const;
  // Entfernt die Messungen eines quittierten Blocks (Zähler counter-n+1 .. counter); true, wenn eine davon im
  // Flash stand.
  bool remove(uint32_t counter, uint8_t n_records);
};
