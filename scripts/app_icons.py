"""Make the app icons in ``src/quizgen/static/`` from the project logo (``website/assets/logo.svg``).

Site mode is an installable web app (DESIGN.md D32), so it needs PNG icons. Run this after
changing the logo (the PNGs are committed; normal builds do not need it):

    pip install -e '.[browser]' && playwright install chromium
    python scripts/app_icons.py

It draws the logo in Chromium and writes:

- ``icon-192.png``, ``icon-512.png``: the logo as it is (purpose "any").
- ``icon-maskable-512.png``: a full-bleed square with the mark inside the central safe zone, so Android
  can cut any shape out of it (purpose "maskable").
- ``apple-touch-icon.png`` (180x180): opaque and full-bleed, because iOS paints transparency black.
"""

from __future__ import annotations

import re
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
LOGO = ROOT / "website" / "assets" / "logo.svg"
OUT = ROOT / "src" / "quizgen" / "static"
PURPLE = "#5233e0"


def parts() -> tuple[str, str]:
    """(the whole logo, just its mark: everything except the background square)."""
    svg = LOGO.read_text(encoding="utf-8")
    inner = re.search(r"<svg[^>]*>(.*)</svg>", svg, re.S).group(1)
    mark = re.sub(r"<rect[^>]*/>", "", inner, count=1)
    return inner, mark


def svg_page(size: int, body: str) -> str:
    return (f'<body style="margin:0;background:transparent"><svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{size}" height="{size}" viewBox="0 0 64 64" style="display:block">{body}</svg></body>')


def full_bleed(mark: str, scale: float) -> str:
    """Opaque purple square with the mark scaled around the centre."""
    shift = 32 * (1 - scale)
    return (f'<rect width="64" height="64" fill="{PURPLE}"/>'
            f'<g transform="translate({shift:.3f} {shift:.3f}) scale({scale})">{mark}</g>')


def main() -> None:
    logo, mark = parts()
    icons = {
        "icon-192.png": (192, logo),
        "icon-512.png": (512, logo),
        "icon-maskable-512.png": (512, full_bleed(mark, 0.75)),
        "apple-touch-icon.png": (180, full_bleed(mark, 0.8)),
    }
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for name, (size, body) in icons.items():
            page = browser.new_page(viewport={"width": size, "height": size})
            page.set_content(svg_page(size, body))
            page.screenshot(path=str(OUT / name), omit_background=True,
                            clip={"x": 0, "y": 0, "width": size, "height": size})
            page.close()
            print(f"wrote {OUT / name} ({(OUT / name).stat().st_size} bytes)")
        browser.close()


if __name__ == "__main__":
    main()
