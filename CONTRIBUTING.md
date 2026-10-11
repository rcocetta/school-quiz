# Contributing to school-quiz

Thank you for helping! school-quiz is built for kids, free forever, and open to everyone. You can contribute in three ways:

- **Code**: improve the tool (`quizgen`), the quiz page, the docs or the tests.
- **Quizzes**: add a quiz to the shared library in `quizzes/`.
- **Collections**: add a whole set of quizzes, for example one teacher's or one school's, as a folder `quizzes/<collection>/` with its own index page.

Everyone taking part follows our [Code of Conduct](CODE_OF_CONDUCT.md). To report a security problem, see [SECURITY.md](SECURITY.md).

You do not need to be a programmer to contribute a quiz. If you are not comfortable with Git, open an issue and attach your quiz file; we can help turn it into a pull request.

## Development setup

You need Python 3.10 or newer.

```bash
git clone https://github.com/rcocetta/school-quiz
cd school-quiz
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
```

(If you fork first, clone your fork.) The `quizgen` command is then at `.venv/bin/quizgen`; `.venv/bin/python -m quizgen` works too.

## Running the tests

```bash
.venv/bin/pytest -q
```

Run this before every pull request. Add tests for new behaviour: `tests/fixtures/` holds a small valid or invalid quiz per validation rule, and `tests/` has one test module per area.

**Browser tests** click through the built examples in Chromium, in single-file and site mode, and fail on any page error. They need Playwright:

```bash
.venv/bin/pip install -e '.[dev,browser]'
.venv/bin/python -m playwright install chromium
.venv/bin/pytest tests/browser
```

Without Playwright these tests are skipped. With `QUIZGEN_BROWSER_TESTS=1` set, a missing Playwright is an error instead (CI does this). Please run them when you change `quiz.js`, `quiz.css`, the templates or the build code.

**Screenshots** in `docs/screenshots/` are generated, not hand-made. Regenerate them with `.venv/bin/python scripts/screenshots.py` if you change how the pages look.

**Checking quizzes:** `.venv/bin/quizgen validate examples/ quizzes/`.

## Continuous integration

`.github/workflows/ci.yml` runs on every pull request: the tests on several Python versions (3.10 and newer), `quizgen validate` on `examples/` and `quizzes/`, and the browser tests. It uses no secrets and costs nothing, so it is safe for pull requests from forks. A pull request should be green before it is reviewed.

## Code conventions

Read the **Working principles** in [PLAN.md](PLAN.md) and [CLAUDE.md](CLAUDE.md). In short:

- **Kids first.** Big tap targets, large clear text, few words per screen, a kind tone (never shaming a wrong answer), gender-neutral interface text in gendered languages, keyboard and screen-reader friendly, WCAG 2.2 AA contrast.
- **Easy for creators.** Sensible defaults. Error messages say *where* the problem is and *how to fix it*.
- **Simple over clever.** Python 3.10 or newer. Runtime dependencies are only `jsonschema` and `jinja2`; do not add more without discussing it first. Browser code is plain JavaScript and CSS: no frameworks, no build step, **no requests to other sites** from page code (system fonts only; quiz authors may link `https://` pictures).
- **Secure by default.**
  - Quiz text goes into the page with `textContent`, never `innerHTML`. No `eval`.
  - JSON embedded in a page is escaped so `</script>` in content cannot break out.
  - Generated pages keep their strict Content-Security-Policy. No inline event handlers or inline styles.
  - Links from author fields are only `http(s)://` and `mailto:`, with `rel="noopener noreferrer"`.
  - Block path traversal when reading or copying images; only write inside the chosen output folder.
  - No tracking, analytics, cookies or third-party requests. `localStorage` is only for the language preference.
  - GitHub Actions: least-privilege `permissions:`, actions pinned to commit SHAs (with the version in a comment), and no secrets in workflows triggered by pull requests.
- The validator produces a **normalised quiz** (defaults filled, every Text a full `{language: string}` map, `any` expanded). Builders and browser code consume only that form.
- Reuse helpers instead of re-implementing them, for example `validate.IMAGE_TYPES`, `validate.is_remote_image` and `validate.discover`.

## Keep the docs in step with the code

If your change affects the schema, the command line or behaviour, update these in the same pull request:

- the JSON schema files in `src/quizgen/` (`schema.json`, `collection.schema.json`, `site.schema.json`),
- the field reference and other sections of [README.md](README.md),
- [PLAN.md](PLAN.md) (decisions, rules, status) if it changes something the plan describes,
- [CHANGELOG.md](CHANGELOG.md) under **Unreleased**.

Settled decisions in `PLAN.md` (marked with a tick) should not be reopened inside a pull request; open an issue to discuss them first.

## Contributing a quiz or collection

Put the quiz in `quizzes/`. For a collection, make a folder `quizzes/<collection>/` with your quizzes in it, optionally with a `collection.json` for its title, description and author; see the [README](README.md#collections-and-folder-layout)). Images go in an `images/` folder next to the quiz.

The [pull request template](.github/PULL_REQUEST_TEMPLATE.md) repeats this checklist. For each quiz or collection:

- [ ] **Age-appropriate.** Content, wording and pictures suit primary and early-secondary school children.
- [ ] **Answers double-checked.** Each question has exactly one right answer, and you checked the facts in a reliable source. Add an `explanation` where it helps a child learn.
- [ ] **Images are yours or openly licensed.** Name the source and licence in the pull request (and add a credits note next to the images if the licence asks for attribution). Prefer local images over remote links, which let the image host see the child's IP address. Add `image_alt` descriptions that describe the picture without giving away the answer (see the [README](README.md#describing-images-image_alt)).
- [ ] **No personal data about children**: no names, photos, school names tied to children, or contact details. For `author`, prefer a website address over a personal email.
- [ ] **It validates.** `quizgen validate quizzes/` shows no errors, and ideally no warnings.
- [ ] **Translations are complete** for every language you list, and read naturally to a native speaker.
- [ ] You are happy for the quiz to be shared under the project's licence.

## Pull request process

1. Fork the repository and create a branch from `main` with a short descriptive name.
2. Make your change, keep it focused, and add or update tests and docs.
3. Run `.venv/bin/pytest -q` (and the browser tests if you touched the page).
4. Open a pull request. The template asks whether it is code, a quiz or a collection, what it changes and why, and has a checklist to tick.
5. CI runs automatically. The maintainer reviews, may ask for changes, and merges when it is ready.

Pull requests from forks never get access to repository secrets.

### Maintainer-triggered Claude review

The maintainer can ask for an automated review by [Claude](https://www.anthropic.com/claude) on a pull request. How it works ([`.github/workflows/claude-review.yml`](.github/workflows/claude-review.yml)):

- **Only the repository owner can start it**, by commenting `/claude-review` on the pull request (or by running the workflow manually from the **Actions** tab). Comments from anyone else are ignored.
- **It never runs automatically**, not when a pull request is opened or updated. Contributors do not need to do anything.
- **Its output is advice** that a human reads. It does not replace human review and cannot merge or push.
- It reads the content of the pull request, which anyone can write, so it could be tricked by text planted in a pull request (prompt injection). That is why it only has permission to read the repository and to comment, and no other secrets.

## Reporting problems

Open an issue on GitHub. For a bug, include the quiz file (or a cut-down version), the command you ran, the message you saw and your Python version. For anything security-related, do not open a public issue. Report it privately with the **Report a vulnerability** button on the repository's **Security** tab (GitHub private vulnerability reporting).

## Licence

By contributing you agree that your contribution is licensed under the project's licence, GPL-3.0-or-later (see [LICENSE](LICENSE)).
