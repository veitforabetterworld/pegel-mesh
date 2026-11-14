#include "tracker_uplink.h"

#include <Arduino.h>
#include <Preferences.h>
#include <time.h>

#include "secrets_receiver.h"
#include "receiver_wifi.h"
#include "uploader.h"

#ifndef TRACKER_COUNT
  #define TRACKER_COUNT 0
#endif
#if TRACKER_COUNT > 0 && defined(TRACKER_API_URL)
  #define TRACKER_UPLINK 1
#else
  #define TRACKER_UPLINK 0
#endif

#define TRK_QUEUE_LEN       256   // Einträge; ein Nachreichen bringt bis zu 7 je REQ
#define TRK_BATCH_MAX       20
#define TRK_RETRY_MS        15000
#define TRK_POLL_MS         60000

#if TRACKER_COUNT > 0

static TrackerUpload queue[TRK_QUEUE_LEN];
static int queued = 0;
static uint32_t uploaded = 0, dropped = 0;
static TrackerSettings cache[TRACKER_COUNT];
static SemaphoreHandle_t lock;
static Preferences prefs;
static uint32_t retry_at = 0;
static uint32_t next_poll[TRACKER_COUNT];

static void key(char* k, uint8_t idx) { snprintf(k, 4, "s%u", idx); }

void tracker_uplink_begin() {
  lock = xSemaphoreCreateMutex();
  prefs.begin("trk", false);
  for (int i = 0; i < TRACKER_COUNT; i++) {
    char k[4];
    key(k, i);
    TrackerSettings s;
    if (prefs.getBytes(k, &s, sizeof(s)) == sizeof(s) && trk_settings_valid(s)) cache[i] = s;
    else cache[i] = trk_default_settings();
    next_poll[i] = 0;
  }
}

static void store(uint8_t idx, const TrackerSettings& s) {
  xSemaphoreTake(lock, portMAX_DELAY);
  bool changed = memcmp(&cache[idx], &s, sizeof(s)) != 0;
  cache[idx] = s;
  xSemaphoreGive(lock);
  if (changed) {
    char k[4];
    key(k, idx);
    prefs.putBytes(k, &s, sizeof(s));
    Serial.printf("tracker %s settings v%u: iv=%lus alarm=%u alarm_iv=%lus\n", TRACKER_NAMES[idx], s.version,
                  (unsigned long)trk_interval_s(s.interval), s.alarm, (unsigned long)trk_interval_s(s.alarm_interval));
  }
}

TrackerSettings tracker_uplink_settings(uint8_t idx) {
  xSemaphoreTake(lock, portMAX_DELAY);
  TrackerSettings s = cache[idx];
  xSemaphoreGive(lock);
  return s;
}

void tracker_uplink_set(uint8_t idx, const TrackerSettings& s) {
  if (idx < TRACKER_COUNT && trk_settings_valid(s)) store(idx, s);
}

void tracker_uplink_push(const TrackerUpload& u) {
  xSemaphoreTake(lock, portMAX_DELAY);
  if (queued == TRK_QUEUE_LEN) {
    memmove(&queue[0], &queue[1], sizeof(TrackerUpload) * (TRK_QUEUE_LEN - 1));
    queued--;
    dropped++;
  }
  queue[queued++] = u;
  xSemaphoreGive(lock);
}

void tracker_uplink_status(char* buf, int len) {
  snprintf(buf, len, "trk_queued=%d trk_uploaded=%lu trk_dropped=%lu", queued, (unsigned long)uploaded,
           (unsigned long)dropped);
}

#if TRACKER_UPLINK

static String isoTime(time_t t) {
  struct tm tm;
  gmtime_r(&t, &tm);
  char buf[24];
  strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%SZ", &tm);
  return buf;
}

// Liest eine ganze Zahl hinter "name": aus dem settings-Objekt der Antwort.
static bool jsonInt(const String& body, int from, const char* name, long& out) {
  String pat = String("\"") + name + "\"";
  int p = body.indexOf(pat, from);
  if (p < 0) return false;
  p = body.indexOf(':', p + pat.length());
  if (p < 0) return false;
  out = strtol(body.c_str() + p + 1, nullptr, 10);
  return true;
}

static void applyResponse(uint8_t idx, const String& body) {
  int s = body.indexOf("\"settings\"");
  if (s < 0) return;
  long version, iv, alarm, alarm_iv;
  if (!jsonInt(body, s, "version", version) || !jsonInt(body, s, "interval_s", iv) ||
      !jsonInt(body, s, "alarm_level", alarm) || !jsonInt(body, s, "alarm_interval_s", alarm_iv)) {
    Serial.printf("tracker %s: settings unreadable\n", TRACKER_NAMES[idx]);
    return;
  }
  TrackerSettings t;
  t.version = (uint16_t)version;
  t.interval = trk_interval_code((uint32_t)iv);
  t.alarm = (uint8_t)alarm;
  t.alarm_interval = trk_interval_code((uint32_t)alarm_iv);
  if (!trk_settings_valid(t)) {
    Serial.printf("tracker %s: settings out of range\n", TRACKER_NAMES[idx]);
    return;
  }
  store(idx, t);
}

static bool uploadBatch() {
  static TrackerUpload batch[TRK_BATCH_MAX];   // nur der Uploader-Task ruft das auf
  int n = 0;
  xSemaphoreTake(lock, portMAX_DELAY);
  int idx = queued > 0 ? queue[0].idx : -1;
  for (int k = 0; k < queued && n < TRK_BATCH_MAX; k++) {
    if (queue[k].idx == idx) batch[n++] = queue[k];
  }
  xSemaphoreGive(lock);
  if (n == 0) return false;

  const char* api_key = TRACKER_API_KEYS[idx];
  bool no_key = strlen(api_key) == 0;   // ohne Key: verwerfen statt ewig stauen
  if (!no_key) {
    time_t now = time(nullptr);
    uint32_t now_ms = millis();
    String body = "{\"reports\":[";
    for (int k = 0; k < n; k++) {
      const TrackerUpload& u = batch[k];
      const TrackerRecord& r = u.rec;
      // Zeitpunkt des Eintrags: Empfang der REQ minus Alter des Eintrags.
      time_t at = now - (time_t)((now_ms - u.received_ms) / 1000) - (time_t)r.age_s;
      String when = isoTime(at);
      char item[400];
      int w = snprintf(item, sizeof(item),
                       "%s{\"counter\":%lu,\"received_at\":\"%s\",\"alarm\":%s,\"motion\":%s,\"charging\":%s,\"usb\":%s,"
                       "\"settings_version\":%u,\"snr\":%.2f,\"rssi\":%.1f",
                       k ? "," : "", (unsigned long)r.counter, when.c_str(), (r.flags & TRK_R_ALARM) ? "true" : "false",
                       (r.flags & TRK_R_MOTION) ? "true" : "false", u.charging ? "true" : "false",
                       u.usb ? "true" : "false", u.settings_version, u.snr, u.rssi);
      if (r.flags & TRK_R_FIX) {
        w += snprintf(item + w, sizeof(item) - w,
                      ",\"position\":{\"observed_at\":\"%s\",\"lat\":%.7f,\"lon\":%.7f,\"alt_m\":%d,\"sats\":%u,\"hdop\":%.1f}",
                      when.c_str(), r.lat_e7 / 1e7, r.lon_e7 / 1e7, r.alt_m, r.sats, r.hdop_x10 / 10.0);
      }
      if (u.batt_mv) w += snprintf(item + w, sizeof(item) - w, ",\"battery_mv\":%u", u.batt_mv);
      snprintf(item + w, sizeof(item) - w, "}");
      body += item;
    }
    body += "]}";
    String resp;
    int code = uploader_http("POST", String(TRACKER_API_URL) + "/v1/tracker/reports", api_key, body, &resp);
    if (code < 200 || code >= 300) return false;
    applyResponse(idx, resp);
    next_poll[idx] = millis() + TRK_POLL_MS;
  }

  xSemaphoreTake(lock, portMAX_DELAY);
  int removed = 0, w = 0;
  for (int k = 0; k < queued; k++) {
    if (removed < n && queue[k].idx == idx) {
      removed++;
      continue;
    }
    queue[w++] = queue[k];
  }
  queued = w;
  if (no_key) dropped += n;
  else uploaded += n;
  xSemaphoreGive(lock);
  return true;
}

bool tracker_uplink_service() {
  if (strlen(TRACKER_API_URL) == 0) {
    xSemaphoreTake(lock, portMAX_DELAY);
    queued = 0;   // keine API eingetragen: die Meldungen stehen schon als JSON auf Serial
    xSemaphoreGive(lock);
    return false;
  }
  bool busy = false;
  if (queued > 0 && (int32_t)(millis() - retry_at) >= 0) {
    if (uploadBatch()) busy = queued > 0;
    else retry_at = millis() + TRK_RETRY_MS;
  }
  for (int i = 0; i < TRACKER_COUNT; i++) {
    if (strlen(TRACKER_API_KEYS[i]) == 0 || (int32_t)(millis() - next_poll[i]) < 0) continue;
    next_poll[i] = millis() + TRK_POLL_MS;
    String resp;
    int code = uploader_http("GET", String(TRACKER_API_URL) + "/v1/tracker/settings", TRACKER_API_KEYS[i], "", &resp);
    if (code >= 200 && code < 300) applyResponse(i, resp);
  }
  return busy;
}

#else   // ohne TRACKER_API_URL: nur Serial-Ausgabe, Einstellungen von Hand

bool tracker_uplink_service() {
  xSemaphoreTake(lock, portMAX_DELAY);
  queued = 0;   // nichts hochzuladen; die Meldungen stehen schon als JSON auf Serial
  xSemaphoreGive(lock);
  return false;
}

#endif

#else   // TRACKER_COUNT == 0

void tracker_uplink_begin() {}
void tracker_uplink_push(const TrackerUpload&) {}
TrackerSettings tracker_uplink_settings(uint8_t) { return trk_default_settings(); }
void tracker_uplink_set(uint8_t, const TrackerSettings&) {}
bool tracker_uplink_service() { return false; }
void tracker_uplink_status(char* buf, int len) { if (len) buf[0] = 0; }

#endif
