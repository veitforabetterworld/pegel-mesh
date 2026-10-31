#include "level_sensor.h"
#include "pegel_packet.h"

#include <Arduino.h>
#include <Wire.h>

#ifndef PEGEL_SENSOR_PIN
  #define PEGEL_SENSOR_PIN  D0   // Trägerplatine: Sondenversorgung, fliegender Aufbau: DE/RE
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

static bool bus_ok = false;

static uint16_t crc16(const uint8_t* data, int len) {
  uint16_t crc = 0xFFFF;
  for (int i = 0; i < len; i++) {
    crc ^= data[i];
    for (int bit = 0; bit < 8; bit++) crc = (crc & 1) ? (crc >> 1) ^ 0xA001 : crc >> 1;
  }
  return crc;
}

// RS485 über Serial1 (TX D6, RX D7, 8N1). MeshCore legt I2C auf D6/D7 (RTC-Suche in radio_init); danach
// gehören die Pins der UART. Trägerplatine: der SP3485 schaltet die Richtung selbst (TX low → Treiber an) und
// ist nur mit der Sonde versorgt, die UART läuft deshalb nur, solange die Sonde an ist. Fliegender Aufbau:
// DE/RE an D0, Sonde dauerhaft versorgt.
static bool busBegin() {
  Wire.end();
#if !PEGEL_BOARD
  digitalWrite(PEGEL_SENSOR_PIN, LOW);
  Serial1.begin(PEGEL_MODBUS_BAUD);
#endif
  return true;
}
static void busFlushRx() {
  while (Serial1.available()) Serial1.read();
}
static void busSend(const uint8_t* data, int len) {
#if !PEGEL_BOARD
  digitalWrite(PEGEL_SENSOR_PIN, HIGH);
#endif
  Serial1.write(data, len);
  Serial1.flush();
#if !PEGEL_BOARD
  digitalWrite(PEGEL_SENSOR_PIN, LOW);
#endif
}
static int busRead() { return Serial1.available() ? Serial1.read() : -1; }

void level_sensor_begin() {
  pinMode(PEGEL_SENSOR_PIN, OUTPUT);
  digitalWrite(PEGEL_SENSOR_PIN, LOW);
  bus_ok = busBegin();
}

void level_sensor_power(bool on) {
#if PEGEL_BOARD
  digitalWrite(PEGEL_SENSOR_PIN, on ? HIGH : LOW);
  // UART nur bei versorgtem SP3485: sonst speisten TX/RX ihn über seine Schutzdioden
  if (on) Serial1.begin(PEGEL_MODBUS_BAUD);
  else Serial1.end();
#endif
}

/** Modbus RTU, Funktion 3: ein Holding-Register lesen. */
static bool readRegister(uint16_t reg, uint16_t& value) {
  uint8_t req[8] = { PEGEL_MODBUS_ADDR, 0x03, (uint8_t)(reg >> 8), (uint8_t)reg, 0x00, 0x01, 0, 0 };
  uint16_t crc = crc16(req, 6);
  req[6] = (uint8_t)crc;
  req[7] = (uint8_t)(crc >> 8);

  busFlushRx();   // Reste einer früheren Antwort verwerfen
  busSend(req, sizeof(req));

  // Antwort: Adresse, 0x03, Bytezahl 2, Wert (big endian), CRC (low, high)
  uint8_t resp[7];
  int n = 0;
  uint32_t start = millis();
  while (n < (int)sizeof(resp) && millis() - start < RESPONSE_TIMEOUT_MS) {
    int b = busRead();
    if (b >= 0) resp[n++] = (uint8_t)b;
  }
  if (n < (int)sizeof(resp)) return false;
  if (resp[0] != PEGEL_MODBUS_ADDR || resp[1] != 0x03 || resp[2] != 2) return false;
  if (crc16(resp, 5) != (uint16_t)(resp[5] | (resp[6] << 8))) return false;
  value = (uint16_t)(resp[3] << 8) | resp[4];
  return true;
}

static uint8_t measure(uint16_t& level_mm) {
  if (!bus_ok && !(bus_ok = busBegin())) return LEVEL_NO_INTERFACE;
  uint16_t cm;
  if (!readRegister(PEGEL_LEVEL_REGISTER, cm)) return LEVEL_NO_RESPONSE;
  if (cm > PEGEL_LEVEL_MAX_CM) return LEVEL_OUT_OF_RANGE;
  long mm = (long)cm * 10 + PEGEL_SENSOR_OFFSET_MM;
  level_mm = (uint16_t)constrain(mm, 0L, (long)PEGEL_LEVEL_MAX_MM);
  return LEVEL_OK;
}

uint8_t level_sensor_read_mm(uint16_t& level_mm) {
  uint8_t status = measure(level_mm);
  level_sensor_power(false);
  return status;
}
