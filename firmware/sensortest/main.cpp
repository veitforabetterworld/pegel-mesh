// Stromtest der Pegelsonde auf der Trägerplatine: Sonde dauerhaft an, Modbus-Abfragen ohne Pause.
//
// Kein Funk (der SX1262 bleibt nach dem Einschalten unberührt im Standby), keine Messpausen. Über USB-Serial:
//   o   Sonde aus (Grundlast der Platine messen)
//   e   Sonde wieder an
// Ausgabe einmal je Sekunde: Abfragen, gültige Antworten und der letzte Pegel.
//
//   python3 tools/pio.py run -e pegel_sensor_test -t upload --upload-port COM14

#include <Arduino.h>

#define SENSOR_PIN     D0     // 12 V für Sonde und SP3485 (HIGH = an)
#define MODBUS_BAUD    9600
#define MODBUS_ADDR    0x01
#define LEVEL_REGISTER 4
#define TIMEOUT_MS     300

static bool sensor_on = false;
static uint32_t requests = 0, answers = 0;
static uint16_t last_cm = 0;

static uint16_t crc16(const uint8_t* data, int len) {
  uint16_t crc = 0xFFFF;
  for (int i = 0; i < len; i++) {
    crc ^= data[i];
    for (int bit = 0; bit < 8; bit++) crc = (crc & 1) ? (crc >> 1) ^ 0xA001 : crc >> 1;
  }
  return crc;
}

static void power(bool on) {
  sensor_on = on;
  digitalWrite(SENSOR_PIN, on ? HIGH : LOW);
  // UART nur bei versorgtem SP3485, sonst speisten TX/RX ihn über seine Schutzdioden
  if (on) Serial1.begin(MODBUS_BAUD);
  else Serial1.end();
  Serial.printf("sensor %s\n", on ? "on" : "off");
}

static bool readLevel(uint16_t& cm) {
  uint8_t req[8] = { MODBUS_ADDR, 0x03, 0x00, LEVEL_REGISTER, 0x00, 0x01, 0, 0 };
  uint16_t crc = crc16(req, 6);
  req[6] = (uint8_t)crc;
  req[7] = (uint8_t)(crc >> 8);
  while (Serial1.available()) Serial1.read();
  Serial1.write(req, sizeof(req));
  Serial1.flush();
  uint8_t resp[7];
  int n = 0;
  uint32_t start = millis();
  while (n < (int)sizeof(resp) && millis() - start < TIMEOUT_MS) {
    int b = Serial1.available() ? Serial1.read() : -1;
    if (b >= 0) resp[n++] = (uint8_t)b;
  }
  if (n < (int)sizeof(resp) || resp[0] != MODBUS_ADDR || resp[1] != 0x03 || resp[2] != 2) return false;
  if (crc16(resp, 5) != (uint16_t)(resp[5] | (resp[6] << 8))) return false;
  cm = (uint16_t)(resp[3] << 8) | resp[4];
  return true;
}

void setup() {
  Serial.begin(115200);
  pinMode(SENSOR_PIN, OUTPUT);
  delay(2000);
  Serial.println("sensor current test: o = sensor off, e = sensor on");
  power(true);
}

void loop() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == 'o' && sensor_on) power(false);
    if (c == 'e' && !sensor_on) power(true);
  }
  if (sensor_on) {
    delay(10);   // Modbus-Pause zwischen zwei Rahmen (mind. 3,5 Zeichen = 4 ms bei 9600 Baud)
    requests++;
    uint16_t cm;
    if (readLevel(cm)) {
      answers++;
      last_cm = cm;
    }
  }
  static uint32_t next_print = 0;
  if ((int32_t)(millis() - next_print) >= 0) {
    next_print = millis() + 1000;
    Serial.printf("sensor=%s requests=%lu answers=%lu level=%u cm\n", sensor_on ? "on" : "off",
                  (unsigned long)requests, (unsigned long)answers, last_cm);
  }
}
