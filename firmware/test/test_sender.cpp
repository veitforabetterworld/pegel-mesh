// PC-Test der Sender-Treiber für die Trägerplatine (PEGEL_BOARD=1):
// level_sensor.cpp gegen eine nachgebildete Modbus-Sonde an Serial1 (SP3485 mit automatischer Richtung),
// battery.cpp gegen den nachgebildeten SAADC an VDD (Spannungen aus der SPICE-Simulation, hardware/pegel-sender/verify).
//
//   g++ -std=c++17 -DPEGEL_BOARD=1 -Imock -I../sender -I../common test_sender.cpp mock/sim.cpp
//       ../sender/level_sensor.cpp ../sender/battery.cpp -o test_sender && ./test_sender

#include <cmath>
#include <cstdio>
#include <vector>

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
  int tx_bytes = 0;
  std::vector<uint8_t> frame;

  // Bytes von der RS485-Leitung; Antwort zurück, sobald ein Rahmen vollständig ist. Ohne D0 (Sonde und
  // SP3485 aus) kommt nichts an.
  std::vector<uint8_t> receive(uint8_t b) {
    tx_bytes++;
    if (sim::pin_state[D0] != HIGH) return {};
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

static Probe probe;
static std::vector<uint8_t> bus(uint8_t b) { return probe.receive(b); }

// ---------------------------------------------------------------- Tests
static void test_level() {
  std::printf("Pegelsonde über Serial1 und SP3485:\n");
  Serial1.wire = bus;
  level_sensor_begin();
  CHECK(!Wire.running, "I2C belegt D6/D7 noch");
  CHECK(!Serial1.open, "UART offen, obwohl die Sonde (und der SP3485) aus ist");

  uint16_t mm = 0;
  probe.mode = Probe::OK;
  probe.level_cm = 123;
  level_sensor_power(true);
  CHECK(sim::pin_state[D0] == HIGH, "D0 (Sondenversorgung) nicht eingeschaltet");
  CHECK(Serial1.open, "UART mit eingeschalteter Sonde nicht offen");
  sim::now_ms += PEGEL_SENSOR_WARMUP_MS;
  uint8_t st = level_sensor_read_mm(mm);
  CHECK(st == LEVEL_OK && mm == 1230, "Messung: Status %u, %u mm (erwartet OK, 1230 mm)", st, mm);
  CHECK(sim::pin_state[D0] == LOW, "Sonde nach der Messung nicht abgeschaltet");
  CHECK(!Serial1.open, "UART nach der Messung noch offen (speist den SP3485 über TX)");

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
  level_sensor_power(false);     // Sonde ohne Versorgung antwortet nicht
  st = level_sensor_read_mm(mm);
  CHECK(st == LEVEL_NO_RESPONSE, "Sonde ohne Versorgung: Status %u", st);
  std::printf("  %d Anfragen an die Sonde, %d Bytes gesendet\n", probe.requests, probe.tx_bytes);
}

static void test_battery() {
  std::printf("Akkuspannung über VDD (+%u mV Diode D10, Werte aus der SPICE-Simulation):\n", PEGEL_VDD_DROP_MV);
  // Akku → XIAO_3V3 (VDD) laut Simulation; bei Ruhestrom liegt D10 nahe an PEGEL_VDD_DROP_MV
  struct Case { const char* name; uint32_t vdd, bat; } cases[] = {
      {"Nacht, Ruhe (Akku 3,30 V)", 3080, 3300},
      {"Laden voll (Akku 3,50 V)", 3290, 3500},
      {"Akku 2,8 V", 2600, 2800},
      {"Akku 2,6 V", 2400, 2600},
  };
  for (auto& c : cases) {
    sim::vdd_mv = c.vdd;
    sim::adc_reference = 0;
    sim::adc_bits = 10;
    uint16_t mv = 0;
    bool ok = battery_read(mv);
    CHECK(ok && std::abs((int)mv - (int)c.bat) <= 25, "%s: %u mV (erwartet %u mV)", c.name, mv, c.bat);
    std::printf("  %-34s VDD %4u mV -> Akku %5u mV\n", c.name, c.vdd, mv);
  }
  sim::vdd_mv = 0;
  uint16_t mv;
  CHECK(!battery_read(mv), "VDD 0 V als gültig gemeldet");
}

static void test_low_battery() {
  std::printf("Unterspannung (Hysterese %u/%u mV, Abschaltung unter %u mV):\n", PEGEL_BATTERY_LOW_MV,
              PEGEL_BATTERY_OK_MV, PEGEL_BATTERY_CUTOFF_MV);
  struct Step { uint16_t mv; bool low; } seq[] = {
      {3300, false}, {2900, false}, {2801, false}, {2799, true}, {2850, true}, {2999, true}, {3000, false}, {2950, false}};
  bool low = false;
  for (auto& s : seq) {
    low = battery_low_update(low, s.mv);
    CHECK(low == s.low, "%u mV: %s (erwartet %s)", s.mv, low ? "leer" : "ok", s.low ? "leer" : "ok");
  }
  CHECK(battery_cutoff(2599) && !battery_cutoff(2600), "Abschaltschwelle nicht bei 2600 mV");
}

int main() {
  test_level();
  test_battery();
  test_low_battery();
  std::printf(failures ? "\n%d FEHLER\n" : "\nalle Tests bestanden\n", failures);
  return failures ? 1 : 0;
}
