"""Checks for the hand-written project website in website/."""

import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

from quizgen.validate import load_quiz

ROOT = Path(__file__).resolve().parent.parent
WEBSITE = ROOT / "website"
PAGES = sorted(WEBSITE.rglob("*.html"))


class _Page(HTMLParser):
    """Collects ids, relative links and the text of <pre data-quiz="..."> blocks."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids, self.links, self.quizzes = set(), [], {}
        self._quiz = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            self.ids.add(a["id"])
        for key in ("href", "src"):
            if a.get(key) and not re.match(r"[a-z]+:", a[key]):
                self.links.append(a[key])
        if tag == "pre" and "data-quiz" in a:
            self._quiz = a["data-quiz"]
            self.quizzes[self._quiz] = ""

    def handle_endtag(self, tag):
        if tag == "pre":
            self._quiz = None

    def handle_data(self, data):
        if self._quiz:
            self.quizzes[self._quiz] += data


def _parse(path):
    page = _Page()
    page.feed(path.read_text(encoding="utf-8"))
    return page


def test_guide_json_examples_validate(tmp_path):
    quizzes = _parse(WEBSITE / "guide" / "index.html").quizzes
    assert quizzes, "no <pre data-quiz> examples found"
    for name, text in quizzes.items():
        path = tmp_path / f"{name}.json"
        path.write_text(text, encoding="utf-8")
        result = load_quiz(path)
        assert not result.errors and not result.warnings, (name, result.errors, result.warnings)


def _exists_after_build(page_path, target):
    """docs/ is website/ plus the built quizzes at /quizzes/ (see scripts/build_docs.py)."""
    rel = (page_path.parent / target).resolve().relative_to(WEBSITE)
    if (WEBSITE / rel).is_file() or (WEBSITE / rel / "index.html").is_file():
        return True
    return bool(rel.parts) and rel.parts[0] == "quizzes"


@pytest.mark.parametrize("path", PAGES, ids=lambda p: str(p.relative_to(WEBSITE)))
def test_links_and_anchors_resolve(path):
    page = _parse(path)
    for link in page.links:
        target, _, fragment = link.partition("#")
        if target:
            assert _exists_after_build(path, target), f"{path.name}: broken link {link}"
        else:
            assert fragment in page.ids, f"{path.name}: missing anchor #{fragment}"
