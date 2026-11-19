// Pegel-Sender (XIAO nRF52840 + Wio-SX1262)
//
// Misst zyklisch und legt jede Messung in den Stau (backlog.h), bis der Empfänger sie quittiert. Gesendet wird
// ein Block der neuesten Messungen (pegel_block.h) als REQ, direkt auf dem bekannten Pfad oder ohne Hops,
// nie geflutet. Im Messtakt geht immer ein Block raus. Kam die Quittung, folgt der restliche Stau Block für
// Block, solange das 1-%-Sendebudget reicht; bleibt sie aus, wartet der Sender auf den nächsten Messtakt.
// Den Pfad lernt der Sender über eine geflutete, verschlüsselte REQ an den Empfänger, der mit einem
// Path-Return antwortet. Stündlich prüft eine direkte REQ, ob der Pfad noch trägt.

#include <Arduino.h>
#include <Mesh.h>
#include <InternalFileSystem.h>
#include <helpers/ArduinoHelpers.h>
#include <helpers/StaticPoolPacketManager.h>
#include <helpers/SimpleMeshTables.h>
#include <target.h>

#include "pegel_packet.h"
#include "pegel_block.h"
#include "backlog.h"
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
#define BLOCK_REPLY_TIMEOUT_MS  30000
#define BACKLOG_GAP_MS          2000    // Pause zwischen Quittung und nächstem Stau-Block
#define BACKLOG_BUDGET_WAIT_MS  10000   // Budget reicht nicht: so lange warten, dann neu prüfen

// MeshCore begrenzt die Sendezeit auf 1 / (1 + Faktor) je Stunde: 99 ergibt 1 %.
#define PEGEL_AIRTIME_FACTOR  99.0f

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

static Backlog backlog;

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
  bool link_ok = false;          // letzter Block wurde quittiert
  bool block_in_flight = false;
  uint8_t block_tag[PGB_TAG_LEN];
  uint32_t block_counter = 0;
  uint8_t block_n = 0;
  uint32_t block_deadline = 0;
  uint32_t next_backlog = 0;
  uint16_t bat_mv = 0;

#if PEGEL_BOARD
  // true, solange der Akku als fast leer gilt. Unplausible Messung: letzten Zustand behalten.
  bool refreshBattery() {
    if (!battery_read(bat_mv)) {
      logf("battery: VDD reading implausible\n");
      return battery_low;
    }
    logf("battery %u mV\n", bat_mv);
    if (battery_cutoff(bat_mv)) hibernate();
    battery_low = battery_low_update(battery_low, bat_mv);
    return battery_low;
  }

  // Tiefentladeschutz: Sonde und Funk aus, halbstündlich nachmessen. Lädt die Sonne den Akku wieder über
  // PEGEL_BATTERY_OK_MV, startet der Sender neu und initialisiert den Funk sauber.
  void hibernate() {
    logf("battery %u mV below %u mV: radio off, sleeping\n", bat_mv, PEGEL_BATTERY_CUTOFF_MV);
    level_sensor_power(false);
    radio_driver.powerOff();
    while (true) {
      delay(30UL * 60 * 1000);
      uint16_t mv;
      if (battery_read(mv) && mv >= PEGEL_BATTERY_OK_MV) NVIC_SystemReset();
    }
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

  // Neue Messung (oder Fehlercode) in den Stau legen. Im Messtakt geht immer ein Block raus, auch wenn der
  // letzte nicht ankam; nur ein noch unbeantworteter Block hat Vorrang (der nächste trägt die Messung dann mit).
  void record(uint8_t status, uint16_t level_mm, uint32_t measured_at) {
    if (status != LEVEL_OK) {
      // Statt eines Messwerts geht der Fehlercode über Funk; die Pegelseite zeigt ihn als Gerätestatus.
      level_mm = PEGEL_STATUS_BASE + status;
      logf("error %u\n", status);
    }
    ++counter;
    if (counter % CTR_SAVE_STEP == 0) saveCounter(counter);
    backlog.expire(measured_at);
    backlog.push(counter, measured_at, level_mm);
    logf("measured #%lu level=%u mm, backlog %d\n", (unsigned long)counter, level_mm, backlog.size());
    if (!block_in_flight) sendBlock();
  }

  void sendReading() {
    uint32_t measured_at = millis();
    uint16_t level_mm = 0;
    record(measureLevel(level_mm), level_mm, measured_at);
  }

  // Sendezeit eines Blocks mit data_len Byte: Kopf, Pfadlänge, Pfad, Ziel- und Absender-Hash, MAC und die auf
  // AES-Blöcke aufgerundeten Daten.
  uint32_t blockAirtime(int data_len) {
    int path_bytes = have_path ? (out_path_len & 63) * ((out_path_len >> 6) + 1) : 0;
    int len = 2 + path_bytes + 4 + ((data_len + 15) / 16) * 16;
    return radio_driver.getEstAirtimeFor(len);
  }

  void sendBlock() {
    PegelBlock b;
    if (backlog.build(millis(), PEGEL_INTERVAL_S, b) == 0) return;
    getRNG()->random(b.tag, PGB_TAG_LEN);
    b.batt_mv = bat_mv;
    uint8_t data[PGB_MAX_LEN];
    int len = pgb_encode(b, data);
    mesh::Packet* pkt = createDatagram(PAYLOAD_TYPE_REQ, receiver, secret, data, len);
    if (!pkt) return;
    // Ohne Pfad ohne Hops: kommt nur an, wenn der Empfänger in Funkreichweite ist.
    if (have_path) sendDirect(pkt, out_path, out_path_len);
    else sendZeroHop(pkt);
    memcpy(block_tag, b.tag, PGB_TAG_LEN);
    block_counter = b.counter;
    block_n = b.n;
    block_in_flight = true;
    block_deadline = millis() + BLOCK_REPLY_TIMEOUT_MS;
    logf("TX block #%lu..#%lu %s\n", (unsigned long)(b.counter - b.n + 1), (unsigned long)b.counter,
         have_path ? "(direct path)" : "(zero hop)");
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
    if (type != PAYLOAD_TYPE_RESPONSE) return;
    if (block_in_flight && pgb_is_ack(data, (int)len, block_tag)) {
      backlog.remove(block_counter, block_n);
      block_in_flight = false;
      link_ok = true;
      uint32_t now = millis();
      next_backlog = now + BACKLOG_GAP_MS;
      if (have_path && !awaiting_reply) next_check = now + PATH_CHECK_INTERVAL_MS;   // die Quittung belegt den Pfad
      logf("ack #%lu..#%lu, backlog %d\n", (unsigned long)(block_counter - block_n + 1), (unsigned long)block_counter,
           backlog.size());
      return;
    }
    awaiting_reply = false;
    logf("receiver answered, path ok\n");
  }

  float getAirtimeBudgetFactor() const override { return PEGEL_AIRTIME_FACTOR; }

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
        record(LEVEL_BATTERY_LOW, 0, now);
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
    if (block_in_flight && due(now, block_deadline)) {
      block_in_flight = false;
      link_ok = false;
      logf("no ack, backlog %d\n", backlog.size());
      // Vielleicht trägt der Pfad nicht mehr: gleich prüfen statt erst zur vollen Stunde.
      if (have_path && !awaiting_reply) next_check = now;
    }
    // Stau nachsenden, solange die Verbindung steht und das Budget den Block und danach noch zwei reguläre
    // Messungen trägt.
    if (link_ok && !block_in_flight && backlog.size() > 0 && due(now, next_backlog)) {
      PegelBlock b;
      int n = backlog.build(now, PEGEL_INTERVAL_S, b);
      uint32_t need = blockAirtime(PGB_HEAD_LEN + 2 * n) + 2 * blockAirtime(PGB_HEAD_LEN + 2);
      if (getRemainingTxBudget() >= need) sendBlock();
      else next_backlog = now + BACKLOG_BUDGET_WAIT_MS;
    }
    if (due(now, next_status)) {
      next_status = now + 30000;
      logf("status: up %lus counter=%lu path=%s bat=%umV backlog=%d dropped=%lu budget=%lums\n",
           (unsigned long)(now / 1000), (unsigned long)counter, have_path ? "yes" : "no", bat_mv, backlog.size(),
           (unsigned long)backlog.dropped, (unsigned long)getRemainingTxBudget());
    }
  }
};

// Wie radio_init() der Variante, aber ohne rtc_clock.begin(Wire): I²C liegt beim XIAO auf D6/D7, dort hängt
// RS485. Bei ausgeschalteter Sonde zieht der unversorgte SP3485 RX auf GND, die RTC-Suche hängt dann für immer.
// Der Sender braucht keine RTC; rtc_clock nutzt ohne begin() die interne Uhr.
extern RADIO_CLASS radio;
static bool sender_radio_init() { return radio.std_init(&SPI); }

StdRNG fast_rng;
SimpleMeshTables tables;
SenderMesh the_mesh(radio_driver, fast_rng, rtc_clock, tables);

void setup() {
  Serial.begin(115200);
  board.begin();
  if (!sender_radio_init()) {
    while (1) { logf("radio init failed\n"); delay(2000); }
  }
  fast_rng.begin(radio_driver.getRngSeed());
  InternalFS.begin();
#if PEGEL_SENSOR
  level_sensor_begin();
#endif
  the_mesh.begin();
}

void loop() {
  the_mesh.loop();
  rtc_clock.tick();
}
