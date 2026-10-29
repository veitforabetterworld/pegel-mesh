#pragma once
// Leitet geprüfte Messwerte per WLAN an die hochwasserdienst-API weiter (POST /v1/ingest/measurements).
// Läuft als eigener FreeRTOS-Task, damit ein langsamer HTTP-Aufruf den Funkempfang nicht aufhält.

#include <stdint.h>

void uploader_begin();
// Eine Messung von Sender sender_idx, empfangen bei millis() = received_ms, age_s Sekunden vor dem Senden gemessen.
void uploader_push(uint8_t sender_idx, uint32_t received_ms, uint8_t age_s, uint16_t level_mm);
// Kurzer Status für die Statuszeile auf Serial.
void uploader_status(char* buf, int len);
