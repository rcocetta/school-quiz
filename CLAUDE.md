# CLAUDE.md

`quizgen` (repo: https://github.com/rcocetta/school-quiz, GPL-3.0): a Python CLI that turns quiz JSON files into static HTML quizzes for kids (no backend, GitHub Pages friendly). It will be open-sourced.

## Always
- **Read `DESIGN.md` first** (decisions, principles, validation rules, module contracts), then `PLAN.md` (status and next steps).
- Don't re-open decisions marked ✅ in `DESIGN.md` without asking the user.
- **When you finish work, update `PLAN.md`:** tick or add items under Next and update the Status table. If you are a subagent, include the `PLAN.md` changes in your final report instead of editing it.
- If implementation forces a change to the schema, CLI or behaviour, update `DESIGN.md` and the README in the same change.
- The repo is public: no personal data (especially about children), credentials, or repository-settings details in `PLAN.md`, `DESIGN.md` or commit messages. Keep `PLAN.md` short; there is no session log.

## Writing quizzes
When asked to write or edit a quiz (not the tool), follow `AGENTS.md`.

## Working principles
Follow the **Working principles** in `DESIGN.md`: kids-first UX, easy for non-programmer creators, simple over clever, secure by default. Use the project agents in `.claude/agents/` (`quiz-implementer`, `quiz-designer`, `security-reviewer`, `simplicity-reviewer`, `accessibility-reviewer`, `e2e-tester`).

Subagents: pick the cheapest model that does the job well: haiku for mechanical work, sonnet for implementation and reviews, opus for orchestration, security review and design decisions. Give each agent a self-contained brief and one task scope; run agents in parallel only when their files don't overlap. Workflow: implement → run the tests → security, simplicity and (for UI changes) accessibility reviews in parallel → fixes → e2e check → update `PLAN.md`, commit. Subagents don't edit `PLAN.md`/`DESIGN.md`; the main session does.

## Conventions
- Python ≥ 3.10; runtime deps only `jsonschema` and `jinja2`. Browser code is vanilla JS/CSS: no frameworks, no external requests.
- Quiz text is rendered with `textContent`, never `innerHTML`.
- The validator outputs a normalised quiz (defaults filled, every Text a full `{lang: string}` map, `any` expanded). Builders and JS consume only that form.
- Run `pytest` before declaring a task done.
