"""SPICE-Netzliste der ganzen Platine aus design.py, plus Umgebung (Panel/Netzteil, Akku, NTC, Heizung, XIAO, Sonde).

Jede Strommessung läuft über eine 0-V-Quelle "VAM_<Ref>[_<Zweig>]" in Reihe, damit Dioden-, MOSFET- und
Spulenströme direkt als Vektor vorliegen. ICs sind Verhaltensmodelle (gemittelt, keine Schaltflanken).
"""

import math
import os
import re
import sys
from dataclasses import dataclass, field

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import design  # noqa: E402
from models import DIODE_MODEL, MOS_MODEL, SPICE_MODELS  # noqa: E402

R_SHUNT = 0.1 / 2                # R15 ‖ R16 im Minuspol des Akkus
OCV = [(0.0, 2.50), (0.02, 2.90), (0.05, 3.10), (0.10, 3.20), (0.20, 3.25), (0.40, 3.29), (0.60, 3.31),
       (0.80, 3.33), (0.90, 3.34), (0.97, 3.40), (1.0, 3.60)]
CAPACITY_AS = 18.0 * 3600       # 3 × 6 Ah (32700) parallel
R_BAT = 0.015


def node(net: str) -> str:
    if not net or net == "GND":
        return "0"
    return "N_" + re.sub(r"[^A-Za-z0-9_]", "_", net.replace("+", "P"))


def num(value: str) -> float:
    """'4.7k', '100nF 50V', '0.1', '10M' → Zahl (M = Mega wie in KiCad, m = milli)."""
    v = value.split()[0]
    m = re.match(r"^([\d.]+)\s*([pnuµmkMG]?)", v)
    base = float(m.group(1))
    return base * {"p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "m": 1e-3, "k": 1e3, "M": 1e6, "G": 1e9, "": 1}[m.group(2)]


@dataclass
class Scenario:
    """Umgebung. sun 0..1 (Bestrahlung), temp °C (Akku/NTC, Panel), dc: Netzteilspannung an J1 oder None."""
    name: str = "default"
    sun: float = 0.0
    temp: float = 20.0
    dc: float | None = None
    jp2: bool = False               # Steckbrücke "NETZTEIL" gesetzt
    soc: float = 0.5
    v_cell: float | None = None     # Zellspannung erzwingen statt SoC-Kennlinie
    battery: bool = True
    ntc: bool = True                # NTC an J4
    heater_ohm: float = 68.0        # Heizwiderstand an J4
    xiao_ma: float = 6.0            # MeshCore: Empfang dauernd an
    sens: bool = False              # SENS_EN (Sonde an)
    probe_ma: float = 30.0
    transmit: bool = False          # UART_TX low: RS485-Treiber sendet "0"
    panel_isc: float = 1.2          # 20-W-Panel (Isc), Voc 22 V bei 25 °C
    panel_voc25: float = 22.0
    extra: list = field(default_factory=list)


def panel_voc(sc: Scenario) -> float:
    return sc.panel_voc25 * (1 - 0.0035 * (sc.temp - 25))


def ocv_pwl() -> str:
    return ", ".join(f"{s}, {v}" for s, v in OCV)


def netlist(sc: Scenario, analysis: str, battery_dynamic=False, temp_expr=None, extra_lines=(), ramp=None,
            save=None) -> str:
    L = [f"* pegel-sender {sc.name}", SPICE_MODELS]
    temp = temp_expr or f"{sc.temp}"
    L.append(f"Btemp N_TEMP 0 V = {temp}")

    for p in design.PARTS:
        if p.group == "mech":
            continue
        L += part_lines(p, sc)

    # ---------------- Umgebung
    voc = panel_voc(sc)
    vta = 36 * 1.3 * 0.0257 * (273.15 + sc.temp) / 298.15
    i0 = sc.panel_isc / (math.exp(voc / vta) - 1)
    sun = f"{sc.sun}" if not isinstance(sc.sun, str) else sc.sun
    if ramp:
        sun = f"({sun})*min(1,time/{ramp})"
    L.append(f"Bpv 0 N_PV I = ({sun})*{sc.panel_isc} - {i0:.4e}*(exp(V(N_PV)/{vta:.4f})-1)")
    L.append("Rpv_s N_PV N_IN_RAW 0.3")
    L.append("Rpv_p N_PV 0 1e6")
    if sc.dc is not None:
        dc = f"{sc.dc}" if not isinstance(sc.dc, str) else sc.dc
        if ramp:
            dc = f"({dc})*min(1,time/{ramp})"
        L.append(f"Bdc N_DCSRC 0 V = {dc}")
        L.append("Ddc N_DCSRC N_IN_RAW BODY")

    # Akku an J2: OCV(SoC) + Innenwiderstand, Strom über VAM_BAT (positiv = Laden)
    if sc.battery:
        if sc.v_cell is not None:
            L.append(f"Bcell N_CELL N_BAT_N V = {sc.v_cell}")
        else:
            if battery_dynamic:
                L.append(f"Csoc N_SOC 0 {CAPACITY_AS} IC={sc.soc}")
                L.append("Bsoc 0 N_SOC I = I(VAM_BAT)")
                L.append("Rsoc N_SOC 0 1e12")
                L.append(f".ic V(N_SOC)={sc.soc}")
            else:
                L.append(f"Vsoc N_SOC 0 {sc.soc}")
            L.append(f"Bcell N_CELL N_BAT_N V = pwl(V(N_SOC), {ocv_pwl()})")
        L.append(f"Rbat N_CELL N_BATI {R_BAT}")
        L.append("VAM_BAT N_VSYS N_BATI 0")

    # NTC 10k B3950 und Heizwiderstand am Akku (J4)
    if sc.ntc:
        L.append("Bntc N_T_NTC 0 I = V(N_T_NTC)/(10k*exp(3950*(1/(V(N_TEMP)+273.15)-1/298.15)))")
    L.append(f"Rheat N_VSOL N_HEATA {sc.heater_ohm}")
    L.append("VAM_HEAT N_HEATA N_HEAT_N 0")

    # XIAO + Funk an XIAO_3V3, SENS_EN und UART_TX vom XIAO
    rf = f"*min(1,time/{ramp})" if ramp else ""
    L.append(f"Bxiao N_XIAO_3V3 0 I = {sc.xiao_ma / 1000}{rf}*min(1,max(0,V(N_XIAO_3V3)-1.5))")
    L.append(f"Bsens N_SENSDRV 0 V = {'V(N_XIAO_3V3)' if sc.sens else 0}")
    L.append("Rsens N_SENSDRV N_SENS_EN 100")
    L.append(f"Btx N_TXDRV 0 V = {0 if sc.transmit else 'V(N_XIAO_3V3)'}")
    L.append("Rtx N_TXDRV N_UART_TX 100")
    # Sonde an J3: Last ab ~8 V, eigener RS485-Empfänger 12 kΩ
    L.append(f"Bprobe N_V12_PROBE 0 I = {sc.probe_ma / 1000}*min(1, max(0, (V(N_V12_PROBE)-8)/2))")
    L.append("Rprobe_a N_RS485_A N_PROBE_MID 12k")
    L.append("Rprobe_b N_RS485_B N_PROBE_MID 12k")
    L.append("Bprobe_mid N_PROBE_MID 0 V = min(V(N_V12_PROBE), 5)/2")
    L.append("Rprobe_idle N_V12_PROBE 0 100k")
    L += list(sc.extra) + list(extra_lines)
    # Hochohmig gegen GND: keine schwebenden Knoten (z. B. Schaltknoten der gemittelten Wandler)
    nodes = sorted({tok for ln in L for tok in re.findall(r"N_[A-Za-z0-9_]+", ln)})
    L += [f"Rleak_{i} {nd} 0 1e10" for i, nd in enumerate(nodes)]
    # Gear und reltol 1e-3: die schnellen Regelkreise (Panel-Arbeitspunkt, Wandler) machen die Netzliste steif
    L.append(".options gmin=1e-12 reltol=1e-3 abstol=1e-9 vntol=1e-6 itl1=500 itl4=200 method=gear")
    if save:
        L.append(".save " + " ".join(f"i({x[2:]})" if x.startswith("i:") else f"v({x})" for x in save))
    L.append(analysis)
    L.append(".end")
    return "\n".join(L)


def part_lines(p, sc) -> list[str]:
    ref = p.ref
    n = {pad: node(net) for pad, net in p.pins.items()}
    kind = p.symbol.split(":")[1]
    out = []
    if p.symbol == "Device:R":
        out.append(f"R{ref} {n['1']} {n['2']} {num(p.value)}")
    elif p.symbol in ("Device:C", "Device:C_Polarized"):
        out.append(f"C{ref} {n['1']} N_{ref}_esr {num(p.value)}")
        out.append(f"R{ref}_esr N_{ref}_esr {n['2']} 0.005")
    elif p.symbol == "Device:L":
        from models import RATINGS
        dcr = next((v["DCR"] for k, v in RATINGS.items() if k in p.mpn and "DCR" in v), 0.05)
        out.append(f"VAM_{ref} {n['1']} N_{ref}_a 0")
        out.append(f"L{ref} N_{ref}_a N_{ref}_b {num(p.value)}")
        out.append(f"R{ref}_dcr N_{ref}_b {n['2']} {dcr}")
    elif kind in ("D_Schottky", "D_Zener", "D_TVS", "D"):
        model = DIODE_MODEL[p.value]
        out.append(f"VAM_{ref} {n['2']} N_{ref}_a 0")       # Pin 2 = Anode
        out.append(f"D{ref} N_{ref}_a {n['1']} {model}")
    elif kind == "BAV70":
        for pad in ("1", "2"):
            out.append(f"D{ref}_{pad} {n[pad]} {n['3']} {DIODE_MODEL['BAV70']}")
    elif kind == "SM712_SOT23":
        for pad in ("1", "2"):
            out.append(f"D{ref}_{pad}p N_{ref}_{pad}m {n[pad]} TVS13")
            out.append(f"D{ref}_{pad}n N_{ref}_{pad}m {n['3']} TVS7")
    elif kind in ("Q_NMOS", "Q_PMOS"):
        g, s, d = n["1"], n["2"], n["3"]
        model = MOS_MODEL[p.value]
        out.append(f"VAM_{ref} {d} N_{ref}_d 0")
        out.append(f"M{ref} N_{ref}_d {g} {s} {s} {model}")
        if kind == "Q_NMOS":
            out.append(f"D{ref}_body {s} N_{ref}_d BODY")
        else:
            out.append(f"D{ref}_body N_{ref}_d {s} BODY")
    elif ref == "JP2":
        out.append(f"R{ref} {n['1']} {n['2']} {0.01 if sc.jp2 else 1e9}")
    elif kind.startswith(("Screw_Terminal", "Conn_")):
        pass   # Umgebung
    elif p.ref.startswith("U"):
        out += ic_lines(p, n, sc)
    else:
        raise SystemExit(f"kein Modell für {ref} ({p.symbol})")
    return out


def ic_lines(p, n, sc) -> list[str]:
    ref = p.ref
    v = p.value
    if v == "TPS5430":
        vin, fb, sw = n["7"], n["4"], n["8"]
        # Gemittelt: Ausgangsstrom aus PI-Regler auf VSENSE = 1,221 V (I-Anteil im Knoten _ctl, ohne
        # bleibende Regelabweichung wie der echte Fehlerverstärker); Einschaltschwelle 5,3 V, Tastgrad max. 87 %,
        # Strombegrenzung 4 A (Datenblatt min.). Body-Diode des internen Schalters PH → VIN.
        on = f"min(1,max(0,(V({vin})-5.3)*5))"
        kd = f"min(1,max(0,(0.87*V({vin})-V({sw}))*5))"
        err = f"(1.221-V({fb}))"
        ctl = f"N_{ref}_ctl"
        iout = f"({on}*{kd}*min(4.0, max(0, V({ctl}) + 20*{err})))"
        return [
            f"C{ref}_ctl {ctl} 0 1",
            f"B{ref}_ctl 0 {ctl} I = 2000*{err}",
            f"V{ref}_hi N_{ref}_hi 0 4.2", f"D{ref}_hi {ctl} N_{ref}_hi BODY",
            f"D{ref}_lo 0 {ctl} BODY",
            f"B{ref}_rst {ctl} 0 I = (1-{on})*V({ctl})*10",
            f"B{ref}_out 0 {sw} I = {iout}",
            f"B{ref}_in {vin} 0 I = {iout}*max(V({sw}),0)/(max(V({vin}),1)*0.9) + 4.4m*{on} + 20u*min(1,max(0,V({vin})/5))",
            f"D{ref}_hs {sw} {vin} BODY",
            f"R{ref}_boot {n['1']} {sw} 1e6",
        ]
    if v == "LM324":
        vcc = n["4"]
        out = [f"B{ref}_q {vcc} 0 I = 0.7m*min(1,max(0,V({vcc})/3))"]
        # Ausgang 5 mV … VCC − 1,5 V, Verstärkung 1e4 mit Pol bei 100 Hz (Verstärkungs-Bandbreite 1 MHz)
        for i, (o, m, pl) in enumerate((("1", "2", "3"), ("7", "6", "5"), ("8", "9", "10"), ("14", "13", "12"))):
            out += [
                f"B{ref}_{i} N_{ref}_{i}a 0 V = max(min(1e4*(V({n[pl]})-V({n[m]})), V({vcc})-1.5), 0.005)"
                f"*min(1,max(0,V({vcc})-2.5))",
                f"R{ref}_{i}p N_{ref}_{i}a N_{ref}_{i}b 1k",
                f"C{ref}_{i}p N_{ref}_{i}b 0 1.6u",
                f"B{ref}_{i}o N_{ref}_{i}c 0 V = V(N_{ref}_{i}b)",
                f"R{ref}_{i}o N_{ref}_{i}c {n[o]} 50",
            ]
        return out
    if v == "HT7550-1":
        vin, vout = n["2"], n["3"]
        return [f"B{ref}_r N_{ref}_r 0 V = min(5.0, max(V({vin})-0.1, 0))",
                f"VAM_{ref}_o N_{ref}_r N_{ref}_o 0",
                f"R{ref}_o N_{ref}_o {vout} 0.5",
                f"B{ref}_in {vin} 0 I = max(I(VAM_{ref}_o),0) + 2.5u*min(1,max(0,V({vin})/5))"]
    if v == "CJ431":
        k, a = n["2"], n["3"]
        return [f"B{ref} {k} {a} I = max(0, V({k},{a})-2.495)*5"]
    if v == "TPS61040":
        vin, sw, fb, en = n["5"], n["1"], n["3"], n["4"]
        out_n = "N_V12_RAW"
        # PFM mit Spitzenstrom 0,4 A, L = 10 µH, Mindest-Ausschaltzeit 400 ns, max. 1 MHz:
        # Ausgangsstrom = Ilim/2 · Toff/T (Lücken), Wirkungsgrad 0,9 der Energie je Puls.
        ton = f"(10u*0.4/max(V({vin}),0.5))"
        toff = f"(10u*0.4/max(V({out_n})+0.4-V({vin}),0.5))"
        per = f"max({ton}+max({toff},400n), 1u)"
        imax = f"(0.9*0.2*{toff}/{per})"
        enb = f"min(1,max(0,(V({en})-0.9)*5))"
        iout = f"({enb}*min({imax}, max(0,(1.233-V({fb}))*20)))"
        return [
            f"B{ref}_out 0 {out_n} I = {iout}",
            f"B{ref}_in {vin} 0 I = {iout}*V({out_n})/(max(V({vin}),1)*0.85) + 28u*{enb}",
            f"R{ref}_sw {sw} 0 1e8",
        ]
    if v == "SP3485EN":
        vcc, a, b, ro, re_, de, di = n["8"], n["6"], n["7"], n["1"], n["2"], n["3"], n["4"]
        on = f"(V({vcc}) > 2 ? 1 : 0)"
        rx = f"(V({re_}) < V({vcc})/2 ? 1 : 0)"
        tx = f"(V({de}) > V({vcc})/2 ? 1 : 0)"
        hi = f"(V({di}) > V({vcc})/2 ? 1 : 0)"
        return [f"B{ref}_icc {vcc} 0 I = 1m*{on}",
                f"R{ref}_ra {a} N_{ref}_mid 12k", f"R{ref}_rb {b} N_{ref}_mid 12k",
                f"B{ref}_mid N_{ref}_mid 0 V = V({vcc})/2",
                f"B{ref}_ro {ro} 0 I = {on}*{rx}*(V({ro}) - (V({a},{b}) > 0.2 ? V({vcc}) : 0))/50",
                f"B{ref}_da {a} 0 I = {on}*{tx}*(V({a}) - {hi}*V({vcc}))/20",
                f"B{ref}_db {b} 0 I = {on}*{tx}*(V({b}) - (1-{hi})*V({vcc}))/20",
                f"R{ref}_re {re_} 0 1e9", f"R{ref}_de {de} 0 1e9"]
    raise SystemExit(f"kein IC-Modell für {ref} {v}")


def settle(ng, sc: Scenario, t_end=0.4, extra_lines=()) -> dict[str, float]:
    """Eingeschwungener Zustand: Quellen in 10 ms hochfahren, Werte am Ende der Simulation."""
    try:
        res = ng.run(netlist(sc, f".tran 50u {t_end} {t_end * 0.98}", ramp="10m", extra_lines=list(extra_lines)))
    except RuntimeError:
        # Ersatzweg bei Konvergenzproblemen: Trapez-Verfahren, gröbere Toleranz
        res = ng.run(netlist(sc, f".tran 50u {t_end} {t_end * 0.98}", ramp="10m",
                             extra_lines=list(extra_lines) + [".options method=trap reltol=2e-3 abstol=1e-9"]))
    return {k: v[-1] for k, v in res.items()}
