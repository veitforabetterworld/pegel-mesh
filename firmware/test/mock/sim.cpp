#include "Arduino.h"
#include "Wire.h"

namespace sim {
uint32_t now_ms = 0;
int pin_state[16] = {};
uint32_t vdd_mv = 3100;
int adc_reference = 0;
int adc_bits = 10;
void tick() { now_ms += 1; }
}

SerialStub Serial1;
TwoWire Wire;
