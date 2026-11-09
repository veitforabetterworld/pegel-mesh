#include <Arduino.h>
#include <Wire.h>
#include "imu.h"
#include "tracker_packet.h"

#define LSM_WHO_AM_I      0x0F
#define LSM_WHO_AM_I_VAL  0x6A
#define LSM_INT1_CTRL     0x0D
#define LSM_INT2_CTRL     0x0E
#define LSM_CTRL1_XL      0x10
#define LSM_CTRL2_G       0x11
#define LSM_CTRL3_C       0x12
#define LSM_CTRL6_C       0x15
#define LSM_WAKE_UP_SRC   0x1B
#define LSM_TAP_CFG       0x58
#define LSM_WAKE_UP_THS   0x5B
#define LSM_WAKE_UP_DUR   0x5C
#define LSM_MD1_CFG       0x5E

#define IMU_INT_PORT_PIN  6   // P0.06 (Arduino-Pin PIN_IMU_INT)

static uint8_t addr = 0;

static bool wr(uint8_t reg, uint8_t val) {
  Wire1.beginTransmission(addr);
  Wire1.write(reg);
  Wire1.write(val);
  return Wire1.endTransmission() == 0;
}

static bool rd(uint8_t reg, uint8_t& val) {
  Wire1.beginTransmission(addr);
  Wire1.write(reg);
  if (Wire1.endTransmission(false) != 0) return false;
  if (Wire1.requestFrom(addr, (uint8_t)1) != 1) return false;
  val = Wire1.read();
  return true;
}

bool imu_begin() {
  pinMode(PIN_IMU_CS, OUTPUT);
  digitalWrite(PIN_IMU_CS, HIGH);   // HIGH = I2C-Modus
  pinMode(PIN_IMU_INT, INPUT);
  Wire1.begin();
  static const uint8_t candidates[] = { 0x6A, 0x6B };
  for (uint8_t a : candidates) {
    addr = a;
    uint8_t who = 0;
    if (rd(LSM_WHO_AM_I, who) && who == LSM_WHO_AM_I_VAL) return true;
  }
  addr = 0;
  return false;
}

bool imu_configure(uint8_t level) {
  if (!addr) return false;
  // Schwelle in Schritten von FS/64 = 31,25 mg bei ±2 g.
  uint8_t ths;
  switch (level) {
    // Der Slope-Filter vergleicht aufeinanderfolgende Messwerte (26 Hz, also 38 ms Abstand): ruhiges Hochheben
    // erreicht oft nur 0,1 bis 0,2 g. Rauschen im Low-Power-Modus liegt bei wenigen mg.
    case TRK_ALARM_LOW:    ths = 6;  break;   // ~190 mg: deutliches Bewegen, Tragen
    case TRK_ALARM_MEDIUM: ths = 3;  break;   // ~94 mg: Hochheben, Verschieben
    case TRK_ALARM_HIGH:   ths = 1;  break;   // ~31 mg: schon leichtes Anstoßen
    default:               ths = 0;  break;
  }
  // Steht diese Konfiguration schon im Sensor (er läuft auch in System OFF weiter), nichts neu schreiben:
  // ein Neustart der Messung erzeugt einen Sprung im Slope-Filter und damit einen Fehlalarm.
  uint8_t cur_xl = 0xFF, cur_ths = 0xFF, cur_md1 = 0xFF, cur_i1 = 0xFF, cur_i2 = 0xFF;
  if (rd(LSM_CTRL1_XL, cur_xl) && rd(LSM_WAKE_UP_THS, cur_ths) && rd(LSM_MD1_CFG, cur_md1) && rd(LSM_INT1_CTRL, cur_i1) &&
      rd(LSM_INT2_CTRL, cur_i2)) {
    bool same = cur_i1 == 0 && cur_i2 == 0 &&
                (ths ? (cur_xl == 0x20 && (cur_ths & 0x3F) == ths && cur_md1 == 0x20) : (cur_xl == 0x00 && cur_md1 == 0x00));
    if (same) return true;
  }
  // INT1_CTRL/INT2_CTRL: keine Data-Ready-Interrupts. Der Sensor wird nie stromlos, Einstellungen einer früheren
  // Firmware (die Seeed-Demo legt Data-Ready auf INT1) bleiben sonst stehen und halten INT1 dauernd aktiv.
  bool ok = wr(LSM_INT1_CTRL, 0x00) && wr(LSM_INT2_CTRL, 0x00)
         && wr(LSM_CTRL3_C, 0x44)          // BDU, Adress-Autoinkrement
         && wr(LSM_CTRL2_G, 0x00);         // Gyroskop aus
  if (!ths) {
    ok = ok && wr(LSM_MD1_CFG, 0x00) && wr(LSM_TAP_CFG, 0x00) && wr(LSM_CTRL1_XL, 0x00);   // alles aus
    uint8_t src;
    rd(LSM_WAKE_UP_SRC, src);
    return ok;
  }
  ok = ok && wr(LSM_CTRL6_C, 0x10)         // XL_HM_MODE: Low-Power statt High-Performance
          && wr(LSM_CTRL1_XL, 0x20)        // 26 Hz, ±2 g
          && wr(LSM_WAKE_UP_DUR, 0x00)     // ein Messwert über der Schwelle genügt
          && wr(LSM_WAKE_UP_THS, ths)
          && wr(LSM_TAP_CFG, 0x81)         // Interrupts an, Slope-Filter, Interrupt gehalten (LIR)
          && wr(LSM_MD1_CFG, 0x20);        // Wake-up auf INT1
  delay(200);                              // ~5 Messwerte: der Einschaltsprung des Filters ist durch
  uint8_t src;
  rd(LSM_WAKE_UP_SRC, src);                // dadurch ausgelösten Interrupt verwerfen
  return ok;
}

bool imu_take_motion() {
  if (!addr || digitalRead(PIN_IMU_INT) == LOW) return false;
  uint8_t src = 0;
  rd(LSM_WAKE_UP_SRC, src);   // Lesen setzt den gehaltenen Interrupt zurück
  return true;
}

void imu_diag(char* buf, int len) {
  uint8_t src = 0xFF, xl = 0xFF, md1 = 0xFF, ths = 0xFF;
  int pin_before = digitalRead(PIN_IMU_INT);
  int p0 = (int)((NRF_P0->IN >> IMU_INT_PORT_PIN) & 1U);
  rd(LSM_WAKE_UP_SRC, src);
  rd(LSM_CTRL1_XL, xl);
  rd(LSM_MD1_CFG, md1);
  rd(LSM_WAKE_UP_THS, ths);
  int pin_after = digitalRead(PIN_IMU_INT);
  uint8_t int1ctrl = 0xFF;
  rd(LSM_INT1_CTRL, int1ctrl);
  snprintf(buf, len, "imu %02x int=%d/%d p0=%d src=%02x xl=%02x md1=%02x ths=%02x i1c=%02x", addr, pin_before, pin_after,
           p0, src, xl, md1, ths, int1ctrl);
}

void imu_arm_wakeup(bool enable) {
  uint32_t cnf = (GPIO_PIN_CNF_DIR_Input << GPIO_PIN_CNF_DIR_Pos) | (GPIO_PIN_CNF_INPUT_Connect << GPIO_PIN_CNF_INPUT_Pos) |
                 (GPIO_PIN_CNF_PULL_Pulldown << GPIO_PIN_CNF_PULL_Pos);
  if (enable) cnf |= (GPIO_PIN_CNF_SENSE_High << GPIO_PIN_CNF_SENSE_Pos);
  NRF_P0->PIN_CNF[IMU_INT_PORT_PIN] = cnf;
}
