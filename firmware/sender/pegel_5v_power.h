#pragma once

#ifndef PEGEL_5V_BOARD
#define PEGEL_5V_BOARD 0
#endif

#if PEGEL_5V_BOARD
void pegel_5v_power_begin();
void pegel_5v_power_update();
#endif