"""Betriebsfälle für die Belastungsprüfung und erwartetes Verhalten je Fall."""

from board import R_SHUNT, Scenario

# (Szenario, Erwartungen: Netz/Größe -> (min, max))
CASES = [
    (Scenario("Nacht 20 °C, Ruhe", sun=0, temp=20),
     {"XIAO_3V3": (2.9, 3.3), "VSOL": (-0.1, 1.0), "Iheat": (-0.001, 0.001), "Ibat": (-0.012, 0)}),
    (Scenario("Nacht −20 °C, Ruhe", sun=0, temp=-20),
     {"VSOL": (-0.1, 1.0), "Iheat": (-0.001, 0.001), "Ibat": (-0.012, 0)}),
    (Scenario("Nacht −20 °C, Messung 30 mA + Funk", sun=0, temp=-20, xiao_ma=120, sens=True, transmit=True),
     {"V12_PROBE": (11.8, 12.8), "XIAO_3V3": (2.8, 3.3), "Iheat": (-0.001, 0.001)}),
    (Scenario("Sonne 20 °C, Akku 30 % (Konstantstrom)", sun=1, temp=20, soc=0.3),
     {"Ichg": (1.8, 2.2), "Iheat": (-0.001, 0.001), "VSOL": (16, 23)}),
    (Scenario("Sonne 20 °C, Akku fast voll (Konstantspannung)", sun=1, temp=20, soc=0.97),
     {"VSYS": (3.45, 3.56), "Ichg": (0, 2.2)}),
    (Scenario("Sonne 20 °C, ohne Akku", sun=1, temp=20, battery=False, xiao_ma=120, sens=True),
     {"VSYS": (3.4, 3.56), "V12_PROBE": (11.8, 12.8)}),
    (Scenario("Sonne −10 °C (Frost: Ladesperre, Heizung)", sun=1, temp=-10, soc=0.5),
     {"Ichg": (-0.02, 0.02), "Iheat": (0.15, 0.4)}),
    (Scenario("Sonne +0,5 °C (unter Ladeschwelle: Sperre, Heizung)", sun=1, temp=0.5, soc=0.5),
     {"Ichg": (-0.02, 0.02), "Iheat": (0.15, 0.4)}),
    (Scenario("Sonne +7 °C (Laden frei, Heizung aus)", sun=1, temp=7, soc=0.5),
     {"Ichg": (0.5, 2.2), "Iheat": (-0.001, 0.001)}),
    (Scenario("Sonne +45 °C, Akku leer", sun=1, temp=45, soc=0.05),
     {"Ichg": (1.0, 2.2), "Iheat": (-0.001, 0.001)}),
    (Scenario("Ohne NTC, Sonne 20 °C (gilt als Frost)", sun=1, temp=20, soc=0.5, ntc=False),
     {"Ichg": (-0.02, 0.02), "Iheat": (0.15, 0.4)}),
    (Scenario("5-W-Panel +10 °C (Arbeitspunkt begrenzt)", sun=1, temp=10, soc=0.3, panel_isc=0.3),
     {"VSOL": (16.5, 18.0), "Ichg": (0.3, 1.8)}),
    (Scenario("Schwaches Licht 10 % (Arbeitspunkt)", sun=0.1, temp=10, soc=0.3),
     {"VSOL": (16.5, 18.0), "Ichg": (0.05, 1.0)}),
    (Scenario("Panel offen −25 °C, Akku voll", sun=1, temp=-25, soc=1.0),
     {"VSOL": (0, 27)}),
    (Scenario("Netzteil 12 V mit Steckbrücke, Akku 30 %", sun=0, temp=20, dc=12.0, jp2=True, soc=0.3),
     {"Ichg": (1.8, 2.2)}),
    (Scenario("Netzteil 12 V ohne Steckbrücke (lädt nicht)", sun=0, temp=20, dc=12.0, soc=0.3),
     {"Ichg": (-0.02, 0.1)}),
    (Scenario("Netzteil 12 V mit Steckbrücke, −10 °C", sun=0, temp=-10, dc=12.0, jp2=True, soc=0.5),
     {"Ichg": (-0.02, 0.02), "Iheat": (0.1, 0.25)}),
    (Scenario("Akku 2,9 V, Sonde 30 mA + Funk", sun=0, temp=20, v_cell=2.9, xiao_ma=120, sens=True,
              transmit=True),
     {"V12_PROBE": (11.8, 12.8), "XIAO_3V3": (2.5, 3.0)}),
    (Scenario("Sonde 30 mA, Senden", sun=0, temp=20, sens=True, transmit=True),
     {"V12_PROBE": (11.8, 12.8)}),
    (Scenario("Sonde 30 mA, Empfang", sun=0, temp=20, sens=True),
     {"V12_PROBE": (11.8, 12.8), "UART_RX": (2.9, 3.6)}),
]


def measure(res) -> dict:
    """Größen für die Erwartungen."""
    return {
        "XIAO_3V3": res.V("XIAO_3V3"), "VSYS": res.V("VSYS"), "VSOL": res.V("VSOL"),
        "V12_PROBE": res.V("V12_PROBE"), "UART_RX": res.V("UART_RX"),
        "Iheat": res.I("HEAT"), "Ibat": res.I("BAT"),
        "Ichg": res.V("BAT_N") / R_SHUNT,
    }
