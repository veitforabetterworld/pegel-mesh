#pragma once
// Leitet geprüfte Messwerte per WLAN an die hochwasserdienst-API weiter (POST /v1/ingest/measurements).
// Läuft als eigener FreeRTOS-Task, damit ein langsamer HTTP-Aufruf den Funkempfang nicht aufhält.

#include <stdint.h>

void uploader_begin();
// Eine Messung von Sender sender_idx, empfangen bei millis() = received_ms, age_s Sekunden vor dem Senden gemessen.
void uploader_push(uint8_t sender_idx, uint32_t received_ms, uint8_t age_s, uint16_t level_mm);
// Kurzer Status für die Statuszeile auf Serial.
void uploader_status(char* buf, int len);

#include <Arduino.h>
// HTTP-Aufruf für die Uploader (nur aus dem Uploader-Task). Schickt api_key als X-API-Key; die Antwort landet in
// response, wenn nicht nullptr. Gibt den HTTP-Status zurück (negativ bei Verbindungsfehlern).
int uploader_http(const char* method, const String& url, const char* api_key, const String& body, String* response);
