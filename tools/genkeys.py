"""Erzeugt die Schlüssel für Empfänger und Sender als C-Header unter secrets/.

Jeder Knoten bekommt eine feste MeshCore-Identität (Ed25519), damit Sender und Empfänger
sich ohne Kontaktaustausch kennen. Jeder Sender bekommt zusätzlich einen eigenen
HMAC-Schlüssel für die Messpakete; der Empfänger kennt alle.

Bestehende Schlüssel werden nicht überschrieben (sonst müssten alle Geräte neu geflasht
werden); --force erzwingt das.

    py -3.12 tools/genkeys.py            # Sender A und B
    py -3.12 tools/genkeys.py A B C      # weitere Sender
"""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

ROOT = Path(__file__).resolve().parent.parent
SECRETS = ROOT / "secrets"
KEYS_JSON = SECRETS / "keys.json"


def new_identity():
    """MeshCore-Format (orlp/ed25519): prv = SHA512(seed), geklemmt; pub = Ed25519-Public-Key."""
    while True:
        seed = os.urandom(32)
        pub = Ed25519PrivateKey.from_private_bytes(seed).public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        if pub[0] in (0x00, 0xFF):  # MeshCore lehnt diese Präfixe ab
            continue
        prv = bytearray(hashlib.sha512(seed).digest())
        prv[0] &= 248
        prv[31] &= 63
        prv[31] |= 64
        return {"prv": prv.hex(), "pub": pub.hex()}


def c_bytes(hex_str):
    b = bytes.fromhex(hex_str)
    return "{ " + ", ".join(f"0x{x:02x}" for x in b) + " }"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("senders", nargs="*", default=["A", "B"])
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    SECRETS.mkdir(exist_ok=True)
    if KEYS_JSON.exists() and not args.force:
        keys = json.loads(KEYS_JSON.read_text(encoding="utf-8"))
    else:
        keys = {"receiver": new_identity(), "senders": {}}
    for name in args.senders:
        if name not in keys["senders"]:
            ident = new_identity()
            ident["hmac"] = os.urandom(32).hex()
            keys["senders"][name] = ident
    KEYS_JSON.write_text(json.dumps(keys, indent=2), encoding="utf-8")

    senders = keys["senders"]
    names = list(senders)
    rx = keys["receiver"]
    header = "#pragma once\n// Erzeugt von tools/genkeys.py -- NICHT einchecken.\n\n"

    for name, s in senders.items():
        (SECRETS / f"secrets_sender_{name.lower()}.h").write_text(
            header
            + f'#define PEGEL_SENDER_NAME   "{name}"\n'
            + f'#define PEGEL_SENDER_PRV    "{s["prv"]}"\n'
            + f'#define PEGEL_SENDER_PUB    "{s["pub"]}"\n'
            + f'#define PEGEL_RECEIVER_PUB  "{rx["pub"]}"\n\n'
            + f"static const uint8_t PEGEL_HMAC_KEY[32] = {c_bytes(s['hmac'])};\n",
            encoding="utf-8",
        )

    (SECRETS / "secrets_receiver.h").write_text(
        header
        + f'#define PEGEL_RECEIVER_PRV  "{rx["prv"]}"\n'
        + f'#define PEGEL_RECEIVER_PUB  "{rx["pub"]}"\n'
        + f"#define PEGEL_SENDER_COUNT  {len(names)}\n\n"
        + "static const char* const PEGEL_SENDER_NAMES[PEGEL_SENDER_COUNT] = { "
        + ", ".join(f'"{n}"' for n in names) + " };\n"
        + "static const char* const PEGEL_SENDER_PUBS[PEGEL_SENDER_COUNT] = {\n"
        + "".join(f'  "{senders[n]["pub"]}",\n' for n in names) + "};\n"
        + "static const uint8_t PEGEL_HMAC_KEYS[PEGEL_SENDER_COUNT][32] = {\n"
        + "".join(f"  {c_bytes(senders[n]['hmac'])},\n" for n in names) + "};\n",
        encoding="utf-8",
    )

    wifi = SECRETS / "receiver_wifi.h"
    if not wifi.exists():
        ids = ", ".join(f'"pegel-mesh-{n.lower()}"' for n in names)
        labels = ", ".join(f'"Pegel {n} (Test)"' for n in names)
        zeros = ", ".join("0.0f" for _ in names)
        wifi.write_text(
            header
            + "// Von Hand ausfüllen. Die Listen folgen der Sender-Reihenfolge aus secrets_receiver.h.\n"
            + '#define PEGEL_WIFI_SSID   ""\n'
            + '#define PEGEL_WIFI_PASS   ""\n'
            + '#define PEGEL_API_URL     ""   // z. B. "https://example.org", ohne / am Ende\n'
            + '#define PEGEL_API_KEY     ""   // aus Admin > API-Keys\n'
            + '#define PEGEL_API_CA      ""   // optional: Root-Zertifikat (PEM); leer = Zertifikat nicht geprüft\n\n'
            + f"static const char* const PEGEL_STATION_IDS[PEGEL_SENDER_COUNT] = {{ {ids} }};\n"
            + f"static const char* const PEGEL_STATION_NAMES[PEGEL_SENDER_COUNT] = {{ {labels} }};\n"
            + f"static const float PEGEL_STATION_LAT[PEGEL_SENDER_COUNT] = {{ {zeros} }};\n"
            + f"static const float PEGEL_STATION_LON[PEGEL_SENDER_COUNT] = {{ {zeros} }};\n",
            encoding="utf-8",
        )

    print(f"receiver pub {rx['pub']}")
    for n in names:
        print(f"sender {n}  pub {senders[n]['pub']}")
    print(f"headers in {SECRETS}")


if __name__ == "__main__":
    sys.exit(main())
