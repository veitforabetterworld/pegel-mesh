#pragma once
// Bewegungserkennung mit dem LSM6DS3TR-C des XIAO nRF54LM20A Sense (I2C an Wire1, INT1 an P0.06).
//
// Der Beschleunigungssensor läuft im Low-Power-Modus mit 26 Hz und löst bei einer Änderung über der
// Schwelle (Wake-up, Slope-Filter, also ohne Erdbeschleunigung) einen gehaltenen Interrupt auf INT1 aus.
// INT1 weckt den nRF54 auch aus System OFF (GPIO-Sense).

#include <stdint.h>

bool imu_begin();
/** Stellt die Empfindlichkeit ein (TRK_ALARM_*); TRK_ALARM_OFF schaltet den Sensor ab. Ist der Sensor schon so
 *  eingestellt, bleibt er unberührt (ein gehaltener Interrupt bleibt dann erhalten). */
bool imu_configure(uint8_t alarm_level);
/** true, wenn seit dem letzten Aufruf eine Bewegung erkannt wurde; setzt den Interrupt zurück. */
bool imu_take_motion();
/** INT1 als Weckquelle für System OFF einrichten (nur bei eingeschaltetem Alarm sinnvoll). */
void imu_arm_wakeup(bool enable);
/** Diagnose: Pegel des INT-Pins und die wichtigsten Register als Text. */
void imu_diag(char* buf, int len);
