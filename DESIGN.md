# Design

Why `quizgen` works the way it does: settled decisions, principles, validation rules and module contracts. For usage see the [README](README.md); for how to contribute see [CONTRIBUTING.md](CONTRIBUTING.md). Current status and next steps are in [PLAN.md](PLAN.md).

Decisions marked ✅ are settled. To change one, open an issue first rather than a pull request.

## Goal

A Python CLI (`quizgen`) that turns quiz JSON files into static HTML quizzes for primary and early-secondary school kids. No backend: output works when served from GitHub Pages, or opened as a local file in single-file mode.

Each quiz file holds a pool of **N** questions; each attempt shows **M** of them (M ≤ N), picked at random in the browser.

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
| D13 | Text maps may use the special key **`"any"`**: the value for every language unless that locale has its own key (`{"any": "12"}`, `{"any": "Rome", "it": "Roma"}`). Plain strings in multi-language mode stay an error (hint: use `any`) | ✅ |
| D14 | Project is **open source**: exhaustive README, licence, contributor docs, clean repo hygiene | ✅ |
| D15 | Licence: **GPL-3.0-or-later** | ✅ |
| D16 | Mission: **built for kids, free forever, anyone can fork and run their own, or contribute back via PR** | ✅ |
| D17 | GitHub Pages site layout: `/` landing page, `/guide/` how-to guide, `/quizzes/` quiz index. Forks can skip the project pages, which puts their quiz index at `/` | ✅ |
| D18 | Website and guide in **English only** (quizzes themselves stay multi-language) | ✅ |
| D19 | ~~Fork → edit in GitHub's web editor → Action builds and deploys~~ Superseded by D30 | ⛔ |
| D20 | PRs welcome for **code, quizzes and collections**. Claude review of PRs exists but is **triggered only by the maintainer** (never automatic) | ✅ |
| D21 | Contributed "sites" are **collections**: a subfolder `quizzes/<collection>/` with its own index page | ✅ |
| D22 | Optional **`author`** (`name` required, `url`, `email` optional) on quizzes and collections; a quiz inherits its collection's author. Plain strings, never translated. The guide discourages personal emails | ✅ |
| D23 | Generated quiz and index pages carry a small **"Made with school-quiz" footer link** to the project's Pages home (https://rcocetta.github.io/school-quiz/). On by default; removable by anyone (no obligation beyond GPL notices) | ✅ |
| D24 | Creators can **override built-in UI text** with an optional `ui` object on a quiz or in `collection.json` (quiz > collection > built-in). Partial overrides allowed | ✅ |
| D25 | **Local images limited to png, jpg/jpeg, gif, webp.** No local SVG: copied to the site, an SVG opened directly runs script on the `github.io` origin. Remote image URLs (any type) still allowed; `https://` recommended (CSP), `http://` gives a warning | ✅ |
| D26 | Optional **`image_alt`** (Text) on questions and options. Error without `image`. `""` marks an image as decorative (not allowed on picture-only options). Missing `image_alt` → validator warning; browser fallback: question image `alt=""`, option image uses the option text, else UI string `picture_n` | ✅ |
| D27 | Optional top-level **`site.json`** (`title`, `description`, `author`, `language`; plain strings). Index text comes from `ui_strings.json` in the site language (default `en`); `collection.json` gains optional `language`. Loose quizzes inherit the site author; collection quizzes inherit only the collection author | ✅ |
| D28 | **Immediate feedback = tap to select, then "Check"**: a mis-tap can be changed before checking. Number keys 1–9 only select, and only while focus is in the options (WCAG 2.1.4) | ✅ |
| D29 | Site output **mirrors the input folder**: each page sits where its JSON is, local images copied once to the same relative path | ✅ |
| D30 | **GitHub Pages serves `/docs` on `main`.** The built site is committed in `docs/` and **rebuilt by hand** with `python scripts/build_docs.py` (`--quizzes-only` for forks that skip the project website); no workflow writes to the repo; **CI fails when `docs/` is out of date** | ✅ |
| D31 | Optional **`unlisted: true`** in `collection.json`: the collection (index page + quizzes) is built at `<collection>/` but not linked from the top index, and its own page has no "All quizzes" back link. Not private (public repo, no `noindex`) | ✅ |

## Working principles

### Quality bar
- **Kids first.** Big tap targets, large clear text, few words per screen, no dead ends, gentle encouraging tone (never shaming on wrong answers; UI text gender-neutral in gendered languages), works on cheap tablets and phones, keyboard and screen-reader friendly (WCAG 2.2 AA contrast, real `<button>`s, labels, focus states, `alt` text for images).
- **Easy for creators.** Teachers and parents shouldn't need to code. Defaults for everything optional, error messages that say *where* and *how to fix*, examples they can copy.
- **Simple over clever.** Few dependencies, no frameworks, no build step for the browser code. Every feature must earn its place.
- **Secure by default** (kids are the audience):
  - Quiz text always via `textContent`; JSON embedded safely (no `</script>` break-out); no `eval`/`innerHTML` with data.
  - Strict Content-Security-Policy `<meta>` in generated pages (no external scripts; images allowed from `https:` for remote image URLs).
  - Links in author fields: only `http(s)://` and `mailto:`, `rel="noopener noreferrer"`, never `javascript:`.
  - Path traversal blocked when copying/inlining images; output only written inside the chosen output dir.
  - No tracking, analytics, cookies or third-party requests. `localStorage` only for the language preference.
  - GitHub Actions: least-privilege `permissions:`, pinned action versions (commit SHAs), no secrets on PR-triggered workflows.

### Contributions (D20)
- PR types: **code**, **quiz** (add to `quizzes/`), **collection** (`quizzes/<collection>/`, D21).
- Quiz/collection checklist in the PR template: age-appropriate content, correct answers double-checked, images owned or openly licensed (source noted), no personal data about children, validates locally or in CI.
- `ci.yml` runs on every PR (tests, validation, `docs/` freshness, browser smoke test). No secrets, so it is safe on fork PRs.
- Claude review (`claude-review.yml`) runs only on the owner's `/claude-review` comment or a manual run. It reads untrusted PR content, so it is split into jobs: `fetch` (read-only token, no secrets), `review` (no repo token; read-only tools; the only job holding the model credential) and `post` (comment-write only; filters secret patterns, images and HTML, neutralises @-mentions). Its output is advice, never an approval.

## Validation rules

All problems are collected and reported together, each with a JSON path, e.g. `farm.json: questions[4].options[2].text: missing translation "it"`. Exit code 1 on any error. Warnings print but don't fail.

Errors:
1. JSON parse failure (line/col).
2. Structural: required fields, types, enums, unknown keys (via `schema.json` + `jsonschema`). Unknown keys anywhere are errors (catches typos like `corect`).
3. Each question has **exactly one** option with `correct: true`.
4. Each question has ≥ 2 options; each option has `text` or `image`.
5. M > N (after applying `--questions`).
6. i18n, when `languages` present: every Text is an object whose keys are a subset of `languages` ∪ {`any`}; every language covered by its own key or `any`; empty strings count as missing; unknown language keys → error. Plain strings → error with hint `use {"any": "..."}`. `"any"` can't appear in `languages`.
7. i18n, when `languages` absent: every Text is a plain string; an object → error with hint "add a `languages` field".
8. `language` and `languages` both present.
9. Every language code must exist in `ui_strings.json`.
10. Local image: missing, escapes the quiz directory (`..`, absolute, symlinks), disallowed type (D25), over 5 MB, content that doesn't match its extension, control characters, `\`, or non-normalised path. `image_alt` without `image`, or `""` on a picture-only option (D26).
11. `author`: missing `name`, `url` not `http(s)://`, `email` not a basic `x@y.z` shape (same for `collection.json`).
12. `ui`: unknown key; language key not in `languages`; string where a map is required (or vice versa); empty string; a placeholder not used by that key's built-in text. A required placeholder that's missing is a **warning**.
13. Folder problems (from `discover`, so `validate` and `build` agree): symlinked JSON files, names that aren't valid UTF-8, a quiz named `index.json`, a collection folder named `assets` or ending in `.html`, `site.json` outside the top level, `collection.json` at the top level, names that differ only in case.

Warnings:
- M == N (every attempt has the same question set, just reordered).
- Duplicate option texts within a question (per language after expansion).
- A Text map has `any` **and** a key for every language (`any` is never used).
- An `http://` image URL (the page CSP only allows `https:` and `data:` images).
- A question image, or a picture-only option, without `image_alt` (D26).
- A collection folder with no quizzes (skipped).

`schema.json` is the structural contract (rules 1–2, plus the shape of Text via `oneOf`); the rest live in Python in `validate.py`.

## Quiz page (browser runtime)

- Vanilla HTML/CSS/JS. No framework, no external requests (system font stack; a small bundled flag font).
- Quiz data embedded as `<script type="application/json" id="quiz-data">`, escaped so `</script>` in content can't break out. Built-in UI strings for the quiz's languages are embedded alongside.
- All quiz text rendered via `textContent`, never `innerHTML`.
- **Screens**
  1. **Start**: title, description, "Made by <name>" (links to `url`, else `mailto:`), number of questions, language switcher (if >1 language), "Start".
  2. **Question**: progress, question text + image, options as large buttons (text and/or image).
     - `immediate` (D28): tap selects (changeable), "Check" locks options, marks chosen and correct ones, shows the explanation if present (focus moves to the feedback), then "Next".
     - `end`: tap highlights the selection, "Next" enabled; no correctness shown.
  3. **End**: score, encouraging message tiered by percentage (great ≥ 80 %, good ≥ 50 %, else keep trying), review list, "Try again" (new random M, reshuffled).
- **Footer** on every generated page (D23).
- **Randomness**: Fisher–Yates shuffle of the pool, take the first M; options shuffled per question if `shuffle_options`.
- **Language switcher**: flag emoji + code. Flags use the bundled `flags.woff2` (a Noto Color Emoji subset, OFL) because Windows has no flag emoji. Switching re-renders in place, keeping state. The choice is remembered in `localStorage` (wrapped in try/catch; the page works without it).
- **Design**: mobile/tablet first, tap targets ≥ 48px, large readable font, high contrast, visible focus, keyboard usable, respects `prefers-reduced-motion`.
- `ui_strings.json` maps `lang → {key: string}` for all interface text. It ships `en`, `it`, `es`, `fr`, `de`.

## Module contracts

- `validate.load_quiz(path, questions_override=None, ui_langs=None) -> ValidationResult(quiz, errors, warnings, structural_failure)`; `Issue(file, path, message)`.
  - On success `quiz` is **normalised**: defaults filled; every Text a full map with one key per language and `any` expanded (single-language quizzes become `{"<language>": "..."}` with `languages: [<language>]`); `ui` kept as a per-language partial map (merged with built-ins and the collection's `ui` at build time); `correct` always a bool; `author` only if given. Builders and JS only ever see this form.
  - Structural errors suppress the semantic pass, so semantic checks never see malformed data.
  - Default M = `min(10, N)`; M > N and the M == N warning apply only when M is explicit.
- `validate.load_collection(path)`, `validate.load_site(path)`, `validate.discover(dir) -> (files, problems)`. A collection's `ui` keeps `any` unexpanded until it is merged into each quiz.
- Reuse, don't re-implement: `validate.IMAGE_TYPES`, `validate.is_remote_image`, `validate.local_image_path`, `validate.is_inside`.
- `build.build_single(quiz_path, out_path=None, questions_override=None) -> BuildResult`; `site.build_site(quiz_dir, out_dir=None, questions_override=None) -> BuildResult`. Shared helpers in `build.py`: `merge_ui` (built-in < collection < quiz), `render_page`, `embed_json`, `_write_atomic`.
- The JS reads the normalised quiz and UI strings; it never needs to know whether the source was single- or multi-language.

### Output safety
- `build` always validates first; on error nothing is written. For sites, every write is planned and checked (clashes, symlinks, file-vs-folder) before anything is written. Output must not be, be inside, or contain the input folder. Existing files are never deleted. Writes go through a random `O_EXCL` temp file and `os.replace`.
- Images: ≤ 5 MB each, content must match the extension (magic bytes); ≤ 20 MB inlined per single-file page.
- CSP, single file: `default-src 'none'; script-src 'sha256-…'; style-src 'sha256-…'; img-src data: https:; font-src data:; base-uri 'none'; form-action 'none'`. CSP, site quiz pages: `script-src 'self'; style-src 'self'; img-src 'self' data: https:; font-src 'self'`; index pages have no JS. `'self'` trusts the whole `<user>.github.io` origin, which is why contributors can't place executable files: only the shared assets and magic-byte-checked images are written.
- Remote `https://` images are requested by the child's browser, so the image host sees their IP. Allowed (D6); the README and the contribution checklist recommend local images.
- `docs/` carries a `.quizgen-build` marker; `build_docs.py` only replaces a `docs/` it built itself.
