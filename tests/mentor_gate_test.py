"""End to end with the real Mentor plugin (plugins/mentor, its "roles" and its `who`), docs/people.md: a learner reaches her
own study routes (every route Mentor declares for learners) and no other route; the owner sees every person in `learners` and
may study as the learner in `today`; a stranger gets nothing; and when the people file that ARGUS_PEOPLE names goes away
(the server keeps its last good copy and still calls her a learner), Mentor refuses her (503) and writes nothing into the
owner's database (4.38, review R4b F1).

    python3 tests/mentor_gate_test.py -v        (tests/run.sh runs it under "== people and roles")

Same stand-in as tests/gate_test.py: on Linux the real /proc lookup runs (ARGUS_SERVE_UID = this test's user id); without
/proc it is simulated and says so. Mentor runs in this process with a temporary HOME; nothing outside it is touched."""
import http.client, importlib.util, json, os, shutil, sys, tempfile, threading, unittest

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.environ.get('MENTOR_SRC') or os.path.join(R, 'plugins', 'mentor')
HAS_PROC = os.path.isfile('/proc/net/tcp')
ME = os.getuid() if hasattr(os, 'getuid') else 4242
TMP = tempfile.mkdtemp(prefix='argus-mentor-gate-')
HOME, STATIC, BUNDLED = os.path.join(TMP, 'home'), os.path.join(TMP, 'static'), os.path.join(TMP, 'bundled')
SHARE = os.path.join(HOME, '.local', 'share', 'argus-ui'); PEOPLE = os.path.join(HOME, '.config', 'argus-ui', 'people.json')
for d in (os.path.join(STATIC, 'decks'), os.path.join(SHARE, 'decks'), os.path.join(SHARE, 'decks-learner-two'), os.path.dirname(PEOPLE)):
    os.makedirs(d, exist_ok=True)
shutil.copytree(SRC, os.path.join(BUNDLED, 'mentor'), ignore=shutil.ignore_patterns('__pycache__'))
shutil.copy(os.path.join(R, 'tests', 'deck-fixtures', 'good-lesson.json'), os.path.join(SHARE, 'decks-learner-two'))
with open(os.path.join(STATIC, 'theme.json'), 'w') as f:
    json.dump({'title': 'Elaia', 'agents': [{'key': 'argus', 'name': 'Argus'}, {'key': 'mentor', 'name': 'Mentor', 'domain': 'Teacher · lessons'}]}, f)
with open(os.path.join(STATIC, 'index.html'), 'w') as f: f.write('<!doctype html><script>const STATE = /*STATE*/null;</script>')
with open(PEOPLE, 'w') as f:
    json.dump({'people': [{'id': 'owner-one', 'name': 'Owner One', 'role': 'owner', 'logins': ['owner@example.com']},
                          {'id': 'learner-two', 'name': 'Learner Two', 'role': 'learner', 'logins': ['learner@example.com']}]}, f)
os.environ.update(HOME=HOME, USERPROFILE=HOME, ARGUS_STATIC=STATIC, ARGUS_BUNDLED=BUNDLED, ARGUS_PLUGINS=os.path.join(TMP, 'mine'),
                  ARGUS_PEOPLE=PEOPLE, ARGUS_SERVE_UID=str(ME), ARGUS_DEV='1', ARGUS_MENTOR_DB=os.path.join(SHARE, 'mentor.db'),
                  ARGUS_DECKS=os.path.join(SHARE, 'decks'), ARGUS_LINKS=os.path.join(TMP, 'links.json'),
                  ARGUS_REGISTRY=os.path.join(TMP, 'agents'), ARGUS_ALERTS=os.path.join(TMP, 'alerts'), ARGUS_WATCH='0', ARGUS_SYSTEMCTL=sys.executable)
for k in ('ARGUS_BIND', 'ARGUS_WEATHER', 'ARGUS_MENTOR_AI'): os.environ.pop(k, None)
_spec = importlib.util.spec_from_file_location('argus_ui_mentor_gate', os.path.join(R, 'server', 'argus_ui.py'))
a = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(a)
if not HAS_PROC: a.identity.connection_uid = lambda peer, ours, proc='/proc', our_inode=None: ME
print(f'\n  [identity path: {"real /proc lookup" if HAS_PROC else "simulated (no /proc on this machine)"}; Mentor from {os.path.relpath(SRC, R)}]', file=sys.stderr)

# Until a Mentor that declares "roles" is in this build (pull request #44), there is nothing to test end to end: skipped, and said.
READY = 'roles' in json.load(open(os.path.join(SRC, 'plugin.json'), encoding='utf-8'))

@unittest.skipUnless(READY, 'the Mentor in this build declares no "roles" yet (#44): nothing to test end to end')
class MentorGate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        a.load_server_plugins()
        assert 'mentor' in a.SERVER_PLUGINS, 'Mentor did not load'
        cls.srv = a.ThreadingHTTPServer(('127.0.0.1', int(os.environ.get('GATE_PORT') or 0)), a.H)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown(); cls.srv.server_close(); shutil.rmtree(TMP, ignore_errors=True)

    def req(self, verb, path, login, body=None):
        c = http.client.HTTPConnection('127.0.0.1', self.srv.server_address[1], timeout=30)
        h = {'Host': '127.0.0.1', 'Tailscale-User-Login': login, 'X-Forwarded-For': '192.0.2.20'}
        if verb == 'POST': h['Content-Type'] = 'application/json'
        c.request(verb, '/argus/' + path, body=json.dumps(body or {}) if verb == 'POST' else None, headers=h)
        r = c.getresponse(); b = r.read(); c.close()
        try: return r.status, json.loads(b)
        except ValueError: return r.status, b

    def test_learner_reaches_her_study_and_nothing_else(self):
        L = 'learner@example.com'
        declared = json.load(open(os.path.join(SRC, 'plugin.json'), encoding='utf-8'))['roles']
        for path in declared['get']:
            code, d = self.req('GET', f'api/mentor/{path}', L)
            self.assertNotEqual(code, 403, f'GET {path}: {d}')
        for path in declared['post']:
            code, d = self.req('POST', f'api/mentor/{path}', L, {})
            self.assertNotEqual(code, 403, f'POST {path}: {d}')
        code, d = self.req('GET', 'api/mentor/learners', L)
        self.assertEqual((code, d['me'], d['role'], [p['id'] for p in d['people']]), (200, 'learner-two', 'learner', ['learner-two']))
        code, d = self.req('GET', 'api/mentor/today', L)
        self.assertEqual((code, d['learner']['id']), (200, 'learner-two'), 'Mentor got who and opened her own book')
        code, d = self.req('GET', 'api/mentor/today?learner=owner-one', L)
        self.assertEqual(d['learner']['id'], 'learner-two', "learner=... from a learner is ignored: never the owner's book")
        self.assertEqual(self.req('GET', 'plugins/mentor/page.js', L)[0], 200)
        for verb, path in (('GET', 'api/mentor/not-declared'), ('POST', 'api/mentor/not-declared'), ('GET', 'api/log/argus-ui'),
                           ('POST', 'api/bolt'), ('POST', 'api/freeze'), ('GET', 'api/nothing')):
            code, d = self.req(verb, path, L, {'job': 'argus-ui'})
            self.assertEqual(code, 403, f'{verb} {path}'); self.assertTrue(d['error'])
        code, d = self.req('GET', 'api/state', L)
        self.assertEqual(([p['id'] for p in d['plugins']], [p['key'] for p in d['personas']]), (['mentor'], ['mentor']))

    def test_owner_sees_everyone(self):
        code, d = self.req('GET', 'api/mentor/learners', 'owner@example.com')
        self.assertEqual((code, d['me'], sorted(p['id'] for p in d['people'])), (200, 'owner-one', ['learner-two', 'owner-one']))
        self.assertEqual(self.req('GET', 'api/mentor/today?learner=learner-two', 'owner@example.com')[1]['learner']['id'], 'learner-two')

    def test_zz_people_file_gone_learner_refused(self):
        """Runs last (it moves the people file away and back). R4b F1 through the real server and identity path."""
        L = 'learner@example.com'
        self.assertEqual(self.req('GET', 'api/mentor/today', L)[1]['learner']['id'], 'learner-two')
        self.req('GET', 'api/mentor/today', 'owner@example.com')        # mentor.db is bound to the owner
        import contextlib, sqlite3
        db = os.path.join(SHARE, 'mentor.db')
        def count():
            with contextlib.closing(sqlite3.connect(db)) as c: return c.execute("SELECT COUNT(*) FROM attempts").fetchone()[0]
        before = count()
        aside = PEOPLE + '.set-aside'; os.replace(PEOPLE, aside)
        try:
            code, d = self.req('GET', 'api/mentor/next', L)
            self.assertEqual(code, 503, f'the file is gone: she is refused, never made the owner ({d})')
            self.assertNotIn(HOME, json.dumps(d), 'no path of the server in what she reads')
            code, d = self.req('POST', 'api/mentor/answer', L, {'card': 'ai-coding:x', 'text': 'an answer'})
            self.assertIn(code, (403, 503), f'her answer is not taken ({code} {d})')
            self.assertEqual(count(), before, "nothing was written into the owner's database")
        finally: os.replace(aside, PEOPLE)

    def test_stranger_gets_nothing(self):
        for verb, path in (('GET', 'api/mentor/today'), ('POST', 'api/mentor/answer'), ('GET', 'api/mentor/status')):
            self.assertEqual(self.req(verb, path, 'stranger@example.com')[0], 403, path)

if __name__ == '__main__':
    unittest.main()
