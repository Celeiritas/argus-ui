"""Private library evidence and publication boundaries, using synthetic text only."""
import copy
from contextlib import closing
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import types
import unittest

spec = importlib.util.spec_from_file_location('library', Path(__file__).resolve().parents[1] / 'plugins/memory/library.py')
lib = importlib.util.module_from_spec(spec); spec.loader.exec_module(lib)


class LibraryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.db = self.root / 'library.sqlite'
        (self.root / 'paper.txt').write_text('First page: touch perception.\fSecond page: tactile timing and accuracy.', encoding='utf-8')
        (self.root / 'note.txt').write_text('Our project note about the boss and tactile timing.', encoding='utf-8')
        self.m = dict(schema='mnemosyne-manifest/1', complete=True, collections=['research'], sources=[
            dict(collection='research', key='one', title='Touch study', kind='paper', health='ready', text='paper.txt', page_scheme='pdf'),
            dict(collection='research', key='two', title='Own learning', kind='learning', health='ready', text='note.txt')])

    def publish(self): return lib.publish(self.db, self.m, self.root)

    def test_reader_preserves_exact_text_and_pinned_retired_revision(self):
        text = '# Heading\n\n  Indented <script>alert(1)</script>\n' + 'x' * 13000
        (self.root / 'note.txt').write_bytes(text.encode('utf-8'))
        self.m['sources'][1]['file_format'] = 'md'
        self.publish(); hit = lib.catalog(self.db, kind='learning')['sources'][0]
        first = lib.reader(self.db, hit['id'])
        self.assertEqual(first['file_format'], 'md'); self.assertEqual(first['total'], 2)
        second = lib.reader(self.db, hit['id'], offset=1)
        self.assertEqual(first['blocks'][0]['text'] + second['blocks'][0]['text'], text)
        self.m['sources'] = []; self.publish()
        self.assertIsNone(lib.reader(self.db, hit['id']))
        self.assertEqual(lib.reader(self.db, hit['id'], hit['revision'])['blocks'], first['blocks'])

    def test_reader_pdf_blank_page_and_verified_count(self):
        (self.root / 'paper.txt').write_text('First\f\fLast\f', encoding='utf-8')
        self.m['sources'][0].update(physical_pages=3, file_format='pdf')
        self.publish(); sid = lib.catalog(self.db, kind='paper')['sources'][0]['id']
        blank = lib.reader(self.db, sid, pdf_page=2)
        self.assertEqual(blank['blocks'][0]['text'], '')
        self.assertEqual(blank['total'], 3)
        self.assertEqual(lib.reader(self.db, sid, pdf_page=3)['blocks'][0]['text'], 'Last')
        with self.assertRaises(ValueError): lib.reader(self.db, sid, offset=3)
        with self.assertRaises(ValueError): lib.reader(self.db, sid, pdf_page=4)

    def test_bad_pdf_count_and_noncharacters_leave_catalog_unchanged(self):
        self.publish(); before = lib.catalog(self.db)
        self.m['sources'][0]['physical_pages'] = 3
        with self.assertRaises(ValueError): self.publish()
        self.m['sources'][0].pop('physical_pages')
        for bad in ('\ufffe', '\ufdd0', '\x01', '\U0001ffff'):
            (self.root / 'paper.txt').write_text('Corrupt ' + bad, encoding='utf-8')
            with self.subTest(glyph=repr(bad)), self.assertRaises(ValueError): self.publish()
        self.assertEqual(lib.catalog(self.db), before)

    def test_schema_one_read_does_not_mutate_then_upgrades_on_publish(self):
        self.publish()
        with closing(sqlite3.connect(self.db)) as c:
            c.execute('DROP TABLE reader_blocks'); c.execute('PRAGMA user_version=1'); c.commit()
        sid = lib.catalog(self.db, kind='paper')['sources'][0]['id']
        before = self.db.read_bytes()
        self.assertFalse(lib.reader(self.db, sid)['available'])
        self.assertEqual(before, self.db.read_bytes())
        # Changed extraction identity creates a new revision with reader blocks.
        self.m['sources'][0]['extraction_version'] = 'reviewed-v2'; self.publish()
        self.assertTrue(lib.reader(self.db, sid)['available'])

    def test_held_text_has_no_reader_and_format_is_explicit(self):
        self.m['sources'][0]['health'] = 'suspect'; self.publish()
        sid = lib.catalog(self.db, kind='paper')['sources'][0]['id']
        self.assertFalse(lib.reader(self.db, sid)['available'])
        self.m['sources'][0]['file_format'] = 'invented'
        with self.assertRaises(ValueError): self.publish()

    def test_epub_chapters_search_and_reader_preserve_locations(self):
        (self.root/'start.txt').write_text('Opening chapter.',encoding='utf-8')
        (self.root/'ending.txt').write_text('Distinctive conclusion.',encoding='utf-8')
        source=self.m['sources'][0];source.pop('text');source.update(kind='book',file_format='epub',page_scheme='none',
            chapters=[dict(text='start.txt',label='Opening',member='OPS/start.xhtml'),dict(text='ending.txt',label='Ending',member='OPS/ending.xhtml',linear=False)])
        self.publish()
        self.assertEqual(lib.search(self.db,'Distinctive')['passages'],[])
        hit=lib.search(self.db,'Distinctive',kind='book')['passages'][0]
        self.assertEqual(hit['chapter']['number'],2);self.assertIsNone(hit['pdf_page'])
        self.assertEqual(hit['chapter']['member'],'OPS/ending.xhtml')
        read=lib.reader(self.db,hit['source_id'],hit['revision'],hit['chapter']['reader_offset'])
        self.assertEqual(read['blocks'][0]['text'],'Distinctive conclusion.')
        self.assertFalse(read['blocks'][0]['chapter']['linear'])
        previous=hit['revision'];source['chapters'][1]['label']='Renamed ending';self.publish()
        self.assertEqual(lib.reader(self.db,hit['source_id'],previous,1)['blocks'][0]['chapter']['label'],'Ending')

    def test_chapter_conflicts_do_not_publish(self):
        self.publish();before=lib.catalog(self.db)
        source=self.m['sources'][0];source.update(file_format='epub',chapters=[dict(text='note.txt',label='One',member='one.xhtml')])
        with self.assertRaises(ValueError):self.publish()
        source.pop('text');source['page_scheme']='none';source['chapters'][0]['member']='../outside.xhtml'
        with self.assertRaises(ValueError):self.publish()
        self.assertEqual(before,lib.catalog(self.db))

    def test_exact_search_needs_no_models_and_preserves_page_identity(self):
        self.publish(); result = lib.search(self.db, 'tactile timing')['passages']
        self.assertEqual(len(result), 1); self.assertEqual(result[0]['pdf_page'], 2)
        self.assertEqual(result[0]['kind'], 'paper'); self.assertIn('accuracy', result[0]['text'])
        self.assertEqual(len(result[0]['revision']), 64)

    def test_originals_scope_never_substitutes_notes(self):
        self.publish(); self.assertEqual(lib.search(self.db, 'boss')['passages'], [])
        self.assertEqual(lib.search(self.db, 'boss', kind='learning')['passages'][0]['kind'], 'learning')

    def test_fts_syntax_is_literal_and_invalid_filter_refused(self):
        self.publish(); self.assertEqual(lib.search(self.db, '" OR * NOT (')['passages'], [])
        with self.assertRaises(ValueError): lib.search(self.db, 'touch', kind='invented')

    def test_invalid_encoding_preserves_current_catalog(self):
        self.publish(); before = lib.catalog(self.db)
        (self.root / 'paper.txt').write_bytes(b'bad\xfftext')
        with self.assertRaises(UnicodeError): self.publish()
        self.assertEqual(lib.catalog(self.db), before)
        self.assertEqual(len(lib.search(self.db, 'perception')['passages']), 1)

    def test_partial_manifest_cannot_retire_sources(self):
        self.publish(); self.m['complete'] = False; self.m['sources'] = []
        with self.assertRaises(ValueError): self.publish()
        self.assertEqual(lib.catalog(self.db)['total'], 2)

    def test_missing_file_after_valid_record_is_atomic(self):
        self.publish(); before = lib.catalog(self.db)
        self.m['sources'][1]['text'] = 'missing.txt'
        with self.assertRaises(OSError): self.publish()
        self.assertEqual(lib.catalog(self.db), before)

    def test_revisions_keep_original_passages(self):
        self.publish(); first = lib.search(self.db, 'perception')['passages'][0]
        (self.root / 'paper.txt').write_text('Replacement passage about hearing.', encoding='utf-8'); self.publish()
        self.assertEqual(lib.search(self.db, 'perception')['passages'], [])
        old = lib.source(self.db, first['source_id'], first['revision'])
        self.assertEqual(old['revision'], first['revision'])
        with closing(sqlite3.connect(self.db)) as c: self.assertEqual(c.execute('SELECT count(*) FROM revisions').fetchone()[0], 3)

    def test_collection_namespace_and_scoped_retirement(self):
        self.publish(); other = copy.deepcopy(self.m);other['collections'] = ['other']
        for s in other['sources']: s['collection'] = 'other'
        lib.publish(self.db, other, self.root)
        self.assertEqual(lib.catalog(self.db)['total'], 4)
        self.m['sources'] = [];self.publish()
        self.assertEqual(lib.catalog(self.db)['total'], 2)
        self.assertEqual(lib.catalog(self.db)['collections'], ['other'])

    def test_retired_source_still_resolves_pinned_citation(self):
        self.publish(); first = lib.search(self.db, 'perception')['passages'][0]
        self.m['sources'] = []; self.publish()
        self.assertIsNone(lib.source(self.db, first['source_id']))
        self.assertEqual(lib.source(self.db, first['source_id'], first['revision'])['title'], first['title'])

    def test_nonready_sources_remain_visible_but_unsearchable(self):
        self.m['sources'][0].update(health='suspect', diagnostic='Check reading order')
        self.publish();self.assertEqual(lib.search(self.db, 'touch')['passages'], [])
        self.assertEqual(lib.catalog(self.db, health='suspect')['sources'][0]['diagnostic'], 'Check reading order')

    def test_bad_paths_and_replacement_character_refused(self):
        for p in ('../paper.txt', '/paper.txt', 'C:/paper.txt', 'folder\\paper.txt'):
            with self.subTest(path=p), self.assertRaises(ValueError): lib.relative_file(self.root, p)
        (self.root / 'paper.txt').write_text('broken \ufffd text', encoding='utf-8')
        with self.assertRaises(ValueError): self.publish()
        self.assertFalse(self.db.exists())

    def test_original_pdf_is_scoped_and_revision_bound(self):
        raw = b'%PDF-1.7\nsynthetic fixture'; (self.root / 'original.pdf').write_bytes(raw)
        self.m['sources'][0].update(original='original.pdf', original_sha256=hashlib.sha256(raw).hexdigest())
        self.publish(); sid=lib.catalog(self.db,kind='paper')['sources'][0]['id']
        self.assertEqual(lib.original(self.db,self.root,sid)['mime'], 'application/pdf')
        (self.root / 'original.pdf').write_bytes(raw+b'changed')
        with self.assertRaises(ValueError): lib.original(self.db,self.root,sid)

    def test_unconnected_read_does_not_create_database(self):
        self.assertFalse(lib.catalog(self.db)['configured']);self.assertFalse(self.db.exists())

    def test_legacy_index_is_never_reused(self):
        with closing(sqlite3.connect(self.db)) as c:
            c.execute('CREATE TABLE chunks(text TEXT)'); c.commit()
        before = self.db.read_bytes()
        with self.assertRaises(ValueError): self.publish()
        self.assertEqual(self.db.read_bytes(), before)

    def test_database_failure_rolls_back_retirement(self):
        self.publish(); before = lib.catalog(self.db)
        with closing(sqlite3.connect(self.db)) as c:
            c.execute("CREATE TRIGGER refuse_revision BEFORE INSERT ON revisions BEGIN SELECT RAISE(ABORT, 'test failure'); END"); c.commit()
        (self.root / 'paper.txt').write_text('New extraction', encoding='utf-8')
        with self.assertRaises(sqlite3.Error): self.publish()
        self.assertEqual(lib.catalog(self.db), before)

    def test_malformed_inventory_refuses_before_creation(self):
        for manifest in ([], dict(self.m, sources=[None]), dict(self.m, collections=['research', ' research '])):
            with self.subTest(manifest=manifest), self.assertRaises(ValueError): lib.publish(self.db, manifest, self.root)
        self.assertFalse(self.db.exists())

    def test_duplicate_and_unsafe_website_rejected(self):
        self.m['sources'].append(copy.deepcopy(self.m['sources'][0]))
        with self.assertRaises(ValueError): self.publish()
        self.m['sources'].pop(); self.m['sources'][0]['url'] = 'javascript:alert(1)'
        with self.assertRaises(ValueError): self.publish()

    def test_api_retired_ask_never_calls_a_model(self):
        ctx=types.SimpleNamespace(data_dir=str(self.root))
        code,data=lib.api('library/ask',{},ctx)
        self.assertEqual(code,410);self.assertIn('retired',data['msg'])


if __name__ == '__main__': unittest.main()
