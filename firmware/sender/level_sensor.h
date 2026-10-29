#pragma once
// Pegelsonde über RS485 / Modbus RTU (wie water-level-sensor.ino): Funktion 3, ein Holding-Register,
// Wert in cm. Verdrahtung am XIAO nRF52840 (alle anderen Pins belegt das Wio-SX1262):
//   D6 (TX, Serial1)  -> DI des RS485-Wandlers
//   D7 (RX, Serial1)  <- RO des RS485-Wandlers
//   D0                -> DE und RE (gebrückt): HIGH senden, LOW empfangen

#include <stdint.h>

void level_sensor_begin();
// Liest den Pegel; false bei Zeitüberschreitung, CRC-Fehler oder Wert außerhalb des Messbereichs.
bool level_sensor_read_mm(uint16_t& level_mm);
