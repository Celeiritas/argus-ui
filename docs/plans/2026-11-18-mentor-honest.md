# Mentor: honest grading, one Rust path, safe publishing — Implementation Plan

> For agentic workers: work task by task; steps use `- [ ]` checkboxes. Leafy note: execute in this session or with plain subagents; open decisions go to the owner as questions.

**Goal:** Mentor stops pretending: no model calls while studying, no "Correct" from keyword counts, no word-count gates; one curated Rust/Hero's Shade path with a resumable daily session; lessons published as validated, revisioned imports whose corrections reach the learner.

**Architecture:** Three pull requests, one per increment of the brief, each shippable alone. PR A changes grading and the page's feedback only (no schema change). PR B adds a focus track (an explicit lesson allowlist) and a saved session to the existing `settings` table. PR C adds revision tables and a staged importer beside the legacy one, then routes the inbox through it.

**Tech Stack:** Python 3 stdlib (`plugins/mentor/*.py`, SQLite), classic-script JS (`plugins/mentor/page.js`), unittest (`tests/mentor_*_test.py`), Playwright (`tests/mentor*.test.js`, Linux/CI only).

**Spec:** private brief `SOL-final-handoff.md` (2026-11-18, owner-approved; kept outside the repo), sections B and D. Code references below were checked at `d4676ca` (4.54.2); Mentor has not changed since the audited 4.53.0 snapshot.

## Global Constraints
- Mentor's normal learning flow makes no model requests. `assist.py` stays in the repo but nothing in the study path calls it.
- No "Correct" badge from keyword coverage. Explanations get a reference comparison plus self-rating.
- Constrained answers distinguish `12` from `-12`, `a+b` from `a-b`, `1 2` from `2 1`.
- Unicode answers are never stripped or blocked; no minimum-word gates anywhere.
- Rust activities never get Python syntax checks; unsupported evaluators say "self-checked".
- Keep FSRS scheduling, the four ratings, Today, pins, shelf, caps, hints, undo, phone reveal/self-rate, learner separation.
- Repo rules: bump `VERSION` + `CHANGELOG.md` per PR; placeholders, never real names; `bash scripts/check-private.sh` before push; UI rules of `docs/ux-audit-4.1.md` (16/14/12 px, 44 px targets, verb-first labels, 375 px no h-scroll).
- Personal lessons (the Rust path content) never go in git: they go to the host's Mentor inbox / drafts.

## Review Focus
1. An old attempt row with grader `rubric-A` and coverage 1.0 must still render in history without a "Correct" word — history shows the stored result, labelled "word check (old)".
2. A trace step whose accepted wording is `[1, 2]` and the learner types `[1,2]` — whitespace-only difference passes; `[2, 1]` fails.
3. A learner with a saved session whose cards were since shelved or deleted — resume skips missing cards instead of erroring.
4. An inbox file whose second lesson has a duplicate id — nothing from the file becomes active, the author sees the reason, the previous revision keeps serving.
5. A phone with the Hint button and no keyboard — Show the answer reveals at once with one tap.

---

## PR A — 4.55.0: honest feedback (Increment 1)

### Task A1: exact comparator for constrained answers
**Files:** Create `plugins/mentor/compare.py`; Modify `plugins/mentor/mentor.py` (`grade_trace` 703–711, the `predict` branch of `answer` ~1309–1318); Test `tests/mentor_compare_test.py` (add to `tests/run.sh` next to "mentor model").

**Interfaces — Produces:**
- `canon(s: str) -> str` — strip ends, collapse runs of whitespace to one space, remove spaces next to `, ( ) [ ] { }`; nothing else (signs, operators, case, order and Unicode kept).
- `same_value(typed: str, accepted: list[str]) -> bool` — `canon(typed) == canon(a)` for any `a`.

- [ ] Step 1: tests `test_sign_kept` (`same_value('-12', ['12'])` is False), `test_operator_kept` (`'a - b'` vs `['a + b']` False), `test_order_kept` (`'2 1'` vs `['1 2']` False), `test_space_tolerant` (`'[1,2]'` vs `['[1, 2]']` True), `test_unicode` (`'猫'` vs `['猫']` True, `''` vs `['猫']` False), `test_variants` (`'None'` vs `['None', 'none']` True).
- [ ] Step 2: run `python tests/mentor_compare_test.py -v` → fails (no module).
- [ ] Step 3: implement `compare.py`; load it in `mentor.py` like `assist` is loaded in `plugin.py`.
- [ ] Step 4: `grade_trace` uses `same_value(typed[i], p['any'])` instead of `point_hit`; the `predict` kind grades with `same_value(text, [c['answer']] + data.get('accept', []))`, coverage 1.0/0.0, grader `predict-exact`. Add `test_predict_minus_twelve` and `test_trace_reversed` in `tests/mentor_model_test.py` through `answer()`.
- [ ] Step 5: run both test files → pass. Commit `feat(mentor): exact comparison for predict and trace`.

### Task A2: explanations are compared, not marked correct
**Files:** Modify `mentor.py` `answer` (rubric branch), `page.js` result view (WORD/tone 76–81, line 438–453, 660); Test `tests/mentor_model_test.py`, `tests/mentor.test.js`.

**Interfaces — Produces:** rubric-graded kinds (`define`, `explain`, `write`, and any card without an exact evaluator) return `grader: 'compare'`, `suggested: None`, `coverage: None` in the response (DB column stores 0.0 as today's self path does), plus `reference`, `points: [idea…]` (the key ideas, not hit/missed).

- [ ] Step 1: test `test_explain_negation_not_correct` — card reference "A shared reference prevents mutation", answer "A shared reference does not prevent mutation" → response `grader == 'compare'`, `suggested is None`, no `hits`.
- [ ] Step 2: run → fails.
- [ ] Step 3: in `answer`, route rubric kinds to the compare result; keep `write` with `lang != 'python'` free of `syntax_problem` (already so) and mark `evaluator: 'self-checked'`.
- [ ] Step 4: page: a `compare` result shows the band "Compare with the reference" (tone `shown`, no Correct/Partly/Not quite), the reference, the key ideas as a checklist the learner reads, then the four rating buttons with plain meanings: Again "I couldn't recall it", Hard "Right, but hard", Good "Right on my own", Easy "Effortless". History rows of old `rubric-A*` attempts say "word check (old)". "X right" counts that come from self-ratings say "rated Good or Easy"; "Mastered" becomes "Practised" (it counts Good/Easy ratings with up to two hints, not retained skill). Browser test: explain card → no element with text "Correct".
- [ ] Step 5: tests pass. Commit `feat(mentor): explanations compared with the reference, rated by you`.

### Task A3: study makes no model calls
**Files:** Modify `plugin.py` (thread start ~157–166), `page.js` `aiLater`/`aiLine` (~780–800), `docs/mentor-ai.md`; Test `tests/mentor_people_test.py` or new `tests/mentor_noai_test.py` using `tests/fixtures/fake_model.py`.

- [ ] Step 1: test `test_answer_sends_no_model_request` — fake model running and config `enabled: true`; answer an explain card; fake model's request count stays 0; `GET ai?attempt=` returns `{'state': 'none'}`.
- [ ] Step 2: run → fails (embedding call made).
- [ ] Step 3: remove the judge thread from the answer path; `ai` route returns `none`; `aiLater` and the "Meaning match" markup deleted; settings line reads "Local AI: retired from study (docs/mentor-ai.md)". `assist.py` kept, header says retired.
- [ ] Step 4: pass; `grep -n "Meaning match" plugins/` empty. Commit `feat(mentor): retire the local AI from study`.

### Task A4: no word gates, Unicode-safe text
**Files:** Modify `page.js` (`words` line 52, `hint` 373–385, `stepAnnotation`/`selfExplain` 618–641), `mentor.py` `norm` (557), `grade_term` (681–687), `grade_drill` level 3 (668); Test `tests/mentor.test.js`, `tests/mentor_model_test.py`.

- [ ] Step 1: tests — `test_term_kanji` (`grade_term` with answer `猫`, typed `猫` → 1.0); `test_rust_drill_level3_self_checked` (card `lang: 'rust'` level 3 → `evaluator == 'self-checked'`, no `problem`); browser: two hints in a row with an empty reflection box both open; annotation "Show the note" works with an empty why; Show the answer reveals with one tap at 375 px.
- [ ] Step 2: run → fail.
- [ ] Step 3: `norm` uses `str.casefold()` and keeps `\w` Unicode letters (`re.sub(r"[^\w\s]", " ", …)`); reflections become optional ("What did that tell you? (optional)"); `grade_drill` level 3 for non-Python: self-check path.
- [ ] Step 4: pass. Commit `feat(mentor): no word-count gates; Unicode answers kept`.

### Task A5: "In your project" drawer
**Files:** Modify `page.js` `crumb` (64–65) and the card header; `page.css`; Test `tests/mentor.test.js`.
- [ ] Step 1: browser test: a card with breadcrumb `src/lib.rs › install` shows a closed `<details>` "In your project" holding `src/lib.rs` and `install`.
- [ ] Step 2: fail → Step 3: `crumb` keeps the function line; a `<details class="where">` lists the full breadcrumb path (escaped; placeholders filled server-side as today). → Step 4 pass → commit.

### Task A6: ship
- [ ] `VERSION` 4.55.0, CHANGELOG entry, `docs/mentor.md` grading section updated (exact / compare / self-checked table from the brief).
- [ ] Windows unit tests; push branch; CI `tests` green; check-private clean; PR; owner's yes; Zeus deploy (owner types it). Live check: answer one explain card on the real page, Mentor log shows no request to the model port.

## PR B — 4.56.0: one Rust path, one Continue (Increment 2)

> Planned in detail and built in `docs/plans/2026-11-18-mentor-pr-b-focus.md` (focus, Review only, the session that resumes, first Easy within 5 days); the Rust content (B5) is drafted outside git.

### Task B1: focus track (lesson allowlist)
**Files:** Modify `mentor.py` (`settings`/`set_settings` 1030–1071, `track_map` 943, `deck_where` 932, `today` 1611), `plugin.py` routes; Test `tests/mentor_today_test.py`.

**Interfaces — Produces:** settings key `focus = {'goal': str, 'lessons': [module or deck ids], 'new_per_day': int (default 2)}`; track id `'focus'`; `deck_where(db, 'focus')` → `c.deck IN (lessons…)`; `today()` returns `focus: {goal, plan: {reviews, learn, practice}}` when set, and only focus cards when focus is set (other tracks stay searchable in Lessons).

- [ ] Tests: `test_focus_excludes_game_research` (two modules under `GAME_RESEARCH ›`, one in focus → Today serves only that one); `test_focus_new_limit_two`; `test_focus_editable` (set, change goal, clear).
- [ ] Implement; pass; commit.

### Task B2: Today = goal, bounded plan, one Continue
**Files:** `page.js` Today render (~685–720), `page.css`; Test `tests/mentor-today.test.js`.
- [ ] Browser test: with focus set, Today shows the goal text, "2 reviews · 1 lesson · 1 practice" style line, one primary button "Continue", an optional "Review only" link, and an "Edit focus" control (goal text, lesson picker, new per day). Without focus the current Today stays (pins/shelf).
- [ ] Session end screen: "You practised … · Next: …" with a prominent Finish.
- [ ] Implement; pass at 375 px and desktop; commit.

### Task B3: resumable session
**Files:** `mentor.py` (new `save_session(db, learner, payload)`, `load_session(db, learner) -> dict|None` stored in `settings` under `session`), `plugin.py` `GET/POST api/mentor/session`, `page.js` (save plan, index, unfinished text on input, debounced 800 ms; restore on load); Test `tests/mentor_today_test.py`, `tests/mentor.test.js`.
- [ ] Tests: `test_session_round_trip`; `test_session_skips_missing_cards` (Review Focus 3); browser: type half an answer, reload, the same card and text are back.
- [ ] Implement; pass; commit.

### Task B4: ship + content
- [ ] 4.56.0, CHANGELOG, docs; CI; PR; owner's yes; deploy.
- [ ] Content (not git): author the four starting outcomes of the brief (function call, registration path from the owner's real hero-shade repo at a pinned commit, `.ok()`, build vs behaviour) with `/mentor` into `mentor_drafts`; review each against the pinned source / Rust docs; copy approved ones to the host inbox; set the focus to them. 12–20 practice items max, new 2/day.

## PR C — 4.57.0: trustworthy publication (Increment 3)

### Task C1: revisions and attempt binding
**Files:** `mentor.py` schema (after 126) + migration in `connect` (163); Test `tests/mentor_model_test.py` (`test_upgrade_old_db_twice` style).

**Interfaces — Produces:** table `revisions(card_id TEXT, rev INTEGER, hash TEXT, prompt TEXT, answer TEXT, points TEXT, data TEXT, state TEXT CHECK(state IN ('draft','published','withdrawn')), at REAL, PRIMARY KEY(card_id, rev))`; `attempts.rev INTEGER NULL` (NULL = unknown for legacy rows); `current_rev(db, card_id) -> int`; exports (1696–1703) join `attempts.rev` to `revisions`, legacy rows say "revision unknown".
- [ ] Tests: migration twice is a no-op; a new attempt stores `rev`; export of an attempt after a correction shows the old answer.
- [ ] Implement; commit.

### Task C2: staged, atomic import
**Files:** new `plugins/mentor/publish.py` (`preflight(doc) -> list[str]` problems; `publish(db, doc, source) -> {'ok', 'problems', 'changed': [card ids]}` one transaction, no nested commits), `scan_inbox` (517–551) calls it; Test `tests/mentor_publish_test.py`.
- [ ] Tests: duplicate id → nothing changes, `imports.msg` names the duplicate (Review Focus 4); broken JSON → previous revision serves; unknown evidence/review fields are kept in `revisions.data`; drafts (`state: draft`) never reach practice.
- [ ] Implement; commit.

### Task C3: corrections reach the learner
**Files:** `publish.py` (`material(old, new) -> bool`: answer, points or accepted variants changed), `mentor.py` (`notes`/notice row per affected learner, sched reset to relearning for material changes), `page.js` notice "What changed and why" + errata list; Test `tests/mentor_publish_test.py`, `tests/mentor.test.js`.
- [ ] Tests: wording-only edit keeps the schedule; answer change → affected learner sees the notice once, card due for relearning, old attempts keep the old revision.
- [ ] Implement; ship 4.57.0 as in A6.
