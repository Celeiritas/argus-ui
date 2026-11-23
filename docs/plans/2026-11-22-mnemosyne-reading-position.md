# Mnemosyne reading position implementation plan

Goal: resume an extracted-text section on this browser and jump directly to a section with compact phone controls.
Architecture: keep the existing SQLite read endpoint. Store only source ID, revision and section offset in a bounded browser-local record. Explicit Save place and Resume reading avoid overwriting a bookmark when opening a search match. No document text is stored.
Spec: docs/mnemosyne-library.md and the approved phone reader task.

## Constraints and review focus
44px controls, visible keyboard focus, 375px without overflow. No new runtime dependency. Positions are browser-local, not synchronized. Invalid storage, denied storage, failed reads, changed revisions and opening search matches must preserve reading and never jump to another document.

## Task: section bookmark and compact navigation
- [ ] Add browser regressions for save/reload/resume, revision isolation, corrupt/denied storage, failed requests, search-target precedence and section jumping.
- [ ] Implement bounded revision-keyed position storage in plugins/memory/page.js. Use explicit save/resume buttons and a collapsed navigation form with integer bounds from the read endpoint.
- [ ] Style wrapping controls and labels in plugins/memory/page.css; document scope and bump VERSION/CHANGELOG.
- [ ] Run production-asset fixture tests, fresh independent review and Linux CI; preserve all local tools and screenshots.

## Approved extension: Library home
- [ ] Default to ten distinct recently read sources, newest first; retain separate manual bookmarks.
- [ ] Resolve current metadata; never apply stale offsets to updated revisions or continue retired sources.
- [ ] Test history limits/order, read-only browsing, reload continuation, changed/retired sources, denied storage and navigation races.
- [ ] Preserve ordinary scrolling. Follow with tiered shelves/alphabet navigation backed by the full filtered catalog, not loaded cards.

## Verification
Implemented bookmarks, compact recent Home and safe section navigation. Both isolated browser suites passed against production assets, including 375px recent Home and 375/430/1440 reader checks. Independent code and fresh visual reviews found no remaining scoped blockers after fixes. Full Linux CI is required before release. The category/alphabet rail remains the next increment.
