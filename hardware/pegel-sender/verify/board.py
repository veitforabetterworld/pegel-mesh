"""SPICE-Netzliste der ganzen Platine aus design.py, plus Umgebung (Panel, Netzteil, Akku, XIAO, Sonde).

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

ICC = 0.120 / 0.040            # CN3795: 120 mV über R1 (40 mΩ)
VREG = 1.205 * (1 + 200 / 100)  # Ladeschlussspannung
OCV = [(0.0, 2.50), (0.02, 2.90), (0.05, 3.10), (0.10, 3.20), (0.20, 3.25), (0.40, 3.29), (0.60, 3.31),
       (0.80, 3.33), (0.90, 3.34), (0.97, 3.40), (1.0, 3.60)]
CAPACITY_AS = 18.0 * 3600       # 3 × 6 Ah (32700) parallel
R_BAT = 0.015


def node(net: str) -> str:
    if not net or net == "GND":
        return "0"
    return "N_" + re.sub(r"[^A-Za-z0-9_]", "_", net.replace("+", "P"))


def num(value: str) -> float:
    """'4.7k', '100nF 50V', '40m 2W', '10M' → Zahl (M = Mega wie in KiCad, m = milli)."""
    v = value.split()[0]
    m = re.match(r"^([\d.]+)\s*([pnuµmkMG]?)", v)
    base = float(m.group(1))
    return base * {"p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "m": 1e-3, "k": 1e3, "M": 1e6, "G": 1e9, "": 1}[m.group(2)]


@dataclass
class Scenario:
    """Umgebung. sun 0..1 (Bestrahlung), temp °C (Platine, Panel), dc: Netzteilspannung oder None."""
    name: str = "default"
    sun: float = 0.0
    temp: float = 20.0
    dc: float | None = None
    soc: float = 0.5
    v_cell: float | None = None    # Zellspannung erzwingen statt SoC-Kennlinie
    xiao_ma: float = 6.0            # MeshCore: Empfang dauernd an
    sens: bool = False              # SENS_EN (Sonde an)
    probe_ma: float = 50.0
    transmit: bool = False          # RS485 sendet (RTS high)
    jp1: bool = False               # 120-Ω-Abschluss
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
    L.append("Rpv_s N_PV N_SOLAR_RAW 0.3")
    L.append("Rpv_p N_PV 0 1e6")
    if sc.dc is not None:
        dc = f"{sc.dc}" if not isinstance(sc.dc, str) else sc.dc
        if ramp:
            dc = f"({dc})*min(1,time/{ramp})"
        L.append(f"Bdc N_DCSRC 0 V = {dc}")
        L.append("Rdc N_DCSRC N_DC_RAW 0.1")
    else:
        L.append("Rdc_open N_DC_RAW 0 1e7")

    # Akku: OCV(SoC) + Innenwiderstand, Strom über VAM_BAT (positiv = Laden)
    if sc.v_cell is not None:
        v = sc.v_cell if not isinstance(sc.v_cell, str) else sc.v_cell
        L.append(f"Bcell N_CELL N_BAT_N V = {v}")
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
    L.append("VAM_BAT N_BAT_P N_BATI 0")

    # XIAO + Funk an XIAO_3V3, SENS_EN vom XIAO-Pin, I²C ruhend
    rf = f"*min(1,time/{ramp})" if ramp else ""
    L.append(f"Bxiao N_XIAO_3V3 0 I = {sc.xiao_ma / 1000}{rf}*min(1,max(0,V(N_XIAO_3V3)-1.5))")
    L.append(f"Bsens N_SENSDRV 0 V = {3.3 if sc.sens else 0}{rf.replace(ramp or 'x', '20m') if ramp else ''}")
    L.append("Rsens N_SENSDRV N_SENS_EN 100")
    L.append("Rscl N_I2C_SCL 0 1e7")
    L.append("Rsda N_I2C_SDA 0 1e7")
    # Sonde an J3: Last ab ~8 V, eigener RS485-Empfänger 12 kΩ
    L.append(f"Bprobe N_V12_PROBE 0 I = {sc.probe_ma / 1000}*min(1, max(0, (V(N_V12_PROBE)-8)/2))")
    L.append("Rprobe_a N_RS485_A N_PROBE_MID 12k")
    L.append("Rprobe_b N_RS485_B N_PROBE_MID 12k")
    L.append("Bprobe_mid N_PROBE_MID 0 V = min(V(N_V12_PROBE), 5)/2")
    L.append("Rprobe_idle N_V12_PROBE 0 100k")
    L.append("Rntc_ext N_NTC_SEL3 0 1e7")
    L += list(sc.extra) + list(extra_lines)
    # Hochohmig gegen GND: keine schwebenden Knoten (z. B. Schaltknoten der gemittelten Wandler)
    nodes = sorted({tok for ln in L for tok in re.findall(r"N_[A-Za-z0-9_]+", ln)})
    L += [f"Rleak_{i} {nd} 0 1e10" for i, nd in enumerate(nodes)]
    L.append(".options gmin=1e-12 reltol=1e-4 abstol=1e-10 vntol=1e-6 itl1=500 itl4=200")
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
        esr = 0.3 if "Polarized" in p.symbol else 0.005
        out.append(f"C{ref} {n['1']} N_{ref}_esr {num(p.value)}")
        out.append(f"R{ref}_esr N_{ref}_esr {n['2']} {esr}")
    elif p.symbol == "Device:L":
        from models import RATINGS
        dcr = next((v["DCR"] for k, v in RATINGS.items() if k in p.mpn and "DCR" in v), 0.05)
        out.append(f"VAM_{ref} {n['1']} N_{ref}_a 0")
        out.append(f"L{ref} N_{ref}_a N_{ref}_b {num(p.value)}")
        out.append(f"R{ref}_dcr N_{ref}_b {n['2']} {dcr}")
    elif p.symbol == "Device:Fuse":
        out.append(f"VAM_{ref} {n['1']} N_{ref}_a 0")
        out.append(f"R{ref} N_{ref}_a {n['2']} 0.04")
    elif kind in ("D_Schottky", "D_Zener", "D_TVS", "LED"):
        model = DIODE_MODEL[p.value]
        out.append(f"VAM_{ref} {n['2']} N_{ref}_a 0")       # Pin 2 = Anode
        out.append(f"D{ref} N_{ref}_a {n['1']} {model}")
    elif kind == "SM712_SOT23":
        for pad in ("1", "2"):
            out.append(f"D{ref}_{pad}p N_{ref}_{pad}m {n[pad]} TVS13")
            out.append(f"D{ref}_{pad}n N_{ref}_{pad}m {n['3']} TVS7")
    elif kind in ("Q_NMOS", "Q_PMOS"):
        g, s, d = (n["1"], n["3"], n["2"]) if "TO-252" in p.footprint else (n["1"], n["2"], n["3"])
        model = MOS_MODEL[p.value]
        out.append(f"VAM_{ref} {d} N_{ref}_d 0")
        out.append(f"M{ref} N_{ref}_d {g} {s} {s} {model}")
        if kind == "Q_NMOS":
            out.append(f"D{ref}_body {s} N_{ref}_d BODY")
        else:
            out.append(f"D{ref}_body N_{ref}_d {s} BODY")
    elif kind == "FS8205A":
        # Zwei N-FETs mit gemeinsamem Drain: FET1 S1/G1, FET2 S2/G2
        dnode = n["1"]
        out.append(f"VAM_{ref}_1 {n['2']} N_{ref}_s1 0")
        out.append(f"M{ref}_1 {dnode} {n['4']} N_{ref}_s1 N_{ref}_s1 NFS8205")
        out.append(f"D{ref}_1body N_{ref}_s1 {dnode} BODY")
        out.append(f"VAM_{ref}_2 {n['6']} N_{ref}_s2 0")
        out.append(f"M{ref}_2 {dnode} {n['5']} N_{ref}_s2 N_{ref}_s2 NFS8205")
        out.append(f"D{ref}_2body N_{ref}_s2 {dnode} BODY")
    elif kind == "Thermistor_NTC":
        out.append(f"B{ref} {n['1']} {n['2']} I = V({n['1']},{n['2']})/(100k*exp(4250*(1/(V(N_TEMP)+273.15)-1/298.15)))")
    elif kind == "SolderJumper_3_Bridged12":
        out.append(f"R{ref} {n['1']} {n['2']} 0.01")
    elif kind == "SolderJumper_2_Open":
        out.append(f"R{ref} {n['1']} {n['2']} {0.01 if sc.jp1 else 1e9}")
    elif kind.startswith(("Screw_Terminal", "Conn_", "Crystal")):
        pass   # Umgebung bzw. ohne Gleichstromwirkung
    elif p.ref.startswith("U"):
        out += ic_lines(p, n, sc)
    else:
        raise SystemExit(f"kein Modell für {ref} ({p.symbol})")
    return out


def ic_lines(p, n, sc) -> list[str]:
    ref = p.ref
    v = p.value
    if v == "CN3795":
        vcc, bat, csp, fb, mppt = n["9"], n["7"], n["8"], n["6"], n["4"]
        on = f"min(1,max(0,(V({vcc})-6.6)*2))*min(1,max(0,(V({vcc})-V({bat})-0.3)*10))"
        pre = f"(V({bat}) < {0.665 * VREG:.3f} ? 0.175 : 1)"
        kcv = f"min(1,max(0,(1.205-V({fb}))*200))"
        kmp = f"min(1,max(0,(V({mppt})-1.205)*40))"
        iout = f"({ICC:.3f}*{pre}*{on}*{kcv}*{kmp})"
        return [
            f"B{ref}_out 0 {csp} I = {iout}",
            f"B{ref}_in {vcc} 0 I = {iout}*V({csp})/(max(V({vcc}),1)*0.92) + 1m*{on}",
            f"B{ref}_bat {bat} 0 I = 15u",
            f"R{ref}_drv {n['10']} {vcc} 10",       # gemittelt: Gate aus, Schaltbelastung in stress.py
            f"B{ref}_vg {n['1']} 0 V = max(V({vcc})-7, 0)",
            f"B{ref}_chrg {n['3']} 0 I = ({iout} > {0.16 * ICC:.3f} ? 1 : 0)*min(V({n['3']})/100, 12m)",
            f"R{ref}_com {n['5']} 0 1e7",
        ]
    if v == "HY2112-CB":
        vdd, vss, od, oc, cs = n["5"], n["6"], n["1"], n["3"], n["2"]
        # OD (Entlade-FET) an: Zelle > 2,3 V (aus < 2,1 V); Entlade-Überstrom 200 mV (HY2112-CB).
        # OC (Lade-FET) an: Zelle < 3,60 V (aus > 3,75 V); Lade-Überstrom −200 mV.
        return [
            f"B{ref}_cell N_{ref}_c 0 V = V({vdd},{vss})",
            f"B{ref}_celln N_{ref}_cn 0 V = -V({vdd},{vss})",
            f"B{ref}_ocur N_{ref}_oi 0 V = 0.20 - V({cs},{vss})",
            f"B{ref}_ccur N_{ref}_ci 0 V = V({cs},{vss}) + 0.20",
            f"S{ref}_odv {vdd} N_{ref}_odi N_{ref}_c 0 SWHY_OD",
            f"R{ref}_odi N_{ref}_odi {od} 1k",   # Überstrom: getrennte Funktionsprüfung (Verzögerung, Latch)
            f"R{ref}_odpd {od} {vss} 1e6",
            f"S{ref}_ocv {vdd} N_{ref}_oci N_{ref}_cn 0 SWHY_OC",
            f"R{ref}_oci N_{ref}_oci {oc} 1k",
            f"R{ref}_ocpd {oc} {vss} 1e6",
            f"I{ref}_q {vdd} {vss} 4u",
            ".model SWHY_OD SW(VT=2.2 VH=0.1 RON=1k ROFF=1e10)",
            ".model SWHY_OC SW(VT=-3.675 VH=0.075 RON=1k ROFF=1e10)",
        ]
    if v == "TPS63900":
        vin, vout = n["10"], n["6"]
        return [
            f"B{ref}_reg N_{ref}_r 0 V = 3.3*min(1,max(0,(V({vin})-1.7)*10))",
            f"VAM_{ref}_out N_{ref}_r N_{ref}_o 0",
            f"R{ref}_o N_{ref}_o {vout} 0.05",
            f"B{ref}_in {vin} 0 I = I(VAM_{ref}_out)*3.3/(max(V({vin}),1.5)*0.9) + 75n",
            f"R{ref}_cfg1 {n['3']} 0 1e9",
        ]
    if v == "LM2735":
        vin, en, fb = n["5"], n["4"], n["3"]
        out = "N_V12_RAW"
        # CCM-Boost, Schalterstrom begrenzt (min. 1,6 A): Imax = (Ilim − ΔI/2)·(1−D), D = 1 − Vin·η/Vout,
        # ΔI = Vin·D/(L·f) mit 4,7 µH, 1,6 MHz.
        d = f"max(0.05, 1 - V({vin})*0.85/max(V({out}),V({vin})+0.5))"
        imax = f"max(0, (1.6 - V({vin})*{d}/(4.7u*1.6meg)/2)*(1-{d}))"
        enb = f"min(1,max(0,(V({en})-1.0)*5))"
        iout = f"({enb}*min({imax}, max(0,(1.255-V({fb}))*20)))"
        return [
            f"B{ref}_out 0 {out} I = {iout}",
            f"B{ref}_in {vin} 0 I = {iout}*V({out})/(max(V({vin}),1)*0.85) + 3m*{enb}",
            f"R{ref}_en {en} 0 1e8",
        ]
    if v in ("TLV3401", "TLV3402"):
        units = [("3", "4", "1")] if v == "TLV3401" else [("3", "2", "1"), ("5", "6", "7")]
        vcc = n["5"] if v == "TLV3401" else n["8"]
        out = [f"I{ref}_q {vcc} 0 {0.47e-6 * len(units)}"]
        for i, (ip, im, o) in enumerate(units):
            # Open-Drain: zieht nach GND, wenn IN+ < IN−; ohne Versorgung hochohmig
            low = f"0.5*(1+tanh((V({n[im]})-V({n[ip]}))*2000))*min(1,max(0,(V({vcc})-1.5)*5))"
            out.append(f"B{ref}_{i} {n[o]} 0 I = {low}*V({n[o]})/50")
        return out
    if v == "INA226":
        return [f"I{ref}_vs {n['6']} 0 330u", f"I{ref}_inp {n['10']} 0 10u", f"I{ref}_inm {n['9']} 0 10u",
                f"R{ref}_vbus {n['8']} 0 830k"]
    if v == "SC16IS740":
        return [f"I{ref}_vdd {n['1']} 0 1m",
                f"V{ref}_tx N_{ref}_tx 0 3.3", f"R{ref}_tx N_{ref}_tx {n['12']} 50",
                f"V{ref}_rts N_{ref}_rts 0 {3.3 if sc.transmit else 0}", f"R{ref}_rts N_{ref}_rts {n['10']} 50",
                f"R{ref}_rx {n['13']} 0 1e8", f"R{ref}_rst {n['14']} 0 1e8",
                f"R{ref}_x1 {n['15']} 0 1e8", f"R{ref}_x2 {n['16']} 0 1e8"]
    if v == "MAX3485":
        vcc, a, b = n["8"], n["6"], n["7"]
        lines = [f"I{ref}_vcc {vcc} 0 1.1m",
                 f"R{ref}_ra {a} N_{ref}_mid 12k", f"R{ref}_rb {b} N_{ref}_mid 12k",
                 f"B{ref}_mid N_{ref}_mid 0 V = V({vcc})/2",
                 f"B{ref}_ro N_{ref}_ro 0 V = (V({a},{b}) > 0.2 ? V({vcc}) : 0)",
                 f"R{ref}_ro N_{ref}_ro {n['1']} {1e7 if sc.transmit else 50}"]
        if sc.transmit:   # Treiber: DI (TX) high → A high, B low
            lines += [f"B{ref}_da N_{ref}_da 0 V = V({vcc})", f"R{ref}_da N_{ref}_da {a} 20",
                      f"B{ref}_db N_{ref}_db 0 V = 0", f"R{ref}_db N_{ref}_db {b} 20"]
        return lines
    if v == "LM66100":
        vin, vout = n["1"], n["6"]
        return [f"VAM_{ref} {vin} N_{ref}_i 0",
                f"B{ref} N_{ref}_i {vout} I = max(V(N_{ref}_i,{vout}),0)/0.08"]
    raise SystemExit(f"kein IC-Modell für {ref} {v}")


def settle(ng, sc: Scenario, t_end=0.08, extra_lines=()) -> dict[str, float]:
    """Eingeschwungener Zustand: Quellen in 10 ms hochfahren, Werte am Ende der Simulation."""
    try:
        res = ng.run(netlist(sc, f".tran 20u {t_end}", ramp="10m", extra_lines=list(extra_lines)))
    except RuntimeError:
        # Ersatzweg bei Konvergenzproblemen: Gear-Verfahren, gröbere Toleranz
        res = ng.run(netlist(sc, f".tran 20u {t_end}", ramp="10m",
                             extra_lines=list(extra_lines) + [".options method=gear reltol=1e-3 abstol=1e-9"]))
    return {k: v[-1] for k, v in res.items()}
