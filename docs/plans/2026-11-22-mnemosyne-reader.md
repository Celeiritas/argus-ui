# Mnemosyne reader implementation plan

Goal: Read reviewed source text within Mnemosyne and preserve file identity and extraction quality.
Architecture: SQLite retains exact text blocks alongside FTS passages. Readers pin a revision; original files stay outside the database under authenticated access. No inference or new dependencies.
Spec: docs/mnemosyne-library.md and the owner request for functional multi-format library organization.

- [ ] Validate explicit file-format metadata, invalid glyphs and optional physical PDF counts before publication.
- [ ] Add backward-compatible schema 2 reader blocks. Existing revision records remain immutable; old imports explain that reimport is needed.
- [ ] Add bounded revision-pinned read API and phone reader with previous/next controls. Render all text as plain text, never active HTML or Markdown.
- [ ] Test invalid imports leave the catalog unchanged, exact text and blank pages survive, large pages paginate, and old citations still read.
- [ ] Verify keyboard/mobile UI, errors and pinned navigation, run required checks, record release status.

Review focus: malicious markup, old databases, stale navigation responses, corrupt PDF page separators, and retired revisions. Format metadata describes a source; it does not promise an extractor exists. EPUB/tool selection research is separate from this foundation.
