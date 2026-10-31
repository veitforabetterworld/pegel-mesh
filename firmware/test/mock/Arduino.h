#pragma once
// Arduino-Nachbildung für den PC-Test: simulierte Zeit, Pins, Serial1 am RS485-Bus, SAADC an VDD.
#include <stdint.h>
#include <stddef.h>
#include <algorithm>
#include <deque>
#include <vector>

#define HIGH 1
#define LOW 0
#define OUTPUT 1
#define INPUT 0
#define D0 0
#define AR_INTERNAL 1

namespace sim {
extern uint32_t now_ms;
extern int pin_state[16];
extern uint32_t vdd_mv;        // Versorgung des XIAO
extern int adc_reference;
extern int adc_bits;
void tick();   // jede Zeitabfrage lässt 1 ms vergehen: Warte-Schleifen enden immer
}

inline uint32_t millis() { sim::tick(); return sim::now_ms; }
inline void delay(uint32_t ms) { sim::now_ms += ms; }
inline void pinMode(int, int) {}
inline void digitalWrite(int pin, int v) { sim::pin_state[pin] = v; }
inline void analogReference(int ref) { sim::adc_reference = ref; }
inline void analogReadResolution(int bits) { sim::adc_bits = bits; }
// SAADC, interne Referenz 0,6 V, Verstärkung 1/6: Vollausschlag 3,6 V
inline uint32_t analogReadVDD() {
  if (sim::adc_reference != AR_INTERNAL) return 0;
  uint32_t full = (1u << sim::adc_bits) - 1;
  return std::min<uint32_t>(full, sim::vdd_mv * full / 3600);
}
using std::min;
using std::max;
template <class T> T constrain(T x, T a, T b) { return x < a ? a : (x > b ? b : x); }

// UART: was gesendet wird, geht an die Gegenstelle am Bus (wire), deren Antwort landet im Empfangspuffer.
struct SerialStub {
  bool open = false;
  std::deque<uint8_t> rx;
  std::vector<uint8_t> (*wire)(uint8_t) = nullptr;
  void begin(unsigned long) { open = true; }
  void end() { open = false; rx.clear(); }
  int available() { return (int)rx.size(); }
  int read() {
    if (rx.empty()) return -1;
    int b = rx.front();
    rx.pop_front();
    return b;
  }
  size_t write(const uint8_t* d, size_t n) {
    for (size_t i = 0; open && wire && i < n; i++)
      for (uint8_t x : wire(d[i])) rx.push_back(x);
    return n;
  }
  void flush() {}
};
extern SerialStub Serial1;
