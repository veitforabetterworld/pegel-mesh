#include <Arduino.h>
#include "gnss.h"

static NmeaParser parser;
static bool powered = false;
static bool alive = false;
static uint32_t bytes = 0;

uint32_t gnss_bytes() { return bytes; }

void gnss_set_pin_raw(bool high) { digitalWrite(GNSS_STANDBY_PIN, high ? HIGH : LOW); }

// Schickt "$<body>*HH\r\n" mit berechneter Prüfsumme.
static void pcas(const char* body) {
  uint8_t sum = 0;
  for (const char* p = body; *p; p++) sum ^= (uint8_t)*p;
  char tail[8];
  snprintf(tail, sizeof(tail), "*%02X\r\n", sum);
  Serial1.write('$');
  Serial1.write((const uint8_t*)body, strlen(body));
  Serial1.write((const uint8_t*)tail, strlen(tail));
}

void gnss_begin() {
  pinMode(GNSS_STANDBY_PIN, OUTPUT);
  digitalWrite(GNSS_STANDBY_PIN, LOW);
  Serial1.begin(9600);
}

void gnss_power(bool on) {
  if (on == powered) return;
  powered = on;
  digitalWrite(GNSS_STANDBY_PIN, on ? HIGH : LOW);
  if (on) {
    alive = false;
    delay(50);
    pcas("PCAS04,7");                            // GPS + BeiDou + GLONASS
    pcas("PCAS03,1,0,0,0,0,0,0,0,0,0,,,0,0");    // nur GGA, 1 Hz
  }
}

bool gnss_is_on() { return powered; }

bool gnss_alive() { return alive; }

bool gnss_poll(NmeaFix& fix) {
  bool got = false;
  while (Serial1.available() > 0) {
    bytes++;
    if (parser.feed((char)Serial1.read(), fix)) {
      alive = true;
      got = true;
    }
  }
  return got;
}
