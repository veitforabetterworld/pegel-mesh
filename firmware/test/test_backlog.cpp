// PC-Test für den Stau des Senders (sender/backlog.cpp) und das Blockformat (common/pegel_block.h).
//
//   g++ -std=c++17 -I../sender -I../common test_backlog.cpp ../sender/backlog.cpp -o test_backlog && ./test_backlog

#include <cstdio>

#include "backlog.h"
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

static Backlog bl;   // 60 KB, nicht auf den Stack

static void testRoundTrip() {
  std::printf("Block kodieren und lesen\n");
  PegelBlock b = {};
  for (int k = 0; k < 4; k++) b.tag[k] = (uint8_t)(0xA0 + k);
  b.n = PGB_MAX_RECORDS;
  b.counter = 0x01020304;
  b.age_s = 90000;
  b.interval_s = 60;
  b.batt_mv = 3312;
  for (int i = 0; i < b.n; i++) b.level_mm[i] = (uint16_t)(1000 + i);
  b.level_mm[3] = 0xFF01;
  uint8_t buf[PGB_MAX_LEN + 16] = {};
  int len = pgb_encode(b, buf);
  CHECK(len == PGB_HEAD_LEN + 2 * PGB_MAX_RECORDS && len <= PGB_MAX_LEN, "Länge %d", len);
  PegelBlock d;
  // mit AES-Auffüllung hinten
  CHECK(pgb_decode(buf, len + 9, d), "decode schlägt fehl");
  CHECK(d.n == b.n && d.counter == b.counter && d.age_s == b.age_s && d.interval_s == 60 && d.batt_mv == 3312,
        "Kopf falsch");
  bool same = true;
  for (int i = 0; i < b.n; i++) same &= d.level_mm[i] == b.level_mm[i];
  CHECK(same, "Pegel falsch");
  CHECK(!pgb_decode(buf, len - 1, d), "zu kurz angenommen");
  buf[4] = 'P';
  CHECK(!pgb_decode(buf, len, d), "falscher Typ angenommen");

  uint8_t ack[PGB_ACK_LEN];
  pgb_encode_ack(b.tag, ack);
  CHECK(pgb_is_ack(ack, sizeof(ack), b.tag), "Quittung nicht erkannt");
  uint8_t other[4] = { 1, 2, 3, 4 };
  CHECK(!pgb_is_ack(ack, sizeof(ack), other), "fremde Quittung angenommen");
}

static void testBacklog() {
  std::printf("Stau: Blöcke, Quittung, Lücken\n");
  PegelBlock b;
  CHECK(bl.build(0, 60, b) == 0, "leerer Stau liefert Block");

  // 200 Messungen im 60-s-Takt (mit etwas Zittern), Zähler ab 257
  uint32_t t = 5000;
  for (uint32_t c = 257; c < 457; c++, t += 60000 + (c % 3) * 100) bl.push(c, t, (uint16_t)c);
  uint32_t now = t;   // 60 s nach der letzten Messung
  int n = bl.build(now, 60, b);
  CHECK(n == PGB_MAX_RECORDS, "Block hat %d statt %d", n, PGB_MAX_RECORDS);
  CHECK(b.counter == 456 && b.level_mm[0] == 456 && b.level_mm[n - 1] == 456 - n + 1, "falsche Reihenfolge");
  CHECK(b.age_s == 60, "Alter %u", (unsigned)b.age_s);

  // Quittung: die 75 neuesten fallen weg, der nächste Block schließt lückenlos an
  bl.remove(b.counter, b.n);
  CHECK(bl.size() == 200 - PGB_MAX_RECORDS, "Größe %d", bl.size());
  n = bl.build(now, 60, b);
  CHECK(b.counter == 456 - PGB_MAX_RECORDS, "nächster Block beginnt bei %u", (unsigned)b.counter);
  // 75 Takte älter, jeder Takt bis 0,2 s länger
  CHECK(b.age_s >= 60 + 60 * PGB_MAX_RECORDS && b.age_s <= 60 + 60 * PGB_MAX_RECORDS + 15, "Alter %u",
        (unsigned)b.age_s);

  // Neue Messung nach einer Lücke im Zähler: der Block enthält nur sie
  bl.push(457, now, 457);
  n = bl.build(now + 1000, 60, b);
  // 457 schließt an 381 nicht an (381..456 sind quittiert)
  CHECK(n == 1 && b.counter == 457, "Block nach Lücke: n=%d counter=%u", n, (unsigned)b.counter);
  bl.remove(457, 1);
  n = bl.build(now + 2000, 60, b);
  CHECK(b.counter == 381 && n == PGB_MAX_RECORDS, "danach Stau ab %u (n=%d)", (unsigned)b.counter, n);

  // Ungleicher Abstand beendet den Block
  Backlog* g = new Backlog();
  g->push(1, 0, 1);
  g->push(2, 60000, 2);
  g->push(3, 125000, 3);   // 5 s später als der Takt
  g->push(4, 185000, 4);
  n = g->build(185000, 60, b);
  CHECK(n == 2 && b.counter == 4, "Abstandsprüfung: n=%d", n);
  delete g;

  // Nach 30 Tagen verfallen Messungen, auch über den millis()-Überlauf hinweg
  Backlog* x = new Backlog();
  uint32_t t0 = 0xFFFFFFFFu - 3600000u;   // eine Stunde vor dem Überlauf
  x->push(1, t0, 1);
  x->push(2, t0 + 60000u, 2);
  x->expire(t0 + 7200000u);                 // nach dem Überlauf, 2 h später: bleibt
  CHECK(x->size() == 2, "zu früh verworfen: %d", x->size());
  n = x->build(t0 + 7200000u, 60, b);
  CHECK(n == 2 && b.age_s == 7140, "Alter über den Überlauf: n=%d age=%u", n, (unsigned)b.age_s);
  x->expire(t0 + 60000u + PEGEL_BACKLOG_MAX_AGE_MS + 1);
  CHECK(x->size() == 0 && x->dropped == 2, "nicht verfallen: %d", x->size());
  delete x;

  // Voller Stau verwirft die ältesten
  Backlog* f = new Backlog();
  for (uint32_t c = 0; c < PEGEL_BACKLOG_LEN + 10; c++) f->push(c, c * 60000, 1);
  CHECK(f->size() == PEGEL_BACKLOG_LEN && f->dropped == 10, "voll: size=%d dropped=%u", f->size(),
        (unsigned)f->dropped);
  delete f;
}

int main() {
  testRoundTrip();
  testBacklog();
  if (failures) {
    std::printf("%d Fehler\n", failures);
    return 1;
  }
  std::printf("alles ok\n");
  return 0;
}
