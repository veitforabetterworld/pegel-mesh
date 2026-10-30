"""Betriebsfälle für die Belastungsprüfung und erwartetes Verhalten je Fall."""

from board import Scenario

# (Szenario, Erwartungen: Netz/Größe -> (min, max))
CASES = [
    (Scenario("Nacht 20 °C, Ruhe", sun=0, temp=20),
     {"P3V3": (3.2, 3.4), "XIAO_3V3": (3.1, 3.4), "Iheat": (0, 0.001), "Ibat": (-0.02, 0)}),
    (Scenario("Nacht −20 °C, Ruhe", sun=0, temp=-20),
     {"Iheat": (0, 0.001), "Ibat": (-0.02, 0)}),
    (Scenario("Nacht −20 °C, Messung 80 mA + Funk", sun=0, temp=-20, xiao_ma=120, sens=True, transmit=True,
              probe_ma=80),
     {"V12_PROBE": (11.0, 12.6), "XIAO_3V3": (3.1, 3.4), "Iheat": (0, 0.001)}),
    (Scenario("Sonne 20 °C, Akku 30 % (Konstantstrom)", sun=1, temp=20, soc=0.3),
     {"Ichg": (2.7, 3.3), "Iheat": (0, 0.001)}),
    (Scenario("Sonne 20 °C, Akku voll (Konstantspannung)", sun=1, temp=20, soc=1.0),
     {"VSYS": (3.5, 3.66)}),
    (Scenario("Sonne −10 °C (Frost: Ladesperre, Heizung)", sun=1, temp=-10, soc=0.5),
     {"Ichg": (-0.01, 0.01), "Iheat": (0.1, 1)}),
    (Scenario("Sonne +1 °C (unter Ladeschwelle: Sperre, Heizung)", sun=1, temp=1, soc=0.5),
     {"Ichg": (-0.01, 0.01), "Iheat": (0.1, 1)}),
    (Scenario("Sonne +4 °C (über der Ladeschwelle)", sun=1, temp=4, soc=0.5),
     {"Ichg": (0.1, 3.3)}),
    (Scenario("Sonne +45 °C, Akku leer", sun=1, temp=45, soc=0.05),
     {"Ichg": (0.3, 3.3), "Iheat": (0, 0.001)}),
    (Scenario("10-W-Panel +10 °C (MPPT begrenzt)", sun=1, temp=10, soc=0.3, panel_isc=0.6),
     {"VSOL": (15, 21)}),
    (Scenario("Panel offen −25 °C, Akku voll", sun=1, temp=-25, soc=1.0),
     {"VSOL": (0, 27)}),
    (Scenario("Netzteil 12 V, 20 °C, Akku 30 %", sun=0, temp=20, dc=12.0, soc=0.3),
     {"Ichg": (0.3, 3.3)}),
    (Scenario("Netzteil 12 V, −10 °C", sun=0, temp=-10, dc=12.0, soc=0.5),
     {"Ichg": (-0.01, 0.01), "Iheat": (0.05, 1)}),
    (Scenario("Netzteil 13,8 V + Sonne, 20 °C", sun=1, temp=20, dc=13.8, soc=0.3),
     {"Ichg": (2.7, 3.3)}),
    (Scenario("Akku 2,8 V, Sondenspitze 200 mA + Funk", sun=0, temp=20, v_cell=2.8, xiao_ma=120, sens=True,
              transmit=True, probe_ma=200),
     {"P3V3": (3.2, 3.4), "V12_PROBE": (11.0, 12.6)}),
    (Scenario("Akku 2,0 V (Tiefentladeschutz)", sun=0, temp=20, v_cell=2.0),
     {"OD": (-0.1, 0.5)}),
    (Scenario("Akku 3,8 V (Überladeschutz)", sun=1, temp=20, v_cell=3.8),
     {"OC": (-0.1, 0.5)}),
    (Scenario("Sonde 200 mA, Abschluss gesetzt, Sendebetrieb", sun=0, temp=20, sens=True, transmit=True, jp1=True,
              probe_ma=200),
     {"V12_PROBE": (11.0, 12.6)}),
]


def measure(res) -> dict:
    """Größen für die Erwartungen."""
    return {
        "P3V3": res.V("+3V3"), "XIAO_3V3": res.V("XIAO_3V3"), "VSYS": res.V("VSYS"), "VSOL": res.V("VSOL"),
        "V12_PROBE": res.V("V12_PROBE"),
        "Iheat": res.I("Q7"), "Ibat": res.I("BAT"),
        "Ichg": (res.V("CHG_CSP") - res.V("VSYS")) / 0.040,
        "OD": res.V("PROT_OD") - res.V("BAT_N"), "OC": res.V("PROT_OC") - res.V("BAT_N"),
    }
