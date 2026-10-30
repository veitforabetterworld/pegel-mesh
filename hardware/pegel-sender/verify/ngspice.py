"""ngspice aus der KiCad-Installation (ngspice.dll / libngspice) über die Shared-Library-Schnittstelle."""

import ctypes
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import kicad_env  # noqa: E402


class VectorInfo(ctypes.Structure):
    _fields_ = [
        ("v_name", ctypes.c_char_p),
        ("v_type", ctypes.c_int),
        ("v_flags", ctypes.c_short),
        ("v_realdata", ctypes.POINTER(ctypes.c_double)),
        ("v_compdata", ctypes.c_void_p),
        ("v_length", ctypes.c_int),
    ]


def _library_path() -> str:
    win = kicad_env.windows_bin()
    if win and os.path.isfile(os.path.join(win, "ngspice.dll")):
        return os.path.join(win, "ngspice.dll")
    for path in ("/usr/lib/libngspice.so.0", "/usr/lib/libngspice.so", "/usr/lib/x86_64-linux-gnu/libngspice.so.0"):
        if os.path.isfile(path):
            return path
    raise SystemExit("ngspice nicht gefunden (KiCad installieren oder libngspice)")


_SEND_CHAR = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p)
_SEND_STAT = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p)
_EXIT = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int, ctypes.c_bool, ctypes.c_bool, ctypes.c_int, ctypes.c_void_p)
_BG = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_bool, ctypes.c_int, ctypes.c_void_p)


class NgSpice:
    def __init__(self, echo=False):
        path = _library_path()
        if os.name == "nt":
            os.add_dll_directory(os.path.dirname(path))
        self.lib = ctypes.CDLL(path)
        self.echo = echo
        self.log = []
        self._cb = (
            _SEND_CHAR(self._on_char),
            _SEND_STAT(lambda *_: 0),
            _EXIT(lambda *_: 0),
            None,
            None,
            _BG(lambda *_: 0),
        )
        self.lib.ngSpice_Init(self._cb[0], self._cb[1], self._cb[2], None, None, self._cb[5], None)
        self.lib.ngGet_Vec_Info.restype = ctypes.POINTER(VectorInfo)
        self.lib.ngSpice_CurPlot.restype = ctypes.c_char_p
        self.lib.ngSpice_AllVecs.restype = ctypes.POINTER(ctypes.c_char_p)

    def _on_char(self, text, _id, _user):
        line = text.decode(errors="replace")
        self.log.append(line)
        if self.echo:
            print(line)
        return 0

    def cmd(self, command: str):
        self.lib.ngSpice_Command(command.encode())

    def run(self, netlist: str) -> dict[str, list[float]]:
        """Netzliste laden und ausführen (Analysekarte in der Netzliste). Gibt alle Vektoren des Plots."""
        self.log.clear()
        self.cmd("destroy all")
        self.cmd("remcirc")
        lines = [ln for ln in netlist.splitlines() if ln.strip()]
        arr = (ctypes.c_char_p * (len(lines) + 1))(*[ln.encode() for ln in lines], None)
        if self.lib.ngSpice_Circ(arr) != 0:
            raise RuntimeError("ngspice: Netzliste abgelehnt\n" + "\n".join(self.log[-20:]))
        self.cmd("run")
        errors = [ln for ln in self.log if ("error" in ln.lower() and "no error" not in ln.lower())
                  or "aborted" in ln or "too small" in ln]
        if errors:
            raise RuntimeError("ngspice:\n" + "\n".join(errors[:20]))
        plot = self.lib.ngSpice_CurPlot()
        names = self.lib.ngSpice_AllVecs(plot)
        out = {}
        i = 0
        while names[i]:
            name = names[i].decode()
            info = self.lib.ngGet_Vec_Info(f"{plot.decode()}.{name}".encode()).contents
            if info.v_realdata:
                out[name.lower()] = [info.v_realdata[k] for k in range(info.v_length)]
            i += 1
        return out


if __name__ == "__main__":
    ng = NgSpice()
    res = ng.run("""test
V1 in 0 5
R1 in out 1k
R2 out 0 1k
.op
.end""")
    print(res)
