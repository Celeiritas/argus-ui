# Mnemosyne DOCX staging implementation plan

**Goal:** Import supported Word text into the existing searchable SQLite library through reviewed staging.
**Architecture:** Optional python-docx runs only in the offline importer after bounded ZIP/XML preflight. Preserve the original and an exact text-offset map; emit the existing incomplete manifest contract. Search and reading use stored text without importing python-docx.
**Tech stack:** Python, python-docx 1.2.0 (MIT), existing SQLite/FTS5 catalog.
**Spec:** Owner's request for multiple file formats and licensable tools, plus docs/mnemosyne-library.md's reviewed-publication contract.

## Constraints and review focus
- No automatic publication, host dependency installation, original modification, or invented Word page numbers.
- Preserve paragraph/table order, nested cells and hyperlink text; offsets identify XML block/cell paths in the immutable original.
- Hold tracked changes, text boxes, notes/comments, fields, graphics/math, merged/omitted cells and numbered lists instead of silently losing their meaning.
- Reject unsafe/duplicate ZIP members, over-limit expansion, DTD/entities, excessive XML depth, and external relationships except non-fetched hyperlinks.
- Retain failure evidence and refuse existing staging destinations. Missing optional dependencies must produce an actionable held result.

## Task 1: bounded DOCX extraction and staging
Files: plugins/memory/docx_import.py; scripts/mnemosyne-docx.py; tests/docx_test.py; requirements-mnemosyne-docx.txt.
Interface: extract(path) returns title, authorship, source_version, extraction_version, text and locations (XML path, start/end character offsets). CLI writes original.docx, text.txt, locations.json, incomplete draft-manifest.json and READY-FOR-REVIEW.json; on failure retains HELD-FOR-REVIEW.json.
- [x] Write synthetic tests for ordering, hyperlinks, nested tables, offsets, malformed/unsupported content, bounds, missing dependency and CLI preservation.
- [x] Verify tests fail before implementation, implement preflight and python-docx traversal, then run all tests.
- [x] Publish only a synthetic fixture to a new temporary catalog; prove search and reader reconstruct the exact staged text with no physical pages.

## Task 2: integration and verification
Files: .github/workflows/tests.yml; tests/run.sh; docs/mnemosyne-library.md; VERSION; CHANGELOG.md.
- [x] Install optional test dependencies in CI; run DOCX tests in the full suite without skips.
- [x] Document installation, licenses, supported scope and held cases; bump to4.64.0.
- [ ] Run local importer/library/publication/EPUB suites, privacy and package checks. Review the final diff, push PR and wait for final Linux CI.

Execute in this session using the installed writing-plans skill's Leafy note. No UI changes or dependency on Word/LibreOffice. Rendering, phone upload, richer previews and exposing block locators in the reader remain later work.

Independent review found and regression-tested explicit-break word joining, alternate-main-part validation bypass, and corrupt-compression missing held markers. All19 DOCX tests pass after fixes; final Linux CI is required on the corrected commit.
