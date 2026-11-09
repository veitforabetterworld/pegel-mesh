#!/usr/bin/env bash
# Liest den Log-Ringpuffer des Trackers per SWD (OpenOCD über den CMSIS-DAP des XIAO nRF54LM20A), ohne die CPU
# anzuhalten. Unabhängig von der USB-Seriell-Brücke, die nach System OFF oft hängt.
#
#   bash tools/tracker_log.sh [tracker_t1]
set -euo pipefail
ENV="${1:-tracker_t1}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ELF="$ROOT/MeshCore-nrf54/.pio/build/$ENV/firmware.elf"
PIO="${PLATFORMIO_CORE_DIR:-$HOME/.platformio}"
NM="$PIO/packages/toolchain-gccarmnoneeabi@1.70201.0/bin/arm-none-eabi-nm"
OCD="$PIO/packages/tool-openocd"
addr() { "$NM" "$ELF" | awk -v s="$1" '$3==s {print "0x"$1}'; }
LOG=$(addr trk_log)
POS=$(addr trk_log_pos)
TMPD="$(mktemp -d)"
if command -v cygpath >/dev/null 2>&1; then TMPD="$(cygpath -m "$TMPD")"; fi   # OpenOCD unter Windows
cat > "$TMPD/dump.cfg" <<EOF
init
set pos [read_memory $POS 32 1]
echo "POS \$pos"
dump_image "$TMPD/log.bin" $LOG 2048
exit
EOF
OUT=$("$OCD/bin/openocd" -s "$OCD/openocd/scripts" -f interface/cmsis-dap.cfg -f target/nordic/nrf54l.cfg \
  -f "$TMPD/dump.cfg" 2>&1)
P=$(echo "$OUT" | sed -n 's/^POS \(0x[0-9a-fA-F]*\).*/\1/p')
if [ -z "$P" ]; then echo "$OUT" | tail -5; exit 1; fi
P=$((P))
if command -v py >/dev/null 2>&1; then PY="py -3"; else PY=python3; fi
cat > "$TMPD/show.py" <<'PYEOF'
import sys
b = open(sys.argv[1], "rb").read()
p = int(sys.argv[2])
n = len(b)
s = b[p % n:] + b[:p % n] if p >= n else b[:p]
print(s.decode("ascii", "replace"))
PYEOF
$PY "$TMPD/show.py" "$TMPD/log.bin" "$P"
