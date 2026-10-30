// Pegel-Sender (XIAO nRF52840 + Wio-SX1262)
//
// Schickt zyklisch ein 13-Byte-Messpaket (pegel_packet.h) als RAW_CUSTOM-Direktpaket an den
// Empfänger. RAW_CUSTOM wird von Repeatern nur auf einem bekannten Pfad weitergeleitet, nie
// geflutet. Den Pfad lernt der Sender über eine geflutete, verschlüsselte REQ an den Empfänger,
// der mit einem Path-Return antwortet. Stündlich prüft eine direkte REQ, ob der Pfad noch trägt.

#include <Arduino.h>
#include <Mesh.h>
#include <InternalFileSystem.h>
#include <helpers/ArduinoHelpers.h>
#include <helpers/StaticPoolPacketManager.h>
#include <helpers/SimpleMeshTables.h>
#include <target.h>

#include "pegel_packet.h"
#include "level_sensor.h"
#if PEGEL_BOARD
  #include "battery.h"
#endif
#include PEGEL_SECRETS

using namespace Adafruit_LittleFS_Namespace;

// 1: Pegel von der RS485-Sonde (level_sensor.h), 0: Dummywerte zum Testen ohne Sonde.
#ifndef PEGEL_SENSOR
  #define PEGEL_SENSOR  1
#endif

#ifndef PEGEL_INTERVAL_S
  #define PEGEL_INTERVAL_S  60
#endif

#define PATH_CHECK_INTERVAL_MS  (60UL * 60 * 1000)   // Pfad stündlich prüfen
#define DISCOVER_RETRY_MS       (10UL * 60 * 1000)   // ohne Pfad: Suche alle 10 min wiederholen
#define DIRECT_REPLY_TIMEOUT_MS 30000
#define FLOOD_REPLY_TIMEOUT_MS  60000

#define CTR_FILE       "/pegel_ctr"
#define CTR_SAVE_STEP  256   // Zähler nur alle 256 Pakete in den Flash schreiben

static bool due(uint32_t now, uint32_t t) { return (int32_t)(now - t) >= 0; }

// Log über USB, ohne zu blockieren: ist ein Host verbunden, der nicht mitliest, wird die Zeile verworfen,
// statt den Sender anzuhalten (sonst bleibt der Sendetakt stehen).
static void logf(const char* fmt, ...) {
  char buf[128];
  va_list args;
  va_start(args, fmt);
  int n = vsnprintf(buf, sizeof(buf), fmt, args);
  va_end(args);
  if (n <= 0 || !Serial) return;
  if (n >= (int)sizeof(buf)) n = sizeof(buf) - 1;
  if (Serial.availableForWrite() < n) return;
  Serial.write((const uint8_t*)buf, n);
}

static uint32_t loadCounter() {
  uint32_t c = 0;
  auto f = InternalFS.open(CTR_FILE, FILE_O_READ);
  if (f) {
    f.read((uint8_t*)&c, sizeof(c));
    f.close();
  }
  return c;
}

static void saveCounter(uint32_t c) {
  InternalFS.remove(CTR_FILE);
  auto f = InternalFS.open(CTR_FILE, FILE_O_WRITE);
  if (f) {
    f.write((const uint8_t*)&c, sizeof(c));
    f.close();
  }
}

class SenderMesh : public mesh::Mesh {
  mesh::Identity receiver;
  uint8_t secret[PUB_KEY_SIZE];
  uint8_t out_path[MAX_PATH_SIZE];
  uint8_t out_path_len = 0;
  bool have_path = false;

  uint32_t counter = 0;
  uint32_t next_send = 0;
  uint32_t next_check = 0;
  uint32_t reply_deadline = 0;
  uint32_t next_status = 0;
  bool awaiting_reply = false;
  bool sensor_on = false;
  bool battery_low = false;
  uint16_t bat_mv = 0;
  int16_t bat_ma = 0;

#if PEGEL_BOARD
  // true, solange der Akku als fast leer gilt. INA226 stumm: letzten Zustand behalten.
  bool refreshBattery() {
    if (!battery_read(bat_mv, bat_ma)) {
      logf("battery: INA226 not responding\n");
      return battery_low;
    }
    logf("battery %u mV %d mA\n", bat_mv, bat_ma);
    if (bat_mv < PEGEL_BATTERY_LOW_MV) battery_low = true;
    else if (bat_mv >= PEGEL_BATTERY_OK_MV) battery_low = false;
    return battery_low;
  }
#endif

  /** LEVEL_OK with the level, or an error code of level_sensor.h. */
  uint8_t measureLevel(uint16_t& level_mm) {
#if PEGEL_SENSOR
    return level_sensor_read_mm(level_mm);
#else
    // Dummywert ohne Sonde: 1,50 m mit 6-Stunden-Welle ±30 cm und etwas Rauschen.
    float t = millis() / 1000.0f;
    float level = 1500.0f + 300.0f * sinf(2.0f * PI * t / (6.0f * 3600.0f)) + (float)random(-5, 6);
    level_mm = (uint16_t)constrain(level, 0.0f, (float)PEGEL_LEVEL_MAX_MM);
    return LEVEL_OK;
#endif
  }

  void transmit(uint8_t status, uint16_t level_mm, uint32_t measured_at) {
    PegelReading r;
    if (status != LEVEL_OK) {
      // Statt eines Messwerts geht der Fehlercode über Funk; die Pegelseite zeigt ihn als Gerätestatus.
      r.level_mm = PEGEL_STATUS_BASE + status;
      logf("error %u\n", status);
    } else {
      r.level_mm = level_mm;
    }
    r.counter = ++counter;
    if (counter % CTR_SAVE_STEP == 0) saveCounter(counter);
    r.age_s = (uint8_t)min((millis() - measured_at) / 1000UL, 255UL);

    uint8_t buf[PEGEL_PKT_LEN];
    pegel_encode(PEGEL_HMAC_KEY, r, buf);
    mesh::Packet* pkt = createRawData(buf, sizeof(buf));
    if (!pkt) return;
    // Ohne Pfad als Direktpaket ohne Hops: kommt nur an, wenn der Empfänger in Funkreichweite ist.
    sendDirect(pkt, out_path, have_path ? out_path_len : 0);
    logf("TX #%lu level=%u mm %s\n", (unsigned long)r.counter, r.level_mm,
                  have_path ? "(direct path)" : "(zero hop)");
  }

  void sendReading() {
    uint32_t measured_at = millis();
    uint16_t level_mm = 0;
    transmit(measureLevel(level_mm), level_mm, measured_at);
  }

  void sendRequest() {
    uint8_t data[5];
    getRNG()->random(data, 4);   // macht jede REQ einzigartig, sonst verwerfen Repeater sie als Duplikat
    data[4] = 'P';
    mesh::Packet* pkt = createDatagram(PAYLOAD_TYPE_REQ, receiver, secret, data, sizeof(data));
    if (!pkt) return;
    if (have_path) {
      sendDirect(pkt, out_path, out_path_len);
      reply_deadline = millis() + DIRECT_REPLY_TIMEOUT_MS;
      logf("REQ direct (path check)\n");
    } else {
      sendFlood(pkt);
      reply_deadline = millis() + FLOOD_REPLY_TIMEOUT_MS;
      logf("REQ flood (path discovery)\n");
    }
    awaiting_reply = true;
  }

protected:
  int searchPeersByHash(const uint8_t* hash) override {
    return receiver.isHashMatch(hash) ? 1 : 0;
  }

  void getPeerSharedSecret(uint8_t* dest_secret, int peer_idx) override {
    memcpy(dest_secret, secret, PUB_KEY_SIZE);
  }

  bool onPeerPathRecv(mesh::Packet* packet, int sender_idx, const uint8_t* secret, uint8_t* path, uint8_t path_len,
                      uint8_t extra_type, uint8_t* extra, uint8_t extra_len) override {
    out_path_len = mesh::Packet::copyPath(out_path, path, path_len);
    have_path = true;
    awaiting_reply = false;
    next_check = millis() + PATH_CHECK_INTERVAL_MS;
    logf("path to receiver learned: %u hop(s)\n", (unsigned)(path_len & 63));
    return true;   // Mesh schickt dem Empfänger daraufhin den Rückweg
  }

  void onPeerDataRecv(mesh::Packet* packet, uint8_t type, int sender_idx, const uint8_t* secret,
                      uint8_t* data, size_t len) override {
    if (type == PAYLOAD_TYPE_RESPONSE) {
      awaiting_reply = false;
      logf("receiver answered, path ok\n");
    }
  }

public:
  SenderMesh(mesh::Radio& radio, mesh::RNG& rng, mesh::RTCClock& rtc, SimpleMeshTables& tables)
    : mesh::Mesh(radio, *new ArduinoMillis(), rng, rtc, *new StaticPoolPacketManager(16), tables),
      receiver(PEGEL_RECEIVER_PUB) { }

  void begin() {
    self_id = mesh::LocalIdentity(PEGEL_SENDER_PRV, PEGEL_SENDER_PUB);
    self_id.calcSharedSecret(secret, receiver);

    // Nach einem Neustart über alle evtl. ungespeicherten Zählerstände hinwegspringen.
    counter = loadCounter() + CTR_SAVE_STEP;
    saveCounter(counter);

    mesh::Mesh::begin();
    uint32_t now = millis();
    next_check = now + 3000;
    next_send = now + 5000;
    logf("pegel sender %s, interval %u s, counter %lu\n", PEGEL_SENDER_NAME, PEGEL_INTERVAL_S,
                  (unsigned long)counter);
  }

  void loop() {
    mesh::Mesh::loop();
    uint32_t now = millis();

    if (awaiting_reply && due(now, reply_deadline)) {
      awaiting_reply = false;
      if (have_path) logf("no answer on path, path dropped\n");
      else logf("no answer to discovery\n");
      have_path = false;
      next_check = now + DISCOVER_RETRY_MS;
    }
    if (!awaiting_reply && due(now, next_check)) {
      sendRequest();
      next_check = now + (have_path ? PATH_CHECK_INTERVAL_MS : DISCOVER_RETRY_MS);
    }
#if PEGEL_SENSOR
    // Sonde vor der Messung einschalten, damit sie bis zum Messzeitpunkt aufgewärmt ist.
    // Bei fast leerem Akku aus lassen: der nächste Sendezeitpunkt meldet nur den Fehlercode.
    if (!sensor_on && due(now, next_send - PEGEL_SENSOR_WARMUP_MS)) {
#if PEGEL_BOARD
      refreshBattery();
#endif
      if (!battery_low) {
        level_sensor_power(true);
        sensor_on = true;
      }
    }
#endif
    if (due(now, next_send)) {
      bool low = false;
#if PEGEL_BOARD
      low = refreshBattery();
#endif
      if (low) {
#if PEGEL_SENSOR
        level_sensor_power(false);
        sensor_on = false;
#endif
        transmit(LEVEL_BATTERY_LOW, 0, now);
        next_send += PEGEL_INTERVAL_S * 1000UL;
      }
#if PEGEL_SENSOR
      else if (!sensor_on) {
        // Akku wieder über der Schwelle, Sonde war aus: erst aufwärmen, dann messen.
        level_sensor_power(true);
        sensor_on = true;
        next_send = now + PEGEL_SENSOR_WARMUP_MS;
      }
#endif
      else {
        sendReading();   // schaltet die Sonde wieder ab
        sensor_on = false;
        next_send += PEGEL_INTERVAL_S * 1000UL;
      }
    }
    if (due(now, next_status)) {
      next_status = now + 30000;
      logf("status: up %lus counter=%lu path=%s bat=%umV\n", (unsigned long)(now / 1000), (unsigned long)counter,
                    have_path ? "yes" : "no", bat_mv);
    }
  }
};

StdRNG fast_rng;
SimpleMeshTables tables;
SenderMesh the_mesh(radio_driver, fast_rng, rtc_clock, tables);

void setup() {
  Serial.begin(115200);
  board.begin();
  if (!radio_init()) {
    while (1) { logf("radio init failed\n"); delay(2000); }
  }
  fast_rng.begin(radio_driver.getRngSeed());
  InternalFS.begin();
#if PEGEL_SENSOR
  level_sensor_begin();
#endif
#if PEGEL_BOARD
  if (!battery_begin()) logf("battery: INA226 not found\n");
#endif
  the_mesh.begin();
}

void loop() {
  the_mesh.loop();
  rtc_clock.tick();
}
