#pragma once
// Pegelsonde über RS485 / Modbus RTU (wie water-level-sensor.ino): Funktion 3, ein Holding-Register,
// Wert in cm.
//
// PEGEL_BOARD=1, Trägerplatine pegel-sender v1 (hardware/pegel-sender):
//   D6/D7 I²C -> SC16IS740 (UART, steuert DE/RE selbst) -> MAX3485 -> Sonde A/B
//   D0        -> 12-V-Versorgung der Sonde (HIGH = an), vor der Messung PEGEL_SENSOR_WARMUP_MS Vorlauf
// PEGEL_BOARD=0, fliegender Aufbau mit RS485-Modul (Sonde dauerhaft versorgt):
//   D6 (TX, Serial1)  -> DI des RS485-Wandlers
//   D7 (RX, Serial1)  <- RO des RS485-Wandlers
//   D0                -> DE und RE (gebrückt): HIGH senden, LOW empfangen

#include <stdint.h>

#ifndef PEGEL_BOARD
  #define PEGEL_BOARD  1
#endif

#ifndef PEGEL_SENSOR_WARMUP_MS
  #if PEGEL_BOARD
    #define PEGEL_SENSOR_WARMUP_MS  2000   // Sonde nach dem Einschalten bis zum ersten gültigen Wert
  #else
    #define PEGEL_SENSOR_WARMUP_MS  0
  #endif
#endif

// Fehlercodes wie im alten Arduino-Code (-1, -2); sie gehen statt eines Messwerts über Funk.
#define LEVEL_OK              0
#define LEVEL_NO_RESPONSE     1   // keine oder fehlerhafte Antwort (Zeitüberschreitung, CRC)
#define LEVEL_OUT_OF_RANGE    2   // Wert außerhalb des Messbereichs
#define LEVEL_NO_INTERFACE    3   // RS485-Wandler (SC16IS740) antwortet nicht

void level_sensor_begin();
// Versorgung der Sonde; ohne Trägerplatine wirkungslos. level_sensor_read_mm schaltet danach selbst ab.
void level_sensor_power(bool on);
// Liest den Pegel in mm; gibt LEVEL_OK oder einen Fehlercode zurück.
uint8_t level_sensor_read_mm(uint16_t& level_mm);
