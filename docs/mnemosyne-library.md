# Mnemosyne library: first catalog release

The Memory plugin now presents search first, with native keyboard-accessible disclosures for filters, full passages and source details. Backup health stays visible; controls/history start folded when healthy and open when attention is needed. A user's choice to collapse them survives refreshes. Search text and results are not redrawn by backup polling.

This is an opt-in catalog, not an automatic migration. The legacy embedding database, originals and installed models stay untouched. No model is loaded or called. The new `library/ask` route returns 410; this does not shut down any separately installed legacy service.

## Publish a collection

Use a **new** SQLite file, distinct from the legacy index. The server defaults to `library.sqlite` in the Memory plugin's private data directory, or `ARGUS_LIBRARY_DB`. PDF originals live under its `originals` folder or `ARGUS_LIBRARY_ORIGINALS`. All library routes inherit the plugin's owner-only access rules. Do not put private manifests, extracted text, databases or PDFs in git.

Prepare a manifest from explicit source inventory, not filename guesses:

```json
{
  "schema": "mnemosyne-manifest/1",
  "complete": true,
  "collections": ["research"],
  "sources": [{
    "collection": "research", "key": "stable-source-key",
    "title": "Example paper", "kind": "paper", "authorship": "Example author",
    "health": "ready", "text": "example.txt", "page_scheme": "pdf",
    "source_version": "1", "extraction_version": "reviewed-extraction-1"
  }]
}
```

Validate with `python scripts/mnemosyne-catalog.py --db <new-catalog> publish <manifest.json> --text-root <extracted-text-root>`. Add `--apply` to publish. Validation alone does not create a database. Publication validates every record before changing the catalog, then updates all declared collections in one transaction. Sources omitted from a declared complete collection become inactive; other collections and previous revisions remain. Never mark a partial inventory complete.

`kind` is one of `paper`, `book`, `summary`, `note`, `guide`, `learning`, `unknown`. `health` is `ready`, `pending`, `failed`, `suspect`, `catalog-only`, or `unknown`. Record extraction problems in `diagnostic`; suspect/failed sources remain browsable but are not searched. Do not supply damaged text: invalid UTF-8, replacement characters and NULs reject publication. A ready source needs nonempty text. Text and original PDFs are limited to 12 MB each in this first version.

For `page_scheme: pdf`, form-feed characters separate physical PDF pages. This must come from a page-preserving extraction; printed journal page numbers are not inferred. Otherwise use `none`, and no PDF page is claimed. Passages retain full text (220 words with overlap), source identity and revision. IDs include the collection and stable key, so identical filenames in separate collections do not collide.

Optional `url` must be HTTPS. Optional `original` is a relative slash-separated PDF path beneath the original root, paired with `original_sha256` (64 lowercase hexadecimal characters). Original bytes must match that revision before the authenticated API returns them. The phone prepares an in-memory PDF and then exposes an explicit Open link; no local disk paths become public static URLs. Original files must actually be present on the serving host; a path on a different computer is not enough.

## Retrieval and remaining work

FTS5 searches literal terms with AND matching and BM25 ranking. It is keyword retrieval, not a semantic answer or confidence score. Up to 20 passages, at most three per source, are returned with full text. Original papers are the default; no-match results never substitute project notes. Filters explicitly allow notes, summaries, guides and private learnings. Catalog browsing paginates 30 sources at a time. The CLI exposes full search/catalog JSON using the same implementation.

Still required before retiring the old library: inventory and classify the real corpus; evaluate extraction quality and page mapping; produce and validate complete manifests; provision originals on the serving host; verify permissions and PDF opening on the actual phone; connect a scheduled, audited sync process; evaluate explicit semantic search. The exact-text reader is available from 4.61 onward. This release can display imported private learnings but does not author them. It does not modify the old service or remove its models.


## Source reader and file organization (4.61)

The catalog is the durable SQLite record; FTS5 is keyword retrieval over its revision-bound passages. Optional future semantic embeddings should reference those same identities rather than replace the catalog. Source kind and file format are separate: a PDF can be a note, and Markdown can contain a paper transcription without becoming an original paper automatically.

Optional `file_format` is `pdf`, `txt`, `md`, `epub`, `docx`, `html`, `other`, or `unknown` (default). This field records the inventoried original format; it does **not** install or promise an extractor for that format. Native reviewed UTF-8 TXT and Markdown can already be supplied as manifest text. Markdown/HTML content is displayed as escaped plain text; no scripts or external resources run. EPUB chapter extraction and locators are supported by the bounded 4.62 adapter described below; DOCX/HTML adapters remain future work.

Schema 2 stores exact decoded text in `reader_blocks`, separately from whitespace-normalized, overlapping search passages. Each response returns one block of at most 12,000 characters. Line breaks and indentation survive; PDF form feeds separate physical pages. Empty PDF pages retain their positions. An optional positive integer `physical_pages` must agree with extracted page separators. One trailing form feed is treated as an extractor terminator. Count agreement is an integrity check, not proof of reading order or mathematical correctness. Invalid C0 controls (except whitespace), Unicode noncharacters and replacement glyphs reject the entire import before catalog changes.

`GET library/read?id=<source>&revision=<revision>&offset=0` reads an exact revision. Optional `pdf_page` starts at that physical page's first block. Responses state availability, total blocks and position; held text is unavailable, never substituted with snippets. The phone reader opens from source details, begins at the search hit's PDF page, and keeps its revision through navigation. Printed page numbers are not invented.

Schema 1 databases remain readable without migration on GET. Publishing upgrades the schema after manifest validation. Back up an existing catalog using SQLite's backup API before publishing. Previously stored revisions have search passages but no exact reader text: the reader explains this rather than reconstructing an approximate source from overlapping chunks. Reimport reviewed source text to create a new reader-capable revision; old citations stay resolvable. Older 4.60 publishers cannot publish into schema 2, so keep the database backup when upgrading and restore the matching backup if rolling the publisher back.


## EPUB staging and chapter reading (4.62)

Use `python scripts/mnemosyne-epub.py <book.epub> --output <new-staging-directory> --collection <collection> --key <stable-key>`. The default source kind is `book`; `--kind` is explicit. A book is not silently treated as an original research paper. The output retains `original.epub`, chapter text files and a `draft-manifest.json` whose `complete` flag is **false**. Review the extracted text and combine the record into the complete collection inventory before publication. Do not simply mark a one-file draft complete for an existing multi-source collection. Nothing is published by this command, and it refuses an existing output directory.

The initial adapter supports a conservative subset of reflowable EPUB 2/3 with XHTML chapters. It follows the package spine, including non-linear items marked as auxiliary content, rather than ZIP filename order. Each chapter retains its container member path and title. No PDF page number is invented. Original EPUB opening/download is not yet exposed by the PDF-only original viewer; the retained staging original is the recovery copy.

The parser reads bounded ZIP members in memory and never extracts executable resources, fetches remote content, or runs scripts/styles. Limits are 64 MB archive, 128 MB declared expansion, 4096 members, 8 MB per member, 12 MB extracted text, and bounded XML depth/node count. Duplicate/unsafe paths and spine identities are refused. Encrypted/obfuscated resources, multiple renditions, fixed-layout content, XML DTDs (including otherwise valid older XHTML declarations), MathML and inline SVG require a separate reviewed extraction. This is not a universal EPUB renderer or OCR tool. Images are represented only by explicitly labeled alternative descriptions when present; visual layout is not reproduced.

Manifest records may supply `chapters: [{text, member, label, linear}]` with `file_format: epub` and `page_scheme: none`, instead of a single `text` file. The combined text limit applies across chapters. Revision metadata maps existing SQLite passage/reader ordinals to chapters, so schema 2 remains unchanged and old records still read. Search results include chapter labels and reader offsets; the reader opens the matching chapter. Renamed chapters create a new immutable revision.

References: [EPUB spine ordering](https://www.w3.org/TR/epub-33/#sec-spine-elem), [Python XML security](https://docs.python.org/3/library/xml.html#xml-security), and [ZIP decompression pitfalls](https://docs.python.org/3/library/zipfile.html#decompression-pitfalls). Keep the interpreter's XML/security patches current even with these application bounds.


## Reviewed repeat publication (4.63)

For an existing schema-2 catalog, running the publish CLI without `--apply` now returns a change report and a `plan` token. Provide `--original-root <serving-originals>` if the inventory references PDFs. All originals must already exist there and match their revision hashes; this command does not transfer them. The report distinguishes additions, changed revisions, restored sources, retirements and unchanged records, and counts ready sources that would become held. Read the report before applying it.

Apply the reviewed inventory with `python scripts/mnemosyne-catalog.py --db <catalog> publish <manifest.json> --text-root <texts> --original-root <serving-originals> --expect-plan <token> --backup <new-recovery-folder> --apply`. Omit the original root only for inventories without local original references. Missing review/backup arguments reject an existing-catalog update. A missing reviewed database is never silently recreated. Initial creation reserves a new database with exclusive file creation, so a competing creator cannot turn bootstrap into an unreviewed overwrite; reviewed updates refuse older schemas rather than migrating them before backup.

The token covers proposed source/revision identities and the catalog's source state, including prior publication timestamps. Changed text, metadata, health, collection scope or a competing publication requires another review. Prepared text is read once for the guarded apply and that exact snapshot is written. Under SQLite `BEGIN IMMEDIATE`, competing writers wait (up to five seconds) or fail as busy; a competing update that changes catalog state invalidates the earlier review. An already-empty collection can be reapplied as a harmless no-op because it has no source state to change. A separate read connection makes `library.sqlite` in the new recovery directory while the write reservation is held; integrity is checked before any source update. `review.json` records the proposal with `published: false`: it is review evidence, not a completion receipt. The successful CLI response reports `published: true`. A crash before commit rolls back the catalog; a crash after commit can be distinguished by reviewing current state again. Existing recovery folders are never reused or deleted.

The backup contains the previous catalog, not original PDF files. Preserve the separately provisioned hash-bound originals and all staging/recovery folders. The catalog retains prior revisions and sources outside the declared collection scope. Restoring a backup is an explicit operator action with the serving application stopped; this command does not swap live databases automatically.

`library.publish()` remains the low-level bootstrap/compatibility API for trusted callers and tests; it serializes its writes but does not provide reviewed-update or backup guarantees. Use `publish_reviewed()` or the guarded CLI for repeat production imports. Legacy personal publisher scripts are not an automatic sync mechanism and should not be scheduled.

Still needed for scheduled sync: authoritative inventories that fail on absent/offline inputs, reviewed transfer packages, retirement policy, durable job outcome reporting and an installed timer. `complete: true` is an operator assertion; neither this CLI nor a zero-error parse proves a partial inventory is complete. This release deliberately installs no job and changes no live catalog by itself.


## Optional EPUBCheck during import

Mnemosyne's staging CLI can use [W3C/DAISY EPUBCheck](https://github.com/w3c/epubcheck) to check EPUB conformance before extraction. Install the official distribution in a local tools directory, keeping `epubcheck.jar`, `lib/`, `LICENSE.txt` and `licenses/` together. Supply `--epubcheck-jar <installed-jar> --java <java-executable>` to `scripts/mnemosyne-epub.py`, or configure `ARGUS_EPUBCHECK_JAR` and `ARGUS_JAVA` for the import process. These paths are operator configuration, never taken from book metadata. The adapter ships inside Mnemosyne; Java and upstream binaries are optional installation components, not vendored into this repository or loaded on reader requests.

When configured, validation is mandatory for that import. The adapter invokes Java with an argument list (no shell), a 512MB heap limit and a 60-second deadline after bounded ZIP inspection. Nonzero exit, missing/malformed JSON or any error/fatal count holds the book. Warnings remain visible in its source diagnostic and the full report for review. It does not change warning severity or automatically repair a book. Without configuration, the source explicitly says EPUBCheck was not run.

Each new staging directory keeps the exact input as `original.epub`. `epubcheck-report.json` and `.log` stay beside it. A successful draft records the validator version in extraction provenance; a failure writes `HELD-FOR-REVIEW.json` and never writes the ready marker/inventory. A standards-valid EPUB may still be unsupported by Mnemosyne's conservative text extractor (for example fixed layout or DTD declarations). Validation success is not a promise of complete visual reproduction or correct text extraction.

Licensing: EPUBCheck 5.4.0's bundled LICENSE.txt is BSD-3-Clause. Its distribution includes separate dependency notices/licenses (Apache-2.0, BSD-3-Clause, MIT, MPL-2.0 and W3C notices); preserve the whole upstream distribution when packaging it. A Java runtime has its own license and notices. The portable Temurin runtime used for local validation retains its GPLv2/ClassPath-exception and other component notices. No upstream binaries or sample books are committed here. See [the official release](https://github.com/w3c/epubcheck/releases/tag/v5.4.0) and the license files in the distribution rather than relying on the promotional site label.


## Optional DOCX text import (4.64)

Install `requirements-mnemosyne-docx.txt` in a dedicated importer environment:
`python -m pip install -r requirements-mnemosyne-docx.txt`.
Then run `python scripts/mnemosyne-docx.py document.docx --output new-staging-directory --collection notes --key stable-source-key`.
The default kind is `note`; choose `--kind guide` or another explicit library kind as appropriate.
This is an offline staging command, not a phone upload interface. Search and reading use already stored SQLite text and do not import these optional packages.

Supported content is body paragraphs, hyperlink display text, and unmerged table cells (including nested tables), in document order. Tables become a sequence of cell paragraphs; styling, automatic list labels, graphics and pagination are not reproduced. Explicit page and column breaks become line separators so adjacent words never join. Word files do not provide reliable physical pages, so the record uses `page_scheme=none`.

The importer retains `original.docx`, `text.txt`, and `locations.json`. The map binds original/text SHA-256 hashes to XML paragraph/table-cell paths and start/end Unicode-code-point offsets in the exact extracted text. It remains in staging for audit; the current reader shows the text, not these structural locators. It is not a Word rendering or an original-DOCX download feature.

Successful staging creates `draft-manifest.json` with `complete=false` and `READY-FOR-REVIEW.json`. Inspect the text and combine the source into a genuinely complete collection inventory before using the reviewed catalog publisher. Never flip the flag just to bypass collection review. Failure after original capture retains a `HELD-FOR-REVIEW.json` reason and the captured original. Existing staging directories are refused. Oversized inputs are refused before capture; the input file is never changed.

Tracked changes, content controls, fields/TOCs, drawings/text boxes, embedded objects/macros, equations, foot/endnote references, comment references, nonempty headers/footers or other text parts, hidden text, numbered/bulleted lists and merged/omitted table cells are deliberately held. Unsupported containers are also held so python-docx cannot silently omit their text. The main relationship must target the canonical `word/document.xml`; alternate main parts are held. XML parts are identified by package content-type defaults/overrides as well as their filenames, and checked regardless of filename case or folder, including unsupported features in unused parts/styles. This conservative check can hold a file even when its visible body looks simple. External relationships other than hyperlinks are refused; hyperlink targets are never fetched. There is no OCR or neural guesswork.

Limits: 64 MiB archive, 4,096 members, 128 MiB total expansion, 8 MiB/member, 100 XML levels and 100,000 elements per XML part, 30 nested table levels, 10,000 extracted paragraphs and 12 MiB extracted UTF-8 text. DTD/entity declarations, unsafe/duplicate member names and encrypted ZIP entries are refused before python-docx opens the immutable byte snapshot.

Licensing: python-docx 1.2.0 is MIT (Copyright Steve Canny); lxml and typing_extensions have their own included notices. Keep the complete installed distributions and license directories when packaging the importer. Binaries are not vendored in this repository, and installation never occurs automatically on the serving host. The pinned optional requirements are tested in Linux CI. Sources: https://github.com/python-openxml/python-docx/blob/master/LICENSE and https://python-docx.readthedocs.io/en/latest/api/document.html.


### Reading places

Save place records the current extracted-text section on this browser; Resume reading returns to it after reopening the same source revision. Up to 100 source/revision positions are retained, without document text. These places do not synchronize across devices. Opening a search match does not change a saved place. Jump to section expands a numeric navigation form. A changed revision starts without a saved place; unavailable browser storage leaves reading usable. These are extracted-text sections, not physical pages or exact scroll positions.

### Recently checked out

Library home lists up to ten distinct sources most recently read on this browser, across all source types. Opening source metadata, browsing or searching does not count: a readable section must load successfully while the reader is open. Continue reading uses the last successfully viewed section; explicit Save place bookmarks remain separate. Only IDs, revisions and section offsets are stored locally, never document text or titles. This history is not synchronized between devices. When persistence is blocked, a session-only history keeps reading usable.

Home resolves current source metadata before offering continuation. An updated revision opens from its beginning; a retired or unavailable source is shown without a continuation button. With no history, Home offers the catalog and search. Browse shelves currently uses the paginated catalog; the category/alphabet side rail is the next navigation increment.
