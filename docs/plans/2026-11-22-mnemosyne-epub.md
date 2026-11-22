# EPUB ingestion implementation plan

Goal: Import reflowable EPUB text in spine order and read/search it with chapter locations.
Architecture: A bounded offline ZIP/XML adapter produces chapter text and a draft source record. The existing SQLite schema retains exact reader blocks; revision metadata maps passages and blocks to chapter members. No new runtime dependency or model.
Spec: docs/mnemosyne-library.md, W3C EPUB 3.3 spine ordering, and the owner's multi-format library request.

- [x] Implement/test bounded EPUB 2/3 extraction, spine order, plain text, and unsupported-content refusal.
- [x] Add chapter-aware manifest ingestion, explicit book kind, and revision-bound reader/search chapter labels without changing old database schemas.
- [x] Add a preview/staging CLI that retains originals, creates a new output directory, and never silently declares a whole collection complete.
- [x] Test end-to-end staged import and chapter navigation; run existing library/phone checks and independent visual review.
- [x] Update release docs, privacy-check and open a PR; deploy only with authorization.

Review focus: unsafe ZIP/XML, unsupported layout/math/encryption, duplicate/missing spine documents, old revisions, and chapter provenance. Synthetic EPUBs prove the initial subset; no actual EPUB was found in the established local research archive. Password-gated Wake-on-LAN work is separate.

Implementation and local/full Linux checks completed in PR77; release authorization and live verification are recorded in the private project handoff. Real-book acceptance remains separate.
