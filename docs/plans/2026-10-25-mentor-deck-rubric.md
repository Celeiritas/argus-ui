# Mentor deck rubric – implementation plan

**Goal:** Mentor's cards teach in plain words: no file paths or repo jargon in what the learner reads, one idea per card, a question before each explanation, a worked example before faded practice, every term defined once.

**Architecture:** A written rubric (`docs/mentor-rubric.md`) plus a stdlib checker (`scripts/check-deck.py`) that tests the mechanical parts and runs in `tests/run.sh`. Two page changes decided by the owner: cards show only the function name where they used to show a file path, and an optional `try_first` question on teach cards and pre-reads. The shipped decks are rewritten to pass. Twelve CC BY-SA education skills are copied into `.claude/skills/` for the sessions that write decks.

**Tech stack:** Python 3 stdlib, the page's plain JS, Playwright tests (Linux / CI only).

**Spec:** hub inbox request 2026-10-25 (`hub\inbox\argus-ui.md`) and the owner's answers in `argus-ui-2026-10-25.md` (handoff).

## Global constraints
- Owner decisions 2026-10-25: cards show the function name only (`current()`), the file list stays in the Lessons view; `try_first` is optional, a typed guess, not graded, not scheduled; GAME_RESEARCH lessons are fixed by their owner, not here.
- Skills copied unchanged, with `LICENSE` notice: CC BY-SA 4.0, © 2026 Gareth Manning, github.com/GarethManning/education-agent-skills, "copied unchanged".
- UI rules (CLAUDE.md): 16/14/12px type, 44px hit areas, verb-first labels, visible focus, keyboard path, no horizontal scroll at 375px.
- `VERSION` 4.24.0 and a `CHANGELOG.md` entry; `bash scripts/check-private.sh` clean before push.

## Review focus
1. A lesson without `try_first` must behave exactly as before (most existing lessons, including GAME_RESEARCH). Test: the second teach card of argus-code has no `try_first` and opens straight on the explanation.
2. Read-only Learn cards (Lessons → read again) show the try-first question as text, with no input step. Test in the read-only check.
3. Breadcrumbs written with `->`, `→` or `›`, or with no separator, all reduce to their last part. Test: drill crumb text is `current()`.
4. The checker must not flag code fields (snippets, canonical code, fades, near-example code): code may name files. Fixture includes a file name inside `full_canonical_code` that is not reported.
5. Old-shape lessons (`faded_code_drills`, `self_explanation_flashcards`) and plain decks still pass through the checker without crashing.

---

### Task 1: Copy the 12 education skills
**Files:** create `.claude/skills/<name>/SKILL.md` ×12 (cognitive-load-analyser, retrieval-practice-generator, worked-example-fading-designer, worked-example-to-problem-solving-transition-designer, self-explanation-prompt-designer, erroneous-example-designer, hinge-question-designer, progressive-hint-ladder, teach-back-evaluator, explain-first-interrogator, confidence-calibration-check, feedback-quality-analyser); `.claude/skills/LICENSE-education-skills.md`.
- [ ] Copy byte for byte from the synced pack; compare SHA-256 of each source and copy.
- [ ] `bash scripts/check-private.sh --tree` clean.
- [ ] Commit.

### Task 2: Rubric and checker
**Files:** create `docs/mentor-rubric.md`, `scripts/check-deck.py`, `tests/deck-fixtures/bad-lesson.json`, `tests/deck-fixtures/good-lesson.json`; modify `tests/run.sh`.

**Interface:** `python3 scripts/check-deck.py PATH...` (files or folders of `*.json`). Prints `file: card-id: R<n> message` per finding, `ERROR` or `WARN`; exit 1 if any ERROR.

Rules (learner-facing fields only; code fields skipped: `full_canonical_code`, `level_*_fade`, `answers`, `snippet`, `near_example.code`):
- R1 ERROR file paths: a word ending in a source-file extension (`.py .js .css .json .sh .md .html .ts .yml .yaml .toml`) or a `dir/file` path; also in `file_breadcrumb` (only the last part may remain: a function or name, no extension).
- R1 WARN repo jargon (a git lesson may need these words): `repo`, `PR #`, `pull request`, `commit`, `handoff`, `CLAUDE.md`, `worktree`, `TODO` (whole words, case-insensitive).
- R2 WARN one idea: definitions over 30 words, explanations / answers over 80 words, key ideas over 3 per pre-read.
- R3 WARN question first: a teach card (term) or pre-read without `try_first`.
- R4 ERROR worked example first: a drill without `level_0_worked` annotations or without `level_1_fade`.
- R5 ERROR define once: a term listed twice, or a term without `concise_definition`.
- [ ] Write the fixtures: `bad-lesson.json` triggers each rule once (and has `server/sky.py` inside `full_canonical_code`, which must not be reported); `good-lesson.json` passes clean.
- [ ] Add to `tests/run.sh` before the browser run: bad fixture exits 1 and reports R1–R5; good fixture and `themes/*/decks` exit 0.
- [ ] Write the checker; run on fixtures locally (`python scripts/check-deck.py ...`); expect the bad fixture to list R1–R5 and nothing for the code field.
- [ ] `docs/mentor-rubric.md`: the five rules in plain words with a bad/better example each, which of the 12 skills helps with which rule, and how to run the checker. Link it from `docs/mentor.md` and `docs/mentor-command.md` (so `/mentor` writes to it, including `try_first`).
- [ ] Commit.

### Task 3: `try_first` on teach cards and pre-reads
**Files:** modify `plugins/mentor/mentor.py` (`import_module`, `card_payload`), `plugins/mentor/page.js` (`learnCard`, `wireLearn`), `plugins/mentor/page.css` if needed, `docs/mentor.md` (Learn fields), `tests/mentor.test.js`.

**Interface:** lesson field `"try_first": "<question>"` on a `tier_3_terminology_cards` entry (its teach card) and inside `preread`. Stored as `data['try']`; `card_payload` returns `try` for `teach` and `preread`.

Page: when `c.try` and not read-only, the card first shows the head, the term or title, a "Try first" label with the question, a textarea `#guess` and a button `#tryBtn` "Show the explanation" (enabled once the guess has a word; <kbd>Ctrl</kbd>+<kbd>Enter</kbd> submits). Then the usual card renders with a callout "Your guess: …" above it. Nothing is sent to the server for the guess. Read-only: the question shows as text, no input.
- [ ] Test (mentor.test.js, at the first teach card): `#guess` and `#tryBtn` show, the definition is not yet on the page; after a guess the definition and "Your guess" show. Second teach card (no `try_first`) opens on the definition. Read-only teach card shows the question text and no `#guess`.
- [ ] Implement; `python -c "import ast,sys; ast.parse(open('plugins/mentor/mentor.py').read())"` and `node --check plugins/mentor/page.js` pass locally.
- [ ] Commit.

### Task 4: Function name only on cards
**Files:** modify `plugins/mentor/page.js` (`crumb`, orientation body), `tests/mentor.test.js`.
- [ ] `crumb(s)` shows only the last part of the breadcrumb (split on `->`, `→`, `›`), screen-reader label "Where in the code:" kept. Orientation drops its "Files:" line; Lessons view keeps `m.files`.
- [ ] Test: on the first drill `.crumb` text is `current()`; the orientation has no "Files:".
- [ ] Commit.

### Task 5: Rewrite the shipped decks
**Files:** `themes/leafy-realm/decks/{argus-code,ux-hci,ai-coding,psych-design}.json`, `themes/starter/decks/argus-basics.json`; `tests/mentor.test.js` where it quotes card text.
- [ ] Run the checker on `themes/*/decks`; fix every ERROR and WARN by rewriting wording only. Keep every card id, term count (8), drill/explain counts, spot-it line numbers and snippet lengths, so history and the tests' structure hold. Add `try_first` to argus-code's first teach card and its pre-reads at least.
- [ ] Update test strings that quote changed text.
- [ ] Checker exits 0 on `themes/*/decks`.
- [ ] Commit.

### Task 6: Ship
- [ ] `VERSION` 4.24.0, `CHANGELOG.md` entry; `bash scripts/check-private.sh`.
- [ ] Push branch, open PR; CI (`tests`, `check-private`) green.
- [ ] Fresh-context review of the Learn page screenshots (visual work is not self-graded).
- [ ] Hub inbox line to the GAME_RESEARCH lessons' owner: rerun `scripts/check-deck.py` and regenerate.
