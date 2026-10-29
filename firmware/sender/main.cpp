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
#include PEGEL_SECRETS

using namespace Adafruit_LittleFS_Namespace;

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
  bool awaiting_reply = false;

  uint16_t measureLevel() {
    // Dummywert: 1,50 m mit 6-Stunden-Welle ±30 cm und etwas Rauschen.
    float t = millis() / 1000.0f;
    float level = 1500.0f + 300.0f * sinf(2.0f * PI * t / (6.0f * 3600.0f)) + (float)random(-5, 6);
    return (uint16_t)constrain(level, 0.0f, 65535.0f);
  }

  void sendReading() {
    uint32_t measured_at = millis();
    PegelReading r;
    r.level_mm = measureLevel();
    r.counter = ++counter;
    if (counter % CTR_SAVE_STEP == 0) saveCounter(counter);
    r.age_s = (uint8_t)min((millis() - measured_at) / 1000UL, 255UL);

    uint8_t buf[PEGEL_PKT_LEN];
    pegel_encode(PEGEL_HMAC_KEY, r, buf);
    mesh::Packet* pkt = createRawData(buf, sizeof(buf));
    if (!pkt) return;
    // Ohne Pfad als Direktpaket ohne Hops: kommt nur an, wenn der Empfänger in Funkreichweite ist.
    sendDirect(pkt, out_path, have_path ? out_path_len : 0);
    Serial.printf("TX #%lu level=%u mm %s\n", (unsigned long)r.counter, r.level_mm,
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
      Serial.println("REQ direct (path check)");
    } else {
      sendFlood(pkt);
      reply_deadline = millis() + FLOOD_REPLY_TIMEOUT_MS;
      Serial.println("REQ flood (path discovery)");
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
    Serial.printf("path to receiver learned: %u hop(s)\n", (unsigned)(path_len & 63));
    return true;   // Mesh schickt dem Empfänger daraufhin den Rückweg
  }

  void onPeerDataRecv(mesh::Packet* packet, uint8_t type, int sender_idx, const uint8_t* secret,
                      uint8_t* data, size_t len) override {
    if (type == PAYLOAD_TYPE_RESPONSE) {
      awaiting_reply = false;
      Serial.println("receiver answered, path ok");
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
    Serial.printf("pegel sender %s, interval %u s, counter %lu\n", PEGEL_SENDER_NAME, PEGEL_INTERVAL_S,
                  (unsigned long)counter);
  }

  void loop() {
    mesh::Mesh::loop();
    uint32_t now = millis();

    if (awaiting_reply && due(now, reply_deadline)) {
      awaiting_reply = false;
      if (have_path) Serial.println("no answer on path, path dropped");
      else Serial.println("no answer to discovery");
      have_path = false;
      next_check = now + DISCOVER_RETRY_MS;
    }
    if (!awaiting_reply && due(now, next_check)) {
      sendRequest();
      next_check = now + (have_path ? PATH_CHECK_INTERVAL_MS : DISCOVER_RETRY_MS);
    }
    if (due(now, next_send)) {
      sendReading();
      next_send += PEGEL_INTERVAL_S * 1000UL;
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
    while (1) { Serial.println("radio init failed"); delay(2000); }
  }
  fast_rng.begin(radio_driver.getRngSeed());
  InternalFS.begin();
  the_mesh.begin();
}

void loop() {
  the_mesh.loop();
  rtc_clock.tick();
}
