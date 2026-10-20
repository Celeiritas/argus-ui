# Mentor – learn the code you build
Mentor turns code you wrote with an AI into practice, so you can read, explain and write it yourself (aiming at Python fluency). Open `<base>/mentor` (**Mentor · Practice** in the section bar). It also still runs plain flashcard decks.

## Why it works this way
Code an AI writes for you skips the part where you build the mental model (the *illusion of competence*: the output works, but you couldn't rebuild or debug it). Mentor puts that effort back where it counts:

| Knowledge | Card | Built on |
|---|---|---|
| **Tier 1 – recurrent skills** (syntax, idioms, patterns) | **Code drill**: a 5–15 line snippet from your project with blanks, faded backwards over three levels | Faded worked examples (Renkl & Atkinson, 2003); 4C/ID (Van Merriënboer & Kirschner, 2018) |
| **Tier 2 – schemas** (why it's built so, what breaks it) | **Explain card**: *Find the bug* (pre-mortem), *Why this design* (trade-off), *Human factors link* | Self-explanation (Chi et al., 1989); testing effect (Roediger & Karpicke, 2006) |
| **Tier 3 – vocabulary** | **Term card**: a sentence with the term blanked; the feedback gives what it does, where it is in your code and the term it's easily confused with | Pre-training (Mayer & Pilegard, 2014); elaborative encoding |

- **Pre-training first.** In a new module, new cards unlock in order: terms → drills → explain cards. Terms take up working memory, so they're learned before the code that uses them.
- **Backward fading and expertise reversal.** Level 1 blanks the endings (return values, a call), level 2 the logic (a condition, a comprehension), level 3 leaves only the signature and docstring. A drill moves up a level when every blank is right and fast (under 15 s at level 1, 30 s at level 2, plus 5 s per extra blank), or right twice in a row at that level; it comes back within a day to try the new level. *Needs work* moves it down. Hints that help a beginner just slow down someone who knows the pattern (Kalyuga et al., 2003).
- **Generate before feedback.** You always type an answer (or choose to show it) before you see the model answer.
- **Interleaving.** When studying everything, each card comes from the module or deck that has waited longest, so you keep working out *which* rule applies (Bjork & Bjork, 2011).
- **Context.** Every code card shows where it lives (`server › sky.py › current()`), and the module's big picture is one click away.

## The loop
1. **Build something** in Claude Code as usual.
2. **Run `/mentor`** (or `/mentor` plus a file or function name). The command reads the latest change, writes one JSON file to the project's `mentor_inbox/` folder, and replies with a single line, so your coding chat stays clean. The command's text is in [`docs/mentor-command.md`](mentor-command.md): copy it to `~/.claude/commands/mentor.md`. Add `mentor_inbox/` to the project's `.gitignore`.
3. **Copy the file to the inbox** on the machine that runs Argus: `~/.local/share/argus-ui/inbox/` (or set `ARGUS_MENTOR_INBOX`). For example: `scp mentor_inbox/*.json <host>:.local/share/argus-ui/inbox/`.
4. **Study.** The module appears the next time Mentor shows a card (no restart). **Code modules** lists every module with its breakdown (big picture, design rules, rules that must hold, human factors link), your progress per tier, and **Study this module**. Files with problems are listed there with the reason; inbox files are read, never moved or deleted. Changing a file re-imports it and keeps your history.

Argus ships one module, **Argus: caching, locks and the Mentor scheduler** (`themes/leafy-realm/decks/argus-code.json`), made from this project's own `sky.py` and `mentor.py`. It doubles as an example of the format.

## How a card works
1. Read the prompt and type: the missing code in each box (levels 1–2), the whole body (level 3; <kbd>Enter</kbd> keeps the indent and adds one after a colon), the missing term, or your explanation. Say how sure you are.
2. Mentor checks it:
   - **Blanks** are compared as code: spacing around symbols, quote style and extra brackets don't matter (`(a)` = `a`). A blank can accept alternatives.
   - **Whole bodies** are parsed with Python's `ast` (never run). Same structure as the model = full marks; otherwise you see both versions, how alike they are, and Python's own syntax error with its line number.
   - **Terms** allow small typos; part of a multi-word term counts as close.
   - **Explanations** use the key-idea rubric (below).
3. You see the full code and *why it's written this way*, then pick how well you knew it (Very well / Well enough / Not well / Needs work, or keys 1–4) and confirm. Each choice shows when the card returns ([FSRS-4.5](https://github.com/open-spaced-repetition/fsrs4anki/wiki/The-Algorithm); internally Easy / Good / Hard / Again, stored as 4–1) and, for drills, the level it comes back at.
4. If Mentor's grade was off, tick **Mentor's grade was wrong**. That flag is training data for the learning grader.

The stats line also tracks **calibration**: how your confidence compares with what you actually got right.

## Grading roadmap
| Stage | Grader | Status |
|---|---|---|
| A | Key-point rubric for explanations (key ideas with accepted wordings; typos and word endings tolerated); code-aware blank matching; `ast` structure match and token similarity for whole bodies | **4.2.0**, code grading **4.7.0** |
| B | Local similarity model adds a meaning-based score (runs on your own machine) | planned |
| Bv2 | A small model trained on *your* saved attempts (features + your ratings + "grade was wrong" flags) predicts grades and coaching hints | planned; data is collected from the first answer |

Every attempt is stored in `~/.local/share/argus-ui/mentor.db` (`attempts` table): answer, confidence, time taken, card kind and drill level, grader features (rubric hits; blanks right; syntax ok, same structure, token similarity), and the suggested and final rating. Older databases gain the new columns on start; nothing is lost.

## Formats
### Code module (what `/mentor` writes)
The full schema is in [`docs/mentor-command.md`](mentor-command.md). In short:
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
Each `{{BLANK_n}}` needs one answer per level, in order; a level that doesn't match is skipped and reported in **Code modules**. `eval_rubric` lines may also be plain sentences (as in the first version of the command); they're graded on their content words, more roughly, and the coach says so. Files in the first draft's shape (`faded_code_drills`, `self_explanation_flashcards`) also import.

### Plain deck
Built-in decks ship in the theme (`themes/<theme>/decks/`). Your own go in `~/.local/share/argus-ui/decks/` and load on restart; editing a deck keeps your history. A code module can also be placed there to ship it with a theme.
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
- Mentor's code: `server/mentor.py` (import, grading, scheduling, levels), `web/js/mentor.js` (the page), `web/css/mentor.css` (added by `mentor.js` itself), `tests/mentor.test.js`.
- The server's Mentor routes are fixed (`decks`, `next`, `stats` to read; `answer`, `rate` to write; POST bodies are at most 4 KB). A drill's blanks travel in `answer` as a JSON list in `text`; modules and inbox status come with `stats`.
- Typed code is only ever parsed (`ast.parse`, `tokenize`), never executed.
