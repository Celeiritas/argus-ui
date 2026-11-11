"""Mentor with people (4.38, docs/mentor.md "People"): who is studying, one database per person, and the AI fence.

    python3 tests/mentor_people_test.py -v        (tests/run.sh runs it under "== mentor people")

The plugin is loaded the way Elaia loads it, inside a temporary HOME; every path (people file, databases, decks, the AI
config) is in that folder. Names are placeholders ("Owner One", "Learner Two")."""
import contextlib, importlib.util, io, json, os, shutil, sqlite3, sys, tempfile, threading, time, types, unittest

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
        else: self.p.learners.MUST_EXIST = False      # "no people file" = ARGUS_PEOPLE not set and nothing at the default path
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
        self.assertEqual(self.get('next', None)[0], 200, 'not told who (an older server): reading still works, as with no file')
        self.assertEqual(self.get('next', OWNER)[0], 503, 'a named owner with no mentor.db of record: Mentor does not decide he is the owner')
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

    # ---- 4.38: the fix round after review ----
    def test_lesson_folder_reload_holds_the_lock(self):
        """Review B2: several threads study as Learner Two while one keeps changing her lesson files. Before the fix the
        reload wrote on her connection outside its lock: SQLite errors and ratings lost. Three rounds."""
        self.start()
        cards = [{'id': f'c{i}', 'prompt': f'Define: placeholder {i}', 'answer': f'placeholder answer {i}',
                  'points': [{'idea': 'answer', 'any': ['answer']}]} for i in range(40)]
        for round_ in range(3):
            errors, lost, stop = [], [0], threading.Event()
            def study():
                for _ in range(25):
                    try:
                        code, r = self.get('today', LEARNER)
                        code, r = self.get('next', LEARNER)
                        c = r.get('card') if code == 200 else None
                        if not c: continue
                        code, a = self.post('answer', {'card': c['id'], 'text': 'answer', 'ms': 900}, LEARNER)
                        if code != 200: errors.append(a); continue
                        code, x = self.post('rate', {'attempt': a['attempt'], 'rating': 1}, LEARNER)
                        if code != 200: lost[0] += 1
                    except Exception as e: errors.append(repr(e))
            def churn():
                i = 0
                while not stop.is_set():
                    write(os.path.join(SHARE, 'decks-learner-two', 'busy.json'), {'id': 'busy', 'name': 'Busy', 'cards': cards[: 10 + i % 30]})
                    i += 1; time.sleep(.002)
            ws = [threading.Thread(target=study) for _ in range(4)]; ch = threading.Thread(target=churn)
            ch.start(); [w.start() for w in ws]; [w.join() for w in ws]; stop.set(); ch.join()
            self.assertEqual((errors[:3], lost[0]), ([], 0), f'round {round_ + 1}: no errors, no lost ratings')
            db = sqlite3.connect(os.path.join(SHARE, 'mentor-learner-two.db'))
            unrated = db.execute("SELECT COUNT(*) FROM attempts WHERE rating IS NULL").fetchone()[0]; db.close()
            self.assertEqual(unrated, 0, 'every answer has its rating')

    def test_two_owners_keep_their_histories(self):
        """Review S1: mentor.db belongs to a person id stored in it, not to the order of lines in the people file."""
        two = {'people': [{'id': 'owner-one', 'name': 'Owner One', 'role': 'owner'}, {'id': 'owner-b', 'name': 'Owner B', 'role': 'owner'},
                          PEOPLE['people'][1]]}
        self.start(two)
        write(os.path.join(SHARE, 'decks-owner-b', 'own.json'), LDECK)        # a second owner studies her own lessons, as a learner does
        one = {'person': 'owner-one', 'name': 'Owner One', 'role': 'owner'}; ob = {'person': 'owner-b', 'name': 'Owner B', 'role': 'owner'}
        self.study(one, n=1, text='ONE-WAS-HERE'); self.study(ob, n=1, text='B-WAS-HERE')
        def mine(path):
            with contextlib.closing(sqlite3.connect(path)) as db: return {r[0] for r in db.execute("SELECT answer FROM attempts")}
        self.assertEqual(mine(OWNER_DB), {'ONE-WAS-HERE'}); self.assertEqual(mine(os.path.join(SHARE, 'mentor-owner-b.db')), {'B-WAS-HERE'})
        self.people({'people': [two['people'][1], two['people'][0], two['people'][2]]})      # lines swapped: Owner B first now
        self.study(one, n=1, text='ONE-AGAIN'); self.study(ob, n=1, text='B-AGAIN')
        self.assertEqual(mine(OWNER_DB), {'ONE-WAS-HERE', 'ONE-AGAIN'}, "Owner One keeps mentor.db")
        self.assertEqual(mine(os.path.join(SHARE, 'mentor-owner-b.db')), {'B-WAS-HERE', 'B-AGAIN'}, "Owner B keeps hers")
        self.assertFalse(os.path.exists(os.path.join(SHARE, 'mentor-owner-one.db')), 'no new empty database for Owner One')
        self.assertEqual(self.get('learners', None)[1]['me'], 'owner-one', 'not told who: the person mentor.db belongs to')

    def test_owner_id_renamed_takes_mentor_db_over(self):
        self.start()
        self.study(OWNER, n=1, text='OLD-ID')
        renamed = {'people': [{'id': 'owner-renamed', 'name': 'Owner One', 'role': 'owner'}, PEOPLE['people'][1]]}
        self.people(renamed)
        err = io.StringIO()
        with contextlib.redirect_stderr(err): code, r = self.get('stats', {'person': 'owner-renamed', 'name': 'Owner One', 'role': 'owner'})
        self.assertEqual((code, r['labels']), (200, 1), 'the renamed owner still studies mentor.db')
        self.assertIn('owner-one', err.getvalue()); self.assertIn('owner-renamed', err.getvalue())
        self.assertEqual(self.p.mentor.meta(self.p.book_for(None).db, 'person'), 'owner-renamed', 'the stored id is updated')

    def test_role_comes_from_the_people_file(self):
        """Mentor reads the role from its own people file, never from `who` alone."""
        self.start()
        code, r = self.get('next', {'person': 'stranger', 'name': 'Stranger', 'role': 'owner'})
        self.assertEqual(code, 403); self.assertIn('people file', r['msg'])
        code, r = self.get('next', {'person': None, 'role': 'owner'})
        self.assertEqual(code, 403, 'an owner claim with no person is refused')
        lt = {'person': 'learner-two', 'name': 'Learner Two', 'role': 'owner'}
        self.assertEqual(self.get('learners', lt)[1]['role'], 'learner', 'an owner claim for a learner counts as learner')
        self.assertTrue(self.get('next', lt, learner='owner-one')[1]['card']['id'].startswith('own-deck:'), '... and studies only as herself')
        self.assertEqual(self.get('ai', lt)[1]['enabled'], False)
        down = {'person': 'owner-one', 'name': 'Owner One', 'role': 'learner'}
        self.assertEqual(self.get('learners', down)[1]['role'], 'learner', 'the smaller of the two roles counts')

    def test_no_people_file_any_who_is_the_owner(self):
        self.start(people=None)
        self.assertEqual(self.get('learners', {'person': 'someone', 'role': 'owner'})[1]['me'], 'owner')
        self.assertEqual(self.get('next', {'person': 'someone', 'role': 'none'})[0], 403)

    def test_a_bad_entry_makes_the_file_unusable(self):
        """Review S9, and the server's reader (#45): a duplicate id, an unknown role, an entry without a name or logins that
        are not a list of names make the whole file unusable, with one log line: read as no file, every change refused,
        and a learner refused even for reading."""
        bad = [({'id': 'learner-two', 'name': 'Second Learner', 'role': 'learner'}, 'used twice'),
               ({'name': 'Third', 'role': 'teacher'}, "role 'teacher'"), ({'role': 'learner'}, 'has no name'),
               ({'name': 'Fourth', 'role': 'learner', 'logins': 'fourth@example.com'}, 'not a list')]
        for k, (entry, words) in enumerate(bad):
            with self.subTest(words):
                if k: self.tearDown(); self.setUp()
                err = io.StringIO()
                with contextlib.redirect_stderr(err):
                    self.start({'people': PEOPLE['people'] + [entry]})
                    r = self.get('learners', None)[1]
                self.assertIn(words, err.getvalue())
                self.assertEqual(([x['id'] for x in r['people']], bool(r['problem'])), (['owner'], True), 'read as no file, the problem named')
                code, x = self.post('settings', {'bury': False}, OWNER)
                self.assertEqual(code, 503); self.assertIn('people.json', x['msg'])
                self.assertEqual(self.get('next', LEARNER)[0], 503, "a learner is refused: it cannot be told whose lessons are hers")
                self.assertEqual(self.get('next', None)[0], 200)

    # ---- 4.38, second fix round (review R4b) ----
    def answers(self, path):
        with contextlib.closing(sqlite3.connect(path)) as db: return db.execute("SELECT COUNT(*) FROM attempts").fetchone()[0]

    def test_people_file_gone_where_argus_people_points(self):
        """R4b F1 (a, b): a good file, then it is moved away while ARGUS_PEOPLE names it. The server keeps its last good copy
        and still calls her a learner; Mentor must not make her the owner: 503, nothing written, no request to the model."""
        two = {'people': PEOPLE['people'] + [{'id': 'owner-b', 'name': 'Owner B', 'role': 'owner'}]}
        self.start(two)
        self.study(OWNER, n=1); self.study(LEARNER, n=1)
        write(os.environ['ARGUS_MENTOR_AI'], {'enabled': True, 'url': 'http://127.0.0.1:9', 'embed_model': 'fake-embed', 'timeout_s': 2})   # the AI on from here
        before = self.answers(OWNER_DB)
        aside = os.environ['ARGUS_PEOPLE'] + '.set-aside'; os.replace(os.environ['ARGUS_PEOPLE'], aside); self.p.learners._cache[:] = [None, None]
        try:
            card = 'ai-coding:' + json.load(open(os.path.join(R, 'themes', 'leafy-realm', 'decks', 'ai-coding.json'), encoding='utf-8'))['cards'][0]['id']
            for path in ('next', 'today', 'learners', 'stats'):
                code, r = self.get(path, LEARNER)
                self.assertEqual(code, 503, path); self.assertEqual(r['msg'], self.p.learners.GENERAL, 'a general sentence, never a path')
            code, r = self.post('answer', {'card': card, 'text': 'review the diff'}, LEARNER)
            self.assertEqual(code, 503); self.assertNotIn('ai_pending', r)
            self.assertEqual(self.get('ai', LEARNER)[0], 503)
            ob = {'person': 'owner-b', 'name': 'Owner B', 'role': 'owner'}
            self.assertEqual(self.get('next', ob)[0], 503, "a second owner never gets the first owner's mentor.db")
            code, r = self.post('answer', {'card': card, 'text': 'x'}, ob); self.assertEqual(code, 503)
            self.assertEqual(self.get('next', OWNER)[0], 200, "the owner mentor.db belongs to still reads his own")
            code, r = self.post('settings', {'bury': False}, OWNER)
            self.assertEqual(code, 503); self.assertIn('people.json', r['msg']); self.assertNotIn(HOME, r['msg'])
            self.assertEqual(self.answers(OWNER_DB), before, "nothing was written into the owner's database")
            self.assertFalse(self.p.PENDING)
        finally: os.replace(aside, os.environ['ARGUS_PEOPLE']); self.p.learners._cache[:] = [None, None]
        self.assertEqual(self.get('today', LEARNER)[1]['learner']['id'], 'learner-two', 'the file back: she is herself again')

    def test_argus_people_empty_means_the_default_path(self):
        """R4b F1 (c): ARGUS_PEOPLE='' and a good file at the default path: Mentor reads that file, as the server does."""
        default = os.path.join(HOME, '.config', 'argus-ui', 'people.json')
        old = os.environ['ARGUS_PEOPLE']; os.environ['ARGUS_PEOPLE'] = ''
        try:
            write(default, PEOPLE); self.p = load_plugin(); self.p.learners._cache[:] = [None, None]
            self.assertEqual((os.path.normcase(self.p.learners.FILE), self.p.learners.MUST_EXIST), (os.path.normcase(default), False))
            self.start(people=None); self.p.learners.MUST_EXIST = False
            self.assertEqual(self.get('today', LEARNER)[1]['learner']['id'], 'learner-two', 'she is herself')
            self.assertEqual(self.get('learners', OWNER)[1]['me'], 'owner-one')
        finally: os.environ['ARGUS_PEOPLE'] = old

    def test_people_file_a_link_whose_target_is_gone(self):
        """R4b F1 (d): a dangling link is unusable, as for the server (Linux; Windows needs a privilege to make links)."""
        target = os.path.join(TMP, 'people-target.json'); write(target, PEOPLE)
        os.replace(os.environ['ARGUS_PEOPLE'], os.environ['ARGUS_PEOPLE'] + '.away') if os.path.exists(os.environ['ARGUS_PEOPLE']) else None
        try: os.symlink(target, os.environ['ARGUS_PEOPLE'])
        except (OSError, NotImplementedError) as e: self.skipTest(f'no symbolic link on this machine ({e.__class__.__name__})')
        try:
            self.p.learners.MUST_EXIST = False; self.start(people=None); self.p.learners.MUST_EXIST = False
            self.assertEqual(self.get('today', LEARNER)[1]['learner']['id'], 'learner-two')
            os.replace(target, target + '.gone'); self.p.learners._cache[:] = [None, None]
            self.assertEqual(self.get('next', LEARNER)[0], 503, 'the link is dead: she is refused, not made the owner')
        finally:
            os.unlink(os.environ['ARGUS_PEOPLE'])     # the link this test made (not a file of anybody's)

    def test_no_people_file_no_person_unchanged(self):
        """R4b F1 (e): no people file and nobody named: one owner, "You", exactly as before."""
        self.start(people=None)
        self.assertEqual(self.get('learners', None)[1]['people'], [{'id': 'owner', 'name': 'You', 'role': 'owner'}])
        self.assertEqual(len(self.study(None, n=1)), 1)
        self.assertEqual(self.get('next', LEARNER)[0], 503, 'with no people file the server never names a learner; if it does, she is refused')

    def test_refusals_never_show_the_home_folder(self):
        """R4b S-b: a learner gets a general sentence; the owner the path as ~/...."""
        self.start('{ not json')
        code, r = self.get('today', LEARNER)
        self.assertEqual((code, r['msg']), (503, self.p.learners.GENERAL))
        self.assertEqual(self.p.learners.shown(os.path.join(os.path.expanduser('~'), '.config', 'argus-ui', 'people.json')), '~/.config/argus-ui/people.json')
        code, r = self.post('settings', {'bury': False}, None)
        self.assertEqual(code, 503); self.assertIn('people.json', r['msg'], 'the owner is told which file')

    def test_deck_folder_only_for_the_owner(self):
        """R4b S-c: stats carries deck_folder only when an owner asks."""
        self.start()
        self.assertNotIn('deck_folder', self.get('stats', LEARNER)[1])
        self.assertEqual(self.get('stats', OWNER, learner='learner-two')[1]['deck_folder'], '~/.local/share/argus-ui/decks-learner-two')

    def test_people_file_nested_too_deeply(self):
        """R4b F3: RecursionError is unusable like the other cases, not a 500 for everybody."""
        deep = '{"people": ' + '[' * 100000 + ']' * 100000 + '}'
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.start(deep)
            code, r = self.get('next', None)
        self.assertEqual(code, 200, 'not told who: read as no file'); self.assertIn('nested too deeply', err.getvalue())
        self.assertEqual(self.get('next', LEARNER)[0], 503)
        self.assertEqual(self.post('settings', {'bury': False}, OWNER)[0], 503)

    def test_two_owners_rename_gives_mentor_db_to_nobody(self):
        """R4b S-a: with two owners a stored id that leaves the file is not handed to the other owner."""
        two = {'people': [{'id': 'owner-one', 'name': 'Owner One', 'role': 'owner'}, {'id': 'owner-b', 'name': 'Owner B', 'role': 'owner'}]}
        self.start(two)
        write(os.path.join(SHARE, 'decks-owner-b', 'own.json'), LDECK)
        self.study({'person': 'owner-one', 'role': 'owner'}, n=1, text='ONE-HISTORY')
        self.people({'people': [{'id': 'owner-renamed', 'name': 'Owner One', 'role': 'owner'}, two['people'][1]]})
        err = io.StringIO()
        with contextlib.redirect_stderr(err): self.study({'person': 'owner-b', 'role': 'owner'}, n=1, text='B')
        with contextlib.closing(sqlite3.connect(OWNER_DB)) as db: mine = {r[0] for r in db.execute("SELECT answer FROM attempts")}
        self.assertEqual(mine, {'ONE-HISTORY'}, "Owner B never studies Owner One's history")
        self.assertIn('goes to nobody', err.getvalue())
        self.assertEqual(self.p.mentor.meta(self.p.book_for(None).db, 'person'), 'owner-one', 'the stored id stays')
        self.people(two)
        self.assertEqual(self.get('stats', {'person': 'owner-one', 'role': 'owner'})[1]['labels'], 1, 'the id back: his history is his again')

if __name__ == '__main__':
    try: unittest.main(verbosity=1 if '-v' not in sys.argv else 2)
    finally: shutil.rmtree(TMP, ignore_errors=True)
