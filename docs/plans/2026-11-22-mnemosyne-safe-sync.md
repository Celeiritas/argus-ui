# Reviewed library publication implementation plan

**Goal:** Make repeat imports reviewable, reject stale updates, and preserve a verified SQLite recovery copy.
**Architecture:** Reuse prepared immutable revisions. SQLite BEGIN IMMEDIATE serializes writers while checking a review token, backing up through a separate read connection, and publishing the prepared records in one transaction. No timer or host change in this slice.
**Tech stack:** Python standard library, SQLite schema 2, existing catalog CLI.
**Spec:** docs/mnemosyne-library.md; owner's request to strengthen library organization and continue the task list.

## Constraints and review focus

- Private data stays local; no models, dependencies, service changes, deletions or public source fixtures.
- Review cannot create a missing database. Guarded repeat updates require schema 2; initial catalog creation retains the explicit bootstrap command.
- Changed source text, metadata or active catalog state invalidates the review token.
- Concurrent writers cannot apply two copies of the same review; competing writes and interrupted writes leave atomic catalog state.
- Missing/mismatched originals, incomplete inventories and backup failures stop publication; old revisions and other collections survive.
- Retirements and ready-to-held regressions are reported explicitly. A complete=true manifest remains an operator assertion, not proof a source drive was inventoried correctly.

## Tasks

1. Add tests/publication_test.py: five diff categories, stale text/catalog, concurrent same-token application, backup recovery, failed backup, transactional failure, incomplete inventory and original verification. Run before implementation to establish failure.
2. Refactor library.publish's writes into _write_records(connection, scope, records); retain its transaction for bootstrap/internal compatibility. Add review_publication(path, manifest, text_root, originals=None) and publish_reviewed(..., expected_plan, backup_dir, originals=None). Keep schema and reads unchanged.
3. Extend mnemosyne-catalog.py repeat-publication review/apply options; existing databases require --expect-plan and --backup for --apply. Add the suite to tests/run.sh. Update VERSION/CHANGELOG and reconcile older EPUB documentation/checkmarks.
4. Run publication/library/EPUB tests, privacy and build checks; inspect diff; push branch/open PR and wait for Linux CI. Record exact evidence and unfinished scheduler/phone work in the handoff. Merge/deploy requires the owner's release approval.
