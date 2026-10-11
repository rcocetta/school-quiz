"""Take the README screenshots of the example quizzes.

Run from the repository root:

    pip install -e . playwright
    python -m playwright install chromium
    python scripts/screenshots.py

It builds ``examples/`` into a temporary folder with quizgen, opens the pages in
Chromium, clicks through them like a child would and writes five PNG files to
``docs/screenshots/``: start, question, end, languages and index.

The result is the same on every run: Math.random is replaced by a seeded
generator, the window size is fixed, animations are switched off and the
browser starts with empty storage.
"""

import json
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

from quizgen.site import build_site

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "screenshots"
WIDTH, HEIGHT = 820, 1000
MAX_HEIGHT = 1100  # long pages (the review list) are cut off here

# A tiny seeded random number generator (mulberry32), so the questions and the
# order of the answers are always the same.
SEEDED_RANDOM = """
(() => {
  let a = 12345;
  Math.random = () => {
    a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
})();
"""


# These questions (counting from 1) are answered wrongly on purpose, so the end
# screen shows a realistic mix of right and wrong answers.
WRONG_ON = {3, 6}


def correct_labels():
    """Map each farm question to the label of its right answer: the option text,
    or the picture description for picture-only options."""
    quiz = json.loads((ROOT / "examples" / "farm-animals.json").read_text(encoding="utf-8"))
    labels = {}
    for q in quiz["questions"]:
        right = next(o for o in q["options"] if o.get("correct"))
        labels[q["text"]] = right.get("text") or right["image_alt"]
    return labels


def shot(page, name):
    """Save a screenshot of the top of the page, cut below the content (at most
    MAX_HEIGHT tall)."""
    page.evaluate("window.scrollTo(0, 0)")
    height = page.evaluate("document.querySelector('main').getBoundingClientRect().bottom") + 40
    clip = {"x": 0, "y": 0, "width": WIDTH, "height": min(height, MAX_HEIGHT)}
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=True, clip=clip)
    print("saved", f"docs/screenshots/{name}.png")


def new_page(browser):
    context = browser.new_context(
        viewport={"width": WIDTH, "height": HEIGHT},
        device_scale_factor=1,
        reduced_motion="reduce",
        locale="en-GB",
    )
    context.add_init_script(SEEDED_RANDOM)
    page = context.new_page()
    page.on("pageerror", lambda e: print("PAGE ERROR:", e))
    page.on("console", lambda m: m.type == "error" and print("CONSOLE ERROR:", m.text))
    return page


def open_page(page, url):
    page.goto(url)
    page.evaluate("localStorage.clear()")  # start fresh, then reload
    page.reload()


def take_screenshots(site):
    with sync_playwright() as p:
        browser = p.chromium.launch()

        # Farm animals: start, question, end.
        page = new_page(browser)
        open_page(page, (site / "farm-animals.html").as_uri())
        shot(page, "start")
        page.get_by_role("button", name="Start the quiz").click()

        labels = correct_labels()
        options = page.locator("button.option")
        saved_question = False
        number = 0
        while True:
            options.first.wait_for()
            number += 1
            label = labels[page.get_by_role("heading", level=2).inner_text()]
            has_image = page.locator("main img").count() > 0
            right = options.filter(has_text=label).or_(
                options.filter(has=page.get_by_alt_text(label, exact=True))
            )
            if number in WRONG_ON:
                right = options.filter(has_not=right)
            right.first.click()  # tap an answer ...
            page.get_by_role("button", name="Check my answer").click()  # ... and check it
            if has_image and not saved_question and number not in WRONG_ON:
                page.locator(".js-feedback").wait_for()
                shot(page, "question")
                saved_question = True
            nxt = page.get_by_role("button", name="Next question")
            if nxt.count():
                nxt.click()
            else:
                page.get_by_role("button", name="See my results").click()
                break
        page.get_by_text("Let's look at your answers").wait_for()
        shot(page, "end")

        # Times tables: the language switcher, in Italian.
        page = new_page(browser)
        open_page(page, (site / "times-tables.html").as_uri())
        page.get_by_role("button", name="Italiano").click()
        page.get_by_role("button", name="Si parte!").wait_for()
        shot(page, "languages")

        # The index page of the whole site.
        page = new_page(browser)
        page.goto((site / "index.html").as_uri())
        shot(page, "index")

        browser.close()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        site = Path(tmp) / "site"
        result = build_site(ROOT / "examples", site)
        if result.output is None:
            raise SystemExit("The examples did not build: " + str(result.validation.errors))
        take_screenshots(site)


if __name__ == "__main__":
    main()
