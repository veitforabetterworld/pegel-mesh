// Pegel-Empfänger (XIAO ESP32S3 + Wio-SX1262)
//
// Nimmt die 13-Byte-Messpakete der Sender an, prüft HMAC und Zähler und gibt jede gültige
// Messung als JSON-Zeile auf Serial aus. Beantwortet die REQs der Sender, damit diese einen
// Pfad hierher lernen bzw. prüfen können (siehe firmware/sender/main.cpp).

#include <Arduino.h>
#include <Mesh.h>
#include <Preferences.h>
#include <helpers/ArduinoHelpers.h>
#include <helpers/StaticPoolPacketManager.h>
#include <helpers/SimpleMeshTables.h>
#include <target.h>

#include "pegel_packet.h"
#include "secrets_receiver.h"
#include "uploader.h"

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
static uint32_t rx_ok = 0, rx_rejected = 0;

class ReceiverMesh : public mesh::Mesh {
  Peer peers[PEGEL_SENDER_COUNT];
  int matches[4];   // Mesh fragt per Index nach; Index -> peers[]

  void saveCounter(int i) {
    char key[4] = { 'c', (char)('0' + i), 0 };
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

protected:
  int searchPeersByHash(const uint8_t* hash) override {
    int n = 0;
    for (int i = 0; i < PEGEL_SENDER_COUNT && n < 4; i++) {
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
    Serial.printf("path to sender %s learned: %u hop(s)\n", PEGEL_SENDER_NAMES[i], (unsigned)(path_len & 63));
    return true;
  }

  void onPeerDataRecv(mesh::Packet* packet, uint8_t type, int sender_idx, const uint8_t* secret,
                      uint8_t* data, size_t len) override {
    if (type != PAYLOAD_TYPE_REQ || len < 5) return;
    int i = matches[sender_idx];
    Peer& p = peers[i];
    uint8_t reply[5];
    memcpy(reply, data, 4);
    reply[4] = 'O';

    if (packet->isRouteFlood()) {
      // Pfadsuche: Rückweg mitschicken, Antwort steckt als extra im Path-Return.
      mesh::Packet* rpath = createPathReturn(p.id, secret, packet->path, packet->path_len,
                                             PAYLOAD_TYPE_RESPONSE, reply, sizeof(reply));
      if (rpath) sendFlood(rpath, 300);
      Serial.printf("REQ flood from %s, path return sent\n", PEGEL_SENDER_NAMES[i]);
    } else {
      mesh::Packet* resp = createDatagram(PAYLOAD_TYPE_RESPONSE, p.id, secret, reply, sizeof(reply));
      if (!resp) return;
      if (p.has_path) sendDirect(resp, p.path, p.path_len, 300);
      else sendFlood(resp, 300);
      Serial.printf("REQ direct from %s, answered\n", PEGEL_SENDER_NAMES[i]);
    }
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
    for (int i = 0; i < PEGEL_SENDER_COUNT; i++) {
      Peer& p = peers[i];
      p.id = mesh::Identity(PEGEL_SENDER_PUBS[i]);
      self_id.calcSharedSecret(p.secret, p.id);
      p.path_len = 0;
      p.has_path = false;
      char key[4] = { 'c', (char)('0' + i), 0 };
      p.has_last = prefs.isKey(key);
      p.last_counter = prefs.getUInt(key, 0);
    }
    mesh::Mesh::begin();
    Serial.printf("pegel receiver up, %d sender(s) known\n", PEGEL_SENDER_COUNT);
  }
};

StdRNG fast_rng;
SimpleMeshTables tables;
ReceiverMesh the_mesh(radio_driver, fast_rng, rtc_clock, tables);

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

  static uint32_t next_status = 0;
  if ((int32_t)(millis() - next_status) >= 0) {
    next_status = millis() + STATUS_INTERVAL_MS;
    char up[96];
    uploader_status(up, sizeof(up));
    Serial.printf("status: up %lus rx_ok=%lu rx_rejected=%lu %s\n", (unsigned long)(millis() / 1000),
                  (unsigned long)rx_ok, (unsigned long)rx_rejected, up);
  }
}
