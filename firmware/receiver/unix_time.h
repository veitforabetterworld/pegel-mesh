#pragma once
// Uhrzeit des Empfängers, unabhängig von time_t und SNTP.
//
// Im Arduino-ESP32 2.x (ESP-IDF 4.4) ist time_t 32 Bit mit Vorzeichen (läuft 2038 über, als uint32 gelesen 2106),
// und lwIP deutet die NTP-Zeitstempel nur bis Februar 2104 richtig. Der Empfänger führt deshalb eine eigene Uhr:
// Sekunden seit 1970 als uint64, gestellt aus dem Date-Header jeder Antwort der API (uploader_http) und mit esp_timer
// (64 Bit, µs seit dem Start) fortgeschrieben. Bis zur ersten Antwort dient die SNTP-Zeit, solange sie plausibel ist.
// Die Funktionen ohne Zustand (Datum lesen und schreiben) liegen hier, damit sie sich am PC testen lassen.

#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define UNIX_VALID_AFTER  1700000000ULL   // davor gilt eine Uhrzeit als nicht gestellt
#define UNIX_ISO_LEN      32

// Sekunden seit 1970 (UTC), 0 solange keine gültige Zeit bekannt ist. Nur aus dem Uploader-Task.
uint64_t unix_now();
// Stellt die Uhr (Sekunden seit 1970) nach einer Server-Antwort. Nur aus dem Uploader-Task.
void unix_sync(uint64_t t);

// Tage seit 1970 zu einem Datum ab 1970 (Howard Hinnant, days_from_civil).
static inline uint64_t unix_days_from_civil(uint64_t y, unsigned m, unsigned d) {
  if (m <= 2) y--;
  uint64_t era = y / 400;
  uint64_t yoe = y - era * 400;
  uint64_t doy = (153 * (m > 2 ? m - 3 : m + 9) + 2) / 5 + d - 1;
  uint64_t doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
  return era * 146097 + doe - 719468;
}

/** Sekunden seit 1970 (UTC) als "YYYY-MM-DDTHH:MM:SSZ" nach out. */
static inline void unix_iso(uint64_t t, char out[UNIX_ISO_LEN]) {
  uint64_t days = t / 86400, secs = t % 86400;
  // Datum aus der Tageszahl (Howard Hinnant, civil_from_days)
  uint64_t z = days + 719468;
  uint64_t era = z / 146097;
  uint64_t doe = z - era * 146097;
  uint64_t yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
  uint64_t y = yoe + era * 400;
  uint64_t doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
  uint64_t mp = (5 * doy + 2) / 153;
  unsigned d = (unsigned)(doy - (153 * mp + 2) / 5 + 1);
  unsigned m = (unsigned)(mp < 10 ? mp + 3 : mp - 9);
  if (m <= 2) y++;
  snprintf(out, UNIX_ISO_LEN, "%04llu-%02u-%02uT%02u:%02u:%02uZ", (unsigned long long)y, m, d,
           (unsigned)(secs / 3600), (unsigned)(secs / 60 % 60), (unsigned)(secs % 60));
}

/** HTTP-Datum (RFC 9110, "Sun, 06 Nov 1994 08:49:37 GMT") zu Sekunden seit 1970; false, wenn es nicht passt. */
static inline bool unix_parse_http_date(const char* s, uint64_t& t) {
  static const char* const MONTHS = "JanFebMarAprMayJunJulAugSepOctNovDec";
  const char* p = strchr(s, ',');
  if (!p) return false;
  unsigned d, hh, mm, ss;
  unsigned long long y;
  char mon[4] = { 0 }, zone[4] = { 0 };
  if (sscanf(p + 1, " %2u %3c %llu %2u:%2u:%2u %3c", &d, mon, &y, &hh, &mm, &ss, zone) != 7) return false;
  if (strcmp(zone, "GMT") != 0) return false;
  const char* found = strstr(MONTHS, mon);
  if (!found || (found - MONTHS) % 3 != 0) return false;
  unsigned m = (unsigned)(found - MONTHS) / 3 + 1;
  if (y < 1970 || y > 9999 || d < 1 || d > 31 || hh > 23 || mm > 59 || ss > 60) return false;
  t = unix_days_from_civil(y, m, d) * 86400 + hh * 3600UL + mm * 60UL + ss;
  return true;
}

/** Zeitpunkt age_s vor dem Empfang bei millis() = received_ms; now und now_ms gehören zusammen. */
static inline uint64_t unix_at(uint64_t now, uint32_t now_ms, uint32_t received_ms, uint32_t age_s) {
  uint64_t back = (uint64_t)((now_ms - received_ms) / 1000) + age_s;
  return back < now ? now - back : 0;
}
