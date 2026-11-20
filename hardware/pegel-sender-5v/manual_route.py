"""Leiterbahnen ohne Freerouting — nur MANUAL_TRACKS / MANUAL_LINKS (in KiCad ergänzen)."""

from __future__ import annotations

import os
import subprocess
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(HERE, "pegel-sender-5v.kicad_pcb")

sys.path.insert(0, HERE)
import gen_pcb  # noqa: E402
import kicad_env  # noqa: E402
import route  # noqa: E402

MANUAL_TRACKS: list[tuple[str, float, int, list[tuple[float, float]]]] = [
    ("V5", 0.5, pcbnew.F_Cu, [(13.5, 34.5), (48.0, 25.24)]),
    ("VBAT", 0.6, pcbnew.F_Cu, [(8.0, 14.0), (15.5, 21.0)]),
    ("RS485_A", 0.3, pcbnew.F_Cu, [(36.0, 7.0), (1.5, 17.5)]),
    ("RS485_B", 0.3, pcbnew.F_Cu, [(36.0, 7.0), (1.5, 20.0)]),
]

MANUAL_LINKS: list[tuple[str, str, str, str, float]] = [
    ("J1", "1", "Q1", "3", 0.6),
    ("Q1", "2", "C1", "1", 0.5),
    ("C1", "1", "C2", "1", 0.5),
]


def apply_manual_tracks(board):
    for net, width, layer, pts in MANUAL_TRACKS:
        if board.FindNet(net) is None:
            continue
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            route.add_track(board, x1, y1, x2, y2, net, layer, width)


def apply_manual_links(board):
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    for ref_a, pad_a, ref_b, pad_b, w in MANUAL_LINKS:
        if ref_a in fps and ref_b in fps:
            route.link_pads(board, ref_a, pad_a, ref_b, pad_b, w)


def main() -> None:
    py = kicad_env.pcbnew_python()
    subprocess.run([py, os.path.join(HERE, "layout.py")], check=True)
    board = pcbnew.LoadBoard(PCB)
    apply_manual_tracks(board)
    apply_manual_links(board)
    route.connect_orphan_gnd_pads(board)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    gen_pcb.layout_silk(board)
    pcbnew.SaveBoard(PCB, board)
    print("manual tracks saved:", PCB)


if __name__ == "__main__":
    main()