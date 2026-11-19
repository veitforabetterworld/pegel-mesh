#pragma once
// Messungen, die der Empfänger noch nicht quittiert hat (Blockformat: common/pegel_block.h).
//
// Liegt nur im RAM: ein Neustart (Firmware-Update, Tiefentladung) verwirft den Stau. Ist er voll, fällt die
// älteste Messung heraus. Ein Block nimmt immer die neuesten Messungen: nach einer Störung kommt zuerst der
// aktuelle Pegel an, der Stau läuft danach rückwärts in der Zeit ab.

#include <stdint.h>
#include "pegel_block.h"

#ifndef PEGEL_BACKLOG_LEN
  #define PEGEL_BACKLOG_LEN  6144   // 60 KB; Sender A (60 s) gut 4 Tage, Sender B (300 s) gut 3 Wochen
#endif

// Ältere Messungen verfallen: millis() läuft nach 49,7 Tagen über, danach ließe sich ihr Alter nicht mehr
// berechnen. expire() muss deshalb spätestens alle 19 Tage laufen (der Sender ruft es bei jeder Messung auf).
#define PEGEL_BACKLOG_MAX_AGE_MS  (30UL * 24 * 3600 * 1000)

// Spielraum beim Messabstand innerhalb eines Blocks (der Abstand im Block ist für alle Einträge gleich).
#define PEGEL_BACKLOG_JITTER_MS  2000

struct BacklogEntry {
  uint32_t counter;
  uint32_t at_ms;      // millis() der Messung
  uint16_t level_mm;   // Pegel oder Fehlercode
} __attribute__((packed));

class Backlog {
  BacklogEntry e[PEGEL_BACKLOG_LEN];
  int n = 0;

public:
  uint32_t dropped = 0;

  int size() const { return n; }
  void push(uint32_t counter, uint32_t at_ms, uint16_t level_mm);
  // Verwirft Messungen, die älter als PEGEL_BACKLOG_MAX_AGE_MS sind.
  void expire(uint32_t now_ms);
  // Füllt b (ohne tag und batt_mv) mit den neuesten Messungen, solange Zähler lückenlos und Abstände gleich sind.
  // Gibt die Anzahl zurück (0 bei leerem Stau).
  int build(uint32_t now_ms, uint16_t interval_s, PegelBlock& b) const;
  // Entfernt die Messungen eines quittierten Blocks (Zähler counter-n+1 .. counter).
  void remove(uint32_t counter, uint8_t n_records);
};
