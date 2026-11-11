"""Mentor 4.37 without a browser: tracks, pin and shelf, question first, the daily limit of new cards, Today's numbers.

    python3 tests/mentor_today_test.py -v        (tests/run.sh runs it under "== mentor today")

Each test gets its own temporary database and inbox, loaded with the theme's decks; nothing outside a temporary folder is touched."""
import importlib.util, os, shutil, sys, tempfile, time, unittest

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
        self.assertEqual(t['new_left'], sum(x['new_left'] for x in t['tracks'] if x['id'] in t['scope']))

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
