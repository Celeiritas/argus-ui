"""Mnemosyne reading places on the server (plugins/memory/places.py, docs/mnemosyne-library.md, 4.67.0).

    python3 tests/places_test.py -v        (tests/run.sh runs it under "== library catalog")

Each person's recently read documents and saved places, kept in one JSON file so every device of that person opens the
same place. Each test gets its own temporary folder."""
import importlib.util, json, os, shutil, sys, tempfile, types, unittest

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(R, 'plugins', 'memory'))
_spec = importlib.util.spec_from_file_location('leafy_memory', os.path.join(R, 'plugins', 'memory', 'plugin.py'))
plugin = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(plugin)
import places  # noqa: F401 (the module the plugin loads by path)

A, B, C = 'a' * 64, 'b' * 64, 'c' * 64
OWNER = {'person': 'owner', 'name': 'You', 'role': 'owner'}
LEARNER = {'person': 'p1', 'name': 'Sam', 'role': 'learner'}
def hexid(n): return format(n, '064x')

class Places(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='places-test-')
        self.file = os.path.join(self.tmp, 'mnemosyne-places.json')
        self.ctx = types.SimpleNamespace(data_dir=self.tmp)
    def tearDown(self): shutil.rmtree(self.tmp, ignore_errors=True)
    def put(self, kind, id_, offset=0, revision=B, who=OWNER, **extra):
        return plugin.post('library/place', dict(kind=kind, id=id_, revision=revision, offset=offset, **extra), self.ctx, who)

    def test_empty_then_round_trip(self):
        self.assertEqual(plugin.get('library/places', {}, self.ctx, OWNER), (200, {'recent': [], 'saved': []}))
        status, lists = self.put('saved', A, 3)
        self.assertEqual(status, 200)
        self.assertEqual([(r['id'], r['revision'], r['offset']) for r in lists['saved']], [(A, B, 3)])
        self.assertRegex(lists['saved'][0]['at'], r'^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d+)?Z$')
        self.assertEqual(plugin.get('library/places', {}, self.ctx, OWNER)[1], lists)
        self.assertTrue(os.path.exists(self.file))

    def test_same_id_replaces_and_recent_is_newest_first(self):
        self.put('recent', A, 1); self.put('recent', C, 0); _, lists = self.put('recent', A, 5)
        self.assertEqual([(r['id'], r['offset']) for r in lists['recent']], [(A, 5), (C, 0)])
        self.put('saved', A, 1); self.put('saved', C, 2); _, lists = self.put('saved', A, 7)
        self.assertEqual([(r['id'], r['offset']) for r in lists['saved']], [(C, 2), (A, 7)])

    def test_limits(self):
        for n in range(12): self.put('recent', hexid(n + 1))
        for n in range(102): _, lists = self.put('saved', hexid(n + 1))
        lists = plugin.get('library/places', {}, self.ctx, OWNER)[1]
        self.assertEqual(len(lists['recent']), 10); self.assertEqual(lists['recent'][0]['id'], hexid(12))
        self.assertEqual(len(lists['saved']), 100); self.assertEqual(lists['saved'][-1]['id'], hexid(102))

    def test_bad_rows_are_refused_and_nothing_written(self):
        for bad in [dict(kind='other', id=A), dict(kind='saved', id='A' * 64), dict(kind='saved', id=A[:-1]),
                    dict(kind='saved', id=A, revision='x'), dict(kind='saved', id=A, offset=-1), dict(kind='saved', id=A, offset=100001),
                    dict(kind='saved', id=A, offset=1.5), dict(kind='saved', id=A, offset=True), dict(kind='saved', id=A, offset='2'),
                    dict(kind=[], id=A), dict(kind={}, id=A), dict(kind=None, id=A)]:
            body = {'revision': B, 'offset': 0, **bad}
            self.assertEqual(plugin.post('library/place', body, self.ctx, OWNER), (400, {'msg': 'Check the reading place.'}), bad)
        self.assertEqual(plugin.post('library/place', 'not a dict', self.ctx, OWNER)[0], 400)
        self.assertFalse(os.path.exists(self.file))

    def test_client_time_is_ignored_and_no_titles_kept(self):
        _, lists = self.put('saved', A, 1, at='2099-01-01T00:00:00Z', title='Secret title')
        self.assertNotEqual(lists['saved'][0]['at'], '2099-01-01T00:00:00Z')
        self.assertEqual(set(lists['saved'][0]), {'id', 'revision', 'offset', 'at'})
        self.assertNotIn('Secret', open(self.file, encoding='utf-8').read())

    def test_people_are_kept_apart(self):
        self.put('saved', A, 1); self.put('saved', C, 2, who=LEARNER)
        self.assertEqual([r['id'] for r in plugin.get('library/places', {}, self.ctx, OWNER)[1]['saved']], [A])
        self.assertEqual([r['id'] for r in plugin.get('library/places', {}, self.ctx, LEARNER)[1]['saved']], [C])
        nobody = {'person': None, 'name': None, 'role': 'none'}
        self.assertEqual(plugin.get('library/places', {}, self.ctx, nobody)[0], 403)
        self.assertEqual(plugin.post('library/place', dict(kind='saved', id=A, revision=B, offset=0), self.ctx, nobody)[0], 403)

    def test_broken_file_is_set_aside(self):
        with open(self.file, 'w', encoding='utf-8') as f: f.write('{broken')
        self.assertEqual(plugin.get('library/places', {}, self.ctx, OWNER), (200, {'recent': [], 'saved': []}))
        self.put('saved', A, 1)
        aside = [n for n in os.listdir(self.tmp) if n.startswith('mnemosyne-places.broken-')]
        self.assertEqual(len(aside), 1)
        self.assertEqual(open(os.path.join(self.tmp, aside[0]), encoding='utf-8').read(), '{broken')
        self.assertEqual(json.load(open(self.file, encoding='utf-8'))['owner']['saved'][0]['id'], A)

    def test_bad_rows_in_the_file_are_dropped(self):
        with open(self.file, 'w', encoding='utf-8') as f:
            json.dump({'owner': {'recent': [{'id': A, 'revision': B, 'offset': 1, 'at': '2026-11-23T00:00:00Z'}, {'id': 'x'}, 'junk'], 'saved': 'junk'}}, f)
        lists = plugin.get('library/places', {}, self.ctx, OWNER)[1]
        self.assertEqual([r['id'] for r in lists['recent']], [A]); self.assertEqual(lists['saved'], [])

    def test_the_backup_post_is_unchanged(self):
        self.assertEqual(plugin.post('nothing', {}, self.ctx, OWNER)[0], 404)

if __name__ == '__main__':
    unittest.main()
