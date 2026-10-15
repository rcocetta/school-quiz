# AGENTS.md: writing quizzes with an AI assistant

This file is for AI coding assistants (Codex, Cursor, Copilot, Claude, Gemini, ...) that help a teacher or parent **write a quiz** for school-quiz. It covers the quiz files only. To change the tool itself, read [CONTRIBUTING.md](CONTRIBUTING.md) instead.

school-quiz turns a JSON file into a web page a child can play on a phone, tablet or computer. Your job is to produce a correct, kind, age-appropriate quiz file that passes `quizgen validate`. The [README](README.md#writing-a-quiz) is the full reference; this page is the short version plus the rules that matter most.

## Workflow

1. **Ask before writing**, unless the person already said:
   - the child's age or school year, and the language of the quiz;
   - the topic, and ideally the **source**: the lesson, the textbook pages, the teacher's worksheet. Questions taken from what the child actually studied work far better than general knowledge;
   - how many questions in total (N) and per attempt (M).
2. **Write the quiz** following the rules below. Put it in `quizzes/` (or in `quizzes/<collection>/` for a group of quizzes), named in lowercase with dashes, for example `quizzes/volcanoes.json`.
3. **Validate**: `quizgen validate quizzes/` (or `python -m quizgen validate ...`). Fix every error and every warning.
4. **Preview**: `quizgen build quizzes/volcanoes.json` writes `volcanoes.html` next to it; open it in a browser.
5. **Publish** (only in a fork of this repository that publishes from `docs/`): run `python scripts/build_docs.py` and commit `docs/` together with the quiz. Never edit `docs/` by hand.
6. **Report honestly**: list any fact you are not sure of, so a person can check it against the lesson.

Installing the tool: `pipx install git+https://github.com/rcocetta/school-quiz` (needs Python 3.10+). From a clone: `python3 -m venv .venv && .venv/bin/pip install -e .`

## The file format

```json
{
  "$schema": "https://raw.githubusercontent.com/rcocetta/school-quiz/main/src/quizgen/schema.json",
  "title": "Volcanoes",
  "description": "What did we learn about volcanoes?",
  "language": "en",
  "questions_per_quiz": 8,
  "feedback": "immediate",
  "shuffle_options": true,
  "author": { "name": "Class 4B" },
  "questions": [
    {
      "text": "What is the hot melted rock inside a volcano called?",
      "explanation": "Inside the volcano it is magma; once it comes out, it is called lava.",
      "options": [
        { "text": "Magma", "correct": true },
        { "text": "Sand" },
        { "text": "Clay" }
      ]
    }
  ]
}
```

This example is shortened to one question; a real file needs more questions than `questions_per_quiz`.

Rules the validator enforces (an error stops the build):

- **Exactly one** option per question has `"correct": true`. At least 2 options; each needs `text` or `image`.
- **No unknown fields.** Allowed at the top: `$schema`, `title`, `description`, `language` or `languages` (not both), `questions_per_quiz`, `feedback` (`"immediate"` or `"end"`), `shuffle_options`, `author`, `ui`, `questions`. In a question: `text`, `image`, `image_alt`, `explanation`, `options`. In an option: `text`, `image`, `image_alt`, `correct`. In `author`: `name` (required), `url`, `email`.
- `questions_per_quiz` (M) must not be larger than the number of questions (N). Make N bigger than M (for example 16 and 8) so each attempt is a different mix; M equal to N gives a warning.
- `language` is one of the built-in interface languages: `en`, `it`, `es`, `fr`, `de`. It sets the buttons and messages; write the questions in the same language.
- **Several languages in one quiz:** use `"languages": ["en", "fr"]` and write **every** text as a map, `{ "en": "...", "fr": "..." }`, with no language missing and no plain strings. `{ "any": "12" }` means the same text in every language (numbers, names). See the [README](README.md#multiple-languages).
- **Images:** local `png`, `jpg`, `jpeg`, `gif` or `webp` files next to the quiz (usually `images/`), at most 5 MB, relative paths with no `..`; or `https://` links. No SVG. Give each picture an `image_alt` that describes it **without giving away the answer** (for "Which animal is this?" write "A brown and white animal with horns", not "A cow"). Use `"image_alt": ""` for pure decoration.
- Valid JSON: double quotes, no trailing commas, no comments.

## Collections

A group of quizzes (one teacher's, one class's) goes in a folder `quizzes/<collection>/`, one level deep. An optional `collection.json` next to the quizzes sets the collection's `title`, `description`, `author`, `language`, `ui` and `unlisted` (no other fields). `"unlisted": true` leaves the collection off the main index but still publishes it, so anyone with the address can open it: it is **not private**, so apply the privacy rules below as usual. See the [README](README.md#collections-and-folder-layout).

## Writing good questions for children

- **Match the lesson and the age.** Use the words, dates and names from the child's lesson. If the child is 9, write for a 9-year-old: short sentences, everyday words, one idea per question.
- **One answer must be clearly right, and the others clearly wrong.** Check every wrong option: if a teacher could argue for it, change it. Avoid answers that are "partly true", and avoid near-dates that are both defensible (for example, a right that was granted in one year and first used the next).
- **Make the wrong options plausible but not tricky.** Same kind of thing as the right answer (all dates, all people, all places), similar length. Avoid trick questions, double negatives and "All of the above" (if you must use ordered or "all of the above" options, set `"shuffle_options": false`).
- **3 options** are a good default for younger children, **4** for older ones.
- **Always add an `explanation`**: one or two short sentences that teach something, shown after the answer. Never mock a wrong answer.
- **Do not let one question give away another's answer** (for example a question naming the date that another question asks for).
- **Check every fact.** Be careful with words like "becomes", "first", "always" and "only": they are often half-true (an anthem *re*adopted, a country only *partly* occupied). If unsure, rephrase to what is certainly true, or tell the person what to check.
- **Mix difficulty.** A few easy questions build confidence; if the person says it was too hard, simplify the wording and the options before removing topics.
- Keep `feedback` as `"immediate"` for learning; `"end"` is for a review at the end only.

## Privacy, copyright and safety

Quizzes in this repository and on GitHub Pages are **public**.

- **No personal data about children**: no names, photos, school or class names tied to a child, or contact details, in the quiz, in `author`, in images or in file names. For `author`, prefer a class or project name and a website over a personal email.
- **Photos of textbooks or worksheets are source material, not content.** Use them to write questions in your own words; never add them to the repository, and never copy long passages word for word.
- **Images must be the author's own or openly licensed** (for example Public Domain, CC0, CC BY, Apache-2.0). Record the source and licence in an `images/CREDITS.md` next to the images when the licence asks for credit. Prefer local images: a remote image lets its host see the child's IP address.
- Content must be suitable for children: no violence beyond what the curriculum requires, no stereotypes, kind wording.

## Before you finish

- [ ] `quizgen validate quizzes/` shows no errors and no warnings.
- [ ] Every correct answer is right, and every wrong answer is wrong, checked against the lesson.
- [ ] Every question has an `explanation`.
- [ ] N is larger than M.
- [ ] No personal data, no copyrighted images or textbook scans.
- [ ] If publishing from a fork: `python scripts/build_docs.py` was run and `docs/` is committed with the quiz.
- [ ] You told the person which facts, if any, they should double-check.
