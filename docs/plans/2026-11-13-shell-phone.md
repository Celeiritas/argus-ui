# Shell at phone size (4.44.0) Implementation Plan

> **For agentic workers:** executed in one session by builder E2 (native). Steps use checkbox (`- [ ]`) syntax.

**Goal:** the 13 phone-size and layout items of the field audit (inbox line "shell slice"), the flaky layout test, and a
way to Phone alerts at every width.

**Architecture:** page-only changes in `web/` (strip, Today, header, fonts), two small server additions (`now` and `media`
in `state()`, owner only), one build step (fonts folder, the Run tool's picture), tests beside each fix.

**Tech Stack:** Python stdlib server, classic browser scripts, Playwright tests through `tests/run.sh`.

**Spec:** `BRIEF-E2-phone-size.md` (hub reports folder, not in the repo) and the A2 field audit it quotes.

## Global Constraints
- VERSION 4.44.0, CHANGELOG entry. Type 16/14/12 px, weights 400/600, 44 px hit areas, verb-first labels, visible focus,
  keyboard path, `prefers-reduced-motion`, no sideways scroll at 375.
- No new icon or drawing. Public text uses `{{SERVER}}`-style placeholders; no addresses, names or ports in the repo.
- POST stays JSON-only; `esc()` everything put into HTML. Nothing fetched from a third party on load.

## Review Focus
1. A section the owner is on that sits inside More (Phone alerts, a folded pill): More must say so (`.on`, read out).
2. Resizing between phone, sideways and 1920: pills come back out of More, nothing stays hidden.
3. A learner: no More pill when it would be empty, no now line, no media rows.
4. A bad `media.json` / `realm.json` (not JSON, http://, a list): no rows, the default name, never a crash.
5. The font arriving late (swap): the strip measures again when it lands.

---

### Task 1: the flaky layout test (item 11)
**Files:** `tests/layout.test.js`
- [ ] Probe the cause: `locator.first().evaluate` resolves a handle, then evaluates; Today's second draw
  (`askStatus().then(draw)` replaces `#main`) can land between, so the rect is of a detached node (all zeros).
- [ ] `box()` becomes one `page.evaluate` (query and measure in the same task); the phone check waits until Today has
  settled (no "Checking…", no "Asking every section…") and measures `.needs` and `.places` in one call.
- [ ] Run `bash tests/run.sh layout` 20 times in a row; count the passes.

### Task 2: Today (items 2, 5, 8; 7 checked)
**Files:** `web/js/home.js`, `tests/home.test.js`, `docs/home.md`
- [ ] Test: a section with a needs row on Today has no card under Sections (fixture: Heracles needs you; Watch's failures).
- [ ] Test: no `#places-h` when no card is left (a learner whose only section needs her, or via `S` in the page).
- [ ] Test: Playground has a card (`place('Playground').count() === 1`).
- [ ] `cards()`: skip `e.id` when a needs row has `of === e.id`; keep Olympus (line "Open it"); `draw()` writes the
  Sections block only when `cards()` is not empty.
- [ ] Item 7: 4.38.0 made the row "Today | Study | Lessons"; the deck chooser is still labelled "Study". Rename it "Deck"
  (`plugins/mentor/page.js`), test in `tests/mentor.test.js`. Anything deeper in Mentor's study screens stays out.

### Task 3: header line (item 6)
**Files:** `web/css/argus.css`, `tests/layout.test.js`
- [ ] Not reproduced with Nunito or without it at 412/360/375 (owner and learner, long weather words). The H2 picture had
  a wider fallback font. Harden: `.title{min-width:0}`, `.title .sub{overflow-wrap:anywhere}`.
- [ ] Test: with a long unbreakable weather word (route `api/sky`), `#sub`'s text stays inside the screen at 412 and 360.

### Task 4: the strip (items 1 and 12)
**Files:** `web/index.html`, `web/js/core.js`, `web/css/scene.css`, `tests/layout.test.js`, `tests/nav.test.js`,
`tests/phone-alerts.test.js`, `docs/home.md`
- Interfaces: `#realmMore` (button, `data-more`, `aria-controls="moreSheet"`), `drawMore()` fills `#moreList` /
  `#moreAway` for whichever More is showing; `.realm.over` = a pill folded into More.
- [ ] Tests: at 915x412 and 800x360 the bar is one row inside the screen, nothing under Mute, `scrollWidth <= clientWidth`;
  at 1024/1440/1920 `#realmMore` is visible and its sheet has Phone alerts; at 1920 the pills keep their second lines;
  a folded pill comes back when the window widens; on `/phone` the More pill is `.on` and says so.
- [ ] Code: More pill after the pills; Phone alerts, links to other pages and coming-later pills always in More;
  `fitRealms()` = compact, then bare, then fold pills from the end (never the first or the current one); scroll mode, its
  wheel handler and `realmsAt` go. One click handler for both More buttons; focus returns to the opener on close.
  `document.fonts.ready` and the weather call `fitRealms()` again.

### Task 5: one Zeus on the Run tool (item 9)
**Files:** `web/index.html`, `scripts/build.sh`, `tests/watch.test.js`
- [ ] Test: `#boltHome img#bolt` shows `static/icons/zeus.png` (leafy-realm theme); dragging still runs a task.
- [ ] The inline bolt sits between `<!--BOLT-->` comments; build.sh swaps it for the theme's `icons/zeus.png` when the
  theme has one (the starter theme keeps the bolt). The thrown bolt (`BOLT_SVG`) is an effect and stays.

### Task 6: fonts from the page (item 10)
**Files:** `web/fonts/` (woff2 + `OFL.txt`), `web/css/argus.css`, `web/index.html`, `scripts/build.sh`,
`server/argus_ui.py`, `tests/fonts.test.js`, `tests/fonts_test.py`
- [ ] Tests: no request leaves 127.0.0.1 on load; `document.fonts.check('600 16px Nunito')`; `static/fonts/*.woff2` is
  `font/woff2` with `public, max-age=31536000, immutable`.
- [ ] Nunito latin + latin-ext (variable, 400-600) with hashed names, `@font-face` with `font-display:swap`, the Google
  link removed, build.sh copies `web/fonts`.

### Task 7: what the server is doing, and Jellyfin / Audiobookshelf (items 3, 4)
**Files:** `server/argus_ui.py`, `web/js/home.js`, `web/css/argus.css`, `tests/today_test.py`, `tests/run.sh`,
`tests/home.test.js`, `docs/home.md`
- Interfaces: `state()['now']` (str), `state()['media']` (list of `{id, name, what, href}`); `server_name()`,
  `now_line(jobs)`, `media()` in the server; env `ARGUS_MEDIA`, `ARGUS_GAMEGUARD`, `LEAFY_REALM`.
- [ ] Python tests: calm; busy (a timer's run, a transient run; never an always-on service); game (record lists
  `mnemosyne-ollama` -> "the local AI is paused"; the alert file alone -> "a game is running"); the name from
  realm.json (any case of SERVER), default "The server"; media: https only, known keys only, no file -> none; a learner's
  state has neither key.
- [ ] Page: the now line under the state heading (in place of "The realm is quiet."); media rows in Open with
  `rel="noopener noreferrer"`, none without the file.

### Task 8: version, docs, proof
- [ ] VERSION 4.44.0, CHANGELOG, docs/home.md; `bash scripts/check-private.sh origin/main..HEAD`; push; PR; CI; after
  pictures; report.
