// PC-Test für das Tracker-Paketformat (tracker_packet.h), die Warteschlange (tracker/trk_queue.h) und den
// NMEA-Parser (tracker/nmea.h).
//
//   g++ -std=c++17 -I../common -I../tracker test_tracker.cpp -o test_tracker && ./test_tracker

#include <cstdio>
#include <cstdlib>
#include <cstring>

#include "tracker_packet.h"
#include "nmea.h"
#include "trk_queue.h"

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

static const uint8_t TAG[TRK_TAG_LEN] = { 1, 2, 3, 4 };

static TrackerRecord rec(uint32_t counter, bool fix, uint32_t age) {
  TrackerRecord r = {};
  r.counter = counter;
  r.flags = fix ? TRK_R_FIX : 0;
  r.age_s = age;
  if (fix) {
    r.lat_e7 = 495672000 + (int32_t)counter;
    r.lon_e7 = -108841000;
    r.alt_m = -12;
    r.sats = 9;
    r.hdop_x10 = 13;
  }
  return r;
}

static void test_uplink_roundtrip() {
  std::printf("Uplink: Kopf und Einträge\n");
  TrackerHead h = { (uint8_t)(TRK_F_BATT | TRK_F_ALARM | TRK_F_USB), 513, 4012 };
  TrackerRecord in[3] = { rec(100, true, 5), rec(99, false, 300), rec(98, true, 20000000) };
  in[0].flags |= TRK_R_MOTION | TRK_R_ALARM;
  uint8_t buf[TRK_UP_MAX_LEN + 16] = {};
  int used = 0;
  int n = trk_encode_uplink(TAG, h, in, 3, buf, used);
  CHECK(used == 3, "used %d", used);
  CHECK(n == 8 + 2 + 1 + 20 + 8 + 20, "Länge %d", n);
  TrackerUplink d;
  // MeshCore füllt auf 16-Byte-Blöcke auf: längere Daten müssen lesbar bleiben.
  CHECK(trk_decode_uplink(buf, ((n + 15) / 16) * 16, d), "mit Auffüllung nicht lesbar");
  CHECK(d.head.flags == h.flags && d.head.settings_version == 513 && d.head.batt_mv == 4012, "Kopf falsch");
  CHECK(d.n == 3, "Anzahl %u", d.n);
  CHECK(d.rec[0].counter == 100 && d.rec[0].flags == (TRK_R_FIX | TRK_R_MOTION | TRK_R_ALARM) && d.rec[0].age_s == 5,
        "Eintrag 0 falsch");
  CHECK(d.rec[0].lat_e7 == in[0].lat_e7 && d.rec[0].lon_e7 == -108841000 && d.rec[0].alt_m == -12, "Position 0 falsch");
  CHECK(d.rec[1].counter == 99 && d.rec[1].flags == 0 && d.rec[1].age_s == 300 && d.rec[1].lat_e7 == 0, "Eintrag 1 falsch");
  CHECK(d.rec[2].age_s == TRK_AGE_MAX, "Alter nicht begrenzt: %u", d.rec[2].age_s);
  CHECK(!trk_decode_uplink(buf, n - 1, d), "zu kurz akzeptiert");
  buf[4] = 'X';
  CHECK(!trk_decode_uplink(buf, n, d), "falscher Typ akzeptiert");
}

static void test_uplink_capacity() {
  std::printf("Uplink: so viele Einträge wie in eine REQ passen\n");
  TrackerRecord in[20];
  for (int i = 0; i < 20; i++) in[i] = rec(1000 - i, true, (uint32_t)i * 900);
  TrackerHead h = { TRK_F_BATT, 1, 3900 };
  uint8_t buf[TRK_UP_MAX_LEN] = {};
  int used = 0;
  int n = trk_encode_uplink(TAG, h, in, 20, buf, used);
  CHECK(used == 7, "mit Fix und Akku: %d Einträge", used);
  CHECK(n <= TRK_UP_MAX_LEN, "zu lang: %d", n);
  // Was MeshCore annimmt: data_len + 2 + 16 - 1 <= 184
  CHECK(n + 2 + 16 - 1 <= 184, "MeshCore nimmt %d Byte nicht", n);
  for (int i = 0; i < 20; i++) in[i] = rec(1000 - i, false, 60);
  n = trk_encode_uplink(TAG, h, in, 20, buf, used);
  CHECK(used == 19, "ohne Fix: %d Einträge", used);
  TrackerUplink d;
  CHECK(trk_decode_uplink(buf, n, d) && d.n == 19, "19 Einträge nicht lesbar");
  n = trk_encode_uplink(TAG, h, in, 0, buf, used);
  CHECK(used == 0 && trk_decode_uplink(buf, n, d) && d.n == 0, "leere REQ");
}

static void test_queue() {
  std::printf("Warteschlange: neueste zuerst, Quittung, Überlauf\n");
  static TrackerQueue q;
  trkq_clear(q);
  QueuedRecord r = {};
  for (uint32_t c = 1; c <= 10; c++) {
    r.counter = c;
    trkq_push(q, r);
  }
  QueuedRecord out[7];
  int n = trkq_take_newest(q, 7, out);
  CHECK(n == 7 && out[0].counter == 10 && out[6].counter == 4, "neueste zuerst: %d %u %u", n, out[0].counter, out[6].counter);
  trkq_drop_newest(q, 7);
  CHECK(q.count == 3 && trkq_newest(q)->counter == 3, "nach Quittung: %u", q.count);
  r.counter = 11;
  trkq_push(q, r);
  n = trkq_take_newest(q, 7, out);
  CHECK(n == 4 && out[0].counter == 11 && out[1].counter == 3 && out[3].counter == 1, "Rückstand nach neuem Eintrag");
  trkq_drop_newest(q, 99);
  CHECK(q.count == 0 && trkq_newest(q) == nullptr, "leeren");

  trkq_clear(q);
  for (uint32_t c = 1; c <= TRK_QUEUE_CAP + 5; c++) {
    r.counter = c;
    trkq_push(q, r);
  }
  CHECK(q.count == TRK_QUEUE_CAP && q.dropped == 5, "Überlauf: count %u dropped %u", q.count, q.dropped);
  CHECK(trkq_at(q, 0).counter == 6 && trkq_newest(q)->counter == TRK_QUEUE_CAP + 5, "älteste verdrängt");
  CHECK(trkq_valid(q), "ungültig nach Überlauf");
}

static void test_settings() {
  std::printf("Downlink: Einstellungen\n");
  TrackerSettings s = { 42, TRK_IV_5MIN, TRK_ALARM_HIGH, TRK_IV_1MIN };
  uint8_t buf[16] = {};
  trk_encode_settings(TAG, s, buf);
  TrackerSettings d = trk_default_settings();
  CHECK(trk_decode_settings(buf, 16, TAG, d), "nicht lesbar");
  CHECK(d.version == 42 && d.interval == TRK_IV_5MIN && d.alarm == TRK_ALARM_HIGH && d.alarm_interval == TRK_IV_1MIN,
        "Werte falsch");
  const uint8_t other[TRK_TAG_LEN] = { 9, 9, 9, 9 };
  CHECK(!trk_decode_settings(buf, 16, other, d), "fremder Tag akzeptiert");
  buf[8] = 7;
  TrackerSettings keep = d;
  CHECK(!trk_decode_settings(buf, 16, TAG, d), "ungültige Alarmstufe akzeptiert");
  CHECK(memcmp(&keep, &d, sizeof(d)) == 0, "ungültige Werte haben Einstellungen verändert");

  CHECK(trk_interval_s(TRK_IV_1MIN) == 60 && trk_interval_s(TRK_IV_60MIN) == 3600, "Intervalle");
  CHECK(trk_interval_code(300) == TRK_IV_5MIN && trk_interval_code(900) == TRK_IV_15MIN, "Codes");
  CHECK(trk_interval_code(120) == 0xFF, "120 s darf keinen Code haben");
  TrackerSettings def = trk_default_settings();
  CHECK(def.interval == TRK_IV_15MIN && def.alarm == TRK_ALARM_OFF, "Werkseinstellung");
}

static bool feed(NmeaParser& p, const char* s, NmeaFix& fix) {
  bool got = false;
  for (const char* c = s; *c; c++) got |= p.feed(*c, fix);
  return got;
}

static void test_nmea() {
  std::printf("NMEA: GGA lesen\n");
  NmeaParser p;
  NmeaFix f = {};
  // Beispielsatz mit gültiger Prüfsumme
  CHECK(feed(p, "$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47\r\n", f), "GGA nicht erkannt");
  CHECK(f.valid, "kein Fix");
  CHECK(std::abs(f.lat_e7 - 481173000) <= 1, "Breite %d", f.lat_e7);
  CHECK(std::abs(f.lon_e7 - 115166667) <= 1, "Länge %d", f.lon_e7);
  CHECK(f.sats == 8 && f.hdop_x10 == 9 && f.alt_m == 545, "Details %u %u %d", f.sats, f.hdop_x10, f.alt_m);

  // Süd/West und GNGGA (Mehrsystem-Empfänger)
  const char* body = "GNGGA,000000,3345.000,S,07030.000,W,1,05,1.5,10.0,M,0,M,,";
  uint8_t sum = 0;
  for (const char* c = body; *c; c++) sum ^= (uint8_t)*c;
  char line[120];
  std::snprintf(line, sizeof(line), "$%s*%02X\r\n", body, sum);
  CHECK(feed(p, line, f) && f.valid, "GNGGA nicht erkannt");
  CHECK(f.lat_e7 == -337500000 && f.lon_e7 == -705000000, "S/W falsch: %d %d", f.lat_e7, f.lon_e7);

  // Ohne Fix (Qualität 0, leere Felder)
  const char* nofix = "GNGGA,000001,,,,,0,00,25.5,,,,,,";
  sum = 0;
  for (const char* c = nofix; *c; c++) sum ^= (uint8_t)*c;
  std::snprintf(line, sizeof(line), "$%s*%02X\r\n", nofix, sum);
  CHECK(feed(p, line, f) && !f.valid, "Satz ohne Fix falsch behandelt");
  CHECK(f.hdop_x10 == 255, "HDOP 25,5 soll 255 sein");

  // Falsche Prüfsumme und andere Sätze werden ignoriert
  CHECK(!feed(p, "$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*48\r\n", f), "falsche Prüfsumme akzeptiert");
  CHECK(!feed(p, "$GPRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W*6A\r\n", f), "RMC als GGA gewertet");
  CHECK(!feed(p, "Müll ohne Dollar\r\n", f), "Müll akzeptiert");
}

int main() {
  test_uplink_roundtrip();
  test_uplink_capacity();
  test_queue();
  test_settings();
  test_nmea();
  if (failures) {
    std::printf("%d Fehler\n", failures);
    return 1;
  }
  std::printf("alles ok\n");
  return 0;
}
