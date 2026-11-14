# Today round 2 (E3b, still 4.45.0) – plan

**Goal:** Dax's answers on the 4.45.0 pictures: the god's name is the only title, Open as compact as 4.44.0, Mentor quiet,
and "Known, low priority" for a failure he already knows.

**Architecture:** one new server module `server/quiet.py` holds both quiet things: the default quiet sections
(`DEFAULT_QUIET = {'mentor'}`, E4 turns it into the owner's setting) and the known marks (`known.json` in the state folder).
The status route, the phone (push.sink) and the daily summary (summary.compose) ask it; the page gets `known` on each task.

## Global constraints
- VERSION stays 4.45.0; the CHANGELOG entry grows. Addresses and ids do not change (/watch, api/<id>/status, data-id).
- UI rules: 16/14/12 px, 400/600, 44 px hit areas, verb-first labels, visible focus, reduced motion, no sideways scroll at 375 px.
- Marking known is not holdConfirm (it changes reminders, not what runs); Undo in the toast, Unmark on the card. Owner only.

## Tasks
1. **Names** (`web/js/core.js` WORDS → `{god, was}`; `placeWord(id, name)`; no realm `<small>` on tiles, tabs, pills, More rows;
   who lines `<Agent> · Argus`; labels `Open Argus`; headings Argus / Mnemosyne / Zeus / Mentor / Olympus; memory plugin's
   "Watch page" → "Argus page"). Tests: home, nav, memory, mentor, people, salience, watch, bundled, layout updated to the new
   words; one new check that no tile, tab or pill has a second title line.
2. **Open** (`web/js/home.js` opens(), `web/css/argus.css`): one `ul.openlist` (media, then links) when no link has a group;
   with groups an unlabelled first run, then `.og` per group; under 600 px `.og` is `display:contents` with the label inline.
   Test: Open's height at 412x915 with no groups equals base's (measured), with two groups at most one chip row more.
3. **Mentor quiet** (`server/quiet.py`, status route in `server/argus_ui.py`, `push.sink`, `summary.compose`): a quiet
   section's status answers `needs: false`, no action, no count (owner only). Tests: no row, no count, no button, no badge
   on tab/pill/More, the tile keeps "6 due"; a Mentor-section event never buzzes and is not in the summary.
4. **Known** (`server/quiet.py` marks + fingerprint; `api/known` POST {job, on}; `info()` reads ExecMainStatus; state()
   puts `known` on jobs; page: trouble() leaves known out, Argus tile "· 1 known", card grey + Unmark, need row + card
   "Mark as known", toast Undo). Fingerprint = `Result/ExecMainStatus/<failing check codes, sorted>`. Cleared when the task
   works again (a run ended well, or an always-on task runs with its checks passing) or the fingerprint changes; kept while
   frozen or while a timer task is mid-run. Tests: row gone, no push, back after success-then-fail, back on a new failure kind,
   learner 403, Undo.

## Review focus
- A systemctl hiccup (no units listed) must not drop marks: marks of tasks not in the list are kept.
- A timer task's next run (state running) must not clear its mark; a frozen known task keeps it.
- A known task's watch check alert must not still count (alerts tied to its job are left out too).
- A learner's Today keeps Mentor's nudge (quiet is the owner's).
- 360 px bottom bar with "Mnemosyne" under More.
