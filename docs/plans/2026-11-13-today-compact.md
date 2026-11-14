# Today, compact and clear (4.45.0) Implementation Plan

> Executed natively in one builder session (Leafy note: no executing-plans skill). Steps use checkboxes.

**Goal:** Sections become compact tiles, the server's line becomes a band in the theme's colours, Open gets group
labels, and the strip's badge gets room, without touching Watch, Study, Approvals or Phone alerts.

**Architecture:** The server adds two small fields (`now_name`, a link's `group`) and cuts status v2 text at a word.
The theme may carry a `colors` map that `scripts/build.sh` writes into the page as CSS custom properties; `argus.css`
holds neutral fallbacks. `home.js` draws the band, the tiles and the Open groups; a small `fitLines()` cuts a tile's
line at a word after layout.

**Tech Stack:** Python stdlib server, classic JS, CSS, Playwright tests through `tests/run.sh`.

**Spec:** the owner's brief "E3 today compact" (kept outside the repo, with the common builder brief).

**As built:** the checks went into a new `tests/today-layout.test.js`; tiles use `minmax(136px,1fr)` (176 px from 601 px);
on a phone the panels sit 12 px apart instead of 16 px, so Today fits at 412 x 915 with the sections' own lines too.
After the fresh visual review: the strip's count stays where it was on 4.44.0 (Task 6's right-anchored count covered the
gods' faces) and the label is moved 4 px right (a transform, so the pill keeps its width) only while a count shows; Open's groups sit side by side where they fit; the
labels use `--frost`; tile words line up at the top; tiles are at least 220 px from 1200 px; " · " keeps its dot with a
no-break space.

## Global Constraints
- VERSION 4.45.0 and a CHANGELOG entry. Type 16/14/12 px, weights 400/600; 44 px hits; visible focus; reduced motion;
  no sideways scroll at 375.
- The repo never writes the server's real name; placeholders only. No new icon or drawing.
- Open chips keep their size, shape and spacing. `LINK_MARK` is already the "opens elsewhere" cue.
- Band colours (leafy-realm): bg `#3a2a5e`, border `#5b4a85`, name `#7bd88f` (600), words `#cbb8ff` (400), 16 px.
  Every text colour reaches 4.5:1 on its background.

## Review Focus
1. A server name with a colon, or no realm.json: the band falls back to plain text and `now` stays the same string.
2. A status line of one long word (no space): the tile cuts it with an ellipsis, never overflows sideways.
3. Two-digit badge ("12") in the strip: still clear of the label.
4. Open with only media, or only ungrouped links: no label (one group looks like 4.44.0).
5. A theme without `colors` (starter): neutral band, still readable.

---

### Task 1: Server fields and word cut
**Files:** `server/argus_ui.py` (links, now_line, state, status v2), `tests/today_test.py`, `tests/bundled.test.js`.
- Produces: `state()['now_name']` (owner only, same name `now` starts with); `links()` entries carry `group` (str, may
  be empty, 40 chars max); `clip(s: str, n: int) -> str` cuts at a word and ends with "…" (total <= n).
- [ ] Tests: `NowName.test_name_matches_now` (`now.startswith(now_name + ': ')`), `test_learner_has_no_now_name`,
  `LinkGroup.test_group_kept_and_cut`, `Clip.test_word_cut` ("Log a workout and more words than fit", 32 ->
  "Log a workout and more words…"), `Clip.test_one_long_word`.
- [ ] bundled.test.js expects "Log a workout and more words…".

### Task 2: Theme colours
**Files:** `scripts/build.sh`, `web/index.html` (`<!--THEME-COLORS-->` after the stylesheets),
`themes/leafy-realm/theme.json`, `web/css/argus.css` (`:root` fallbacks), `docs/themes.md`.
- Allowed keys: `server-bg`, `server-border`, `server-name`, `server-words`; values `#rgb` or `#rrggbb`; anything else
  stops the build with a message.
- [ ] Build both themes; leafy-realm's page has the `<style>`, starter's has none.

### Task 3: The band
**Files:** `web/js/home.js`, `web/css/argus.css`.
- `<p class="now"><b class="nowname">NAME</b><span class="nowwords">: words</span></p>` when `S.now_name` matches the
  start of `S.now`, else the plain string. Full width of `.home` (grid-column 1/-1), same left edge as the panels.

### Task 4: Section tiles
**Files:** `web/js/home.js` (`cards()`, `fitLines()`), `web/css/argus.css`.
- Grid `repeat(auto-fill, minmax(150px, 1fr))`; tile: 32 px mark, word 14/600, line 12/400 up to two lines, min 44 px.
- `.pl` is `aria-hidden`; an `.sr` span carries the whole line. `fitLines()` cuts at a word + "…" when two lines
  overflow; reruns on resize and `document.fonts.ready`.

### Task 5: Open groups
**Files:** `web/js/home.js` (`opens()`), `web/css/argus.css`, `docs/home.md`.
- Order: "Watch and listen" (media), link groups by first appearance, then the default "Other pages". Labels
  (`h3.opengroup`, 12/600) only with two or more groups; each group its own `ul.openlist`.

### Task 6: Strip badge room
**File:** `web/css/scene.css`: `.realm .dot` anchored by its right edge at 42 px (`transform:translateX(-100%)`), so
any count ends 6 px before the label (4 px past its 2 px ring).

### Task 7: Checks (fail on 3e9de5d, pass on head)
**File:** `tests/layout.test.js` (new block) and `tests/home.test.js` (band split, groups).
- Two tiles per row at 412 and 360; fit at 412x915 with the fixture (or the measured height); no mid-word cut
  (every visible `.pl` text is a prefix of the full line ending at a word or "…"); band contrast from computed styles
  >= 4.5 and band width = `.home` width; last element of each page clear of `.tabbar` at 360x800; strip badge gap
  >= 6 px at 915x412; group labels only with two or more groups; no sideways scroll at 375.

### Task 8: Docs, version, proof
- docs/home.md: the rule, groups, band, integrations; VERSION 4.45.0; CHANGELOG.
- Before/after pictures and close-ups, base proof, check-private, PR, CI, report.
