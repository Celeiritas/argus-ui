# Mnemosyne e-ink mode, synced reading places and index vibration – implementation plan

> For agentic workers: work task by task, tests first; each task ends green and committed.

**Goal:** Make the Mnemosyne Library comfortable on an e-ink tablet, carry reading places between the owner's devices, and add an opt-in vibration for the side index.

**Architecture:** All client work stays in the bundled `memory` plugin (`page.js` / `page.css`). A new `plugins/memory/places.py` stores each person's reading places in one small JSON file on the server, reached through `api/memory/library/places` (GET) and `api/memory/library/place` (POST). The browser keeps its existing local copy as the fallback. The preview page gets the vibration choice through its URL because it is sandboxed and cannot read storage.

**Tech stack:** Python stdlib, classic browser JS, CSS; Playwright tests through `tests/run.sh` (CI on Linux).

**Spec:** owner decisions of 2026-11-23 (hub inbox, argus-ui): build inside the Library, not a new app. E-ink mode with auto-detect and a manual switch; no animation; monochrome; paged reading with edge taps; bigger margins. Reading-place sync across Argus devices only (no KOSync server). Side-index vibration behind a Settings switch, OFF by default.

## Global constraints
- Type 16/14/12px, weights 400/600; 44px hit areas; verb-first labels; visible focus; keyboard path for every pointer action; no horizontal scroll at 375px (CLAUDE.md UI rules).
- No new runtime dependency. Escape everything put into HTML (`api.esc`). POST stays JSON-only (the server's existing checks).
- Stored records hold IDs, revisions, offsets and times only: no titles, no text.
- Bounds copied from the existing client: id and revision `^[a-f0-9]{64}$`, offset integer 0..100000, recent list 10, saved places 100.
- VERSION 4.67.0 and a CHANGELOG entry; `docs/mnemosyne-library.md` gets a "Reading settings, e-ink and synced places" section.

## Review focus
1. The server is unreachable or answers an error: reading, Save place and Continue reading still work from this browser, and the status says the place is kept on this browser only.
2. Two devices save the same document: the newer save (server time) wins on both, and a place saved for an old revision never moves a reader in the new revision.
3. E-ink paging with a section shorter than one screen (one page; an edge tap moves to the next section) and after rotating the tablet (pages are counted again, and the reader stays on the same text).
4. Local storage denied (private mode) while e-ink is chosen manually: the choice holds for this visit, nothing throws.
5. A person other than the owner (a learner) reading: their places never mix with the owner's.

---

### Task 1: Reading settings and e-ink look

**Files:** Modify `plugins/memory/page.js`, `plugins/memory/page.css`; Test `tests/library-ui.test.js`.

**Interfaces – produces:** `readingPrefs()` → `{eink: 'auto'|'on'|'off', vibrate: boolean}` (localStorage key `mnemosyne-reading-settings-v1`, session fallback like `recentReads`); `einkActive()` → boolean; class `eink` on `document.documentElement` while the Library is shown, removed when it is left (the existing `removed` observer).

- [ ] Write failing tests: a "Reading settings" `<details>` in the Library holds an "E-ink mode" select (Automatic / On / Off) and a "Vibrate when the side index moves" checkbox that is unchecked by default; choosing On adds `html.eink` and survives a reload; Off removes it; with storage denied the choice still applies for the visit; an emulated `update: slow` media with Automatic turns it on; leaving the section removes `html.eink`.
- [ ] Run `bash tests/run.sh library-ui` (CI) and see them fail.
- [ ] Implement. Detection for Automatic: `matchMedia('(update: slow)').matches || matchMedia('(monochrome)').matches || /\b(BOOX|Onyx)\b|NoteAir|NoteMax|Tab ?Ultra|Go ?10\.3|Palma|Poke ?\d|Nova ?\d|Leaf ?\d/i.test(navigator.userAgent)`. The settings line says which one won, e.g. "Automatic: e-ink screen found" / "Automatic: not an e-ink screen".
- [ ] E-ink CSS under `html.eink`: black text on white, 2px black borders instead of shadows and colour, no gradients, no `backdrop-filter`, `animation: none` and `transition: none` on everything, the scene layer hidden, reader text padding 32px at the sides (16px at 375px), line-height 1.6.
- [ ] Tests pass; commit.

### Task 2: Paged reading with edge taps (e-ink only)

**Files:** Modify `plugins/memory/page.js` (inside `sourceDetail`), `plugins/memory/page.css`; Test `tests/library-ui.test.js`.

**Interfaces – consumes:** `einkActive()`. **Produces:** `.lib-reader-text.paged`, a `.lib-page-status` line "Page P of N".

- [ ] Write failing tests (e-ink On, long fixture section): text is shown one screen at a time; a tap on the right 25% of the text goes to page 2 with no scroll animation; on the last page a right tap loads the next section at page 1; on page 1 a left tap loads the previous section at its last page; a section shorter than one screen shows "Page 1 of 1" and a right tap opens the next section; PageDown/PageUp and ArrowRight/ArrowLeft do the same with the text focused; a resize keeps the first visible character's page; with e-ink Off the old scrolling text and buttons are unchanged.
- [ ] Run and see them fail.
- [ ] Implement with CSS columns: the text box gets a fixed height (viewport height minus the reader tools, minimum 240px), `column-width` equal to its width, `overflow: hidden`; page = `scrollLeft` step of the box width, set without smooth scrolling. The middle 50% of the text does nothing on tap (leaves room to select text). The previous/next section buttons stay as the keyboard and screen-reader path.
- [ ] Tests pass; commit.

### Task 3: Places on the server

**Files:** Create `plugins/memory/places.py`; Modify `plugins/memory/plugin.py` (`get`/`post` take `who`); Test `tests/places_test.py`.

**Interfaces – produces:**
- `places.load(path, person) -> {'recent': [...], 'saved': [...]}`; rows `{'id', 'revision', 'offset', 'at'}` (`at` = server UTC ISO time), recent newest first (max 10), saved newest last (max 100).
- `places.put(path, person, kind, row) -> dict` (`kind` 'recent' or 'saved'; same id replaces; returns the new lists). Raises `ValueError` on a bad row.
- File `~/.local/share/argus-ui/mnemosyne-places.json`, `{person: {...}}`, written to a temp file then `os.replace`, one lock around read-modify-write; a broken file is moved aside as `mnemosyne-places.broken-<time>.json` and treated as empty.
- GET `library/places` → 200 `{'recent', 'saved'}`; POST `library/place` body `{'kind','id','revision','offset'}` → 200 the new lists, 400 `{'msg': 'Check the reading place.'}` on bad input.

- [ ] Write failing tests: round trip; same id replaces and moves to the front; limits 10/100; bad id, revision, offset, kind and extra-large bodies refused; two persons kept apart; broken file set aside and recovered; client-sent `at` ignored.
- [ ] Run `python -m pytest tests/places_test.py` (or the repo's runner) and see them fail.
- [ ] Implement; tests pass; commit.

### Task 4: The page uses synced places

**Files:** Modify `plugins/memory/page.js`; Test `tests/library-home.test.js`, `tests/library-ui.test.js`.

**Interfaces – consumes:** Task 3 endpoints.

- [ ] Write failing tests: a place saved in one browser context shows as "Continue reading" at the same section in a second context; Library home merges server and local recent rows by id (newer `at` wins; local rows without `at` lose to server rows); with the server answering 503 the old local behaviour holds and the status reads "Saved section N on this browser. Other devices get it when the server answers."; when the server accepted it: "Saved section N. Your other devices will open it here."; a changed revision still shows "Open updated document".
- [ ] Run and see them fail.
- [ ] Implement: `rememberRead` and Save place keep writing locally, then POST; home and `sourceDetail` read `library/places` once per visit to the Library (cached for the visit, refreshed by Library home).
- [ ] Tests pass; commit.

### Task 5: Side-index vibration (preview)

**Files:** Modify `plugins/memory/page.js` (preview link), `plugins/memory/reading-room-preview.html`; Test `tests/reading-room-preview-check.js`.

- [ ] Write failing tests (stub `navigator.vibrate`): with the switch off the link has no `vibrate` parameter and moving the rail never calls vibrate; with it on the link ends `?vibrate=1` and each change of the rail's value calls `navigator.vibrate(8)` once (not on every pointer move within the same letter); reduced motion does not change this (vibration is not motion).
- [ ] Run and see them fail.
- [ ] Implement; the real Library's future side index reads `readingPrefs().vibrate` the same way.
- [ ] Tests pass; commit.

### Task 6: Docs, version, release check

- [ ] `docs/mnemosyne-library.md` section; VERSION 4.67.0; CHANGELOG entry.
- [ ] `bash scripts/check-private.sh`; push; CI green (Linux tests + privacy).
- [ ] One fresh visual review of e-ink mode at 375px and 1404×1872 portrait (the 10.3-inch e-ink resolution) before asking the owner to try it on the e-ink tablet. Merge and deploy only after his yes.
