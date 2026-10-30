// PC-Test der Sender-Treiber für die Trägerplatine (PEGEL_BOARD=1):
// level_sensor.cpp + sc16is740.cpp gegen einen nachgebildeten SC16IS740 mit Modbus-Sonde dahinter,
// battery.cpp gegen einen nachgebildeten INA226 (Messwerte aus der SPICE-Simulation, hardware/pegel-sender/verify).
//
//   g++ -std=c++17 -DPEGEL_BOARD=1 -Imock -I../sender -I../common test_sender.cpp mock/sim.cpp
//       ../sender/level_sensor.cpp ../sender/sc16is740.cpp ../sender/battery.cpp -o test_sender && ./test_sender

#include <cmath>
#include <cstdio>
#include <deque>
#include <map>
#include <string>

#include "Arduino.h"
#include "Wire.h"
#include "battery.h"
#include "level_sensor.h"

static int failures = 0;
#define CHECK(cond, ...)                                     \
  do {                                                       \
    if (!(cond)) {                                           \
      failures++;                                            \
      std::printf("  FEHLER %s:%d: ", __FILE__, __LINE__);   \
      std::printf(__VA_ARGS__);                              \
      std::printf("\n");                                     \
    }                                                        \
  } while (0)

static uint16_t crc16(const uint8_t* d, size_t n) {
  uint16_t crc = 0xFFFF;
  for (size_t i = 0; i < n; i++) {
    crc ^= d[i];
    for (int b = 0; b < 8; b++) crc = (crc & 1) ? (crc >> 1) ^ 0xA001 : crc >> 1;
  }
  return crc;
}

// ---------------------------------------------------------------- Modbus-Sonde (RTU, Adresse 1)
struct Probe {
  enum Mode { OK, SILENT, BAD_CRC } mode = OK;
  uint16_t level_cm = 123;
  int requests = 0;
  std::vector<uint8_t> frame;

  // Bytes von der RS485-Leitung; Antwort zurück, sobald ein Rahmen vollständig ist
  std::vector<uint8_t> receive(uint8_t b) {
    frame.push_back(b);
    if (frame.size() < 8) return {};
    std::vector<uint8_t> req = frame;
    frame.clear();
    requests++;
    bool valid = req[0] == 0x01 && req[1] == 0x03 && req[2] == 0 && req[3] == 4 && req[4] == 0 && req[5] == 1 &&
                 crc16(req.data(), 6) == (uint16_t)(req[6] | (req[7] << 8));
    if (!valid || mode == SILENT) return {};
    std::vector<uint8_t> resp = {0x01, 0x03, 0x02, (uint8_t)(level_cm >> 8), (uint8_t)level_cm};
    uint16_t c = crc16(resp.data(), resp.size());
    if (mode == BAD_CRC) c ^= 0x55;
    resp.push_back((uint8_t)c);
    resp.push_back((uint8_t)(c >> 8));
    return resp;
  }
};

// ---------------------------------------------------------------- SC16IS740 (I²C, Kanal 0)
struct Sc16 : I2CDevice {
  Probe* probe;
  uint8_t reg[16] = {};
  uint8_t dll = 0, dlh = 0, efr = 0;
  std::deque<uint8_t> rx;
  uint8_t pending = 0;
  bool sleeping = false;
  int tx_bytes = 0;

  explicit Sc16(Probe* p) : probe(p) { reg[3] = 0x1D; }

  bool lcr_dlab() const { return reg[3] & 0x80; }
  bool configured() const {
    // 9600 Bd bei 14,7456 MHz: Teiler 96; 8N1; RS-485: RTS durch Sender, beim Senden high
    return dll == 96 && dlh == 0 && (reg[3] & 0x3F) == 0x03 && (reg[0x0F] & 0x30) == 0x30;
  }

  void write(const std::vector<uint8_t>& b) override {
    if (b.empty()) return;
    uint8_t r = (b[0] >> 3) & 0x0F;
    pending = r;
    if (b.size() == 1) return;   // Registeradresse für folgendes Lesen
    if (r == 0 && !lcr_dlab()) {
      sleeping = false;
      for (size_t i = 1; i < b.size(); i++) {
        tx_bytes++;
        bool powered = sim::pin_state[D0] == HIGH;
        if (configured() && powered)
          for (uint8_t x : probe->receive(b[i])) rx.push_back(x);
      }
      return;
    }
    uint8_t v = b[1];
    if (reg[3] == 0xBF && r == 2) { efr = v; return; }
    if (lcr_dlab() && r == 0) { dll = v; return; }
    if (lcr_dlab() && r == 1) { dlh = v; return; }
    if (r == 2) {                      // FCR
      if (v & 0x02) rx.clear();
      return;
    }
    if (r == 1) sleeping = (v & 0x10) && (efr & 0x10);
    reg[r] = v;
  }

  std::vector<uint8_t> read(size_t n) override {
    std::vector<uint8_t> out;
    for (size_t i = 0; i < n; i++) {
      uint8_t v = 0;
      switch (pending) {
        case 0: if (!rx.empty()) { v = rx.front(); rx.pop_front(); } break;
        case 5: v = 0x60 | (rx.empty() ? 0 : 1); break;   // LSR: THR und Schieberegister leer
        case 8: v = 64; break;                            // TXLVL
        case 9: v = (uint8_t)rx.size(); break;            // RXLVL
        default: v = reg[pending]; break;
      }
      out.push_back(v);
    }
    return out;
  }
};

// ---------------------------------------------------------------- INA226 (Shunt 10 mΩ)
struct Ina : I2CDevice {
  std::map<uint8_t, uint16_t> regs = {{0x00, 0x4127}, {0x05, 0}, {0x06, 0}};
  uint8_t pointer = 0;
  double bus_v = 3.29, current_a = -0.0096;
  int conversions = 0;

  void write(const std::vector<uint8_t>& b) override {
    pointer = b[0];
    if (b.size() < 3) return;
    uint16_t v = (uint16_t)(b[1] << 8 | b[2]);
    regs[pointer] = v;
    if (pointer == 0x00 && (v & 0x7) == 0x3) {          // getriggert: Shunt und Bus
      conversions++;
      double shunt_lsb = 2.5e-6;
      int32_t shunt = (int32_t)std::lround(current_a * 0.010 / shunt_lsb);
      int32_t cur = shunt * (int32_t)regs[0x05] / 2048;
      regs[0x01] = (uint16_t)(int16_t)shunt;
      regs[0x02] = (uint16_t)std::lround(bus_v / 1.25e-3);
      regs[0x04] = (uint16_t)(int16_t)std::max(-32768, std::min(32767, cur));
      regs[0x06] |= 0x0008;
    }
  }

  std::vector<uint8_t> read(size_t n) override {
    uint16_t v = regs[pointer];
    if (pointer == 0x06) regs[0x06] &= ~0x0008;
    std::vector<uint8_t> out = {(uint8_t)(v >> 8), (uint8_t)v};
    out.resize(n);
    return out;
  }
};

// ---------------------------------------------------------------- Tests
static void test_level(Probe& probe, Sc16& uart) {
  std::printf("Pegelsonde über SC16IS740:\n");
  level_sensor_begin();
  CHECK(uart.configured(), "SC16IS740 nicht wie erwartet konfiguriert (Teiler %u/%u, LCR %02X, EFCR %02X)",
        uart.dll, uart.dlh, uart.reg[3], uart.reg[0x0F]);
  CHECK(uart.sleeping, "SC16IS740 schläft nach begin nicht");

  uint16_t mm = 0;
  probe.mode = Probe::OK;
  probe.level_cm = 123;
  level_sensor_power(true);
  CHECK(sim::pin_state[D0] == HIGH, "D0 (Sondenversorgung) nicht eingeschaltet");
  sim::now_ms += PEGEL_SENSOR_WARMUP_MS;
  uint8_t st = level_sensor_read_mm(mm);
  CHECK(st == LEVEL_OK && mm == 1230, "Messung: Status %u, %u mm (erwartet OK, 1230 mm)", st, mm);
  CHECK(sim::pin_state[D0] == LOW, "Sonde nach der Messung nicht abgeschaltet");
  CHECK(uart.sleeping, "SC16IS740 nach der Messung nicht im Schlaf");

  probe.level_cm = 0;
  level_sensor_power(true);
  st = level_sensor_read_mm(mm);
  CHECK(st == LEVEL_OK && mm == 0, "0 cm: Status %u, %u mm", st, mm);

  probe.level_cm = 400;
  level_sensor_power(true);
  st = level_sensor_read_mm(mm);
  CHECK(st == LEVEL_OK && mm == 4000, "400 cm (Messbereichsende): Status %u, %u mm", st, mm);

  probe.level_cm = 401;
  level_sensor_power(true);
  st = level_sensor_read_mm(mm);
  CHECK(st == LEVEL_OUT_OF_RANGE, "401 cm: Status %u (erwartet OUT_OF_RANGE)", st);

  probe.mode = Probe::SILENT;
  level_sensor_power(true);
  uint32_t t0 = sim::now_ms;
  st = level_sensor_read_mm(mm);
  CHECK(st == LEVEL_NO_RESPONSE, "Sonde stumm: Status %u", st);
  CHECK(sim::now_ms - t0 < 1000, "Zeitüberschreitung dauert %u ms", (unsigned)(sim::now_ms - t0));

  probe.mode = Probe::BAD_CRC;
  level_sensor_power(true);
  st = level_sensor_read_mm(mm);
  CHECK(st == LEVEL_NO_RESPONSE, "CRC-Fehler: Status %u", st);

  probe.mode = Probe::OK;
  level_sensor_power(false);     // Sonde ohne Versorgung (z. B. 12-V-Wandler aus) antwortet nicht
  st = level_sensor_read_mm(mm);
  CHECK(st == LEVEL_NO_RESPONSE, "Sonde ohne Versorgung: Status %u", st);
  std::printf("  %d Anfragen an die Sonde, %d Bytes gesendet\n", probe.requests, uart.tx_bytes);
}

static void test_no_uart(Sc16& uart) {
  std::printf("SC16IS740 fehlt:\n");
  Wire.detach(0x48);
  level_sensor_begin();
  uint16_t mm = 0;
  level_sensor_power(true);
  uint8_t st = level_sensor_read_mm(mm);
  CHECK(st == LEVEL_NO_INTERFACE, "Status %u (erwartet NO_INTERFACE)", st);
  CHECK(sim::pin_state[D0] == LOW, "Sonde bleibt an, obwohl nicht gemessen werden kann");
  Wire.attach(0x48, &uart);
}

static void test_battery(Ina& ina) {
  std::printf("Akkumessung INA226 (Werte aus der SPICE-Simulation):\n");
  CHECK(battery_begin(), "battery_begin meldet keinen INA226");
  CHECK(ina.regs[0x05] == 5120, "Kalibrierung %u (erwartet 5120)", ina.regs[0x05]);
  CHECK((ina.regs[0x00] & 0x7) == 0, "INA226 nach begin nicht abgeschaltet");
  struct Case { const char* name; double v, a; } cases[] = {
      {"Nacht, Ruhe", 3.290, -0.0096},
      {"Laden 3 A (Sonne)", 3.390, 2.99},
      {"Laden voll (CV)", 3.610, 0.338},
      {"Sondenspitze 200 mA + Funk, 2,8 V", 2.770, -1.21},
      {"Ladestrom an der Obergrenze (130 mV/40 mΩ)", 3.40, 3.25},
  };
  for (auto& c : cases) {
    ina.bus_v = c.v;
    ina.current_a = c.a;
    uint16_t mv = 0;
    int16_t ma = 0;
    bool ok = battery_read(mv, ma);
    int exp_mv = (int)std::lround(c.v * 1000), exp_ma = (int)(c.a * 1000);
    CHECK(ok && std::abs((int)mv - exp_mv) <= 2 && std::abs((int)ma - exp_ma) <= 1,
          "%s: %u mV %d mA (erwartet %d mV %d mA)", c.name, mv, ma, exp_mv, exp_ma);
    CHECK((ina.regs[0x00] & 0x7) == 0, "%s: INA226 nach der Messung nicht abgeschaltet", c.name);
    std::printf("  %-44s %5u mV %6d mA\n", c.name, mv, ma);
  }
  Wire.detach(0x40);
  uint16_t mv;
  int16_t ma;
  CHECK(!battery_read(mv, ma), "fehlender INA226 nicht erkannt");
  Wire.attach(0x40, &ina);
}

static void test_low_battery() {
  std::printf("Unterspannung (Hysterese %u/%u mV):\n", PEGEL_BATTERY_LOW_MV, PEGEL_BATTERY_OK_MV);
  struct Step { uint16_t mv; bool low; } seq[] = {
      {3300, false}, {2900, false}, {2801, false}, {2799, true}, {2850, true}, {2999, true}, {3000, false}, {2950, false}};
  bool low = false;
  for (auto& s : seq) {
    low = battery_low_update(low, s.mv);
    CHECK(low == s.low, "%u mV: %s (erwartet %s)", s.mv, low ? "leer" : "ok", s.low ? "leer" : "ok");
  }
}

int main() {
  Probe probe;
  Sc16 uart(&probe);
  Ina ina;
  Wire.attach(0x48, &uart);
  Wire.attach(0x40, &ina);
  test_level(probe, uart);
  test_no_uart(uart);
  test_battery(ina);
  test_low_battery();
  std::printf(failures ? "\n%d FEHLER\n" : "\nalle Tests bestanden\n", failures);
  return failures ? 1 : 0;
}
