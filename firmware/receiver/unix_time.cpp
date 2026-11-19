#include "unix_time.h"

#include <Arduino.h>
#include <esp_timer.h>
#include <time.h>

static uint64_t sync_s = 0;
static int64_t sync_us = 0;
static bool synced = false;

void unix_sync(uint64_t t) {
  if (t < UNIX_VALID_AFTER) return;
  if (!synced) {
    char iso[UNIX_ISO_LEN];
    unix_iso(t, iso);
    Serial.printf("time from server: %s\n", iso);
  }
  sync_s = t;
  sync_us = esp_timer_get_time();
  synced = true;
}

uint64_t unix_now() {
  if (synced) return sync_s + (uint64_t)((esp_timer_get_time() - sync_us) / 1000000);
  // Ersatz bis zur ersten Server-Antwort: SNTP, als uint32 gelesen (bis 2106; SNTP selbst trägt bis 2104)
  uint32_t sntp = (uint32_t)time(nullptr);
  return sntp >= UNIX_VALID_AFTER ? sntp : 0;
}
