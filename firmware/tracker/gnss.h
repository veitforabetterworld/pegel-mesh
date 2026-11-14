#pragma once
// L76K-GNSS (Seeed 109100021) an der XIAO-UART: Serial1 auf D6 (TX) / D7 (RX), 9600 Baud.
// D0 ist der Standby-Pin: HIGH = in Betrieb, LOW = Standby (Uhr und Bahndaten bleiben, Neustart in Sekunden).

#include <stdint.h>
#include "nmea.h"

#define GNSS_STANDBY_PIN  PIN_D0

void gnss_begin();
void gnss_power(bool on);
bool gnss_is_on();
/** Liest die UART leer. true, wenn ein neuer GGA-Satz kam; fix ist dann der neue Stand. */
bool gnss_poll(NmeaFix& fix);
/** Seit gnss_power(true) überhaupt ein gültiger NMEA-Satz empfangen? (Diagnose: Modul steckt und spricht) */
bool gnss_alive();
/** Diagnose: Anzahl empfangener Rohbytes, Standby-Pin direkt setzen. */
uint32_t gnss_bytes();
void gnss_set_pin_raw(bool high);
