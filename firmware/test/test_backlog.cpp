// PC-Test für den Stau des Senders (sender/backlog.cpp), das Flash-Log (sender/flashlog.cpp) und das Blockformat
// (common/pegel_block.h).
//
//   g++ -std=c++17 -I../sender -I../common test_backlog.cpp ../sender/backlog.cpp ../sender/flashlog.cpp
//       -o test_backlog && ./test_backlog

#include <cstdio>
#include <cstring>
#include <vector>

#include "backlog.h"
#include "flashlog.h"
#include "pegel_block.h"

static int failures = 0;
#define CHECK(cond, ...)                                     \
  do {                                                       \
    if (!(cond)) {                                           \
      failures++;                                            \
      std::printf("  FEHLER %s:%d: ", __FILE__, __LINE__);   \
      std::printf(__VA_ARGS__);                              \
      std::printf("\n");                                     \
    }                                                        \
  } while (0)

static Backlog bl;   // 92 KB, nicht auf den Stack

static const uint64_t T0 = 1795000000000ULL;   // Unix-ms, November 2026

static void testRoundTrip() {
  std::printf("Block kodieren und lesen\n");
  PegelBlock b = {};
  for (int k = 0; k < 4; k++) b.tag[k] = (uint8_t)(0xA0 + k);
  b.n = PGB_MAX_RECORDS;
  b.counter = 0x01020304;
  b.flags = PGB_F_ABS;
  b.time = 253402300799ULL;   // 9999-12-31
  b.interval_s = 60;
  b.batt_mv = 3312;
  for (int i = 0; i < b.n; i++) b.level_mm[i] = (uint16_t)(1000 + i);
  b.level_mm[3] = 0xFF01;
  uint8_t buf[PGB_MAX_LEN + 16] = {};
  int len = pgb_encode(b, buf);
  CHECK(len == PGB_HEAD_LEN + 2 * PGB_MAX_RECORDS && len <= PGB_MAX_LEN, "Länge %d", len);
  PegelBlock d;
  CHECK(pgb_decode(buf, len + 9, d), "decode schlägt fehl");   // mit AES-Auffüllung hinten
  CHECK(d.n == b.n && d.counter == b.counter && d.time == b.time && d.flags == PGB_F_ABS && d.interval_s == 60 &&
        d.batt_mv == 3312, "Kopf falsch");
  bool same = true;
  for (int i = 0; i < b.n; i++) same &= d.level_mm[i] == b.level_mm[i];
  CHECK(same, "Pegel falsch");
  CHECK(!pgb_decode(buf, len - 1, d), "zu kurz angenommen");
  buf[4] = 'P';
  CHECK(!pgb_decode(buf, len, d), "falscher Typ angenommen");

  uint8_t ack[PGB_ACK_LEN];
  pgb_encode_ack(b.tag, 1795080665ULL, ack);
  uint64_t now = 0;
  CHECK(pgb_is_ack(ack, sizeof(ack), b.tag, now) && now == 1795080665ULL, "Quittung/Zeit nicht erkannt");
  uint8_t other[4] = { 1, 2, 3, 4 };
  CHECK(!pgb_is_ack(ack, sizeof(ack), other, now), "fremde Quittung angenommen");
}

static void testBacklog() {
  std::printf("Stau: Blöcke, Quittung, Lücken, Uhrzeit\n");
  bl.clear();
  PegelBlock b;
  CHECK(bl.build(0, 60, b) == 0, "leerer Stau liefert Block");

  // 200 Messungen ohne Uhrzeit im 60-s-Takt (mit etwas Zittern), Zähler ab 257
  uint64_t t = 5000;
  for (uint32_t c = 257; c < 457; c++, t += 60000 + (c % 3) * 100) bl.push(c, t, (uint16_t)c, 0);
  uint64_t now = t;
  int n = bl.build(now, 60, b);
  CHECK(n == PGB_MAX_RECORDS && !(b.flags & PGB_F_ABS), "Block n=%d flags=%u", n, b.flags);
  CHECK(b.counter == 456 && b.level_mm[0] == 456 && b.level_mm[n - 1] == 456 - n + 1, "falsche Reihenfolge");
  CHECK(b.time == 60, "Alter %llu", (unsigned long long)b.time);

  bl.remove(b.counter, b.n);
  CHECK(bl.size() == 200 - PGB_MAX_RECORDS, "Größe %d", bl.size());

  // Uhrzeit kommt: alles wird absolut, der Block trägt Unix-Sekunden
  bl.sync(now, T0);
  n = bl.build(now, 60, b);
  CHECK((b.flags & PGB_F_ABS) && b.counter == 456 - PGB_MAX_RECORDS, "nach sync: flags=%u counter=%u", b.flags,
        (unsigned)b.counter);
  uint64_t want = (T0 - 60000ULL * (PGB_MAX_RECORDS + 1)) / 1000;
  CHECK(b.time + 20 >= want && b.time <= want + 20, "absolute Zeit %llu statt ~%llu", (unsigned long long)b.time,
        (unsigned long long)want);

  // Neue Messung nach einer Lücke im Zähler: der Block enthält nur sie
  bl.push(457, T0, 457, BL_ABS);
  n = bl.build(now, 60, b);
  CHECK(n == 1 && b.counter == 457 && b.time == T0 / 1000, "Block nach Lücke: n=%d counter=%u", n,
        (unsigned)b.counter);
  bl.remove(457, 1);

  // Relative und absolute Messungen kommen nicht in denselben Block
  Backlog* m = new Backlog();
  m->push(1, T0, 1, BL_ABS);
  m->push(2, 70000, 2, 0);
  n = m->build(70000, 60, b);
  CHECK(n == 1 && !(b.flags & PGB_F_ABS), "gemischter Block: n=%d", n);
  delete m;

  // Ungleicher Abstand beendet den Block
  Backlog* g = new Backlog();
  g->push(1, 0, 1, 0);
  g->push(2, 60000, 2, 0);
  g->push(3, 125000, 3, 0);   // 5 s später als der Takt
  g->push(4, 185000, 4, 0);
  n = g->build(185000, 60, b);
  CHECK(n == 2 && b.counter == 4, "Abstandsprüfung: n=%d", n);
  delete g;

  // Verfallen: relative nach 30 Tagen Laufzeit, absolute nach 30 Tagen Uhrzeit, absolute ohne Uhrzeit bleiben
  Backlog* x = new Backlog();
  x->push(1, 1000, 1, 0);
  x->push(2, T0, 2, BL_ABS);
  uint64_t d31 = 31ULL * 24 * 3600 * 1000;
  x->expire(1000 + d31, 0);
  CHECK(x->size() == 1 && x->at(0).counter == 2, "relativ verfallen: size=%d", x->size());
  x->expire(1000 + d31, T0 + d31);
  CHECK(x->size() == 0, "absolut verfallen: size=%d", x->size());
  delete x;

  // Einfügen aus dem Flash: sortiert, ohne Doppelte
  Backlog* s = new Backlog();
  s->push(600, 1, 6, 0);
  s->insert(300, T0, 3);
  s->insert(500, T0 + 1, 5);
  s->insert(300, T0, 3);
  CHECK(s->size() == 3 && s->at(0).counter == 300 && s->at(1).counter == 500 && s->at(2).counter == 600,
        "insert: size=%d", s->size());
  delete s;

  // Voller Stau verwirft die ältesten
  Backlog* f = new Backlog();
  for (uint32_t c = 0; c < PEGEL_BACKLOG_LEN + 10; c++) f->push(c, c * 60000ULL, 1, 0);
  CHECK(f->size() == PEGEL_BACKLOG_LEN && f->dropped == 10, "voll: size=%d dropped=%u", f->size(),
        (unsigned)f->dropped);
  delete f;
}

// Flash im RAM, wie der nRF52840: Löschen setzt 0xFF, Schreiben kann nur Bits löschen. Zählt Löschvorgänge je Seite.
struct RamFlash : FlashLogIO {
  uint32_t base;
  std::vector<uint8_t> mem;
  std::vector<int> erases;
  int fail_after = -1;   // Stromausfall: nach so vielen geschriebenen Bytes nichts mehr
  RamFlash(uint32_t base, int pages) : base(base), mem(pages * FLASHLOG_PAGE, 0xFF), erases(pages, 0) {}
  bool erase(uint32_t a) override {
    std::memset(&mem[a - base], 0xFF, FLASHLOG_PAGE);
    erases[(a - base) / FLASHLOG_PAGE]++;
    return true;
  }
  bool write(uint32_t a, const uint8_t* src, int len) override {
    for (int i = 0; i < len; i++) {
      if (fail_after == 0) return false;
      if (fail_after > 0) fail_after--;
      mem[a - base + i] &= src[i];
    }
    return true;
  }
  const uint8_t* ptr(uint32_t a) override { return &mem[a - base]; }
};

static void testFlashLog() {
  std::printf("Flash-Log: Stromausfall, Quittungen, Ring\n");
  const uint32_t BASE = 0xD5000;
  RamFlash flash(BASE, 24);

  // Erster Start: leeres Log
  {
    FlashLog log(flash, BASE, 24);
    bl.clear();
    CHECK(log.begin(bl) == 0 && bl.size() == 0, "leeres Log liefert Messungen");
    for (uint32_t c = 1000; c < 1100; c++) {
      BacklogEntry e = { c, T0 + (c - 1000) * 60000ULL, (uint16_t)(c - 900), BL_ABS };
      CHECK(log.append(e), "append %u", (unsigned)c);
    }
    CHECK(log.ack(1099, 20), "ack");   // die neuesten 20 kamen noch an
  }
  // Stromausfall, Neustart: 80 Messungen mit Pegel und Zeit zurück
  {
    FlashLog log(flash, BASE, 24);
    bl.clear();
    int r = log.begin(bl);
    CHECK(r == 80 && bl.size() == 80, "nach Neustart %d statt 80", r);
    CHECK(bl.at(0).counter == 1000 && bl.at(79).counter == 1079, "Zähler %u..%u", (unsigned)bl.at(0).counter,
          (unsigned)bl.at(79).counter);
    CHECK(bl.at(5).t == T0 + 5 * 60000ULL && bl.at(5).level_mm == 105, "Zeit/Pegel falsch");
    CHECK((bl.at(0).flags & (BL_ABS | BL_PERSISTED)) == (BL_ABS | BL_PERSISTED), "Flags %u", bl.at(0).flags);
    PegelBlock b;
    int n = bl.build(0, 60, b);   // ohne Uhrzeit sendbar: absolute Zeit
    CHECK(n == 73 && (b.flags & PGB_F_ABS) && b.time == (T0 + 79 * 60000ULL) / 1000, "Block nach Neustart n=%d", n);
    log.ack(1079, 73);
    log.ack(1006, 7);
    log.clear();
  }
  // Nach "Leer" kommt nichts zurück
  {
    FlashLog log(flash, BASE, 24);
    bl.clear();
    CHECK(log.begin(bl) == 0, "nach clear noch %d", bl.size());
  }
  // Halb geschriebener Datensatz (Strom fällt beim Schreiben): wird übergangen, danach geht es weiter
  {
    FlashLog log(flash, BASE, 24);
    bl.clear();
    log.begin(bl);
    BacklogEntry e = { 2000, T0, 7, BL_ABS };
    log.append(e);
    flash.fail_after = 7;
    BacklogEntry e2 = { 2001, T0 + 60000, 8, BL_ABS };
    log.append(e2);
    flash.fail_after = -1;
  }
  {
    FlashLog log(flash, BASE, 24);
    bl.clear();
    int r = log.begin(bl);
    CHECK(r == 1 && bl.at(0).counter == 2000, "halber Datensatz: %d", r);
    BacklogEntry e3 = { 2002, T0 + 120000, 9, BL_ABS };
    log.append(e3);
  }
  {
    FlashLog log(flash, BASE, 24);
    bl.clear();
    CHECK(log.begin(bl) == 2 && bl.at(1).counter == 2002, "nach halbem Datensatz weitergeschrieben: %d", bl.size());
    log.ack(2002, 3);
    log.clear();
  }
  // Langer Ausfall: der Ring läuft mehrfach um, die ältesten Seiten fallen heraus; Löschzyklen bleiben verteilt
  {
    FlashLog log(flash, BASE, 24);
    bl.clear();
    log.begin(bl);
    for (uint32_t c = 10000; c < 10000 + 3 * 24 * 255; c++) {
      BacklogEntry e = { c, T0 + c * 1000ULL, 1, BL_ABS };
      log.append(e);
    }
  }
  {
    FlashLog log(flash, BASE, 24);
    bl.clear();
    int r = log.begin(bl);
    CHECK(r >= 22 * 255 && r <= 24 * 255, "nach Umlauf %d Messungen", r);
    CHECK(bl.at(bl.size() - 1).counter == 10000 + 3 * 24 * 255 - 1, "neueste fehlt");
    int lo = 1 << 30, hi = 0;
    for (int e : flash.erases) {
      lo = e < lo ? e : lo;
      hi = e > hi ? e : hi;
    }
    CHECK(hi - lo <= 1, "Löschzyklen ungleich verteilt: %d..%d", lo, hi);
  }
  // Fremde Daten im Bereich (z. B. Firmware-Bild nach einem Update): kein Absturz, nichts übernommen
  {
    RamFlash junk(BASE, 24);
    for (size_t i = 0; i < junk.mem.size(); i++) junk.mem[i] = (uint8_t)(i * 2654435761u >> 13);
    FlashLog log(junk, BASE, 24);
    bl.clear();
    CHECK(log.begin(bl) == 0, "fremde Daten übernommen: %d", bl.size());
    BacklogEntry e = { 1, T0, 1, BL_ABS };
    CHECK(log.append(e), "nach fremden Daten nicht schreibbar");
  }
}

int main() {
  testRoundTrip();
  testBacklog();
  testFlashLog();
  if (failures) {
    std::printf("%d Fehler\n", failures);
    return 1;
  }
  std::printf("alles ok\n");
  return 0;
}
