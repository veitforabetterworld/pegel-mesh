#include "uploader.h"

#include <Arduino.h>
#include <HTTPClient.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <time.h>

#include "secrets_receiver.h"
#include "receiver_wifi.h"

#define QUEUE_LEN        1024   // reicht für ~17 h von Sender A ohne Verbindung
#define BATCH_MAX        60
#define RETRY_DELAY_MS   30000
#define TIME_VALID_AFTER 1700000000L   // vor NTP-Sync steht die Uhr bei 1970

struct Pending {
  uint32_t received_ms;
  uint16_t level_mm;
  uint8_t sender;
  uint8_t age_s;
};

static Pending queue[QUEUE_LEN];
static int queued = 0;
static uint32_t dropped = 0;
static uint32_t uploaded = 0;
static int last_http = 0;
static SemaphoreHandle_t lock;

void uploader_push(uint8_t sender_idx, uint32_t received_ms, uint8_t age_s, uint16_t level_mm) {
  xSemaphoreTake(lock, portMAX_DELAY);
  if (queued == QUEUE_LEN) {   // voll: ältesten Wert verwerfen
    memmove(&queue[0], &queue[1], sizeof(Pending) * (QUEUE_LEN - 1));
    queued--;
    dropped++;
  }
  queue[queued++] = { received_ms, level_mm, sender_idx, age_s };
  xSemaphoreGive(lock);
}

void uploader_status(char* buf, int len) {
  // wl_status_t: 1 SSID not found, 4 connect failed (password), 6 disconnected.
  snprintf(buf, len, "wifi=%s(%d) queued=%d uploaded=%lu dropped=%lu last_http=%d",
           WiFi.status() == WL_CONNECTED ? "up" : "down", (int)WiFi.status(), queued, (unsigned long)uploaded,
           (unsigned long)dropped, last_http);
}

static int request(const char* method, const String& path, const String& body) {
  String url = String(PEGEL_API_URL) + path;
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
  http.addHeader("X-API-Key", PEGEL_API_KEY);
  int code = http.sendRequest(method, body);
  if (code < 200 || code >= 300) {
    Serial.printf("HTTP %s %s -> %d %s\n", method, path.c_str(), code, http.getString().c_str());
  }
  http.end();
  last_http = code;
  return code;
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

static String isoTime(time_t t) {
  struct tm tm;
  gmtime_r(&t, &tm);
  char buf[24];
  strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%SZ", &tm);
  return buf;
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

  time_t now = time(nullptr);
  uint32_t now_ms = millis();
  String body = "{\"observations\":[";
  for (int k = 0; k < n; k++) {
    time_t measured = now - (time_t)((now_ms - batch[k].received_ms) / 1000) - batch[k].age_s;
    if (k) body += ",";
    body += "{\"observed_at\":\"" + isoTime(measured) + "\",\"water_level\":" + String(batch[k].level_mm / 1000.0f, 3) + "}";
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

static void uploaderTask(void*) {
  WiFi.mode(WIFI_STA);
  logScan();
  WiFi.begin(PEGEL_WIFI_SSID, PEGEL_WIFI_PASS);
  configTime(0, 0, "pool.ntp.org", "time.google.com");
  uint32_t next_scan = millis() + 60000;
  for (;;) {
    if (WiFi.status() != WL_CONNECTED && (int32_t)(millis() - next_scan) >= 0) {
      next_scan = millis() + 60000;
      logScan();
      WiFi.begin(PEGEL_WIFI_SSID, PEGEL_WIFI_PASS);
    }
    if (WiFi.status() != WL_CONNECTED || time(nullptr) < TIME_VALID_AFTER) {
      vTaskDelay(pdMS_TO_TICKS(1000));
      continue;
    }
    if (queued == 0) {
      vTaskDelay(pdMS_TO_TICKS(1000));
      continue;
    }
    if (!uploadBatch()) vTaskDelay(pdMS_TO_TICKS(RETRY_DELAY_MS));
  }
}

void uploader_begin() {
  lock = xSemaphoreCreateMutex();
  if (strlen(PEGEL_WIFI_SSID) == 0 || strlen(PEGEL_API_URL) == 0 || strlen(PEGEL_API_KEY) == 0) {
    Serial.println("uploader off: WLAN/API in secrets/receiver_wifi.h nicht eingetragen");
    return;
  }
  xTaskCreatePinnedToCore(uploaderTask, "uploader", 8192, nullptr, 1, nullptr, 0);
}
