"""Bauteilbelastung je Szenario gegen Grenzwerte, plus Schaltbelastung der Wandler (analytisch)."""

import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import design  # noqa: E402
from board import R_SHUNT, node, num  # noqa: E402
from models import IC_PINS, RATINGS, RES_P, RES_V  # noqa: E402

WARN = 0.8   # ab 80 % der Grenze: Warnung


def rating_for(part) -> dict:
    for key, val in RATINGS.items():
        if key in part.mpn or key == part.value:
            return val
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
        elif kind in ("D_Schottky", "D_Zener", "D_TVS", "D"):
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
            g, s, d = n["1"], n["2"], n["3"]
            vds, vgs, i = res.V(d) - res.V(s), res.V(g) - res.V(s), res.I(p.ref)
            add(p.ref, "Uds [V]", vds, rt["Vds"])
            add(p.ref, "Ugs [V]", vgs, rt["Vgs"])
            add(p.ref, "Id [A]", i, rt["Id"])
            add(p.ref, "P [W]", vds * i, rt["P"])
        elif p.symbol == "Device:L":
            add(p.ref, "I DC [A]", res.I(p.ref), rt.get("Irms"))
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
    """Schaltbelastung TPS5430-Lader (500 kHz, CCM) und TPS61040 (PFM, Spitzenstrom 0,4 A typ., 0,475 A max.)."""
    rows = []
    vin, vout = res.V("VSOL"), res.V("CHG_OUT")
    iout = res.I("L1")
    if iout > 0.05 and vin > vout + 0.5:
        f, L = 500e3, 15e-6
        D = min(0.87, (vout + 0.45) / (vin + 0.45))
        di = (vin - vout) * D / (L * f)
        ipk = iout + di / 2
        cin_rms = iout * math.sqrt(D * (1 - D))
        rows += [
            ("U1", "I Schalter Spitze [A] (Strombegrenzung min. 4 A)", ipk, 4.0),
            ("D3", "I Mittel [A]", iout * (1 - D), RATINGS["SS54"]["If"]),
            ("D3", "P [W]", iout * (1 - D) * 0.45, RATINGS["SS54"]["P"]),
            ("L1", "I Spitze [A] (Isat)", ipk, RATINGS["RLB0914-150KL"]["Isat"]),
            ("L1", "I eff [A]", math.sqrt(iout ** 2 + di ** 2 / 12), RATINGS["RLB0914-150KL"]["Irms"]),
            ("C1–C3", "Rippelstrom je C [A]", cin_rms / 3, 2.0),
            ("R15/R16", "P je R [W]", (res.V("BAT_N") ** 2) / (2 * R_SHUNT) / 2, 0.25),
        ]
    v12, vin_b = res.V("V12_RAW"), res.V("VSYS")
    if res.V("SENS_EN") > 1.5 and v12 > vin_b + 1:
        iout = res.sc.probe_ma / 1000 if res.V("V12_PROBE") > 8 else 0
        ilim_max = 0.475
        rows += [
            ("L2", "I Spitze [A] (Isat)", ilim_max, RATINGS["RLB0912-100KL"]["Isat"]),
            ("D7", "I Spitze [A]", ilim_max, 2.0),
            ("D7", "I Mittel [A]", iout, RATINGS["B0540W"]["If"]),
            ("D7", "U Sperr [V]", v12, RATINGS["B0540W"]["Vr"]),
            ("U5", "U SW [V]", v12 + 0.4, 28),
        ]
    return [(r, w, v, lim, v / lim) for r, w, v, lim in rows]
