// Ersatz für variants/xiao_nrf54lm20a/target.cpp (in tracker.ini ausgeblendet).
//
// Der einzige Unterschied: das Funkmodul hängt an einer eigenen SPI-Instanz (SPIM22) statt am globalen SPI
// (SPIM21). Beim nRF54 teilen sich SPIM21 und UARTE21 dieselbe Hardware (SERIAL21), und UARTE21 ist Serial1,
// die UART zum GNSS-Modul. Mit SPI auf SPIM21 kommt vom GNSS nur Müll an.
// Instanz 22 ist frei: ihr TWIM22 wäre Wire an D4/D5, die hier Funk-NSS und RXEN sind.

#include <Arduino.h>
#include "target.h"
#include <helpers/ArduinoHelpers.h>

SPIClass LoRaSPI(NRF_SPIM22, P_LORA_MOSI, P_LORA_MISO, P_LORA_SCLK, PIN_SPI_SS);

XiaoNrf54Board board;

RADIO_CLASS radio = new Module(P_LORA_NSS, P_LORA_DIO_1, P_LORA_RESET, P_LORA_BUSY, LoRaSPI);

WRAPPER_CLASS radio_driver(radio, board);

VolatileRTCClock rtc_clock;

SensorManager sensors;

bool radio_init() {
  return radio.std_init(&LoRaSPI);
}

mesh::LocalIdentity radio_new_identity() {
  RadioNoiseListener rng(radio);
  return mesh::LocalIdentity(&rng);
}
