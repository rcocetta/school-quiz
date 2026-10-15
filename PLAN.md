# Plan

Current status and next steps. Design decisions, validation rules and module contracts are in [DESIGN.md](DESIGN.md). This file is public: keep it short, and put no personal data, credentials or repository-settings details in it.

## Status

| Phase | State |
|---|---|
| 1. Schema + validator | ✅ done |
| 2. Quiz page + single-file build | ✅ done |
| 3. Site build + index page | ✅ done |
| 4. Examples, docs, CI | ✅ done |
| 5. Project website + community | 🟨 built; needs a check on the deployed site and in a real fork |

Legend: ⬜ not started · 🟨 in progress · ✅ done · ⛔ blocked

## Next

- [ ] Check the deployed site (landing ↔ guide ↔ quizzes ↔ repo links) and follow the guide in a real test fork.
- [ ] First real run of `claude-review.yml`.
- [ ] `v0.1.0` tag, then pin the install in the README's Pages workflow snippet.
- [ ] Not tested yet: Firefox/WebKit, real devices, screen readers, `es`/`de` index text.

## Ideas (not planned)

- Link from the quiz index back to the landing page or guide (needs a small `site.json` option).
- Deeper folder nesting or categories on the index page.
- Other question types (multiple correct, true/false, type-the-answer).
- Timer, sound effects, confetti on high scores.
