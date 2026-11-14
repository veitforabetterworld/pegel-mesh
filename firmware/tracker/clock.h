#pragma once
// Uhr des Trackers: der GRTC-Systemzähler (1 MHz) des nRF54. Er läuft in System OFF weiter (er weckt den Chip
// ja auch) und wird beim Aufwachen nicht zurückgesetzt, nur beim Einschalten. Damit stimmen die Zeitstempel der
// zwischengespeicherten Einträge auch dann, wenn eine Bewegung den Tracker früher als geplant weckt.

#include <stdint.h>

/** Sekunden seit dem Start des GRTC (Einschalten). */
uint32_t grtc_seconds();
