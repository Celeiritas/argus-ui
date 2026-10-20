# Mentor – learn the code you build
Mentor turns code you wrote with an AI into practice (and, from 4.8.0, teaches it first: see [The Learn phase](#the-learn-phase-planned-for-480)), so you can read, explain and write it yourself (aiming at Python fluency). Open `<base>/mentor` (**Mentor · Practice** in the section bar). It also still runs plain flashcard decks.

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

## The Learn phase (planned for 4.8.0)
Status: **spec, not built yet.** Everything above describes 4.7.0; this section is the design for the next version.

Mentor 4.7 tests before it teaches: every card is a test with the lesson on the back. A term card probes a term that was never introduced, a drill opens at level 1 with no worked example, an explain card asks about a failure mode nobody explained, and the only escape is *Show answer*, which costs the card. For someone who vibe-codes, the lesson has to come first, once, and then the tests. This spec adds that phase without touching the Practice half (FSRS, calibration, graders), which is sound.

The research line: pre-train the vocabulary (Mayer & Pilegard, 2014) → study a complete, annotated worked example and self-explain it (Sweller & Cooper, 1985; Chi et al., 1989; Renkl, 2014) → fade backwards into completion problems (Renkl, Atkinson & Große, 2004; already Mentor's levels 1–3) → erroneous examples only after the correct one is secure (Große & Renkl, 2007) → retrieval with graded hints, never the answer handed over (Roediger & Karpicke, 2006; VanLehn, 2011; Koedinger & Aleven, 2007). Fading is visible and reversible (Collins, Brown & Newman, 1989), and the learner's own confidence is checked against reality so AI-written code can't fake competence (Bjork, Dunlosky & Kornell, 2013; Kazemitabaar et al., 2023).

### 1. The Learn phase

A module has two phases. **Learn** runs once per card, in a fixed order, and gates **Practice**, which is the existing FSRS loop.

| Step | Card | What the learner does | Gate to the next step |
|---|---|---|---|
| 0 Orient | **Orientation** (1 per module) | Reads one screen: what the code does in 3 sentences, the files, the terms coming, and *why this module* (the `hci_human_factors_bridge`). Types a one-line "in my words, this code…". | Typed ≥ 5 words (retrieve-first; the text is stored, never graded) |
| 1 Teach terms | **Teach card** (1 per term, before its term card) | Reads definition → anchor in their code → contrast. Then one **spot-it** check: a 2–6 line snippet with the term's instance highlighted-on-answer; the learner clicks or types the line/token where the term appears. | Spot-it right, or wrong once then shown (either way it counts as seen) |
| 2 Worked example | **Level 0** of each drill (1 per drill, before level 1) | Full code with 3–6 numbered annotations revealed one at a time. For each, the learner types *why* that line is there (≥ 3 words) **before** the annotation's `why` appears (Renkl 2014: generation, not reading). After the last one, one self-explanation prompt graded by rubric. | All annotations stepped through and the self-explain answered (any coverage) |
| 3 Pre-read | **Pre-read** (1 per explain card, before it) | The explain card's `key_ideas` as 2–4 short statements, then a **near example**: the same principle in different code, with a one-line "what would break here?" typed before the answer shows. | Typed and shown |
| → Practice | term cards → drills L1–3 → explain cards | Unchanged FSRS loop, now with hints (§2). | — |

**Gate rule.** Within a module, the existing funnel (`terms → drills → explain`) stays, and each practice card additionally requires its own Learn card to be *seen*. `next_card()` therefore orders new cards: orientation → teach_01…n → term_01…n → level0_01…n → drill_01…n (level 1) → preread_01…n → card_01…n. "Everything, mixed" keeps interleaving across modules for *due* cards; *new* Learn cards still come in module order so a lesson isn't split by a review from another module.

**Learn cards are never scheduled by FSRS.** They get a `sched` row with `reps=1`, `due=NULL`, `stability=NULL`: seen, never due. They stay reachable from *Code modules → Read the breakdown* (re-read any time, no rating). Two triggers bring one back into the queue:
- **Stuck** on its practice card (§4) → the Learn card is re-queued once, immediately, as a *refresher* (`attempts.kind='refresh'`), then the practice card returns.
- **Lapse twice** on a practice card (two *Needs work* ratings within 7 days) → same.

Expertise reversal guard (Kalyuga et al., 2003): a teach or level-0 card can be **skipped** with one button, *I know this, test me*, which marks it seen and logs `attempts.skipped=1`. If the practice card then fails, the Learn card is re-queued (the skip was a miscalibration and goes into the calibration stat).

### 2. Hint ladder (practice cards)

Four rungs, in order, on every practice card. The learner picks *Hint* instead of *Show answer*; each rung needs a typed reflection of ≥ 3 words before the next one ("what did that tell you?", Aleven & Koedinger 2002, to stop hint-clicking). Rung 4 is the answer and ends the attempt as a shown card.

| Rung | Name | What it shows | Written by | Cost |
|---|---|---|---|---|
| 1 | Nudge | A question that points at the principle without naming it | `hints[level][0]` | coverage cap 1.0, rating suggestion unchanged |
| 2 | Expert's first move | What an expert scans for first, as one sentence (`expert_move`) | `expert_move` | suggested rating capped at *Well enough* (3) |
| 3 | Near example | The same move in different code, 2–4 lines, answer visible | `hints[level][1]` | suggested rating capped at *Not well* (2); drill can't move up a level this attempt |
| 4 | Answer | The model answer (what *Show answer* does today) | — | counts as a blank answer: coverage 0, suggested *Needs work* (1) |

For drills the ladder is per level (`hints.level_1` etc.); for terms and explain cards a single list. A card with no authored hints still gets rungs 2 and 4 (the module's `expert_move`, or a kind-level default: *"Look at what the function already returns"* for drills, *"Name what it does before you name it"* for terms, *"Start from what can go wrong, then why the code prevents it"* for explain cards).

**Logging.** `attempts.hints` INTEGER = highest rung reached (0–4); `attempts.reflections` TEXT = JSON list of the typed reflections. Both feed the learning grader (the rung reached is a strong feature) and the stats line shows *hints per card* for the week.

### 3. Feedback rules (the coach line after a wrong answer)

Hattie & Timperley (2007): process and self-regulation feedback, never self-level. Narciss (2008): the elaboration matches the error type. Shute (2008): short enough for a novice.

- **≤ 2 sentences.** First: the expert's first move for this card (`expert_move`). Second: one concrete thing to look at in the code shown below. No praise, no "almost", no "good try". A right answer gets one sentence of task feedback and nothing else.
- **Never blame or diagnose the person.** "You wrote `cache`; the function returns `_mem` on every path, so the cached value is `_mem`" — not "you forgot".
- **Name the error class when the grader can tell**: *slip* (a blank right on the other level or in a previous attempt → "Right idea, wrong name: it's `_mem`, you had it last time"), *mistake* (never right → expert move + where to look), *syntax* (level 3 → Python's own message and line, as now).

Templates (`{move}` = `expert_move`, `{look}` = the card's `look_at` or a kind default):

| Kind | Wrong | Right |
|---|---|---|
| term | "{move}. The term is **{term}**: find it in `{anchor}` below." | "Right. Note the look-alike: {contrast, first clause}." |
| drill L1–2 | "{move}. Blank {n}: {look}." | "All {n} blanks right." |
| drill L3 | "{move}. Your version differs at line {k}: {diff summary}." / syntax: as now | "Same structure as the model." |
| explain | "{move}. Missing: *{first missed idea}* — look at {look}." | "All {n} key ideas." |
| teach / level 0 / pre-read | (not graded) spot-it wrong: "It's on line {k}: {why}." | "That's it: {why}." |

The existing calibration lines ("You felt sure but got…") stay and take precedence; they are self-regulation feedback.

### 4. Stuck detection

| Signal | Threshold | Response |
|---|---|---|
| Blank answer submitted (*Show answer* with nothing typed) | once | Offer rung 1 instead of the answer: "Try a hint first?" (one click either way) |
| Idle | 45 s with no keystroke on a drill, 30 s on a term, 90 s on an explain card | Hint button pulses once; no modal, no sound |
| Wrong twice in a row on the same card | 2 attempts within one session | Rung 2 shown automatically with the feedback; the Learn card is re-queued before the next try (§1) |
| Rung 4 reached twice on the same card | 2 | The card is held (`sched.due = now + 1 day`) and its Learn card re-queued; the stats line says "1 card sent back to Learn" |
| *Needs work* twice in 7 days | 2 | Same as above |

Nothing here changes the FSRS rating by itself; the learner still rates. The signals are logged (`attempts.stuck` TEXT: `blank|idle|repeat|held`) for the learning grader.

### 5. Cognitive-load rules for authoring

Sweller (1988, 2019): working memory holds ~4 interacting elements; annotations and prompts must sit *in* the code, not beside it (split attention).

- **Snippets**: 5–15 lines, one function or one block. Strip imports, logging, type noise unless they are the point.
- **Blanks**: level 1 ≤ 2, level 2 ≤ 3, level 3 = 1 (the body). A blank is one token or one expression, never two statements.
- **Annotations (level 0)**: 3–6, each ≤ 25 words, each attached to one line number, in reading order. Annotate the *why*, not the *what* ("holds the lock so a second request can't fetch too" — not "acquires lock").
- **One new term per card.** A teach card introduces its term only; if the anchor line needs a second new term, that term's teach card must come first (`ord`).
- **Pre-train**: every term used in a drill's annotations has a teach card earlier in the module (the command checks this; the importer notes misses in *Code modules*).
- **Self-explanation prompts** ask *why*, not *what*: "Why does `current()` return `_mem` instead of `data` after a failed fetch?" not "What does it return?"
- **Erroneous examples** (pre-mortems) always after the level-0 worked example of the same code (Große & Renkl, 2007): the `preread` is required for a Pre-Mortem card; the importer notes its absence.
- **Hints** never contain the answer token for that blank; rung 3's near example uses different names.

### 6. JSON additions (all optional; old modules import unchanged)

```json
{
  "cta_summary": {
    "…existing four…": "…",
    "orientation": "3 sentences max, plain words: what this code does, in which files, and what you'll be able to do after",
    "expert_move": "Module-level default: the first thing an expert looks at in this code"
  },
  "tier_3_terminology_cards": [{
    "…existing…": "…",
    "teach_order": 1,
    "spot_it": {"snippet": "with _lock:\n    if _mem.get('at', 0) > time.time() - TTL:\n        return _mem", "line": 1, "why": "the `with` statement is the context manager in use"},
    "expert_move": "Look for `with …:` — whatever follows is a context manager",
    "hints": ["What keyword starts the block the lock lives in?", "Near example: `with open(p) as f:` — `open(p)` is one of these too"]
  }],
  "tier_1_faded_code_drills": [{
    "…existing…": "…",
    "level_0_worked": {
      "annotations": [{"line": 3, "note": "Takes the lock first", "why": "Two browser tabs could ask at once; only one may fetch and write _mem"}],
      "self_explain": {"prompt": "Why return _mem and not data after a failed fetch?", "rubric": [{"idea": "keeps the last good reading", "any": ["last", "old", "previous", "stale"]}]}
    },
    "expert_move": "Scan the return statements: whatever every path returns is the cache",
    "look_at": {"level_1": ["the last line of the function", "what fetch() hands back"], "level_2": ["…"], "level_3": ["…"]},
    "hints": {
      "level_1": ["Nudge question", "Near example, 2–4 lines, different names"],
      "level_2": ["…", "…"],
      "level_3": ["…", "…"]
    }
  }],
  "tier_2_self_explanation_cards": [{
    "…existing…": "…",
    "preread": {
      "key_ideas": ["A file is written in pieces; a crash leaves part of it", "Write to a temp file, then rename: rename is one step"],
      "near_example": {"code": "f = open(LOG, 'w'); f.write(big)   # power cut here", "ask": "What does the next start find?", "answer": "A truncated LOG that may not parse"}
    },
    "expert_move": "Ask: at which line could the process die, and what is on disk at that moment?",
    "hints": ["Where could the process stop between opening and closing the file?", "Near example: an editor's '.swp' file is the same trick"]
  }]
}
```

**Learn cards for modules without these fields.** The importer derives a plainer Learn phase from what every module already has, so the shipped module and any older inbox file get one without being regenerated: an orientation from `schematic_mental_model`; a teach card per term from `concise_definition`, `project_anchor` and `contrast_anchor` (no spot-it check, so it is read-and-confirm); a level 0 per drill from `full_canonical_code` with `python_fluency_note` and `context_comment` as one annotation; a pre-read per explain card from the rubric's `idea` lines. The authored fields, when present, replace these. Plain decks get no Learn phase (their cards are already self-contained).

Names follow the existing style (`snake_case`, `*_prompt`, `eval_rubric`-style `{idea, any}` lists). `spot_it.line` is 1-based within `snippet`. `hints` lists are 1–2 strings (rungs 1 and 3); rung 2 is `expert_move`, rung 4 is the answer. Card-level `expert_move` falls back to the module's, then the kind default.

### 7. Changes to the `/mentor` command

Add to `docs/mentor-command.md`:

- **§3 Extraction**, new tier 0: *"Pre-training & worked examples. For every term, write a `spot_it` snippet (2–6 lines from the same code, `line` = where the term's instance is) and a `teach_order` so no term's anchor uses a term taught later. For every drill, write `level_0_worked`: 3–6 annotations (`line`, `note` ≤ 8 words, `why` ≤ 25 words) that explain *why* the line exists, plus one `self_explain` prompt that asks why, with a 1–3 idea rubric. For every explain card, write `preread.key_ideas` (2–4 statements the card's rubric assumes) and a `near_example` in different code. For every card and the module, write `expert_move`: the first thing an expert looks at, one sentence, no answer tokens. For every drill level and every term/explain card write `hints`: [a question that points at the principle, a 2–4 line near example with different names]."*
- **§5 Authoring rules** = §5 above, verbatim as a checklist the command runs before writing the file; a module that breaks a rule is still written, with a `"lint": ["…"]` list in `metadata` so *Code modules* shows the misses.
- **Reply line** unchanged (one line), plus the count of Learn cards: `Mentor: weather_cache → 8 terms, 4 drills, 5 explain cards (+17 learn cards)`.

### 8. UI flow

**Where Learn lives.** No new view. The Practice panel shows the card the server sends; Learn cards are kinds like any other. Two additions:
- Stats line: `3 to learn · 0 due · 51 new · …` (`stats.learn` = unseen Learn cards in the selection). The *Study* picker's module entries get a suffix while learning: `argus-ui: Argus… (learning 3/17)`.
- *Code modules*: the breakdown shows the orientation and each Learn card as a re-readable list (*Teach: context manager*, *Worked example: current()*, *Pre-read: find the bug*), each a 44px row that opens it read-only.

**States per card** (one `<form class="panel">`, as now; the `kind` line names the state):

| Kind | Screen | Keyboard | Primary button |
|---|---|---|---|
| orientation | Module name; orientation text (16px); files; terms as a plain list; one textarea "In my words, this code…" | Ctrl+Enter | *Start learning* |
| teach | `Teach · <category>`; the term as `<h3>`; three labelled blocks *What it does / In your code / Not to be confused with*; then the spot-it snippet with clickable lines (`<button class="line">`) and a text box alternative "or type the line number" | ↑/↓ moves between lines, Enter picks; or type a number + Enter | *That's the line* → feedback → *Next* ; secondary *I know this, test me* |
| level0 (drill) | `Worked example · <breadcrumb>`; full code; annotation *k of n* shown as a callout attached to its line (the line is highlighted, the callout sits directly under it to avoid split attention); a one-line input "Why is this line here?"; after typing, the `why` appears under it; *Next annotation*. After the last: the self-explain prompt with a textarea, graded by rubric, feedback shown, no rating | Enter in the one-liner reveals and advances; Ctrl+Enter checks the self-explain | *Reveal* / *Next annotation* / *Check* / *Next* |
| preread | `Before the bug hunt · <breadcrumb>`; key ideas as 2–4 `<li>`; the near example code; a one-line "What would break here?"; Enter reveals the answer | Enter | *Reveal* → *Next* |
| practice (all kinds) | As now, plus a *Hint* button (secondary) beside *Check answer*; pressing it opens the rung in a callout under the prompt with a ≥ 3-word reflection box and *Next hint*; after rung 3 the button reads *Show answer* | Alt+H opens the next rung; keys 1–4 still rate | *Check answer* |

Learn cards have **no** confidence radios and **no** rating: finishing one calls `rate` with `rating=0` (new value: *seen*), which the server stores as `reps=1, due=NULL`. Rules kept: 16/14/12 px, 400/600, 44 px rows and buttons, verb-first labels, visible focus, 375 px with no sideways scroll (the annotation callout wraps under the code, never beside it), `prefers-reduced-motion` (callouts fade only).

**Routes stay fixed.** `next` returns Learn kinds (`orientation|teach|level0|preread`) in the same payload shape (`prompt`, `data`, `kind`); `answer` accepts the spot-it line number, the annotation reflections (as a JSON list in `text`, like drill blanks) and the self-explain text; `rate` accepts `rating: 0`. `answer` also accepts `{"card": …, "hint": k, "text": "<reflection>"}` to log a rung without grading (returns the rung's content), so hints never need a new route. POST bodies stay under 4 KB (reflections are capped at 300 chars each).

### 9. Worked example (argus-code module)

**Teach card: context manager**
- What it does: An object used with `with` that runs setup on entry and cleanup on exit, even after an error.
- In your code: `sky.py → current()`: `with _lock:` — the lock is acquired on entry and released on exit.
- Not to be confused with: a hand-written `try/finally`. Same effect, but the cleanup lives in the object, so you can't forget it.
- Spot it (click the line that uses a context manager):
  ```
  1  def current(loc):
  2      with _lock:
  3          if _mem.get('at', 0) > time.time() - TTL:
  4              return _mem
  ```
  Answer: line 2. Why: "`with _lock:` — the lock is the context manager; the block under it is what runs while it's held."
- expert_move: "Look for `with …:`; whatever follows `with` is a context manager."

**drill_01 at level 0** (`current()`, the full code as in the module)
| # | Line | Note | Why (shown after the learner types) |
|---|---|---|---|
| 1 | `with _lock:` | Takes the lock first | Two requests can arrive at once; only one may fetch and write `_mem`. The `with` releases it even if `fetch()` raises. |
| 2 | `if _mem.get('at', 0) > time.time() - TTL:` | Is the cache fresh? | `.get('at', 0)` gives 0 on the very first call instead of a `KeyError`; `time.time() - TTL` is "TTL seconds ago". |
| 3 | `return _mem` | Serve from memory | Nothing is fetched; the dict already holds the last reading. |
| 4 | `_mem.clear(); _mem.update(data)` | Replace, don't rebind | `_mem = data` would make a new dict that other code doesn't see; clearing and updating keeps the one shared object. |
| 5 | `except Exception: _mem['stale'] = True` | Never raise | The page must always get *something*; a failed fetch keeps the old reading and flags it. |
| 6 | `return _mem` (last line) | Every path returns `_mem` | Fresh, refetched or stale, the caller always gets the same dict. |
Self-explain: "Why does `current()` return `_mem` rather than `data` after the `try`?" Rubric: *every path returns the same dict* (any: "same", "every path", "both", "always `_mem`"); *a failed fetch keeps the old reading* (any: "old", "last", "previous", "stale", "fail").

**Pre-read for card_01** (atomic write pre-mortem)
- Key ideas: (1) A file is written in pieces; the process can die between pieces. (2) A half-written JSON file doesn't parse, so the next start has nothing. (3) Write to a temporary file, then `os.replace()` it over the real one — the replace is one step, so the real file is always whole.
- Near example: `f = open(LOG, 'w'); f.write(big)   # power cut here` — "What does the next start find?" → "A truncated LOG: the bytes written so far, which may stop mid-line."
- expert_move: "Ask: at which line could the process die, and what is on disk at that moment?"

**Hint ladder for drill_01, level 1** (blanks: `return ___` and `_mem.update(___)`)
1. Nudge: "Every branch of this function hands back the same thing. Which name appears on the last line?"
2. Expert's first move: "Scan the `return` statements first: whatever every path returns is the cache."
3. Near example:
   ```
   def read(key):
       if key in _seen:
           return _seen
       _seen.update(load(key))
       return _seen
   ```
   "Same shape: the dict that's returned is the one that's updated."
4. Answer: `_mem`, `data`.

### 10. Migration and tests

**DB.** Append to `ADDED`: `('attempts','hints','INTEGER DEFAULT 0')`, `('attempts','reflections','TEXT')`, `('attempts','stuck','TEXT')`, `('attempts','skipped','INTEGER DEFAULT 0')`, `('cards','learn_of','TEXT')` (the practice card a Learn card gates; NULL for practice cards). `sched.due` becomes nullable-by-convention for Learn cards (`reps=1, due=NULL`); `stats.new` must exclude Learn cards and report them as `stats.learn`. `rate` accepts `rating=0` only for Learn kinds. `FUNNEL` gains `orientation: -1, teach: 0, level0: 1, preread: 2` with the extra rule "a practice card is new-eligible only when its `learn_of` partner has `reps>0`".

**`tests/mentor.test.js`** adds:
- a new module starts with its orientation card; typing < 5 words keeps *Start learning* disabled; 5 words enables it
- the first teach card precedes its term card; clicking the wrong spot-it line shows the `why` and still advances; *I know this, test me* skips and logs `skipped=1`
- level 0 reveals annotation 1 only; the `why` is hidden until ≥ 3 words are typed; after annotation n the self-explain appears and is graded by rubric; no rating radios are shown
- a drill at level 1 is not offered until its level 0 is seen; an explain card not until its pre-read is seen
- *Hint* on a drill shows rung 1; *Next hint* is disabled until 3 words are typed; rung 2 caps the suggested rating at 3; rung 4 marks the attempt as shown with coverage 0; `attempts.hints` records the highest rung
- blank *Show answer* first offers a hint; two wrong answers in a row re-queue the Learn card before the next try; the toast says so
- stats line shows `N to learn`; *Code modules* lists the Learn cards and opens one read-only
- an old module JSON (no Learn fields) still imports, gets derived Learn cards (orientation, read-and-confirm teach cards, one-annotation level 0, rubric pre-reads), and uses kind defaults for rungs 2 and 4
- 375 px: the annotation callout sits under the code line, no sideways scroll

## Notes for changing it
- Mentor's code: `server/mentor.py` (import, grading, scheduling, levels), `web/js/mentor.js` (the page), `web/css/mentor.css` (added by `mentor.js` itself), `tests/mentor.test.js`.
- The server's Mentor routes are fixed (`decks`, `next`, `stats` to read; `answer`, `rate` to write; POST bodies are at most 4 KB). A drill's blanks travel in `answer` as a JSON list in `text`; modules and inbox status come with `stats`.
- Typed code is only ever parsed (`ast.parse`, `tokenize`), never executed.
