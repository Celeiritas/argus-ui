"""Mentor clean slate and publication (4.59, docs/mentor.md "Clean slate and publication").

    python3 tests/mentor_clean_slate_test.py -v        (tests/run.sh runs it under "== mentor clean slate")

The reset (scripts/mentor-clean-slate-v1.py) runs on a copy made in a temporary HOME: the owner's old decks never come
back after a restart or a rescan, other learners stay byte for byte, and the dry run changes nothing. The gate
(plugins/mentor/publish.py) refuses every unsupported or unchecked lesson and publishes a checked one with its revision;
an attempt records the revision it saw. Normal study opens no network connection. Names are placeholders."""
import contextlib, hashlib, importlib.util, io, json, os, shutil, socket, sqlite3, sys, tempfile, types, unittest

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = tempfile.mkdtemp(prefix='mentor-clean-slate-')
HOME = os.path.join(TMP, 'home')
CONFIG = os.path.join(HOME, '.config', 'argus-ui', 'mentor.json')
os.environ.update(HOME=HOME, USERPROFILE=HOME, ARGUS_PEOPLE=os.path.join(TMP, 'people.json'), ARGUS_MENTOR_CONFIG=CONFIG,
                  ARGUS_MENTOR_AI=os.path.join(TMP, 'mentor-ai.json'), LEAFY_REALM=os.path.join(TMP, 'realm.json'))
for k in ('ARGUS_MENTOR_DB', 'ARGUS_DECKS', 'ARGUS_MENTOR_INBOX', 'ARGUS_MENTOR_LESSONS'): os.environ.pop(k, None)
SHARE = os.path.join(HOME, '.local', 'share', 'argus-ui')
INBOX, LESSONS, OWNER_DB = os.path.join(SHARE, 'inbox'), os.path.join(SHARE, 'lessons'), os.path.join(SHARE, 'mentor.db')
THEME = os.path.join(R, 'themes', 'leafy-realm')
CTX = types.SimpleNamespace(theme_dir=THEME)
CODE = os.path.join(R, 'plugins', 'mentor')
PEOPLE = {'people': [{'id': 'owner-one', 'name': 'Owner One', 'role': 'owner', 'logins': ['owner@example.com']},
                     {'name': 'Learner Two', 'role': 'learner', 'logins': ['learner@example.com']}]}
OWNER = {'person': 'owner-one', 'name': 'Owner One', 'role': 'owner'}
LEARNER = {'person': 'learner-two', 'name': 'Learner Two', 'role': 'learner'}
LDECK = {'id': 'own-deck', 'name': 'Learner deck', 'cards': [
    {'id': 'c1', 'prompt': 'Define: placeholder one', 'answer': 'the first placeholder', 'points': [{'idea': 'first', 'any': ['first']}]}]}

def term(i, word, define):
    return {'id': f't-{i}', 'term': word, 'concise_definition': define, 'cloze_prompt': f'{define} This is called {{{{BLANK}}}}.'}

OLD_LESSON = {'metadata': {'module_name': 'Old capture'}, 'cta_summary': {'orientation': 'An old capture.'},
              'tier_3_terminology_cards': [term(1, 'Placeholder', 'A word that stands in for another.')]}
LESSON = {'metadata': {'module_name': 'Fetch and merge'}, 'cta_summary': {'orientation': 'Two steps, not one.'},
          'tier_3_terminology_cards': [term(1, 'Fetch', 'Copies new commits into your remote-tracking refs, changing no branch.'),
                                       term(2, 'Integration', 'Brings fetched commits into your branch, by merge or rebase.')]}

def sha(path):
    with open(path, 'rb') as fh: return hashlib.sha256(fh.read()).hexdigest()

def tree(folder):
    """Every file under folder with its sha256: to show something was left byte for byte."""
    out = {}
    for d, _, files in os.walk(folder):
        for f in files: out[os.path.relpath(os.path.join(d, f), folder)] = sha(os.path.join(d, f))
    return out

def write(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f: f.write(obj if isinstance(obj, bytes) else (obj if isinstance(obj, str) else json.dumps(obj)).encode('utf-8'))

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod

RESET = load('mentor_clean_slate_v1', os.path.join(R, 'scripts', 'mentor-clean-slate-v1.py'))

def evidence(raw, ids, **over):
    ev = {'format': 'mentor-evidence/1', 'policy': 'mentor-policy/1', 'payload_sha256': hashlib.sha256(raw).hexdigest(),
          'revision': '2026-11-18a', 'risk': 'routine', 'sources': [{'locator': 'git help fetch', 'revision': 'git 2.47'}],
          'items': {i: {'status': 'ready', 'checks': {c: 'pass' for c in ('answerability', 'alignment', 'leakage', 'prerequisites',
                                                                         'support', 'solution', 'novelty', 'contract')}} for i in ids}}
    ev.update(over)
    return ev

class Base(unittest.TestCase):
    def setUp(self):
        shutil.rmtree(HOME, ignore_errors=True)
        write(os.environ['ARGUS_PEOPLE'], PEOPLE)
        self.p = None
    def tearDown(self):
        self.close()
    def close(self):
        if self.p:
            for b in self.p.BOOKS.values(): b.db.close()
            self.p.BOOKS.clear()
    def start(self):
        """A server start: the plugin loaded fresh, as after a restart."""
        self.close()
        self.p = load('mentor_plugin_under_test', os.path.join(CODE, 'plugin.py'))
        self.p.learners._cache[:] = [None, None]
        self.m = self.p.mentor
        self.p.init(CTX)
    def get(self, path, who=OWNER, **q):
        return self.p.get(path, {k: [v] for k, v in q.items()}, CTX, who)
    def post(self, path, body, who=OWNER):
        return self.p.post(path, body, CTX, who)
    def study(self, who, n=1, **extra):
        out = []
        for _ in range(n):
            code, r = self.get('next', who); self.assertEqual(code, 200)
            c = r['card']
            if not c: break
            code, a = self.post('answer', {'card': c['id'], 'text': 'first', 'ms': 1000}, who); self.assertEqual(code, 200, a)
            code, x = self.post('rate', {'attempt': a['attempt'], 'rating': 3, **extra}, who); self.assertEqual(code, 200, x)
            out.append((c['id'], a['attempt']))
        return out
    def owner_rows(self, sql):
        db = sqlite3.connect(OWNER_DB)
        try: return db.execute(sql).fetchall()
        finally: db.close()
    def reset(self, *args):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = RESET.main(['--share', SHARE, '--theme-decks', os.path.join(THEME, 'decks'), '--config', CONFIG, '--service', '',
                               '--code', CODE, '--stamp', '20261118-0000', *args])
        return code, buf.getvalue()

class Reset(Base):
    def old_realm(self):
        """The owner studied the theme decks and an inbox capture; a learner studied her own deck."""
        write(os.path.join(INBOX, 'old_capture.json'), OLD_LESSON)
        write(os.path.join(SHARE, 'decks-learner-two', 'own.json'), LDECK)
        self.start()
        self.assertTrue(self.study(OWNER, n=2)); self.assertTrue(self.study(LEARNER, n=1))
        self.assertIn('old_capture', {r[0] for r in self.owner_rows("SELECT DISTINCT deck FROM cards")})
        self.close()

    def test_dry_run_changes_nothing(self):
        self.old_realm()
        before = tree(HOME)
        code, out = self.reset()
        self.assertEqual(code, 0, out)
        self.assertIn('DRY RUN', out); self.assertIn('old_capture.json', out); self.assertIn('Dry run only. Nothing was changed.', out)
        self.assertIn('other learners: decks-learner-two, mentor-learner-two.db', out)
        self.assertEqual(tree(HOME), before, 'a dry run writes nothing, not even a database journal')

    def test_reset_then_restart_and_rescan_shows_no_old_decks(self):
        self.old_realm()
        learner_before = {k: v for k, v in tree(SHARE).items() if k.startswith('decks-learner-two') or k == 'mentor-learner-two.db'}
        people_before = sha(os.environ['ARGUS_PEOPLE'])
        old_inbox_sha = sha(os.path.join(INBOX, 'old_capture.json'))
        code, out = self.reset('--apply')
        self.assertEqual(code, 0, out)
        snap = os.path.join(SHARE, '.set-aside-20261118-0000-mentor-clean-slate')
        with open(os.path.join(snap, 'manifest.json'), encoding='utf-8') as fh: man = json.load(fh)
        self.assertEqual(man['quick_check'], 'ok')
        self.assertEqual({os.path.basename(f['to']) for f in man['files']} >= {'mentor.db', 'old_capture.json'}, True)
        snapdb = sqlite3.connect(os.path.join(snap, 'mentor.db'))
        self.assertEqual(snapdb.execute("SELECT COUNT(*) FROM attempts").fetchone()[0], 2, 'the snapshot keeps the attempts'); snapdb.close()
        self.assertEqual(sha(os.path.join(snap, 'inbox', 'old_capture.json')), old_inbox_sha)
        self.assertFalse(os.path.exists(OWNER_DB))
        # restart, then put every old file back where Mentor reads and rescan
        self.start()
        shutil.copy(os.path.join(snap, 'inbox', 'old_capture.json'), os.path.join(INBOX, 'old_capture.json'))
        os.makedirs(os.path.join(SHARE, 'decks'), exist_ok=True)
        shutil.copy(os.path.join(THEME, 'decks', 'ux-hci.json'), os.path.join(SHARE, 'decks', 'ux-hci.json'))
        self.start()                                    # a second restart loads the deck folder again
        self.assertEqual(self.get('next')[1]['card'], None, 'no old card is due or new')
        self.get('stats'); self.m.scan_inbox(self.p.book_for(None).db)
        self.assertEqual(self.owner_rows("SELECT COUNT(*) FROM cards"), [(0,)])
        self.assertEqual(self.owner_rows("SELECT COUNT(*) FROM attempts"), [(0,)])
        self.assertEqual(self.owner_rows("SELECT COUNT(*) FROM sched"), [(0,)])
        self.assertEqual(self.get('decks')[1]['decks'], [], 'no theme deck and no retired copy is listed')
        self.assertEqual(self.owner_rows("SELECT value FROM settings WHERE key='_collection'"), [('"owner-20261118-0000"',)])
        # other learners: the same bytes, and she still studies her own deck
        self.assertEqual({k: v for k, v in tree(SHARE).items() if k.startswith('decks-learner-two') or k == 'mentor-learner-two.db'}, learner_before)
        self.assertEqual(sha(os.environ['ARGUS_PEOPLE']), people_before)
        self.assertEqual([d['id'] for d in self.get('decks', LEARNER)[1]['decks']], ['own-deck'], 'she still has her own deck')
        self.assertEqual(self.get('stats', LEARNER)[1]['labels'], 1, 'and her one rated card')

    def test_a_retired_lesson_cannot_be_published_again(self):
        self.old_realm(); self.reset('--apply'); self.start()
        with open(os.path.join(SHARE, '.set-aside-20261118-0000-mentor-clean-slate', 'inbox', 'old_capture.json'), 'rb') as fh: raw = fh.read()
        write(os.path.join(LESSONS, 'old_capture.json'), raw)
        write(os.path.join(LESSONS, 'old_capture.evidence.json'), evidence(raw, ['t-1']))
        self.m.scan_inbox(self.p.book_for(None).db)
        msg = self.owner_rows("SELECT ok, msg FROM imports WHERE path='lessons/old_capture.json'")[0]
        self.assertEqual(msg[0], 0); self.assertIn('held', msg[1]); self.assertIn('retired', msg[1])

    def test_apply_refuses_old_code(self):
        self.old_realm()
        code, out = self.reset('--apply', '--code', os.path.join(TMP, 'no-such-code'))
        self.assertEqual(code, 3); self.assertIn('STOP', out)
        self.assertTrue(os.path.exists(OWNER_DB) and not os.path.exists(CONFIG), 'nothing was changed')

    def test_keep_leaves_a_file_active(self):
        self.old_realm(); write(os.path.join(INBOX, 'path-keep-me.json'), LESSON)
        code, out = self.reset('--apply', '--keep', 'path-*.json')
        self.assertEqual(code, 0, out)
        self.assertTrue(os.path.exists(os.path.join(INBOX, 'path-keep-me.json')))
        self.assertFalse(os.path.exists(os.path.join(INBOX, 'old_capture.json')))

class Gate(Base):
    def publish(self, name, doc, **over):
        raw = json.dumps(doc).encode('utf-8')
        ids = [i['id'] for i in doc.get('tier_3_terminology_cards', [])]
        ev = over.pop('ev') if 'ev' in over else evidence(raw, ids, **over)
        write(os.path.join(LESSONS, name + '.json'), raw)
        if ev is not False: write(os.path.join(LESSONS, name + '.evidence.json'), ev)
        self.m.scan_inbox(self.p.book_for(None).db)
        return self.owner_rows(f"SELECT ok, msg FROM imports WHERE path='lessons/{name}.json'")[0]

    def setUp(self):
        super().setUp(); write(CONFIG, {'format': 'mentor-collection/1', 'collection': 'owner-test', 'theme_decks': False,
                                        'legacy_inbox': False, 'retired': {'files': [], 'decks': []}}); self.start()

    def held(self, row, *words):
        self.assertEqual(row[0], 0, row); self.assertTrue(row[1].startswith('held: '), row)
        for w in words: self.assertIn(w, row[1])

    def test_unchecked_and_unsupported_lessons_are_held(self):
        self.held(self.publish('a', LESSON, ev=False), 'nothing was checked')
        self.held(self.publish('b', LESSON, payload_sha256='0' * 64), 'other bytes')
        self.held(self.publish('c', LESSON, sources=[{'locator': 'a page'}]), 'locator and the revision')
        ev = evidence(json.dumps(LESSON).encode('utf-8'), ['t-1', 't-2']); ev['items']['t-2'] = {'status': 'hold', 'reason': 'unsupported claim'}
        self.held(self.publish('d', LESSON, ev=ev), 't-2: on hold')
        ev = evidence(json.dumps(LESSON).encode('utf-8'), ['t-1']); self.held(self.publish('e', LESSON, ev=ev), 't-2: not in the evidence')
        ev = evidence(json.dumps(LESSON).encode('utf-8'), ['t-1', 't-2']); ev['items']['t-1']['checks']['leakage'] = 'fail'
        self.held(self.publish('f', LESSON, ev=ev), 'checks not passed: leakage')
        self.held(self.publish('g', LESSON, policy='mentor-policy/0'), 'not the installed')
        clin = json.loads(json.dumps(LESSON)); clin['tier_3_terminology_cards'][0]['concise_definition'] = 'The usual dosage for adults.'
        self.held(self.publish('h', clin), 'never routine')
        self.held(self.publish('i', clin, risk='clinical', review={'by': 'Claude', 'qualification': 'model'}), 'Claude cannot sign')
        self.held(self.publish('git_20261118_0912', LESSON), 'named by a time')
        self.assertEqual(self.owner_rows("SELECT COUNT(*) FROM cards"), [(0,)], 'nothing held was imported')

    def test_publish_then_revise_binds_attempts_to_revisions(self):
        row = self.publish('fetch-merge', LESSON)
        self.assertEqual(row[0], 1, row); self.assertIn('published revision 2026-11-18a: 2 cards', row[1])
        self.held(self.publish('fetch-merge-2', LESSON), 'already teaches')
        (cid, att), = self.study(OWNER, n=1, unclear=True)
        rev1 = self.owner_rows(f"SELECT rev FROM cards WHERE id='{cid}'")[0][0]
        self.assertTrue(rev1)
        self.assertEqual(self.owner_rows(f"SELECT card_rev, flag FROM attempts WHERE id={att}"), [(rev1, 'unclear')])
        # a changed lesson without a reason is held, and the published revision stays
        v2 = json.loads(json.dumps(LESSON))
        for t in v2['tier_3_terminology_cards']: t['concise_definition'] += ' (revised)'
        self.held(self.publish('fetch-merge', v2, revision='2026-11-18b'), 'correction.reason')
        self.assertEqual(self.owner_rows(f"SELECT rev FROM cards WHERE id='{cid}'")[0][0], rev1)
        row = self.publish('fetch-merge', v2, revision='2026-11-18b', correction={'reason': 'item 1 was unclear (flagged)'})
        self.assertEqual(row[0], 1, row)
        rev2 = self.owner_rows(f"SELECT rev FROM cards WHERE id='{cid}'")[0][0]
        self.assertNotEqual(rev1, rev2)
        self.assertEqual(self.owner_rows(f"SELECT reason, source FROM card_revs WHERE card_id='{cid}' AND rev='{rev2}'"),
                         [('item 1 was unclear (flagged)', 'fetch-merge.json 2026-11-18b')])
        self.assertEqual(self.owner_rows(f"SELECT card_rev FROM attempts WHERE id={att}"), [(rev1,)], 'the old attempt keeps what it saw')
        ctx = self.get('context')[1]
        self.assertEqual((ctx['format'], ctx['policy'], ctx['collection']), ('mentor-context/1', 'mentor-policy/1', 'owner-test'))
        f = ctx['flags'][0]
        self.assertEqual((f['flag'], f['seen_rev'], f['current_rev'], f['revised_since']), ('unclear', rev1, rev2, True))
        self.assertEqual(self.get('context', LEARNER)[0], 403, 'only the owner reads the context packet')

class NoNetwork(Base):
    def test_normal_study_opens_no_connection(self):
        write(CONFIG, {'format': 'mentor-collection/1', 'collection': 'owner-test', 'theme_decks': True, 'legacy_inbox': True,
                       'retired': {'files': [], 'decks': []}})
        write(os.path.join(TMP, 'mentor-ai.json'), {'enabled': True, 'url': 'http://127.0.0.1:9/', 'model': 'none'})
        calls = []
        real = socket.socket.connect
        def refuse(self_, addr):
            calls.append(addr); raise OSError('no network in study')
        socket.socket.connect = refuse
        try:
            self.start()
            self.assertEqual(len(self.study(OWNER, n=3)), 3)
            self.assertEqual(self.get('today')[0], 200); self.assertEqual(self.get('stats')[0], 200)
        finally: socket.socket.connect = real
        self.assertEqual(calls, [], 'study, rating, Today and stats open no connection (no model, no web)')

if __name__ == '__main__':
    try: unittest.main()
    finally: shutil.rmtree(TMP, ignore_errors=True)
