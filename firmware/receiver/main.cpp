// Pegel-Empfänger (XIAO ESP32S3 + Wio-SX1262)
//
// Nimmt die Messblöcke der Sender an (pegel_block.h), quittiert sie und gibt jeden Block als JSON-Zeile auf
// Serial aus. Beantwortet die Pfad-REQs der Sender, damit diese einen Pfad hierher lernen bzw. prüfen können
// (siehe firmware/sender/main.cpp).
//
// Außerdem Gateway für die GPS-Tracker (firmware/tracker): deren zwischengespeicherte Einträge kommen gebündelt
// als verschlüsselte REQ (tracker_packet.h); die Antwort quittiert sie und trägt die aktuellen Einstellungen des
// Trackers. Die Einträge gehen einzeln per tracker_uplink an die Tracker-API.
//
// Serial-Befehle:
//   tset <tracker> <intervall> <alarm> <alarmintervall>   Tracker-Einstellungen zum Testen ohne API;
//       Intervalle als Code 0..3 (1 / 5 / 15 / 60 min), alarm 0..3 (aus / leicht / mittel / sensibel).
//   creset <sender>   vergisst den Zählerstand eines Pegel-Senders (nach Tausch oder Neuaufsetzen des Senders,
//       dessen Zähler dann wieder klein anfängt).

#include <Arduino.h>
#include <Mesh.h>
#include <Preferences.h>
#include <esp_task_wdt.h>
#include <helpers/ArduinoHelpers.h>
#include <helpers/StaticPoolPacketManager.h>
#include <helpers/SimpleMeshTables.h>
#include <target.h>

#include "pegel_packet.h"
#include "pegel_block.h"
#include "tracker_packet.h"
#include "secrets_receiver.h"
#include "uploader.h"
#include "tracker_uplink.h"

#ifndef TRACKER_COUNT
  #define TRACKER_COUNT 0
#endif
#define PEER_COUNT (PEGEL_SENDER_COUNT + TRACKER_COUNT)

#define STATUS_INTERVAL_MS  60000

// Langzeitbetrieb: Empfangsteil des SX1262 regelmäßig zurücksetzen, Funkchip nach langer Stille neu starten,
// Watchdog für Schleife und Uploader, Neustart bei zerstückeltem Heap (String/HTTP über Jahre).
#define AGC_RESET_INTERVAL_MS  (10UL * 60 * 1000)
#define RADIO_SILENCE_MS       (6UL * 3600 * 1000)
#define WDT_TIMEOUT_S          90       // länger als die längste HTTP-Folge des Uploaders (2 x 15 s + TLS)
#define HEAP_RESTART_BLOCK     32000    // TLS braucht 2 x 16 KB: darunter neu starten, sobald nichts wartet
#define HEAP_CRITICAL_BLOCK    16000    // darunter sofort neu starten

struct Peer {
  mesh::Identity id;
  uint8_t secret[PUB_KEY_SIZE];
  uint8_t path[MAX_PATH_SIZE];
  uint8_t path_len;
  bool has_path;
  uint32_t last_counter;
  uint32_t saved_counter;   // zuletzt in den Flash geschriebener Stand
  bool has_last;
  uint32_t low_counter;     // Zählerneustart erkennen (ReceiverMesh::counterRestarted)
  uint32_t low_since;
  uint16_t low_count;
};

// Fängt der Zähler eines Senders neu an (Flash verloren, Gerät getauscht), wären alle seine Blöcke "veraltet".
// Kommen mindestens RESYNC_BLOCKS solcher Blöcke mit steigendem Zähler über mindestens RESYNC_MIN_MS, gilt der
// neue Stand wie nach creset. Ein Angreifer müsste dafür ebenso viele aufgezeichnete Blöcke in Folge einspielen.
#define RESYNC_BLOCKS  30
#define RESYNC_MIN_MS  (30UL * 60 * 1000)

// Der Zählerstand landet nur alle COUNTER_SAVE_STEP Zähler im Flash (NVS): bei jedem Block geschrieben, wären das
// über 30 Jahre mehrere Millionen Schreibvorgänge je Sender. Nach einem Neustart fehlen höchstens so viele; das
// schadet nicht, das Zählerfenster ist nach einem Neustart ohnehin offen.
#define COUNTER_SAVE_STEP  64

static Preferences prefs;
static uint32_t rx_ok = 0, rx_rejected = 0, trk_ok = 0;

static bool isTracker(int i) { return i >= PEGEL_SENDER_COUNT; }

static const char* peerName(int i) {
#if TRACKER_COUNT > 0
  if (isTracker(i)) return TRACKER_NAMES[i - PEGEL_SENDER_COUNT];
#endif
  return PEGEL_SENDER_NAMES[i];
}

static const char* peerPub(int i) {
#if TRACKER_COUNT > 0
  if (isTracker(i)) return TRACKER_PUBS[i - PEGEL_SENDER_COUNT];
#endif
  return PEGEL_SENDER_PUBS[i];
}

// Zählerschlüssel: c<i> für Pegel-Sender (wie bisher), t<i> für Tracker.
static void counterKey(char key[4], int i) {
  if (isTracker(i)) {
    key[0] = 't';
    key[1] = (char)('0' + (i - PEGEL_SENDER_COUNT));
  } else {
    key[0] = 'c';
    key[1] = (char)('0' + i);
  }
  key[2] = 0;
}

extern RADIO_CLASS radio;   // aus der MeshCore-Variante (target.cpp)

class ReceiverMesh : public mesh::Mesh {
  Peer peers[PEER_COUNT];
  uint32_t last_heard = 0;   // millis() des letzten gültigen Pakets eines Peers
  int matches[4];   // Mesh fragt per Index nach; Index -> peers[]

  void saveCounter(int i) {
    Peer& p = peers[i];
    if (p.last_counter - p.saved_counter < COUNTER_SAVE_STEP) return;
    p.saved_counter = p.last_counter;
    char key[4];
    counterKey(key, i);
    prefs.putUInt(key, peers[i].last_counter);
  }

  // Antwort an Peer i: bei einer gefluteten REQ als Path-Return (lehrt den Rückweg), sonst als Datagramm.
  void reply(int i, mesh::Packet* req, const uint8_t* secret, const uint8_t* data, size_t len) {
    Peer& p = peers[i];
    if (req->isRouteFlood()) {
      mesh::Packet* rpath = createPathReturn(p.id, secret, req->path, req->path_len, PAYLOAD_TYPE_RESPONSE, data, len);
      if (rpath) sendFlood(rpath, 300);
    } else {
      mesh::Packet* resp = createDatagram(PAYLOAD_TYPE_RESPONSE, p.id, secret, data, len);
      if (!resp) return;
      if (p.has_path) sendDirect(resp, p.path, p.path_len, 300);
      else sendFlood(resp, 300);
    }
  }

  // Zähler, die mehr als das Fenster unter dem höchsten liegen, gelten als veraltet (der Stau des Senders fasst
  // PEGEL_BACKLOG_LEN = 6144 Messungen). Innerhalb des Fensters merkt sich seen[] jeden angenommenen Zähler:
  // wiederholte Blöcke (Quittung verloren) und eingespielte Kopien zählen nicht doppelt. seen[] liegt nur im RAM,
  // nach einem Neustart des Empfängers ist das Fenster wieder offen.
  static constexpr uint32_t PGB_COUNTER_WINDOW = 8192;
  uint8_t seen[PEGEL_SENDER_COUNT][PGB_COUNTER_WINDOW / 8];

  bool isSeen(int i, uint32_t ctr) { return seen[i][(ctr % PGB_COUNTER_WINDOW) / 8] & (1 << (ctr % 8)); }
  void markSeen(int i, uint32_t ctr) { seen[i][(ctr % PGB_COUNTER_WINDOW) / 8] |= (uint8_t)(1 << (ctr % 8)); }
  void unmarkSeen(int i, uint32_t ctr) { seen[i][(ctr % PGB_COUNTER_WINDOW) / 8] &= (uint8_t)~(1 << (ctr % 8)); }

  bool counterRestarted(int i, uint32_t ctr) {
    Peer& p = peers[i];
    uint32_t now = millis();
    if (p.low_count == 0 || ctr <= p.low_counter) {   // neue Folge
      p.low_count = 0;
      p.low_since = now;
    }
    p.low_counter = ctr;
    if (p.low_count < 0xFFFF) p.low_count++;
    return p.low_count >= RESYNC_BLOCKS && now - p.low_since >= RESYNC_MIN_MS;
  }

  void forgetCounter(int i) {
    char key[4];
    counterKey(key, i);
    prefs.remove(key);
    peers[i].has_last = false;
    peers[i].last_counter = 0;
    peers[i].saved_counter = 0;
    peers[i].low_count = 0;
    memset(seen[i], 0, sizeof(seen[i]));
  }

  // true, wenn der Zähler neu ist; schiebt das Fenster bei einem neuen Höchststand weiter.
  bool acceptCounter(int i, uint32_t ctr) {
    Peer& p = peers[i];
    if (!p.has_last || ctr > p.last_counter) {
      uint32_t from = p.has_last ? p.last_counter + 1 : ctr;
      uint32_t span = ctr - from;   // ctr > last_counter, also kein Unterlauf
      if (span >= PGB_COUNTER_WINDOW) memset(seen[i], 0, sizeof(seen[i]));
      else for (uint32_t k = 0; k <= span; k++) unmarkSeen(i, from + k);
      p.last_counter = ctr;
      p.has_last = true;
    } else if (p.last_counter - ctr >= PGB_COUNTER_WINDOW || isSeen(i, ctr)) {   // hier ist ctr <= last_counter
      return false;
    }
    markSeen(i, ctr);
    return true;
  }

  void handleBlock(int i, mesh::Packet* packet, const uint8_t* data, size_t len) {
    static PegelBlock b;
    if (!pgb_decode(data, (int)len, b)) {
      Serial.printf("sender %s: unreadable block\n", peerName(i));
      return;
    }
    last_heard = millis();
    Peer& p = peers[i];
    // Ganzer Block unter dem Zählerfenster: nicht quittieren, der Sender behält die Messungen. Nur ein
    // erkannter Zählerneustart lässt ihn durch.
    if (p.has_last && b.counter < p.last_counter && p.last_counter - b.counter >= PGB_COUNTER_WINDOW) {
      if (!counterRestarted(i, b.counter)) {
        rx_rejected += b.n;
        Serial.printf("sender %s: block #%lu below window (last %lu), not acknowledged\n", peerName(i),
                      (unsigned long)b.counter, (unsigned long)p.last_counter);
        return;
      }
      Serial.printf("sender %s: counter restarted at %lu, accepted\n", peerName(i), (unsigned long)b.counter);
      forgetCounter(i);
    } else {
      p.low_count = 0;
    }

    // Quittung sofort, auf dem bekannten Pfad oder ohne Hops (ein Sender ohne Pfad sendet ohne Hops, ist also
    // in Reichweite). Nie fluten: das kostete bei jeder Messung Sendezeit im ganzen Netz. Doppelte (Quittung
    // verloren) werden ebenfalls quittiert, sonst schickte der Sender sie immer wieder.
    uint8_t ack[PGB_ACK_LEN];
    pgb_encode_ack(b.tag, ack);
    mesh::Packet* resp = createDatagram(PAYLOAD_TYPE_RESPONSE, p.id, p.secret, ack, sizeof(ack));
    if (resp) {
      if (p.has_path) sendDirect(resp, p.path, p.path_len, 300);
      else sendZeroHop(resp, 300);
    }

    uint32_t now_ms = millis();
    int accepted = 0, stale = 0;
    for (int k = 0; k < b.n; k++) {
      if (!acceptCounter(i, b.counter - k)) {
        stale++;
        continue;
      }
      uploader_push(i, now_ms, b.age_s + (uint32_t)k * b.interval_s, b.level_mm[k]);
      accepted++;
    }
    if (accepted) saveCounter(i);
    rx_ok += accepted;
    rx_rejected += stale;
    Serial.printf("{\"sender\":\"%s\",\"counter\":%lu,\"records\":%u,\"accepted\":%d,\"stale\":%d,"
                  "\"last_counter\":%lu,\"level_mm\":%u,\"age_s\":%lu,\"batt_mv\":%u,\"snr\":%.2f,"
                  "\"rssi\":%.1f,\"route\":\"%s\"}\n",
                  peerName(i), (unsigned long)b.counter, b.n, accepted, stale, (unsigned long)p.last_counter,
                  b.level_mm[0], (unsigned long)b.age_s, b.batt_mv, packet->getSNR(), _radio->getLastRSSI(),
                  p.has_path ? "direct" : "zero hop");
  }

  // Gegen das Wiedereinspielen alter, längst gelöschter Pakete: nur Zähler annehmen, die höchstens so weit unter
  // dem höchsten bisher gesehenen liegen, wie die Warteschlange des Trackers fasst. Doppelte innerhalb des Fensters
  // (Quittung verloren, Tracker wiederholt) erkennt der Server am Zähler.
  static constexpr uint32_t TRK_COUNTER_WINDOW = 1024;

  void handleTracker(int i, mesh::Packet* packet, const uint8_t* secret, const uint8_t* data, size_t len) {
    static TrackerUplink u;   // groß; nur aus der Mesh-Schleife aufgerufen
    if (!trk_decode_uplink(data, (int)len, u)) {
      Serial.printf("tracker %s: unreadable req\n", peerName(i));
      return;
    }
    last_heard = millis();
    Peer& p = peers[i];
    int t = i - PEGEL_SENDER_COUNT;
    // Quittung sofort: der Tracker wartet mit eingeschaltetem Funk darauf. data beginnt mit dem Tag.
    uint8_t out[TRK_DOWN_LEN];
    trk_encode_settings(data, tracker_uplink_settings(t), out);
    reply(i, packet, secret, out, sizeof(out));

    float snr = packet->getSNR(), rssi = _radio->getLastRSSI();
    uint32_t now_ms = millis();
    int accepted = 0, stale = 0;
    for (int k = 0; k < u.n; k++) {
      const TrackerRecord& r = u.rec[k];
      if (p.has_last && r.counter <= p.last_counter && p.last_counter - r.counter >= TRK_COUNTER_WINDOW) {
        stale++;
        continue;
      }
      TrackerUpload up;
      memset(&up, 0, sizeof(up));
      up.rec = r;
      up.received_ms = now_ms;
      up.settings_version = u.head.settings_version;
      up.batt_mv = (k == 0 && (u.head.flags & TRK_F_BATT)) ? u.head.batt_mv : 0;   // Akku gehört zum neuesten
      up.charging = u.head.flags & TRK_F_CHARGING;
      up.usb = u.head.flags & TRK_F_USB;
      up.snr = snr;
      up.rssi = rssi;
      up.idx = (uint8_t)t;
      tracker_uplink_push(up);
      accepted++;
      if (!p.has_last || r.counter > p.last_counter) {
        p.last_counter = r.counter;
        p.has_last = true;
      }
    }
    if (accepted) saveCounter(i);
    trk_ok += accepted;
    rx_rejected += stale;
    const TrackerRecord* newest = u.n ? &u.rec[0] : nullptr;
    Serial.printf("{\"tracker\":\"%s\",\"records\":%u,\"accepted\":%d,\"stale\":%d,\"settings\":%u", peerName(i), u.n,
                  accepted, stale, u.head.settings_version);
    if (newest) {
      Serial.printf(",\"newest\":%lu,\"age\":%lu", (unsigned long)newest->counter, (unsigned long)newest->age_s);
      if (newest->flags & TRK_R_FIX) {
        Serial.printf(",\"lat\":%.7f,\"lon\":%.7f,\"sats\":%u", newest->lat_e7 / 1e7, newest->lon_e7 / 1e7, newest->sats);
      }
      if (newest->flags & TRK_R_MOTION) Serial.print(",\"motion\":true");
    }
    if (u.head.flags & TRK_F_BATT) Serial.printf(",\"batt_mv\":%u", u.head.batt_mv);
    Serial.printf(",\"snr\":%.2f,\"rssi\":%.1f,\"route\":\"%s\"}\n", snr, rssi, packet->isRouteFlood() ? "flood" : "direct");
  }

protected:
  int searchPeersByHash(const uint8_t* hash) override {
    int n = 0;
    for (int i = 0; i < PEER_COUNT && n < 4; i++) {
      if (peers[i].id.isHashMatch(hash)) matches[n++] = i;
    }
    return n;
  }

  void getPeerSharedSecret(uint8_t* dest_secret, int peer_idx) override {
    memcpy(dest_secret, peers[matches[peer_idx]].secret, PUB_KEY_SIZE);
  }

  bool onPeerPathRecv(mesh::Packet* packet, int sender_idx, const uint8_t* secret, uint8_t* path, uint8_t path_len,
                      uint8_t extra_type, uint8_t* extra, uint8_t extra_len) override {
    int i = matches[sender_idx];
    last_heard = millis();
    peers[i].path_len = mesh::Packet::copyPath(peers[i].path, path, path_len);
    peers[i].has_path = true;
    Serial.printf("path to %s learned: %u hop(s)\n", peerName(i), (unsigned)(path_len & 63));
    return true;
  }

  void onPeerDataRecv(mesh::Packet* packet, uint8_t type, int sender_idx, const uint8_t* secret,
                      uint8_t* data, size_t len) override {
    if (type != PAYLOAD_TYPE_REQ || len < 5) return;
    int i = matches[sender_idx];
    if (isTracker(i)) {
      handleTracker(i, packet, secret, data, len);
      return;
    }
    if (data[4] == PGB_TYPE) {
      handleBlock(i, packet, data, len);
      return;
    }
    uint8_t out[5];
    memcpy(out, data, 4);
    out[4] = 'O';
    reply(i, packet, secret, out, sizeof(out));
    Serial.printf("REQ %s from %s, answered\n", packet->isRouteFlood() ? "flood" : "direct", peerName(i));
  }

  int getAGCResetInterval() const override { return AGC_RESET_INTERVAL_MS; }

public:
  // Seit Stunden kein Paket: Funkchip neu starten (falls er hängt; ohne Sender in Reichweite kostet es nichts).
  void maintain() {
    uint32_t now = millis();
    if ((int32_t)(now - (last_heard + RADIO_SILENCE_MS)) < 0) return;
    last_heard = now;
    Serial.printf("no packet for %lu h: radio restart %s\n", RADIO_SILENCE_MS / 3600000UL,
                  radio.std_init() ? "ok" : "failed");
    radio_driver.resetAGC();
  }

  bool resetCounter(const char* name) {
    for (int i = 0; i < PEGEL_SENDER_COUNT; i++) {
      if (strcmp(name, PEGEL_SENDER_NAMES[i]) != 0) continue;
      forgetCounter(i);
      return true;
    }
    return false;
  }

  ReceiverMesh(mesh::Radio& radio, mesh::RNG& rng, mesh::RTCClock& rtc, SimpleMeshTables& tables)
    : mesh::Mesh(radio, *new ArduinoMillis(), rng, rtc, *new StaticPoolPacketManager(16), tables) { }

  void begin() {
    self_id = mesh::LocalIdentity(PEGEL_RECEIVER_PRV, PEGEL_RECEIVER_PUB);
    prefs.begin("pegel", false);
    for (int i = 0; i < PEER_COUNT; i++) {
      Peer& p = peers[i];
      p.id = mesh::Identity(peerPub(i));
      self_id.calcSharedSecret(p.secret, p.id);
      p.path_len = 0;
      p.has_path = false;
      char key[4];
      counterKey(key, i);
      p.has_last = prefs.isKey(key);
      p.last_counter = prefs.getUInt(key, 0);
      p.saved_counter = p.last_counter;
      p.low_counter = 0;
      p.low_since = 0;
      p.low_count = 0;
    }
    memset(seen, 0, sizeof(seen));
    mesh::Mesh::begin();
    last_heard = millis();
    Serial.printf("pegel receiver up, %d sender(s), %d tracker(s) known\n", PEGEL_SENDER_COUNT, TRACKER_COUNT);
  }
};

StdRNG fast_rng;
SimpleMeshTables tables;
ReceiverMesh the_mesh(radio_driver, fast_rng, rtc_clock, tables);

// "creset <sender>": Zählerstand vergessen; "tset <tracker> <iv> <alarm> <alarm_iv>": Einstellungen von Hand, Version
// eins höher als bisher.
static void handleCommand(char* line) {
  if (strncmp(line, "creset ", 7) == 0) {
    if (the_mesh.resetCounter(line + 7)) Serial.printf("creset: counter of %s forgotten\n", line + 7);
    else Serial.printf("creset: unknown sender %s\n", line + 7);
    return;
  }
  if (strncmp(line, "tset ", 5) != 0) return;
  char name[16];
  int iv, alarm, aiv;
  if (sscanf(line + 5, "%15s %d %d %d", name, &iv, &alarm, &aiv) != 4) {
    Serial.println("usage: tset <tracker> <iv 0..3> <alarm 0..3> <alarm_iv 0..3>");
    return;
  }
#if TRACKER_COUNT > 0
  for (int t = 0; t < TRACKER_COUNT; t++) {
    if (strcmp(name, TRACKER_NAMES[t]) != 0) continue;
    TrackerSettings s = tracker_uplink_settings(t);
    s.version++;
    s.interval = (uint8_t)iv;
    s.alarm = (uint8_t)alarm;
    s.alarm_interval = (uint8_t)aiv;
    if (!trk_settings_valid(s)) {
      Serial.println("tset: value out of range");
      return;
    }
    tracker_uplink_set(t, s);
    return;
  }
#endif
  Serial.printf("tset: unknown tracker %s\n", name);
}

static void pollSerial() {
  static char line[64];
  static int len = 0;
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\r' || c == '\n') {
      line[len] = 0;
      if (len) handleCommand(line);
      len = 0;
    } else if (len < (int)sizeof(line) - 1) {
      line[len++] = c;
    }
  }
}

void setup() {
  esp_task_wdt_init(WDT_TIMEOUT_S, true);   // stellt den schon laufenden Task-Watchdog um
  enableLoopWDT();                          // loop() bedient ihn bei jedem Durchlauf
  Serial.begin(115200);
  delay(2000);   // USB-CDC: dem Host Zeit zum Verbinden lassen, sonst gehen die Startmeldungen verloren
  Serial.println("pegel receiver booting");
  board.begin();
  Serial.println("board ok, radio init...");
  if (!radio_init()) {
    while (1) { Serial.println("radio init failed"); delay(2000); }
  }
  fast_rng.begin(radio_driver.getRngSeed());
  the_mesh.begin();
  uploader_begin();
}

void loop() {
  the_mesh.loop();
  the_mesh.maintain();
  rtc_clock.tick();
  pollSerial();

  static uint32_t next_status = 0;
  if ((int32_t)(millis() - next_status) >= 0) {
    next_status = millis() + STATUS_INTERVAL_MS;
    char up[96], trk[64];
    uploader_status(up, sizeof(up));
    tracker_uplink_status(trk, sizeof(trk));
    // Interner RAM: WLAN und TLS brauchen ihn, das PSRAM zählt hier nicht.
    size_t heap_block = heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT);
    size_t heap_free = heap_caps_get_free_size(MALLOC_CAP_INTERNAL);
    Serial.printf("status: up %lus rx_ok=%lu rx_rejected=%lu trk_ok=%lu heap=%u/%u %s %s\n",
                  (unsigned long)(millis() / 1000), (unsigned long)rx_ok, (unsigned long)rx_rejected,
                  (unsigned long)trk_ok, (unsigned)heap_block, (unsigned)heap_free, up, trk);
    // Zerstückelter Heap: neu starten, bevor eine Zuweisung im Uploader scheitert. Verloren gehen dabei nur
    // Pfade und das Duplikatfenster; wartende Uploads nur im kritischen Fall.
    if (heap_block < HEAP_CRITICAL_BLOCK || (heap_block < HEAP_RESTART_BLOCK && uploader_idle())) {
      Serial.printf("heap fragmented (largest block %u): restart\n", (unsigned)heap_block);
      Serial.flush();
      ESP.restart();
    }
  }
}
