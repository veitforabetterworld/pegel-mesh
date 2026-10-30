#include "sc16is740.h"

#include <Arduino.h>
#include <Wire.h>

#ifndef PEGEL_UART_I2C_ADDR
  #define PEGEL_UART_I2C_ADDR  0x48   // A0 = A1 = VDD
#endif
#define XTAL_HZ  14745600UL

// Register (Datenblatt Tabelle 10); die I²C-Unteradresse ist Register << 3, Kanal 0.
#define REG_RHR_THR  0x00
#define REG_IER      0x01
#define REG_FCR      0x02
#define REG_EFR      0x02   // nur bei LCR = 0xBF
#define REG_LCR      0x03
#define REG_LSR      0x05
#define REG_SPR      0x07
#define REG_TXLVL    0x08
#define REG_RXLVL    0x09
#define REG_EFCR     0x0F
#define REG_DLL      0x00   // nur bei LCR[7] = 1
#define REG_DLH      0x01

#define LSR_TX_EMPTY  0x40   // THR und Schieberegister leer
#define EFCR_RTSCON   0x10   // Sender steuert RTS (RS-485)
#define EFCR_RTSINVER 0x20   // RTS = 1 beim Senden
#define IER_SLEEP     0x10
#define EFR_ENHANCED  0x10

namespace sc16is740 {

static void writeReg(uint8_t reg, uint8_t value) {
  Wire.beginTransmission(PEGEL_UART_I2C_ADDR);
  Wire.write(reg << 3);
  Wire.write(value);
  Wire.endTransmission();
}

static int readReg(uint8_t reg) {
  Wire.beginTransmission(PEGEL_UART_I2C_ADDR);
  Wire.write(reg << 3);
  if (Wire.endTransmission(false) != 0) return -1;
  if (Wire.requestFrom((uint8_t)PEGEL_UART_I2C_ADDR, (uint8_t)1) != 1) return -1;
  return Wire.read();
}

bool begin(uint32_t baud) {
  Wire.begin();
  writeReg(REG_SPR, 0x5A);
  if (readReg(REG_SPR) != 0x5A) return false;

  writeReg(REG_LCR, 0xBF);   // EFR erreichbar: erweiterte Funktionen (Sleep) freigeben
  writeReg(REG_EFR, EFR_ENHANCED);
  uint16_t div = (uint16_t)((XTAL_HZ + 8UL * baud) / (16UL * baud));
  writeReg(REG_LCR, 0x80);   // Teiler erreichbar
  writeReg(REG_DLL, (uint8_t)div);
  writeReg(REG_DLH, (uint8_t)(div >> 8));
  writeReg(REG_LCR, 0x03);   // 8N1
  writeReg(REG_FCR, 0x07);   // FIFOs an und leeren
  writeReg(REG_EFCR, EFCR_RTSCON | EFCR_RTSINVER);
  writeReg(REG_IER, 0);
  return true;
}

void write(const uint8_t* data, int len) {
  writeReg(REG_IER, 0);   // aufwecken
  while (len > 0) {
    int room = readReg(REG_TXLVL);
    if (room <= 0) continue;
    int n = min(min(room, len), 30);   // Wire-Puffer: 32 Byte inkl. Unteradresse
    Wire.beginTransmission(PEGEL_UART_I2C_ADDR);
    Wire.write(REG_RHR_THR << 3);
    Wire.write(data, n);
    Wire.endTransmission();
    data += n;
    len -= n;
  }
  uint32_t start = millis();
  while (!(readReg(REG_LSR) & LSR_TX_EMPTY) && millis() - start < 100) { }
}

int read() {
  if (readReg(REG_RXLVL) <= 0) return -1;
  return readReg(REG_RHR_THR);
}

void flushRx() {
  writeReg(REG_FCR, 0x03);   // RX-FIFO leeren, FIFOs bleiben an
}

void sleep() {
  writeReg(REG_IER, IER_SLEEP);
}

}
