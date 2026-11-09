"""Mentor's data model without a browser: courses, the Loose lessons course, the review log (docs/plans/2026-10-25-mentor-courses-phase1.md),
and the 4.29 study behaviours: learning steps, undo of the last rating, bury siblings.

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
        a = self.go(3)                                # new card, Good: learning step 2 (10 min)
        self.assertEqual(a['review'], 'learn'); self.assertIsNone(a['ivl_before']); self.assertAlmostEqual(a['ivl_after'] * m.DAY, 600, delta=2)
        self.overdue(0); a = self.go(3)               # Good on the last step: graduates to days
        self.assertEqual(a['review'], 'learn'); self.assertGreaterEqual(a['ivl_after'], 1)
        self.overdue(3); a = self.go(1)               # a lapse on a review card: relearning
        self.assertEqual(a['review'], 'review'); self.assertAlmostEqual(a['ivl_before'], 3, delta=0.01)
        self.overdue(0); a = self.go(3)
        self.assertEqual(a['review'], 'relearn')

    def test_again_on_a_new_card_is_still_learning(self):
        self.go(1); self.overdue(0)
        self.assertEqual(self.go(3)['review'], 'learn')

    def test_review_log_manual(self):
        self.go(4)          # Easy graduates at once, due in days: rating it again now is practising ahead
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
        self.assertEqual(self.count("SELECT COUNT(*) FROM cards WHERE is_check=1 AND kind NOT IN ('teach','preread','level0')"), 3)
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
        m.set_settings(self.db, {'bury': False})       # every practice card in one sitting (bury siblings is tested in Bury)
        self.load()
        checks = {r[0] for r in self.db.execute("SELECT id FROM cards WHERE is_check=1")}
        served = self.study() + self.study(deck='group:Rebuild a small web server') + self.study(extra=True)
        self.assertFalse(checks & set(served))
        practice = {r[0] for r in self.db.execute("SELECT id FROM cards WHERE is_check=0 AND kind IN ('term','explain')")}
        self.assertEqual(practice - set(served), set(), 'a check item held back the rest of its lesson')

    def test_check_items_learn_cards_hidden(self):
        # a check item's teach card or pre-read would show its answer: it waits with the check item
        self.load()
        served = set(self.study())
        hidden = {r[0] for r in self.db.execute("SELECT id FROM cards WHERE is_check=1")}
        self.assertEqual(hidden, {m.slug('demo-server--words') + ':' + x for x in ('t-json', 'teach-t-json')} |
                         {m.slug('demo-server--origin') + ':' + x for x in ('k-origin', 'preread-k-origin')} |
                         {m.slug('demo-server--cache') + ':' + x for x in ('k-cache', 'preread-k-cache')})
        self.assertFalse(hidden & served)
        listed = {l['id'] for x in m.stats(self.db)['modules'] for l in x['learn']}
        self.assertFalse(hidden & listed, 'Lessons lists a check item\'s Learn card to read again')

    def test_same_lesson_id_in_two_modules(self):
        doc = json.loads(json.dumps(self.doc)); dup = json.loads(json.dumps(doc['modules'][0]['lessons'][0]))
        doc['modules'][1]['lessons'].append(dup)                 # "words" again, in module weather
        n, notes = self.load(doc)
        self.assertIn('lesson id words is used twice in the course', ' | '.join(notes))
        les = self.db.execute("SELECT cmodule FROM modules WHERE id=?", (m.slug('demo-server--words'),)).fetchone()
        self.assertEqual(les['cmodule'], 'demo-server/requests', 'the first lesson keeps its place and its cards')
        self.assertEqual(self.count("SELECT COUNT(*) FROM cards WHERE deck=?", m.slug('demo-server--words')), 7)   # orientation, 3 teach cards, 3 terms

    def test_course_renamed_in_its_file(self):
        self.load()
        doc = json.loads(json.dumps(self.doc)); doc['id'] = 'small-server'
        self.load(doc)                                           # the same file, a new id: one course, not two
        self.assertEqual([r[0] for r in self.db.execute("SELECT id FROM courses WHERE id<>'loose'")], ['small-server'])
        self.assertEqual(self.count("SELECT COUNT(*) FROM modules WHERE course='demo-server'"), 0)
        self.assertEqual(self.count("SELECT COUNT(*) FROM cards WHERE deck LIKE 'demo-server--%'"), 0)
        self.assertEqual(self.count("SELECT COUNT(*) FROM los WHERE course='demo-server'"), 0)

    def test_recall_role_on_a_term(self):
        doc = json.loads(json.dumps(self.doc)); doc['modules'][0]['lessons'][0]['tier_3_terminology_cards'][0]['role'] = 'recall'
        n, notes = self.load(doc)
        self.assertEqual(notes, [])
        self.assertEqual(self.db.execute("SELECT role FROM cards WHERE id LIKE '%:t-origin'").fetchone()[0], 'recall')

    def test_checks_not_counted_as_waiting(self):
        self.load()
        self.study()
        s = m.stats(self.db)
        self.assertEqual((s['new'], s['learn']), (0, 0))

    def test_stats_courses(self):
        self.load()
        with m.DB_LOCK: m.import_module(self.db, {'metadata': {'module_name': 'old one', 'project': 'argus-ui'},
                                                  'cta_summary': {'orientation': 'x'}}, 'old-one', 'old-one.json', False)
        cs = m.stats(self.db)['courses']
        self.assertEqual([c['id'] for c in cs], ['demo-server', m.LOOSE])
        self.assertEqual(cs[0]['los'], 7)
        self.assertEqual([(x['id'], x['requires'], x['lessons']) for x in cs[0]['modules']],
                         [('demo-server/requests', [], [m.slug('demo-server--words'), m.slug('demo-server--origin')]),
                          ('demo-server/weather', ['demo-server/requests'], [m.slug('demo-server--cache')])])
        self.assertTrue(cs[1]['loose']); self.assertEqual(cs[1]['modules'][0]['lessons'], ['old-one'])
        mod = next(x for x in m.stats(self.db)['modules'] if x['id'] == m.slug('demo-server--cache'))
        self.assertEqual((mod['course'], mod['cmodule']), ('demo-server', 'demo-server/weather'))

    def test_course_text_filled(self):
        with open(m.REALM_FILE, 'w', encoding='utf-8') as fh: json.dump({'SERVER': 'TestHost'}, fh)
        self.load()
        names = [x['name'] for x in m.stats(self.db)['courses'][0]['modules']]
        self.assertEqual(names[0], 'Requests on TestHost')

    def test_inbox_course(self):
        os.makedirs(m.INBOX, exist_ok=True); shutil.copy(FIXTURE, os.path.join(m.INBOX, 'demo-server.json'))
        m.scan_inbox(self.db)
        r = self.db.execute("SELECT ok, msg, module FROM imports").fetchone()
        self.assertEqual((r['ok'], r['module']), (1, 'demo-server')); self.assertIn('in 3 lessons', r['msg'])

class Upgrade429(Upgrade):
    """4.29 adds sched.step / sched.relearn, attempts.prev_json / attempts.undone and the settings table."""
    def test_upgrade_twice_keeps_everything(self):
        self.old_db()
        m.connect(self.path).close(); self.db = m.connect(self.path)
        cols = lambda t: {r[1] for r in self.db.execute(f"PRAGMA table_info({t})")}
        self.assertTrue({'step', 'relearn'} <= cols('sched')); self.assertTrue({'prev_json', 'undone'} <= cols('attempts'))
        self.assertEqual([self.count(f"SELECT COUNT(*) FROM {t}") for t in ('cards', 'sched', 'attempts')], [3, 2, 4])
        self.assertEqual(self.count("SELECT COUNT(*) FROM sched WHERE step IS NOT NULL"), 0, 'a card from before steps stays in review')
        self.assertEqual(self.count("SELECT COUNT(*) FROM attempts WHERE undone=1"), 0)
        self.assertEqual(m.settings(self.db), {'bury': True})

class Card(Base):
    """Two plain cards, answered and rated through the same calls the page makes."""
    def setUp(self):
        super().setUp(); self.db = m.connect(self.path)
        with m.DB_LOCK:
            m.upsert_card(self.db, 'd:fitts', 'd', 'define', "Define: Fitts's law", 'time to point grows with distance',
                          [{'idea': 'distance', 'any': ['distance']}], {}, [], 0)
            m.upsert_card(self.db, 'd:hick', 'd', 'define', "Define: Hick's law", 'time to choose grows with the choices',
                          [{'idea': 'choices', 'any': ['choices']}], {}, [], 1)
            self.db.commit()
    def answer(self, card='d:fitts', text='it grows with distance'):
        return m.answer(self.db, card, text, 3, 4000)
    def go(self, rating, card='d:fitts'):
        a = self.answer(card); return a, m.rate(self.db, a['attempt'], rating, False)
    def sched(self, card='d:fitts'):
        r = self.db.execute("SELECT * FROM sched WHERE card_id=?", (card,)).fetchone()
        return {k: r[k] for k in m.SCHED_COLS} if r else None
    def due_now(self, card='d:fitts', days_ago=0):
        now = time.time()
        self.db.execute("UPDATE sched SET due=?, last=? WHERE card_id=?", (now - 1, now - days_ago * m.DAY - 1, card)); self.db.commit()

class Steps(Card):
    def test_timeline_new_card(self):
        now = 1_000_000.0
        s, d, due, reps, lapses, step, relearn = m.schedule(None, 3, now)          # Good: step 2, in 10 min
        self.assertEqual((due - now, step, relearn, reps, lapses), (600, 1, 0, 1, 0))
        self.assertEqual((s, d), (m.W[2], m.init_d(3)))
        row = {'stability': s, 'difficulty': d, 'due': due, 'last': now, 'reps': reps, 'lapses': lapses, 'step': step, 'relearn': relearn}
        s2, d2, due2, _, _, step2, _ = m.schedule(row, 3, due)                       # Good on the last step: FSRS days
        self.assertIsNone(step2); self.assertEqual(due2 - due, m.interval_days(s) * m.DAY)
        self.assertEqual((s2, d2), (s, d), 'same-day steps leave the FSRS memory as the first rating set it')
        self.assertEqual((m.schedule(row, 1, due)[2] - due, m.schedule(row, 1, due)[5]), (60, 0), 'Again goes back to step 1 (1 min)')
        self.assertEqual(m.schedule(row, 2, due)[2] - due, 600, 'Hard on step 2 repeats it')
        self.assertEqual(m.schedule(None, 1, now)[2] - now, 60, 'Again on a new card: 1 min')
        self.assertEqual(m.schedule(None, 2, now)[2] - now, 360, 'Hard on step 1: between 1 and 10 min (6 min)')
        e = m.schedule(None, 4, now)
        self.assertEqual((e[2] - now, e[5]), (m.interval_days(m.W[3]) * m.DAY, None), 'Easy graduates at once')
        self.assertEqual(m.schedule(None, 1, now)[4], 0, 'Again on a new card is not a lapse')

    def test_timeline_lapse_relearns(self):
        now = 5_000_000.0
        row = {'stability': 10.0, 'difficulty': 5.0, 'due': now, 'last': now - 10 * m.DAY, 'reps': 4, 'lapses': 0, 'step': None, 'relearn': 0}
        s, d, due, reps, lapses, step, relearn = m.schedule(row, 1, now)
        self.assertEqual((due - now, step, relearn, lapses), (600, 0, 1, 1)); self.assertLess(s, 10)
        rl = {**row, 'stability': s, 'difficulty': d, 'due': due, 'last': now, 'reps': reps, 'lapses': lapses, 'step': step, 'relearn': relearn}
        self.assertEqual(m.schedule(rl, 2, due)[2] - due, 900, 'Hard on the one relearning step: half as long again')
        g = m.schedule(rl, 3, due)
        self.assertEqual((g[2] - due, g[5], g[6]), (m.interval_days(s) * m.DAY, None, 0), 'Good graduates from relearning')
        self.assertGreater(m.schedule(rl, 4, due)[2], g[2], 'Easy is longer than Good')

    def test_previews_are_what_rating_does(self):
        a = self.answer()
        self.assertEqual({g: round(v * m.DAY) for g, v in a['previews'].items() if g < 4}, {1: 60, 2: 360, 3: 600})
        self.assertEqual(round(a['previews'][4]), m.interval_days(m.W[3]))
        r = m.rate(self.db, a['attempt'], 3, False)
        self.assertAlmostEqual(r['days'] * m.DAY, 600, delta=2); self.assertEqual(r['step'], 1)

    def test_step_card_served_and_counted_when_due(self):
        self.go(3); self.go(3, 'd:hick')
        c, nxt = m.next_card(self.db)
        self.assertIsNone(c, 'a card 10 minutes away is not served yet'); self.assertAlmostEqual(nxt - time.time(), 600, delta=5)
        st = m.stats(self.db)
        self.assertEqual((st['due'], st['steps'], st['new']), (0, 2, 0))
        self.due_now()
        self.assertEqual(m.next_card(self.db)[0]['id'], 'd:fitts')
        st = m.stats(self.db)
        self.assertEqual((st['due'], st['steps']), (1, 1), 'a step card whose minutes are up is due, not also back later today')

class Undo(Card):
    def test_undo_restores_exactly(self):
        self.go(4); self.due_now(days_ago=20)                   # a review card, due
        before = self.sched(); n = self.count("SELECT COUNT(*) FROM attempts")
        a, r = self.go(1)
        self.assertNotEqual(self.sched(), before)
        u = m.undo(self.db, a['attempt'])
        self.assertTrue(u['undone']); self.assertEqual(u['card']['id'], 'd:fitts'); self.assertNotIn('answer', u['card'])
        self.assertEqual(self.sched(), before, 'stability, difficulty, due, last, reps, lapses, level, step: as before the rating')
        self.assertEqual(self.count("SELECT COUNT(*) FROM attempts"), n + 1, 'the log row stays')
        row = self.db.execute("SELECT rating, undone, review FROM attempts WHERE id=?", (a['attempt'],)).fetchone()
        self.assertEqual(tuple(row), (1, 1, 'review'))

    def test_undo_a_new_card_makes_it_new_again(self):
        a, _ = self.go(3)
        m.undo(self.db, a['attempt'])
        self.assertEqual(self.sched(), m.NEVER)
        self.assertEqual(m.stats(self.db)['new'], 2)
        self.assertEqual(m.next_card(self.db)[0]['id'], 'd:fitts', 'served as a new card again')

    def test_only_the_last_rating_once(self):
        a1, _ = self.go(3); a2, _ = self.go(3, 'd:hick')
        self.assertFalse(m.undo(self.db, a1['attempt'])['undone'], 'an older rating')
        self.assertTrue(m.undo(self.db, a2['attempt'])['undone'])
        self.assertFalse(m.undo(self.db, a2['attempt'])['undone'], 'the same one twice')
        self.assertFalse(m.undo(self.db, a1['attempt'])['undone'], 'one step back only: never the rating before an undone one')
        a3, _ = self.go(3, 'd:hick')
        self.assertTrue(m.undo(self.db, a3['attempt'])['undone'], 'answering again makes a new rating to undo')
        self.assertFalse(m.undo(self.db, 99999)['undone'])

    def test_undone_rating_left_out_of_history(self):
        a, _ = self.go(1); m.undo(self.db, a['attempt'])
        self.assertEqual(m.stats(self.db)['labels'], 0, 'an undone rating is not a grader label')
        _, r = self.go(3)
        self.assertEqual(self.db.execute("SELECT review FROM attempts ORDER BY id DESC LIMIT 1").fetchone()[0], 'learn')
        self.assertEqual(r['step'], 1, 'the card starts its steps as if the undone Again never happened')

    def test_rating_from_before_undo_existed(self):
        a, _ = self.go(3)
        self.db.execute("UPDATE attempts SET prev_json=NULL"); self.db.commit()
        self.assertFalse(m.undo(self.db, a['attempt'])['undone'])

    def test_undo_a_hold_takes_the_learn_card_back(self):
        with m.DB_LOCK:
            m.upsert_card(self.db, 'd:teach-x', 'd', 'teach', 'x', '', [], {}, [], 2)
            m.upsert_card(self.db, 'd:x', 'd', 'define', 'Define x', 'x is x', [{'idea': 'x', 'any': ['x']}], {}, [], 3, learn_of='d:teach-x')
            self.db.commit()
        a = m.answer(self.db, 'd:teach-x', '', None, 1000); m.rate(self.db, a['attempt'], 0, False)
        right = lambda: m.answer(self.db, 'd:x', 'x', 3, 4000)      # a right answer, so the rating alone sends it back (not stuck)
        m.rate(self.db, right()['attempt'], 1, False)
        a2 = right(); r2 = m.rate(self.db, a2['attempt'], 1, False)  # Again twice in a week: held, the teach card sent back
        self.assertIsNone(a2['stuck'])
        self.assertTrue(r2['held'] and r2['back'])
        self.assertEqual(self.sched('d:teach-x')['refresh'], 1)
        m.undo(self.db, a2['attempt'])
        self.assertEqual(self.sched('d:teach-x')['refresh'], 0)
        self.assertEqual(self.sched('d:teach-x')['reps'], 1, 'it stays read')

class Bury(Base):
    def setUp(self):
        super().setUp(); self.db = m.connect(self.path)
        with open(FIXTURE, encoding='utf-8') as fh: doc = json.load(fh)
        with m.DB_LOCK: m.import_course(self.db, doc, FIXTURE, False)
        self.deck = m.slug('demo-server--words')
        self.origin, self.allow = self.deck + ':t-origin', self.deck + ':t-allow'        # one note, n-words
    def read_learn(self, **kw):
        """Mark Learn cards read until a practice card comes up; returns it (None: nothing left today)."""
        while True:
            c, _ = m.next_card(self.db, self.deck, **kw)
            if not c or c['kind'] not in m.LEARN: return c
            a = m.answer(self.db, c['id'], '', None, 1000); m.rate(self.db, a['attempt'], 0, False)
    def rate_first(self, rating=4):
        c = self.read_learn(); self.assertIn(c['id'], (self.origin, self.allow))
        a = m.answer(self.db, c['id'], 'x', 3, 2000); m.rate(self.db, a['attempt'], rating, False)
        return c['id'], ({self.origin, self.allow} - {c['id']}).pop()

    def test_sibling_hidden_from_next_and_counts(self):
        new_before = m.stats(self.db, self.deck)['new']
        first, sib = self.rate_first()
        self.assertIsNone(self.read_learn(), 'the sibling is not served today')
        self.assertEqual(m.stats(self.db, self.deck)['new'], new_before - 2, 'neither the answered card nor its buried sibling is waiting')
        ahead = m.next_card(self.db, self.deck, extra=True)[0]
        self.assertNotEqual(ahead and ahead['id'], sib, 'practising ahead skips it too')

    def test_sibling_due_review_is_buried_too(self):
        first, sib = self.rate_first()
        now = time.time()
        self.db.execute("INSERT INTO sched(card_id,stability,difficulty,due,last,reps,lapses) VALUES(?,5,5,?,?,3,0)", (sib, now - 60, now - 5 * m.DAY))
        self.db.commit()
        self.assertEqual(m.stats(self.db, self.deck)['due'], 0, 'a due sibling is not counted as due today')
        self.assertIsNone(m.next_card(self.db, self.deck)[0])

    def test_back_tomorrow(self):
        first, sib = self.rate_first()
        self.db.execute("UPDATE attempts SET at=at-?", (m.DAY,)); self.db.commit()
        self.assertEqual(self.read_learn()['id'], sib)

    def test_setting_off(self):
        self.assertEqual(m.set_settings(self.db, {'bury': False}), {'bury': False})
        first, sib = self.rate_first()
        self.assertEqual(self.read_learn()['id'], sib)
        m.set_settings(self.db, {'bury': True})
        self.assertIsNone(self.read_learn())

    def test_step_card_not_buried(self):
        first, sib = self.rate_first(3)                         # Good on a new card: on its steps
        a = m.answer(self.db, sib, 'x', 3, 2000)                # practised anyway (replay, or ahead): now both are rated today
        m.rate(self.db, a['attempt'], 3, False)
        self.db.execute("UPDATE sched SET due=? WHERE step IS NOT NULL", (time.time() - 1,)); self.db.commit()
        self.assertIn(self.read_learn()['id'], (first, sib), 'cards on their learning steps keep coming back')

    def test_undo_unburies(self):
        first, sib = self.rate_first()
        a = self.db.execute("SELECT id FROM attempts WHERE card_id=? ORDER BY id DESC LIMIT 1", (first,)).fetchone()[0]
        self.assertTrue(m.undo(self.db, a)['undone'])
        self.assertIn(self.read_learn()['id'], (first, sib))
        self.assertEqual(m.stats(self.db, self.deck)['new'], 2)

    def test_settings_ignore_unknown_and_wrong_types(self):
        self.assertEqual(m.set_settings(self.db, {'bury': 'no', 'other': 1}), {'bury': True})
        self.assertEqual(self.count("SELECT COUNT(*) FROM settings"), 0)
        self.assertEqual(m.stats(self.db)['settings'], {'bury': True})

_spec = importlib.util.spec_from_file_location('check_deck', os.path.join(R, 'scripts', 'check-deck.py'))
cd = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(cd)

class Checker(unittest.TestCase):
    """check-deck.py v2 on inputs the fixtures don't cover: odd values never crash it, and spec notation is understood."""
    def setUp(self):
        with open(FIXTURE, encoding='utf-8') as fh: self.doc = json.load(fh)
        cd.OPTS.update(repos={'argus-ui': R}, online=False, links_skipped=0)
    def rules(self, doc):
        return {(lvl, rule) for _w, lvl, rule, _m in cd.check_course(doc)}
    def msgs(self, doc):
        return ' | '.join(f'{lvl} {rule} {msg}' for _w, lvl, rule, msg in cd.check_course(doc))

    def test_lesson_id_twice_in_a_course(self):
        doc = json.loads(json.dumps(self.doc)); doc['modules'][1]['lessons'].append(json.loads(json.dumps(doc['modules'][0]['lessons'][0])))
        self.assertIn('lesson id "words" used twice in the course', self.msgs(doc))
        doc = json.loads(json.dumps(self.doc)); doc['modules'][1]['lessons'][0]['id'] = 'Words'      # the same once made into an id
        self.assertIn('used twice in the course', self.msgs(doc))

    def test_odd_values_dont_crash(self):
        doc = json.loads(json.dumps(self.doc))
        doc['modules'][0]['lessons'][0]['tier_3_terminology_cards'][0]['lo'] = ['L1']
        doc['modules'][0]['lessons'][0]['tier_3_terminology_cards'][1]['note'] = {'id': 'n-words'}
        doc['modules'][1]['id'] = {'weather': 1}
        doc['modules'][0]['lessons'][1]['los'][0]['id'] = ['L2']
        doc['modules'][0]['lessons'][1]['notes'][0]['id'] = 7
        found = self.rules(doc)                                  # no exception
        self.assertIn(('ERROR', 'C1'), found); self.assertIn(('ERROR', 'C4'), found)

    def test_links_that_arent_http(self):
        for url in ('http://example.com:abc/', 'file:///etc/passwd', 'ftp://example.com/x'):
            level, rule, _ = cd.link_problem(url)
            self.assertEqual((level, rule), ('ERROR', 'C9'), url)

    def test_symbol_notation_from_the_spec(self):
        for sym in ('host_ok()', 'H.do_POST', 'do_POST()'):
            ref = {'repo': 'argus-ui', 'path': 'server/argus_ui.py', 'symbol': sym, 'commit': 'beab7ba'}
            self.assertEqual(cd.resolve_ref(ref), [], sym)

    def test_defines_in_other_languages(self):
        self.assertTrue(cd.defines('class Box {\n  fitInside(w, h) {\n    return w < h;\n  }\n}', 'fitInside'))       # JS method
        self.assertTrue(cd.defines('public static int Clamp(int v, int lo)\n{', 'Clamp'))                           # C#
        self.assertTrue(cd.defines('const fade = (x) => x * 2;', 'fade'))
        self.assertFalse(cd.defines('  return fitInside(w, h);', 'fitInside'), 'a call is not a definition')

    def test_doi_written_as_a_link(self):
        for doi in ('https://doi.org/10.1145/1455770.1455782', 'doi:10.1145/1455770.1455782', 'http://dx.doi.org/10.1145/1455770.1455782'):
            self.assertEqual(cd.doi_id(doi), '10.1145/1455770.1455782')

    def test_commit_must_be_a_commit(self):
        ref = {'repo': 'argus-ui', 'path': 'server/argus_ui.py', 'symbol': 'host_ok', 'commit': '--output=x'}
        [(level, rule, msg)] = cd.resolve_ref(ref)
        self.assertEqual((level, rule), ('ERROR', 'C8')); self.assertIn('commit', msg)
        self.assertFalse(os.path.exists(os.path.join(R, 'x')))

if __name__ == '__main__':
    unittest.main()
