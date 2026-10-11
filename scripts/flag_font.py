"""Make ``src/quizgen/static/flags.woff2``: the flags from ``ui_strings.json``, cut out of Noto Color Emoji.

Windows has no flag emoji (it shows "GB" instead of the British flag), so quiz pages bring
this small font for the flags only. Run it after adding a language to ``ui_strings.json``:

    pip install fonttools brotli uharfbuzz
    python scripts/flag_font.py path/to/Noto-COLRv1.ttf

Get ``Noto-COLRv1.ttf`` from https://github.com/googlefonts/noto-emoji (``2D/fonts/``).
The font is under the SIL Open Font License 1.1 (no Reserved Font Name); the copyright and
licence notice are kept inside the output file.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import uharfbuzz as hb
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
STRINGS = ROOT / "src" / "quizgen" / "ui_strings.json"
OUT = ROOT / "src" / "quizgen" / "static" / "flags.woff2"


def main(source: str) -> None:
    flags = [lang["flag"] for lang in json.loads(STRINGS.read_text(encoding="utf-8")).values()]
    font = hb.Font(hb.Face(Path(source).read_bytes()))
    names = TTFont(source).getGlyphOrder()
    glyphs = set()
    for flag in flags:
        buf = hb.Buffer()
        buf.add_str(flag)
        buf.guess_segment_properties()
        hb.shape(font, buf)
        if len(buf.glyph_infos) != 1:
            sys.exit(f"{flag!r} is not a single flag in this font")
        glyphs.add(names[buf.glyph_infos[0].codepoint])
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write("\n".join(sorted(glyphs)))
    # Only the flag glyphs and their letters: layout closure would pull in every flag those letters spell.
    subprocess.run([sys.executable, "-m", "fontTools.subset", source, f"--glyphs-file={f.name}",
                    "--text=" + "".join(flags), "--no-layout-closure", "--layout-features=*",
                    "--name-IDs=*", "--flavor=woff2", f"--output-file={OUT}"], check=True)
    Path(f.name).unlink()
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB, {len(flags)} flags)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
