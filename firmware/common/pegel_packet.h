#pragma once
// Wertebereich eines Pegels in den Messblöcken (pegel_block.h).

#include <stdint.h>

// level_mm ab PEGEL_STATUS_BASE ist kein Pegel, sondern ein Fehlercode des Geräts (1..255):
// level_mm = PEGEL_STATUS_BASE + Code. Pegel reichen damit bis 65,279 m.
#define PEGEL_STATUS_BASE  0xFF00
#define PEGEL_LEVEL_MAX_MM (PEGEL_STATUS_BASE - 1)
