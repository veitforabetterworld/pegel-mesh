#pragma once
// SC16IS740: UART hinter I²C (Trägerplatine pegel-sender v1, Adresse 0x48, Quarz 14,7456 MHz).
// RTS steuert DE/RE des MAX3485 automatisch: HIGH, solange gesendet wird (EFCR RTSCON + RTSINVER).

#include <stdint.h>

namespace sc16is740 {

bool begin(uint32_t baud);          // false: Chip antwortet nicht
void write(const uint8_t* data, int len);   // kehrt zurück, wenn das letzte Bit draußen ist
int read();                         // nächstes empfangene Byte oder -1
void flushRx();
void sleep();                       // ~ 30 µA weniger; der nächste Zugriff weckt den Chip

}
