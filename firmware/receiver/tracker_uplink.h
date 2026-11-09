#pragma once
// Tracker-Einträge an die Tracker-API (tracker.plenivo.de) weiterleiten und deren Einstellungen vorhalten.
//
// Jeder Tracker hat einen eigenen API-Key (TRACKER_API_KEYS in receiver_wifi.h); der Key bestimmt auf dem Server,
// welcher Tracker gemeint ist.
//
//   POST {TRACKER_API_URL}/v1/tracker/reports   {"reports":[...]}        -> 200 {"settings":{...}}
//   GET  {TRACKER_API_URL}/v1/tracker/settings                            -> 200 {"settings":{...}}
//   settings: {"version":3,"interval_s":900,"alarm_level":2,"alarm_interval_s":60}
//
// Ein Eintrag wird ein report; received_at ist der Zeitpunkt des Eintrags (Empfang minus dessen Alter), bei einem
// Eintrag mit Position zugleich observed_at. Nachgereichte Einträge kommen also mit ihrer echten Zeit an.
//
// Die Einstellungen werden minütlich abgefragt und im Flash gehalten, damit der Empfänger sie dem Tracker sofort
// in der Antwort auf dessen nächste REQ mitgeben kann.

#include <stdint.h>
#include "tracker_packet.h"

struct TrackerUpload {
  TrackerRecord rec;
  uint32_t received_ms;   // millis() beim Empfang der REQ
  uint16_t settings_version;
  uint16_t batt_mv;       // 0 = nicht dabei
  bool charging, usb;
  float snr, rssi;
  uint8_t idx;
};

void tracker_uplink_begin();
void tracker_uplink_push(const TrackerUpload& u);
TrackerSettings tracker_uplink_settings(uint8_t idx);
/** Einstellungen von Hand setzen (Test über Serial, solange es die API noch nicht gibt). */
void tracker_uplink_set(uint8_t idx, const TrackerSettings& s);
/** Aus dem Uploader-Task: lädt hoch und fragt Einstellungen ab. true, wenn noch Arbeit ansteht. */
bool tracker_uplink_service();
void tracker_uplink_status(char* buf, int len);
