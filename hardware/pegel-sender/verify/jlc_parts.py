"""Prüft die LCSC-Nummern einer Platine gegen die JLCPCB-Teilebibliothek: Basic, Preferred oder Extended, Lager.

    python verify/jlc_parts.py                    # Teile aus design.py (dieses Verzeichnis)
    python verify/jlc_parts.py ../pegel-sender-v2  # Teile aus design.py eines anderen Platinenordners
    python verify/jlc_parts.py --search "10uH 1210 inductor"   # Suche, Basic/Preferred zuerst

Extended-Teile kosten bei JLCPCB je Sorte und Auftrag eine Rüstgebühr (~3 USD); Basic und Preferred nicht.
"""
import importlib.util
import json
import sys
import urllib.request
from pathlib import Path

API = "https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList"


def query(keyword, size=10):
    body = json.dumps({"keyword": keyword, "currentPage": 1, "pageSize": size}).encode()
    req = urllib.request.Request(API, body, {"Content-Type": "application/json"})
    data = json.loads(urllib.request.urlopen(req, timeout=60).read())
    return data["data"]["componentPageInfo"]["list"] or []


def kind(item):
    if item.get("componentLibraryType") == "base":
        return "basic"
    if item.get("preferredComponentFlag"):
        return "preferred"
    return "EXTENDED"


def check(folder):
    spec = importlib.util.spec_from_file_location("design", Path(folder) / "design.py")
    design = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(design)
    bad = 0
    seen = {}
    for p in design.PARTS:
        if not p.lcsc or p.hand or p.dnp:
            continue
        seen.setdefault(p.lcsc, []).append(p)
    for code, parts in sorted(seen.items(), key=lambda kv: kv[1][0].ref):
        hits = [i for i in query(code, 5) if i.get("componentCode") == code]
        refs = ",".join(x.ref for x in parts)
        if not hits:
            print(f"{code:10s} {refs:20s} NICHT GEFUNDEN")
            bad += 1
            continue
        i = hits[0]
        k = kind(i)
        bad += k == "EXTENDED" or i.get("stockCount", 0) < 100
        print(f"{code:10s} {refs:20s} {k:9s} Lager {i.get('stockCount', 0):>9d}  {i.get('componentModelEn', '')}")
    print(f"\n{len(seen)} Sorten, davon {bad} Extended, nicht gefunden oder kaum auf Lager")
    return bad


def search(keyword):
    items = query(keyword, 30)
    items.sort(key=lambda i: (kind(i) == "EXTENDED", -i.get("stockCount", 0)))
    for i in items:
        print(f"{i.get('componentCode'):10s} {kind(i):9s} Lager {i.get('stockCount', 0):>9d}  "
              f"{i.get('componentModelEn', '')}  {i.get('componentSpecificationEn', '')}  {i.get('describe', '')[:60]}")


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--search":
        search(" ".join(sys.argv[2:]))
    else:
        sys.exit(1 if check(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent) else 0)
