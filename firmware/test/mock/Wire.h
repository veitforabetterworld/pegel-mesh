#pragma once
// I²C-Nachbildung: die Platine hat kein I²C-Gerät mehr, level_sensor gibt nur die Pins für die UART frei.

struct TwoWire {
  bool running = true;
  void begin() { running = true; }
  void end() { running = false; }
};
extern TwoWire Wire;
