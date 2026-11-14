#include <Arduino.h>
#include "clock.h"

// Wie readGrtcCounterPreserveActive() im Core (wiring_time.c), der das nicht öffentlich anbietet:
// Zähler bei Bedarf aktiv schalten, 52 Bit konsistent lesen (BUSY/OVERFLOW beachten), danach Zustand zurück.
static uint64_t grtc_us() {
  NRF_GRTC_Type* grtc = NRF_GRTC;
  bool was_inactive = (NRF54L15_GRTC_SYSCOUNTER(grtc).ACTIVE & GRTC_SYSCOUNTER_ACTIVE_ACTIVE_Msk) ==
                      (GRTC_SYSCOUNTER_ACTIVE_ACTIVE_NotActive << GRTC_SYSCOUNTER_ACTIVE_ACTIVE_Pos);
  if (was_inactive) {
    grtc->TASKS_START = GRTC_TASKS_START_TASKS_START_Trigger;
    __asm volatile("dsb 0xF" ::: "memory");
    NRF54L15_GRTC_SYSCOUNTER(grtc).ACTIVE = GRTC_SYSCOUNTER_ACTIVE_ACTIVE_Active << GRTC_SYSCOUNTER_ACTIVE_ACTIVE_Pos;
    __asm volatile("dsb 0xF" ::: "memory");
    for (uint32_t spin = 0; spin < 100000; spin++) {
      (void)NRF54L15_GRTC_SYSCOUNTER(grtc).SYSCOUNTERL;
      if ((NRF54L15_GRTC_SYSCOUNTER(grtc).SYSCOUNTERH & GRTC_SYSCOUNTER_SYSCOUNTERH_BUSY_Msk) == 0) break;
    }
  }
  uint64_t value = 0;
  for (int attempt = 0; attempt < 32; attempt++) {
    uint32_t lo = NRF54L15_GRTC_SYSCOUNTER(grtc).SYSCOUNTERL;
    uint32_t hi = NRF54L15_GRTC_SYSCOUNTER(grtc).SYSCOUNTERH;
    if (hi & GRTC_SYSCOUNTER_SYSCOUNTERH_BUSY_Msk) continue;
    uint32_t high = (hi & GRTC_SYSCOUNTER_SYSCOUNTERH_VALUE_Msk) >> GRTC_SYSCOUNTER_SYSCOUNTERH_VALUE_Pos;
    if (hi & GRTC_SYSCOUNTER_SYSCOUNTERH_OVERFLOW_Msk) {
      high = (high - 1U) & (GRTC_SYSCOUNTER_SYSCOUNTERH_VALUE_Msk >> GRTC_SYSCOUNTER_SYSCOUNTERH_VALUE_Pos);
    }
    value = ((uint64_t)high << 32) | lo;
    break;
  }
  if (was_inactive) {
    NRF54L15_GRTC_SYSCOUNTER(grtc).ACTIVE =
        GRTC_SYSCOUNTER_ACTIVE_ACTIVE_NotActive << GRTC_SYSCOUNTER_ACTIVE_ACTIVE_Pos;
  }
  return value;
}

uint32_t grtc_seconds() { return (uint32_t)(grtc_us() / 1000000ULL); }
