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

class ReviewLog(Base):
    def setUp(self):
        super().setUp(); self.db = m.connect(self.path)
        with m.DB_LOCK: m.upsert_card(self.db, 'd:fitts', 'd', 'define', 'Define: Fitts\'s law', 'time to point grows with distance',
                                      [{'idea': 'distance', 'any': ['distance']}], {}, [], 0); self.db.commit()
    def go(self, rating, ms=4000, card='d:fitts'):
        a = m.answer(self.db, card, 'it grows with distance', 3, ms)
        m.rate(self.db, a['attempt'], rating, False)
        return self.db.execute("SELECT * FROM attempts WHERE id=?", (a['attempt'],)).fetchone()
    def overdue(self, days_ago=3):
        now = time.time(); self.db.execute("UPDATE sched SET due=?, last=? WHERE card_id='d:fitts'", (now - 60, now - days_ago * m.DAY)); self.db.commit()

    def test_review_log_new_then_review(self):
        a = self.go(3)
        self.assertEqual(a['review'], 'learn'); self.assertIsNone(a['ivl_before']); self.assertGreater(a['ivl_after'], 0)
        self.overdue(3); a = self.go(1)
        self.assertEqual(a['review'], 'review'); self.assertAlmostEqual(a['ivl_before'], 3, delta=0.01)
        self.overdue(0); a = self.go(3)
        self.assertEqual(a['review'], 'relearn')

    def test_again_on_a_new_card_is_still_learning(self):
        self.go(1); self.overdue(0)
        self.assertEqual(self.go(3)['review'], 'learn')

    def test_review_log_manual(self):
        self.go(3)          # due in days: rating it again now is practising ahead
        self.assertEqual(self.go(3)['review'], 'manual')

    def test_took_capped(self):
        a = self.go(3, ms=95000)
        self.assertEqual((a['took'], a['ms']), (60000, 95000))

    def test_learn_card_no_log(self):
        with m.DB_LOCK: m.upsert_card(self.db, 'd:teach-x', 'd', 'teach', 'x', '', [], {}, [], 0); self.db.commit()
        a = m.answer(self.db, 'd:teach-x', '', None, 1000); m.rate(self.db, a['attempt'], 0, False)
        r = self.db.execute("SELECT review, ivl_before, ivl_after, took FROM attempts WHERE id=?", (a['attempt'],)).fetchone()
        self.assertEqual(tuple(r), (None, None, None, None))

FIXTURE = os.path.join(R, 'tests', 'deck-fixtures', 'good-course.json')

class Course(Base):
    def setUp(self):
        super().setUp(); self.db = m.connect(self.path)
        with open(FIXTURE, encoding='utf-8') as fh: self.doc = json.load(fh)
    def load(self, doc=None):
        with m.DB_LOCK: return m.import_course(self.db, doc or self.doc, FIXTURE, False)
    def study(self, **kw):
        """Answer and rate Good every card the queue serves until it has nothing left; returns the served card ids."""
        served = []
        for _ in range(200):
            c, _due = m.next_card(self.db, **kw)
            if not c: break
            served.append(c['id']); a = m.answer(self.db, c['id'], 'x', 3, 2000); m.rate(self.db, a['attempt'], 3, False)
        return served

    def test_import_course_tables(self):
        n, notes = self.load()
        self.assertEqual(notes, [])
        self.assertEqual(self.count("SELECT COUNT(*) FROM courses WHERE id='demo-server'"), 1)
        self.assertEqual([r[0] for r in self.db.execute("SELECT id FROM cmodules WHERE course='demo-server' ORDER BY ord")],
                         ['demo-server/requests', 'demo-server/weather'])
        self.assertEqual({r[0]: r[1] for r in self.db.execute("SELECT scope, COUNT(*) FROM los WHERE course='demo-server' GROUP BY scope")},
                         {'course': 2, 'module': 2, 'lesson': 3})
        self.assertEqual(self.count("SELECT COUNT(*) FROM notes"), 5)
        self.assertEqual(json.loads(self.db.execute("SELECT source_ref FROM notes WHERE id LIKE '%:n-host'").fetchone()[0])['symbol'], 'do_POST')
        practice = self.db.execute("SELECT * FROM cards WHERE kind IN ('term','explain','drill','define')").fetchall()
        self.assertEqual(len(practice), 9)
        self.assertTrue(all(c['lo'].startswith('demo-server/L') and c['role'] and c['note'] for c in practice))
        self.assertEqual(self.count("SELECT COUNT(*) FROM cards WHERE is_check=1"), 3)
        self.assertEqual(self.db.execute("SELECT role FROM cards WHERE id LIKE '%:c-bug'").fetchone()[0], 'find-bug')
        les = self.db.execute("SELECT * FROM modules WHERE id=?", (m.slug('demo-server--origin'),)).fetchone()
        self.assertEqual((les['course'], les['cmodule'], les['project']), ('demo-server', 'demo-server/requests', 'Rebuild a small web server'))
        self.assertEqual(self.db.execute("SELECT parent FROM los WHERE id='demo-server/L2'").fetchone()[0], 'demo-server/M1')

    def test_reimport_drops_removed_lesson(self):
        self.load()
        kept = m.slug('demo-server--cache')
        a = m.answer(self.db, kept + ':c-ttl', 'it changes slowly', 3, 2000); m.rate(self.db, a['attempt'], 3, False)
        doc = json.loads(json.dumps(self.doc)); doc['modules'][0]['lessons'].pop(0)       # lesson "words" removed
        self.load(doc)
        gone = m.slug('demo-server--words')
        self.assertEqual(self.count("SELECT COUNT(*) FROM modules WHERE id=?", gone), 0)
        self.assertEqual(self.count("SELECT COUNT(*) FROM cards WHERE deck=?", gone), 0)
        self.assertEqual(self.count("SELECT COUNT(*) FROM notes WHERE lesson=?", gone), 0)
        self.assertEqual(self.count("SELECT COUNT(*) FROM los WHERE id='demo-server/L1'"), 0)
        self.assertEqual(self.count("SELECT COUNT(*) FROM attempts WHERE card_id=?", kept + ':c-ttl'), 1)
        self.assertEqual(self.count("SELECT COUNT(*) FROM sched WHERE card_id=?", kept + ':c-ttl'), 1)

    def test_lenient_import_notes(self):
        doc = json.loads(json.dumps(self.doc)); les = doc['modules'][0]['lessons'][1]['tier_2_self_explanation_cards']
        les[0]['role'] = 'parsons'; les[1]['lo'] = 'L9'; doc['modules'][1]['lessons'].append('not a lesson')
        n, notes = self.load(doc)
        text = ' | '.join(notes)
        self.assertIn('role parsons arrives in phase 4', text); self.assertIn('L9', text); self.assertIn('lesson 2', text)
        self.assertEqual(self.count("SELECT COUNT(*) FROM cards WHERE id LIKE '%:c-why'"), 0)
        self.assertIsNone(self.db.execute("SELECT lo FROM cards WHERE id LIKE '%:c-bug'").fetchone()[0])
        self.assertGreater(n, 0)

    def test_check_items_never_served(self):
        self.load()
        checks = {r[0] for r in self.db.execute("SELECT id FROM cards WHERE is_check=1")}
        served = self.study() + self.study(deck='group:Rebuild a small web server') + self.study(extra=True)
        self.assertFalse(checks & set(served))
        practice = {r[0] for r in self.db.execute("SELECT id FROM cards WHERE is_check=0 AND kind IN ('term','explain')")}
        self.assertEqual(practice - set(served), set(), 'a check item held back the rest of its lesson')

    def test_checks_not_counted_as_waiting(self):
        self.load()
        self.study()
        s = m.stats(self.db)
        self.assertEqual((s['new'], s['learn']), (0, 0))

    def test_inbox_course(self):
        os.makedirs(m.INBOX, exist_ok=True); shutil.copy(FIXTURE, os.path.join(m.INBOX, 'demo-server.json'))
        m.scan_inbox(self.db)
        r = self.db.execute("SELECT ok, msg, module FROM imports").fetchone()
        self.assertEqual((r['ok'], r['module']), (1, 'demo-server')); self.assertIn('in 3 lessons', r['msg'])

if __name__ == '__main__':
    unittest.main()
