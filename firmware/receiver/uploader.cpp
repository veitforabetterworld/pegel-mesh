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
static bool station_ready[PEGEL_SENDER_COUNT];
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
  snprintf(buf, len, "wifi=%s queued=%d uploaded=%lu dropped=%lu last_http=%d",
           WiFi.status() == WL_CONNECTED ? "up" : "down", queued, (unsigned long)uploaded,
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

// Legt die Messstelle an bzw. aktualisiert sie; ohne Koordinaten (0/0) muss sie schon existieren.
static bool ensureStation(int i) {
  if (PEGEL_STATION_LAT[i] == 0.0f && PEGEL_STATION_LON[i] == 0.0f) return true;
  char body[256];
  snprintf(body, sizeof(body), "{\"name\":\"%s\",\"lat\":%.6f,\"lon\":%.6f}", PEGEL_STATION_NAMES[i],
           PEGEL_STATION_LAT[i], PEGEL_STATION_LON[i]);
  int code = request("PUT", String("/v1/ingest/stations/") + PEGEL_STATION_IDS[i], body);
  return code >= 200 && code < 300;
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

  if (!station_ready[sender]) {
    station_ready[sender] = ensureStation(sender);
    if (!station_ready[sender]) return false;
  }

  time_t now = time(nullptr);
  uint32_t now_ms = millis();
  String body = String("{\"station\":\"") + PEGEL_STATION_IDS[sender] + "\",\"values\":[";
  for (int k = 0; k < n; k++) {
    time_t measured = now - (time_t)((now_ms - batch[k].received_ms) / 1000) - batch[k].age_s;
    if (k) body += ",";
    body += "{\"t\":\"" + isoTime(measured) + "\",\"level_m\":" + String(batch[k].level_mm / 1000.0f, 3) + "}";
  }
  body += "]}";

  int code = request("POST", "/v1/ingest/measurements", body);
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

static void uploaderTask(void*) {
  WiFi.mode(WIFI_STA);
  WiFi.begin(PEGEL_WIFI_SSID, PEGEL_WIFI_PASS);
  configTime(0, 0, "pool.ntp.org", "time.google.com");
  for (;;) {
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
  if (strlen(PEGEL_WIFI_SSID) == 0 || strlen(PEGEL_API_URL) == 0) {
    Serial.println("uploader off: WLAN/API in secrets/receiver_wifi.h nicht eingetragen");
    return;
  }
  xTaskCreatePinnedToCore(uploaderTask, "uploader", 8192, nullptr, 1, nullptr, 0);
}
