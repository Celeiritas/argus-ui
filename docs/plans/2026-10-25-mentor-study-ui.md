# Mentor study screen and course map – implementation plan (spec phases 2 + 3)

**Goal:** the approved mockup's study screen and Lessons page, on today's lessons and data, plus the Sound Lab link.
**Spec:** `docs/plans/2026-10-25-mentor-courses-spec.md` (sections 7, 12, 14) and the mockup canvas (owner-approved 2026-10-25).
**Architecture:** page-only change in `plugins/mentor/page.js` / `page.css`, plus a small server addition for links (`server/argus_ui.py`, `web/js/core.js`, `web/js/home.js`). No database change (that is phase 1).

## Global constraints
- UI rules (CLAUDE.md, docs/ux-audit-4.1.md, vectorlab skills): 16/14/12 px, weights 400/600, 44 px targets, verb-first labels, visible focus, keyboard path, reduced motion, no page overflow at 375 px, **no disabled submit buttons** (say what's missing instead), verdict never by colour alone.
- Escape everything (`esc()`); the verdict band is `role="status"`.
- Every check runs on the owner's real lessons (copies of the GAME_RESEARCH inbox in a throwaway HOME), not only the built-in lesson.
- `VERSION` 4.25.0, `CHANGELOG.md`, `bash scripts/check-private.sh`.

## Review focus
1. Old lessons with long `back_explanation` (answer + evidence + "For SoulSeed" + research note): only the first paragraph shows; the rest sits behind "Show the full answer and sources".
2. Keys: 1–4 now mean Again, Hard, Good, Easy (Anki order); typing in an answer box never triggers them.
3. A lesson with no Learn cards (plain decks) still works; progress bar hidden.
4. Spot-it lines and code wrap (`pre-wrap`), indentation kept; the code-writing box (`textarea.codein`) still does not wrap.
5. `links.json` missing, broken, or with an unsafe `href` (`javascript:`) → no link, no error.

---

### Task 1: The verdict band and the rating row
**Files:** `page.js` (`check`, `learnFeedback`, `rate`, keydown handler, `RATES`), `page.css`, `tests/mentor.test.js`.
- `verdict(kind, title, body)` → `<div class="verdict ok|part|bad|shown" role="status">` with an inline SVG icon (tick / minus / cross / eye) **and** the word (Correct / n of m key ideas / Not quite / Answer shown). Used by every practice and Learn feedback: term, drill blanks, whole body, explain, level-0 self-explanation, spot-it, near example.
- Right/wrong rule: coverage ≥ .99 → ok; > 0 → part; 0 → bad; hints = 4 → shown.
- Missed answer: the band says the right answer and the coach line (*why*), once (no repeated coach line below).
- Model answers: `firstPara + <details>Show the full answer and sources</details>` for the rest.
- Rating row: four buttons in Anki order **Again · Hard · Good · Easy**, each with "in 10 min / in 4 days" (`r.previews`), the suggested one marked "Mentor suggests"; keys 1–4 = Again…Easy; Enter saves; primary button "Save and continue".
- "Mentor's grade was wrong" moves into `<details>Report a grading problem</details>`.
- Tests: right term → `.verdict.ok` with "Correct"; wrong → `.verdict.bad`, "Not quite", the answer; key 1 picks Again; the full-answer toggle exists on an explain card.

### Task 2: No disabled buttons; plainer Learn cards
**Files:** `page.js` (`learnCard`, `tryFirst`, `wireLearn`, `selfExplain`), tests.
- Start learning / That's the line / Reveal / Show the explanation / Check: always enabled; an empty or too-short input shows an inline message under the field (`.need`, `role="alert"`) and focuses it.
- Orientation: lesson name as heading, "What this lesson covers" (its text), "Terms you'll meet: a, b, c" as one plain line (no pills), "Why it matters"; no "In my words, this code…" box; button "Start the lesson".
- Spot-it result: the picked line marked ✕/✓ and red/green, the right line ✓ green.
- Teach card "In your code" → "Where it's used".
- Tests: an empty try-first shows the message and stays; orientation has no textarea; spot-it marks.

### Task 3: Wrapping, header and progress
**Files:** `page.css`, `page.js` (`next`, `learnCard`, header).
- `pre.code`, `.lines .line`, `.model pre`: `white-space: pre-wrap; overflow-wrap: anywhere`; `textarea.codein` unchanged.
- Card header: "project › lesson" (14 px), and when studying one lesson a progress bar of its Learn cards read (`m.learn`) with "n of N".
- The stats line shortens to "N due · N new today"; calibration moves to the Lessons page.
- Test: at 375 px a GAME_RESEARCH spot-it card has no inner horizontal scroll (`scrollWidth <= clientWidth` on `.lines`).

### Task 4: End of session
**Files:** `page.js`.
- `M.session = {answered, right, missed: [card ids]}` (practice cards only).
- "All caught up" panel: "This session: 12 answered, 9 right." + **Replay your 3 mistakes** (asks each missed card via `next?card=` in turn, practice mode, not rescheduled twice: rating still goes through `rate`) + Practice ahead + See lessons.
- Test: after one wrong answer and an empty queue, the replay button names 1 mistake.

### Task 5: Lessons → course map
**Files:** `page.js` (`modulesView`), `page.css`, tests.
- Top: **Continue** panel (the lesson studied last with cards still to learn: `M.deck` or the newest with `to_learn`), button "Continue the lesson"; **Review** panel when `due > 0`: "N cards due", "Review N cards".
- Groups by project (submenus as now): heading + "Study all"; a framed list (`.course-list`, L1 frame, hairlines), one row per lesson: name (link-button), one meta line (cards · due), progress bar (seen/total), one action (Start / Continue / Review).
- Each row's `<details>About this lesson`: breakdown, Read again list, the `/mentor` notes, files. One `<details>` per group: "Where these lessons come from" with the union of files, one per line.
- Bottom: `<details>Add a lesson</details>` and the local AI line; inbox problems stay visible.
- Tests: the Lessons page for 12 GAME_RESEARCH lessons is under 2,500 px tall at 1280; Continue starts the lesson; Read again still opens read-only.

### Task 6: Sound Lab link
**Files:** `server/argus_ui.py` (`links()` read in `state()`), `web/js/core.js` (section bar), `web/js/home.js` (`places()`), `docs/home.md`, `docs/themes.md`, `tests/home.test.js`.
- `~/.config/argus-ui/links.json`: `[{"name": "Sound Lab", "what": "Studio", "href": "/path/"}]`; `href` must start with `/` (same host) or `https://`; at most 8; bad file → none.
- Section bar: after plugins, `<a class="realm link" href target="_self">` with an "opens another page" icon and accessible name "Sound Lab, opens the studio".
- Home Places: one tile per link, "Open <name>".
- Tests: a fixture `links.json` in the test HOME → the bar and Home show it; `javascript:` href ignored.

### Task 7: Ship
- `bash tests/run.sh` in CI; screenshots of every changed screen at 1280 and 375 on the GAME_RESEARCH copies; a fresh-context reviewer (not self-graded); VERSION 4.25.0; changelog; PR.
