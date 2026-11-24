# Mnemosyne book reader Implementation Plan

> **For agentic workers:** execute task by task in this session or with plain subagents (Leafy note: executing-plans / subagent-driven-development are not installed). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Open a library book's real EPUB or PDF inside Mnemosyne and read it page by page (tap the edges, swipe, Page Up/Page Down), e-ink friendly, with the reading place synced across Argus devices.

**Architecture:** A new reader page in the Memory plugin's folder `plugins/memory/reader/`, served on LeafyGrove's own origin through the plugin's open folder with a **strict** content policy (scripts from `'self'` only), renders the book with vendored foliate-js (pinned commit; EPUB natively, PDF through its bundled pdf.js 5.5.207). The page fetches the checked original from the server (`library/original.pdf`, new `library/original.epub`) and saves its place (an EPUB CFI plus a 0–1 fraction) through the existing `library/place` route.

**Tech Stack:** Python stdlib server, classic/ES-module browser JS, foliate-js (MIT) with zip.js (BSD-3-Clause), fflate (MIT), pdf.js (Apache-2.0); Playwright tests.

**Spec:** Dax's decisions, 2026-11-24 handoff `argus-ui-2026-11-24-v2.md` ("Reader direction: page-turning first for reading the book, EPUB/PDF inside Mnemosyne, tap-to-turn; permissive code only") and the 2026-11-23 DECISIONS entry in `hub/inbox/argus-ui.md` (e-ink: no animation, monochrome, paged reading with edge taps, bigger margins; reading-place sync across Argus devices only, no KOSync).

## Global Constraints

- Licences: MIT / BSD / Apache-2.0 only. No GPL/AGPL code (the Foliate *app* is GPL-3.0: never copy from it; foliate-js the library is MIT).
- foliate-js pinned at commit `78914aef4466eb960965702401634c2cb348e9b1` (2026-05-01); its `vendor/pdfjs` is pdf.js `5.5.207`. Every vendored file keeps its licence file; `plugins/memory/reader/vendor/THIRD-PARTY.md` lists each library, version and licence.
- The reader page's policy blocks every script that is not a file from `'self'`: no `'unsafe-inline'`, no `blob:` or `data:` in `script-src` (foliate-js README: "use CSP to block all scripts except 'self'").
- Book files: PDF ≤ 12 MB (existing `MAX_BYTES`), EPUB ≤ 64 MB (`epub.MAX_ARCHIVE`); both bound to the revision's SHA-256.
- Places: `offset` stays required (0–100000); new optional `cfi` (string, ≤ 1024 chars, starts with `epubcfi(`, only printable ASCII without `<>"'\``) and `fraction` (number 0–1). Same newest-save-wins rule.
- UI rules from `CLAUDE.md`: type 16/14/12 px, weights 400/600, 44 px hit areas, verb-first labels, visible focus, keyboard path, `prefers-reduced-motion`, no sideways scroll at 375 px.
- E-ink (`?eink=1` or the 4.67 setting): no page-turn animation, black on white, no shadows, margins ≥ 32 px.
- `VERSION` 4.69.0, `CHANGELOG.md` entry, Memory `plugin.json` version 1.4.0. Placeholders only in docs; `bash scripts/check-private.sh` before every push.

## Review Focus

1. **An EPUB that carries a script** (inline `<script>`, `onload=`, `<script src>`): nothing runs. Test in Task 4.
2. **A place saved on an older revision** (book republished): the reader opens at the start and says "This book changed since your saved place; starting at the beginning", never a wrong page. Test in Task 4.
3. **The server is down when the place is saved**: the place is kept on this device and sent later (same pending rule as the text reader), and the page says so. Test in Task 4.
4. **Rotation / resize on the tablet**: the same text stays in view (foliate relocates by CFI; we re-apply `lastLocation`). Test in Task 4.
5. **A book with no original on the host, or one over the size limit**: no "Read book" button; the text reader stays. Test in Task 5.

---

### Task 1: Server gives EPUB originals

**Files:**
- Modify: `plugins/memory/library.py` (`original_file`, `api`)
- Modify: `server/argus_ui.py` (`PLUGIN_FILE_TYPES`)
- Test: `tests/library_test.py`, `tests/plugins.test.js`

**Interfaces:**
- Produces: `original_file(path, root, sid, revision='', kind='pdf') -> (name: str, raw: bytes)`; `kind` is `'pdf'` or `'epub'`. Route `GET api/memory/library/original.epub?id=&revision=` answers `(200, raw, {'type': 'application/epub+zip', 'name': name})`.

- [ ] **Step 1: Failing tests** in `library_test.py`: `test_original_epub_checked_and_bound_to_revision` — a fixture EPUB original with matching SHA returns its bytes; wrong SHA → `ValueError`; a `.pdf` asked as `epub` → `ValueError`; bytes not starting with `PK\x03\x04` → `ValueError`; over 64 MB (patch the limit to 10 bytes) → `ValueError`. In `plugins.test.js`: the demo server plugin answering `application/epub+zip` passes with `nosniff` and `inline`.
- [ ] **Step 2: Run** `python tests/library_test.py` → the new test FAILS.
- [ ] **Step 3: Implement** `kind` in `original_file` (suffix, magic bytes, limit per kind); add the `library/original.epub` branch in `api`; add `'application/epub+zip'` to `PLUGIN_FILE_TYPES`. `prepare()` already accepts any relative original; leave it.
- [ ] **Step 4: Run** `python tests/library_test.py` → OK (26 tests).
- [ ] **Step 5: Commit** `Mnemosyne: serve checked EPUB originals (library/original.epub)`.

### Task 2: Places remember a book location

**Files:**
- Modify: `plugins/memory/places.py` (`_row`, `put`), `plugins/memory/plugin.py` (`post` for `library/place`)
- Test: `tests/memory_test.py`

**Interfaces:**
- Produces: a place row `{'id','revision','offset','at'[, 'cfi': str][, 'fraction': float]}`. `put(path, person, kind, row)` keeps `cfi`/`fraction` when valid, refuses the row (ValueError) when present and invalid.

- [ ] **Step 1: Failing tests** `test_place_keeps_valid_cfi_and_fraction` (`cfi='epubcfi(/6/4!/4/2/1:0)'`, `fraction=0.25` round-trip through `put`/`load`), `test_place_refuses_bad_cfi` (`'<script>'`, 1025 chars, `'epubcfi(x)"'`, `fraction=1.5`, `fraction=True` → ValueError), `test_old_rows_without_cfi_still_load`.
- [ ] **Step 2: Run** `python tests/memory_test.py` → FAIL.
- [ ] **Step 3: Implement** in `_row`: `CFI = re.compile(r'^epubcfi\([\x21-\x7e]{1,1015}\)$')` minus the characters `<>"'\``; `fraction` must be `float`/`int` (not bool) in [0, 1]. Pass both from the POST body in `plugin.py`.
- [ ] **Step 4: Run** `python tests/memory_test.py` → OK.
- [ ] **Step 5: Commit** `Mnemosyne places: optional book location (cfi, fraction)`.

### Task 3: A strict open folder, and foliate-js vendored

**Files:**
- Modify: `server/argus_ui.py` (`STRICT_FOLDER_HEADERS`, `plugin_file`, manifest field `open_folder_policy`; `mimetypes.add_type('text/javascript', '.mjs')`)
- Modify: `plugins/memory/plugin.json` (`"open_folder": "reader", "open_folder_policy": "strict"`, version 1.4.0)
- Create: `scripts/vendor-foliate.sh` (downloads the pinned commit's files listed below from GitHub's codeload tarball, checks the tarball SHA-256 written in the script, copies into `plugins/memory/reader/vendor/foliate-js/`)
- Create: `plugins/memory/reader/vendor/THIRD-PARTY.md`
- Modify: `docs/leafy-plugin.md` (the `open_folder_policy` field)
- Test: `tests/plugins.test.js`

**Interfaces:**
- Produces: files under `plugins/memory/reader/` are served at `<base>/plugins/memory/reader/...` with `STRICT_FOLDER_HEADERS`:
  `default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self' 'unsafe-inline' blob:; img-src 'self' data: blob:; font-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self' blob: data:; worker-src 'self' blob:; frame-src 'self' blob:; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'self'` plus the other `OWN_HEADERS` (nosniff, CORP same-origin, COOP, `X-Frame-Options: SAMEORIGIN`).
- Vendored file set: `view.js epub.js epubcfi.js paginator.js fixed-layout.js pdf.js progress.js overlayer.js text-walker.js footnotes.js search.js comic-book.js fb2.js mobi.js uri-template.js LICENSE vendor/zip.js vendor/fflate.js vendor/pdfjs/{pdf.mjs,pdf.worker.mjs,cmaps/,standard_fonts/}` (no `.map`, no `reader.html/js`, no `ui/`, no `tts.js`, no `dict.js`, no `opds.js`).

- [ ] **Step 1: Failing test** in `plugins.test.js`: a fixture server plugin with `open_folder_policy: "strict"` answers a file in that folder with exactly the CSP above; with the field missing or any other value it keeps the 4.47 `OPEN_FOLDER_HEADERS`; a `.mjs` file answers `text/javascript`.
- [ ] **Step 2: Run** `bash tests/run.sh plugins` (Linux/CI) → FAIL.
- [ ] **Step 3: Implement** the headers and the field; run `bash scripts/vendor-foliate.sh`; write `THIRD-PARTY.md` (library, commit/version, licence, upstream URL).
- [ ] **Step 4: Run** `bash tests/run.sh plugins` → PASS; `bash scripts/build.sh` → the tarball contains `plugins/memory/reader/vendor/foliate-js/view.js`; `bash scripts/check-private.sh` → nothing found.
- [ ] **Step 5: Commit** `Strict open folder policy; vendor foliate-js 78914ae (MIT) with pdf.js 5.5.207`.

### Task 4: The reader page

**Files:**
- Create: `plugins/memory/reader/index.html` (no inline script or style attribute handlers), `reader.js` (ES module), `reader.css`
- Create: `tests/fixtures/books/make-books.py` (writes `tiny.epub`: 3 chapters of ~2000 words, chapter 2 contains `<script>window.parent.BAD=1</script>`, an `<img onerror="window.parent.BAD=2" src="x">` and `<script src="evil.js">`; `tiny.pdf`: 3 pages, stdlib only), generated at test time, not committed as binaries
- Test: `tests/library-reader.test.js`, entry in `tests/run.sh` under `memory`

**Interfaces:**
- Consumes: `library/original.{epub,pdf}` (Task 1), `library/places` + `library/place` with `cfi`/`fraction` (Task 2), the strict folder (Task 3).
- Produces: the URL `plugins/memory/reader/?id=<64hex>&revision=<64hex>&format=epub|pdf[&eink=1]`, opened by Task 5.

Behaviour the tests pin (each a `check(...)` in `library-reader.test.js`, 375×812 and 1404×1872 e-ink viewport, `reducedMotion: 'reduce'` and not):
- [ ] **Step 1: Failing tests:**
  - opens `tiny.epub`, shows chapter 1 text, header shows the title and `Page n of N`-style progress from `fraction` ("12% read");
  - tap at x = 90 % of width → next page (the first visible word changes); x = 10 % → previous; tap in the middle third → toggles the top bar (Back to library, title, progress), nothing turns;
  - `PageDown`, `ArrowRight`, `Space` → next; `PageUp`, `ArrowLeft` → previous; a horizontal swipe ≥ 40 px turns;
  - e-ink (`?eink=1`): paginator has no `animated` attribute, computed background `rgb(255, 255, 255)`, text `rgb(0, 0, 0)`, no box-shadow on the bar, side margin ≥ 32 px; not e-ink and not reduced motion: `animated` set;
  - `window.BAD` is undefined after paging through chapter 2 (Review Focus 1) and the console shows the CSP refusal;
  - after a turn, within 2 s a POST `library/place` carries `kind:'recent'`, `cfi` starting `epubcfi(` and `0 < fraction < 1`; reopening the URL lands on the same first word;
  - a saved place with an older `revision` → opens at the start and shows "This book changed since your saved place; starting at the beginning." (Review Focus 2);
  - place POST answering 503 → `"Place kept on this device; it will sync when the library answers."` and the row stays in `localStorage` with `pending:true`; the next successful POST clears it (Review Focus 3);
  - resize 375×812 → 812×375 keeps the first visible word (Review Focus 4);
  - opens `tiny.pdf`: page 1 drawn on a canvas, next turns to page 2, place saved with a `cfi`;
  - a 404/400 from the original route → "This book's file is not on the server. Read its text in the library instead." with a Back to library link; no page errors anywhere;
  - 375 px: no sideways scroll; every control ≥ 44 px.
- [ ] **Step 2: Run** `bash tests/run.sh memory` → FAIL.
- [ ] **Step 3: Implement** `reader.js`: read the query (validate both ids with `/^[a-f0-9]{64}$/`, format in `{epub,pdf}`), `fetch` the original as a `File`, `import './vendor/foliate-js/view.js'`, create `<foliate-view>`, `view.open(file)`, `renderer.setAttribute('flow','paginated')`, max one column, margins from CSS vars; turn with `view.goLeft()/goRight()` (respect `dir`); on `relocate` debounce 1500 ms then POST place `{kind:'recent', id, revision, offset:0, cfi, fraction}` (keep the 4.67 pending/local rule: mirror `page.js` `keep()` row shape with `cfi`/`fraction` added); on `visibilitychange` hidden send immediately. Start at the newest of local vs server row for this id **and revision**; e-ink from `?eink=1` or the stored 4.67 setting key. Back to library = link to `<base>/memory`.
- [ ] **Step 4: Run** `bash tests/run.sh memory` → PASS.
- [ ] **Step 5: Commit** `Mnemosyne reader: EPUB and PDF in pages, edge taps, e-ink, synced place`.

### Task 5: "Read book" in the library, docs, version

**Files:**
- Modify: `plugins/memory/page.js` (`sourceDetail`, recent rows), `plugins/memory/page.css`
- Modify: `docs/mnemosyne-library.md` (new section "Reading the book itself"), `CHANGELOG.md`, `VERSION` → 4.69.0
- Test: `tests/library-ui.test.js`, `tests/library-home.test.js`

**Interfaces:**
- Consumes: the reader URL from Task 4; source fields `original`, `file_format`.

- [ ] **Step 1: Failing tests:** a source with `original` and `file_format: 'epub'` (or a `.pdf` original) shows a **Read book** link (first action, ≥ 44 px) to `plugins/memory/reader/?id=…&revision=…&format=…` plus `&eink=1` when e-ink is on; a source without `original` shows none (Review Focus 5); a recent row that has a `cfi` reads "Book · 34% read" and its Continue opens the reader, not the text reader; "Open original PDF" stays.
- [ ] **Step 2: Run** `bash tests/run.sh memory` → FAIL.
- [ ] **Step 3: Implement** the link and the recent-row wording; docs + CHANGELOG (name the licences and the pinned commit); VERSION 4.69.0.
- [ ] **Step 4: Run** the full `bash tests/run.sh` on a `ci/` branch or the PR → all suites pass; `python tests/library_test.py` and `python tests/memory_test.py` OK locally.
- [ ] **Step 5: Commit** `Mnemosyne 4.69.0: Read book opens the EPUB/PDF reader`, open the PR, then one fresh-picture review (phone + e-ink viewport) before asking the owner to test on the e-ink tablet and {{PHONE}}.
