#include "level_sensor.h"
#include "pegel_packet.h"

#include <Arduino.h>
#include <Wire.h>

#ifndef PEGEL_RS485_DE_PIN
  #define PEGEL_RS485_DE_PIN  D0
#endif
#ifndef PEGEL_MODBUS_BAUD
  #define PEGEL_MODBUS_BAUD  9600
#endif
#ifndef PEGEL_MODBUS_ADDR
  #define PEGEL_MODBUS_ADDR  0x01   // manche Sonden haben 0x1A
#endif
#ifndef PEGEL_LEVEL_REGISTER
  #define PEGEL_LEVEL_REGISTER  4
#endif
#ifndef PEGEL_LEVEL_MAX_CM
  #define PEGEL_LEVEL_MAX_CM  400   // Messbereich der Sonde; darüber gilt der Wert als Lesefehler
#endif
#ifndef PEGEL_SENSOR_OFFSET_MM
  #define PEGEL_SENSOR_OFFSET_MM  0  // Höhe der Sonde über dem Pegelnullpunkt
#endif

#define RESPONSE_TIMEOUT_MS  300

static uint16_t crc16(const uint8_t* data, int len) {
  uint16_t crc = 0xFFFF;
  for (int i = 0; i < len; i++) {
    crc ^= data[i];
    for (int bit = 0; bit < 8; bit++) crc = (crc & 1) ? (crc >> 1) ^ 0xA001 : crc >> 1;
  }
  return crc;
}

void level_sensor_begin() {
  // MeshCore legt I2C auf D6/D7 (RTC-Suche in radio_init); der Sender braucht I2C nicht, die Pins gehören der UART.
  Wire.end();
  pinMode(PEGEL_RS485_DE_PIN, OUTPUT);
  digitalWrite(PEGEL_RS485_DE_PIN, LOW);
  Serial1.begin(PEGEL_MODBUS_BAUD);   // 8N1, TX D6, RX D7
}

/** Modbus RTU, Funktion 3: ein Holding-Register lesen. */
static bool readRegister(uint16_t reg, uint16_t& value) {
  uint8_t req[8] = { PEGEL_MODBUS_ADDR, 0x03, (uint8_t)(reg >> 8), (uint8_t)reg, 0x00, 0x01, 0, 0 };
  uint16_t crc = crc16(req, 6);
  req[6] = (uint8_t)crc;
  req[7] = (uint8_t)(crc >> 8);

  while (Serial1.available()) Serial1.read();   // Reste einer früheren Antwort verwerfen
  digitalWrite(PEGEL_RS485_DE_PIN, HIGH);
  Serial1.write(req, sizeof(req));
  Serial1.flush();
  digitalWrite(PEGEL_RS485_DE_PIN, LOW);

  // Antwort: Adresse, 0x03, Bytezahl 2, Wert (big endian), CRC (low, high)
  uint8_t resp[7];
  int n = 0;
  uint32_t start = millis();
  while (n < (int)sizeof(resp) && millis() - start < RESPONSE_TIMEOUT_MS) {
    if (Serial1.available()) resp[n++] = (uint8_t)Serial1.read();
  }
  if (n < (int)sizeof(resp)) return false;
  if (resp[0] != PEGEL_MODBUS_ADDR || resp[1] != 0x03 || resp[2] != 2) return false;
  if (crc16(resp, 5) != (uint16_t)(resp[5] | (resp[6] << 8))) return false;
  value = (uint16_t)(resp[3] << 8) | resp[4];
  return true;
}

uint8_t level_sensor_read_mm(uint16_t& level_mm) {
  uint16_t cm;
  if (!readRegister(PEGEL_LEVEL_REGISTER, cm)) return LEVEL_NO_RESPONSE;
  if (cm > PEGEL_LEVEL_MAX_CM) return LEVEL_OUT_OF_RANGE;
  long mm = (long)cm * 10 + PEGEL_SENSOR_OFFSET_MM;
  level_mm = (uint16_t)constrain(mm, 0L, (long)PEGEL_LEVEL_MAX_MM);
  return LEVEL_OK;
}
