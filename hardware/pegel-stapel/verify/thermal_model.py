"""3D-Wärmemodell der 5-V-Ladeplatine im Stapel (Finite Volumen auf ungleichmäßigem Quadergitter).

Aufbau von unten: Styropor | Akku 700 mAh | Klebeschicht | Ladeplatine mit Kupfer, Vias, Bauteilen | Buchsen mit
Stiften | XIAO | Wio-SX1262 | Styropor. Keine RS485-Platine. Alle Temperaturen sind Übertemperaturen zur Außenluft.

Das Modell ist linear: Wärmeleitung, Strahlung und Luft in den Hohlräumen als wirksame Leitfähigkeit, außen fester
Übergangswert. Deshalb überlagern sich die Quellen (Heizung, Lader), und ein auf wenige Zustände reduziertes Modell
(rationale Krylov-Projektion, Reduced) rechnet den Thermostat über Stunden ohne neues Gittermodell.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass

import numpy as np
from matplotlib.path import Path as MplPath
from numba import njit
from scipy.linalg import expm

HERE = os.path.dirname(os.path.abspath(__file__))
STAPEL = os.path.dirname(HERE)
PCB = os.path.join(STAPEL, "lader-5v", "pegel-lader-5v.kicad_pcb")
W, H = 20.955, 17.78
K_CU = 390.0


def load_geometry() -> dict:
    sys.path.insert(0, os.path.join(STAPEL, "tools"))
    import kicad_env
    out = subprocess.run([kicad_env.pcbnew_python(), os.path.join(HERE, "thermal_geometry.py"), PCB],
                         check=True, capture_output=True, text=True).stdout
    return json.loads(next(line for line in out.splitlines() if line.startswith("JSON"))[4:])


@dataclass(frozen=True)
class Setup:
    cell: tuple = (39.5, 31.5, 5.9)    # mm, RS PRO 700 mAh (Datenblatt)
    cell_mass: float = 15.0            # g
    k_cell_plane: float = 26.5         # W/mK, Lin et al., Pouchzelle in der Ebene
    k_cell_thick: float = 0.51         # W/mK, durch die Lagen
    gap: float = 1.2                   # mm zwischen Platine und Akku (Lötstellen der Buchsen + Isolierung)
    k_gap: float = 0.10                # W/mK: Schaumklebeband. Luft ~0,033, Wärmeleitpad ~1,5
    wall: float = 30.0                 # mm Styropor
    k_eps: float = 0.035               # W/mK
    k_air: float = 0.055               # W/mK wirksam: Leitung 0,026 + Strahlung über einige mm
    h_out: float = 10.0                # W/m²K außen (ruhige Luft + Strahlung), Wind ~25
    tight: bool = False                # Styropor bündig ausgeschnitten statt rechteckiger Hohlraum
    wire_mm2: float = 0.205            # Querschnitt je 5-V-Ader (AWG 24), 0 = ohne Leitung
    k_fr4: float = 0.8                 # W/mK in der Ebene (quer 0,35)
    cu_um: float = 35.0
    k_pin: float = 80.0                # W/mK Stifte/Kontakte
    h_step: float = 0.25               # mm Raster auf der Platine


def axis(breaks, steps):
    """Gitterlinien: breaks sind Zwangslinien, steps die größte Zellbreite je Abschnitt."""
    out = [breaks[0]]
    for a, b, s in zip(breaks, breaks[1:], steps):
        if b - a < 1e-9:
            continue
        n = max(1, int(np.ceil((b - a) / s - 1e-6)))
        out += list(np.linspace(a, b, n + 1)[1:])
    return np.array(out)


class Model:
    def __init__(self, setup: Setup, geo: dict, copper: bool = True):
        self.s, self.geo = setup, geo
        s = setup
        bl, bw, bt = s.cell
        self.bx = (W / 2 - bl / 2, W / 2 + bl / 2)
        self.by = (H / 2 - bw / 2, H / 2 + bw / 2)
        self.bz = (-s.gap - bt, -s.gap)
        self.pcb_t = t = geo["thickness"]
        self.cav = (min(self.bx[0], 0), min(self.by[0], 0), self.bz[0],
                    max(self.bx[1], W), max(self.by[1], H), t + 19.0)
        x0, y0, z0, x1, y1, z1 = self.cav
        w = s.wall
        hs = s.h_step
        f = hs / 0.25
        self.ex = axis(self._plane(x0, x1, W, w), self._plane_steps(x0, x1, W, w, hs, f))
        self.ey = axis(self._plane(y0, y1, H, w), self._plane_steps(y0, y1, H, w, hs, f))
        self.ez = axis([z0 - w, z0 - 10, z0 - 2, z0, -s.gap, 0, 0.2, t - 0.2, t, t + 0.10, t + 0.50, t + 0.65,
                        t + 1.75, t + 2.4, t + 8.5, t + 11.0, t + 12.0, t + 15.0, t + 16.0, t + 17.5, z1,
                        z1 + 2, z1 + 10, z1 + w],
                       [5, 2, 1, 0.6 * f, 0.4 * f, 0.2, 0.4 * f, 0.2, 0.1, 0.2 * f, 0.15, 0.4 * f, 0.65, 1.2 * f,
                        1.2 * f, 0.5 * f, 1.0 * f, 0.5 * f, 0.75 * f, 0.75 * f, 1, 2, 5])
        self.dx, self.dy, self.dz = (np.diff(e) * 1e-3 for e in (self.ex, self.ey, self.ez))
        self.xc, self.yc, self.zc = ((e[1:] + e[:-1]) / 2 for e in (self.ex, self.ey, self.ez))
        self.shape = (len(self.xc), len(self.yc), len(self.zc))
        self.vol = self.dx[:, None, None] * self.dy[None, :, None] * self.dz[None, None, :]
        self._materials(copper)
        self._couple()
        self._sources()

    @staticmethod
    def _plane(a, b, size, wall):
        pts = [a - wall, a - 10, a - 2, a]
        if a < -1.5:
            pts.append(-1.5)
        if a < 0:
            pts.append(0.0)
        pts.append(size)
        if b > size + 1.5:
            pts.append(size + 1.5)
        if b > size:
            pts.append(b)
        return pts + [b + 2, b + 10, b + wall]

    @staticmethod
    def _plane_steps(a, b, size, wall, hs, f):
        steps = [5, 2, 1]
        if a < -1.5:
            steps.append(1.2 * f)
        if a < 0:
            steps.append(0.5 * f)
        steps.append(hs)
        if b > size:
            steps.append(0.5 * f)
        if b > size + 1.5:
            steps.append(1.2 * f)
        return steps + [1, 2, 5]

    def idx(self, x0, y0, z0, x1, y1, z1):
        def rng(c, a, b):
            i, j = np.searchsorted(c, [a, b])
            if i == j:    # dünner als eine Zelle: die nächste nehmen
                i = min(int(np.argmin(np.abs(c - (a + b) / 2))), len(c) - 1)
                j = i + 1
            return slice(i, j)
        return rng(self.xc, x0, x1), rng(self.yc, y0, y1), rng(self.zc, z0, z1)

    def fill(self, region, kxy, kz=None, rhoc=2.0e6):
        self.kx[region] = kxy
        self.ky[region] = kxy
        self.kz[region] = kxy if kz is None else kz
        self.rhoc[region] = rhoc

    def _materials(self, copper):
        s, t = self.s, self.pcb_t
        self.kx, self.ky, self.kz, self.rhoc = (np.full(self.shape, v) for v in (s.k_eps, s.k_eps, s.k_eps, 20 * 1300.))
        x0, y0, z0, x1, y1, z1 = self.cav
        fill_k = (s.k_eps, None, 20 * 1300.) if s.tight else (s.k_air, None, 1.2e3)
        self.fill(self.idx(*self.cav), *fill_k)
        self.fill(self.idx(0, 0, t, W, H, z1), s.k_air, None, 1.2e3)

        bl, bw, bt = s.cell
        rc_cell = s.cell_mass * 1e-3 * 1100 / (bl * bw * bt * 1e-9)
        self.battery = self.idx(self.bx[0], self.by[0], self.bz[0], self.bx[1], self.by[1], self.bz[1])
        self.fill(self.battery, s.k_cell_plane, s.k_cell_thick, rc_cell)
        self.fill(self.idx(0, 0, -s.gap, W, H, 0), s.k_gap, None, 0.8e6)
        self.board = self.idx(0, 0, 0, W, H, t)
        self.fill(self.board, s.k_fr4, 0.35, 1850 * 1100.)

        X, Y = np.meshgrid(self.xc, self.yc, indexing="ij")
        front, back = np.zeros(X.shape, bool), np.zeros(X.shape, bool)
        for p in self.geo["pads"]:
            a, b, c, d = p["box"]
            if p["round"]:
                m = np.hypot(X - p["at"][0], Y - p["at"][1]) <= (c - a) / 2
            else:
                m = (X >= a) & (X <= c) & (Y >= b) & (Y <= d)
            if p["front"]:
                front |= m
            if p["back"]:
                back |= m
        for tr in self.geo["tracks"]:
            (ax, ay), (bx, by) = tr["a"], tr["b"]
            vx, vy = bx - ax, by - ay
            u = np.clip(((X - ax) * vx + (Y - ay) * vy) / max(vx * vx + vy * vy, 1e-12), 0, 1)
            m = np.hypot(X - ax - u * vx, Y - ay - u * vy) <= tr["w"] / 2
            if tr["front"]:
                front |= m
            else:
                back |= m
        points = np.column_stack((X.ravel(), Y.ravel()))
        for zone in self.geo["zones"]:
            outer, *holes = (MplPath(ring).contains_points(points).reshape(X.shape) for ring in zone["rings"])
            for hole in holes:
                outer &= ~hole
            if zone["front"]:
                front |= outer
            else:
                back |= outer
        for v in self.geo["vias"]:
            m = np.hypot(X - v["at"][0], Y - v["at"][1]) <= v["d"] / 2
            front |= m
            back |= m
        self.cu_front, self.cu_back = front, back
        if copper:
            for mask, z in ((front, t - 0.1), (back, 0.1)):
                k = int(np.argmin(np.abs(self.zc - z)))
                th = self.dz[k] * 1e6
                kp = (K_CU * s.cu_um + s.k_fr4 * (th - s.cu_um)) / th
                self.kx[:, :, k][mask] = kp
                self.ky[:, :, k][mask] = kp
            for v in self.geo["vias"]:
                i, j, k = self.idx(v["at"][0] - .01, v["at"][1] - .01, 0, v["at"][0] + .01, v["at"][1] + .01, t)
                r = v["drill"] / 2
                barrel = np.pi * ((r + 0.02) ** 2 - r ** 2) * 1e-6      # 20 µm Hülse
                area = self.dx[i].sum() * self.dy[j].sum()
                self.kz[i, j, k] = K_CU * barrel / area + 0.35

        for b in self.geo["bodies"]:
            self._component(b)

        # XIAO und Wio-SX1262: 4 Lagen mit Masseflächen, Schirmblech bzw. Modul
        self.fill(self.idx(0, 0, t + 11.0, W, H, t + 12.0), 20.0, 0.4, 2.0e6)
        self.fill(self.idx(4, 3, t + 12.0, W - 3, H - 3, t + 13.5), 15.0, 1.0, 2.0e6)
        self.fill(self.idx(0, 0, t + 15.0, W, H, t + 16.0), 20.0, 0.4, 2.0e6)
        self.fill(self.idx(4, 3, t + 16.0, W - 3, H - 3, t + 17.5), 15.0, 1.0, 2.0e6)

        # 14 Stifte als leitende Säule mit echtem Querschnitt (0,41 mm²), von der Lötstelle bis zum Wio
        for p in self.geo["pads"]:
            if not p["drill"]:
                continue
            px, py = p["at"]
            i, j, k = self.idx(px - 0.32, py - 0.32, 0, px + 0.32, py + 0.32, t + 16.0)
            area = self.dx[i].sum() * self.dy[j].sum()
            self.kz[i, j, k] = s.k_pin * 0.41e-6 / area
            i, j, k = self.idx(px - 0.5, py - 0.5, 0, px + 0.5, py + 0.5, t)
            self.fill((i, j, k), 50.0, 50.0, 2.5e6)

    def _component(self, b):
        t, (x0, y0, x1, y1), fp = self.pcb_t, b["box"], b["fp"]
        pads = [p for p in self.geo["pads"] if p["ref"] == b["ref"]]
        if "Socket" in fp:
            self.fill(self.idx(x0, y0, t, x1, y1, t + 8.5), 0.25, None, 1.7e6)
        elif "1206" in fp or "0603" in fp:
            h = 0.65 if "1206" in fp else 0.5
            k = 25.0 if "1206" in fp else (3.0 if b["ref"].startswith("C") else 25.0)
            self.fill(self.idx(x0, y0, t + 0.1, x1, y1, t + h), k, None, 3.0e6)
            self.fill(self.idx(x0, y0, t, x1, y1, t + 0.1), 0.3, None, 1.5e6)
            for p in pads:    # Lot unter den Endkappen
                a, c, d, e = p["box"]
                self.fill(self.idx(max(a, x0), max(c, y0), t, min(d, x1), min(e, y1), t + 0.1), 50.0, None, 2.0e6)
                self.fill(self.idx(max(a, x0), max(c, y0), t + 0.1, min(d, x1), min(e, y1), t + h), 40.0, None, 3.0e6)
        else:
            h = {"SOT-23": 1.0, "SOIC": 1.75}.get(next((k for k in ("SOT-23", "SOIC") if k in fp), ""), 2.3)
            self.fill(self.idx(x0, y0, t + 0.1, x1, y1, t + h), 0.9, None, 1.8e6)
            self.fill(self.idx(x0, y0, t, x1, y1, t + 0.1), 0.2, None, 1.5e6)
            for p in pads:    # Anschlussbeine
                a, c, d, e = p["box"]
                self.fill(self.idx(a + .1, c + .1, t, d - .1, e - .1, t + 0.5), 30.0, None, 3.0e6)

    def _couple(self):
        s = self.s
        dx, dy, dz = self.dx[:, None, None], self.dy[None, :, None], self.dz[None, None, :]
        rx, ry, rz = dx / (2 * self.kx), dy / (2 * self.ky), dz / (2 * self.kz)
        self.gx = (dy * dz) / (rx[:-1] + rx[1:])
        self.gy = (dx * dz) / (ry[:, :-1] + ry[:, 1:])
        self.gz = (dx * dy) / (rz[:, :, :-1] + rz[:, :, 1:])
        g = np.zeros(self.shape)
        Ri = 1.0 / s.h_out
        g[[0, -1]] += (dy * dz) / (rx[[0, -1]] + Ri)
        g[:, [0, -1]] += (dx * dz) / (ry[:, [0, -1]] + Ri)
        g[:, :, [0, -1]] += (dx * dy) / (rz[:, :, [0, -1]] + Ri)
        self.g_box = g.copy()
        if s.wire_mm2:    # 5-V-Adern durch die Wand, außen als Rippe
            a = s.wire_mm2 * 1e-6
            inside = K_CU * a / ((s.wall + 10) * 1e-3)
            outside = np.sqrt(15.0 * np.pi * 1.2e-3 * K_CU * a)
            for p in self.geo["pads"]:
                if p["ref"] == "J1":
                    r = self.idx(p["box"][0], p["box"][1], 0, p["box"][2], p["box"][3], 0.2)
                    g[r] += (1 / (1 / inside + 1 / outside)) / g[r].size
        self.g_amb = g
        d = g.copy()
        d[:-1] += self.gx
        d[1:] += self.gx
        d[:, :-1] += self.gy
        d[:, 1:] += self.gy
        d[:, :, :-1] += self.gz
        d[:, :, 1:] += self.gz
        self.diag = d
        self.cap = self.rhoc * self.vol

    def source(self, region, watts):
        q = np.zeros(self.shape)
        v = self.vol[region]
        q[region] = watts * v / v.sum()
        return q

    def _sources(self):
        """Quellen bei 5,0 V: 'heat' (Heizbetrieb), 'charge' (Laden mit 100 mA bei 3,7 V im Akku)."""
        t = self.pcb_t
        body = {b["ref"]: b for b in self.geo["bodies"]}
        self.heaters = {r: b for r, b in body.items() if "1206" in b["fp"]}
        n = len(self.heaters)
        ohm = float(next(iter(self.heaters.values()))["value"])
        r_q1, r_q4 = 0.060, 0.030       # AO3401A, AO3400A bei 4,9 V Gate
        i = 5.0 / (ohm / n + r_q1 + r_q4)
        heat = np.zeros(self.shape)
        self.film = {}
        for ref, b in self.heaters.items():
            x0, y0, x1, y1 = b["box"]
            self.film[ref] = self.idx(x0 + .2, y0 + .55, t + .50, x1 - .2, y1 - .55, t + .65)
            heat += self.source(self.film[ref], (i / n) ** 2 * ohm)
        mid = lambda ref: self.idx(*body[ref]["box"][:2], t + .1, *body[ref]["box"][2:], t + .9)
        heat += self.source(mid("Q1"), i * i * r_q1) + self.source(mid("Q4"), i * i * r_q4)
        ctrl = self.source(mid("U1"), 5.0 * 1.2e-3)      # LM393, Teiler, ein Pullup
        self.p_film = (i / n) ** 2 * ohm
        self.b = {
            "heat": heat + ctrl,
            # Linearlader BQ25101 im XIAO: (5 - 3,7 V) x 100 mA, dazu LED und Regler ~5 mW
            "charge": ctrl + self.source(self.idx(W - 8, 6, t + 11, W - 4, 11, t + 12), 1.3 * 0.100 + 0.005),
        }

    # ---------------------------------------------------------------- Auswertung
    def ntc_points(self) -> dict:
        (x0, x1), (y0, y1), (z0, z1) = self.bx, self.by, self.bz
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        at = {
            "unter der Heizung (Spalt)": (cx + 1, 5.3, -self.s.gap / 2),
            "Akku oben, neben der Platine": ((x0 + min(0, x0 + 6)) / 2, cy, z1 - .2),
            "Akku unten, Mitte": (cx, cy, z0 + .2),
            "Akku Schmalseite": (x0 + .4, cy, (z0 + z1) / 2),
        }
        # Perle ~2 mm: Mittel über ihre Fläche, unabhängig vom Gitter
        r = {k: 1.0 for k in at}
        return {k: self.idx(x - r[k], y - r[k], z - 0.3, x + r[k], y + r[k], z + 0.3) for k, (x, y, z) in at.items()}

    def probes(self) -> dict:
        """Name -> Maske der Zellen, deren Maximum, Minimum oder Mittel berichtet wird."""
        mask = lambda *regions: self._mask(regions)
        x0, y0, z0, x1, y1, z1 = self.cav
        cav = mask(self.idx(*self.cav))
        shell = np.zeros(self.shape, bool)
        for ax in range(3):
            for d in (1, -1):
                shell |= np.roll(cav, d, ax)
        u1 = next(b["box"] for b in self.geo["bodies"] if b["ref"] == "U1")
        u1 = self.idx(u1[0], u1[1], self.pcb_t + .1, u1[2], u1[3], self.pcb_t + 1.5)
        return {"film": mask(*self.film.values()), "board": mask(self.board), "cell": mask(self.battery),
                "eps": shell & ~cav, "u1": mask(u1)}

    def _mask(self, regions):
        m = np.zeros(self.shape, bool)
        for r in regions:
            m[r] = True
        return m

    def solve(self, b, shift=0.0, tol=1e-6, x0=None):
        x = np.zeros(self.shape) if x0 is None else x0.copy()
        it = pcg(self.gx, self.gy, self.gz, self.diag + shift * self.cap, b, x, tol, 60000)
        if it < 0:
            raise RuntimeError("Löser nicht konvergiert")
        self.iterations = it
        return x

    def apply(self, x):
        y = np.empty(self.shape)
        matvec(self.gx, self.gy, self.gz, self.diag, x, y)
        return y

    def balance(self, x, b):
        return float((self.g_amb * x).sum() / b.sum())


@njit(parallel=False, fastmath=True, cache=True)
def matvec(gx, gy, gz, d, x, y):
    nx, ny, nz = x.shape
    for i in range(nx):
        for j in range(ny):
            for k in range(nz):
                v = d[i, j, k] * x[i, j, k]
                if i > 0:
                    v -= gx[i - 1, j, k] * x[i - 1, j, k]
                if i < nx - 1:
                    v -= gx[i, j, k] * x[i + 1, j, k]
                if j > 0:
                    v -= gy[i, j - 1, k] * x[i, j - 1, k]
                if j < ny - 1:
                    v -= gy[i, j, k] * x[i, j + 1, k]
                if k > 0:
                    v -= gz[i, j, k - 1] * x[i, j, k - 1]
                if k < nz - 1:
                    v -= gz[i, j, k] * x[i, j, k + 1]
                y[i, j, k] = v


@njit(fastmath=True, cache=True)
def ssor(gx, gy, gz, d, r, z, w):
    """Symmetrisches SOR als Vorkonditionierer."""
    nx, ny, nz = r.shape
    for i in range(nx):
        for j in range(ny):
            for k in range(nz):
                v = r[i, j, k]
                if i > 0:
                    v += gx[i - 1, j, k] * z[i - 1, j, k]
                if j > 0:
                    v += gy[i, j - 1, k] * z[i, j - 1, k]
                if k > 0:
                    v += gz[i, j, k - 1] * z[i, j, k - 1]
                z[i, j, k] = v * w / d[i, j, k]
    for i in range(nx - 1, -1, -1):
        for j in range(ny - 1, -1, -1):
            for k in range(nz - 1, -1, -1):
                v = z[i, j, k] * d[i, j, k] * (2 - w) / w
                if i < nx - 1:
                    v += gx[i, j, k] * z[i + 1, j, k]
                if j < ny - 1:
                    v += gy[i, j, k] * z[i, j + 1, k]
                if k < nz - 1:
                    v += gz[i, j, k] * z[i, j, k + 1]
                z[i, j, k] = v * w / d[i, j, k]


@njit(fastmath=True, cache=True)
def dot(a, b):
    s = 0.0
    nx, ny, nz = a.shape
    for i in range(nx):
        for j in range(ny):
            for k in range(nz):
                s += a[i, j, k] * b[i, j, k]
    return s


@njit(fastmath=True, cache=True)
def pcg(gx, gy, gz, d, b, x, tol, maxit, w=1.85):
    r = np.empty(x.shape)
    matvec(gx, gy, gz, d, x, r)
    r = b - r
    z = np.empty(x.shape)
    ap = np.empty(x.shape)
    ssor(gx, gy, gz, d, r, z, w)
    p = z.copy()
    rz = dot(r, z)
    stop = tol * tol * dot(b, b)
    for it in range(maxit):
        if dot(r, r) <= stop:
            return it
        matvec(gx, gy, gz, d, p, ap)
        a = rz / dot(p, ap)
        x += a * p
        r -= a * ap
        ssor(gx, gy, gz, d, r, z, w)
        new = dot(r, z)
        p *= new / rz
        p += z
        rz = new
    return -1


class Reduced:
    """Galerkin-Projektion auf rationale Krylov-Vektoren: exakt im Dauerzustand, wenige mK im Zeitverlauf."""
    SHIFTS = (0.0, 1e-4, 3e-4, 1e-3, 3e-3, 1e-2, 3e-2, 0.1, 0.3, 1.0, 5.0)    # 1/s

    def __init__(self, model: Model, sources=("heat", "charge"), shifts=SHIFTS):
        self.names = list(sources)
        self.steady, basis = {}, []
        for name in self.names:
            x = None
            for s in shifts:
                x = model.solve(model.b[name], s, x0=x)
                if s == 0.0:
                    self.steady[name] = x.copy()
                v = x.copy()
                n0 = np.sqrt((v * v * model.cap).sum())
                for _ in range(2):
                    for q in basis:
                        v -= (q * v * model.cap).sum() * q
                n1 = np.sqrt((v * v * model.cap).sum())
                if n1 > 1e-7 * n0:
                    basis.append(v / n1)
        kv = [model.apply(q) for q in basis]
        A = np.array([[(p * kq).sum() for kq in kv] for p in basis])
        self.A = -(A + A.T) / 2
        self.B = np.array([[(p * model.b[n]).sum() for n in self.names] for p in basis])
        masks = model.probes()
        self.out = {k: np.array([q[m] for q in basis]).T for k, m in masks.items()}
        vc = model.vol[masks["cell"]]
        self.cell_mean = (vc / vc.sum()) @ self.out["cell"]
        self.ntc = {k: np.array([q[r].mean() for q in basis]) for k, r in model.ntc_points().items()}
        self._disc = {}

    def step_matrices(self, dt):
        if dt not in self._disc:
            n, m = self.B.shape
            M = np.zeros((n + m, n + m))
            M[:n, :n], M[:n, n:] = self.A, self.B
            E = expm(M * dt)
            self._disc[dt] = (E[:n, :n], E[:n, n:])
        return self._disc[dt]
