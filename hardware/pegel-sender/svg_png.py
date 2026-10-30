"""SVG → PNG: rsvg-convert, sonst PyMuPDF (pip install pymupdf, z. B. unter Windows)."""

import shutil
import subprocess


def svg_to_png(svg: str, png: str, width: int | None = None) -> None:
    if shutil.which("rsvg-convert"):
        size = ["-w", str(width)] if width else []
        subprocess.run(["rsvg-convert", *size, "-o", png, svg], check=True)
        return
    try:
        import pymupdf
    except ImportError:
        raise SystemExit("SVG → PNG: rsvg-convert oder PyMuPDF (pip install pymupdf) installieren")
    page = pymupdf.open(svg)[0]
    zoom = width / page.rect.width if width else 96 / 72   # ohne Breite wie rsvg: 96 dpi
    page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False).save(png)
