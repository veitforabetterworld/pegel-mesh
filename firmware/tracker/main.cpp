// GPS-Tracker (XIAO nRF54LM20A Sense + Wio-SX1262 + L76K-GNSS)
//
// Arbeitet in Sitzungen: aufwachen, GPS einschalten, auf einen Fix warten, einen Eintrag (Position, Zustand) in
// die Warteschlange legen und alle noch nicht quittierten Einträge als verschlüsselte REQs an den Empfänger
// schicken, neueste zuerst, bis zu 7 je REQ. Die Antwort des Empfängers quittiert die Einträge einer REQ und
// bringt die Einstellungen mit. Dann alles abschalten und bis zum nächsten Intervall in System OFF schlafen.
//
// Zwischenspeichern und Nachreichen ist fest eingebaut: Ein Eintrag bleibt in der Warteschlange, bis er quittiert
// ist (auch über viele Sitzungen ohne Empfang). Sie liegt im RAM, der System OFF übersteht (.noinit), fasst
// TRK_QUEUE_CAP Einträge und verdrängt bei Überlauf die ältesten. Ein Stromausfall (leerer Akku) leert sie.
// Zeitstempel kommen vom GRTC-Zähler (clock.h), der durch System OFF weiterläuft.
//
// Jedes Aufwachen ist ein Neustart; was über den Schlaf hinweg gebraucht wird, steht in .noinit-RAM, Zähler und
// Einstellungen zusätzlich im Flash.
//
// Alarm: Ist er eingeschaltet, überwacht der Bewegungssensor den Tracker auch im Schlaf und weckt ihn bei
// Bewegung. Dann geht sofort ein Eintrag raus, danach Positionen im Alarmintervall, bis 30 s lang keine
// Bewegung mehr kam. Danach geht der Tracker ohne eigene Meldung wieder in den normalen Takt.
//
// Den Weg zum Empfänger lernt der Tracker wie der Pegel-Sender: ohne Pfad geht die REQ geflutet raus und der
// Empfänger antwortet mit einem Path-Return; danach direkt. Bleibt eine direkte Antwort aus, wird der Pfad
// verworfen und dieselbe REQ einmal geflutet wiederholt; bleibt auch die unbeantwortet, wartet der Rest bis zur
// nächsten Sitzung.

#include <Arduino.h>
#include <SPI.h>
#include <Wire.h>
#include <Mesh.h>
#include <InternalFileSystem.h>
#include <helpers/ArduinoHelpers.h>
#include <helpers/StaticPoolPacketManager.h>
#include <helpers/SimpleMeshTables.h>
#include <target.h>

#include "tracker_packet.h"
#include "trk_queue.h"
#include "clock.h"
#include "gnss.h"
#include "imu.h"
#include TRACKER_SECRETS

using namespace Adafruit_LittleFS_Namespace;

extern SPIClass LoRaSPI;   // tracker_target.cpp

#define FIX_TIMEOUT_COLD_MS   600000UL   // erster Fix überhaupt (Almanach und Bahndaten fehlen noch)
#define FIX_TIMEOUT_MS        90000UL
#define FIX_SETTLE_MS         10000UL    // nach dem ersten Fix so lange auf einen besseren warten
#define FIX_GOOD_HDOP_X10     20         // HDOP <= 2,0 mit mind. 5 Satelliten: sofort nehmen
#define REPLY_DIRECT_MS       10000UL
#define REPLY_FLOOD_MS        30000UL
#define ALARM_QUIET_MS        30000UL    // Alarm endet 30 s nach der letzten Bewegung
#define MIN_SLEEP_MS          5000UL
#define MAX_BATCHES           8          // höchstens so viele REQs je Sitzung (Rückstand: Rest beim nächsten Mal)
#define BATT_CHANGE_MV        25         // Akkustand nur mitschicken, wenn er sich mindestens so stark ändert,
#define BATT_REFRESH_S        86400UL    // ... nach neuen Einstellungen (neuer Empfänger/Server) oder spätestens täglich

#define CTR_FILE       "/trk_ctr"
#define SET_FILE       "/trk_set"
#define CTR_SAVE_STEP  256

#define RET_MAGIC      0x54524B32UL   // "TRK2"
#define QUEUE_MAGIC    0x54525131UL   // "TRQ1"

static bool due(uint32_t now, uint32_t t) { return (int32_t)(now - t) >= 0; }

// Log-Ringpuffer im RAM, der System OFF übersteht; per SWD auslesbar (tools/tracker_log.sh), weil die
// USB-Brücke des Boards oft hängen bleibt. trk_log_pos zählt fortlaufend, die Position im Puffer ist pos % Größe.
#define TRK_LOG_SIZE 2048
extern "C" {
__attribute__((section(".noinit"), used)) char trk_log[TRK_LOG_SIZE];
__attribute__((section(".noinit"), used)) uint32_t trk_log_pos;
__attribute__((section(".noinit"), used)) uint32_t trk_log_magic;
}

// Log über die USB-Brücke (nicht blockierend, kurz: lange Ausgaben bringen die Brücke zum Stehen) und in den Ringpuffer.
static void logf(const char* fmt, ...) {
  char buf[96];
  va_list args;
  va_start(args, fmt);
  int n = vsnprintf(buf, sizeof(buf), fmt, args);
  va_end(args);
  if (n <= 0) return;
  if (n >= (int)sizeof(buf)) n = sizeof(buf) - 1;
  if (trk_log_magic != 0x4C4F4721UL) {
    trk_log_magic = 0x4C4F4721UL;
    trk_log_pos = 0;
    memset(trk_log, 0, sizeof(trk_log));
  }
  char stamp[12];
  int sn = snprintf(stamp, sizeof(stamp), "%lu ", (unsigned long)(millis() / 1000));
  for (int i = 0; i < sn; i++) trk_log[trk_log_pos++ % TRK_LOG_SIZE] = stamp[i];
  for (int i = 0; i < n; i++) trk_log[trk_log_pos++ % TRK_LOG_SIZE] = buf[i];
  if (Serial.availableForWrite() < n) return;
  Serial.write((const uint8_t*)buf, n);
}

// Zustand über System OFF hinweg. Wird beim Kaltstart (Prüfsumme falsch) aus dem Flash neu aufgebaut.
struct Retained {
  uint32_t magic;
  uint32_t counter;
  TrackerSettings settings;
  uint8_t path[MAX_PATH_SIZE];
  uint8_t path_len;
  uint8_t have_path;
  uint8_t batt_valid;
  uint16_t batt_mv;
  uint8_t had_fix;       // seit dem Kaltstart schon einmal einen Fix gehabt (danach reicht der kurze Timeout)
  uint8_t cold_tries;    // Sitzungen ohne jeden Fix seit dem Kaltstart
  uint32_t clock_base;   // Uhr = GRTC-Sekunden + clock_base (springt der GRTC zurück, bleibt die Uhr monoton)
  uint32_t last_clock;   // zuletzt gelesene Uhrzeit
  uint32_t batt_sent_s;  // Uhrzeit des letzten quittierten Akkustands
  uint32_t check;
};
__attribute__((section(".noinit"))) static Retained ret;

// Warteschlange: eigene Prüfsumme, damit nicht jede kleine Zustandsänderung 24 KB durchrechnet.
__attribute__((section(".noinit"))) static TrackerQueue queue;
__attribute__((section(".noinit"))) static uint32_t queue_magic;
__attribute__((section(".noinit"))) static uint32_t queue_check;

static uint32_t fnv(const void* data, size_t len, uint32_t h = 2166136261UL) {
  const uint8_t* p = (const uint8_t*)data;
  for (size_t i = 0; i < len; i++) h = (h ^ p[i]) * 16777619UL;
  return h;
}

static uint32_t retChecksum() { return fnv(&ret, offsetof(Retained, check)); }
static void retSeal() { ret.check = retChecksum(); }
static bool retValid() { return ret.magic == RET_MAGIC && ret.check == retChecksum(); }

static uint32_t queueChecksum() {
  uint32_t h = fnv(&queue, offsetof(TrackerQueue, rec));
  for (int i = 0; i < queue.count; i++) h = fnv(&trkq_at(queue, i), sizeof(QueuedRecord), h);
  return h;
}
static void queueSeal() {
  queue_magic = QUEUE_MAGIC;
  queue_check = queueChecksum();
}
static bool queueValid() { return queue_magic == QUEUE_MAGIC && trkq_valid(queue) && queue_check == queueChecksum(); }

static bool loadFile(const char* name, void* data, size_t len) {
  auto f = InternalFS.open(name, FILE_O_READ);
  if (!f) return false;
  bool ok = f.read((uint8_t*)data, len) == (int)len;
  f.close();
  return ok;
}

static void saveFile(const char* name, const void* data, size_t len) {
  InternalFS.remove(name);
  auto f = InternalFS.open(name, FILE_O_WRITE);
  if (f) {
    f.write((const uint8_t*)data, len);
    f.close();
  }
}

/** Uhr in Sekunden, monoton über System OFF und GRTC-Neustarts hinweg. */
static uint32_t clockNow() {
  uint32_t g = grtc_seconds();
  if (g + ret.clock_base < ret.last_clock) ret.clock_base = ret.last_clock - g;   // GRTC neu gestartet
  ret.last_clock = g + ret.clock_base;
  return ret.last_clock;
}

class TrackerMesh : public mesh::Mesh {
  mesh::Identity receiver;
  uint8_t secret[PUB_KEY_SIZE];
  mesh::PacketManager& mgr;

  // Sitzung
  uint32_t session_start = 0;
  uint32_t fix_deadline = 0;
  uint32_t first_fix_ms = 0;
  uint32_t fix_ms = 0;
  NmeaFix best = {};
  bool have_fix = false;
  uint8_t max_sats = 0;        // Diagnose: meiste Satelliten in einem GGA dieser Sitzung
  bool fix_done = false;       // Warten auf den Fix ist für den nächsten Eintrag beendet
  bool normal_done = false;    // der eine Eintrag einer normalen Sitzung ist angelegt
  bool alarm_active = false;
  bool motion_event = false;   // nächster Eintrag ist der Alarmbeginn
  uint32_t last_motion = 0;
  uint32_t next_alarm_report = 0;

  // Senden
  int batches = 0;             // REQs dieser Sitzung
  bool send_failed = false;    // eine REQ blieb unbeantwortet: Rest bis zur nächsten Sitzung liegen lassen
  bool awaiting = false;
  bool flood_retry_done = false;
  uint32_t reply_deadline = 0;
  uint8_t tag[TRK_TAG_LEN];
  uint8_t out[TRK_UP_MAX_LEN];
  int out_len = 0;
  int out_records = 0;         // so viele der neuesten Einträge stecken in der ausstehenden REQ
  uint16_t out_batt_mv = 0;
  bool out_has_batt = false;

  void coldInit() {
    memset(&ret, 0, sizeof(ret));
    ret.magic = RET_MAGIC;
    uint32_t c = 0;
    loadFile(CTR_FILE, &c, sizeof(c));
    ret.counter = c + CTR_SAVE_STEP;   // über evtl. ungespeicherte Zählerstände springen
    saveFile(CTR_FILE, &ret.counter, sizeof(ret.counter));
    TrackerSettings s;
    if (loadFile(SET_FILE, &s, sizeof(s)) && trk_settings_valid(s)) ret.settings = s;
    else ret.settings = trk_default_settings();
    retSeal();
  }

  void applySettings(const TrackerSettings& s) {
    // Nach Inhalt vergleichen, nicht nur nach Version: Versionen aus verschiedenen Quellen (API, Test per tset)
    // können gleich lauten und doch andere Werte meinen.
    const TrackerSettings& c = ret.settings;
    if (s.version == 0 || (s.version == c.version && s.interval == c.interval && s.alarm == c.alarm &&
                           s.alarm_interval == c.alarm_interval)) {
      return;
    }
    bool alarm_changed = s.alarm != ret.settings.alarm;
    ret.settings = s;
    ret.batt_valid = 0;   // die Gegenseite ist evtl. neu: Akkustand mit der nächsten REQ schicken
    retSeal();
    saveFile(SET_FILE, &s, sizeof(s));
    logf("settings v%u: iv=%lus alarm=%u alarm_iv=%lus\n", s.version, (unsigned long)trk_interval_s(s.interval), s.alarm,
         (unsigned long)trk_interval_s(s.alarm_interval));
    if (alarm_changed) {
      imu_configure(s.alarm);
      if (s.alarm == TRK_ALARM_OFF && alarm_active) {
        alarm_active = false;   // Alarm abgeschaltet: laufenden Alarm beenden
      }
    }
  }

  void onReply(const uint8_t* data, size_t len) {
    if (!awaiting) return;
    TrackerSettings s;
    if (!trk_decode_settings(data, (int)len, tag, s)) return;
    awaiting = false;
    trkq_drop_newest(queue, out_records);
    queueSeal();
    if (out_has_batt) {
      ret.batt_valid = 1;
      ret.batt_mv = out_batt_mv;
      ret.batt_sent_s = clockNow();
    }
    retSeal();
    logf("ack %d, left %u, settings v%u\n", out_records, queue.count, s.version);
    applySettings(s);
  }

  /** Legt einen Eintrag für jetzt an (mit der besten Position dieser Sitzung, falls vorhanden). */
  void addRecord() {
    QueuedRecord r;
    memset(&r, 0, sizeof(r));
    uint32_t now_s = clockNow();
    r.t_s = now_s;
    if (have_fix) {
      r.flags |= TRK_R_FIX;
      r.lat_e7 = best.lat_e7;
      r.lon_e7 = best.lon_e7;
      r.alt_m = best.alt_m;
      r.sats = best.sats;
      r.hdop_x10 = best.hdop_x10;
      r.t_s = now_s - (millis() - fix_ms) / 1000;   // Zeitpunkt des Fixes
    }
    if (alarm_active) r.flags |= TRK_R_ALARM;
    if (motion_event) r.flags |= TRK_R_MOTION;
    motion_event = false;
    // Ein unquittierter Eintrag ohne Position und ohne Bewegung sagt nichts mehr, sobald ein neuer kommt: ersetzen.
    QueuedRecord* last = trkq_newest(queue);
    if (last && !(last->flags & (TRK_R_FIX | TRK_R_MOTION))) trkq_drop_newest(queue, 1);
    r.counter = ++ret.counter;
    if (ret.counter % CTR_SAVE_STEP == 0) saveFile(CTR_FILE, &ret.counter, sizeof(ret.counter));
    retSeal();
    trkq_push(queue, r);
    queueSeal();
    logf("rec #%lu fix=%d alarm=%d motion=%d queued=%u\n", (unsigned long)r.counter, have_fix ? 1 : 0,
         (r.flags & TRK_R_ALARM) ? 1 : 0, (r.flags & TRK_R_MOTION) ? 1 : 0, queue.count);
  }

  /** Schickt die neuesten noch nicht quittierten Einträge als eine REQ. */
  void sendBatch() {
    TrackerHead h;
    memset(&h, 0, sizeof(h));
    h.settings_version = ret.settings.version;
    if (alarm_active) h.flags |= TRK_F_ALARM;
    if (board.isChargerActive()) h.flags |= TRK_F_CHARGING;
    if (board.isUsbPowered()) h.flags |= TRK_F_USB;
    uint16_t mv = board.getBattMilliVolts();
    out_has_batt = mv > 0 && (!ret.batt_valid || abs((int)mv - (int)ret.batt_mv) >= BATT_CHANGE_MV ||
                              clockNow() - ret.batt_sent_s >= BATT_REFRESH_S);
    if (out_has_batt) {
      h.flags |= TRK_F_BATT;
      h.batt_mv = mv;
      out_batt_mv = mv;
    }
    QueuedRecord q[TRK_MAX_RECORDS];
    int n = trkq_take_newest(queue, TRK_MAX_RECORDS, q);
    TrackerRecord rec[TRK_MAX_RECORDS];
    uint32_t now_s = clockNow();
    for (int i = 0; i < n; i++) {
      memset(&rec[i], 0, sizeof(rec[i]));
      rec[i].counter = q[i].counter;
      rec[i].flags = q[i].flags;
      rec[i].age_s = now_s - q[i].t_s;
      rec[i].lat_e7 = q[i].lat_e7;
      rec[i].lon_e7 = q[i].lon_e7;
      rec[i].alt_m = q[i].alt_m;
      rec[i].sats = q[i].sats;
      rec[i].hdop_x10 = q[i].hdop_x10;
    }
    retSeal();
    getRNG()->random(tag, TRK_TAG_LEN);
    out_len = trk_encode_uplink(tag, h, rec, n, out, out_records);
    batches++;
    flood_retry_done = false;
    logf("req %d: %d rec (#%lu..), bat=%u\n", batches, out_records, (unsigned long)q[0].counter, out_has_batt ? mv : 0);
    transmit();
  }

  void transmit() {
    mesh::Packet* pkt = createDatagram(PAYLOAD_TYPE_REQ, receiver, secret, out, out_len);
    if (!pkt) {
      logf("req too long (%d)\n", out_len);
      send_failed = true;
      return;
    }
    if (ret.have_path) {
      sendDirect(pkt, ret.path, ret.path_len);
      reply_deadline = millis() + REPLY_DIRECT_MS;
    } else {
      sendFlood(pkt);
      reply_deadline = millis() + REPLY_FLOOD_MS;
    }
    awaiting = true;
  }

  void checkReplyTimeout(uint32_t now) {
    if (!awaiting || !due(now, reply_deadline)) return;
    awaiting = false;
    if (ret.have_path) {
      ret.have_path = 0;
      retSeal();
      logf("no ack on path, path dropped\n");
      if (!flood_retry_done) {
        flood_retry_done = true;
        transmit();   // dieselbe REQ einmal geflutet
        return;
      }
    }
    logf("no ack, %u queued\n", queue.count);
    send_failed = true;
  }

  /** Noch Einträge zu schicken und in dieser Sitzung erlaubt? */
  bool canSendMore() const { return queue.count > 0 && !send_failed && batches < MAX_BATCHES; }

  void resetFixWait(uint32_t now, uint32_t timeout) {
    fix_done = false;
    fix_deadline = now + timeout;
  }

  void startAlarm(uint32_t now) {
    alarm_active = true;
    motion_event = true;
    last_motion = now;
    next_alarm_report = now;   // sofort melden, auch ohne Fix: der Alarm soll schnell ankommen
    send_failed = false;       // ein Alarm verdient einen neuen Versuch
    gnss_power(true);
    logf("motion: alarm\n");
  }

  void goToSleep() {
    uint32_t now = millis();
    uint32_t interval_ms = trk_interval_s(ret.settings.interval) * 1000UL;
    uint32_t spent = now - session_start;
    uint32_t sleep_ms = spent + MIN_SLEEP_MS < interval_ms ? interval_ms - spent : MIN_SLEEP_MS;
    gnss_power(false);
    radio_driver.powerOff();
    bool alarm_on = ret.settings.alarm != TRK_ALARM_OFF;
    imu_configure(ret.settings.alarm);   // ein noch gehaltener Interrupt (Bewegung eben) weckt sofort wieder: gewollt
    imu_arm_wakeup(alarm_on);
    clockNow();
    retSeal();
    queueSeal();
    // Laufende DMA-Empfänger (GNSS-UART) und Busse beenden, sonst bricht der Core System OFF ab (Stufe 2).
    Serial1.end();
    Wire1.end();
    LoRaSPI.end();
    logf("sleep %lus, %u queued\n", (unsigned long)(sleep_ms / 1000), queue.count);
    Serial.flush();
    delay(20);
    const uint32_t spin = 200000;
    bool qs = nrf54_core_quiesce_serial_for_system_off(spin), qp = nrf54_core_quiesce_spi_for_system_off(spin),
         qw = nrf54_core_quiesce_wire_for_system_off(spin), qa = nrf54_core_quiesce_analog_for_system_off(spin);
    if (!(qs && qp && qw && qa)) logf("quiesce serial=%d spi=%d wire=%d analog=%d\n", qs, qp, qw, qa);
    delaySystemOff(sleep_ms);
  }

protected:
  int searchPeersByHash(const uint8_t* hash) override { return receiver.isHashMatch(hash) ? 1 : 0; }

  void getPeerSharedSecret(uint8_t* dest_secret, int peer_idx) override { memcpy(dest_secret, secret, PUB_KEY_SIZE); }

  bool onPeerPathRecv(mesh::Packet* packet, int sender_idx, const uint8_t* secret, uint8_t* path, uint8_t path_len,
                      uint8_t extra_type, uint8_t* extra, uint8_t extra_len) override {
    ret.path_len = mesh::Packet::copyPath(ret.path, path, path_len);
    ret.have_path = 1;
    retSeal();
    logf("path learned: %u hop(s)\n", (unsigned)(path_len & 63));
    if (extra_type == PAYLOAD_TYPE_RESPONSE) onReply(extra, extra_len);
    return true;
  }

  void onPeerDataRecv(mesh::Packet* packet, uint8_t type, int sender_idx, const uint8_t* secret, uint8_t* data,
                      size_t len) override {
    if (type == PAYLOAD_TYPE_RESPONSE) onReply(data, len);
  }

public:
  TrackerMesh(mesh::Radio& radio, mesh::RNG& rng, mesh::RTCClock& rtc, SimpleMeshTables& tables, mesh::PacketManager& m)
    : mesh::Mesh(radio, *new ArduinoMillis(), rng, rtc, m, tables), receiver(TRACKER_RECEIVER_PUB), mgr(m) { }

  void begin(bool motion_wake) {
    bool warm = retValid();
    if (!warm) coldInit();
    if (!queueValid()) {
      trkq_clear(queue);
      queueSeal();
    }
    self_id = mesh::LocalIdentity(TRACKER_PRV, TRACKER_PUB);
    self_id.calcSharedSecret(secret, receiver);
    mesh::Mesh::begin();

    uint32_t now = millis();
    session_start = now;
    imu_configure(ret.settings.alarm);
    gnss_power(true);
    // Ohne je einen Fix (keine Bahndaten): die ersten Versuche lang, danach nicht mehr den Akku leersuchen.
    resetFixWait(now, ret.had_fix ? FIX_TIMEOUT_MS : ret.cold_tries < 3 ? FIX_TIMEOUT_COLD_MS : FIX_TIMEOUT_MS * 2);
    if (motion_wake && ret.settings.alarm != TRK_ALARM_OFF) startAlarm(now);
    logf("tracker %s %s, iv=%lus alarm=%u ctr=%lu queued=%u clock=%lu\n", TRACKER_NAME, warm ? "warm" : "cold",
         (unsigned long)trk_interval_s(ret.settings.interval), ret.settings.alarm, (unsigned long)ret.counter,
         queue.count, (unsigned long)clockNow());
    retSeal();
  }

  void loop() {
    mesh::Mesh::loop();
    uint32_t now = millis();

    NmeaFix f;
    bool got = gnss_poll(f);
    if (got && f.sats > max_sats) max_sats = f.sats;
    if (got && f.valid) {
      if (!have_fix || f.hdop_x10 <= best.hdop_x10 || now - fix_ms > 5000) {
        best = f;
        fix_ms = now;
      }
      if (!have_fix) {
        first_fix_ms = now;
        logf("fix: %u sats hdop %u.%u\n", f.sats, f.hdop_x10 / 10, f.hdop_x10 % 10);
      }
      have_fix = true;
      if (!ret.had_fix) {
        ret.had_fix = 1;
        retSeal();
      }
    }
    if (!fix_done) {
      bool good = have_fix && best.hdop_x10 <= FIX_GOOD_HDOP_X10 && best.sats >= 5;
      bool settled = have_fix && due(now, first_fix_ms + FIX_SETTLE_MS);
      if (good || settled || due(now, fix_deadline)) {
        fix_done = true;
        if (!have_fix) {
          logf("no fix (gnss %s, max %u sats)\n", gnss_alive() ? "ok" : "silent", max_sats);
          if (!ret.had_fix && ret.cold_tries < 255) {
            ret.cold_tries++;
            retSeal();
          }
        }
      }
    }

    if (ret.settings.alarm != TRK_ALARM_OFF && imu_take_motion()) {
      if (!alarm_active) startAlarm(now);
      last_motion = now;
    }
    if (alarm_active && due(now, last_motion + ALARM_QUIET_MS)) {
      alarm_active = false;
      logf("alarm over\n");
    }

    checkReplyTimeout(now);

    if (!awaiting) {
      if (alarm_active && due(now, next_alarm_report) && (motion_event || fix_done)) {
        addRecord();
        next_alarm_report = now + trk_interval_s(ret.settings.alarm_interval) * 1000UL;
        resetFixWait(now, FIX_TIMEOUT_MS);
        normal_done = true;   // die Alarmeinträge ersetzen den normalen Eintrag dieser Sitzung
        batches = 0;          // neuer Eintrag: wieder volles Kontingent an REQs
        sendBatch();
      } else if (!alarm_active && !normal_done && fix_done) {
        normal_done = true;
        addRecord();
        sendBatch();
      } else if (normal_done && canSendMore()) {
        sendBatch();          // Rückstand nachreichen
      } else if (normal_done && !alarm_active && mgr.getOutboundTotal() == 0) {
        goToSleep();
      }
    }
    board.loop();
  }
};

StdRNG fast_rng;
SimpleMeshTables tables;
StaticPoolPacketManager pkt_mgr(16);
TrackerMesh the_mesh(radio_driver, fast_rng, rtc_clock, tables, pkt_mgr);

void setup() {
  Serial.begin(115200);
  board.begin();
  bool motion_wake = imu_begin() && imu_take_motion();
  gnss_begin();
  if (!radio_init()) {
    while (1) {
      logf("radio init failed\n");
      delay(2000);
    }
  }
  fast_rng.begin(radio_driver.getRngSeed());
  InternalFS.begin();
#ifdef TRACKER_DIAG
  delay(1500);
  logf("diag: reset=0x%lx offabort=%lu imu=%d grtc=%lu\n", (unsigned long)nrf54ResetReason(),
       (unsigned long)nrf54SystemOffAbortStage(), motion_wake ? 1 : 0, (unsigned long)grtc_seconds());
  nrf54ClearSystemOffAbortStage();
  {
    char d[96];
    imu_diag(d, sizeof(d));
    logf("diag: %s\n", d);
  }
#endif
  the_mesh.begin(motion_wake);
}

void loop() {
  the_mesh.loop();
  rtc_clock.tick();
}
