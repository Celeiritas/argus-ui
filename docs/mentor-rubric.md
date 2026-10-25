# Mentor deck rubric – how a card should read
Every lesson and deck Mentor shows follows these five rules. They exist because a card is read by someone who is still building the idea: anything that isn't the idea (a folder, a file name, a word from the project's workflow) takes up the same small working memory the idea needs (Sweller, 1988).

Check a file before it goes in a theme or the Mentor inbox:
```
python3 scripts/check-deck.py themes/leafy-realm/decks          # or one file, or several
```
It prints one line per finding (`ERROR` stops the tests, `WARN` is a prompt to look again) and checks only what the learner reads: code, snippets and answers may name files. `tests/run.sh` runs it on every pull request.

## R1 – No file paths, no repo jargon
The card says *what the code does*, not *where it lives*. Cards show only a function's name (`current()`) above the code; the file list stays in the **Lessons** view for when you want to find it.

| Instead of | Write |
|---|---|
| "`sky.py -> current()`: `with _lock:`" | "`current()`: `with _lock:`" |
| "mentor.py keeps your cards in SQLite" | "Mentor keeps your cards in SQLite" |
| "as decided in the handoff" | (say the reason itself) |

ERROR: a file name or path (`sky.py`, `server/sky.py`, `~/…`, `{{HOME_PC}}`), or a breadcrumb ending in a file. WARN: *repo, PR, pull request, handoff, CLAUDE.md, worktree, TODO*.

## R2 – One idea per card
A card that teaches two things teaches neither well. Definitions and contrasts are one sentence (≤ 30 words); explanations and answers ≤ 80 words; a pre-read lists at most three key ideas. If it needs more, split it into two cards. WARN.

## R3 – A question before each explanation
Trying to answer first, even wrongly, makes the explanation that follows stick better (the pretesting effect: Richland, Kornell & Kao, 2009). Every teach card and pre-read gets a `try_first` question: you type a guess, nothing is graded or scheduled, then the explanation appears next to your guess. Ask about the idea, not the code's details: "Why would a program keep a copy of something it could fetch again?" WARN when missing.

## R4 – Worked example first, then fade
Novices learn a procedure from a fully worked example before they write it themselves (Sweller & Cooper, 1985), then the help is taken away one step at a time (Renkl & Atkinson, 2003). Every drill has `level_0_worked` annotations (the full code, line by line, with why each line is there) and starts fading at `level_1_fade`. ERROR when missing.

## R5 – Plain words, every term defined once
Use everyday words; a technical term appears only after its term card has defined it. Each term has exactly one term card with a `concise_definition`, and no term is defined twice (two definitions compete). ERROR.

## Courses: checker v2 (4.26.0)
A course file (`"format": "mentor-course/1"`, [docs/mentor.md](mentor.md#courses-4260)) gets R1–R5 on every lesson, plus:

| Rule | Refuses |
|---|---|
| C1 | a missing `format`, `id`, `name`, `los` or `modules`; a module without `name` / `lessons`, a lesson without `los`; an id used twice (LOs and lessons in the course, where `Words` and `words` count as the same; modules; notes and cards in a lesson); an id that is a list or an object |
| C2 | an LO missing any of `id, text, verb, bloom, mode, knowledge, condition, standard, parent`; a `bloom`, `mode` or `knowledge` outside its list; more than one verb; *know*, *understand* or *learn about* as the verb; text that doesn't start with its verb. An unusual verb is a warning |
| C3 | a module LO whose parent isn't a course LO, a lesson LO whose parent isn't an LO of its own module. A course or module LO nothing serves is a warning |
| C4 | a card without an LO of its lesson, a role that doesn't fit its list (term, recall · drill · explain, find-bug, choose-design), a role phase 4 adds (predict, trace, parsons, write, make), a `note` the lesson doesn't have; an LO with fewer than 2 practice cards or no check item |
| C5 | `requires` naming a module the course doesn't have, or modules that require each other in a circle |
| C6 | a citation not written **Author(s) (year). Title. Venue.** |
| C7 | a Python drill whose canonical code or level-3 answer doesn't parse (`ast`, never run; other languages are reported as not checked) |
| C8 | a `commit` that isn't a commit id; with `--repo NAME=PATH`: a code reference whose file isn't in the repository at its commit, or doesn't define its symbol (a Python, JS or C# function, class, method or assignment). Without it: a note that it wasn't checked |
| C9 | with `--online`: a link that isn't http(s), answers 404 or not at all; a DOI (bare, `doi:` or a doi.org link) doi.org doesn't know. A site that refuses robots (401, 403, 429) is a warning: open it yourself |

`python3 scripts/check-deck.py --repo argus-ui=. --online course.json`. The tests run it on `tests/deck-fixtures/good-course.json` (clean) and `bad-course.json` (each rule broken once).

## Not checked by the script (read it yourself)
- Every term used in the orientation or a prompt has a term card, or is replaced by plain words.
- Feedback and hints say where to look, never judge the person (Hattie & Timperley, 2007).
- An erroneous example (a *Find the bug* card) comes only after the correct version was taught (Große & Renkl, 2007).

## Skills that help (in `.claude/skills/`, CC BY-SA 4.0, see its licence note)
| Rule | Skill |
|---|---|
| R1, R2 | `cognitive-load-analyser` – find what crowds a card |
| R3 | `retrieval-practice-generator`, `hinge-question-designer` – try-first and check questions |
| R4 | `worked-example-fading-designer`, `worked-example-to-problem-solving-transition-designer` |
| Explain cards | `self-explanation-prompt-designer`, `erroneous-example-designer` |
| Hints and feedback | `progressive-hint-ladder`, `feedback-quality-analyser` |
| Rating and calibration | `confidence-calibration-check`, `teach-back-evaluator`, `explain-first-interrogator` |
