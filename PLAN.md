# School Quizzes — Plan

> **Living document.** This is the single source of truth for the project across sessions and subagents.
> Before starting work: read this whole file. After finishing work: update **Status**, tick tasks, and append to the **Session log**.
> Decisions marked ✅ are settled — don't re-open them without asking the user.

## Goal

Repository: https://github.com/rcocetta/school-quiz (public, GPL-3.0). Per its description it will hold both the generator and the user's own quizzes.


A Python CLI (`quizgen`) that turns quiz JSON files into static HTML quizzes for primary / early-secondary school kids. No backend: output must work when served from GitHub Pages (or opened as a local file, in single-file mode).

Each quiz file holds a pool of **N** questions; each attempt shows **M** of them (M ≤ N), picked at random in the browser.

## Status

| Phase | State |
|---|---|
| 0. Planning | ✅ done |
| 1. Schema + validator | ✅ done |
| 2. Quiz page + single-file build | ✅ done |
| 3. Site build + index page | ✅ done |
| 4. Examples, docs, deploy | ⬜ not started |
| 5. Project website + community | ⬜ not started |

Legend: ⬜ not started · 🟨 in progress · ✅ done · ⛔ blocked

---

## Decisions

| # | Decision | Status |
|---|---|---|
| D1 | CLI written in **Python**, deps limited to `jsonschema` + `jinja2`, CLI via `argparse` | ✅ |
| D2 | M questions picked **in the browser, per attempt** (full pool embedded; answers visible in source — acceptable, it's for practice) | ✅ |
| D3 | Feedback mode **configurable per quiz**: `"immediate"` (default) or `"end"` | ✅ |
| D4 | Two output modes: **folder → site** (index + one page per quiz + copied images) and **file → one self-contained HTML** (CSS/JS/local images inlined). Single-file mode must stay dead simple | ✅ |
| D5 | Correct answer marked with `"correct": true` **on the option** (not an index) | ✅ |
| D6 | Image paths relative to the JSON file; `https://` URLs also allowed (never inlined/copied, not checked) | ✅ |
| D7 | i18n is **opt-in**: no `languages` field → plain strings everywhere, creator never thinks about i18n | ✅ |
| D8 | Multi-language uses **per-field translations** (`{"en": "...", "it": "..."}`), one question list, so switching language mid-quiz keeps position/score | ✅ |
| D9 | i18n problems **fail the build** (missing/extra translations, mixed string/map). No fallback language | ✅ |
| D10 | Language switcher shows **flag + code** (🇬🇧 EN · 🇮🇹 IT) | ✅ |
| D11 | v1 extras: shuffle options, per-question explanation, CLI override of M, remote image URLs | ✅ |
| D12 | End screen: **score + encouraging message + review list + "Try again"** (new random set) | ✅ |
| D14 | Project will be **open-sourced**: exhaustive README, licence, contributor docs, clean repo hygiene are v1 deliverables | ✅ |
| D15 | Licence: **GPL-3.0** (already in the GitHub repo) | ✅ |
| D16 | Mission, stated on the website and README: **built for kids, free forever, anyone can fork and run their own, or contribute back via PR** | ✅ |
| D17 | GitHub Pages site layout: `/` landing page, `/guide/` how-to guide, `/quizzes/` quiz index. Forks can turn off the project pages with one setting, which puts their quiz index at `/` | ✅ |
| D18 | Website and guide in **English only** (quizzes themselves stay multi-language) | ✅ |
| D19 | **Main path for non-programmers: fork → edit JSON in GitHub's web editor → GitHub Action builds and deploys.** No local install needed. The CLI path is for developers | ✅ |
| D20 | PRs welcome for **code, quizzes and sites**. Claude review of PRs exists but is **triggered only by the maintainer** (never automatic, to control cost) | ✅ |
| D21 | Contributed "sites" are **collections**: a subfolder `quizzes/<collection>/` with its own index page (e.g. one teacher's or school's set) | ✅ |
| D22 | Optional **`author`** (`name` required, `url`, `email` optional) on quizzes and collections; a quiz inherits its collection's author. Plain strings, never translated. Guide discourages personal emails | ✅ |
| D23 | Generated quiz and index pages carry a small **"Made with school-quiz" footer link** to the repo. On by default, so forks credit the project; removable by anyone (no obligation beyond GPL notices) | ✅ |
| D24 | Creators can **override built-in UI text** with an optional `ui` object on a quiz or in `collection.json` (quiz > collection > built-in). Partial overrides allowed: any key, any subset of languages | ✅ |
| D25 | **Local images limited to png, jpg/jpeg, gif, webp.** No local SVG in v1: copied to the site, an SVG opened directly runs script on the `github.io` origin. Remote image URLs (any type) still allowed, `https://` recommended (CSP); `http://` gives a warning | ✅ |
| D26 | Optional **`image_alt`** (Text) on questions and options describes the image for screen readers; error without `image`. `"image_alt": ""` (any mode) marks a question image or an option image next to text as decorative; not allowed on picture-only options. Missing `image_alt` → validator warning (question image; picture-only option); browser fallback: question image `alt=""`, option image uses the option text, else the UI string `picture_n` ("Picture {n}") | ✅ |
| D28 | **Immediate feedback = tap to select, then "Check"** (UI string `check`): a mis-tap can be changed before checking. Number keys 1–9 only select, and only while focus is in the options (WCAG 2.1.4) | ✅ |
| D29 | Site output **mirrors the input folder**: each page sits where its JSON is, local images copied once to the same relative path (refs URL-encoded in the page). Replaces the planned `images/<slug>/` | ✅ |
| D27 | Optional top-level **`site.json`** (`title`, `description`, `author`, `language`; plain strings). Index text comes from `ui_strings.json` in the site language (default `en`); `collection.json` gains optional `language` (default: the site's). Loose quizzes inherit the site author; collection quizzes inherit only the collection author | ✅ |
| D13 | Text maps may use the special key **`"any"`**: the value for every language unless that locale has its own key (`{"any": "12"}`, `{"any": "Rome", "it": "Roma"}`). Plain strings in multi-language mode stay an error (hint: use `any`) | ✅ |

---

## Working principles

These apply to every phase, every session and every subagent.

### Quality bar
- **Kids first.** Big tap targets, large clear text, few words per screen, no dead ends, gentle encouraging tone (never shaming on wrong answers; UI text gender-neutral in gendered languages, e.g. no "Bravissimo" in Italian), works on cheap tablets and phones, keyboard and screen-reader friendly (WCAG 2.2 AA contrast, real `<button>`s, labels, focus states, `alt` text for images).
- **Easy for creators.** Teachers and parents shouldn't need to code. Defaults for everything optional, error messages that say *where* and *how to fix*, examples they can copy.
- **Simple over clever.** Few dependencies, no frameworks, no build step for the browser code. Every feature in the plan must earn its place; no speculative abstractions.
- **Secure by default** (simple, but kids are the audience):
  - Quiz text always via `textContent`; JSON embedded safely (no `</script>` break-out); no `eval`/`innerHTML` with data.
  - Strict Content-Security-Policy `<meta>` in generated pages (no external scripts; images allowed from `https:` for remote image URLs).
  - Links in author fields: only `http(s)://` and `mailto:`, `rel="noopener noreferrer"`, never `javascript:`.
  - Path traversal blocked when copying/inlining images; output only written inside the chosen output dir.
  - No tracking, analytics, cookies or third-party requests. `localStorage` only for the language preference.
  - GitHub Actions: least-privilege `permissions:`, pinned action versions (commit SHAs), no secrets on PR-triggered workflows; Claude review maintainer-triggered only (§8).

### Using subagents
Pick the cheapest model that can do the job well; the main session (Opus) orchestrates, keeps `PLAN.md` current, and reviews results.

The project ships its own agents in **`.claude/agents/`**, so they work in local, cloud (Claude Code on the web) and contributor sessions alike. Don't rely on agents or plugins that only exist on one machine.

| Work | Agent (model) |
|---|---|
| Mechanical: fixtures, translations, boilerplate, renames | built-in `general-purpose` with `model: haiku` |
| Implementing a well-specified task from this plan (validator, builders, CLI, workflows, docs) | `quiz-implementer` (sonnet) |
| Browser UI and visual design (quiz page, index, landing, guide) | `quiz-designer` (sonnet); design reviewed by main session |
| Security review at the end of each phase | `security-reviewer` (opus, read-only) |
| Correctness + simplicity review at the end of each phase | `simplicity-reviewer` (sonnet, read-only) |
| Accessibility review (WCAG 2.2 AA + child-specific needs) at the end of every phase touching UI | `accessibility-reviewer` (sonnet, read-only) |
| End-to-end check: build, serve, click through, follow README/guide from scratch | `e2e-tester` (sonnet) |
| Ambiguous design decisions, architecture changes, coordinating the phase | main session (opus); ask the user |

**Phase workflow:** implement (`quiz-implementer` / `quiz-designer`, parallel only when files don't overlap) → main session verifies tests → `security-reviewer` + `simplicity-reviewer` (+ `accessibility-reviewer` when UI changed) in parallel → fixes (same implementer agent, which keeps its context) → `e2e-tester` → main session ticks tasks, updates this file, commits, pushes.

Rules for subagents:
- Give each one a self-contained brief: the task's checklist items from §6, the relevant sections of this plan, the module contracts, and the "Done when" criteria. Tell it to read `CLAUDE.md` and `PLAN.md` first.
- One task scope per agent; parallelise only tasks that touch different files.
- Subagents don't edit `PLAN.md` directly (avoids conflicts); they report what they did and anything that deviates from the plan, and the main session updates `PLAN.md`.
- The main session verifies results (runs tests, reads diffs) before ticking anything.

---

## 1. Quiz JSON schema

### Single-language example
```json
{
  "$schema": "../schema.json",
  "title": "Farm Animals",
  "description": "Optional subtitle",
  "language": "en",
  "questions_per_quiz": 10,
  "feedback": "immediate",
  "shuffle_options": true,
  "questions": [
    {
      "text": "Which animal says 'moo'?",
      "image": "images/farm.png",
      "explanation": "Cows moo to talk to their calves.",
      "options": [
        { "text": "Cow", "image": "https://example.org/cow.png", "correct": true },
        { "text": "Dog" },
        { "text": "Cat" }
      ]
    }
  ]
}
```

### Multi-language example
```json
{
  "languages": ["en", "it"],
  "title": { "en": "Farm Animals", "it": "Animali della fattoria" },
  "questions": [
    {
      "text": { "en": "Which animal says 'moo'?", "it": "Quale animale fa 'muu'?" },
      "explanation": { "en": "Cows moo.", "it": "Le mucche muggiscono." },
      "options": [
        { "text": { "en": "Cow", "it": "Mucca" }, "correct": true },
        { "text": { "en": "Dog", "it": "Cane" } },
        { "text": { "any": "Rex", "it": "Rex il cane" } }
      ]
    },
    {
      "text": { "en": "What is 7 + 5?", "it": "Quanto fa 7 + 5?" },
      "options": [
        { "text": { "any": "10" } },
        { "text": { "any": "12" }, "correct": true },
        { "text": { "any": "13" } }
      ]
    }
  ]
}
```

### Fields

**Top level**

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `$schema` | string | no | — | Ignored by the tool; enables editor autocomplete |
| `title` | Text | yes | — | |
| `description` | Text | no | — | Shown on start screen |
| `languages` | string[] (≥1, unique) | no | — | Presence switches on multi-language mode. First entry = initial language |
| `language` | string | no | `"en"` | Single-language mode only (error if combined with `languages`). Sets UI-chrome language |
| `questions_per_quiz` | int ≥ 1 | no | `min(10, N)` | M. Overridable by `--questions`. M > N is only an error when M is set explicitly |
| `feedback` | `"immediate"` \| `"end"` | no | `"immediate"` | |
| `shuffle_options` | bool | no | `true` | |
| `author` | Author | no | collection's author, if any | Shown on the start screen and index cards (D22) |
| `ui` | UiOverrides | no | — | Replace built-in screen text (D24) |
| `questions` | Question[] (≥1) | yes | — | N = length |

**Question**: `text` (Text, required), `image` (ImageRef, optional), `image_alt` (Text, optional, D26; needs `image`), `explanation` (Text, optional), `options` (Option[], ≥2, required).

**Option**: `text` (Text, optional), `image` (ImageRef, optional), `image_alt` (Text, optional, D26; needs `image`), `correct` (bool, optional, default false). At least one of `text`/`image` required.

**Author** (D22): `name` (string, required), `url` (`http(s)://` string, optional), `email` (string, optional). Always plain strings, even in multi-language mode. Unknown keys → error.

**UiOverrides** (D24): object with any subset of the text keys of `ui_strings.json` (everything except `name` and `flag`); `messages` is a nested object with any subset of `great`/`good`/`keep_trying`. Each value is a string in single-language mode, or in multi-language mode a map with **any subset** of the quiz languages plus optional `any` (unlike normal Text, missing languages fall back to the built-in text rather than erroring). Example:
```json
"ui": {
  "correct": { "it": "Esatto!", "en": "Spot on!" },
  "messages": { "great": { "any": "🌟🌟🌟" } }
}
```

**Text** = `string` in single-language mode; `{lang: string}` object in multi-language mode, where the reserved key `"any"` is the value for every language without its own key (D13).
**ImageRef** = relative path (resolved against the JSON file's directory) or `http(s)://` URL.

Unknown keys anywhere → error (catches typos like `corect`).

---

## 2. Validation rules

All problems are collected and reported together, each with a JSON path, e.g.
`farm.json: questions[4].options[2].text: missing translation "it"`. Exit code 1 on any error. Warnings print but don't fail.

Errors:
1. JSON parse failure (report line/col).
2. Structural: required fields, types, enums, unknown keys (via `schema.json` + `jsonschema`).
3. Each question has **exactly one** option with `correct: true`.
4. Each question has ≥ 2 options; each option has `text` or `image`.
5. M > N (after applying `--questions` override).
6. i18n, when `languages` present: every Text is an object whose keys are a subset of `languages` ∪ {`any`}; every language must be covered, either by its own key or by `any`; empty strings count as missing; unknown language keys → error. Plain strings → error with hint `use {"any": "..."}` (D13). `"any"` is reserved and can't appear in `languages`.
7. i18n, when `languages` absent: every Text is a plain string; an object → error with hint "add a `languages` field".
8. `language` and `languages` both present.
9. Every language code must exist in `ui_strings.json`.
10. Local image path doesn't exist, escapes the quiz directory (`..`, absolute, symlinks), isn't an allowed image type (D25), is over 5 MB, has content that doesn't match its extension, or contains control characters, `\` or a non-normalised path (`./`, `a/../`). `image_alt` without `image`, or `""` on a picture-only option (D26).
13. Folder problems (from `discover`, so `validate` and `build` agree): symlinked JSON files, names that aren't valid UTF-8, a quiz named `index.json`, a collection folder named `assets` or ending in `.html` (any case), `site.json` outside the top level, `collection.json` at the top level.
11. `author`: missing `name`, `url` not `http(s)://`, `email` not a basic `x@y.z` shape (same checks for `collection.json`).
12. `ui`: unknown key; language key not in `languages`; a string where a map is required (or vice versa); empty string; a placeholder not used by that key's built-in text (e.g. `{name}` in `correct`). A required placeholder that's missing (e.g. `question_x_of_y` without `{total}`) is a **warning**.

Warnings:
- M == N (every attempt has the same question set, just reordered).
- Duplicate option texts within a question (compared per language after expansion).
- A Text map has `any` **and** a key for every language (`any` is never used).
- An `http://` image URL: it will not load, because the page CSP only allows `https:` and `data:` images.
- A question image, or a picture-only option, without `image_alt` (D26).
- A collection folder with no quizzes (skipped).

`schema.json` is the structural contract (rules 1–2, plus shape of Text via `oneOf`); rules 3–10 live in Python in `validate.py`.

---

## 3. CLI

```
quizgen build <input> [-o OUTPUT] [--questions M]
quizgen validate <input>...
```

- `<input>` is a **directory** → site mode. Every `*.json` directly inside is a quiz (`schema.json` excluded). Each **immediate subfolder** containing quiz files is a collection (D21) and gets its own index page at `<collection>/index.html`; the top index lists loose quizzes and collections. No deeper nesting in v1. Optional `collection.json` in a subfolder gives it a `title`, `description`, `author` (Author object, D22), `language` and `ui` (validated with its own small schema). Optional top-level `site.json` (D27). Default output `site/`.
  - Output (D29): `index.html`, `<stem>.html` per loose quiz, `<collection>/index.html` and `<collection>/<stem>.html`, `assets/quiz.css`, `assets/quiz.js`, referenced local images at their source-relative paths, empty `.nojekyll`. Index pages have no JS.
  - Safety: everything validated and every write planned and checked (clashes, symlinks, file-vs-folder) before anything is written; output must not be, be inside, or contain the input folder; existing files are never deleted.
- `<input>` is a **file** → single-file mode. Default output `<stem>.html` next to the input.
  - CSS + JS inlined; local images inlined as `data:` URIs (MIME by extension); remote URLs untouched.
- `--questions M` overrides `questions_per_quiz` for every quiz in this build (re-validated).
- `build` always validates first; on error nothing is written.
- Entry point: `quizgen = "quizgen.cli:main"` in `pyproject.toml`; also runnable as `python -m quizgen`.

---

## 4. Quiz page (browser runtime)

- Vanilla HTML/CSS/JS. No framework, no external requests (fonts: system stack).
- Quiz data embedded as `<script type="application/json" id="quiz-data">` (JSON escaped so `</script>` in content can't break out). Built-in UI strings for the quiz's languages embedded alongside.
- All quiz text rendered via `textContent` — never `innerHTML`.
- **Screens**
  1. **Start**: title, description, "Made by <name>" (if author; links to `url`, else `mailto:` email), number of questions, language switcher (if >1 language), "Start" button.
  2. **Question**: progress bar ("3 / 10"), question text + image, options as large buttons (text and/or image).
     - `immediate` (D28): tap selects (changeable), "Check" locks options, marks chosen and correct ones, shows explanation if present (focus moves to the feedback), then "Next".
     - `end`: on click, highlight selection, "Next" enabled; no correctness shown.
  3. **End**: score ("7 / 10"), encouraging message tiered by percentage (from UI strings), review list (question, your answer, correct answer, explanation), "Try again" → new random M, reshuffled.
- **Footer** on every generated page (D23): small "Made with school-quiz" link to https://github.com/rcocetta/school-quiz.
- **Randomness**: Fisher–Yates shuffle of question pool, take first M; shuffle options per question if `shuffle_options`.
- **Language switcher**: flag emoji + uppercase code; switching re-renders the current screen in place, preserving state. Remember choice in `localStorage` (wrapped in try/catch; page must work without it).
- **Design**: mobile/tablet first, big tap targets (≥ 48px), large readable font, high contrast, friendly colours, visible focus states, keyboard usable (Tab/Enter, number keys 1–9 to pick options as a nice-to-have), respects `prefers-reduced-motion`.

### `ui_strings.json`
Map `lang → {key: string}` for chrome text: `start`, `next`, `finish`, `try_again`, `question_x_of_y`, `your_score`, `correct`, `wrong`, `your_answer`, `correct_answer`, `picture_n`, `check`, `questions_count(_one)`, index-page keys `quizzes`, `quizzes_count(_one)`, `collections`, `back_to_all`, `no_quizzes_yet`, `languages`, `messages.{great,good,keep_trying}`, plus `flag` and `name` per language. Ship `en`, `it`, `es`, `fr`, `de`.

---

## 5. Project layout

```
pyproject.toml
README.md                    # exhaustive, see Phase 4
LICENSE
CONTRIBUTING.md
CHANGELOG.md
PLAN.md                      # this file
docs/screenshots/            # images used by the README
website/                     # hand-written project pages (landing + guide), plain HTML/CSS
  index.html                 # landing page → served at /
  guide/index.html           # guide → served at /guide/
  assets/                    # site CSS, logo, screenshots
quizzes/                     # the real quiz library published on Pages (maintainer's + contributed)
  <collection>/              # contributed collections (D21), optional collection.json
.github/
  workflows/pages.yml        # build quizzes + website, deploy to Pages
  workflows/ci.yml           # tests + `quizgen validate quizzes/` on every PR (free, no secrets)
  workflows/claude-review.yml # maintainer-triggered Claude review (§8)
  PULL_REQUEST_TEMPLATE.md
  ISSUE_TEMPLATE/            # bug, feature, "quiz idea"
CODE_OF_CONDUCT.md
src/quizgen/
  __init__.py
  __main__.py                # python -m quizgen
  cli.py                     # argparse; dispatch to validate/build
  validate.py                # load + validate → (quiz, errors, warnings)
  build.py                   # build_single(), build_site()
  schema.json
  ui_strings.json
  templates/
    quiz.html                # Jinja2; inline vs linked assets controlled by a flag
    index.html
  static/
    quiz.js
    quiz.css
examples/
  farm-animals.json          # single-language
  times-tables.json          # multi-language (en/it)
  images/
tests/
  fixtures/                  # valid + one invalid file per error rule
  test_validate.py
  test_build.py
```

### Module contracts (so phases can be worked on independently)
- `validate.load_quiz(path: Path, questions_override: int | None = None) -> ValidationResult`
  - `ValidationResult(quiz: dict | None, errors: list[Issue], warnings: list[Issue])`; `Issue(file, path, message)`.
  - On success `quiz` is **normalised**: defaults filled in, `ui` overrides kept as a per-language partial map with `any` expanded (merged with built-ins and the collection's `ui` at build time), and Text always in full map form, one key per language, `any` expanded (single-language quizzes become `{"<language>": "..."}` with `languages: [<language>]`). The builder and JS only ever deal with the normalised form.
- `build.build_single(quiz_path, out_path, questions_override=None)`
- `build.build_site(quiz_dir, out_dir, questions_override=None)`
- JS reads the normalised quiz JSON + UI strings; it never needs to know whether the source was single- or multi-language.

---

## 6. Tasks

### Phase 1 — Schema + validator
- [x] `pyproject.toml` (Python ≥ 3.10, deps `jsonschema`, `jinja2`; dev dep `pytest`), package skeleton (git already set up, `.gitignore` from GitHub's Python template)
- [x] `schema.json` (draft 2020-12) covering structure incl. Text `oneOf`
- [x] `ui_strings.json` with en/it/es/fr/de
- [x] `validate.py` implementing rules 1–12 + warnings + normalisation
- [x] `cli.py validate` subcommand, readable error output
- [x] `ui` overrides: schema, rule 12, normalisation (D24)
- [x] Tests: one fixture per rule, normalisation tests (incl. `any` expansion and override)
- **Done when**: `pytest` passes; `quizgen validate examples/` reports clean; each bad fixture yields its specific error message.
- **Implementation notes** (decisions made while building, accepted):
  - Default M = `min(10, N)`; M > N and the M == N warning only apply when M is explicit (file or `--questions`).
  - Structural (schema) errors suppress the semantic pass, so the semantic checks never see malformed data; users fix structure first, then see rule 3–12 errors.
  - Normalised quiz: `language`/`$schema` dropped, `languages` always set, `questions_per_quiz`/`feedback`/`shuffle_options` always filled, `ui` always present (`{}` if none), `correct` always bool, `author` only if given, absent optional fields omitted, image refs unchanged (builders rewrite them).
  - `collection.json`: `title`/`description` plain strings; `ui` kept with `any` **unexpanded** (a collection doesn't know its quizzes' languages); Phase 3 expands `any` when merging per quiz.
  - Public helpers: `load_quiz(path, questions_override=None, ui_langs=None)`, `load_collection(path)`, `discover(dir)` (reuse in Phase 3).
  - `validate` on an empty folder exits 0 (fresh forks with empty `quizzes/` must not fail CI).
  - `pyproject.toml` has no `readme` field yet; add it in Phase 4 with the README.
  - Post-review hardening: files > 5 MB rejected; deep nesting/huge numbers/lone surrogates/duplicate keys reported, never a traceback; CLI output never crashes on non-UTF-8 consoles; author `url`/`email` strictly checked and stored stripped.
  - **For builders (Phase 2/3), reuse, don't re-implement:** `validate.IMAGE_TYPES` (extension → MIME, D25) and `validate.is_remote_image(ref)`. `discover(dir)` returns `(files, problems)` (since Phase 3 also `site.json` and folder-rule problems, rule 13). `ValidationResult` also has `structural_failure`.
  - `duplicate field` errors carry the key name but no JSON path (hook limitation).

### Phase 2 — Quiz page + single-file build
- [x] `static/quiz.css`, `static/quiz.js` (screens, randomness, feedback modes, switcher, review)
- [x] `templates/quiz.html` with inline-asset mode
- [x] `build_single()` incl. image → data URI, safe JSON embedding
- [x] `cli.py build <file>`
- [x] Tests: output exists, contains embedded data, no local paths remain, `</script>` in content is escaped
- **Done when**: building `examples/farm-animals.json` gives one HTML that works opened via `file://` with no network, in both feedback modes; switching language mid-quiz keeps state.
- **Implementation notes** (accepted):
  - API: `build_single(quiz_path, out_path=None, questions_override=None) -> BuildResult(validation, output)`; `output` is None when nothing was written and build-time problems are appended to `validation.errors`. Reusable for Phase 3: `merge_ui(languages, quiz_ui, collection_ui=None)` (built-in < collection < quiz), `render_page(quiz, ui, *, inline_assets, asset_base="")` (linked mode raises `NotImplementedError` until Phase 3, which also adds the `'self'` CSP), `_rewrite_images(quiz, fn)`, `embed_json`, `_write_atomic`, `validate.ui_strings()`.
  - Embedded data: `quiz-data` = normalised quiz minus `ui`, local images as `data:` URIs; `ui-strings` = full merged strings per quiz language. JSON escapes `< > &` and U+2028/2029.
  - CSP (inline mode): `default-src 'none'; script-src 'sha256-…'; style-src 'sha256-…'; img-src data: https:; base-uri 'none'; form-action 'none'`, plus `referrer no-referrer`. No inline styles/handlers anywhere; assets normalised to LF before hashing; `.gitattributes` forces LF.
  - Output: refuses to overwrite the input; `-o <folder>` (existing or ending in `/`) writes `<folder>/<stem>.html`; random O_EXCL temp file then `os.replace`; write failures are clean errors.
  - Images: ≤ 5 MB each (validator, applies to site mode too), ≤ 20 MB total inlined per single-file page (repeats counted, each file encoded once), file content must match its extension (magic bytes).
  - Page: score tiers great ≥ 80 %, good ≥ 50 %, else keep_trying; wrong answers amber with ✗ (not red), correct green with ✓; author/footer links open in a new tab (`noopener noreferrer`); language stored in `localStorage["quizgen-lang"]`; one `h1` per screen; `<noscript>` message is English only.
  - Folder input to `build` exited 2 until Phase 3 (now site mode).
  - Known gap: remote `https://` images are requested by the child's browser, so the image host sees their IP. Allowed (D6); Phase 4 README and the Phase 5 contribution checklist must say so and recommend local images.
  - Tested in Chromium only (Playwright, `file://`, network blocked); no Firefox/WebKit, real devices or screen readers yet.

### Phase 3 — Site build + index
- [x] `templates/index.html` (quiz cards: title in first language, question count, language flags, author name; collection cards linking to per-collection index pages, D21)
- [x] `build_site()`: per-quiz pages linking shared assets, image copy (D29: same relative path, refs URL-encoded)
- [x] `cli.py build <dir>`
- [x] Collections: one level of subfolders, optional `collection.json`, per-collection index with author in the header, author and `ui` inheritance for quizzes (D21, D22, D24)
- [x] Tests: expected file tree incl. collections, rewritten image paths resolve
- **Done when**: `quizgen build examples/ -o site/` + `python -m http.server -d site` serves a working index and quizzes.
- **Implementation notes** (accepted):
  - Code: `site.py` holds `build_site(quiz_dir, out_dir=None, questions_override=None) -> BuildResult` (`output` = out folder, `count` = quizzes); steps `_check_folders` → `_load_all` → `_plan` → `_preflight` → `_write`. `build.py` keeps shared helpers and `build_single`. `validate.load_site`, `validate.local_image_path`, `validate.is_inside` are public.
  - Index pages: no JS; CSP `default-src 'none'; style-src 'self'; img-src 'self'; base-uri 'none'; form-action 'none'`. Site quiz pages: `script-src 'self'; style-src 'self'; img-src 'self' data: https:`. `'self'` trusts the whole `<user>.github.io` origin; contributors can't place executable files (only the two assets and magic-byte-checked images are written).
  - Index text in the site language (D27); a collection index in its own `language`. A collection without `collection.json` is titled with its folder name. A collection's `ui` applies to its quiz pages only, not to index pages.
  - Order: collections, then loose quizzes, each by title ignoring case and accents. Counts use `_one` strings for 1.
  - Quiz pages in site mode get `index_url`; the back link ("All quizzes") shows on start, question and end screens.
  - Output must not be, be inside, or contain the input; `quizgen build .` with the default `site/` is therefore refused (use `-o` outside the quiz folder).
  - Not tested yet: Firefox/WebKit, real devices and screen readers, actual GitHub Pages hosting, `es`/`de` index text.

### Phase 4 — Examples, docs, deploy
- [ ] Polished example quizzes (one single-language, one en/it) with a few images
- [ ] Exhaustive `README.md` (D14) — audience is both **teachers/parents** (non-programmers) and **developers**. Sections:
  1. Title, one-line pitch, screenshots/GIF of start, question (immediate feedback), end screen, language switcher; link to a live demo on GitHub Pages
  2. Features list
  3. Quick start (install → write minimal quiz → build → open) in ≤ 5 commands
  4. Installation: `pipx install` / `pip install`, from source, supported Python versions
  5. Writing a quiz: minimal example, then full **field reference** (every field, type, required, default — kept in sync with `schema.json`), images (local vs remote, supported formats, size tips), feedback modes, shuffling, choosing M vs N
  6. Multiple languages: opting in, translation maps, `any` key with override examples, supported UI languages, how the switcher behaves
  7. Validation: what is checked, example error output and how to fix common errors
  8. CLI reference: every command/flag with examples, exit codes
  9. Output modes: single-file vs site, what gets generated, when to use which
  10. Publishing on GitHub Pages: step by step (manual and via the Actions workflow), plus other static hosts
  11. Editor support: `$schema` for autocomplete/validation in VS Code
  12. Adding a new UI language (`ui_strings.json`)
  13. FAQ / limitations (answers visible in page source — practice tool, not exams; no tracking; works offline)
  14. Privacy note: no backend, no analytics, no cookies (only `localStorage` for language)
  15. Development: setup, running tests, project layout, architecture overview (validate → normalise → render)
  16. Contributing link, licence, credits
- [ ] `CONTRIBUTING.md`, `CHANGELOG.md` (Keep a Changelog format, v0.1.0)
- [ ] README screenshots in `docs/screenshots/`, generated from the example quizzes
- [ ] `ci.yml`: tests + validate `examples/` and `quizzes/` on every PR (Pages deploy moved to Phase 5)
- [ ] Browser smoke test in CI (Playwright + Chromium): build examples in single-file and site mode, click through a quiz in both feedback modes, fail on any page error. Phase 3 shipped a single-file-only crash that pytest could not see
- [ ] `pyproject.toml` metadata for PyPI: description, readme, licence, classifiers, project URLs
- [ ] Final check: every README code snippet and command actually runs against the current code (have a subagent follow the README from scratch in a clean venv)
- **Done when**: a non-programmer teacher can go from README to a deployed quiz without reading the source, and a developer can set up, test and contribute using only the README + CONTRIBUTING.

---

### Phase 5 — Project website + community
- [ ] `website/index.html` landing page (§8)
- [ ] `website/guide/index.html` guide (§8)
- [ ] `pages.yml`: build `quizzes/` → `_site/quizzes/`, copy `website/` → `_site/`, deploy. Repo variable `PROJECT_PAGES=false` → skip `website/` and build quizzes at `_site/` root (for forks)
- [ ] Fork-friendliness: a fresh fork deploys after only enabling Pages + Actions; documented in the guide with screenshots
- [ ] Community files: `CODE_OF_CONDUCT.md` (Contributor Covenant), PR template with type checkboxes (code / quiz / collection) and the quiz checklist, issue templates
- [ ] `claude-review.yml` (§8) + section in CONTRIBUTING explaining that reviews are maintainer-triggered
- [ ] Link checks: landing ↔ guide ↔ quizzes ↔ GitHub repo all work on the deployed site and in a fork with `PROJECT_PAGES=false`
- **Done when**: the live site at `https://rcocetta.github.io/school-quiz/` shows landing, guide and quizzes; a test fork following only the guide gets its own working quiz site.

---

## 8. Project website, guide and community

### Landing page (`/`)
Audience: teachers, parents, and developers who stumble on the repo. Friendly, warm, kid-themed but not childish. Sections:
1. Hero: name, one-line pitch ("Free, simple quizzes for kids, made by teachers and parents, hosted anywhere"), buttons **Try a quiz** (→ `/quizzes/`) and **Make your own** (→ `/guide/`)
2. What it is: short explanation + screenshots of a quiz in action (question, feedback, end screen, language switcher)
3. Principles (D16): built for kids (no ads, no tracking, no accounts, works on tablets), free forever (GPL-3.0), yours to fork, open to contributions
4. How it works in 3 steps: fork → write questions in a simple file → your quiz site is online
5. Get involved: contribute code, quizzes or collections; link to CONTRIBUTING and the GitHub repo
6. Footer: licence, repo link, "made with love for kids" tone

### Guide (`/guide/`)
Step-by-step, written for non-programmers first (D19), with screenshots of GitHub's UI. One page with a sticky table of contents:
1. **Make your own quiz site in 10 minutes**: create a GitHub account → fork → enable Pages + Actions → see your site live
2. **Write your first quiz**: edit a JSON file in the GitHub web editor, a minimal annotated example, commit → wait for the Action → refresh
3. **Quiz file reference**: every field, in plain language, with examples (kept in sync with the README / `schema.json`)
4. **Saying who made it**: the `author` field, why to prefer a website or a quiz-only email over a personal address, and never including children's names or contact details
5. **Changing the button and message text** (`ui` overrides)
6. **Adding images**: uploading via the GitHub web UI, using image links, size and licensing tips
7. **Multiple languages**: `languages`, translation maps, the `any` key
8. **When something goes wrong**: reading the failed Action log, common validation errors and fixes
9. **Turning off the project pages** in your fork (`PROJECT_PAGES=false`)
10. **Sharing a quiz without a website**: single-file HTML (for developers or with help, needs the CLI)
11. **Contributing back**: sending a quiz or collection to the main library via PR; the quiz checklist
12. **For developers**: link to the README sections on local install and CLI

The guide must not duplicate the README wholesale: the README is the full reference, and the guide is the friendly walkthrough that links to it for details.

### Contributions (D20)
- PR types: **code** (tool improvements), **quiz** (add to `quizzes/`), **collection** (a new `quizzes/<collection>/` folder, D21).
- Quiz/collection checklist in the PR template: age-appropriate content, correct answers double-checked, images owned by the contributor or openly licensed (with source noted), no personal data about children, validates locally or in CI.
- `ci.yml` runs automatically on every PR: tests + `quizgen validate quizzes/`. No secrets needed, so it's safe on fork PRs and costs nothing.

### Maintainer-triggered Claude review (D20)
- Uses `anthropics/claude-code-action`, triggered **only** by a PR comment such as `/claude-review` **from the repo owner** (check `github.event.comment.author_association == 'OWNER'`, or the actor equals `rcocetta`), plus `workflow_dispatch` with a PR number. Never on `pull_request` or `pull_request_target` events.
- `ANTHROPIC_API_KEY` as a repo secret; Actions settings require approval before workflows run for first-time contributors.
- Security: the workflow reads untrusted PR content, so it's prompt-injection exposed. Give it read-only repo permissions plus permission to comment, no ability to push or merge, no other secrets. Treat its output as advice.
- The review prompt focuses on: correctness of quiz answers, age-appropriateness, image licensing notes, i18n completeness, and, for code PRs, the usual code review plus whether `PLAN.md`/README were updated.
- Budget guard: low `max_turns`, so a single trigger can't run up a large bill.

---

## 9. Future ideas (not in v1)
- Deeper nesting / categories on the index page
- Other question types (multiple correct, true/false, type-the-answer)
- Timer, sound effects, confetti on high scores
- Fallback language mode (rejected for v1, see D9)

---

## Session log

Append one entry per session/subagent run: date, who, what changed, what's next.

- **2026-10-11** — Planning session with user. Agreed D1–D13 (D13: `any` key for language-neutral text), drafted schema, CLI, runtime and task breakdown. **Next:** start Phase 1.
- **2026-10-11** — User confirmed the project will be open-sourced (D14). Expanded Phase 4 into an exhaustive README spec plus licence/contributing/changelog/CI. D15 (licence) open.
- **2026-10-11** — Linked local folder to https://github.com/rcocetta/school-quiz (existing `LICENSE` GPL-3.0 + `.gitignore`); D15 settled. Added `CLAUDE.md`. Nothing committed yet.
- **2026-10-11** — Planned the project website (landing `/`, guide `/guide/`, quizzes `/quizzes/`), fork-first guide for non-programmers, contribution model (code/quizzes/collections) and maintainer-triggered Claude review. Added D16–D21 and Phase 5. D21 (meaning of "sites") open.
- **2026-10-11** — D21 confirmed (collections). Added D22: optional `author` (name/url/email) on quizzes and collections, with inheritance and validation rule 11. Open proposal: "Made with school-quiz" footer credit in generated pages (not yet decided).
- **2026-10-11** — Added D23 (footer credit) and the Working principles section (quality bar, security rules, subagent/model policy). Planning complete; committed and pushed. **Next:** Phase 1.
- **2026-10-11** — UI strings written (en/it/es/fr/de); Italian reviewed by user and made gender-neutral. Added D24: creator `ui` overrides (quiz > collection > built-in), validation rule 12.
- **2026-10-11** — Phase 1 implemented (sonnet subagent; 68 tests) + UI strings (haiku). Example times-tables is en/it/fr. Opus security review found 12 issues (crash on hostile JSON/long paths, `null` file passing, loose author url/email, non-image files accepted as images, …); fixes in progress. Added D25 (local image types). Researched Claude Code on the web for cloud work: user to link repo via GitHub App (only this repo).
- **2026-10-11** — Review fixes applied and verified (114 tests; hostile-input repros all give clean errors). **Phase 1 done**, committed and pushed. **Next:** Phase 2 (quiz page + single-file build) — can run in Claude Code on the web once the user links the repo.
- **2026-10-11** — User confirmed D25. Added project agents in `.claude/agents/` (quiz-implementer, quiz-designer, security-reviewer, simplicity-reviewer, e2e-tester) so the subagent policy works in cloud sessions; documented the per-phase workflow. User linking the repo to Claude Code on the web.
- **2026-10-11** — Phase 2 (cloud session). User approved D26 (`image_alt`). Contract for template/data/CSP set by main session; `quiz-implementer` built `build.py`, `build <file>`, `image_alt`, `picture_n`; `quiz-designer` built the quiz page (in parallel). Security review: no XSS/breakout found; fixed input overwrite, planted-symlink temp file, unbounded image inlining (1.2 GB output repro), tracebacks on bad `-o`, CRLF/CSP hash risk, added image magic-byte check. Simplicity review fixes: dead JS fallbacks removed, `render_page`/`_rewrite_images` extracted for Phase 3. E2E (fresh non-editable install, Chromium): all "Done when" criteria pass; fixed `-o dir/` and jargon in the folder message. 149 tests. **Phase 2 done.** **Next:** Phase 3 (site build + index).

- **2026-10-11** — Phase 3 (cloud session). User decisions: D27 `site.json` (index language/title), D28 select-then-Check in immediate mode, D26 extended (`image_alt: ""` decorative, warnings for undescribed images); main session chose D29 (output mirrors input folder). `quiz-implementer` built `build_site`/`site.py`, `site.json`, collection `language`, `build <dir>`; `quiz-designer` built index pages and the back link, then the Check flow. First `accessibility-reviewer` run (covering the Phase 2 quiz page too): axe clean, fixed feedback/score announcements, number-key shortcut (WCAG 2.1.4), progress description, review right/wrong text, landmarks, font weights. Security review: fixed symlinked JSON being published, control-char image refs turning into remote requests, tracebacks on non-UTF-8 names, partial writes and mkdir outside output (now full pre-flight), reserved names moved into `discover`. Simplicity review: split `site.py`, single image walker, exact test asserts. E2E: site Done-when passes; found a single-file crash on Start (null back link) — fixed by main session and re-verified in Chromium (both examples, full run, no errors). 187 tests. **Phase 3 done.** **Next:** Phase 4 (examples, docs, CI incl. browser smoke test).
