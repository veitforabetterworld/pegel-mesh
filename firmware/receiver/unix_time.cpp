#include "unix_time.h"

#include <Arduino.h>
#include <esp_timer.h>
#include <time.h>

static uint64_t sync_s = 0;
static int64_t sync_us = 0;
static bool synced = false;
static portMUX_TYPE mux = portMUX_INITIALIZER_UNLOCKED;   // Uploader stellt, Funk-Schleife liest

void unix_sync(uint64_t t) {
  if (t < UNIX_VALID_AFTER) return;
  if (!synced) {
    char iso[UNIX_ISO_LEN];
    unix_iso(t, iso);
    Serial.printf("time from server: %s\n", iso);
  }
  portENTER_CRITICAL(&mux);
  sync_s = t;
  sync_us = esp_timer_get_time();
  synced = true;
  portEXIT_CRITICAL(&mux);
}

uint64_t unix_now() {
  portENTER_CRITICAL(&mux);
  bool ok = synced;
  uint64_t s = sync_s;
  int64_t us = sync_us;
  portEXIT_CRITICAL(&mux);
  if (ok) return s + (uint64_t)((esp_timer_get_time() - us) / 1000000);
  // Ersatz bis zur ersten Server-Antwort: SNTP, als uint32 gelesen (bis 2106; SNTP selbst trägt bis 2104)
  uint32_t sntp = (uint32_t)time(nullptr);
  return sntp >= UNIX_VALID_AFTER ? sntp : 0;
}
