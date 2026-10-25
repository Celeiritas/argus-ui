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
