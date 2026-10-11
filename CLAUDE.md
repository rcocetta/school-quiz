# CLAUDE.md

`quizgen` (repo: https://github.com/rcocetta/school-quiz, GPL-3.0): a Python CLI that turns quiz JSON files into static HTML quizzes for kids (no backend, GitHub Pages friendly). It will be open-sourced.

## Always
- **Read `PLAN.md` first.** It is the source of truth: decisions, schema, validation rules, module contracts, task list and status.
- Don't re-open decisions marked ✅ in `PLAN.md` without asking the user. Ask about ❓ open ones before work that depends on them.
- **When you finish work, update `PLAN.md`:** tick tasks, update the Status table, and add a Session log entry (date, what changed, what's next). If you are a subagent, include in your final report the `PLAN.md` changes you made.
- If implementation forces a change to the schema, CLI or behaviour, update `PLAN.md` (and the README once it exists) in the same change.

## Writing quizzes
When asked to write or edit a quiz (not the tool), follow `AGENTS.md`.

## Working principles
Follow the **Working principles** section of `PLAN.md`: kids-first UX, easy for non-programmer creators, simple over clever, secure by default, and the subagent/model policy. Use the project agents in `.claude/agents/` (`quiz-implementer`, `quiz-designer`, `security-reviewer`, `simplicity-reviewer`, `accessibility-reviewer`, `e2e-tester`) and follow the per-phase workflow in `PLAN.md` → "Using subagents". Cheapest model that does the job well: haiku for mechanical work, sonnet for implementation and reviews, opus for orchestration, security review and design decisions.

## Conventions
- Python ≥ 3.10; runtime deps only `jsonschema` and `jinja2`. Browser code is vanilla JS/CSS: no frameworks, no external requests.
- Quiz text is rendered with `textContent`, never `innerHTML`.
- The validator outputs a normalised quiz (defaults filled, every Text a full `{lang: string}` map, `any` expanded). Builders and JS consume only that form.
- Run `pytest` before declaring a task done.
