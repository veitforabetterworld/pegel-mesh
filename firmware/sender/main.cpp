// Pegel-Sender (XIAO nRF52840 + Wio-SX1262)
//
// Misst zyklisch und legt jede Messung in den Stau (backlog.h), bis der Empfänger sie quittiert. Gesendet wird
// ein Block der neuesten Messungen (pegel_block.h) als REQ, direkt auf dem bekannten Pfad oder ohne Hops,
// nie geflutet. Im Messtakt geht immer ein Block raus. Kam die Quittung, folgt der restliche Stau Block für
// Block, solange das 1-%-Sendebudget reicht; bleibt sie aus, wartet der Sender auf den nächsten Messtakt.
// Den Pfad lernt der Sender über eine geflutete, verschlüsselte REQ an den Empfänger, der mit einem
// Path-Return antwortet. Stündlich prüft eine direkte REQ, ob der Pfad noch trägt.
//
// Strom sparen: zwischen den Ereignissen schläft der Funkchip (SX1262 Sleep) und die CPU (FreeRTOS-Leerlauf),
// der Flash-Chip des XIAO bleibt im Deep Power-down. Wach ist der Sender nur zum Messen, Senden und solange er auf
// eine Antwort wartet. Die Uhrzeit kommt mit jeder Quittung vom Empfänger; Messungen mit Uhrzeit wandern bei
// gestörter Verbindung in den Flash (flashlog.h) und überstehen so einen Stromausfall.

#include <Arduino.h>
#include <Mesh.h>
#include <InternalFileSystem.h>
#include <nrf_sdm.h>
#include <helpers/ArduinoHelpers.h>
#include <helpers/StaticPoolPacketManager.h>
#include <helpers/SimpleMeshTables.h>
#include <target.h>

#include "pegel_packet.h"
#include "pegel_block.h"
#include "backlog.h"
#include "flashlog.h"
#include "level_sensor.h"
#if PEGEL_BOARD
  #include "battery.h"
#endif
#include "pegel_5v_power.h"
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
#define DISCOVER_RETRY_MIN_MS   (10UL * 60 * 1000)   // ohne Pfad: Suche nach 10 min wiederholen,
#define DISCOVER_RETRY_MAX_MS   (6UL * 3600 * 1000)  // bei jedem Fehlschlag doppelt so lange warten, bis 6 h
#define FLOOD_REPLY_TIMEOUT_MS  60000
#define REPLY_TIMEOUT_BASE_MS   4000    // Antwort auf direktem Weg: 4 s + 3 s je Hop, höchstens 30 s
#define REPLY_TIMEOUT_HOP_MS    3000
#define REPLY_TIMEOUT_MAX_MS    30000
#define TX_GRACE_MS             3000    // nach einem Sendeauftrag mindestens so lange wach (Warteschlange, CAD)
#define BACKLOG_GAP_MS          2000    // Pause zwischen Quittung und nächstem Stau-Block
#define BACKLOG_BUDGET_WAIT_MS  10000   // Budget reicht nicht: so lange warten, dann neu prüfen
#define SLEEP_MAX_MS            30000   // längster Schlaf am Stück (Watchdog, Überlauf der Laufzeit)
#define STATUS_INTERVAL_MS      30000   // Statuszeile, nur wenn ohnehin wach und USB verbunden
#define UNIX_VALID_AFTER_S      1700000000ULL

// MeshCore begrenzt die Sendezeit auf 1 / (1 + Faktor) je Stunde: 99 ergibt 1 %.
#define PEGEL_AIRTIME_FACTOR  99.0f

// Langzeitbetrieb: das Empfangsteil des SX1262 regelmäßig zurücksetzen (wie die MeshCore-Repeater), den Funkchip
// nach langer Stille ganz neu starten, und ein Watchdog, der eine hängende Firmware neu startet.
#define AGC_RESET_INTERVAL_MS   (10UL * 60 * 1000)
#define RADIO_SILENCE_MS        (6UL * 3600 * 1000)   // so lange keine Antwort vom Empfänger: Funkchip neu starten
#define WDT_TIMEOUT_S           120                    // länger als ein Firmware-Update per USB (ca. 40 s)

// Stau im Flash: 24 Seiten direkt unter dem Dateisystem (0xED000), Platz für gut 6000 Messungen. Die Firmware
// belegt ab 0x27000 rund 270 KB; setup() prüft, dass sie nicht in den Bereich hineinreicht.
#define FLASHLOG_BASE   0xD5000UL
#define FLASHLOG_PAGES  24

#define CTR_FILE       "/pegel_ctr"
#define CTR_SAVE_STEP  256   // Zähler nur alle 256 Pakete in den Flash schreiben

static bool due(uint32_t now, uint32_t t) { return (int32_t)(now - t) >= 0; }

// Laufzeit in ms, 64 Bit: über den Überlauf von millis() alle 49,7 Tage hinweg. Muss öfter als alle 49 Tage laufen
// (die Schleife läuft mindestens alle SLEEP_MAX_MS).
static uint64_t uptime64() {
  static uint32_t last = 0;
  static uint64_t high = 0;
  uint32_t m = millis();
  if (m < last) high += 1ULL << 32;
  last = m;
  return high | m;
}

// Hardware-Watchdog des nRF52840; läuft auch im Schlaf. Einmal gestartet, hält ihn nur ein Reset an (nach einem
// Soft-Reset läuft er weiter, dann bleibt die Einstellung).
static void wdtBegin() {
  if (NRF_WDT->RUNSTATUS) return;
  NRF_WDT->CONFIG = (WDT_CONFIG_SLEEP_Run << WDT_CONFIG_SLEEP_Pos) | (WDT_CONFIG_HALT_Pause << WDT_CONFIG_HALT_Pos);
  NRF_WDT->CRV = WDT_TIMEOUT_S * 32768UL;
  NRF_WDT->RREN = WDT_RREN_RR0_Msk;
  NRF_WDT->TASKS_START = 1;
}
static void wdtFeed() { NRF_WDT->RR[0] = WDT_RR_RR_Reload; }

// Flash-Chip des XIAO (P25Q16H an QSPI, von der Firmware nicht benutzt) in den Deep Power-down: Befehl 0xB9,
// per Bit-Banging. Spart im Schlaf rund 10-15 µA.
static void qspiFlashSleep() {
  pinMode(PIN_QSPI_CS, OUTPUT);
  pinMode(PIN_QSPI_SCK, OUTPUT);
  pinMode(PIN_QSPI_IO0, OUTPUT);
  pinMode(PIN_QSPI_IO2, OUTPUT);   // WP
  pinMode(PIN_QSPI_IO3, OUTPUT);   // HOLD
  digitalWrite(PIN_QSPI_IO2, HIGH);
  digitalWrite(PIN_QSPI_IO3, HIGH);
  digitalWrite(PIN_QSPI_SCK, LOW);
  digitalWrite(PIN_QSPI_CS, LOW);
  for (int bit = 7; bit >= 0; bit--) {
    digitalWrite(PIN_QSPI_IO0, (0xB9 >> bit) & 1);
    digitalWrite(PIN_QSPI_SCK, HIGH);
    digitalWrite(PIN_QSPI_SCK, LOW);
  }
  digitalWrite(PIN_QSPI_CS, HIGH);
}

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

// Flash direkt über den NVMC (der SoftDevice läuft im Sender nicht; setup() prüft das).
struct NvmcIO : FlashLogIO {
  static void wait() { while (!NRF_NVMC->READY) { } }
  bool erase(uint32_t page_addr) override {
    NRF_NVMC->CONFIG = NVMC_CONFIG_WEN_Een;
    wait();
    NRF_NVMC->ERASEPAGE = page_addr;
    wait();
    NRF_NVMC->CONFIG = NVMC_CONFIG_WEN_Ren;
    wait();
    return true;
  }
  bool write(uint32_t addr, const uint8_t* src, int len) override {
    NRF_NVMC->CONFIG = NVMC_CONFIG_WEN_Wen;
    wait();
    for (int i = 0; i < len; i += 4) {
      uint32_t w;
      memcpy(&w, src + i, 4);
      *(volatile uint32_t*)(addr + i) = w;
      wait();
    }
    NRF_NVMC->CONFIG = NVMC_CONFIG_WEN_Ren;
    wait();
    return memcmp((const void*)addr, src, len) == 0;
  }
  const uint8_t* ptr(uint32_t addr) override { return (const uint8_t*)addr; }
};

static Backlog backlog;
static NvmcIO nvmc;
static FlashLog flashlog(nvmc, FLASHLOG_BASE, FLASHLOG_PAGES);
static bool flashlog_ok = false;
extern RADIO_CLASS radio;   // aus der MeshCore-Variante (target.cpp)

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
  uint32_t discover_retry = DISCOVER_RETRY_MIN_MS;
  uint32_t reply_deadline = 0;
  uint32_t next_status = 0;
  uint32_t awake_until = 0;
  bool awaiting_reply = false;
  bool sensor_on = false;
  bool battery_low = false;
  bool radio_awake = true;
  bool link_ok = false;          // letzter Block wurde quittiert
  bool block_in_flight = false;
  uint8_t block_tag[PGB_TAG_LEN];
  uint32_t block_counter = 0;
  uint8_t block_n = 0;
  uint32_t block_deadline = 0;
  uint32_t next_backlog = 0;
  uint32_t last_heard = 0;       // millis() der letzten Antwort des Empfängers
  uint16_t bat_mv = 0;
#if PEGEL_BOARD
  BatteryKind bat_kind = BAT_LIFEPO4;
#endif

  // Uhrzeit aus der letzten Quittung: Unix-ms zum Zeitpunkt unix_at (Laufzeit).
  bool time_known = false;
  uint64_t unix_base = 0, unix_at = 0;

  uint64_t unixNow() { return time_known ? unix_base + (uptime64() - unix_at) : 0; }

  void radioWake() {
    if (radio_awake) return;
    radio_driver.resetAGC();   // Warm-Sleep verlassen; die nächste Schleife startet den Empfang
    radio_awake = true;
  }

  void radioSleep() {
    if (!radio_awake) return;
    radio.sleep();             // SX1262 Warm-Sleep, Einstellungen bleiben erhalten (~1 µA)
    radio_awake = false;
  }

  void stayAwake(uint32_t ms) {
    uint32_t until = millis() + ms;
    if ((int32_t)(until - awake_until) > 0) awake_until = until;
  }

  uint32_t replyTimeout() {
    uint32_t t = REPLY_TIMEOUT_BASE_MS + (have_path ? (out_path_len & 63) * REPLY_TIMEOUT_HOP_MS : 0);
    return t < REPLY_TIMEOUT_MAX_MS ? t : REPLY_TIMEOUT_MAX_MS;
  }

#if PEGEL_BOARD
  // true, solange der Akku als fast leer gilt. Unplausible Messung: letzten Zustand behalten.
  bool refreshBattery() {
    if (!battery_read(bat_mv, bat_kind)) {
      logf("battery: reading implausible\n");
      return battery_low;
    }
    logf("battery %u mV %s\n", bat_mv, bat_kind == BAT_LIION ? "Li-ion" : "LiFePO4");
    if (battery_cutoff(bat_mv, bat_kind)) hibernate();
    battery_low = battery_low_update(battery_low, bat_mv, bat_kind);
    return battery_low;
  }

  // Tiefentladeschutz: Sonde und Funk aus, halbstündlich nachmessen. Lädt die Sonne den Akku wieder über die
  // ok-Schwelle (battery.h), startet der Sender neu und initialisiert den Funk sauber. Der Stau geht vorher in den
  // Flash.
  void hibernate() {
    logf("battery %u mV below %u mV: radio off, sleeping\n", bat_mv, BATTERY_LIMITS[bat_kind].cutoff);
    persistAll();
    level_sensor_power(false);
    radio_driver.powerOff();
    while (true) {
      for (int i = 0; i < 30; i++) {   // 30 min, minütlich den Watchdog bedienen
        delay(60000);
        wdtFeed();
      }
      uint16_t mv;
      BatteryKind kind;
      if (battery_read(mv, kind) && mv >= BATTERY_LIMITS[kind].ok) NVIC_SystemReset();
    }
  }
#endif

  // Alle Messungen mit Uhrzeit, die noch nicht im Flash stehen, dorthin schreiben.
  void persistAll() {
    if (!flashlog_ok) return;
    int written = 0;
    for (int i = 0; i < backlog.size(); i++) {
      BacklogEntry& e = backlog.at(i);
      if ((e.flags & BL_ABS) && !(e.flags & BL_PERSISTED) && flashlog.append(e)) {
        e.flags |= BL_PERSISTED;
        written++;
      }
    }
    if (written) logf("flash: %d measurement(s) saved\n", written);
  }

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
  void record(uint8_t status, uint16_t level_mm) {
    if (status != LEVEL_OK) {
      // Statt eines Messwerts geht der Fehlercode über Funk; die Pegelseite zeigt ihn als Gerätestatus.
      level_mm = PEGEL_STATUS_BASE + status;
      logf("error %u\n", status);
    }
    ++counter;
    if (counter % CTR_SAVE_STEP == 0) saveCounter(counter);
    uint64_t up = uptime64(), unix_ms = unixNow();
    backlog.expire(up, unix_ms);
    if (time_known) backlog.push(counter, unix_ms, level_mm, BL_ABS);
    else backlog.push(counter, up, level_mm, 0);
    // Verbindung gestört: jede Messung mit Uhrzeit sofort in den Flash
    if (!link_ok) persistAll();
    logf("measured #%lu level=%u mm, backlog %d\n", (unsigned long)counter, level_mm, backlog.size());
    if (!block_in_flight) sendBlock();
  }

  void sendReading() {
    uint16_t level_mm = 0;
    record(measureLevel(level_mm), level_mm);
  }

  // Sendezeit eines Blocks mit data_len Byte: Kopf, Pfadlänge, Pfad, Ziel- und Absender-Hash, MAC und die auf
  // AES-Blöcke aufgerundeten Daten. Selbst gerechnet (Semtech AN1200.13): der Funkchip schläft hier oft und
  // liefert dann keine Werte.
  uint32_t blockAirtime(int data_len) {
    int path_bytes = have_path ? (out_path_len & 63) * ((out_path_len >> 6) + 1) : 0;
    int len = 2 + path_bytes + 4 + ((data_len + 15) / 16) * 16;
    const float ts = (float)(1UL << LORA_SF) / (LORA_BW * 1000.0f);   // Symboldauer in s
    const int de = ts > 0.016f ? 1 : 0;                               // Low Data Rate Optimize
#ifdef LORA_CR
    const int cr = LORA_CR - 4;
#else
    const int cr = 1;                                                 // 4/5 wie CustomSX1262::std_init
#endif
    int num = 8 * len - 4 * LORA_SF + 28 + 16;                        // expliziter Kopf, CRC an
    int nsym = 8 + (num > 0 ? (num + 4 * (LORA_SF - 2 * de) - 1) / (4 * (LORA_SF - 2 * de)) * (cr + 4) : 0);
    return (uint32_t)(((16 + 4.25f) + nsym) * ts * 1000.0f) + 1;      // Präambel 16 Symbole
  }

  void sendBlock() {
    PegelBlock b;
    if (backlog.build(uptime64(), PEGEL_INTERVAL_S, b) == 0) return;
    getRNG()->random(b.tag, PGB_TAG_LEN);
    b.batt_mv = bat_mv;
    uint8_t data[PGB_MAX_LEN];
    int len = pgb_encode(b, data);
    mesh::Packet* pkt = createDatagram(PAYLOAD_TYPE_REQ, receiver, secret, data, len);
    if (!pkt) {
      logf("block: no packet buffer\n");
      return;
    }
    radioWake();
    // Ohne Pfad ohne Hops: kommt nur an, wenn der Empfänger in Funkreichweite ist.
    if (have_path) sendDirect(pkt, out_path, out_path_len);
    else sendZeroHop(pkt);
    memcpy(block_tag, b.tag, PGB_TAG_LEN);
    block_counter = b.counter;
    block_n = b.n;
    block_in_flight = true;
    block_deadline = millis() + replyTimeout();
    stayAwake(TX_GRACE_MS);
    logf("TX block #%lu..#%lu %s %s\n", (unsigned long)(b.counter - b.n + 1), (unsigned long)b.counter,
         (b.flags & PGB_F_ABS) ? "abs" : "rel", have_path ? "(direct path)" : "(zero hop)");
  }

  void sendRequest() {
    uint8_t data[5];
    getRNG()->random(data, 4);   // macht jede REQ einzigartig, sonst verwerfen Repeater sie als Duplikat
    data[4] = 'P';
    mesh::Packet* pkt = createDatagram(PAYLOAD_TYPE_REQ, receiver, secret, data, sizeof(data));
    if (!pkt) return;
    radioWake();
    if (have_path) {
      sendDirect(pkt, out_path, out_path_len);
      reply_deadline = millis() + replyTimeout();
      logf("REQ direct (path check)\n");
    } else {
      sendFlood(pkt);
      reply_deadline = millis() + FLOOD_REPLY_TIMEOUT_MS;
      logf("REQ flood (path discovery)\n");
    }
    awaiting_reply = true;
    stayAwake(TX_GRACE_MS);
  }

  void onAck(uint64_t receiver_now_s) {
    uint32_t now = millis();
    if (receiver_now_s >= UNIX_VALID_AFTER_S) {
      unix_base = receiver_now_s * 1000 + 500;   // die Quittung war im Mittel ~0,5 s unterwegs
      unix_at = uptime64();
      if (!time_known) logf("time from receiver: %lu\n", (unsigned long)receiver_now_s);
      time_known = true;
      backlog.sync(unix_at, unix_base);
    }
    bool persisted = backlog.remove(block_counter, block_n);
    if (flashlog_ok) {
      if (persisted) flashlog.ack(block_counter, block_n);
      if (backlog.size() == 0) flashlog.clear();
    }
    block_in_flight = false;
    link_ok = true;
    next_backlog = now + BACKLOG_GAP_MS;
    if (have_path && !awaiting_reply) next_check = now + PATH_CHECK_INTERVAL_MS;   // die Quittung belegt den Pfad
    logf("ack #%lu..#%lu, backlog %d\n", (unsigned long)(block_counter - block_n + 1), (unsigned long)block_counter,
         backlog.size());
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
    discover_retry = DISCOVER_RETRY_MIN_MS;
    last_heard = millis();
    next_check = millis() + PATH_CHECK_INTERVAL_MS;
    stayAwake(TX_GRACE_MS);   // Mesh schickt dem Empfänger gleich den Rückweg
    logf("path to receiver learned: %u hop(s)\n", (unsigned)(path_len & 63));
    return true;
  }

  void onPeerDataRecv(mesh::Packet* packet, uint8_t type, int sender_idx, const uint8_t* secret,
                      uint8_t* data, size_t len) override {
    if (type != PAYLOAD_TYPE_RESPONSE) return;
    last_heard = millis();
    uint64_t receiver_now;
    if (block_in_flight && pgb_is_ack(data, (int)len, block_tag, receiver_now)) {
      onAck(receiver_now);
      return;
    }
    awaiting_reply = false;
    logf("receiver answered, path ok\n");
  }

  float getAirtimeBudgetFactor() const override { return PEGEL_AIRTIME_FACTOR; }
  int getAGCResetInterval() const override { return AGC_RESET_INTERVAL_MS; }

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

    if (flashlog_ok) {
      int restored = flashlog.begin(backlog);
      if (restored) logf("flash: %d measurement(s) from before the restart\n", restored);
    }

    mesh::Mesh::begin();
    uint32_t now = millis();
    last_heard = now;
    next_check = now + 3000;
    next_send = now + 5000;
    next_status = now;
    logf("pegel sender %s, interval %u s, counter %lu\n", PEGEL_SENDER_NAME, PEGEL_INTERVAL_S,
                  (unsigned long)counter);
  }

  void loop() {
    wdtFeed();
#if PEGEL_5V_BOARD
    pegel_5v_power_update();
#endif
    uptime64();
    if (radio_awake) mesh::Mesh::loop();
    uint32_t now = millis();

    // Seit Stunden keine Antwort: vielleicht ist nur der Empfänger weg, vielleicht hängt der Funkchip. Ein
    // Neustart des Chips kostet nichts; der Stau bleibt erhalten.
    if (due(now, last_heard + RADIO_SILENCE_MS) && !block_in_flight) {
      last_heard = now;
      logf("no reply for %lu h: radio restart %s\n", RADIO_SILENCE_MS / 3600000UL,
           radio.std_init() ? "ok" : "failed");
      radio_awake = false;
      radioWake();
    }

    if (awaiting_reply && due(now, reply_deadline)) {
      awaiting_reply = false;
      if (have_path) logf("no answer on path, path dropped\n");
      else logf("no answer to discovery, next in %lu min\n", discover_retry / 60000UL);
      have_path = false;
      next_check = now + discover_retry;
      discover_retry = discover_retry * 2 < DISCOVER_RETRY_MAX_MS ? discover_retry * 2 : DISCOVER_RETRY_MAX_MS;
    }
    if (!awaiting_reply && due(now, next_check)) {
      sendRequest();
      next_check = now + (have_path ? PATH_CHECK_INTERVAL_MS : discover_retry);
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
        record(LEVEL_BATTERY_LOW, 0);
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
      persistAll();
      logf("no ack, backlog %d\n", backlog.size());
      // Vielleicht trägt der Pfad nicht mehr: gleich prüfen statt erst zur vollen Stunde.
      if (have_path && !awaiting_reply) next_check = now;
    }
    // Stau nachsenden, solange die Verbindung steht und das Budget den Block und danach noch zwei reguläre
    // Messungen trägt.
    bool backlog_pending = link_ok && !block_in_flight && backlog.size() > 0;
    if (backlog_pending && due(now, next_backlog)) {
      PegelBlock b;
      int n = backlog.build(uptime64(), PEGEL_INTERVAL_S, b);
      uint32_t need = blockAirtime(PGB_HEAD_LEN + 2 * n) + 2 * blockAirtime(PGB_HEAD_LEN + 2);
      if (getRemainingTxBudget() >= need) sendBlock();
      else next_backlog = now + BACKLOG_BUDGET_WAIT_MS;
    }
    if (Serial && due(now, next_status)) {
      next_status = now + STATUS_INTERVAL_MS;
      logf("status: up %lus counter=%lu path=%s bat=%umV backlog=%d dropped=%lu budget=%lums time=%s\n",
           (unsigned long)(uptime64() / 1000), (unsigned long)counter, have_path ? "yes" : "no", bat_mv,
           backlog.size(), (unsigned long)backlog.dropped, (unsigned long)getRemainingTxBudget(),
           time_known ? "yes" : "no");
    }

    // Schlafen, wenn nichts ansteht: Funkchip in den Warm-Sleep, CPU bis zum nächsten Ereignis in den Leerlauf.
    bool busy = block_in_flight || awaiting_reply || !due(now, awake_until) || _mgr->getOutboundTotal() > 0 ||
                (radio_awake && !_radio->isInRecvMode());
    if (busy) return;
    radioSleep();
    uint32_t wake = next_send - (sensor_on ? 0 : PEGEL_SENSOR_WARMUP_MS);
    if ((int32_t)(next_check - wake) < 0) wake = next_check;
    if (backlog_pending && (int32_t)(next_backlog - wake) < 0) wake = next_backlog;
    int32_t dt = (int32_t)(wake - millis());
    if (dt > SLEEP_MAX_MS) dt = SLEEP_MAX_MS;
    if (dt > 0) delay(dt);
  }
};

// Wie radio_init() der Variante, aber ohne rtc_clock.begin(Wire): I²C liegt beim XIAO auf D6/D7, dort hängt
// RS485. Bei ausgeschalteter Sonde zieht der unversorgte SP3485 RX auf GND, die RTC-Suche hängt dann für immer.
// Der Sender braucht keine RTC; rtc_clock nutzt ohne begin() die interne Uhr.
static bool sender_radio_init() { return radio.std_init(&SPI); }

// Stau im Flash nur, wenn der SoftDevice aus ist (sonst gehört ihm der NVMC) und die Firmware den Bereich nicht
// erreicht.
extern uint32_t __etext, __data_start__, __data_end__;
static bool flashlogUsable() {
  uint8_t sd = 0;
  sd_softdevice_is_enabled(&sd);
  uint32_t image_end = (uint32_t)&__etext + ((uint32_t)&__data_end__ - (uint32_t)&__data_start__);
  return !sd && image_end <= FLASHLOG_BASE;
}

StdRNG fast_rng;
SimpleMeshTables tables;
SenderMesh the_mesh(radio_driver, fast_rng, rtc_clock, tables);

void setup() {
  wdtBegin();
  Serial.begin(115200);
  board.begin();
  qspiFlashSleep();
#if PEGEL_BOARD
  battery_charger_begin();
#endif
#if PEGEL_5V_BOARD
  pegel_5v_power_begin();
#endif
  if (!sender_radio_init()) {
    while (1) { logf("radio init failed\n"); delay(2000); }
  }
  fast_rng.begin(radio_driver.getRngSeed());
  InternalFS.begin();
  flashlog_ok = flashlogUsable();
  if (!flashlog_ok) logf("flash backlog off (SoftDevice on or firmware too large)\n");
#if PEGEL_SENSOR
  level_sensor_begin();
#endif
  the_mesh.begin();
}

#if PEGEL_TEST_CMDS
// Notfallwege auslösen (nur im Test-Build pegel_sender_a_test): h = Firmware hängt (Watchdog),
// r = Funkchip neu starten wie nach 6 h Stille, x = Neustart ohne Firmware-Update (wie Stromausfall).
static void pollTestCommands() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == 'h') {
      logf("test: firmware hangs, watchdog restarts in %u s\n", WDT_TIMEOUT_S);
      for (;;) { }
    }
    if (c == 'r') {
      logf("test: radio restart %s\n", radio.std_init() ? "ok" : "failed");
      radio_driver.resetAGC();
    }
    if (c == 'x') {
      logf("test: restart\n");
      delay(100);
      NVIC_SystemReset();
    }
  }
}
#endif

void loop() {
#if PEGEL_TEST_CMDS
  pollTestCommands();
#endif
  the_mesh.loop();
  rtc_clock.tick();
}
