#pragma once
// Arduino-Nachbildung für den PC-Test: simulierte Zeit, Pins, min/max.
#include <stdint.h>
#include <stddef.h>
#include <algorithm>

#define HIGH 1
#define LOW 0
#define OUTPUT 1
#define INPUT 0
#define D0 0

namespace sim {
extern uint32_t now_ms;
extern int pin_state[16];
void tick();   // jede Zeitabfrage lässt 1 ms vergehen: Warte-Schleifen enden immer
}

inline uint32_t millis() { sim::tick(); return sim::now_ms; }
inline void delay(uint32_t ms) { sim::now_ms += ms; }
inline void pinMode(int, int) {}
inline void digitalWrite(int pin, int v) { sim::pin_state[pin] = v; }
using std::min;
using std::max;
template <class T> T constrain(T x, T a, T b) { return x < a ? a : (x > b ? b : x); }

struct SerialStub {
  void begin(unsigned long) {}
  int available() { return 0; }
  int read() { return -1; }
  size_t write(const uint8_t*, size_t n) { return n; }
  void flush() {}
};
extern SerialStub Serial1;
