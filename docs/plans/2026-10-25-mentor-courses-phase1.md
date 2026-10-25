# Mentor courses, phase 1 (data model + checker v2) Implementation Plan

> **For agentic workers:** execute task by task in this session or with plain subagents (only writing-plans, systematic-debugging and verification-before-completion are installed). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mentor stores courses → modules → lessons → notes → cards with learning objectives (LOs) and a review log, imports a new course file format beside today's lessons (which become the "Loose lessons" course), and `scripts/check-deck.py` refuses a course that breaks the spec's rules.

**Architecture:** A course lesson *is* today's lesson JSON (tier lists, Learn fields) plus `id`, `los`, `notes`, and `lo` / `note` / `role` / `check` on each tier item, so `import_module()` keeps building every card and Learn card; a new `import_course()` walks the course and calls it per lesson. The existing `modules` table stays the lesson table (renaming it would touch every query); new tables hold courses, course modules, LOs and notes. The page is unchanged: a course lesson's `project` is its course name, so the 4.25.0 course map already groups it.

**Tech Stack:** Python 3 stdlib (sqlite3, ast, json, subprocess for `git`, urllib for `--online`), `unittest` for the new model tests, the existing Playwright suite.

**Spec:** `docs/plans/2026-10-25-mentor-courses-spec.md` (sections 3, 4, 5, 6, 7 review log, 10, 14 phase 1).

## Global Constraints
- App stays MIT, stdlib only; Anki (AGPL) read for behaviour only, never copied.
- No personal names, paths or hosts in fixtures or docs: placeholders `{{SERVER}}` etc. Personal courses never go in `themes/`.
- Nothing lost on upgrade: new columns via `ADDED`, new tables via `SCHEMA` (`CREATE TABLE IF NOT EXISTS`); `connect()` stays idempotent on a 4.25.0 database.
- LO fields exactly: `{id, text, verb, bloom, mode, knowledge, condition, standard, parent}`; `bloom` ∈ remember | understand | apply | analyse | evaluate | create; `mode` ∈ read | write; `knowledge` ∈ factual | conceptual | procedural | metacognitive. Never the verbs know / understand / learn about.
- Card roles (spec §5): term, recall, predict, trace, explain, parsons, drill, write, find-bug, choose-design, make. Phase 1 imports the ones today's kinds can run: term→`term`, recall→`define`, explain / find-bug / choose-design→`explain`, drill→`drill`. predict, trace, parsons, write, make are phase 4: the checker says so (ERROR) and the importer skips them with a note.
- Every LO has ≥ 2 practice cards and ≥ 1 check item; check items never appear in practice.
- Review-log ms capped at 60 s; kinds `learn` / `review` / `relearn` / `manual`.
- `source_ref`: code `{repo, path, symbol, commit, lines}`; paper `{cite, url, doi}`; note `{note, path}`. Citation format: **Author(s) (year). Title. Venue.**
- Bump `VERSION` to 4.26.0 and add a `CHANGELOG.md` entry; `bash scripts/check-private.sh` before every push.

## Course file format (`"format": "mentor-course/1"`)
One JSON file per course, dropped into the inbox (or a decks folder) like a lesson:
```json
{"format": "mentor-course/1", "id": "elaia-server", "name": "Rebuild Elaia's server", "summary": "…",
 "requires": [], "retention": 0.9, "sources": [{"cite": "Rosenshine, B. (2012). Principles of instruction. American Educator.", "url": "https://…"}],
 "los": [{"id": "T2", "text": "Build request checks that refuse unsafe POSTs", "verb": "build", "bloom": "create", "mode": "write",
          "knowledge": "procedural", "condition": "docs allowed", "standard": "all tests pass", "parent": null}],
 "capstone": {"spec": "…", "tests": "…"},
 "modules": [{"id": "safe-posts", "name": "Safe POSTs", "requires": ["serving"],
   "los": [{"id": "M3a", "parent": "T2", "…": "…"}],
   "lessons": [{"id": "origin-check", "name": "Why the Origin check", "los": [{"id": "L1", "parent": "M3a", "…": "…"}],
     "notes": [{"id": "n-origin", "kind": "snippet", "source_ref": {"repo": "argus-ui", "path": "server/argus_ui.py", "symbol": "host_ok", "commit": "beab7ba", "lines": "120-131"}}],
     "metadata": {"module_name": "…"}, "cta_summary": {"orientation": "…"},
     "tier_2_self_explanation_cards": [{"id": "c1", "lo": "L1", "note": "n-origin", "role": "explain", "front_prompt": "…", "back_explanation": "…", "eval_rubric": []},
                                       {"id": "k1", "lo": "L1", "note": "n-origin", "role": "explain", "check": true, "…": "…"}]}]}]}
```
LO ids are unique within a course. `note` kinds: term | concept | snippet | claim. Lesson ids are unique within a course; the stored lesson id is `slug(course + '--' + lesson)`.

## Review Focus
1. **The live 4.25.0 database upgraded twice** (start, restart): no duplicate Loose-lessons rows, every attempt and schedule row kept, every old lesson in `loose`. → Task 1 `test_upgrade_old_db_twice`.
2. **A course re-imported after a lesson is renamed or removed**: the removed lesson's cards go (attempts and schedule kept, as `import_module` does today), its `modules` row, notes and LOs go too; the other lessons keep their history. → Task 3 `test_reimport_drops_removed_lesson`.
3. **A broken course in the inbox** (missing `lo`, unknown note, phase-4 role, not a dict): the importer never raises; `imports.msg` names what was skipped, the rest imports. → Task 3 `test_lenient_import_notes`.
4. **A check item served by any route** (`next`, `next?deck=group:…`, practise ahead): never. → Task 3 `test_check_items_never_served`.
5. **Placeholders in course text** (`{{SERVER}}` in a course name, LO text, module name): filled like lesson text wherever `stats` returns it. → Task 4 `test_course_text_filled`.

---

### Task 1: Model tests harness, new tables, Loose lessons

**Files:**
- Create: `tests/mentor_model_test.py` (stdlib `unittest`; imports `plugins/mentor/mentor.py` by path, as `plugin.py` does; temp dir per test with `ARGUS_MENTOR_INBOX` and `LEAFY_REALM` pointed into it before import)
- Modify: `plugins/mentor/mentor.py` (`SCHEMA`, `ADDED`, `connect()`, `import_module()`), `tests/run.sh` (run the model tests under `== mentor model` when `$1` is empty or `mentor`)

**Interfaces:**
- Produces tables: `courses(id PK, name, summary, requires TEXT json, retention REAL, data TEXT json, source TEXT, at REAL)`; `cmodules(id PK, course, name, ord INTEGER, requires TEXT json)`; `los(id PK, course, owner, scope, text, verb, bloom, mode, knowledge, condition, standard, parent)` — `id` = `course/LOid`, `scope` ∈ course | module | lesson, `owner` = course / cmodule / lesson id; `notes(id PK, lesson, kind, source_ref TEXT json)` — `id` = `lesson:note`.
- Produces columns: `modules.course TEXT`, `modules.cmodule TEXT`, `modules.ord INTEGER DEFAULT 0`; `cards.lo TEXT`, `cards.note TEXT`, `cards.role TEXT`, `cards.is_check INTEGER DEFAULT 0`.
- Produces `LOOSE = 'loose'`, `loose_module(project: str) -> str` (= `'loose/' + slug(project or 'lessons')`), `ensure_loose(db) -> None` (upserts the `loose` course "Loose lessons" and one cmodule per distinct project; fills `course`/`cmodule` where `course IS NULL`). `connect()` calls it; `import_module(..., course=None, cmodule=None, ord_=0)` sets the three new `modules` columns (old-format callers pass nothing → Loose).

- [ ] **Step 1: Write the failing tests** — `test_upgrade_old_db_twice`: build a DB with the 4.25.0 `SCHEMA`+`ADDED` only (copy the strings into the test as `OLD_SCHEMA`), insert two lessons (projects `argus-ui`, `GAME_RESEARCH › Topics`), 3 cards, 2 sched rows, 4 attempts; `connect()` twice → counts of cards/sched/attempts unchanged, `SELECT COUNT(*) FROM courses WHERE id='loose'` == 1, both lessons have `course='loose'` and `cmodule` = `loose/argus-ui`, `loose/game_research-topics`; 2 cmodules. `test_old_lesson_import_is_loose`: import `themes/leafy-realm/decks/argus-code.json` via `load_decks` → its `modules` row is in `loose`.
- [ ] **Step 2: Run** `python3 tests/mentor_model_test.py -v` → FAIL (no table `courses`).
- [ ] **Step 3: Implement** the tables, columns, `LOOSE`, `loose_module`, `ensure_loose`, and the `import_module` parameters.
- [ ] **Step 4: Run** the model tests → PASS; `bash tests/run.sh mentor` → all mentor browser checks still pass (CI or the server).
- [ ] **Step 5: Commit** `Mentor: course tables, card LO/note/role columns, old lessons as the Loose lessons course; model tests`.

### Task 2: Review log on every rating

**Files:** Modify `plugins/mentor/mentor.py` (`ADDED`, `rate()`); Test `tests/mentor_model_test.py`.

**Interfaces:**
- Produces columns `attempts.review TEXT`, `attempts.ivl_before REAL` (days), `attempts.ivl_after REAL` (days), `attempts.took INTEGER` (ms, ≤ 60000). Written by `rate()` for practice cards only (Learn cards stay `NULL`).
- `review_kind(srow, ratings: list[int], now: float) -> str` (ratings: the card's earlier ratings, newest first): `learn` until the card has been rated Hard or better once (Anki's learning phase); then `manual` when `srow['due'] > now` (practise ahead); `relearn` when the latest earlier rating was 1; else `review`.
- `ivl_before` = `(due - last) / DAY` of the sched row before this rating, `None` for a new card; `ivl_after` = `(new due - now) / DAY`.

- [ ] **Step 1: Failing tests** — `test_review_log_new_then_review`: answer+rate a new card 3 → `review='learn'`, `ivl_before IS NULL`, `ivl_after > 0`; move its `due` to the past, rate 1 → `review='review'`; rate again → `relearn`. `test_review_log_manual`: rate a card whose due is tomorrow → `manual`. `test_took_capped`: answer with `ms=95000` → `took == 60000`, `ms == 95000` (the grader keeps the raw time). `test_learn_card_no_log`: rate a teach card → all four columns NULL.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** `review_kind` and the columns in `rate()`'s UPDATE. **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `Mentor: review log (kind, interval before and after, capped time) on every rating`.

### Task 3: Import a course

**Files:** Modify `plugins/mentor/mentor.py` (`is_course()`, `import_course()`, `scan_inbox()`, `load_decks()`, `import_module()` item fields, `next_card()`); Create `tests/deck-fixtures/good-course.json` (2 modules, 3 lessons, each lesson LO with 2 practice + 1 check, one note per kind, Learn fields present, placeholders `{{SERVER}}` in one LO and one module name; public text only); Test `tests/mentor_model_test.py`.

**Interfaces:**
- `is_course(doc) -> bool`: `doc.get('format', '').startswith('mentor-course/')`.
- `import_course(db, doc, source: str, built_in: bool) -> tuple[int, list[str]]` (cards added, notes); caller holds `DB_LOCK`, like `import_module`. Upserts `courses`, `cmodules` (`id` = `course/module`, `ord` = position), `los` (all three scopes), `notes`; calls `import_module(db, lesson, slug(course + '--' + lesson_id), source, built_in, course=..., cmodule=..., ord_=...)` with `lesson['metadata']['project']` defaulted to the course name and `module_name` to the lesson name. Deletes `modules`, `cards`, `notes`, `los` rows of this course that the file no longer has (never `sched` / `attempts`).
- `import_module` reads per tier item: `lo` (stored as `course/LOid` when the lesson is in a course), `note` (stored as `lesson:note`), `role` (default from kind: term→term, drill→drill, explain→explain, define→recall), `check` → `is_check`. A Learn card inherits its practice card's `lo` and `note`. Items with a phase-4 role are skipped with the note `"<id>: role <role> arrives in phase 4"`; an item whose `lo` is not one of its lesson's LOs keeps `lo = NULL` and adds a note.
- `scan_inbox` / `load_decks`: a course file goes to `import_course`; `imports.module` = the course id; message `"N cards in M lessons"` plus skipped notes.
- `next_card`: rows with `is_check = 1` are dropped before anything else, so they are never in `due`, `new` or practise-ahead *and* never hold back the lesson's unlock order (an unanswered check item would freeze the funnel). `stats()` and `modules()` leave them out of every count, or Home would show them as waiting for ever (`test_checks_not_counted_as_waiting`).

- [ ] **Step 1: Failing tests** — `test_import_course_tables`: import the fixture → 1 course, 2 cmodules, LO counts per scope as in the fixture, notes with parsed `source_ref`, every practice card has `lo` like `course/L…` and a `role`, `is_check` count = 3. `test_reimport_drops_removed_lesson` (Review Focus 2): import, answer+rate one card in lesson B, remove lesson A from the doc, re-import → A's `modules`/cards/notes/LOs gone, B's attempt and sched kept. `test_lenient_import_notes` (Review Focus 3): a copy with one `role: "parsons"` item, one unknown `lo`, one non-dict lesson → no exception, notes mention all three, the rest imported. `test_check_items_never_served` (Review Focus 4): study the course through `next_card(deck=None)`, `deck='group:<course name>'`, and `extra=True` until `None` → no card with `is_check=1` returned. `test_inbox_course`: copy the fixture into the inbox → `scan_inbox` → `imports` row ok with "in 3 lessons".
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `Mentor: import courses (modules, LOs, notes; check items kept out of practice)`.

### Task 4: Courses in stats, and on the page as they are

**Files:** Modify `plugins/mentor/mentor.py` (`modules()`, `stats()`); `tests/mentor.test.js` (one block); `tests/run.sh` (copy `good-course.json` into the test inbox before the server starts); Test `tests/mentor_model_test.py`.

**Interfaces:**
- `modules()` rows gain `course`, `cmodule`.
- `courses(db) -> list[dict]`: `[{id, name, summary, loose: bool, modules: [{id, name, requires, lessons: [lesson ids in ord]}], los: n}]`, Loose last; every text through `fill()`. `stats()` returns it as `courses`.

- [ ] **Step 1: Failing tests** — model: `test_stats_courses` (the fixture course first with 2 modules in order, Loose last); `test_course_text_filled` (Review Focus 5): with a realm file setting `SERVER`, the module name comes back filled. Browser (`mentor.test.js`): Lessons shows a group headed with the fixture course's name holding its 3 lessons; *Study this lesson* on one serves a card whose id starts with that lesson's id; no page errors.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** model tests and `bash tests/run.sh mentor` → PASS (CI).
- [ ] **Step 5: Commit** `Mentor: courses in stats; a course's lessons show in Lessons as one group`.

### Task 5: Checker v2, structure

**Files:** Modify `scripts/check-deck.py` (course branch in `check()`); Create `tests/deck-fixtures/bad-course.json` (one break per rule below); Modify `tests/run.sh` (good course passes; bad course fails and each rule id is reported).

**Interfaces:** `check_course(doc) -> list[(where, level, rule, message)]`, called from `check()` when `is_course`-shaped (same test as Task 3, copied: the script stays standalone). Rules, all ERROR unless marked:
- **C1 schema:** required keys (`format`, `id`, `name`, `los`, `modules`; module `id`, `name`, `lessons`; lesson `id`, `los`); ids unique (LOs in the course; modules; lessons; notes in a lesson; items in a lesson).
- **C2 LO form:** all nine fields present (`parent` may be null on course LOs only); enums as in Global Constraints; `verb` one word; `text` starts with the verb (case-insensitive); `know`, `understand`, `learn about` as the verb → ERROR. A verb outside {trace, predict, explain, write, fix, choose, build, name, define, order, find, modify, compare, rebuild, describe} → WARN.
- **C3 alignment:** a module LO's `parent` is a course LO, a lesson LO's `parent` is a module LO of its own module; every course LO has ≥ 1 module LO under it and every module LO ≥ 1 lesson LO (WARN for the latter two).
- **C4 cards:** every tier item has `lo` naming one of its lesson's LOs and a `role` from spec §5; phase-4 roles → ERROR "arrives in phase 4"; `note` names a note of the lesson; each lesson LO has ≥ 2 practice items and ≥ 1 `check: true` item.
- **C5 requires:** module and course `requires` name existing ids; no cycles (depth-first search).
- **C6 citations:** every paper `source_ref.cite` and `sources[].cite` matches `^.+ \(\d{4}[a-z]?\)\. .+\. .+\.$`.
- **C7 answers parse:** a drill's `full_canonical_code` and level-3 answer parse with `ast` when the note's `source_ref.path` ends in `.py` or the item says `"lang": "python"`; others → INFO "not parsed (lang)".
- Each lesson also gets today's rules R1–R5 by calling the existing per-lesson code.

- [ ] **Step 1:** write `bad-course.json`; add to `run.sh` the loop `for r in C1 C2 C3 C4 C5 C6 C7; do grep -q " $r " …`, and the good course to the passing list. **Step 2: Run** `python3 scripts/check-deck.py tests/deck-fixtures/bad-course.json` → rules missing. **Step 3: Implement.** **Step 4: Run** `bash tests/run.sh mentor` (the rubric block) → passes; good course 0 errors.
- [ ] **Step 5: Commit** `check-deck v2: course structure, LO form, alignment, card links and counts, requires cycles, citations, answers parse`.

### Task 6: Checker v2, source references resolve

**Files:** Modify `scripts/check-deck.py` (`--repo NAME=PATH` repeatable, `--online`); `tests/run.sh` (run the good course with `--repo argus-ui="$R"`); `tests/deck-fixtures/bad-course.json` (a missing symbol; a missing path).

**Interfaces:** `resolve_ref(ref: dict, repos: dict[str, str], online: bool) -> tuple[level, message] | None`.
- **C8 code refs:** repo given → `git -C <path> cat-file -e <commit>:<path>` (ERROR when missing); symbol found in `git show <commit>:<path>` by `\b(def|class|function)\s+<symbol>\b|^\s*<symbol>\s*=` (ERROR when not); repo not given → INFO "not checked: pass --repo NAME=PATH".
- **C9 links:** `--online`: URL answers (HEAD, then GET, 10 s timeout, status < 400) and `doi` resolves at `https://doi.org/<doi>`; failure → ERROR. Without `--online` → nothing printed (the summary line says `links not checked (add --online)`).
- Note refs `{note, path}`: path exists relative to the current directory → else WARN.

- [ ] **Step 1:** add the bad refs; `run.sh` greps ` C8 `. **Step 2: Run** → missing. **Step 3: Implement.** **Step 4: Run** the rubric block → passes; the good course's refs point at real symbols in this repo at a commit on `main` (e.g. `host_ok` in `server/argus_ui.py`; CI clones with history: confirm `fetch-depth` in `.github/workflows/tests.yml`, set `0` if shallow).
- [ ] **Step 5: Commit** `check-deck v2: code references resolve at their commit; --online checks links and DOIs`.

### Task 7: Docs, version, real-lesson check, PR

**Files:** `docs/mentor.md` (a *Courses* section: the format above, Loose lessons, the review log; a *Checker v2* paragraph), `docs/mentor-rubric.md` (C1–C9 table), `plugins/mentor/mentor.py` docstring (courses line), `VERSION` 4.26.0, `CHANGELOG.md`, `CLAUDE.md` map line for Mentor (mention courses + `tests/mentor_model_test.py`).

- [ ] **Step 1: Real-lesson check (on the PC):** on copies of the 12 GAME_RESEARCH lessons in the scratchpad, `python -I` a small script that `connect()`s a fresh DB, imports them, and prints lessons per cmodule (expect 12 in `loose`, the same card counts as 4.25.0's import). Then the same on a copy of the live `mentor.db` (fetched read-only from the server): row counts before and after `connect()` identical, all lessons in `loose`.
- [ ] **Step 2:** docs, VERSION, CHANGELOG; `bash scripts/check-private.sh` on the staged diff.
- [ ] **Step 3: Commit, push, PR** against `main` (body: carries the spec; phase-1 scope; what's not in it: staleness on rebuild and the Drafts review are phase 5, new card roles phase 4). Wait for CI green; fresh-context review of the branch; fix; ask Dax to merge.
