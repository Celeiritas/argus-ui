"""Reviewed repeat imports: synthetic data, stale plans, locking and recovery."""
from contextlib import closing
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('library',Path(__file__).resolve().parents[1]/'plugins/memory/library.py')
lib=importlib.util.module_from_spec(spec);spec.loader.exec_module(lib)

class PublicationTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.db=self.root/'catalog.sqlite'
        (self.root/'text.txt').write_text('Synthetic exact original text.',encoding='utf-8')
        self.m=dict(schema='mnemosyne-manifest/1',complete=True,collections=['notes'],sources=[self.record('one'),self.record('two')])
        lib.publish(self.db,self.m,self.root)
    def record(self,key,collection='notes'):
        return dict(collection=collection,key=key,title=key,kind='note',health='ready',file_format='txt',text='text.txt')
    def review(self):return lib.review_publication(self.db,self.m,self.root)
    def apply(self,plan,folder='backup'):
        return lib.publish_reviewed(self.db,self.m,self.root,plan,self.root/folder)
    def test_initial_creation_refuses_existing_database_atomically(self):
        before=self.db.read_bytes()
        with self.assertRaises(FileExistsError):lib.initialize(self.db,self.m,self.root)
        self.assertEqual(self.db.read_bytes(),before)
        fresh=self.root/'fresh.sqlite'
        self.assertTrue(lib.initialize(fresh,self.m,self.root)['published'])
        self.assertEqual(lib.catalog(fresh)['total'],2)

    def test_review_is_read_only_and_diffs_all_categories(self):
        other=dict(schema='mnemosyne-manifest/1',complete=True,collections=['other'],sources=[self.record('outside','other')])
        lib.publish(self.db,other,self.root)
        self.m['sources'] += [self.record('restored'),self.record('retired')];lib.publish(self.db,self.m,self.root)
        with closing(sqlite3.connect(self.db)) as c:
            c.execute("UPDATE sources SET active=0 WHERE source_key='restored'");c.commit()
        self.m['sources']=[self.record('one'),dict(self.record('two'),title='Changed'),self.record('restored'),self.record('added')]
        before=self.db.read_bytes();r=self.review()
        self.assertEqual(r['counts'],dict(added=1,changed=1,restored=1,retired=1,unchanged=1))
        self.assertEqual(r['outside_scope_active'],1);self.assertEqual(self.db.read_bytes(),before)
        self.assertFalse(r['published'])
    def test_backup_is_recoverable_and_old_revision_stays_readable(self):
        old=lib.catalog(self.db)['sources'][0];old_text=lib.reader(self.db,old['id'],old['revision'])
        (self.root/'text.txt').write_text('Updated source text.',encoding='utf-8')
        r=self.apply(self.review()['plan']);self.assertTrue(r['published'])
        self.assertEqual(lib.reader(self.db,old['id'],old['revision']),old_text)
        self.assertEqual(lib.catalog(self.root/'backup/library.sqlite')['sources'][0]['revision'],old['revision'])
        self.assertNotEqual(lib.catalog(self.db)['sources'][0]['revision'],old['revision'])
    def test_stale_text_and_catalog_refuse_before_backup(self):
        token=self.review()['plan'];(self.root/'text.txt').write_text('Different bytes',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'changed'):self.apply(token)
        self.assertFalse((self.root/'backup').exists())
        token=self.review()['plan'];lib.publish(self.db,self.m,self.root)
        with self.assertRaisesRegex(ValueError,'changed'):self.apply(token)
    def test_concurrent_same_plan_only_one_applies(self):
        self.m['sources'][0]['title']='Changed title';token=self.review()['plan']
        def attempt(n):
            try:self.apply(token,'backup'+str(n));return 'published'
            except ValueError as e:
                self.assertIn('changed',str(e));return 'stale'
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(attempt,range(2)))
        self.assertCountEqual(results,['published','stale'])
    def test_wal_backup_includes_committed_content(self):
        with closing(sqlite3.connect(self.db)) as c:
            c.execute('PRAGMA journal_mode=WAL')
            c.execute("UPDATE sources SET title='Committed in WAL' WHERE source_key='one'");c.commit()
            self.m['sources']=[];self.apply(self.review()['plan'])
            self.assertEqual(lib.catalog(self.root/'backup/library.sqlite')['sources'][0]['title'],'Committed in WAL')

    def test_backup_failure_does_not_change_catalog(self):
        before=lib.catalog(self.db);self.m['sources']=[];token=self.review()['plan']
        (self.root/'backup').mkdir()
        with self.assertRaises(FileExistsError):self.apply(token)
        self.assertEqual(lib.catalog(self.db),before)
    def test_write_failure_rolls_back_with_recovery_copy(self):
        before=lib.catalog(self.db);self.m['sources']=[];token=self.review()['plan']
        def fail(c,*args):
            c.execute('UPDATE sources SET active=0');raise sqlite3.OperationalError('synthetic interruption')
        with patch.object(lib,'_write_records',fail):
            with self.assertRaises(sqlite3.Error):self.apply(token)
        self.assertEqual(lib.catalog(self.db),before)
        self.assertEqual(lib.catalog(self.root/'backup/library.sqlite'),before)
    def test_missing_and_incomplete_inputs_do_not_create_catalog(self):
        missing=self.root/'absent.sqlite'
        with self.assertRaises(ValueError):lib.review_publication(missing,self.m,self.root)
        self.assertFalse(missing.exists())
        self.m['complete']=False
        with self.assertRaises(ValueError):self.review()
    def test_original_is_required_and_hash_checked(self):
        original=self.root/'original.pdf';original.write_bytes(b'%PDF-synthetic')
        self.m['sources'][0].update(original='original.pdf',original_sha256=hashlib.sha256(original.read_bytes()).hexdigest())
        with self.assertRaises(ValueError):self.review()
        r=lib.review_publication(self.db,self.m,self.root,self.root)
        original.write_bytes(b'%PDF-different')
        with self.assertRaisesRegex(ValueError,'[Oo]riginal'):
            lib.publish_reviewed(self.db,self.m,self.root,r['plan'],self.root/'backup',self.root)
        self.assertFalse((self.root/'backup').exists())
    def test_retirements_and_health_regressions_are_explicit(self):
        self.m['sources']=[dict(self.record('one'),health='suspect')]
        r=self.review();self.assertEqual(r['counts']['retired'],1)
        self.assertEqual(r['ready_to_held'],1);self.assertEqual(r['counts']['changed'],1)
    def test_cli_requires_review_for_existing_database(self):
        mf=self.root/'manifest.json';mf.write_text(json.dumps(self.m),encoding='utf-8')
        cli=Path(__file__).resolve().parents[1]/'scripts/mnemosyne-catalog.py'
        command=[sys.executable,str(cli),'--db',str(self.db),'publish',str(mf),'--text-root',str(self.root)]
        r=subprocess.run(command,capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr)
        plan=json.loads(r.stdout)['plan']
        refused=subprocess.run(command+['--apply'],capture_output=True,text=True);self.assertNotEqual(refused.returncode,0)
        accepted=subprocess.run(command+['--apply','--expect-plan',plan,'--backup',str(self.root/'backup')],capture_output=True,text=True)
        self.assertEqual(accepted.returncode,0,accepted.stderr)

    def test_missing_text_and_old_schema_leave_database_unchanged(self):
        before=self.db.read_bytes()
        self.m['sources'][0]['text']='missing.txt'
        with self.assertRaises(OSError):self.review()
        self.assertEqual(self.db.read_bytes(),before)
        self.m['sources'][0]['text']='text.txt'
        with closing(sqlite3.connect(self.db)) as c:c.execute('PRAGMA user_version=1')
        before=self.db.read_bytes()
        with self.assertRaisesRegex(ValueError,'schema'):self.review()
        self.assertEqual(self.db.read_bytes(),before)
    def test_other_collection_survives_guarded_retirement(self):
        other=dict(schema='mnemosyne-manifest/1',complete=True,collections=['other'],sources=[self.record('outside','other')])
        lib.publish(self.db,other,self.root)
        before=lib.catalog(self.db,collection='other')
        self.m['sources']=[];self.apply(self.review()['plan'])
        self.assertEqual(lib.catalog(self.db,collection='other')['sources'],before['sources'])
        self.assertEqual(lib.catalog(self.db,collection='notes')['total'],0)
    def test_actual_backup_failure_stops_writes(self):
        before=lib.catalog(self.db);self.m['sources']=[];token=self.review()['plan']
        def fail_backup(path,create=False):
            raise OSError('Synthetic backup read failure')
        with patch.object(lib,'connect',fail_backup):
            with self.assertRaises(OSError):self.apply(token)
        self.assertEqual(lib.catalog(self.db),before)
    def test_cli_missing_reviewed_database_never_bootstraps(self):
        mf=self.root/'manifest.json';mf.write_text(json.dumps(self.m),encoding='utf-8')
        missing=self.root/'missing.sqlite'
        cli=Path(__file__).resolve().parents[1]/'scripts/mnemosyne-catalog.py'
        r=subprocess.run([sys.executable,str(cli),'--db',str(missing),'publish',str(mf),'--text-root',str(self.root),'--apply','--expect-plan',self.review()['plan'],'--backup',str(self.root/'backup')],capture_output=True,text=True)
        self.assertNotEqual(r.returncode,0);self.assertFalse(missing.exists())

if __name__=='__main__':unittest.main()
