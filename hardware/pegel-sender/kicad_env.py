"""KiCad-Pfade: System-Paket, extrahiertes AppImage (build/kicad-appimage) oder KICAD_CLI / KICAD_APPIMAGE."""

import glob
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, "build", "kicad-appimage")


def _appimage_candidates() -> list[str]:
    env = os.environ.get("KICAD_APPIMAGE")
    if env and os.path.isfile(env):
        return [env]
    return sorted(glob.glob(os.path.join(BUILD, "*.AppImage")))


def appimage_path() -> str | None:
    c = _appimage_candidates()
    return c[0] if c else None


def _squashfs_root() -> str | None:
    img = appimage_path()
    if not img:
        return None
    root = os.path.join(os.path.dirname(img), "squashfs-root")
    if os.path.isdir(root):
        return root
    subprocess.run([img, "--appimage-extract"], cwd=os.path.dirname(img), check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return root if os.path.isdir(root) else None


def kicad_cli_argv(*args: str) -> list[str]:
    cli = os.environ.get("KICAD_CLI")
    if cli:
        return [cli, *args]
    found = shutil.which("kicad-cli")
    if found:
        return [found, *args]
    img = appimage_path()
    if img:
        return [img, "kicad-cli", *args]
    raise SystemExit(
        "kicad-cli not found: install kicad, set KICAD_CLI, or put AppImage in build/kicad-appimage/"
    )


def run_kicad_cli(*args: str) -> None:
    subprocess.run(kicad_cli_argv(*args), check=True)


def footprint_root() -> str:
    env = os.environ.get("KICAD_FOOTPRINT_DIR")
    if env:
        return env
    sq = _squashfs_root()
    if sq:
        fp = os.path.join(sq, "usr", "share", "kicad", "footprints")
        if os.path.isdir(fp):
            return fp
    if os.path.isdir("/usr/share/kicad/footprints"):
        return "/usr/share/kicad/footprints"
    return os.path.join(os.path.dirname(os.path.dirname(sys.executable)), "share", "kicad", "footprints")


def pcbnew_python() -> str:
    try:
        import pcbnew  # noqa: F401

        return sys.executable
    except ImportError:
        pass
    sq = _squashfs_root()
    if sq:
        bindir = os.path.join(sq, "usr", "bin")
        for name in ("python3.11", "python3", "python"):
            p = os.path.join(bindir, name)
            if os.path.isfile(p):
                return p
    img = appimage_path()
    raise SystemExit(
        "pcbnew not importable: install KiCad, extract AppImage to build/kicad-appimage/, "
        f"or run {img} python gen_pcb.py" if img else "pcbnew not importable: install KiCad"
    )


def run_pcbnew_script(script: str, script_args: list[str] | None = None) -> None:
    subprocess.run([pcbnew_python(), script, *(script_args or [])], check=True)
