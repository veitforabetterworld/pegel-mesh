#include "pegel_5v_power.h"

#if PEGEL_5V_BOARD

#include <nrf.h>

// HEAT_EN ist P0.09 (NFC1 auf der Rückseite des XIAO). Der Sockel hat keinen
// freien Pin: D1–D5 und D8–D10 sind Funk, D0/D6/D7 sind Sonde. TP1 auf der
// Platine wird mit einem Draht an dieses Pad gelötet.
// high = heizen, Lader aus. low = laden, Heizung aus. Pulldown auf der Platine,
// damit vor dem Start und nach einem Reset geladen wird und nicht geheizt.

static const int HEAT_ON_C = 5;
static const int HEAT_OFF_C = 8;

static bool heating = false;

static void nfcPinAsGpio() {
  if (NRF_UICR->NFCPINS != UICR_NFCPINS_PROTECT_Disabled) {
    NRF_NVMC->CONFIG = NVMC_CONFIG_WEN_Wen;
    while (NRF_NVMC->READY == NVMC_READY_READY_Busy) {}
    NRF_UICR->NFCPINS = UICR_NFCPINS_PROTECT_Disabled;
    while (NRF_NVMC->READY == NVMC_READY_READY_Busy) {}
    NRF_NVMC->CONFIG = NVMC_CONFIG_WEN_Ren;
    NVIC_SystemReset();
  }
}

static void heatPin(bool on) {
  NRF_P0->PIN_CNF[9] =
      (GPIO_PIN_CNF_DIR_Output << GPIO_PIN_CNF_DIR_Pos) |
      (GPIO_PIN_CNF_INPUT_Disconnect << GPIO_PIN_CNF_INPUT_Pos) |
      (GPIO_PIN_CNF_PULL_Pulldown << GPIO_PIN_CNF_PULL_Pos) |
      (GPIO_PIN_CNF_DRIVE_S0S1 << GPIO_PIN_CNF_DRIVE_Pos) |
      (GPIO_PIN_CNF_SENSE_Disabled << GPIO_PIN_CNF_SENSE_Pos);
  if (on) NRF_P0->OUTSET = 1u << 9;
  else NRF_P0->OUTCLR = 1u << 9;
}

// Chip-Temperatur in °C. Bleibt die Messung aus, gilt es als warm (nicht heizen).
static int dieC() {
  NRF_TEMP->EVENTS_DATARDY = 0;
  NRF_TEMP->TASKS_START = 1;
  for (int i = 0; i < 10000 && !NRF_TEMP->EVENTS_DATARDY; i++) {}
  if (!NRF_TEMP->EVENTS_DATARDY) return 25;
  int raw = (int)NRF_TEMP->TEMP;
  NRF_TEMP->EVENTS_DATARDY = 0;
  NRF_TEMP->TASKS_STOP = 1;
  return raw / 4;
}

void pegel_5v_power_begin() {
  nfcPinAsGpio();
  heating = false;
  heatPin(false);
  pegel_5v_power_update();
}

void pegel_5v_power_update() {
  int t = dieC();
  if (heating) {
    if (t >= HEAT_OFF_C) heating = false;
  } else if (t <= HEAT_ON_C) {
    heating = true;
  }
  heatPin(heating);
}

#endif
