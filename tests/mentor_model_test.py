"""Mentor's data model without a browser: courses, the Loose lessons course, the review log (docs/plans/2026-10-25-mentor-courses-phase1.md).

    python3 tests/mentor_model_test.py -v        (tests/run.sh runs it under "== mentor model")

Each test gets its own temporary database, inbox and realm file; nothing outside a temporary folder is touched."""
import importlib.util, json, os, shutil, sqlite3, sys, tempfile, time, unittest

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location('leafy_mentor', os.path.join(R, 'plugins', 'mentor', 'mentor.py'))
m = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(m)

# the 4.25.0 database, as it is on a server today
OLD_SCHEMA = """
CREATE TABLE cards(id TEXT PRIMARY KEY, deck TEXT, kind TEXT, prompt TEXT, answer TEXT, points TEXT, tags TEXT, updated REAL,
  data TEXT DEFAULT '{}', ord INTEGER DEFAULT 0, learn_of TEXT);
CREATE TABLE sched(card_id TEXT PRIMARY KEY, stability REAL, difficulty REAL, due REAL, last REAL, reps INTEGER, lapses INTEGER,
  level INTEGER DEFAULT 1, refresh INTEGER DEFAULT 0);
CREATE TABLE attempts(id INTEGER PRIMARY KEY AUTOINCREMENT, card_id TEXT, at REAL, answer TEXT, confidence INTEGER, ms INTEGER,
  coverage REAL, hits TEXT, missed TEXT, features TEXT, suggested INTEGER, rating INTEGER, grade_wrong INTEGER, grader TEXT,
  kind TEXT, level INTEGER, hints INTEGER DEFAULT 0, reflections TEXT, stuck TEXT, skipped INTEGER DEFAULT 0, ai TEXT);
CREATE TABLE modules(id TEXT PRIMARY KEY, name TEXT, project TEXT, built_in INTEGER, at REAL, summary TEXT, concepts TEXT, files TEXT, source TEXT);
CREATE TABLE imports(path TEXT PRIMARY KEY, mtime REAL, size INTEGER, ok INTEGER, msg TEXT, module TEXT, at REAL);
"""

class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='mentor-test-')
        m.INBOX = os.path.join(self.tmp, 'inbox'); m.REALM_FILE = os.path.join(self.tmp, 'realm.json'); m._realm[:] = [None, {}]
        self.path = os.path.join(self.tmp, 'mentor.db')
    def tearDown(self):
        try: self.db.close()
        except AttributeError: pass
        shutil.rmtree(self.tmp, ignore_errors=True)
    def count(self, sql, *args):
        return self.db.execute(sql, args).fetchone()[0]

class Upgrade(Base):
    def old_db(self):
        old = sqlite3.connect(self.path); old.executescript(OLD_SCHEMA)
        old.executemany("INSERT INTO modules(id,name,project,built_in,at) VALUES(?,?,?,0,0)",
                        [('a', 'Caching', 'argus-ui'), ('b', 'Game loops', 'GAME_RESEARCH › Topics')])
        old.executemany("INSERT INTO cards(id,deck,kind,prompt,answer) VALUES(?,?,?,'p','x')",
                        [('a:term_01', 'a', 'term'), ('a:card_01', 'a', 'explain'), ('b:term_01', 'b', 'term')])
        old.executemany("INSERT INTO sched(card_id,stability,difficulty,due,last,reps,lapses) VALUES(?,1,5,0,0,1,0)", [('a:term_01',), ('b:term_01',)])
        old.executemany("INSERT INTO attempts(card_id,at,rating) VALUES(?,0,3)", [('a:term_01',), ('a:term_01',), ('a:card_01',), ('b:term_01',)])
        old.commit(); old.close()

    def test_upgrade_old_db_twice(self):
        self.old_db()
        m.connect(self.path).close(); self.db = m.connect(self.path)
        self.assertEqual([self.count(f"SELECT COUNT(*) FROM {t}") for t in ('cards', 'sched', 'attempts')], [3, 2, 4])
        self.assertEqual(self.count("SELECT COUNT(*) FROM courses WHERE id=?", m.LOOSE), 1)
        rows = {r['id']: (r['course'], r['cmodule']) for r in self.db.execute("SELECT id, course, cmodule FROM modules")}
        self.assertEqual(rows, {'a': ('loose', 'loose/argus-ui'), 'b': ('loose', 'loose/game_research-topics')})
        self.assertEqual(self.count("SELECT COUNT(*) FROM cmodules WHERE course=?", m.LOOSE), 2)

    def test_old_lesson_import_is_loose(self):
        self.db = m.connect(self.path)
        m.load_decks(self.db, os.path.join(R, 'themes', 'leafy-realm', 'decks'))
        mods = self.db.execute("SELECT course, cmodule FROM modules").fetchall()
        self.assertTrue(mods)
        self.assertTrue(all(r['course'] == m.LOOSE and r['cmodule'].startswith('loose/') for r in mods))

if __name__ == '__main__':
    unittest.main()
