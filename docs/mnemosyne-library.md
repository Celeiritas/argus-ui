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

`kind` is one of `paper`, `summary`, `note`, `guide`, `learning`, `unknown`. `health` is `ready`, `pending`, `failed`, `suspect`, `catalog-only`, or `unknown`. Record extraction problems in `diagnostic`; suspect/failed sources remain browsable but are not searched. Do not supply damaged text: invalid UTF-8, replacement characters and NULs reject publication. A ready source needs nonempty text. Text and original PDFs are limited to 12 MB each in this first version.

For `page_scheme: pdf`, form-feed characters separate physical PDF pages. This must come from a page-preserving extraction; printed journal page numbers are not inferred. Otherwise use `none`, and no PDF page is claimed. Passages retain full text (220 words with overlap), source identity and revision. IDs include the collection and stable key, so identical filenames in separate collections do not collide.

Optional `url` must be HTTPS. Optional `original` is a relative slash-separated PDF path beneath the original root, paired with `original_sha256` (64 lowercase hexadecimal characters). Original bytes must match that revision before the authenticated API returns them. The phone prepares an in-memory PDF and then exposes an explicit Open link; no local disk paths become public static URLs. Original files must actually be present on the serving host; a path on a different computer is not enough.

## Retrieval and remaining work

FTS5 searches literal terms with AND matching and BM25 ranking. It is keyword retrieval, not a semantic answer or confidence score. Up to 20 passages, at most three per source, are returned with full text. Original papers are the default; no-match results never substitute project notes. Filters explicitly allow notes, summaries, guides and private learnings. Catalog browsing paginates 30 sources at a time. The CLI exposes full search/catalog JSON using the same implementation.

Still required before retiring the old library: inventory and classify the real corpus; evaluate extraction quality and page mapping; produce and validate complete manifests; provision originals on the serving host; verify permissions and PDF opening on the actual phone; connect a scheduled, audited sync process; decide whether a separate nearby-passage reader and explicit semantic search are useful. This release can display imported private learnings but does not author them. It does not modify the old service or remove its models.


## Source reader and file organization (4.61)

The catalog is the durable SQLite record; FTS5 is keyword retrieval over its revision-bound passages. Optional future semantic embeddings should reference those same identities rather than replace the catalog. Source kind and file format are separate: a PDF can be a note, and Markdown can contain a paper transcription without becoming an original paper automatically.

Optional `file_format` is `pdf`, `txt`, `md`, `epub`, `docx`, `html`, `other`, or `unknown` (default). This field records the inventoried original format; it does **not** install or promise an extractor for that format. Native reviewed UTF-8 TXT and Markdown can already be supplied as manifest text. Markdown/HTML content is displayed as escaped plain text; no scripts or external resources run. EPUB chapter extraction and format-specific locators remain future adapter work.

Schema 2 stores exact decoded text in `reader_blocks`, separately from whitespace-normalized, overlapping search passages. Each response returns one block of at most 12,000 characters. Line breaks and indentation survive; PDF form feeds separate physical pages. Empty PDF pages retain their positions. An optional positive integer `physical_pages` must agree with extracted page separators. One trailing form feed is treated as an extractor terminator. Count agreement is an integrity check, not proof of reading order or mathematical correctness. Invalid C0 controls (except whitespace), Unicode noncharacters and replacement glyphs reject the entire import before catalog changes.

`GET library/read?id=<source>&revision=<revision>&offset=0` reads an exact revision. Optional `pdf_page` starts at that physical page's first block. Responses state availability, total blocks and position; held text is unavailable, never substituted with snippets. The phone reader opens from source details, begins at the search hit's PDF page, and keeps its revision through navigation. Printed page numbers are not invented.

Schema 1 databases remain readable without migration on GET. Publishing upgrades the schema after manifest validation. Back up an existing catalog using SQLite's backup API before publishing. Previously stored revisions have search passages but no exact reader text: the reader explains this rather than reconstructing an approximate source from overlapping chunks. Reimport reviewed source text to create a new reader-capable revision; old citations stay resolvable. Older 4.60 publishers cannot publish into schema 2, so keep the database backup when upgrading and restore the matching backup if rolling the publisher back.
