# Mentor 4.56.0: one focus path, one Continue, a session that resumes — Implementation Plan

> For agentic workers: work task by task; steps use `- [ ]` checkboxes. Leafy note: execute in this session or with plain subagents; open decisions go to the owner as questions. Python unit tests run on Windows (`python tests/mentor_today_test.py`); browser tests (`tests/*.test.js`) run on Linux CI only.

**Goal:** Today studies one chosen set of lessons (the focus) toward one goal, with a short plan and one Continue button, and a session stopped halfway (reload, phone locked, tab closed) comes back on the same card with the half-typed answer.

**Architecture:** The focus is one study setting (`focus`) holding a goal line, an explicit list of lesson/deck ids and a new-card limit. `track_map()` maps those ids to one track `'focus'`, so every existing mechanism (pins, shelf, daily new limit, `deck_where`, `next_card(session=True)`, Today's counts) works on it without a new code path, and the focus is isolated from the `group:GAME_RESEARCH` grouping that today makes the modding lesson share a track with fourteen game decks. The resumable session is a Mentor note (`set_meta(db, 'session', …)`) in each person's own database, written by the page on every card change and debounced while typing.

**Tech Stack:** Python 3 stdlib + SQLite (`plugins/mentor/mentor.py`, `plugin.py`), classic-script JS (`plugins/mentor/page.js`, `page.css`), unittest, Playwright on CI.

**Spec:** parent plan `docs/plans/2026-11-18-mentor-honest.md` (PR B section) and the owner-approved private brief `SOL-final-handoff.md` (outside the repo), Increment 2: "One guided Rust/navigation goal; separate curated track/course or lesson allowlist; short lesson/practice/apply/finish flow; honest comparison; direct help/reveal; optional typing; resumable session. Acceptance: phone and desktop complete a bounded relevant session; no forced word-count reflections; all activities belong to selected scope. The selected Rust scope excludes unrelated GAME_RESEARCH decks; initial focus settings are editable. Help/reveal works directly with touch and keyboard; session position/response survives refresh or a supported pause." Code references checked at `6032141` (4.55.0).

## Global Constraints
- Everything the parent plan's Global Constraints say (no model calls in study, no keyword "Correct", FSRS + four ratings + undo + pins + shelf + learner separation kept, placeholders never real names, `check-private.sh` before push, 16/14/12 px, 44 px targets, verb-first labels, no h-scroll at 375 px).
- Without a focus set, Today, pins and shelf behave exactly as in 4.55.0 (the existing tests in `tests/mentor_today_test.py` and `tests/mentor-today.test.js` pass unchanged).
- With a focus set, a session (Continue) serves only focus cards: reviews and new. Other lessons stay reachable in Lessons and the Study picker.
- The focus is per database (per person), like every study setting; a learner may set their own focus; nothing of the owner's moves.
- POST bodies stay ≤ 4 KB (server limit): the saved unfinished answer is cut to 2,000 characters.
- No real lesson content in git: the Rust lessons go to the host inbox (task B5). Tests use fixture lessons.

## Review Focus
1. A saved session whose card was since shelved, deleted, or moved out of the focus → resume skips it and serves the next card; no error, no blank screen. (B3 `test_session_skips_missing_card`)
2. Focus lists a lesson id that no longer exists (file removed from the inbox) → Today shows the focus with the remaining lessons and one plain line "1 lesson in your focus is no longer on the server"; an all-missing focus says so and offers Edit focus. (B1 `test_focus_missing_lesson`)
3. A focus lesson that is also on the shelf → the focus wins (it is served); the shelf entry for its old track does not hide it. (B1 `test_focus_beats_shelf`)
4. Two tabs (phone and desktop) on the same session → the newer save wins; the older tab's next save does not bring back an answer already submitted (saves carry the card id; a save for a card that has been rated is ignored). (B3 `test_session_stale_save_ignored`)
5. Typing in a language Mentor can't check (Rust) on a phone with no hardware keyboard → Show the answer works with one tap and the half-typed text is kept in the session until rated. (B3 browser test)

---

### Task B1: the focus setting and its track
**Files:** Modify `plugins/mentor/mentor.py` (`SETTINGS` 1005, `set_settings` 1056–1077, `track_map` 949–957, `tracks` 959–970, `deck_where` 938–943, `today` 1658–1706); Modify `plugins/mentor/plugin.py` 200–202 (no change to key filtering needed: `focus` is in `SETTINGS`); Test `tests/mentor_today_test.py`.

**Interfaces — Produces:**
- Setting `focus`: `{'goal': str (≤140, same cleaning as _goal), 'lessons': [id, …] (≤ 50, via _ids), 'new_per_day': int 0..20 (default 2)}`; `{}` = no focus. `set_settings(db, {'focus': {...}})` replaces it whole; `{'focus': {}}` clears it.
- `FOCUS = 'focus'` track id. `track_map(db)` maps every id in `focus.lessons` that exists to `'focus'` (overrides its group/own track).
- `deck_where(db, 'focus')` → `"c.deck IN (…)"` over the existing focus lessons; `"0", []` when none exist.
- `tracks()` lists the focus track first with name `'Focus'` (the goal is shown separately).
- `new_limit(st, 'focus')` returns `focus.new_per_day`.
- `today()` adds `focus: None | {goal, lessons: n, missing: n, plan: {reviews, new, later}}` where `plan.reviews` = focus cards due now, `plan.new` = focus new left today; when focus is set, `scope` = `['focus']` and `due`/`new_left` count the focus only.
- `next_card(..., session=True)` with a focus set: reviews of the focus first, then focus new cards; no other tracks (both branches at 1217ff take `pins = {'focus'}` when focus is set).

- [ ] Step 1: tests (fixture: two lessons under project `GAME_RESEARCH › Games`, one `GAME_RESEARCH › Topics` lesson `mod1`, one plain deck):
  - `test_focus_excludes_game_research`: focus `{'lessons': ['mod1']}` → `today()['scope'] == ['focus']`; ten `next_card(db, session=True)` calls serve only `mod1` cards.
  - `test_focus_new_limit_two`: default `new_per_day` 2 → after rating two new focus cards, `today()['focus']['plan']['new'] == 0` and the next session card is not new.
  - `test_focus_editable`: set goal "Read a Rust call", change it, clear with `{}` → `today()['focus'] is None` and scope is back to the 4.55 rule.
  - `test_focus_missing_lesson`: focus `['mod1', 'gone']` → `today()['focus']['missing'] == 1`, `lessons == 1`.
  - `test_focus_beats_shelf`: shelve `group:GAME_RESEARCH`, focus `['mod1']` → `mod1` cards are served.
  - `test_focus_bad_input_ignored`: `{'focus': {'lessons': 'mod1'}}` and 51 lessons → setting unchanged (wrong type is ignored, as for every setting).
- [ ] Step 2: run `python tests/mentor_today_test.py` → the six fail.
- [ ] Step 3: implement as in Interfaces. Shelf check in `next_card` / `today` uses `track_of(tm, deck)`, which is `'focus'` for focus lessons, so 3 holds as long as `'focus'` itself is never put on the shelf (refuse it in `set_settings`: drop `'focus'` from a `shelved` list).
- [ ] Step 4: run the whole Python Mentor suite (`mentor_model`, `mentor_people`, `mentor_today`, `mentor_compare`, `mentor_gate`) → all pass.
- [ ] Step 5: commit `feat(mentor): focus = an explicit lesson list as one track (4.56)`.

### Task B2: Today = goal, a short plan, one Continue; Edit focus
**Files:** Modify `plugins/mentor/page.js` `todayView` 683–748 and `summary` 768ff, `plugins/mentor/page.css`; Test `tests/mentor-today.test.js`.

**Interfaces — Consumes:** `today().focus` (B1); `POST settings {focus}` (B1).

- [ ] Step 1: browser tests (Linux CI):
  - with focus set: the top section shows the goal as a heading, one line like "2 reviews · 2 new" (from `plan`), one primary button **Continue** (`#goCont`), and a link-styled button **Review only** (shown only when `plan.reviews > 0`); the 4.55 "Nothing is pinned yet…" line is absent.
  - **Edit focus** (`#editFocus`) opens a form: Goal (text, 140 max), Lessons (checkbox list grouped by project, from `tracks`/Lessons data), New per day (number 0–20); **Save focus** saves and re-renders; **Clear focus** returns to the 4.55 Today.
  - without focus: Today is exactly the 4.55 Today plus one quiet **Set a focus** button under the Study button.
  - at 375 px: no horizontal scroll; Continue, Review only, Edit focus ≥ 44 px tall.
  - re-add the 44 px check of "Report a grading problem" on a term card (left from the 4.55 review).
- [ ] Step 2: implement. Continue = `startSession(false)` (focus scope comes from the server); Review only = `startSession(false, {reviewOnly: true})` → `next?session=1&reviews=1` (server: `next_card(..., reviews_only=True)` returns no new card; add that parameter in this task with `test_review_only_serves_no_new` in `tests/mentor_today_test.py`).
- [ ] Step 3: end-of-session screen (`summary`): with a focus, its first line is "You practised N · M right" and its next line names the next step from `today().focus.plan` ("Next: 1 review tomorrow" / "Next: 2 new questions tomorrow"); one primary **Finish** button back to Today.
- [ ] Step 4: CI green on a `ci/mentor-focus` push; commit `feat(mentor): Today shows the focus goal, its plan and one Continue`.

### Task B3: the session resumes
**Files:** Modify `plugins/mentor/mentor.py` (new `save_session`, `load_session`, `clear_session` near `today`), `plugins/mentor/plugin.py` (`GET session`, `POST session`), `plugins/mentor/page.js` (`startSession`, `next`, the answer box input handler, `summary`, page load); Test `tests/mentor_today_test.py`, `tests/mentor.test.js`.

**Interfaces — Produces:**
- `save_session(db, s: dict) -> dict|None`: keeps `{started: float, review_only: bool, card: str, text: str (≤2000), shown: bool, answered: int, right: int, missed: [card ids ≤ 50], at: float}`; ignores a save whose `card` already has an attempt rated after `s['started']` with `at` newer than that rating (Review Focus 4); returns the stored session.
- `load_session(db) -> dict|None`: the stored session, or None when older than 12 hours; drops `card` (and `text`) if that card no longer exists, is shelved, or is outside the current focus (Review Focus 1).
- `clear_session(db)`.
- `GET api/mentor/session` → `{session: …|None}`; `POST api/mentor/session {session: {...}}` saves, `{session: null}` clears. Per person (the database is already chosen per person by `plugin.py`).

- [ ] Step 1: Python tests `test_session_round_trip`, `test_session_skips_missing_card`, `test_session_expires_after_12h`, `test_session_stale_save_ignored`, `test_session_text_capped` (2,500 chars → 2,000).
- [ ] Step 2: run → fail; implement; run the Python Mentor suite → pass.
- [ ] Step 3: page: save on session start, on each card shown, and 800 ms after the last keystroke in the answer box; clear on Finish. On load, when `GET session` returns one, Today shows **Continue where you stopped** (primary) in place of Continue; it reopens the session view on the saved card with `text` back in the box and the timer restarted with the minutes left (at least 2).
- [ ] Step 4: browser test in `tests/mentor.test.js`: start a session, type half an answer, reload → Continue where you stopped → same card, same text; then Show the answer with one tap on a 375 px touch viewport keeps the text (Review Focus 5).
- [ ] Step 5: CI green; commit `feat(mentor): a session stopped halfway comes back with its answer`.

### Task B4: ship 4.56.0
**Files:** `VERSION`, `CHANGELOG.md`, `docs/mentor.md` (a "Focus" section after "Tracks", a "Session" line; the settings table gains `focus`, the API table `GET/POST session`), this plan's checkboxes, the parent plan's PR B section (point here).
- [ ] `bash scripts/check-private.sh`; push; PR "Mentor 4.56.0: one focus, one Continue, a session that resumes"; CI green; one fresh Opus review of the branch; fix; the owner's look at a picture of Today with and without a focus (phone width); the owner's yes; merge; the owner deploys through Zeus.

### Task B5 (content, not in git): the first Rust focus
- [ ] With `/mentor` (writes `mentor_drafts/`), draft the brief's four starting outcomes: reading one function call; the registration path in the owner's hero-shade repo at a pinned commit; `.ok()` (Result → Option, Rust docs R4); build succeeded vs the game behaving. Plain Rust examples first, then the mod code. 12–20 practice items, `lang: "rust"` on every code card.
- [ ] `python scripts/check-deck.py` on each; the owner reads them; copy the approved ones to the host inbox; set the focus to them with goal words the owner picks.

### Not in this PR (owner to decide; asked 2026-11-18)
- **The jump in review times.** New card today: Again 1 min, Hard 6 min, Good 10 min, Easy 14 days (FSRS-4.5's default first Easy memory, `W[3]` = 13.8 days, at 90% retention); Good after the 10-minute step gives 4 days (`W[2]` = 3.7). Cheap option (one constant + two tests): cap a new card's first Easy at Good's interval + 1 day (4 → 5 days). Bigger option: fit FSRS's weights to the owner's own rating history (an optimiser; needs a few hundred reviews to be worth it).
