#pragma once
// Pakete zwischen GPS-Tracker und Empfänger.
//
// Beide reisen als Nutzdaten einer MeshCore-Datagramm-Nachricht: der Tracker schickt eine REQ, der Empfänger
// antwortet mit einer RESPONSE (bzw. bei der Pfadsuche mit einem Path-Return, der die RESPONSE mitträgt).
// MeshCore verschlüsselt beides mit dem gemeinsamen ECDH-Schlüssel der zwei Knoten.
//
// Der Tracker speichert jede Meldung (Eintrag) zwischen und schickt sie, bis sie quittiert ist; eine REQ trägt
// mehrere Einträge, die neuesten zuerst. Jeder Eintrag hat einen eigenen, fortlaufenden Zähler; der Server
// erkennt daran Doppelte. Die Quittung gilt für alle Einträge der REQ.
//
// Uplink (REQ-Daten), Tracker -> Empfänger:
//   0..3    tag        Zufall: macht jede REQ einzigartig (sonst verwerfen Repeater sie als Duplikat),
//                      die Antwort wiederholt ihn
//   4       'T'
//   5       flags      Zustand beim Senden: TRK_F_*
//   6..7    settings   uint16 LE, Version der gerade angewandten Einstellungen (0 = Werkseinstellung)
//   bei TRK_F_BATT: batt_mv uint16 LE
//   n       uint8      Anzahl der Einträge
//   n Einträge:
//           counter uint32 LE, rflags uint8 (TRK_R_*), age uint24 LE (s zwischen Eintrag und Senden)
//           bei TRK_R_FIX zusätzlich: lat int32 LE (1e-7 Grad), lon int32 LE, alt int16 LE (m), sats uint8,
//           hdop uint8 (Zehntel, 255 = 25,5 oder mehr)
//
// Downlink (RESPONSE-Daten), Empfänger -> Tracker:
//   0..3    tag        aus der REQ
//   4       'S'
//   5..6    version    uint16 LE; 0 = der Empfänger kennt keine Einstellungen, der Tracker behält seine
//   7       interval   TRK_IV_* (Ortungsintervall im Ruhezustand)
//   8       alarm      TRK_ALARM_* (Empfindlichkeit des Bewegungsalarms)
//   9       alarm_iv   TRK_IV_* (Intervall während eines Alarms)

#include <stdint.h>
#include <string.h>

#define TRK_TAG_LEN       4
#define TRK_UP_TYPE       'T'
#define TRK_DOWN_TYPE     'S'
// Größte REQ, die MeshCore verschlüsselt verschickt: data_len + MAC (2) + Block (16) - 1 <= 184.
#define TRK_UP_MAX_LEN    167
#define TRK_REC_BASE_LEN  8
#define TRK_REC_FIX_LEN   12
#define TRK_MAX_RECORDS   20      // obere Grenze beim Lesen (Einträge ohne Fix sind kürzer)
#define TRK_AGE_MAX       0xFFFFFFUL
#define TRK_DOWN_LEN      10

// Zustand beim Senden (Kopf)
#define TRK_F_BATT      0x01   // Akkuspannung folgt
#define TRK_F_ALARM     0x02   // Alarm gerade aktiv
#define TRK_F_CHARGING  0x04   // Akku wird geladen
#define TRK_F_USB       0x08   // USB-Versorgung vorhanden

// Eintrag
#define TRK_R_FIX       0x01   // Positionsdaten folgen
#define TRK_R_MOTION    0x02   // Eintrag wurde durch eine Bewegung ausgelöst (Alarmbeginn)
#define TRK_R_ALARM     0x04   // Alarm war beim Eintrag aktiv

enum TrackerInterval : uint8_t { TRK_IV_1MIN = 0, TRK_IV_5MIN = 1, TRK_IV_15MIN = 2, TRK_IV_60MIN = 3 };
enum TrackerAlarm : uint8_t { TRK_ALARM_OFF = 0, TRK_ALARM_LOW = 1, TRK_ALARM_MEDIUM = 2, TRK_ALARM_HIGH = 3 };

static inline uint32_t trk_interval_s(uint8_t code) {
  switch (code) {
    case TRK_IV_1MIN:  return 60;
    case TRK_IV_5MIN:  return 300;
    case TRK_IV_60MIN: return 3600;
    default:           return 900;
  }
}

/** Code zu einer Sekundenzahl (für die API), oder 0xFF, wenn sie keinem Code entspricht. */
static inline uint8_t trk_interval_code(uint32_t seconds) {
  for (uint8_t c = 0; c <= TRK_IV_60MIN; c++) {
    if (trk_interval_s(c) == seconds) return c;
  }
  return 0xFF;
}

struct TrackerSettings {
  uint16_t version;
  uint8_t interval;
  uint8_t alarm;
  uint8_t alarm_interval;
};

static inline TrackerSettings trk_default_settings() {
  TrackerSettings s;
  s.version = 0;
  s.interval = TRK_IV_15MIN;
  s.alarm = TRK_ALARM_OFF;
  s.alarm_interval = TRK_IV_1MIN;
  return s;
}

static inline bool trk_settings_valid(const TrackerSettings& s) {
  return s.interval <= TRK_IV_60MIN && s.alarm <= TRK_ALARM_HIGH && s.alarm_interval <= TRK_IV_60MIN;
}

struct TrackerRecord {
  uint32_t counter;
  uint8_t flags;      // TRK_R_*
  uint32_t age_s;     // beim Kodieren auf TRK_AGE_MAX begrenzt
  int32_t lat_e7, lon_e7;
  int16_t alt_m;
  uint8_t sats;
  uint8_t hdop_x10;
};

struct TrackerHead {
  uint8_t flags;      // TRK_F_*
  uint16_t settings_version;
  uint16_t batt_mv;
};

struct TrackerUplink {
  TrackerHead head;
  uint8_t n;
  TrackerRecord rec[TRK_MAX_RECORDS];
};

static inline void trk_put16(uint8_t* p, uint16_t v) { p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8); }
static inline void trk_put24(uint8_t* p, uint32_t v) { for (int i = 0; i < 3; i++) p[i] = (uint8_t)(v >> (8 * i)); }
static inline void trk_put32(uint8_t* p, uint32_t v) { for (int i = 0; i < 4; i++) p[i] = (uint8_t)(v >> (8 * i)); }
static inline uint16_t trk_get16(const uint8_t* p) { return (uint16_t)(p[0] | (p[1] << 8)); }
static inline uint32_t trk_get24(const uint8_t* p) { return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16); }
static inline uint32_t trk_get32(const uint8_t* p) {
  return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

static inline int trk_record_len(const TrackerRecord& r) {
  return TRK_REC_BASE_LEN + ((r.flags & TRK_R_FIX) ? TRK_REC_FIX_LEN : 0);
}

/**
 * Schreibt den Uplink nach out (mind. TRK_UP_MAX_LEN Byte): Kopf und so viele der Einträge rec[0..avail) in dieser
 * Reihenfolge, wie in TRK_UP_MAX_LEN passen. used erhält die Anzahl der aufgenommenen Einträge; gibt die Länge zurück.
 */
static inline int trk_encode_uplink(const uint8_t tag[TRK_TAG_LEN], const TrackerHead& h, const TrackerRecord* rec,
                                    int avail, uint8_t* out, int& used) {
  memcpy(out, tag, TRK_TAG_LEN);
  out[4] = TRK_UP_TYPE;
  out[5] = h.flags;
  trk_put16(&out[6], h.settings_version);
  int n = 8;
  if (h.flags & TRK_F_BATT) {
    trk_put16(&out[n], h.batt_mv);
    n += 2;
  }
  int count_at = n++;
  used = 0;
  while (used < avail && used < 255 && n + trk_record_len(rec[used]) <= TRK_UP_MAX_LEN) {
    const TrackerRecord& r = rec[used];
    trk_put32(&out[n], r.counter);
    out[n + 4] = r.flags;
    trk_put24(&out[n + 5], r.age_s > TRK_AGE_MAX ? TRK_AGE_MAX : r.age_s);
    n += TRK_REC_BASE_LEN;
    if (r.flags & TRK_R_FIX) {
      trk_put32(&out[n], (uint32_t)r.lat_e7);
      trk_put32(&out[n + 4], (uint32_t)r.lon_e7);
      trk_put16(&out[n + 8], (uint16_t)r.alt_m);
      out[n + 10] = r.sats;
      out[n + 11] = r.hdop_x10;
      n += TRK_REC_FIX_LEN;
    }
    used++;
  }
  out[count_at] = (uint8_t)used;
  return n;
}

/** Liest einen Uplink; false bei falschem Typ oder zu kurzen Daten. Länger ist erlaubt (MeshCore füllt auf 16 Byte auf). */
static inline bool trk_decode_uplink(const uint8_t* in, int len, TrackerUplink& u) {
  if (len < 9 || in[4] != TRK_UP_TYPE) return false;
  memset(&u, 0, sizeof(u));
  u.head.flags = in[5];
  u.head.settings_version = trk_get16(&in[6]);
  int n = 8;
  if (u.head.flags & TRK_F_BATT) {
    if (len < n + 3) return false;
    u.head.batt_mv = trk_get16(&in[n]);
    n += 2;
  }
  int count = in[n++];
  if (count > TRK_MAX_RECORDS) return false;
  for (int i = 0; i < count; i++) {
    if (len < n + TRK_REC_BASE_LEN) return false;
    TrackerRecord& r = u.rec[i];
    r.counter = trk_get32(&in[n]);
    r.flags = in[n + 4];
    r.age_s = trk_get24(&in[n + 5]);
    n += TRK_REC_BASE_LEN;
    if (r.flags & TRK_R_FIX) {
      if (len < n + TRK_REC_FIX_LEN) return false;
      r.lat_e7 = (int32_t)trk_get32(&in[n]);
      r.lon_e7 = (int32_t)trk_get32(&in[n + 4]);
      r.alt_m = (int16_t)trk_get16(&in[n + 8]);
      r.sats = in[n + 10];
      r.hdop_x10 = in[n + 11];
      n += TRK_REC_FIX_LEN;
    }
  }
  u.n = (uint8_t)count;
  return true;
}

static inline void trk_encode_settings(const uint8_t tag[TRK_TAG_LEN], const TrackerSettings& s, uint8_t out[TRK_DOWN_LEN]) {
  memcpy(out, tag, TRK_TAG_LEN);
  out[4] = TRK_DOWN_TYPE;
  trk_put16(&out[5], s.version);
  out[7] = s.interval;
  out[8] = s.alarm;
  out[9] = s.alarm_interval;
}

/** Liest einen Downlink. false bei falschem Typ, falscher Länge, fremdem Tag oder ungültigen Werten. */
static inline bool trk_decode_settings(const uint8_t* in, int len, const uint8_t tag[TRK_TAG_LEN], TrackerSettings& s) {
  if (len < TRK_DOWN_LEN || in[4] != TRK_DOWN_TYPE || memcmp(in, tag, TRK_TAG_LEN) != 0) return false;
  TrackerSettings t;
  t.version = trk_get16(&in[5]);
  t.interval = in[7];
  t.alarm = in[8];
  t.alarm_interval = in[9];
  if (!trk_settings_valid(t)) return false;
  s = t;
  return true;
}
