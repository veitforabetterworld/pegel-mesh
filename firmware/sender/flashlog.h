#pragma once
// Stau im Flash, damit Messungen einen Stromausfall überstehen (Sturzflut: erst bricht der Funk weg, dann der Strom).
//
// Ein Ringlog aus Seiten zu 4 KB im internen Flash, je Seite 256 Datensätze zu 16 Byte; der erste ist der
// Seitenkopf mit fortlaufender Nummer. Datensätze: Messung (Zähler, Unix-Sekunden, Pegel), Quittung (Zählerbereich),
// Leer (alles davor ist quittiert). Beim Start liest begin() das Log in Reihenfolge und legt die offenen Messungen in
// den Stau. Geschrieben wird nur bei gestörter Verbindung, im Normalbetrieb nie: über 30 Jahre bleibt jede Seite weit
// unter den 10 000 Löschzyklen des nRF52840. Jeder Datensatz trägt eine CRC; halb geschriebene oder fremde Daten
// (z. B. nach einem Firmware-Update) werden übergangen.

#include <stdint.h>
#include "backlog.h"

#define FLASHLOG_PAGE  4096
#define FLASHLOG_REC   16

// Zugriff auf den Flash; auf dem Gerät NVMC, im PC-Test ein Puffer.
struct FlashLogIO {
  virtual bool erase(uint32_t page_addr) = 0;
  virtual bool write(uint32_t addr, const uint8_t* src, int len) = 0;   // len Vielfaches von 4, nur 1 -> 0
  virtual const uint8_t* ptr(uint32_t addr) = 0;
};

class FlashLog {
  FlashLogIO& io;
  uint32_t base;
  int pages;
  int cur_page = -1;     // Seite, in die geschrieben wird
  int cur_slot = 0;      // nächster freier Datensatz darin
  uint32_t cur_seq = 0;
  bool dirty = false;    // seit dem letzten "Leer" etwas geschrieben

  bool writeRecord(uint8_t* rec);
  bool newPage();

public:
  FlashLog(FlashLogIO& io, uint32_t base, int pages) : io(io), base(base), pages(pages) {}

  // Liest das Log und legt offene Messungen in bl; gibt ihre Anzahl zurück.
  int begin(Backlog& bl);
  bool append(const BacklogEntry& e);           // nur Messungen mit Unix-Zeit (BL_ABS)
  bool ack(uint32_t counter, uint8_t n);
  bool clear();                                 // nur wenn seit dem letzten "Leer" etwas geschrieben wurde
  bool hasContent() const { return dirty; }
};
