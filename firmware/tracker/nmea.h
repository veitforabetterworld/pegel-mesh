#pragma once
// Minimaler NMEA-Parser für das L76K: wertet nur GGA aus (Fix-Qualität, Position, Höhe, Satelliten, HDOP).
// Zeichenweise füttern; prüft die Prüfsumme. Ohne Hardware-Abhängigkeit, damit er am PC testbar ist.

#include <stdint.h>
#include <stdlib.h>
#include <string.h>

struct NmeaFix {
  bool valid;        // GGA mit Fix-Qualität > 0
  int32_t lat_e7;
  int32_t lon_e7;
  int16_t alt_m;
  uint8_t sats;
  uint8_t hdop_x10;  // 255 = 25,5 oder schlechter
};

class NmeaParser {
  char buf[100];
  int len = 0;
  bool in_sentence = false;

  static int hexval(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    return -1;
  }

  // "ddmm.mmmm" bzw. "dddmm.mmmm" in 1e-7 Grad.
  static bool coord(const char* s, char hemi, int32_t& out) {
    if (!*s) return false;
    const char* dot = strchr(s, '.');
    int intlen = dot ? (int)(dot - s) : (int)strlen(s);
    if (intlen < 3) return false;
    int deg_digits = intlen - 2;
    long deg = 0;
    for (int i = 0; i < deg_digits; i++) {
      if (s[i] < '0' || s[i] > '9') return false;
      deg = deg * 10 + (s[i] - '0');
    }
    double minutes = atof(s + deg_digits);
    double v = (double)deg + minutes / 60.0;
    if (hemi == 'S' || hemi == 'W') v = -v;
    out = (int32_t)(v * 1e7 + (v >= 0 ? 0.5 : -0.5));
    return true;
  }

  // Zerlegt buf (ohne '$' und '*xx') an Kommas, leere Felder bleiben erhalten.
  static int split(char* s, char* fields[], int max) {
    int n = 0;
    fields[n++] = s;
    for (char* p = s; *p && n < max; p++) {
      if (*p == ',') {
        *p = 0;
        fields[n++] = p + 1;
      }
    }
    return n;
  }

  bool handle(NmeaFix& fix) {
    // buf: "GPGGA,....*HH"
    char* star = strrchr(buf, '*');
    if (!star || star[1] == 0 || star[2] == 0) return false;
    int hi = hexval(star[1]), lo = hexval(star[2]);
    if (hi < 0 || lo < 0) return false;
    uint8_t sum = 0;
    for (char* p = buf; p < star; p++) sum ^= (uint8_t)*p;
    if (sum != (uint8_t)((hi << 4) | lo)) return false;
    *star = 0;
    if (strlen(buf) < 5 || strncmp(buf + 2, "GGA", 3) != 0) return false;

    char* f[16];
    int n = split(buf, f, 16);
    if (n < 10) return false;
    // 0 GGA, 1 Zeit, 2 Breite, 3 N/S, 4 Länge, 5 E/W, 6 Qualität, 7 Satelliten, 8 HDOP, 9 Höhe
    NmeaFix r;
    memset(&r, 0, sizeof(r));
    int quality = atoi(f[6]);
    r.sats = (uint8_t)atoi(f[7]);
    double hdop = *f[8] ? atof(f[8]) : 99.0;
    r.hdop_x10 = hdop >= 25.5 ? 255 : (uint8_t)(hdop * 10.0 + 0.5);
    double alt = atof(f[9]);
    r.alt_m = (int16_t)(alt < -32768 ? -32768 : alt > 32767 ? 32767 : alt);
    r.valid = quality > 0 && coord(f[2], *f[3], r.lat_e7) && coord(f[4], *f[5], r.lon_e7);
    fix = r;
    return true;
  }

public:
  /** Ein Zeichen verarbeiten. true, wenn damit ein gültiger GGA-Satz endete; fix enthält ihn dann (valid sagt, ob mit Fix). */
  bool feed(char c, NmeaFix& fix) {
    if (c == '$') {
      in_sentence = true;
      len = 0;
      return false;
    }
    if (!in_sentence) return false;
    if (c == '\r' || c == '\n') {
      in_sentence = false;
      buf[len] = 0;
      return handle(fix);
    }
    if (len >= (int)sizeof(buf) - 1) {
      in_sentence = false;   // zu lang, verwerfen
      return false;
    }
    buf[len++] = c;
    return false;
  }
};
