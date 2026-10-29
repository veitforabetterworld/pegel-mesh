#pragma once
// Pegelsonde über RS485 / Modbus RTU (wie water-level-sensor.ino): Funktion 3, ein Holding-Register,
// Wert in cm. Verdrahtung am XIAO nRF52840 (alle anderen Pins belegt das Wio-SX1262):
//   D6 (TX, Serial1)  -> DI des RS485-Wandlers
//   D7 (RX, Serial1)  <- RO des RS485-Wandlers
//   D0                -> DE und RE (gebrückt): HIGH senden, LOW empfangen

#include <stdint.h>

// Fehlercodes wie im alten Arduino-Code (-1, -2); sie gehen statt eines Messwerts über Funk.
#define LEVEL_OK              0
#define LEVEL_NO_RESPONSE     1   // keine oder fehlerhafte Antwort (Zeitüberschreitung, CRC)
#define LEVEL_OUT_OF_RANGE    2   // Wert außerhalb des Messbereichs

void level_sensor_begin();
// Liest den Pegel in mm; gibt LEVEL_OK oder einen Fehlercode zurück.
uint8_t level_sensor_read_mm(uint16_t& level_mm);
