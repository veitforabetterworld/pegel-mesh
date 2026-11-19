#include "uploader.h"
#include "pegel_packet.h"

#include <Arduino.h>
#include <HTTPClient.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include "unix_time.h"

#include "secrets_receiver.h"
#include "receiver_wifi.h"
#include "tracker_uplink.h"

#define QUEUE_LEN        1024   // reicht für ~17 h von Sender A ohne Verbindung
#define BATCH_MAX        60
#define RETRY_DELAY_MS   30000
#define TIME_SYNC_RETRY_MS 60000

struct Pending {
  uint32_t received_ms;
  uint32_t age_s;
  uint16_t level_mm;
  uint8_t sender;
};

static Pending queue[QUEUE_LEN];
static int queued = 0;
static uint32_t dropped = 0;
static uint32_t uploaded = 0;
static int last_http = 0;
static SemaphoreHandle_t lock;

void uploader_push(uint8_t sender_idx, uint32_t received_ms, uint32_t age_s, uint16_t level_mm) {
  xSemaphoreTake(lock, portMAX_DELAY);
  if (queued == QUEUE_LEN) {   // voll: ältesten Wert verwerfen
    memmove(&queue[0], &queue[1], sizeof(Pending) * (QUEUE_LEN - 1));
    queued--;
    dropped++;
  }
  queue[queued++] = { received_ms, age_s, level_mm, sender_idx };
  xSemaphoreGive(lock);
}

void uploader_status(char* buf, int len) {
  // wl_status_t: 1 SSID not found, 4 connect failed (password), 6 disconnected.
  snprintf(buf, len, "wifi=%s(%d) queued=%d uploaded=%lu dropped=%lu last_http=%d",
           WiFi.status() == WL_CONNECTED ? "up" : "down", (int)WiFi.status(), queued, (unsigned long)uploaded,
           (unsigned long)dropped, last_http);
}

int uploader_http(const char* method, const String& url, const char* api_key, const String& body, String* response) {
  HTTPClient http;
  WiFiClient plain;
  WiFiClientSecure secure;
  if (url.startsWith("https://")) {
    if (strlen(PEGEL_API_CA) > 0) secure.setCACert(PEGEL_API_CA);
    else secure.setInsecure();
    http.begin(secure, url);
  } else {
    http.begin(plain, url);
  }
  http.setTimeout(15000);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-API-Key", api_key);
  static const char* keep[] = { "Date" };
  http.collectHeaders(keep, 1);
  int code = http.sendRequest(method, body);
  // Jede Antwort stellt die Uhr (unix_time.h), auch eine Fehlerantwort.
  uint64_t server_time;
  if (code > 0 && unix_parse_http_date(http.header("Date").c_str(), server_time)) unix_sync(server_time);
  if (code < 200 || code >= 300) {
    Serial.printf("HTTP %s %s -> %d %s\n", method, url.c_str(), code, http.getString().c_str());
  } else if (response) {
    *response = http.getString();
  }
  http.end();
  last_http = code;
  return code;
}

static int request(const char* method, const String& path, const String& body) {
  return uploader_http(method, String(PEGEL_API_URL) + path, PEGEL_API_KEY, body, nullptr);
}

// Legt die Messstelle privat an (der Key braucht stations.write); 409 = ID schon vergeben, dann besteht sie.
// Ohne Koordinaten (0/0) muss sie schon existieren, angelegt im Konto oder per API.
static bool createStation(int i) {
  if (PEGEL_STATION_LAT[i] == 0.0f && PEGEL_STATION_LON[i] == 0.0f) {
    Serial.printf("station %s fehlt, ohne Koordinaten in receiver_wifi.h wird sie nicht angelegt\n", PEGEL_STATION_IDS[i]);
    return false;
  }
  char body[256];
  snprintf(body, sizeof(body), "{\"slug\":\"%s\",\"name\":\"%s\",\"latitude\":%.6f,\"longitude\":%.6f}",
           PEGEL_STATION_IDS[i], PEGEL_STATION_NAMES[i], PEGEL_STATION_LAT[i], PEGEL_STATION_LON[i]);
  int code = request("POST", "/v1/stations", body);
  return (code >= 200 && code < 300) || code == 409;
}


// Schickt die ältesten Werte eines Senders; true, wenn die Schlange danach weiterverarbeitet werden kann.
static bool uploadBatch() {
  Pending batch[BATCH_MAX];
  int n = 0;
  xSemaphoreTake(lock, portMAX_DELAY);
  int sender = queued > 0 ? queue[0].sender : -1;
  for (int k = 0; k < queued && n < BATCH_MAX; k++) {
    if (queue[k].sender == sender) batch[n++] = queue[k];
  }
  xSemaphoreGive(lock);
  if (n == 0) return false;

  uint64_t now = unix_now();
  uint32_t now_ms = millis();
  String body = "{\"observations\":[";
  for (int k = 0; k < n; k++) {
    char measured[UNIX_ISO_LEN];
    unix_iso(unix_at(now, now_ms, batch[k].received_ms, batch[k].age_s), measured);
    if (k) body += ",";
    body += String("{\"observed_at\":\"") + measured + "\",";
    // Ab PEGEL_STATUS_BASE meldet der Sender einen Fehlercode statt eines Pegels.
    if (batch[k].level_mm >= PEGEL_STATUS_BASE) body += "\"status\":" + String(batch[k].level_mm - PEGEL_STATUS_BASE) + "}";
    else body += "\"water_level\":" + String(batch[k].level_mm / 1000.0f, 3) + "}";
  }
  body += "]}";

  String path = String("/v1/stations/") + PEGEL_STATION_IDS[sender] + "/observations";
  int code = request("POST", path, body);
  // 404: die Station gibt es (für diesen Key) noch nicht. Einmal anlegen und erneut senden.
  if (code == 404 && createStation(sender)) code = request("POST", path, body);
  if (code < 200 || code >= 300) return false;

  // Die gesendeten Einträge entfernen (in der Zwischenzeit können neue hinten dazugekommen sein).
  xSemaphoreTake(lock, portMAX_DELAY);
  int removed = 0, w = 0;
  for (int k = 0; k < queued; k++) {
    if (removed < n && queue[k].sender == sender) {
      removed++;
      continue;
    }
    queue[w++] = queue[k];
  }
  queued = w;
  uploaded += n;
  xSemaphoreGive(lock);
  return true;
}

/** Diagnosis while not connected: how many networks, the strongest signal, and whether ours is among them. */
static void logScan() {
  int found = WiFi.scanNetworks();
  int ours = -1, oursIgnoringCase = -1, best = -127;
  for (int i = 0; i < found; i++) {
    if (WiFi.RSSI(i) > best) best = WiFi.RSSI(i);
    if (WiFi.SSID(i) == PEGEL_WIFI_SSID) ours = i;
    if (WiFi.SSID(i).equalsIgnoreCase(PEGEL_WIFI_SSID)) oursIgnoringCase = i;
  }
  if (ours >= 0) {
    Serial.printf("wifi scan: %d networks, ours on channel %d with %d dBm\n", found, WiFi.channel(ours), WiFi.RSSI(ours));
  } else if (oursIgnoringCase >= 0) {
    Serial.printf("wifi scan: %d networks, ours only with other upper/lower case (%d dBm)\n", found, WiFi.RSSI(oursIgnoringCase));
  } else {
    Serial.printf("wifi scan: %d networks, strongest %d dBm, ours not among them\n", found, found > 0 ? best : 0);
  }
  WiFi.scanDelete();
}

// Holt die Uhrzeit vom Server, solange sie unbekannt ist (SNTP fehlt oder ist nach 2104 falsch).
static void syncTime() {
  const char* url = PEGEL_API_URL;
#if TRACKER_COUNT > 0 && defined(TRACKER_API_URL)
  if (strlen(url) == 0) url = TRACKER_API_URL;
#endif
  if (strlen(url) > 0) uploader_http("GET", String(url) + "/v1/health", "", "", nullptr);
}

static void uploaderTask(void*) {
  WiFi.mode(WIFI_STA);
  logScan();
  WiFi.begin(PEGEL_WIFI_SSID, PEGEL_WIFI_PASS);
  configTime(0, 0, "pool.ntp.org", "time.google.com");
  uint32_t next_scan = millis() + 60000;
  uint32_t pegel_retry_at = 0;
  uint32_t time_sync_at = 0;
  bool pegel_on = strlen(PEGEL_API_URL) > 0 && strlen(PEGEL_API_KEY) > 0;
  for (;;) {
    if (WiFi.status() != WL_CONNECTED && (int32_t)(millis() - next_scan) >= 0) {
      next_scan = millis() + 60000;
      logScan();
      WiFi.begin(PEGEL_WIFI_SSID, PEGEL_WIFI_PASS);
    }
    if (WiFi.status() != WL_CONNECTED) {
      vTaskDelay(pdMS_TO_TICKS(1000));
      continue;
    }
    if (unix_now() == 0) {
      if ((int32_t)(millis() - time_sync_at) >= 0) {
        time_sync_at = millis() + TIME_SYNC_RETRY_MS;
        syncTime();
      }
      vTaskDelay(pdMS_TO_TICKS(1000));
      continue;
    }
    // Tracker zuerst: ein Alarm soll nicht hinter einem Pegel-Rückstau warten.
    bool busy = tracker_uplink_service();
    if (pegel_on && queued > 0 && (int32_t)(millis() - pegel_retry_at) >= 0) {
      if (uploadBatch()) busy = true;
      else pegel_retry_at = millis() + RETRY_DELAY_MS;
    }
    if (!busy) vTaskDelay(pdMS_TO_TICKS(1000));
  }
}

void uploader_begin() {
  lock = xSemaphoreCreateMutex();
  tracker_uplink_begin();
  if (strlen(PEGEL_WIFI_SSID) == 0) {
    Serial.println("uploader off: WLAN in secrets/receiver_wifi.h nicht eingetragen");
    return;
  }
  xTaskCreatePinnedToCore(uploaderTask, "uploader", 8192, nullptr, 1, nullptr, 0);
}
