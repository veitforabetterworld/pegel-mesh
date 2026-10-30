"""Alle Betriebsfälle simulieren, Bauteilbelastung und Funktion prüfen. Aufruf: python3 verify/run_stress.py"""

import os
import sys

from board import settle
from ngspice import NgSpice
from scenarios import CASES, measure
from stress import WARN, Result, check, switching

HERE = os.path.dirname(os.path.abspath(__file__))
REPORT = os.path.join(HERE, "report")


def main():
    ng = NgSpice()
    worst: dict[tuple, tuple] = {}
    func = []
    for sc, expect in CASES:
        res = Result(sc, settle(ng, sc))
        m = measure(res)
        for key, (lo, hi) in expect.items():
            ok = lo <= m[key] <= hi
            func.append((sc.name, key, m[key], lo, hi, ok))
        for ref, what, value, limit, load in check(res) + switching(res):
            k = (ref, what)
            if k not in worst or load > worst[k][3]:
                worst[k] = (value, limit, sc.name, load)
        print(f"{sc.name:45s} " + " ".join(f"{k}={v:.3g}" for k, v in m.items()))

    os.makedirs(REPORT, exist_ok=True)
    lines = ["# Bauteilbelastung und Funktion (SPICE)", "",
             "Größte Auslastung je Bauteil über alle Betriebsfälle. ⚠ ab 80 %, ✗ über der Grenze.", "",
             "| Bauteil | Größe | Wert | Grenze | Auslastung | Fall |", "|---|---|---:|---:|---:|---|"]
    over = []
    for (ref, what), (value, limit, case, load) in sorted(worst.items(), key=lambda kv: -kv[1][3]):
        mark = "✗" if load > 1 else "⚠" if load >= WARN else ""
        if load >= WARN:
            over.append((ref, what, value, limit, case, load))
        lines.append(f"| {ref} | {what} | {value:.3g} | {limit:.3g} | {load * 100:.0f} % {mark} | {case} |")
    lines += ["", "## Funktion", "", "| Fall | Größe | Wert | Soll | |", "|---|---|---:|---|---|"]
    for case, key, value, lo, hi, ok in func:
        lines.append(f"| {case} | {key} | {value:.3g} | {lo:g} … {hi:g} | {'✓' if ok else '✗'} |")
    with open(os.path.join(REPORT, "stress.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    print("\nAuslastung ≥ 80 %:")
    for ref, what, value, limit, case, load in over:
        print(f"  {ref:7s} {what:28s} {value:9.3g} / {limit:<8.3g} {load * 100:5.0f} %  {case}")
    print("\nFunktion nicht erfüllt:")
    for case, key, value, lo, hi, ok in func:
        if not ok:
            print(f"  {case}: {key} = {value:.3g} (Soll {lo:g} … {hi:g})")
    return 1 if over and any(o[5] > 1 for o in over) or not all(f[5] for f in func) else 0


if __name__ == "__main__":
    sys.exit(main())
