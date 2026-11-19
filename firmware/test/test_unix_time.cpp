// PC-Test der Datumsfunktionen des Empfängers (receiver/unix_time.h): ISO-Datum schreiben, HTTP-Datum lesen,
// über 2038, 2100 (kein Schaltjahr), 2106 und 2400 (Schaltjahr) hinaus.
//
//   g++ -std=c++17 -I../receiver test_unix_time.cpp -o test_unix_time && ./test_unix_time

#include <cstdio>
#include <cstring>
#include <ctime>

#include "unix_time.h"

static int failures = 0;
#define CHECK(cond, ...)                                     \
  do {                                                       \
    if (!(cond)) {                                           \
      failures++;                                            \
      std::printf("  FEHLER %s:%d: ", __FILE__, __LINE__);   \
      std::printf(__VA_ARGS__);                              \
      std::printf("\n");                                     \
    }                                                        \
  } while (0)

static void expectIso(uint64_t t, const char* want) {
  char got[UNIX_ISO_LEN];
  unix_iso(t, got);
  CHECK(strcmp(got, want) == 0, "%llu: %s statt %s", (unsigned long long)t, got, want);
}

static void expectParse(const char* s, uint64_t want) {
  uint64_t t = 0;
  bool ok = unix_parse_http_date(s, t);
  CHECK(ok && t == want, "\"%s\": ok=%d %llu statt %llu", s, ok, (unsigned long long)t, (unsigned long long)want);
}

int main() {
  std::printf("feste Zeitpunkte\n");
  expectIso(0, "1970-01-01T00:00:00Z");
  expectIso(2147483647ULL, "2038-01-19T03:14:07Z");
  expectIso(2147483648ULL, "2038-01-19T03:14:08Z");
  expectIso(4107456000ULL, "2100-02-28T00:00:00Z");
  expectIso(4107542400ULL, "2100-03-01T00:00:00Z");   // 2100 ist kein Schaltjahr
  expectIso(4294967295ULL, "2106-02-07T06:28:15Z");
  expectIso(4294967296ULL, "2106-02-07T06:28:16Z");
  expectIso(13574563200ULL, "2400-02-29T00:00:00Z");  // 2400 ist ein Schaltjahr
  expectIso(253402300799ULL, "9999-12-31T23:59:59Z");

  std::printf("gegen gmtime bis 2999\n");
  int mismatches = 0;
  for (uint64_t t = 0; t < 32503680000ULL; t += 86400ULL * 13 + 3607) {
    time_t tt = (time_t)t;
    struct tm tm;
#ifdef _WIN32
    gmtime_s(&tm, &tt);
#else
    gmtime_r(&tt, &tm);
#endif
    char want[UNIX_ISO_LEN], got[UNIX_ISO_LEN];
    strftime(want, sizeof(want), "%Y-%m-%dT%H:%M:%SZ", &tm);
    unix_iso(t, got);
    if (strcmp(want, got) != 0 && mismatches++ < 5) CHECK(false, "%llu: %s statt %s", (unsigned long long)t, got, want);
  }

  std::printf("HTTP-Datum lesen\n");
  expectParse("Sun, 06 Nov 1994 08:49:37 GMT", 784111777ULL);
  expectParse("Wed, 19 Nov 2026 09:31:05 GMT", 1795080665ULL);
  expectParse("Sun, 07 Feb 2106 06:28:16 GMT", 4294967296ULL);
  expectParse("Mon, 01 Mar 2100 00:00:00 GMT", 4107542400ULL);
  expectParse("Tue, 29 Feb 2400 00:00:00 GMT", 13574563200ULL);
  uint64_t t;
  CHECK(!unix_parse_http_date("", t), "leer angenommen");
  CHECK(!unix_parse_http_date("Sun, 06 Nov 1994 08:49:37 UTC", t), "falsche Zone angenommen");
  CHECK(!unix_parse_http_date("Sun, 06 Foo 1994 08:49:37 GMT", t), "falscher Monat angenommen");
  CHECK(!unix_parse_http_date("Sun, 06 Nov 1994 25:49:37 GMT", t), "Stunde 25 angenommen");
  CHECK(!unix_parse_http_date("Sun, 06 Nov 1969 08:49:37 GMT", t), "vor 1970 angenommen");

  std::printf("Zeitpunkt vor dem Empfang\n");
  CHECK(unix_at(5000000000ULL, 70000, 10000, 3600) == 5000000000ULL - 60 - 3600, "unix_at");
  CHECK(unix_at(100, 0, 0, 1000) == 0, "Unterlauf nicht abgefangen");
  CHECK(unix_at(5000000000ULL, 5000, 0xFFFFF000u, 0) == 5000000000ULL - 9, "millis-Überlauf");

  if (failures) {
    std::printf("%d Fehler\n", failures);
    return 1;
  }
  std::printf("alles ok\n");
  return 0;
}
