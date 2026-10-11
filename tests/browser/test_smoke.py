"""Browser smoke test: build quizzes, open them in real Chromium, click through, fail on any error.

pytest alone can't see JavaScript crashes (Phase 3 shipped a single-file-only one), so this runs
the built pages for real. Skipped when Playwright is missing, unless QUIZGEN_BROWSER_TESTS=1
(set in CI) in which case a missing Playwright is a failure.
"""
import functools
import http.server
import json
import os
import struct
import threading
import zlib
from pathlib import Path

import pytest

if os.environ.get("QUIZGEN_BROWSER_TESTS") == "1":
    import playwright.sync_api as pw   # a broken install must fail loudly here
else:
    pw = pytest.importorskip("playwright.sync_api")

from quizgen.build import build_single
from quizgen.site import build_site

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
LOCAL_HOSTS = ("127.0.0.1", "localhost")


# ---------------------------------------------------------------- fixtures

def tiny_png() -> bytes:
    """A valid 1x1 red PNG."""
    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))
    raw = zlib.compress(b"\x00\xff\x00\x00")
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", raw) + chunk(b"IEND", b""))


def opt(text=None, correct=False, **extra):
    o = dict(extra)
    if text is not None:
        o["text"] = text
    if correct:
        o["correct"] = True
    return o


def write_quiz(folder: Path, name: str, data: dict) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{name}.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def image_quiz(feedback: str) -> dict:
    return {
        "title": "Colours", "feedback": feedback, "questions_per_quiz": 3,
        "questions": [
            {"text": "Which is red?", "image": "red.png", "image_alt": "A red square",
             "options": [opt("Red", True), opt("Blue")]},
            {"text": "Pick the picture", "options": [opt(None, True, image="red.png", image_alt="Red"),
                                                      opt(None, image="red.png", image_alt="Also red")]},
            {"text": "Two plus two?", "explanation": "Four.", "options": [opt("4", True), opt("5"), opt("6")]},
        ],
    }


ITALIAN = {"First?": "Prima?", "Second?": "Seconda?", "Third?": "Terza?"}


def multilang_quiz() -> dict:
    def q(en, it):
        return {"text": {"en": en, "it": it},
                "options": [opt({"en": "Yes", "it": "Sì"}, True), opt({"en": "No", "it": "No"})]}
    return {"title": {"en": "Bilingual", "it": "Bilingue"}, "languages": ["en", "it"],
            "questions": [q(en, it) for en, it in ITALIAN.items()]}


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    """Build once: single-file pages and a site, from small fixture quizzes."""
    root = tmp_path_factory.mktemp("browser")
    src = root / "src"
    for feedback in ("immediate", "end"):
        write_quiz(src, f"colours-{feedback}", image_quiz(feedback))
    write_quiz(src, "bilingual", multilang_quiz())
    write_quiz(src / "shapes", "extra", image_quiz("immediate"))
    for folder in (src, src / "shapes"):
        (folder / "red.png").write_bytes(tiny_png())

    single = root / "single"
    single.mkdir()
    for name in ("colours-immediate", "colours-end", "bilingual"):
        assert build_single(src / f"{name}.json", single / f"{name}.html").output
    site = root / "site"
    assert build_site(src, site).output
    examples = root / "examples-site"
    if EXAMPLES.is_dir() and any(EXAMPLES.glob("*.json")):
        assert build_site(EXAMPLES, examples).output
    return {"single": single, "site": site, "examples": examples}


@pytest.fixture(scope="module")
def serve():
    """Serve a folder on 127.0.0.1 (random port). Returns serve(folder) -> base URL."""
    servers = []

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    def start(folder: Path) -> str:
        handler = functools.partial(Quiet, directory=str(folder))
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        return f"http://127.0.0.1:{server.server_address[1]}"

    yield start
    for server in servers:
        server.shutdown()
        server.server_close()


@pytest.fixture(scope="module")
def browser():
    with pw.sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


class Watched:
    """A page that records every problem; `check()` fails the test if there was any."""

    def __init__(self, browser):
        self.problems: list[str] = []
        self.context = browser.new_context()
        self.context.route("**/*", self._only_local)
        self.page = self.context.new_page()
        self.page.on("pageerror", lambda e: self.problems.append(f"page error: {e}"))
        self.page.on("console", self._console)
        self.page.on("requestfailed", lambda r: self.problems.append(f"request failed: {r.url} {r.failure}"))
        self.page.on("response", lambda r: r.status >= 400 and self.problems.append(f"HTTP {r.status}: {r.url}"))

    def _only_local(self, route):
        url = route.request.url
        host = url.split("/")[2].split(":")[0] if url.startswith("http") else ""
        if url.startswith(("file://", "data:", "blob:", "about:")) or host in LOCAL_HOSTS:
            route.continue_()
        else:
            self.problems.append(f"external request blocked: {url}")
            route.abort()

    def _console(self, msg):
        if msg.type == "error":
            self.problems.append(f"console error: {msg.text}")

    def check(self):
        assert not self.problems, "\n".join(self.problems)

    def close(self):
        self.context.close()


@pytest.fixture
def watched(browser):
    w = Watched(browser)
    yield w
    w.close()


# ---------------------------------------------------------------- helpers

def start(page):
    page.locator(".hero button.btn").click()
    pw.expect(page.locator("main h2.js-heading")).to_be_visible()


def answer_all(page, feedback: str) -> int:
    """Answer every question (first option) through the real buttons. Returns how many."""
    count = 0
    while page.locator("main h2.js-heading").count():
        count += 1
        page.locator(".option").first.click()
        if feedback == "immediate":
            page.locator(".js-check").click()
            pw.expect(page.locator(".feedback")).to_be_visible()
        page.locator(".js-next").click()
    return count


def finish_and_retry(page, feedback: str, expected_questions: int | None = None):
    start(page)
    n = answer_all(page, feedback)
    if expected_questions is not None:
        assert n == expected_questions
    pw.expect(page.locator(".score-value")).to_be_visible()
    assert page.locator(".review-item").count() == n
    page.locator(".result .btn").click()          # Try again
    pw.expect(page.locator("main h2.js-heading")).to_be_visible()


def all_images_loaded(page):
    """Every <img> currently on the page has finished loading and is a real picture."""
    try:
        page.wait_for_function("[...document.images].every(i => i.complete && i.naturalWidth > 0)", timeout=5000)
    except pw.TimeoutError:
        broken = page.evaluate("[...document.images].filter(i => !i.complete || !i.naturalWidth).map(i => i.src)")
        raise AssertionError(f"images did not load: {broken}") from None


# ---------------------------------------------------------------- single-file mode

@pytest.mark.parametrize("feedback", ["immediate", "end"])
def test_single_file_run_through(watched, built, feedback):
    page = watched.page
    page.goto((built["single"] / f"colours-{feedback}.html").as_uri())
    assert page.locator(".back-link").count() == 0          # no index in single-file mode
    finish_and_retry(page, feedback, expected_questions=3)
    watched.check()


def test_single_file_images_load(watched, built):
    page = watched.page
    page.goto((built["single"] / "colours-immediate.html").as_uri())
    start(page)
    seen_images = 0
    while page.locator("main h2.js-heading").count():
        seen_images += page.locator("img").count()
        all_images_loaded(page)
        page.locator(".option").first.click()
        page.locator(".js-check").click()
        page.locator(".js-next").click()
    assert seen_images >= 3          # question image + two picture options appear in the run
    watched.check()


def test_single_file_language_switch_keeps_progress(watched, built):
    page = watched.page
    page.goto((built["single"] / "bilingual.html").as_uri())
    start(page)
    page.locator(".option").first.click()
    page.locator(".js-check").click()
    page.locator(".js-next").click()
    english = page.locator("h2.js-heading").inner_text()                   # questions come in random order
    page.locator('.lang-btn[data-lang="it"]').click()
    pw.expect(page.locator("h2.js-heading")).to_have_text(ITALIAN[english])    # same question, new language
    assert page.locator(".progress-text").inner_text() == "Domanda 2 di 3"
    assert page.evaluate("document.documentElement.lang") == "it"
    page.locator('.lang-btn[data-lang="en"]').click()
    pw.expect(page.locator("h2.js-heading")).to_have_text(english)
    watched.check()


# ---------------------------------------------------------------- site mode

def test_site_index_links_to_quizzes(watched, built, serve):
    base = serve(built["site"])
    page = watched.page
    page.goto(base + "/index.html")
    hrefs = page.locator("a.card-link").evaluate_all("els => els.map(e => e.getAttribute('href'))")
    assert "colours-immediate.html" in hrefs and "bilingual.html" in hrefs
    assert any(h.startswith("shapes/") for h in hrefs)      # the collection
    page.locator("a.card-link", has_text="Colours").first.click()
    pw.expect(page.locator(".hero")).to_be_visible()
    page.go_back()
    page.locator("a.card-link", has_text="shapes").first.click()   # collection index (titled after folder)
    pw.expect(page.locator("a.card-link").first).to_be_visible()
    watched.check()


@pytest.mark.parametrize("feedback", ["immediate", "end"])
def test_site_run_through(watched, built, serve, feedback):
    page = watched.page
    page.goto(f"{serve(built['site'])}/colours-{feedback}.html")
    finish_and_retry(page, feedback, expected_questions=3)
    all_images_loaded(page)
    watched.check()


def test_site_quiz_in_collection(watched, built, serve):
    page = watched.page
    page.goto(f"{serve(built['site'])}/shapes/extra.html")
    finish_and_retry(page, "immediate", expected_questions=3)
    watched.check()


def test_site_back_link(watched, built, serve):
    base = serve(built["site"])
    page = watched.page
    page.goto(f"{base}/colours-end.html")
    page.locator(".back-link").click()
    pw.expect(page).to_have_url(base + "/index.html")
    # also from mid-quiz and from the end screen
    page.goto(f"{base}/colours-end.html")
    start(page)
    assert page.locator(".back-link").count() == 1
    answer_all(page, "end")
    page.locator(".back-link").click()
    pw.expect(page).to_have_url(base + "/index.html")
    watched.check()


def test_site_language_switch(watched, built, serve):
    page = watched.page
    page.goto(f"{serve(built['site'])}/bilingual.html")
    start(page)
    page.locator('.lang-btn[data-lang="it"]').click()
    italian = page.locator("h2.js-heading").inner_text()
    english = next(en for en, it in ITALIAN.items() if it == italian)
    page.locator(".option").first.click()
    page.locator(".js-check").click()
    page.locator('.lang-btn[data-lang="en"]').click()
    pw.expect(page.locator(".feedback")).to_be_visible()           # answered state survives the switch
    pw.expect(page.locator("h2.js-heading")).to_have_text(english)
    watched.check()


# ---------------------------------------------------------------- shipped examples

def example_pages(site: Path) -> list[str]:
    if not site.is_dir():
        return []
    return sorted(str(p.relative_to(site)) for p in site.rglob("*.html") if p.name != "index.html")


def test_shipped_examples(watched, built, serve):
    pages = example_pages(built["examples"])
    if not pages:
        pytest.skip("no examples/ quizzes to test")
    base = serve(built["examples"])
    page = watched.page
    page.goto(base + "/index.html")
    pw.expect(page.locator("a.card-link").first).to_be_visible()
    for rel in pages:
        page.goto(f"{base}/{rel}")
        feedback = json.loads(page.locator("#quiz-data").inner_text())["feedback"]
        finish_and_retry(page, feedback)
        all_images_loaded(page)
        # every language the quiz offers
        for code in page.locator(".lang-btn").evaluate_all("els => els.map(e => e.dataset.lang)"):
            page.locator(f'.lang-btn[data-lang="{code}"]').click()
            pw.expect(page.locator("h2.js-heading")).to_be_visible()
            all_images_loaded(page)
    watched.check()
