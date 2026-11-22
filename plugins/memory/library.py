"""Private, local source catalog. Explicit manifests, immutable revisions, lexical retrieval.

The existing embedding index is never modified. This catalog is a separate, opt-in
database; publication is one transaction after every source has been validated.
No network requests or model calls are made here.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
from datetime import datetime, timezone
from urllib.parse import urlsplit

KINDS = ('paper', 'summary', 'note', 'guide', 'learning', 'unknown')
HEALTH = ('ready', 'pending', 'failed', 'suspect', 'catalog-only', 'unknown')
MAX_BYTES = 12 * 1024 * 1024
SCHEMA = 2
FORMATS = ('pdf', 'txt', 'md', 'epub', 'docx', 'html', 'other', 'unknown')
READER_BLOCK = 12000


def location(ctx):
    return Path(os.environ.get('ARGUS_LIBRARY_DB', str(Path(ctx.data_dir) / 'library.sqlite')))


def roots(ctx):
    return Path(os.environ.get('ARGUS_LIBRARY_ORIGINALS', str(Path(ctx.data_dir) / 'originals')))


def connect(path, create=False):
    path = Path(path)
    if not create:
        if not path.is_file(): return None
        c = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=5)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        c = sqlite3.connect(path, timeout=5)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    return c


def schema(c):
    v = c.execute('PRAGMA user_version').fetchone()[0]
    if v not in (0, 1, SCHEMA): raise ValueError('Unsupported library schema; keep the existing database.')
    if v == 0 and c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchone():
        raise ValueError('Use a new catalog database; the legacy index must stay unchanged')
    c.executescript('''
    CREATE TABLE IF NOT EXISTS sources (
      id TEXT PRIMARY KEY, collection TEXT NOT NULL, source_key TEXT NOT NULL,
      title TEXT NOT NULL, kind TEXT NOT NULL, authorship TEXT NOT NULL,
      revision TEXT NOT NULL, health TEXT NOT NULL, diagnostic TEXT NOT NULL,
      active INTEGER NOT NULL DEFAULT 1, indexed_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS revisions (
      id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES sources(id),
      content_hash TEXT NOT NULL, metadata TEXT NOT NULL, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS passages (
      id INTEGER PRIMARY KEY, revision TEXT NOT NULL REFERENCES revisions(id),
      ordinal INTEGER NOT NULL, pdf_page INTEGER, printed_page TEXT, text TEXT NOT NULL,
      UNIQUE(revision, ordinal));
    CREATE VIRTUAL TABLE IF NOT EXISTS passage_fts USING fts5(title, text, tokenize='unicode61');
    CREATE INDEX IF NOT EXISTS passage_revision ON passages(revision);
    CREATE INDEX IF NOT EXISTS source_collection ON sources(collection, active);
    CREATE TABLE IF NOT EXISTS reader_blocks (
      revision TEXT NOT NULL REFERENCES revisions(id), ordinal INTEGER NOT NULL,
      pdf_page INTEGER, text TEXT NOT NULL, PRIMARY KEY(revision, ordinal));
    PRAGMA user_version=2;
    ''')


def word(value, name, limit=200):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError('Invalid ' + name)
    return value.strip()


def relative_file(root, value):
    value = word(value, 'relative source path', 800)
    if '\\' in value or ':' in value: raise ValueError('Use a relative slash-separated source path')
    p = Path(value)
    if p.is_absolute() or '..' in p.parts: raise ValueError('Source path leaves its configured root')
    target = (Path(root).resolve() / p).resolve()
    if not target.is_relative_to(Path(root).resolve()): raise ValueError('Source path leaves its configured root')
    return target


def source_url(value):
    if not value: return ''
    u = urlsplit(value)
    if u.scheme != 'https' or not u.netloc or u.username or u.password:
        raise ValueError('Source websites must use HTTPS without credentials')
    return value


def prepare(manifest, text_root):
    if not isinstance(manifest, dict): raise ValueError('Manifest must be an object')
    if manifest.get('schema') != 'mnemosyne-manifest/1' or manifest.get('complete') is not True:
        raise ValueError('Only a completed mnemosyne-manifest/1 may be published')
    scope = manifest.get('collections')
    if not isinstance(scope, list) or not scope:
        raise ValueError('Name each complete collection once')
    scope = [word(x, 'collection', 100) for x in scope]
    if len(scope) != len(set(scope)): raise ValueError('Name each complete collection once')
    records = manifest.get('sources')
    if not isinstance(records, list): raise ValueError('Sources must be a list')
    seen, prepared = set(), []
    for item in records:
        if not isinstance(item, dict): raise ValueError('Each source must be an object')
        collection = word(item.get('collection'), 'collection', 100)
        if collection not in scope: raise ValueError('Source is outside the declared collection scope')
        key = word(item.get('key'), 'source key', 200)
        sid = hashlib.sha256(json.dumps([collection, key], ensure_ascii=False).encode('utf-8')).hexdigest()
        if sid in seen: raise ValueError('Duplicate source identity')
        seen.add(sid)
        kind, health = item.get('kind'), item.get('health')
        if kind not in KINDS or health not in HEALTH: raise ValueError('Explicit source kind and extraction health required')
        title = word(item.get('title'), 'title', 500)
        authorship = word(item.get('authorship', 'unknown'), 'authorship', 200)
        diagnostic = str(item.get('diagnostic', ''))[:1000]
        original = item.get('original', '')
        if original: relative_file(text_root, original)  # syntax/symlink check; served against a separately configured root
        url = source_url(item.get('url', ''))
        original_hash = item.get('original_sha256', '')
        if original and not re.fullmatch('[0-9a-f]{64}', original_hash):
            raise ValueError('A local original requires its SHA-256 to bind the indexed revision')
        file_format = item.get('file_format', 'unknown')
        if file_format not in FORMATS: raise ValueError('Unknown file format')
        physical_pages = item.get('physical_pages')
        if physical_pages is not None and (type(physical_pages) is not int or physical_pages < 1):
            raise ValueError('Physical page count must be a positive integer')
        scheme = item.get('page_scheme', 'none')
        if scheme not in ('pdf', 'none'): raise ValueError('Page scheme must be pdf or none')
        pages, blocks, content_hash = [], [], ''
        if item.get('text'):
            f = relative_file(text_root, item['text'])
            if f.stat().st_size > MAX_BYTES: raise ValueError('Extracted text exceeds the per-source limit')
            raw = f.read_bytes()
            text = raw.decode('utf-8-sig', errors='strict')
            if any(c == '\ufffd' or (ord(c) < 32 and c not in '\n\r\t\f') or ord(c) % 65536 in (65534, 65535) or 0xFDD0 <= ord(c) <= 0xFDEF for c in text):
                raise ValueError('Damaged extraction: repair text or publish catalog metadata with suspect health')
            content_hash = hashlib.sha256(raw).hexdigest()
            if health == 'ready' and not text.strip(): raise ValueError('Empty extraction cannot be ready')
            sections = text.split('\f') if scheme == 'pdf' else [text]
            # Extractors commonly terminate the final physical page with one form feed.
            if scheme == 'pdf' and len(sections) > 1 and not sections[-1].strip(): sections.pop()
            if scheme == 'pdf' and physical_pages is not None and len(sections) != physical_pages:
                raise ValueError('Extracted page count does not match the physical PDF')
            if health == 'ready':
                for i, page in enumerate(sections, 1):
                    for start in range(0, max(1, len(page)), READER_BLOCK):
                        blocks.append((i if scheme == 'pdf' else None, page[start:start + READER_BLOCK]))
                    words = page.split()
                    for start in range(0, len(words), 180):
                        chunk = ' '.join(words[start:start + 220])
                        if chunk: pages.append((i if scheme == 'pdf' else None, '', chunk))
        elif health == 'ready': raise ValueError('Ready sources need extracted text')
        meta = dict(collection=collection, key=key, title=title, kind=kind, authorship=authorship,
                    health=health, diagnostic=diagnostic, original=original, original_sha256=original_hash,
                    url=url, page_scheme=item.get('page_scheme', 'none'),
                    file_format=file_format, physical_pages=physical_pages, reader_version=1,
                    extraction_version=str(item.get('extraction_version', 'unknown'))[:120],
                    source_version=str(item.get('source_version', 'unknown'))[:200])
        revision = hashlib.sha256((sid + content_hash + json.dumps(meta, sort_keys=True)).encode()).hexdigest()
        prepared.append((sid, revision, content_hash, meta, pages, blocks))
    return scope, prepared


def publish(path, manifest, text_root):
    scope, records = prepare(manifest, text_root)  # failed reads/validation leave the active catalog untouched
    c = connect(path, create=True)
    try:
        schema(c)
        now = datetime.now(timezone.utc).isoformat()
        with c:
            for collection in scope: c.execute('UPDATE sources SET active=0 WHERE collection=?', (collection,))
            for sid, rev, content_hash, meta, pages, blocks in records:
                values = (sid, meta['collection'], meta['key'], meta['title'], meta['kind'], meta['authorship'], rev,
                          meta['health'], meta['diagnostic'], 1, now)
                c.execute('''INSERT INTO sources VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                  title=excluded.title,kind=excluded.kind,authorship=excluded.authorship,revision=excluded.revision,
                  health=excluded.health,diagnostic=excluded.diagnostic,active=1,indexed_at=excluded.indexed_at''', values)
                if c.execute('SELECT 1 FROM revisions WHERE id=?', (rev,)).fetchone(): continue
                c.execute('INSERT INTO revisions VALUES(?,?,?,?,?)', (rev, sid, content_hash, json.dumps(meta), now))
                c.executemany('INSERT INTO reader_blocks VALUES(?,?,?,?)',
                              [(rev, n, page, text) for n, (page, text) in enumerate(blocks)])
                for ordinal, (pdf_page, printed, text) in enumerate(pages):
                    pid = c.execute('INSERT INTO passages(revision,ordinal,pdf_page,printed_page,text) VALUES(?,?,?,?,?)',
                                    (rev, ordinal, pdf_page, printed, text)).lastrowid
                    c.execute('INSERT INTO passage_fts(rowid,title,text) VALUES(?,?,?)', (pid, meta['title'], text))
        return dict(sources=len(records), collections=scope, indexed_at=now)
    finally: c.close()


def catalog(path, kind='', collection='', health='', offset=0):
    c = connect(path)
    if c is None: return dict(configured=False, sources=[], total=0, totals={}, collections=[])
    try:
        where, args = filters(kind, collection, health)
        total = c.execute('SELECT count(*) FROM sources s WHERE ' + where, args).fetchone()[0]
        rows = c.execute('SELECT s.* FROM sources s WHERE ' + where + ' ORDER BY title COLLATE NOCASE,id LIMIT 30 OFFSET ?', args + [offset]).fetchall()
        totals = dict(c.execute('SELECT health,count(*) FROM sources WHERE active=1 GROUP BY health').fetchall())
        return dict(configured=True, sources=[dict(r) for r in rows], total=total, offset=offset,
                    totals=totals, collections=[r[0] for r in c.execute('SELECT DISTINCT collection FROM sources WHERE active=1 ORDER BY collection')])
    finally: c.close()


def filters(kind='', collection='', health=''):
    where, args = ['s.active=1'], []
    for col, val, allowed in [('kind', kind, KINDS), ('collection', collection, None), ('health', health, HEALTH)]:
        if val:
            if allowed and val not in allowed: raise ValueError('Unknown ' + col)
            where.append('s.' + col + '=?'); args.append(val)
    return ' AND '.join(where), args


def search(path, query, kind='paper', collection=''):
    query = word(query, 'search text', 300)
    tokens = re.findall(r'\w+', query, flags=re.UNICODE)[:30]
    if not tokens: return dict(passages=[], query=query)
    # Every term is a quoted literal, never executable FTS syntax supplied by the caller.
    match = ' AND '.join('"' + t.replace('"', '""') + '"' for t in tokens)
    c = connect(path)
    if c is None: return dict(passages=[], query=query, configured=False)
    try:
        where, args = filters(kind, collection, 'ready')
        rows = c.execute('''SELECT p.id,p.text,p.pdf_page,p.printed_page,p.ordinal,s.id AS source_id,
          s.title,s.collection,s.kind,s.authorship,s.revision,s.health,s.indexed_at,r.metadata,
          bm25(passage_fts,2.0,1.0) AS rank FROM passage_fts
          JOIN passages p ON p.id=passage_fts.rowid JOIN sources s ON s.revision=p.revision
          JOIN revisions r ON r.id=p.revision WHERE passage_fts MATCH ? AND ''' + where +
          ' ORDER BY rank,p.id LIMIT 90', [match] + args).fetchall()
        counts, results = {}, []
        for row in rows:
            d = dict(row); meta = json.loads(d.pop('metadata')); sid = d['source_id']
            if counts.get(sid, 0) >= 3: continue
            counts[sid] = counts.get(sid, 0) + 1
            d.update(page_scheme=meta['page_scheme'], source_version=meta['source_version'])
            results.append(d)
            if len(results) == 20: break
        return dict(passages=results, query=query, configured=True, mode='keyword', ranking='BM25, not confidence')
    finally: c.close()


def source(path, sid, revision=''):
    c = connect(path)
    if c is None: return None
    try:
        r = c.execute('''SELECT s.*,r.metadata,r.id AS selected_revision,r.created_at FROM sources s
          JOIN revisions r ON r.source_id=s.id AND r.id=COALESCE(NULLIF(?,''),s.revision)
          WHERE s.id=? AND (s.active=1 OR ?<>'')''', (revision, sid, revision)).fetchone()
        if r is None: return None
        d = dict(r);d.update(json.loads(d.pop('metadata')));d['revision'] = d.pop('selected_revision')
        d['indexed_at'] = d.pop('created_at');return d
    finally: c.close()



def reader(path, sid, revision='', offset=0, pdf_page=None):
    if type(offset) is not int or not 0 <= offset <= 100000: raise ValueError('Invalid reader position')
    if pdf_page is not None and (type(pdf_page) is not int or pdf_page < 1): raise ValueError('Invalid PDF page')
    d = source(path, sid, revision)
    if not d: return None
    answer = dict(source_id=sid, revision=d['revision'], title=d['title'], file_format=d.get('file_format', 'unknown'),
                  available=False, blocks=[], total=0, offset=offset)
    c = connect(path)
    try:
        if not c.execute("SELECT 1 FROM sqlite_master WHERE name='reader_blocks' AND type='table'").fetchone():
            return dict(answer, reason='This revision predates the text reader. Reimport its reviewed extraction to read it here.')
        total = c.execute('SELECT count(*) FROM reader_blocks WHERE revision=?', (d['revision'],)).fetchone()[0]
        if not total: return dict(answer, reason='No reviewed readable text is stored for this revision. Check its extraction status or original.')
        if pdf_page is not None:
            row = c.execute('SELECT min(ordinal) FROM reader_blocks WHERE revision=? AND pdf_page=?', (d['revision'], pdf_page)).fetchone()
            if row[0] is None: raise ValueError('PDF page is not available')
            offset = row[0]
        if offset >= total: raise ValueError('Reader position is outside this source')
        rows = c.execute('SELECT ordinal,pdf_page,text FROM reader_blocks WHERE revision=? AND ordinal=?', (d['revision'], offset)).fetchall()
        return dict(answer, available=True, blocks=[dict(r) for r in rows], total=total, offset=offset)
    finally: c.close()


def original(path, root, sid, revision=''):
    d = source(path, sid, revision)
    if not d or not d.get('original'): raise ValueError('No local original is available for this source')
    f = relative_file(root, d['original'])
    if f.suffix.lower() != '.pdf' or f.stat().st_size > MAX_BYTES: raise ValueError('Original PDF is unavailable or exceeds 12 MB')
    raw = f.read_bytes()
    if not raw.startswith(b'%PDF-') or hashlib.sha256(raw).hexdigest() != d['original_sha256']:
        raise ValueError('The original changed; publish its new revision before opening it')
    return dict(filename=f.name, mime='application/pdf', base64=base64.b64encode(raw).decode('ascii'))


def api(path, query, ctx):
    def q(key, default=''): return (query.get(key) or [default])[0]
    db = location(ctx)
    try:
        if path == 'library/catalog':
            offset = int(q('offset', '0'))
            if not 0 <= offset <= 100000: raise ValueError('Invalid page')
            return 200, catalog(db, q('kind'), q('collection'), q('health'), offset)
        if path == 'library/search': return 200, search(db, q('q'), q('kind', 'paper'), q('collection'))
        if path == 'library/source':
            d = source(db, q('id'), q('revision'))
            if not d: return 404, {'msg': 'Source not found'}
            return 200, d
        if path == 'library/read':
            d = reader(db, q('id'), q('revision'), int(q('offset', '0')), int(q('pdf_page')) if q('pdf_page') else None)
            return (200, d) if d else (404, {'msg': 'Source not found'})
        if path == 'library/original': return 200, original(db, roots(ctx), q('id'), q('revision'))
        if path == 'library/ask': return 410, {'msg': 'Generated answers are retired. Search the sources instead.'}
        return 404, {'msg': 'Not found'}
    except (ValueError, UnicodeError): return 400, {'msg': 'Check the search, filters, or source revision.'}
    except (OSError, sqlite3.Error): return 503, {'msg': 'The library is unavailable. Your existing sources have been kept.'}
