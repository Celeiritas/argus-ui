"""Mentor 4.38 without a browser: tracks, pin and shelf, question first, the daily limit of new cards, Today's numbers.

    python3 tests/mentor_today_test.py -v        (tests/run.sh runs it under "== mentor today")

Each test gets its own temporary database and inbox, loaded with the theme's decks; nothing outside a temporary folder is touched."""
import importlib.util, json, os, shutil, sys, tempfile, time, unittest

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location('leafy_mentor', os.path.join(R, 'plugins', 'mentor', 'mentor.py'))
m = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(m)
DECKS = os.path.join(R, 'themes', 'leafy-realm', 'decks')
LESSON = 'argus-code'                  # the theme's lesson: Learn cards in front of its practice cards
TRACK = 'group:argus-ui'               # ... and the track it belongs to (its project)

class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='mentor-today-')
        m.INBOX = os.path.join(self.tmp, 'inbox'); m.REALM_FILE = os.path.join(self.tmp, 'realm.json'); m._realm[:] = [None, {}]
        self.path = os.path.join(self.tmp, 'mentor.db')
        self.db = m.connect(self.path); m.load_decks(self.db, DECKS)
    def tearDown(self):
        self.db.close(); shutil.rmtree(self.tmp, ignore_errors=True)
    def count(self, sql, *args):
        return self.db.execute(sql, args).fetchone()[0]
    def rate(self, cid, rating=3, text='x'):
        a = m.answer(self.db, cid, text, None, 2000); m.rate(self.db, a['attempt'], rating, False); return a
    def served(self, n=60, **kw):
        """Track ids of the cards next_card serves, each rated Easy, up to n."""
        out = []
        for _ in range(n):
            c, _ = m.next_card(self.db, **kw)
            if not c: break
            out.append(c['track']); self.rate(c['id'], 0 if c['kind'] in m.LEARN else 4)
        return out

class Tracks(Base):
    def test_tracks_and_their_ids(self):
        ts = {t['id']: t for t in m.tracks(self.db, {'ux-hci': 'UX & HCI terms'})}
        self.assertEqual(set(ts), {'ai-coding', 'psych-design', 'ux-hci', TRACK})
        self.assertEqual(ts['ux-hci']['name'], 'UX & HCI terms')
        self.assertEqual(ts[TRACK]['lessons'], [LESSON], 'a lesson belongs to the track of its project')
        self.assertEqual(m.scope_of(self.db, LESSON), TRACK)

class PinShelf(Base):
    def test_fourth_pin_refused_with_a_way_out(self):
        s = m.set_settings(self.db, {'pinned': ['ai-coding', 'ux-hci', TRACK]})
        self.assertEqual(s['pinned'], ['ai-coding', 'ux-hci', TRACK])
        with self.assertRaises(m.Refusal) as e: m.set_settings(self.db, {'pinned': ['ai-coding', 'ux-hci', TRACK, 'psych-design']})
        self.assertIn('Unpin', str(e.exception))
        self.assertEqual(m.settings(self.db)['pinned'], ['ai-coding', 'ux-hci', TRACK], 'nothing saved')

    def test_pinned_or_shelved_never_both(self):
        m.set_settings(self.db, {'pinned': ['ux-hci']})
        s = m.set_settings(self.db, {'shelved': ['ux-hci']})
        self.assertEqual((s['pinned'], s['shelved']), ([], ['ux-hci']))
        s = m.set_settings(self.db, {'pinned': ['ux-hci']})
        self.assertEqual((s['pinned'], s['shelved']), (['ux-hci'], []))

    def test_shelved_never_served_never_counted_history_kept(self):
        a = self.rate('ux-hci:affordance', 3)           # studied once, then made due
        self.db.execute("UPDATE sched SET due=? WHERE card_id='ux-hci:affordance'", (time.time() - 60,)); self.db.commit()
        due = m.stats(self.db)['due']; self.assertGreaterEqual(due, 1)
        before = [tuple(r) for r in self.db.execute("SELECT * FROM sched ORDER BY card_id")]
        attempts = self.count("SELECT COUNT(*) FROM attempts")
        m.set_settings(self.db, {'shelved': ['ux-hci'], 'new_per_day': {'*': 500}})
        self.assertEqual(m.stats(self.db)['due'], due - 1, 'its due card is not counted')
        self.assertEqual(m.today(self.db)['due'], due - 1)
        self.assertEqual(m.stats(self.db, 'ux-hci')['new'], 0)
        self.assertNotIn('ux-hci', self.served(n=200), 'never served while on the shelf')
        self.assertEqual(m.next_card(self.db, 'ux-hci')[0], None)
        self.assertIn('on the shelf', m.locked_reason(self.db, 'ux-hci'))
        self.assertEqual(self.count("SELECT COUNT(*) FROM attempts WHERE card_id LIKE 'ux-hci:%'"), 1, 'its history stays')
        row = lambda: [tuple(r) for r in self.db.execute("SELECT * FROM sched WHERE card_id LIKE 'ux-hci:%' ORDER BY card_id")]
        self.assertEqual(row(), [r for r in before if r[0].startswith('ux-hci:')], 'its schedule is untouched')
        m.set_settings(self.db, {'shelved': []})
        self.assertEqual(row(), [r for r in before if r[0].startswith('ux-hci:')], 'unshelving restores it exactly')
        self.assertEqual(m.next_card(self.db, 'ux-hci')[0]['id'], 'ux-hci:affordance', 'and its due card is served again')
        self.assertGreater(self.count("SELECT COUNT(*) FROM attempts"), attempts)

    def test_session_takes_new_cards_from_pinned_tracks(self):
        m.set_settings(self.db, {'pinned': ['psych-design']})
        self.assertEqual(set(self.served(n=30, session=True)), {'psych-design'})
        t = m.today(self.db)
        self.assertEqual((t['scope'], t['tracks'][0]['id'], t['tracks'][0]['pinned']), (['psych-design'], 'psych-design', True))

    def test_no_pins_every_track_off_the_shelf(self):
        m.set_settings(self.db, {'shelved': ['ux-hci']})
        t = m.today(self.db)
        self.assertEqual(set(t['scope']), {'ai-coding', 'psych-design', TRACK})
        self.assertEqual(t['shelf'], 1)
        self.assertEqual(t['new_left'], min(m.NEW_PER_DAY, sum(x['new_left'] for x in t['tracks'] if x['id'] in t['scope'])),
                         'nothing pinned: one shared limit of new questions for the day, not one per track')

    def test_nothing_pinned_one_limit_for_the_day(self):
        # 4.38 (review N1): four tracks with 59 new questions open on 10 waiting, and a session stops at 10 new
        t = m.today(self.db)
        self.assertGreater(sum(x['new_left'] for x in t['tracks']), m.NEW_PER_DAY)
        self.assertEqual(t['new_left'], m.NEW_PER_DAY)
        new = 0
        for _ in range(40):
            c, _ = m.next_card(self.db, session=True)
            if not c: break
            if not c['reps'] and c['kind'] not in m.LEARN: new += 1
            self.rate(c['id'], 4)
        self.assertEqual(new, m.NEW_PER_DAY)
        self.assertEqual(m.today(self.db)['new_left'], 0)
        m.set_settings(self.db, {'pinned': ['ux-hci']})
        self.assertGreater(m.today(self.db)['new_left'], 0, 'a pinned track keeps its own limit')

class QuestionFirst(Base):
    def test_a_new_lesson_asks_first(self):
        c, _ = m.next_card(self.db, LESSON)
        self.assertNotIn(c['kind'], m.LEARN, 'a practice card, not the orientation')
        self.assertTrue(c['teach_id'], '"Teach me first" has something to open')
        self.assertEqual(m.one_card(self.db, c['teach_id'])['kind'] in m.LEARN, True)
        a = m.answer(self.db, c['id'], 'x', None, 1000)
        self.assertTrue(a['teach'] and a['teach_new'], 'the teaching comes as feedback after the first try')
        self.assertEqual(self.count("SELECT reps FROM sched WHERE card_id=?", c['learn_of']), 1, 'and counts as read')
        self.assertFalse(m.answer(self.db, c['id'], 'x', None, 1000)['teach_new'], 'once')
        self.assertEqual(m.stats(self.db, LESSON)['learn'], 0, 'no wall of reading cards waits in front')

    def test_teach_first_setting_keeps_the_old_order(self):
        m.set_settings(self.db, {'teach_first': True})
        self.assertEqual(m.next_card(self.db, LESSON)[0]['kind'], 'orientation')
        self.assertGreater(m.stats(self.db, LESSON)['learn'], 0)

    def test_a_miss_still_sends_the_teaching_back(self):
        c, _ = m.next_card(self.db, LESSON)
        self.assertTrue(c['learn_of'])
        m.answer(self.db, c['id'], '', None, 1000); a = m.answer(self.db, c['id'], '', None, 1000)
        self.assertEqual(a['stuck'], 'repeat')
        back, _ = m.next_card(self.db, LESSON)
        self.assertEqual((back['id'], back['refresh']), (c['learn_of'], True), 'the Learn card comes back before the next try')

class ThinkIt(Base):
    def test_think_reveal_rate(self):
        cid = 'ux-hci:affordance'
        a = m.answer(self.db, cid, 'ignored', None, 3000, think=True)
        self.assertEqual((a['think'], a['coverage'], a['suggested'], a['stuck']), (True, None, 0, None), 'nothing graded, nothing suggested')
        self.assertTrue(a['reference'] and set(a['previews']) == {1, 2, 3, 4}, 'the answer and what each rating does')
        self.assertEqual(self.count("SELECT grader FROM attempts WHERE id=?", a['attempt']), 'self')
        m.rate(self.db, a['attempt'], 1, False)
        b = m.answer(self.db, cid, '', None, 3000, think=True)
        self.assertIsNone(b['stuck'], 'two self-rated misses are not "stuck" (nothing was graded)')
        m.rate(self.db, b['attempt'], 3, False)
        st = m.stats(self.db)
        self.assertEqual((st['labels'], st['avg_coverage']), (2, None), 'rated, but no coverage to average')
        t = m.answer(self.db, 'ux-hci:csrf', 'x', None, 1000, think=True)
        self.assertTrue(t['think'])
        drill = self.db.execute("SELECT id FROM cards WHERE kind='drill' LIMIT 1").fetchone()[0]
        self.assertNotIn('think', m.answer(self.db, drill, '[]', None, 1000, think=True), 'a drill is always graded')

class Rollback(Base):
    """4.38 (review B1): a self-rated answer stores coverage 0.0, never NULL, so the Mentor before 4.38 still reads the
    database after a rollback; the new counts leave grader 'self' out."""
    def test_no_null_coverage_and_the_old_sums_still_run(self):
        g = m.answer(self.db, 'ux-hci:affordance', 'what an element lets you do, its perceived action', 3, 2000)
        m.rate(self.db, g['attempt'], 3, False)
        for cid in ('ux-hci:csrf', 'ux-hci:arm-then-choose', 'ux-hci:accessible-name'):
            a = m.answer(self.db, cid, '', 4, 2000, think=True); m.rate(self.db, a['attempt'], 3, False)
        self.assertEqual(self.count("SELECT COUNT(*) FROM attempts WHERE coverage IS NULL"), 0, 'no NULL coverage anywhere')
        self.assertEqual(self.count("SELECT COUNT(*) FROM attempts WHERE grader='self' AND coverage=0.0"), 3)
        st = m.stats(self.db)
        self.assertEqual(st['avg_coverage'], round(g['coverage'], 2), 'self-rated rows are not graded coverage')
        self.assertEqual(st['labels'], 4)
        # the two sums of the Mentor before 4.38 (mentor.py:1382 and :1393 at 4.34.0), over every rated attempt
        att = self.db.execute("SELECT * FROM attempts ORDER BY id DESC LIMIT 500").fetchall()
        rated = [a for a in att if a['rating'] and not a['undone']]
        conf = [a for a in rated if a['confidence']]
        round(sum((a['confidence'] - 1) / 3 - a['coverage'] for a in conf) / len(conf), 2)
        round(sum(a['coverage'] for a in rated) / len(rated), 2)
        self.assertTrue(m.today(self.db)['tracks'])

    def test_self_rated_miss_is_not_stuck(self):
        a = m.answer(self.db, 'ux-hci:csrf', '', None, 1000, think=True); m.rate(self.db, a['attempt'], 1, False)
        b = m.answer(self.db, 'ux-hci:csrf', '', None, 1000)
        self.assertNotEqual(b['stuck'], 'repeat', 'a self-rated attempt before a blank one is not "wrong twice in a row"')

class TeachFirst(Base):
    """4.38 (review S2): reading the lesson card first ("Teach me first") counts as help."""
    def test_capped_at_hard(self):
        free = m.answer(self.db, 'ux-hci:affordance', 'perceived action possibility an object offers', 4, 1000)
        taught = m.answer(self.db, 'ux-hci:affordance', 'perceived action possibility an object offers', 4, 1000, taught=True)
        self.assertLessEqual(taught['suggested'], 2, 'at most Hard after Teach me first')
        self.assertGreaterEqual(free['suggested'], taught['suggested'])
        self.assertTrue(json.loads(self.db.execute("SELECT features FROM attempts WHERE id=?", (taught['attempt'],)).fetchone()[0])['taught'])

    def test_a_drill_does_not_move_up(self):
        drill = self.db.execute("SELECT c.id, c.data FROM cards c WHERE c.kind='drill' ORDER BY c.id LIMIT 1").fetchone()
        answers = json.loads(drill['data'])['fades']['1']['answers']
        typed = json.dumps([a if isinstance(a, str) else a[0] for a in answers])
        fast = m.answer(self.db, drill['id'], typed, 4, 2000)
        self.assertGreater(fast['level_after'][4], 1, 'without help a fast, right drill moves up')
        taught = m.answer(self.db, drill['id'], typed, 4, 2000, taught=True)
        self.assertEqual(taught['level_after'][4], 1, 'after Teach me first it stays at its level')
        self.assertLessEqual(taught['suggested'], 2)

class DailyLimit(Base):
    def test_limit_holds_across_sessions_and_resets_at_midnight(self):
        m.set_settings(self.db, {'new_per_day': {'ux-hci': 2}})
        got = self.served(n=10, deck='ux-hci')
        self.assertEqual(len(got), 2)
        out = {}
        self.assertEqual(m.next_card(self.db, 'ux-hci', out=out)[0], None); self.assertGreater(out['held'], 0)
        self.db.close(); self.db = m.connect(self.path)        # a new session (a reload, a restart): still today's limit
        self.assertEqual(m.next_card(self.db, 'ux-hci')[0], None)
        t = next(x for x in m.today(self.db)['tracks'] if x['id'] == 'ux-hci')
        self.assertEqual((t['new_today'], t['new_left']), (2, 0))
        # the next local day: move today's answers to before last midnight
        self.db.execute("UPDATE attempts SET at=? ", (m.day_start(time.time()) - 3600,)); self.db.commit()
        self.assertIsNotNone(m.next_card(self.db, 'ux-hci')[0], 'a new day, new cards again')
        self.assertEqual(next(x for x in m.today(self.db)['tracks'] if x['id'] == 'ux-hci')['new_left'], 2)

    def test_default_is_ten_and_star_sets_every_track(self):
        t = next(x for x in m.today(self.db)['tracks'] if x['id'] == 'ux-hci')
        self.assertEqual((t['new_per_day'], t['new_left']), (10, 10))
        m.set_settings(self.db, {'new_per_day': {'*': 3}})
        self.assertEqual(next(x for x in m.today(self.db)['tracks'] if x['id'] == 'ux-hci')['new_left'], 3)
        m.set_settings(self.db, {'new_per_day': {'*': None}})
        self.assertEqual(m.settings(self.db)['new_per_day'], {}, 'null takes a value out again')

class TodayNumbers(Base):
    def test_week_minutes_and_preview(self):
        self.rate('psych-design:' + self.db.execute("SELECT id FROM cards WHERE deck='psych-design' LIMIT 1").fetchone()[0].split(':', 1)[1])
        self.db.execute("UPDATE attempts SET ms=600000"); self.db.commit()         # a page left open: capped at 2 minutes a card
        t = m.today(self.db)
        self.assertEqual(len(t['week']), 7); self.assertEqual(t['week'][-1]['minutes'], 2)
        self.assertEqual(t['minutes'], 10)
        p = m.track_preview(self.db, 'psych-design')
        self.assertEqual((p['answers'], p['learned']), (1, 1)); self.assertEqual(len(p['questions']), 3)
        self.assertIsNone(m.track_preview(self.db, 'no-such-track'))
        ans = {r[0] for r in self.db.execute("SELECT answer FROM cards WHERE deck='psych-design'")}
        self.assertFalse(ans & set(p['questions']), 'a preview never shows an answer')

    def test_goal_and_confidence_per_track(self):
        m.set_settings(self.db, {'goal': {'ux-hci': '  Know   the words of HCI  '}, 'ask_confidence': ['ux-hci']})
        t = next(x for x in m.today(self.db)['tracks'] if x['id'] == 'ux-hci')
        self.assertEqual((t['goal'], t['ask_confidence']), ('Know the words of HCI', True))
        self.assertTrue(m.next_card(self.db, 'ux-hci')[0]['ask_confidence'])

if __name__ == '__main__':
    unittest.main(verbosity=1 if '-v' not in sys.argv else 2)
