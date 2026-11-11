"""Mentor with people (4.34, docs/mentor.md "People"): who is studying, one database per person, and the AI fence.

    python3 tests/mentor_people_test.py -v        (tests/run.sh runs it under "== mentor people")

The plugin is loaded the way Elaia loads it, inside a temporary HOME; every path (people file, databases, decks, the AI
config) is in that folder. Names are placeholders ("Owner One", "Learner Two")."""
import importlib.util, json, os, shutil, sqlite3, sys, tempfile, time, types, unittest

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = tempfile.mkdtemp(prefix='mentor-people-')
HOME = os.path.join(TMP, 'home')
os.environ.update(HOME=HOME, USERPROFILE=HOME, ARGUS_PEOPLE=os.path.join(TMP, 'people.json'),
                  ARGUS_MENTOR_AI=os.path.join(TMP, 'mentor-ai.json'), LEAFY_REALM=os.path.join(TMP, 'realm.json'))
for k in ('ARGUS_MENTOR_DB', 'ARGUS_DECKS', 'ARGUS_MENTOR_INBOX'): os.environ.pop(k, None)
SHARE = os.path.join(HOME, '.local', 'share', 'argus-ui')
OWNER_DB = os.path.join(SHARE, 'mentor.db')
CTX = types.SimpleNamespace(theme_dir=os.path.join(R, 'themes', 'leafy-realm'))
PEOPLE = {'people': [{'id': 'owner-one', 'name': 'Owner One', 'role': 'owner', 'logins': ['owner@example.com']},
                     {'name': 'Learner Two', 'role': 'learner', 'logins': ['learner@example.com']}]}
OWNER = {'person': 'owner-one', 'name': 'Owner One', 'role': 'owner'}
LEARNER = {'person': 'learner-two', 'name': 'Learner Two', 'role': 'learner'}
LDECK = {'id': 'own-deck', 'name': 'Learner deck', 'cards': [
    {'id': 'c1', 'prompt': 'Define: placeholder one', 'answer': 'the first placeholder', 'points': [{'idea': 'first', 'any': ['first']}]},
    {'id': 'c2', 'prompt': 'Define: placeholder two', 'answer': 'the second placeholder', 'points': [{'idea': 'second', 'any': ['second']}]}]}
# the 4.25.0 database, as it is on a server today (tests/mentor_model_test.py)
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

def load_plugin():
    spec = importlib.util.spec_from_file_location('mentor_plugin_under_test', os.path.join(R, 'plugins', 'mentor', 'plugin.py'))
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod

def write(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f: f.write(obj if isinstance(obj, str) else json.dumps(obj))

def snapshot(path):
    """Every row of the tables a person's history lives in, to compare before and after."""
    db = sqlite3.connect(path)
    try: return {t: db.execute(f"SELECT * FROM {t} ORDER BY 1").fetchall() for t in ('cards', 'sched', 'attempts', 'modules')}
    finally: db.close()

class People(unittest.TestCase):
    def setUp(self):
        shutil.rmtree(HOME, ignore_errors=True)
        for f in ('people.json', 'mentor-ai.json'):
            try: os.remove(os.path.join(TMP, f))
            except FileNotFoundError: pass
        self.p = load_plugin(); self.p.learners._cache[:] = [None, None]
    def tearDown(self):
        for _ in range(50):                  # an AI thread still running holds a lock; wait for it, then close every database
            if not self.p.PENDING: break
            time.sleep(.1)
        for b in self.p.BOOKS.values(): b.db.close()
    def people(self, obj=PEOPLE):
        write(os.environ['ARGUS_PEOPLE'], obj); self.p.learners._cache[:] = [None, None]
    def start(self, people=PEOPLE):
        if people is not None: self.people(people)
        write(os.path.join(SHARE, 'decks-learner-two', 'own.json'), LDECK)
        self.p.init(CTX)
    def get(self, path, who=None, **q):
        return self.p.get(path, {k: [v] for k, v in q.items()}, CTX, who)
    def post(self, path, body, who=None):
        return self.p.post(path, body, CTX, who)
    def study(self, who, learner=None, n=1, text='x'):
        """Answer and rate n cards as `who` (studying as `learner`); returns the card ids."""
        ids = []
        for _ in range(n):
            code, r = self.get('next', who, **({'learner': learner} if learner else {}))
            self.assertEqual(code, 200); c = r['card']
            if not c: break
            body = {'card': c['id'], 'text': text, 'ms': 1000, **({'learner': learner} if learner else {})}
            code, a = self.post('answer', body, who); self.assertEqual(code, 200, a)
            code, x = self.post('rate', {'attempt': a['attempt'], 'rating': 3, **({'learner': learner} if learner else {})}, who); self.assertEqual(code, 200, x)
            ids.append(c['id'])
        return ids

    def test_no_people_file_is_todays_behaviour(self):
        self.start(people=None)
        code, r = self.get('learners')
        self.assertEqual((code, r['me'], r['role'], r['people']), (200, 'owner', 'owner', [{'id': 'owner', 'name': 'You', 'role': 'owner'}]))
        self.assertEqual(self.p.DB, self.p.book_for(None).db, 'the owner database is opened at start, as before')
        ids = self.study(None, n=2)
        self.assertEqual(len(ids), 2)
        self.assertTrue(os.path.exists(OWNER_DB) and not [f for f in os.listdir(SHARE) if f.startswith('mentor-')], 'only mentor.db, no per-person file')
        decks = {d['id'] for d in self.get('decks')[1]['decks']}
        self.assertTrue({'ai-coding', 'psych-design', 'ux-hci'} <= decks, 'the theme decks, as before')
        code, s = self.get('status'); self.assertEqual(code, 200); self.assertTrue(s['line'] and s['action'] == 'Study 10 minutes')
        # the same, when the server says who: the owner of a file-less realm is the one person there is
        self.assertEqual(self.get('next', {'person': 'owner', 'name': 'You', 'role': 'owner'})[0], 200)

    def test_two_people_never_see_each_other(self):
        self.start()
        owner_ids = self.study(OWNER, n=2)
        learner_ids = self.study(LEARNER, n=2)
        self.assertTrue(all(i.startswith('own-deck:') for i in learner_ids), learner_ids)
        self.assertFalse(set(owner_ids) & set(learner_ids))
        self.assertTrue(os.path.exists(os.path.join(SHARE, 'mentor-learner-two.db')))
        # the learner's database holds only her own lessons: no theme deck, no inbox
        ldb = sqlite3.connect(os.path.join(SHARE, 'mentor-learner-two.db'))
        self.assertEqual({r[0] for r in ldb.execute("SELECT DISTINCT deck FROM cards")}, {'own-deck'})
        self.assertEqual(ldb.execute("SELECT COUNT(*) FROM attempts").fetchone()[0], 2); ldb.close()
        odb = sqlite3.connect(OWNER_DB)
        self.assertEqual(odb.execute("SELECT COUNT(*) FROM attempts WHERE card_id LIKE 'own-deck:%'").fetchone()[0], 0)
        self.assertEqual(odb.execute("SELECT COUNT(*) FROM attempts").fetchone()[0], 2); odb.close()
        ls, os_ = self.get('stats', LEARNER)[1], self.get('stats', OWNER)[1]
        self.assertEqual((ls['labels'], ls['cards']), (2, 2)); self.assertEqual(os_['labels'], 2); self.assertGreater(os_['cards'], 2)
        self.assertEqual({d['id'] for d in self.get('decks', LEARNER)[1]['decks']}, {'own-deck'})
        self.assertEqual(self.get('stats', LEARNER)[1]['inbox'], '', 'a learner has no inbox')
        # an attempt id of one person is not the other's: undoing the owner's last rating from the learner's side does nothing
        self.assertEqual(self.post('undo', {'attempt': 2}, LEARNER)[1].get('undone'), True, "her own last rating")
        self.assertEqual(self.post('undo', {'attempt': 2}, OWNER)[1].get('undone'), True, "his own last rating, untouched by hers")

    def test_learner_cannot_study_as_someone_else(self):
        self.start()
        ids = self.study(LEARNER, learner='owner-one', n=1)
        self.assertTrue(ids[0].startswith('own-deck:'), 'learner= from a learner is ignored')
        self.assertEqual(self.get('stats', LEARNER, learner='owner-one')[1]['labels'], 1)
        r = self.get('learners', LEARNER)[1]
        self.assertEqual((r['me'], r['role'], [x['id'] for x in r['people']]), ('learner-two', 'learner', ['learner-two']), 'she sees only herself')
        self.assertEqual(self.get('next', {'person': 'stranger', 'role': 'none'})[0], 403)
        code, msg = self.get('next', {'person': 'stranger', 'role': 'learner'})
        self.assertEqual(code, 403); self.assertIn('people file', msg['msg'])

    def test_owner_studies_as_a_learner(self):
        self.start()
        r = self.get('learners', OWNER)[1]
        self.assertEqual([x['id'] for x in r['people']], ['owner-one', 'learner-two'])
        ids = self.study(OWNER, learner='learner-two', n=1)
        self.assertTrue(ids[0].startswith('own-deck:'))
        self.assertEqual(self.get('stats', LEARNER)[1]['labels'], 1, "the owner's answer as Learner Two is in her history")
        code, msg = self.get('next', OWNER, learner='nobody-here')
        self.assertEqual(code, 404); self.assertIn('Pick a name', msg['msg'])
        self.assertEqual(self.get('today', OWNER, learner='learner-two')[1]['learner']['id'], 'learner-two')

    def test_broken_people_file_fails_closed_for_changes(self):
        self.start(people='{ not json')
        self.assertEqual(self.get('next', OWNER)[0], 200, 'reading still works, as with no file')
        code, r = self.post('settings', {'bury': False}, OWNER)
        self.assertEqual(code, 503); self.assertIn('people.json', r['msg'])

    def test_owner_database_kept_row_for_row(self):
        os.makedirs(SHARE, exist_ok=True)
        old = sqlite3.connect(OWNER_DB); old.executescript(OLD_SCHEMA)
        old.execute("INSERT INTO cards(id,deck,kind,prompt,answer,points) VALUES('old:c1','old','define','Define: old card','old answer','[]')")
        old.execute("INSERT INTO sched(card_id,stability,difficulty,due,last,reps,lapses) VALUES('old:c1',3,5,0,0,2,0)")
        old.executemany("INSERT INTO attempts(card_id,at,answer,rating) VALUES('old:c1',?,'mine',3)", [(1.0,), (2.0,)])
        old.commit(); old.close()
        before = snapshot(OWNER_DB)
        self.start()
        after = snapshot(OWNER_DB)
        self.assertEqual([r[:9] for r in after['attempts']], [r[:9] for r in before['attempts']], 'every old attempt, unchanged')
        self.assertEqual([r[:7] for r in after['sched']], [r[:7] for r in before['sched']], 'every old schedule row, unchanged')
        self.assertIn(before['cards'][0][:5], [r[:5] for r in after['cards']])
        self.study(LEARNER, n=2)
        self.study(OWNER, learner='learner-two', n=1)
        self.assertEqual(snapshot(OWNER_DB), after, "a learner's study never touches the owner's database")

    def test_ai_fence(self):
        write(os.environ['ARGUS_MENTOR_AI'], {'enabled': True, 'url': 'http://127.0.0.1:9', 'embed_model': 'fake-embed', 'timeout_s': 2})
        self.start()
        lcard = self.get('next', LEARNER)[1]['card']
        code, r = self.post('answer', {'card': lcard['id'], 'text': 'the first placeholder'}, LEARNER)
        self.assertEqual(code, 200); self.assertNotIn('ai_pending', r, "a learner's answer never starts the AI")
        code, r = self.post('answer', {'card': lcard['id'], 'text': 'the first placeholder', 'learner': 'learner-two'}, OWNER)
        self.assertNotIn('ai_pending', r, 'the owner studying as a learner: no AI either')
        self.assertEqual(self.get('ai', LEARNER)[1]['enabled'], False)
        ocard = self.get('next', OWNER, deck='ux-hci')[1]['card']
        code, r = self.post('answer', {'card': ocard['id'], 'text': 'people and the tools they use'}, OWNER)
        self.assertTrue(r.get('ai_pending'), "the owner's own answer: the AI part is started (the config is untouched)")
        for _ in range(50):
            if not self.p.PENDING: break
            time.sleep(.1)
        self.assertFalse(self.p.PENDING)

    def test_goal_is_the_owners(self):
        self.start()
        code, r = self.post('settings', {'goal': {'own-deck': 'Pass the exam'}, 'pinned': ['own-deck']}, LEARNER)
        self.assertEqual((code, r['settings']['goal'], r['settings']['pinned']), (200, {}, ['own-deck']), 'she pins, the goal is not hers to set')
        code, r = self.post('settings', {'goal': {'own-deck': 'Pass the exam'}, 'learner': 'learner-two'}, OWNER)
        self.assertEqual(r['settings']['goal'], {'own-deck': 'Pass the exam'})
        t = self.get('today', LEARNER)[1]
        self.assertEqual([(x['id'], x['goal'], x['pinned']) for x in t['tracks']], [('own-deck', 'Pass the exam', True)])
        self.assertEqual(self.get('today', OWNER)[1]['pinned'], [], "her pins are not his")

    def test_new_learner_deck_without_restart(self):
        self.start()
        self.assertEqual(self.get('stats', LEARNER)[1]['cards'], 2)
        write(os.path.join(SHARE, 'decks-learner-two', 'more.json'), {**LDECK, 'id': 'more', 'name': 'More'})
        self.assertEqual(self.get('stats', LEARNER)[1]['cards'], 4, 'a file copied into her folder shows up on the next request')

if __name__ == '__main__':
    try: unittest.main(verbosity=1 if '-v' not in sys.argv else 2)
    finally: shutil.rmtree(TMP, ignore_errors=True)
