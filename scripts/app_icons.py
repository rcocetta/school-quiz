"""Make the app icons in ``src/quizgen/static/`` from the project logo (``website/assets/logo.svg``).

Site mode is an installable web app (DESIGN.md D32), so it needs PNG icons. Run this after
changing the logo (the PNGs are committed; normal builds do not need it):

    pip install -e '.[browser]' && playwright install chromium
    python scripts/app_icons.py

It draws the logo in Chromium and writes (the green set, ``green-*``, is for the green collection theme, D33:
the same logo in green with a star instead of the tick):

- ``icon-192.png``, ``icon-512.png``: the logo as it is (purpose "any").
- ``icon-maskable-512.png``: a full-bleed square with the mark inside the central safe zone, so Android
  can cut any shape out of it (purpose "maskable").
- ``apple-touch-icon.png`` (180x180): opaque and full-bleed, because iOS paints transparency black.
"""

from __future__ import annotations

import math
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
LOGO = ROOT / "website" / "assets" / "logo.svg"
OUT = ROOT / "src" / "quizgen" / "static"
CSP = "default-src 'none'; style-src 'unsafe-inline'"  # the logo is drawn from inline SVG only
PURPLE = "#5233e0"  # must match THEMES in src/quizgen/build.py
GREEN = "#256b1f"


def star(cx: float, cy: float, outer: float, inner: float) -> str:
    """Points of a five-pointed star."""
    points = []
    for i in range(10):
        radius = outer if i % 2 == 0 else inner
        angle = math.radians(-90 + 36 * i)
        points.append(f"{cx + radius * math.cos(angle):.2f},{cy + radius * math.sin(angle):.2f}")
    return " ".join(points)


def parts(theme: str = "purple") -> tuple[str, str]:
    """(the whole logo, just its mark: everything except the background square) in the given theme."""
    svg = LOGO.read_text(encoding="utf-8")
    found = re.search(r"<svg[^>]*>(.*)</svg>", svg, re.S)
    if not found:
        raise SystemExit(f"{LOGO}: expected one <svg ...>...</svg> element; the icon script needs to be updated")
    inner = found.group(1)
    if theme == "green":
        inner = inner.replace(PURPLE, GREEN)
        inner = re.sub(r'<path d="M21 31l8 8 15-16"[^>]*/>',
                       f'<polygon points="{star(32, 28, 13, 5.5)}" fill="{GREEN}" stroke="{GREEN}" stroke-width="3" '
                       'stroke-linejoin="round"/>', inner, count=1)
        assert "<polygon" in inner, "the tick in logo.svg was not found; update the green variant"
    mark = re.sub(r"<rect[^>]*/>", "", inner, count=1)
    return inner, mark


def svg_page(size: int, body: str) -> str:
    return (f'<meta http-equiv="Content-Security-Policy" content="{CSP}">'
            f'<body style="margin:0;background:transparent"><svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{size}" height="{size}" viewBox="0 0 64 64" style="display:block">{body}</svg></body>')


def full_bleed(mark: str, scale: float, colour: str = PURPLE) -> str:
    """Opaque square with the mark scaled around the centre."""
    shift = 32 * (1 - scale)
    return (f'<rect width="64" height="64" fill="{colour}"/>'
            f'<g transform="translate({shift:.3f} {shift:.3f}) scale({scale})">{mark}</g>')


def main() -> None:
    icons = {}
    for prefix, theme, colour in (("", "purple", PURPLE), ("green-", "green", GREEN)):
        logo, mark = parts(theme)
        icons |= {
            prefix + "icon-192.png": (192, logo),
            prefix + "icon-512.png": (512, logo),
            prefix + "icon-maskable-512.png": (512, full_bleed(mark, 0.75, colour)),
            prefix + "apple-touch-icon.png": (180, full_bleed(mark, 0.8, colour)),
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
