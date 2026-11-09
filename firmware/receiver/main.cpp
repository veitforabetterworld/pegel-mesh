// Pegel-Empfänger (XIAO ESP32S3 + Wio-SX1262)
//
// Nimmt die 13-Byte-Messpakete der Sender an, prüft HMAC und Zähler und gibt jede gültige
// Messung als JSON-Zeile auf Serial aus. Beantwortet die REQs der Sender, damit diese einen
// Pfad hierher lernen bzw. prüfen können (siehe firmware/sender/main.cpp).
//
// Außerdem Gateway für die GPS-Tracker (firmware/tracker): deren zwischengespeicherte Einträge kommen gebündelt
// als verschlüsselte REQ (tracker_packet.h); die Antwort quittiert sie und trägt die aktuellen Einstellungen des
// Trackers. Die Einträge gehen einzeln per tracker_uplink an die Tracker-API.
//
// Serial-Befehl zum Testen ohne API:  tset <tracker> <intervall> <alarm> <alarmintervall>
//   Intervalle als Code 0..3 (1 / 5 / 15 / 60 min), alarm 0..3 (aus / leicht / mittel / sensibel).

#include <Arduino.h>
#include <Mesh.h>
#include <Preferences.h>
#include <helpers/ArduinoHelpers.h>
#include <helpers/StaticPoolPacketManager.h>
#include <helpers/SimpleMeshTables.h>
#include <target.h>

#include "pegel_packet.h"
#include "tracker_packet.h"
#include "secrets_receiver.h"
#include "uploader.h"
#include "tracker_uplink.h"

#ifndef TRACKER_COUNT
  #define TRACKER_COUNT 0
#endif
#define PEER_COUNT (PEGEL_SENDER_COUNT + TRACKER_COUNT)

#define STATUS_INTERVAL_MS  60000

struct Peer {
  mesh::Identity id;
  uint8_t secret[PUB_KEY_SIZE];
  uint8_t path[MAX_PATH_SIZE];
  uint8_t path_len;
  bool has_path;
  uint32_t last_counter;
  bool has_last;
};

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

class ReceiverMesh : public mesh::Mesh {
  Peer peers[PEER_COUNT];
  int matches[4];   // Mesh fragt per Index nach; Index -> peers[]

  void saveCounter(int i) {
    char key[4];
    counterKey(key, i);
    prefs.putUInt(key, peers[i].last_counter);
  }

  void handleReading(const uint8_t* buf, float snr, float rssi) {
    for (int i = 0; i < PEGEL_SENDER_COUNT; i++) {
      Peer& p = peers[i];
      PegelReading r;
      if (!pegel_verify(PEGEL_HMAC_KEYS[i], buf, p.has_last, p.last_counter, r)) continue;
      p.last_counter = r.counter;
      p.has_last = true;
      saveCounter(i);
      rx_ok++;
      uploader_push(i, millis(), r.age_s, r.level_mm);
      Serial.printf("{\"sender\":\"%s\",\"counter\":%lu,\"level_mm\":%u,\"age_s\":%u,\"snr\":%.2f,\"rssi\":%.1f}\n",
                    PEGEL_SENDER_NAMES[i], (unsigned long)r.counter, r.level_mm, r.age_s, snr, rssi);
      return;
    }
    rx_rejected++;
    Serial.println("rejected: unknown key, bad MAC or replayed counter");
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
      if (p.has_last && r.counter + TRK_COUNTER_WINDOW <= p.last_counter) {
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
    uint8_t out[5];
    memcpy(out, data, 4);
    out[4] = 'O';
    reply(i, packet, secret, out, sizeof(out));
    Serial.printf("REQ %s from %s, answered\n", packet->isRouteFlood() ? "flood" : "direct", peerName(i));
  }

  void onRawDataRecv(mesh::Packet* packet) override {
    if (packet->payload_len != PEGEL_PKT_LEN) return;
    handleReading(packet->payload, packet->getSNR(), _radio->getLastRSSI());
  }

public:
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
    }
    mesh::Mesh::begin();
    Serial.printf("pegel receiver up, %d sender(s), %d tracker(s) known\n", PEGEL_SENDER_COUNT, TRACKER_COUNT);
  }
};

StdRNG fast_rng;
SimpleMeshTables tables;
ReceiverMesh the_mesh(radio_driver, fast_rng, rtc_clock, tables);

// "tset <tracker> <iv> <alarm> <alarm_iv>": Einstellungen von Hand, Version eins höher als bisher.
static void handleCommand(char* line) {
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
  rtc_clock.tick();
  pollSerial();

  static uint32_t next_status = 0;
  if ((int32_t)(millis() - next_status) >= 0) {
    next_status = millis() + STATUS_INTERVAL_MS;
    char up[96], trk[64];
    uploader_status(up, sizeof(up));
    tracker_uplink_status(trk, sizeof(trk));
    Serial.printf("status: up %lus rx_ok=%lu rx_rejected=%lu trk_ok=%lu %s %s\n", (unsigned long)(millis() / 1000),
                  (unsigned long)rx_ok, (unsigned long)rx_rejected, (unsigned long)trk_ok, up, trk);
  }
}
