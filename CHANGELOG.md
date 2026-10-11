# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Everything below will be released as 0.1.0, the first version.

### Added

- `quizgen validate`: checks quiz, `collection.json` and `site.json` files and folders, reports every problem at once with its location in the file and a hint on how to fix it, and warns about things that work but are probably mistakes.
- Quiz format: JSON files with a pool of N questions of which M are shown per attempt (`questions_per_quiz`); multiple choice with exactly one correct option; text and/or picture options; `explanation`; `feedback` mode (`immediate` or `end`); `shuffle_options`. A JSON Schema (`schema.json`) gives editors autocomplete.
- Multiple languages in one quiz (`languages`), with per-field translation maps, the `any` key for text that is the same in every language, and a flag-and-code language switcher that keeps the child's place and remembers the choice in `localStorage`. Built-in interface text in English, Italian, Spanish, French and German.
- `author` (name, optional link and email) on quizzes, collections and sites, with inheritance.
- `ui` overrides to replace built-in button and message text on a quiz or a collection, with placeholder checks.
- Images: local png, jpg/jpeg, gif and webp (5 MB each, content checked against the extension, path traversal blocked) and remote `https://` links; `image_alt` text for screen readers, with warnings for undescribed images.
- `quizgen build <file>`: one self-contained HTML page (CSS, JavaScript and images inlined) that works offline.
- `quizgen build <folder>`: a static website with an index page, one page per quiz, collections (one level of subfolders, each with its own index page), shared assets, copied images and a `.nojekyll` file. The output mirrors the input folder. Optional `site.json` for the site title, description, author and language.
- `--questions M` to override the number of questions per attempt for a build.
- Quiz page: kid-friendly start, question and end screens; tap to select then "Check my answer" in immediate mode; score, encouraging message, answer review and "Play again" with a new random set; keyboard and screen-reader support; respects reduced-motion.
- Safe by default: no external requests, strict Content-Security-Policy on every page, quiz text inserted with `textContent`, safe JSON embedding, nothing written when validation fails, output kept out of the input folder, no overwriting the input.
- Example quizzes (single-language and multi-language) with pictures from Noto Emoji (Apache-2.0).
- Documentation: README with a full field reference, validation guide, CLI reference, publishing guide (including a copy-paste GitHub Actions workflow) and FAQ; CONTRIBUTING; this changelog.
- Project website at <https://rcocetta.github.io/school-quiz/>: landing page, step-by-step guide for teachers (fork, edit in the browser, publish), and the shared quiz library in `quizzes/`.
- `.github/workflows/pages.yml` builds `quizzes/` and the website and deploys them to GitHub Pages; forks can set the repository variable `PROJECT_PAGES=false` to publish only their quizzes at the root of their site.
- `.github/workflows/claude-review.yml`: Claude review of a pull request, started only by the repository owner (comment `/claude-review`), split into isolated steps (reading the pull request has no secrets, running Claude has only the API key and no shell or network access, posting the comment checks the text first).
- Community files: Code of Conduct (Contributor Covenant 2.1), security policy (private vulnerability reporting), pull request template with quiz and collection checklist, issue forms for bugs, feature requests and quiz ideas.
- Contributor tooling: browser smoke tests with Playwright (optional `browser` extra), a script that regenerates the README screenshots, and a CI workflow that runs the tests and validates the examples and quizzes.

### Fixed

- Index pages no longer repeat the page title as a section heading when they have only one kind of card (only quizzes, or only collections); cards are then second-level headings, so screen readers hear each heading once and levels never skip.
