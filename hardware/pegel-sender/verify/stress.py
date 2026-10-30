"""Bauteilbelastung je Szenario gegen Grenzwerte, plus Schaltbelastung der Wandler (analytisch)."""

import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import design  # noqa: E402
from board import ICC, node, num  # noqa: E402
from models import IC_PINS, RATINGS, RES_P, RES_V  # noqa: E402

WARN = 0.8   # ab 80 % der Grenze: Warnung


def rating_for(part) -> dict:
    for key, val in RATINGS.items():
        if key in part.mpn or key == part.value:
            return val
    if part.symbol == "Device:LED":
        return RATINGS["LED"]
    if "SM712" in part.value:
        return RATINGS["SM712"]
    return {}


class Result:
    def __init__(self, scenario, values):
        self.sc = scenario
        self.v = values

    def V(self, net) -> float:
        nd = node(net).lower()
        return 0.0 if nd == "0" else self.v.get(nd, float("nan"))

    def I(self, name) -> float:
        return self.v.get(f"vam_{name.lower()}#branch", float("nan"))


def check(res: Result) -> list[tuple]:
    """(Ref, Größe, Wert, Grenze, Auslastung) für alle Bauteile."""
    rows = []

    def add(ref, what, value, limit):
        if limit and not math.isnan(value):
            rows.append((ref, what, value, limit, abs(value) / limit))

    for p in design.PARTS:
        if p.group == "mech":
            continue
        n = p.pins
        kind = p.symbol.split(":")[1]
        rt = rating_for(p)
        size = next((s for s in RES_P if s in p.footprint), None)
        if p.symbol == "Device:R":
            v = res.V(n["1"]) - res.V(n["2"])
            r = num(p.value)
            add(p.ref, "P [W]", v * v / r, RES_P.get(size))
            add(p.ref, "U [V]", v, RES_V.get(size))
        elif p.symbol in ("Device:C", "Device:C_Polarized"):
            v = res.V(n["1"]) - res.V(n["2"])
            vr = float(p.value.split()[1].rstrip("V")) if len(p.value.split()) > 1 else None
            add(p.ref, "U [V]", v, vr)
            if p.symbol == "Device:C_Polarized" and v < -0.3:
                rows.append((p.ref, "Verpolung [V]", v, 0.3, 9.9))
        elif kind in ("D_Schottky", "D_Zener", "D_TVS", "LED"):
            vk, va = res.V(n["1"]), res.V(n["2"])
            i = res.I(p.ref)
            if "Vwm" in rt:
                add(p.ref, "U Sperr [V] (≤ Vwm)", vk - va, rt["Vwm"])
            if "Vr" in rt:
                add(p.ref, "U Sperr [V]", max(vk - va, 0), rt["Vr"])
            if "If" in rt:
                add(p.ref, "I [A]", max(i, 0), rt["If"])
            if "P" in rt:
                add(p.ref, "P [W]", abs((va - vk) * i), rt["P"])
        elif kind == "SM712_SOT23":
            for pad in ("1", "2"):
                v = res.V(n[pad])
                add(p.ref, f"U Pin {pad} [V]", v, rt["Vwm+"] if v >= 0 else abs(rt["Vwm-"]))
        elif kind in ("Q_NMOS", "Q_PMOS"):
            g, s, d = (n["1"], n["3"], n["2"]) if "TO-252" in p.footprint else (n["1"], n["2"], n["3"])
            vds, vgs, i = res.V(d) - res.V(s), res.V(g) - res.V(s), res.I(p.ref)
            add(p.ref, "Uds [V]", vds, rt["Vds"])
            add(p.ref, "Ugs [V]", vgs, rt["Vgs"])
            add(p.ref, "Id [A]", i, rt["Id"])
            add(p.ref, "P [W]", vds * i, rt["P"])
        elif kind == "FS8205A":
            for k, (s, gpin) in (("1", ("2", "4")), ("2", ("6", "5"))):
                vds = res.V(n["1"]) - res.V(n[s])
                vgs = res.V(n[gpin]) - res.V(n[s])
                i = res.I(f"{p.ref}_{k}")
                add(f"{p.ref}.{k}", "Uds [V]", vds, rt["Vds"])
                add(f"{p.ref}.{k}", "Ugs [V]", vgs, rt["Vgs"])
                add(f"{p.ref}.{k}", "Id [A]", i, rt["Id"])
        elif p.symbol == "Device:L":
            add(p.ref, "I DC [A]", res.I(p.ref), rt.get("Irms"))
        elif p.symbol == "Device:Fuse":
            add(p.ref, "I [A]", res.I(p.ref), RATINGS["0466002.NR"]["I"])
        if p.ref in IC_PINS:
            for pin, (lo, hi) in IC_PINS[p.ref].items():
                if isinstance(pin, tuple):
                    v = res.V(pin[0]) - res.V(pin[1])
                    label = f"U {pin[0]}–{pin[1]} [V]"
                else:
                    v = res.V(pin)
                    label = f"U {pin} [V]"
                if isinstance(hi, str):   # "VSYS+5"
                    hi = res.V(hi.split("+")[0]) + float(hi.split("+")[1])
                if v > hi:
                    rows.append((p.ref, label, v, hi, 9.9))
                elif v < lo:
                    rows.append((p.ref, label, v, lo, 9.9))
                elif v >= 0 and hi > 0:
                    add(p.ref, label, v, hi)
                elif v < 0 and lo < 0:
                    add(p.ref, label, v, lo)
    return rows


def switching(res: Result) -> list[tuple]:
    """Schaltbelastung CN3795-Leistungsteil (310 kHz, CCM) und TPS61040 (PFM, 400 mA Spitze)."""
    rows = []
    vin, vout = res.V("VSOL"), res.V("VSYS")
    iout = (res.V("CHG_CSP") - res.V("VSYS")) / 0.040
    if iout > 0.05 and vin > vout + 0.5:
        f, L = 310e3, 15e-6
        D = min(0.94, (vout + 0.45) / (vin + 0.45))
        di = (vin - vout) * D / (L * f)
        ipk = iout + di / 2
        q1_cond = iout ** 2 * D * 0.035
        q1_sw = 0.5 * vin * iout * 60e-9 * f
        d3_avg = iout * (1 - D)
        cin_rms = iout * math.sqrt(D * (1 - D))
        # Rippelstrom-Aufteilung Elko (ESR 0,3 Ω) gegen die Keramik an VSOL (10 µF/50 V: bei Vin ~35 % wirksam)
        c_cer = sum(num(q.value) for q in design.PARTS
                    if q.symbol == "Device:C" and "VSOL" in q.pins.values() and num(q.value) >= 1e-6)
        x_cer = 1 / (2 * math.pi * f * c_cer * 0.35)
        elko_share = x_cer / (x_cer + 0.30)
        rows += [
            ("Q1", "P Schalt+Leit [W]", q1_sw + q1_cond, RATINGS["AOD4189"]["P"]),
            ("Q1", "I Spitze [A]", ipk, RATINGS["AOD4189"]["Id"]),
            ("D3", "I Mittel [A]", d3_avg, RATINGS["B540C"]["If"]),
            ("D3", "P [W]", d3_avg * 0.45, RATINGS["B540C"]["P"]),
            ("L1", "I Spitze [A] (Isat)", ipk, RATINGS["SRP1245A-150M"]["Isat"]),
            ("L1", "I eff [A]", math.sqrt(iout ** 2 + di ** 2 / 12), RATINGS["SRP1245A-150M"]["Irms"]),
            ("C2", "Rippelstrom [A]", cin_rms * elko_share, RATINGS["EEE-FK1V101P"]["Irip"]),
            ("C3/C4/C22", "Rippelstrom je C [A]", cin_rms * (1 - elko_share) * 10e-6 / c_cer, 3.0),
            ("R1", "P [W]", iout ** 2 * 0.040, 2.0),
        ]
    v12, vin_b = res.V("V12_RAW"), res.V("VSYS")
    if res.V("SENS_EN") > 1.5 and v12 > vin_b + 1:
        iout = res.sc.probe_ma / 1000 if res.V("V12_PROBE") > 8 else 0
        d = 1 - vin_b * 0.85 / v12
        iin = iout * v12 / (vin_b * 0.85)
        di = vin_b * d / (4.7e-6 * 1.6e6)
        rows += [
            ("L3", "I Spitze [A] (Isat)", iin + di / 2, RATINGS["SRN6045TA-4R7Y"]["Isat"]),
            ("L3", "I eff [A]", iin, RATINGS["SRN6045TA-4R7Y"]["Irms"]),
            ("U5", "I Schalter Spitze [A] (Grenze min 1,6)", iin + di / 2, 1.6),
            ("D5", "I Mittel [A]", iout, RATINGS["MBR0540"]["If"]),
            ("D5", "U Sperr [V]", v12, RATINGS["MBR0540"]["Vr"]),
            ("U5", "U SW [V]", v12 + 0.4, 25),
        ]
    return [(r, w, v, lim, v / lim) for r, w, v, lim in rows]
