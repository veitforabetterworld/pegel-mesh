#pragma once
// Uhrzeit für die Uploader, über das Jahr 2038 hinaus.
//
// Der Empfänger läuft auf Arduino-ESP32 2.x (ESP-IDF 4.4): time_t ist dort 32 Bit mit Vorzeichen und wird am
// 19.01.2038 negativ. Die Bits bleiben richtig: als uint32 gelesen stimmt die Zeit bis 2106. Deshalb rechnen die
// Uploader nur mit unix_now() und formatieren selbst, statt gmtime/strftime mit time_t zu benutzen.
// Die SNTP-Zeit selbst trägt nur bis Februar 2104 (NTP-Epoche in lwIP), siehe README "Langzeitbetrieb".

#include <Arduino.h>
#include <time.h>

static inline uint32_t unix_now() { return (uint32_t)time(nullptr); }

/** Sekunden seit 1970 (UTC) als "YYYY-MM-DDTHH:MM:SSZ". */
static inline String unix_iso(uint32_t t) {
  uint32_t days = t / 86400, secs = t % 86400;
  // Kalender aus der Tageszahl (Howard Hinnant, civil_from_days), nur für Tage ab 1970
  uint32_t z = days + 719468;
  uint32_t era = z / 146097;
  uint32_t doe = z - era * 146097;
  uint32_t yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
  uint32_t y = yoe + era * 400;
  uint32_t doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
  uint32_t mp = (5 * doy + 2) / 153;
  uint32_t d = doy - (153 * mp + 2) / 5 + 1;
  uint32_t m = mp < 10 ? mp + 3 : mp - 9;
  if (m <= 2) y++;
  char buf[24];
  snprintf(buf, sizeof(buf), "%04lu-%02lu-%02luT%02lu:%02lu:%02luZ", (unsigned long)y, (unsigned long)m,
           (unsigned long)d, (unsigned long)(secs / 3600), (unsigned long)(secs / 60 % 60), (unsigned long)(secs % 60));
  return buf;
}

/** Zeitpunkt age_s vor dem Empfang bei millis() = received_ms; now und now_ms gehören zusammen. */
static inline uint32_t unix_at(uint32_t now, uint32_t now_ms, uint32_t received_ms, uint32_t age_s) {
  uint32_t back = (now_ms - received_ms) / 1000 + age_s;
  return back < now ? now - back : 0;
}
