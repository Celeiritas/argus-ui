# Mentor – learn the code you build
Mentor turns code you wrote with an AI into practice, so you can read, explain and write it yourself (aiming at Python fluency). Open `<base>/mentor` (**Mentor · Practice** in the section bar). It also still runs plain flashcard decks.

## Why it works this way
Code an AI writes for you skips the part where you build the mental model (the *illusion of competence*: the output works, but you couldn't rebuild or debug it). Mentor puts that effort back where it counts:

| Knowledge | Card | Built on |
|---|---|---|
| **Tier 1 – recurrent skills** (syntax, idioms, patterns) | **Code drill**: a 5–15 line snippet from your project with blanks, faded backwards over three levels | Faded worked examples (Renkl & Atkinson, 2003); 4C/ID (Van Merriënboer & Kirschner, 2018) |
| **Tier 2 – schemas** (why it's built so, what breaks it) | **Explain card**: *Find the bug* (pre-mortem), *Why this design* (trade-off), *Human factors link* | Self-explanation (Chi et al., 1989); testing effect (Roediger & Karpicke, 2006) |
| **Tier 3 – vocabulary** | **Term card**: a sentence with the term blanked; the feedback gives what it does, where it is in your code and the term it's easily confused with | Pre-training (Mayer & Pilegard, 2014); elaborative encoding |
| **Learn first** (4.8.0) | **Learn cards** in front of each practice card: an *orientation* for the lesson, a *teach card* per term (ending in "spot it in this snippet"), a *worked example* per drill (the full code, annotated line by line; you say why a line is there before the note appears, then explain the whole), a *pre-read* per explain card (the ideas it rests on, and a near example). A teach card or pre-read with a `try_first` question (4.24.0) asks it first: you type a guess, never graded or stored, then the explanation appears under it. Read once, never scheduled; they come back only when you are stuck | Worked examples before problems (Sweller & Cooper, 1985; Renkl, 2014); self-explanation (Chi et al., 1989); erroneous examples only after the correct one (Große & Renkl, 2007); pretesting (Richland, Kornell & Kao, 2009) |

- **Teach before test.** In a new lesson, cards unlock in order: orientation → teach cards → terms → worked examples → drills → pre-reads → explain cards. Each practice card also waits for its own Learn card. Terms take up working memory, so they're learned before the code that uses them. A teach card or worked example can be skipped with *I know this, test me*; if the practice card then goes wrong, the skipped card comes back (Kalyuga et al., 2003).
- **Hints before answers.** Every practice card has a four-rung hint ladder: a *nudge*, *the expert's first move* (what an expert scans for), a *near example* in different code, and the answer. Each rung needs a three-word reflection before the next (Aleven & Koedinger, 2002) and caps the rating Mentor suggests (rung 2: at most *Well enough*; rung 3: at most *Not well*, and a drill can't move up); the answer counts as a blank. A blank *Show answer* offers a hint first. The rung reached is stored with the attempt.
- **Stuck detection.** Wrong twice in a row on a card, a skipped Learn card whose practice card then fails, the answer shown twice, or *Needs work* twice in a week: the card's Learn card comes back before the next try (and in the last two cases the card is held for a day). The stats line counts cards sent back today. The Hint button pulses after 30–90 s without typing (never a modal, never a sound).
- **Feedback that says where to look.** After a wrong answer the coach line is at most two sentences: the result, then the expert's first move and one place to look in the code. A slip (right before, wrong now) is named as one. Never about the person (Hattie & Timperley, 2007).
- **Backward fading and expertise reversal.** Level 1 blanks the endings (return values, a call), level 2 the logic (a condition, a comprehension), level 3 leaves only the signature and docstring. A drill moves up a level when every blank is right and fast (under 15 s at level 1, 30 s at level 2, plus 5 s per extra blank), or right twice in a row at that level; it comes back within a day to try the new level. *Needs work* moves it down. Hints that help a beginner just slow down someone who knows the pattern (Kalyuga et al., 2003).
- **Generate before feedback.** You always type an answer (or choose to show it) before you see the model answer.
- **Interleaving.** When studying everything, each card comes from the lesson or deck that has waited longest, so you keep working out *which* rule applies (Bjork & Bjork, 2011).
- **Context.** Every code card shows where it lives (`server › sky.py › current()`), and the lesson's big picture is one click away.

## The loop
1. **Build something** in Claude Code as usual.
2. **Run `/mentor`** (or `/mentor` plus a file or function name). The command reads the latest change, writes one JSON file to the project's `mentor_inbox/` folder, and replies with a single line, so your coding chat stays clean. The command's text is in [`docs/mentor-command.md`](mentor-command.md): copy it to `~/.claude/commands/mentor.md`. Add `mentor_inbox/` to the project's `.gitignore`.
3. **Copy the file to the inbox** on the machine that runs Argus: `~/.local/share/argus-ui/inbox/` (or set `ARGUS_MENTOR_INBOX`). For example: `scp mentor_inbox/*.json <host>:.local/share/argus-ui/inbox/`.
4. **Study.** The lesson appears the next time Mentor shows a card (no restart). **Lessons** lists every lesson with its breakdown (big picture, design rules, rules that must hold, human factors link), your progress per tier, every Learn card to read again, any notes the `/mentor` command left about its own output, and **Study this lesson**. Files with problems are listed there with the reason; inbox files are read, never moved or deleted. Changing a file re-imports it and keeps your history.

Argus ships one lesson, **Argus: caching, locks and the Mentor scheduler** (`themes/leafy-realm/decks/argus-code.json`), made from this project's own `sky.py` and `mentor.py`. It doubles as an example of the format, Learn fields included. A lesson needs no drills: terms and explain cards alone import and run, and a spot-it snippet can be a terminal transcript rather than code. Anything that names your machines, paths or hosts belongs in your private inbox or decks folder, not in a theme: themes ship with the repository.

**How a card should read** (4.24.0): every lesson and deck follows the [deck rubric](mentor-rubric.md): no file paths or repo words in what you read, one idea per card, a question before each explanation, a worked example before the fades, plain words with every term defined once. `python3 scripts/check-deck.py <file or folder>` checks a lesson before it goes in the inbox; the tests run it on the decks that ship.

## The study screen and the Lessons page (4.25.0)
- **No greyed-out buttons.** Every button works; if something is missing (a guess, a picked line, three words of *why*), a line under the field says what, and focus goes there.
- **Lines wrap.** Code and spot-it snippets wrap long lines and keep their indentation; nothing scrolls sideways. The box you write a whole function body in still doesn't wrap.
- **One lesson chosen:** the header shows how many of its lesson cards you've read.
- **End of a session:** "This session: 12 cards answered, 9 right", and **Replay your 3 mistakes** asks those cards again (`next?replay=<card id>` serves a practice card without its answer).
- **Lessons** is a course map: one *Continue where you left off*, the reviews due, then each project's lessons as one framed list. A row has the name, one line, how much is practised and one action (Start, Continue, Review); *About this lesson* and *Read the lesson again* open under it; each project's sources are one list behind *Where these lessons come from*. Calibration, the local AI line and how to add a lesson are under *About Mentor and adding a lesson*.

## Menus and submenus (4.22.0)
A lesson's `metadata.project` names where it sits in the Study picker. A plain project (`Sound-Haptics-Lab`) puts the lesson under **Lessons** as "project: name". A project with the separator ` › ` (space, U+203A, space), such as `GAME_RESEARCH › Topics`, puts it in its own submenu; the picker offers **Study all** for that submenu and **Study all of GAME_RESEARCH** for the whole menu. Group choices travel as `group:<project>` (`next?deck=group:GAME_RESEARCH`) and take every lesson whose project is that name or lies under it.

## Placeholders: your machines, never in a lesson
A lesson is meant to move between people (and to sit in a public repository), so it never names a real machine, path or account. It says `{{SERVER}}` instead, and Mentor fills that in every time it shows a card, from `~/.config/leafy/realm.json` on the machine that runs it (yours alone; never commit it). Every field a card shows is filled: prompts, answers, hints, snippets, the Lessons view. Grading compares your answer against the filled-in text, so you type your server's real name. The database keeps the `{{…}}` form, so editing `realm.json` takes effect on the next card, with no restart and no re-import.

| Placeholder | Means | Default (no `realm.json`) |
|---|---|---|
| `{{SERVER}}` | the always-on machine that runs Argus | `homeserver` |
| `{{PC}}` | the computer you code on | `desktop` |
| `{{PHONE}}` | your phone | `phone` |
| `{{SSH}}` | the ssh name of the server (`ssh {{SSH}}`) | `server` |
| `{{HOME_PC}}` | your home folder on the PC | `C:\Users\you` |
| `{{HOME_SERVER}}` | your home folder on the server | `~` |
| `{{REPO_URL}}` | your clone's URL | `https://github.com/you/argus-ui` |

Copy [`realm.example.json`](realm.example.json) to `~/.config/leafy/realm.json` and change the values; keys you leave out keep their default, and key case doesn't matter. A missing or broken file means the defaults (`LEAFY_REALM` points Mentor at another file). Unknown `{{NAMES}}` and `{{BLANK_n}}` are left alone. `scripts/check-private.sh` stops a push that names a real home path, host, address or email (see `CLAUDE.md`).

## How a card works
1. Read the prompt and type: the missing code in each box (levels 1–2), the whole body (level 3; <kbd>Enter</kbd> keeps the indent and adds one after a colon), the missing term, or your explanation. Say how sure you are.
2. Mentor checks it:
   - **Blanks** are compared as code: spacing around symbols, quote style and extra brackets don't matter (`(a)` = `a`). A blank can accept alternatives.
   - **Whole bodies** are parsed with Python's `ast` (never run). Same structure as the model = full marks; otherwise you see both versions, how alike they are, and Python's own syntax error with its line number.
   - **Terms** allow small typos; part of a multi-word term counts as close.
   - **Explanations** use the key-idea rubric (below).
3. The result comes in one band under the question, the same place every time: **Correct** (green, a tick), **Partly right** (amber, a minus), **Not quite** (red, a cross) or **Answer shown**, always with the word and the icon, never colour alone, and the coach line saying why or where to look. Key ideas are marked "✓ Got it" / "✕ Missing"; a long model answer shows its first paragraph, with the rest (evidence, notes, sources) behind *Show the full answer and sources*. Then pick how well you knew it, in Anki's order: **1 Again · 2 Hard · 3 Good · 4 Easy**, each showing when the card comes back (keys 1–4, Enter saves; a Learn card has no rating: *Next card* marks it read). If Mentor's grade was off, *Report a grading problem* holds the "grade was wrong" flag ([FSRS-4.5](https://github.com/open-spaced-repetition/fsrs4anki/wiki/The-Algorithm); stored as 1–4).
4. If Mentor's grade was off, tick **Mentor's grade was wrong**. That flag is training data for the learning grader.

The stats line also tracks **calibration**: how your confidence compares with what you actually got right.

## Grading roadmap
| Stage | Grader | Status |
|---|---|---|
| A | Key-point rubric for explanations (key ideas with accepted wordings; typos and word endings tolerated); code-aware blank matching; `ast` structure match and token similarity for whole bodies | **4.2.0**, code grading **4.7.0** |
| B | Local similarity model adds a meaning-based score (runs on your own machine) | planned |
| Bv2 | A small model trained on *your* saved attempts (features + your ratings + "grade was wrong" flags) predicts grades and coaching hints | planned; data is collected from the first answer |

Every attempt is stored in `~/.local/share/argus-ui/mentor.db` (`attempts` table): answer, confidence, time taken, card kind and drill level, grader features (rubric hits; blanks right; syntax ok, same structure, token similarity), the highest hint rung reached and the reflections typed, the stuck signal if any, whether a Learn card was skipped, and the suggested and final rating. Older databases gain the new columns on start; nothing is lost.

## Formats
### Lesson (what `/mentor` writes)
The full schema is in [`docs/mentor-command.md`](mentor-command.md). In short (the Learn fields are in the section below):
```json
{
  "metadata": {"timestamp": "2026-10-20T14:22:33", "module_name": "weather_cache", "project": "argus-ui",
               "source_files": ["server/sky.py"], "concepts_covered": ["context managers"]},
  "cta_summary": {"schematic_mental_model": "…", "design_rules_heuristics": "…",
                  "hard_rules_invariants": "…", "hci_human_factors_bridge": "…"},
  "tier_1_faded_code_drills": [{"id": "drill_01", "file_breadcrumb": "server -> sky.py -> current()",
      "context_comment": "…", "full_canonical_code": "…",
      "level_1_fade": "… return {{BLANK_1}} …", "level_2_fade": "…", "level_3_fade": "def f(x):\n    \"\"\"…\"\"\"\n    {{BLANK_1}}",
      "answers": {"level_1": ["_mem"], "level_2": ["…"], "level_3": ["body, indented relative to the blank's line"]},
      "python_fluency_note": "…"}],
  "tier_2_self_explanation_cards": [{"id": "card_01", "card_type": "Pre-Mortem", "file_breadcrumb": "…",
      "front_prompt": "… code may go in ``` fences …", "back_explanation": "…",
      "eval_rubric": [{"idea": "a crash leaves a half-written file", "any": ["half", "partial", "truncated"]}]}],
  "tier_3_terminology_cards": [{"id": "term_01", "term": "context manager", "category": "Python Syntax",
      "concise_definition": "…", "project_anchor": "sky.py -> current(): `with _lock:`",
      "contrast_anchor": "Unlike …", "cloze_prompt": "`with _lock:` uses the lock as a {{BLANK}} …"}]
}
```
Each `{{BLANK_n}}` needs one answer per level, in order; a level that doesn't match is skipped and reported in **Lessons**. `eval_rubric` lines may also be plain sentences (as in the first version of the command); they're graded on their content words, more roughly, and the coach says so. Files in the first draft's shape (`faded_code_drills`, `self_explanation_flashcards`) also import.

### Plain deck
Built-in decks ship in the theme (`themes/<theme>/decks/`). Your own go in `~/.local/share/argus-ui/decks/` and load on restart; editing a deck keeps your history. A lesson can also be placed there to ship it with a theme. Plain decks have no Learn phase (their cards are self-contained) but do get the hint ladder (the expert's move and the answer).
```json
{
  "id": "ux-hci", "name": "UX & HCI terms", "blurb": "One line about the deck",
  "cards": [
    {"id": "fitts", "prompt": "Define: Fitts's law",
     "answer": "The model answer shown after you try.",
     "points": [
       {"idea": "time to point at a target", "any": ["time", "point", "acquire", "fast"]},
       {"idea": "increases with distance",   "any": ["distance", "far", "close"]},
       {"idea": "decreases with target size", "any": ["size", "bigger", "width"], "weight": 1}
     ]}
  ]
}
```
A key idea counts as covered when **all** words of **any** of its phrases appear in the answer (common words ignored, endings like -s/-ing/-ed ignored, small typos allowed). `weight` defaults to 1.

## Notes for changing it
- Mentor's code is a bundled server plugin (`docs/leafy-plugin.md`), `plugins/mentor/`: `mentor.py` (import with derived Learn cards, grading, the hint ladder, stuck detection, scheduling, levels), `plugin.py` (the door: `api/mentor/...` and Home's `status` line, one request at a time on the database), `page.js` (the page), `page.css`, `plugin.json` (`"agent": true`). Tests: `tests/mentor.test.js`, and `tests/bundled.test.js` for the plugin side.
- A local AI can add a meaning score and feedback, off by default and never used for the rating yet: `docs/mentor-ai.md`. `python plugins/mentor/mentor.py export` writes your rated attempts as JSON lines for a grader that learns from you.
- Your data did not move: the database is still `~/.local/share/argus-ui/mentor.db` (or `ARGUS_MENTOR_DB`), the inbox `~/.local/share/argus-ui/inbox`, your decks `~/.local/share/argus-ui/decks`. To try a changed Mentor without a deploy, copy `plugins/mentor/` to `~/.config/argus-ui/plugins/mentor/` and restart Elaia: your copy wins over the bundled one.
- The server's Mentor routes are fixed (`decks`, `next`, `stats` to read; `answer`, `rate` to write; POST bodies are at most 4 KB). A drill's blanks travel in `answer` as a JSON list in `text`; a worked example's reflections and self-explanation as a JSON object; `answer` with `hint: k` returns rung k without writing an attempt, and the final answer carries `hints` (highest rung) and `reflections`; `rate` with `rating: 0` marks a Learn card read; `next?card=<id>` returns one Learn card to read again. Lessons and inbox status come with `stats`.
- Typed code is only ever parsed (`ast.parse`, `tokenize`), never executed.
