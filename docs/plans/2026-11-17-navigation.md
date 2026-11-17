# One way to each place (4.54.0) Implementation Plan

> **For agentic workers:** executed in one session. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Today shows only what needs you and one line per section with news, at every width; the computer's top bar and the
phone's bottom bar plus More do all the navigating (no Open chips, no Sections tiles on Today).

**Architecture:** `sections()` in `web/js/core.js` stays the one list of places. A links.json entry with `"section": true`
becomes a place on the strip (computer) and a section row in More (phone). More gets four parts: sections (each with its live
line and count), Media, Other pages, Settings. Today (`web/js/home.js`) draws one layout at every width. Edit Today keeps its
three lists; its "Open" list becomes "Links in More".

**Tech Stack:** Python stdlib server, classic browser JS in one global scope, Playwright tests on Linux CI (`tests/run.sh`).

**Spec:** the owner's navigation brief (his decisions of 2026-11-16; kept outside the repository) and the visual review of
4.52.0, items 5, 7, 10-14. These override docs/home.md "Sections or Open (4.45.0)".

## Global Constraints
- VERSION 4.54.0, a CHANGELOG entry; docs/home.md says the new rules.
- Placeholders only: the real Tactylos Studio path (today in the host's links.json) is never in the repo; tests use `/studio-test/`.
- UI rules: type 16/14/12 (h1 24 and h2 18 are named exceptions), weights 400/600, 44 px targets, verb-first buttons, visible
  focus, no sideways scroll at 375.
- Nothing on the host is changed by this branch. The host step (below) is for the owner's session, with his yes.
- `bash scripts/check-private.sh` before every push.

## Decisions settled here
1. **A section that opens elsewhere** is configured in links.json, never in the repo: `{"name": "...", "what": "...", "href": "...", "section": true}`.
   The server's `links()` passes `section` through (true only for JSON `true`). Its name is links.json's `name`, or the owner's
   rename in Edit Today (`open.names`, as for any link). Its place: after the plugin sections, so on a narrow strip it is the
   first to fold into More. On the strip it is a pill with class `realm link` and the opens-elsewhere mark (`LINK_MARK`), read
   out as "…, opens another page". On a phone it is a row in More's sections list.
   **Host step (needs the owner's yes):** in the host's `~/.config/argus-ui/links.json`, rename the Sound Lab entry
   to `"name": "Tactylos Studio"` and add `"section": true`, keeping its `href` as it is.
2. **More** (`#moreSheet`), top to bottom:
   - the sections list `#moreList` (phone: every place not in the bottom bar; computer: the pills folded off the strip). Each
     row: mark, name, its live line (`placeLine(e)`, 12 px), and its count badge (gold: waits for you; red: Argus failed).
   - **Media** `#moreMedia` (heading `#moreMediaH`): media.json's players other than one that is also a section (Mealie has its
     own section), plain links with `rel="noopener noreferrer"`, the opens-elsewhere mark, the "what" line.
   - **Other pages** `#moreAway`: links.json entries that are not sections, in the owner's order, under his names.
   - **Settings** `#moreSetH`, list `#moreSet`: Phone alerts (owner), Mute sounds (`#muteMore`, phone only; the computer's
     strip has its own), Edit Today (`#editToday`, owner only).
   A group of links (links.json or Edit Today) is no longer drawn: More's list is short and each row says what it is.
3. **Edit Today from More**: on Today it closes More and starts editing; elsewhere it goes to Today (`<base>/#edit`) and starts
   there. Done or Cancel gives the keyboard back to the More button that is showing.
4. **Today, one layout at every width:** the people/today problem line, then what needs you (solid card, `.needs.first`) or the
   calm band (Nothing needs you + the server's line), the devices line, then one line per section with news (`.qline`, ending in
   the shared `CHEVRON`). "News" = a shown section (Edit Today's Sections list) whose server status has a line, that is not a
   row above. Argus (its news is the rows), Olympus and static plugins get no line. No Open, no tiles, no Edit Today on Today.
   The computer's `.home` is one column (max 880 px) at every width.
5. **Needs order by consequence:** a stable sort by `needRank(of)`: troubleItems (failures, alerts) 0, `memory` (data) 1,
   `throne` (deploys) 2, everything else 3. In code so it can be checked.
6. **Visual leftovers:** #5 a need's text: first sentence 16 px, the rest under it 14 px (`.ndetail`). #7 moot (no Open).
   #10 h1 24/h2 18 written into docs/ux-audit-4.1.md as the named exceptions. #11 a test fixture (left). #12 the qline chevron.
   #13 the mode switch's hold ring shows only while held (plain segments). #14a the fixture's hyphen becomes a colon.
   #14b `.fold-go` becomes the same SVG `CHEVRON` (16 px). #14c an event's full date hidden on a phone (`title` keeps it).

## Review Focus
- A links.json `section` that is a string `"true"` or a number: not a section (server test).
- No media, no links, a learner: More shows no empty headings; a learner has no Settings rows except Mute on a phone.
- Edit Today pressed from More on another page: lands on Today in edit mode, once (a reload does not re-open it).
- A section link while you are on it cannot be "current" (it leaves LeafyGrove): it never takes `.on`.
- A long Tactylos name at 1024: the strip still one row (it folds into More).

---

### Task 1: server `section` flag
**Files:** `server/argus_ui.py` `links()`; test `tests/today_test.py` or a new block in the links server test.
- [ ] Test: links.json with `section: true`, `"true"`, `1`, missing → state links carry `section` True only for the first.
- [ ] `links()` adds `'section': x.get('section') is True` to each kept entry.
- [ ] Run `python tests/<file>.py`; commit.

### Task 2: places and More (core.js, index.html, scene.css)
**Interfaces produced:** `placeLine(e) -> string` (Argus/Olympus/plugins, as the old tiles), `CHEVRON` (svg string),
`needRank(of) -> 0..3`, `sections()` entries for section links: `{id:'link-i', kind:'link', section:true, href, word, realm:'', mark:LINK_MARK}`.
- [ ] Strip: `(!e.kind || e.section) && e.id !== 'phone'`; More on the strip: folded, phone, non-section links, media, settings.
- [ ] `row(e)` shows `placeLine(e)` as its small line for sections.
- [ ] index.html: `#moreMediaH/#moreMedia`, `#moreAwayH/#moreAway`, `#moreSetH/#moreSet` (Phone alerts row, `#muteMore`, `#editToday`).
- [ ] `#editToday` click: close More; on Today `todayEdit.start()`, else go to `url('') + '#edit'`.

### Task 3: Today (home.js, argus.css)
- [ ] `draw()`: one path; remove `opens()`, `cards()`, `fitLines()`, the places panel; `newsLines()` replaces `quietLines()`.
- [ ] `needs()` sorted by `needRank`; `row()` splits the first sentence.
- [ ] CSS: `.home` one column; qline chevron; `.ndetail`; mode ring; `.fold-go` svg; `.ew .exw` hidden under 600 px.

### Task 4: Edit Today (today-edit.js)
- [ ] Sections list hint: "Shown: its line on Today when it has news." Open list → "Links in More": name and order only (no Show,
  no Group; the group code goes). `layout()` sends `open.order/names` only. `stop()` focuses the visible `[data-more]`.
- [ ] On Today with `location.hash === '#edit'`: start once, then drop the hash.

### Task 5: tests
- [ ] New `tests/navigation.test.js`: at 412, 1024, 1440, 1920 with a section link `/studio-test/`, two players and one plain link:
  Today has no `.open`, `.places`, `#editToday`; the strip (computer) has the Tactylos pill with `.link` and no media; More's
  parts in order; Settings rows; Edit Today from More and focus back; needs order (memory above chiron); the qline chevron;
  no sideways scroll at 375. Shots: `nav-phone-today-calm`, `nav-phone-today-needs`, `nav-phone-more`, `nav-1440-today`,
  `nav-1920-bar`.
- [ ] Update home, today-edit, today-layout, phone-first, nav, layout, quiet, devices, phone-alerts tests for the new model.

### Task 6: docs, version, PR, pictures, report
- [ ] VERSION 4.54.0, CHANGELOG, docs/home.md (Today, On a phone, Sections or Open replaced by "One way to each place", Edit
  Today, Links), docs/ux-audit-4.1.md (type exceptions).
- [ ] check-private, push, PR, CI green; pictures through ci/phone-shots; report.
