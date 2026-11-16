"""The owner's own Today (server/today.py, docs/home.md "Edit Today", 4.50.0): the settings file and POST api/today. No browser.

    python tests/today_edit_test.py -v        (tests/run.sh runs it under "== edit today")

  * the file: missing (the default, nothing said), good (read, tidied), broken in each way (not JSON, not an object, a field
    this version does not know, a name too long, too many entries, a bad id, larger than 64 KB): the default layout and one
    plain line for the owner; read again when it changes
  * saving: checked strictly (each refusal says why, nothing written), written whole (no .tmp left), a broken file moved aside
    first (today.set-aside-<YYYYMMDD-HHMM>.json, the same bytes), Reset writes {} and keeps the file
  * quiet: Mentor is always quiet whatever the file says; a section switched off is quiet for the status, Today's count
    and the phone (quiet.hushed); a broken file leaves only Mentor quiet
  * the route on a real server: the owner saves and resets; a learner gets 403 and no `today` in her state; not JSON 415,
    from another site 403, over 16 KB 413, a bad layout 400 with its reason
The page side is tests/today-edit.test.js. Who is asking comes from the real check on Linux; without /proc (Windows, macOS)
the lookup is stood in for, as in tests/gate_test.py."""
import glob, http.client, importlib.util, json, os, shutil, sys, tempfile, textwrap, threading, unittest
from unittest import mock

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HAS_PROC = os.path.isfile('/proc/net/tcp')
ME = os.getuid() if hasattr(os, 'getuid') else 4242
TMP = tempfile.mkdtemp(prefix='argus-today-edit-test-')
HOME = os.path.join(TMP, 'home'); CONF = os.path.join(HOME, '.config', 'argus-ui')
STATIC, FX, STATE, PLUG = os.path.join(TMP, 'static'), os.path.join(TMP, 'fx'), os.path.join(TMP, 'state'), os.path.join(CONF, 'plugins')
PEOPLE, TODAY = os.path.join(CONF, 'people.json'), os.path.join(CONF, 'today.json')
for d in (STATIC, FX, STATE, CONF, os.path.join(TMP, 'alerts'), os.path.join(TMP, 'agents')): os.makedirs(d, exist_ok=True)

def put(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f: f.write(data if isinstance(data, str) else json.dumps(data))

def bump(path, n=[0]):
    # a new modification time on every write, even on a coarse clock: the server reads the file again when it changes
    n[0] += 1; st = os.stat(path); os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + n[0] * 1_000_000_000))

def write(path, data): put(path, data); bump(path)

def read(path):
    with open(path, encoding='utf-8') as f: return f.read()

def set_aside(path):
    # tests keep their own files in TMP; one that must be gone is moved aside, never deleted
    if os.path.exists(path): shutil.move(path, os.path.join(TMP, f'gone-{os.urandom(4).hex()}-{os.path.basename(path)}'))

def asides(): return sorted(glob.glob(os.path.join(CONF, 'today.set-aside-*.json')))

put(os.path.join(STATIC, 'theme.json'), {'title': 'LeafyGrove', 'agents': [{'key': 'argus', 'name': 'Argus'}, {'key': 'zeus', 'name': 'Zeus'}]})
put(os.path.join(STATIC, 'index.html'), '<!doctype html><title>the page</title><script>const STATE = /*STATE*/null;</script>')
put(os.path.join(STATIC, 'VERSION'), '9.9.9')
shutil.copy(os.path.join(R, 'tests', 'fixtures', 'fake_systemctl.py'), FX)
put(os.path.join(FX, 'units.json'), {'argus-ui': {'ActiveState': 'active', 'Result': 'success'}})
put(os.path.join(FX, 'fake_journal.py'), 'print("")\n')
def wrapper(name, script):
    if os.name == 'nt':
        put(os.path.join(FX, name + '.cmd'), f'@"{sys.executable}" "{os.path.join(FX, script)}" %*\n'); return os.path.join(FX, name + '.cmd')
    put(os.path.join(FX, name), f'#!/bin/sh\nexec "{sys.executable}" "{os.path.join(FX, script)}" "$@"\n'); os.chmod(os.path.join(FX, name), 0o755)
    return os.path.join(FX, name)

# two server plugins whose status says they need him: mentor (always quiet) and throne (quiet once switched off)
NEEDY = textwrap.dedent('''
    def get(path, query, ctx, who=None):
        if path == 'status': return 200, {'line': '3 waiting', 'needs': True, 'action': 'Look now', 'count': 3}
        return 404, {'error': 'Not here.'}
''')
for pid in ('mentor', 'throne'):
    put(os.path.join(PLUG, pid, 'plugin.json'), {'id': pid, 'kind': 'server', 'page': 'page.js', 'name': pid.title(), 'roles': {'get': {'status': 'learner'}}})
    put(os.path.join(PLUG, pid, 'plugin.py'), NEEDY); put(os.path.join(PLUG, pid, 'page.js'), f'// {pid}')

os.environ.update(HOME=HOME, USERPROFILE=HOME, ARGUS_STATIC=STATIC, ARGUS_PLUGINS=PLUG,
                  ARGUS_BUNDLED=os.path.join(TMP, 'bundled'), ARGUS_LINKS=os.path.join(CONF, 'links.json'),
                  ARGUS_REGISTRY=os.path.join(TMP, 'agents'), ARGUS_ALERTS=os.path.join(TMP, 'alerts'),
                  ARGUS_PEOPLE_LAST_GOOD=os.path.join(STATE, 'people.last-good.json'), ARGUS_KNOWN=os.path.join(STATE, 'known.json'),
                  ARGUS_SERVE_UID=str(ME), ARGUS_DEV='1', ARGUS_WATCH='0', LEAFY_REALM=os.path.join(TMP, 'realm.json'),
                  ARGUS_SYSTEMCTL=wrapper('systemctl', 'fake_systemctl.py'), ARGUS_JOURNALCTL=wrapper('journalctl', 'fake_journal.py'))
for k in ('ARGUS_BIND', 'ARGUS_WEATHER', 'ARGUS_PEOPLE', 'ARGUS_TODAY', 'ARGUS_MODES'): os.environ.pop(k, None)
_spec = importlib.util.spec_from_file_location('argus_ui_today_edit_test', os.path.join(R, 'server', 'argus_ui.py'))
a = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(a)
T = a.today                                         # the very module the server uses
if not HAS_PROC:                                    # no /proc: stand in for the lookup (as tests/gate_test.py does)
    a.identity.connection_uid = lambda peer, ours, proc='/proc', our_inode=None: ME
print(f'\n  [identity path: {"real /proc lookup" if HAS_PROC else "simulated (no /proc on this machine)"}]', file=sys.stderr)

OWNER, LEARNER = 'owner@example.com', 'learner@example.com'
put(PEOPLE, {'people': [{'id': 'owner-one', 'name': 'Owner One', 'role': 'owner', 'logins': [OWNER]},
                        {'id': 'learner-two', 'name': 'Learner Two', 'role': 'learner', 'logins': [LEARNER]}]})

GOOD = {'tiles': {'order': ['olympus', 'argus', 'argus'], 'hidden': ['controllers'], 'names': {'olympus': '  Play\tground '}},
        'open': {'order': ['link:/studio/', 'media:jellyfin'], 'hidden': ['link:https://example.com/'],
                 'names': {'link:/studio/': 'Music'}, 'groups': {'link:/studio/': 'Make', 'media:jellyfin': ''}},
        'quiet': ['throne']}
TIDY = {'tiles': {'order': ['olympus', 'argus'], 'hidden': ['controllers'], 'names': {'olympus': 'Play ground'}},
        'open': GOOD['open'], 'quiet': ['throne']}


class File(unittest.TestCase):
    def setUp(self): set_aside(TODAY); [set_aside(p) for p in asides()]

    def test_missing_is_the_default_and_silent(self):
        self.assertEqual(T.load(), ({}, None))
        self.assertEqual(a.quiet.quiet_sections(), {'mentor'})

    def test_good_file_is_read_and_tidied(self):
        write(TODAY, dict(v=1, **GOOD))
        self.assertEqual(T.load(), (TIDY, None))
        self.assertEqual(a.quiet.quiet_sections(), {'mentor', 'throne'})
        write(TODAY, {'quiet': []})                 # changed on disk: read again
        self.assertEqual(T.load(), ({}, None))

    def test_broken_files_fall_back_and_say_so(self):
        cases = {'not JSON': '{"tiles": ', 'not an object': '[1, 2]', 'unknown field': {'colour': 'red'},
                 'unknown inner field': {'tiles': {'size': 2}}, 'name too long': {'tiles': {'names': {'olympus': 'x' * 41}}},
                 'too many': {'quiet': [f's{i}' for i in range(65)]}, 'bad id': {'tiles': {'order': ['Not An Id']}},
                 'bad key': {'open': {'hidden': ['file:/etc/passwd']}}, 'other version': {'v': 2},
                 'too big': ' ' * (T.FILE_MAX + 1) + '{}', 'Today renamed': {'tiles': {'names': {'home': 'Mine'}}},
                 'quiet broken': {'quiet': 'throne'}, 'not text': {'tiles': {'names': {'olympus': 7}}},
                 'nested too deeply': '[' * 60000}
        for what, data in cases.items():
            with self.subTest(what):
                write(TODAY, data)
                lay, why = T.load()
                self.assertEqual(lay, {}, what)
                self.assertTrue(why and why.startswith('Your Today settings (today.json) could not be used (') and 'default layout' in why, why)
                self.assertNotIn(HOME, why, 'no home path in the line')
                self.assertEqual(a.quiet.quiet_sections(), {'mentor'}, 'a broken file: only Mentor is quiet')

    def test_too_deep_for_the_parser_says_so(self):
        # How deep json.load can go depends on the Python build (Windows gives up sooner than Linux), so the
        # RecursionError is made here rather than hoped for from a file
        write(TODAY, '[[[]]]')
        with mock.patch.object(T.json, 'load', side_effect=RecursionError):
            lay, why = T.load()
        self.assertEqual(lay, {})
        self.assertIn('could not be used (it is nested too deeply)', why or '')

    def test_save_is_checked_whole_and_atomic(self):
        self.assertEqual(T.save(GOOD), TIDY)
        self.assertEqual(json.loads(read(TODAY)), dict(v=1, **TIDY))
        self.assertFalse(os.path.exists(TODAY + '.tmp'), 'no half-written file left')
        for bad, why in (({'tiles': {'names': {'olympus': ''}}}, 'is empty'), ({'nope': 1}, 'does not know'),
                         ({'open': {'order': ['javascript:alert(1)']}}, 'not a section or link'),
                         ({'tiles': {'names': {'olympus': 'y' * 41}}}, 'longer than 40'), ([], 'must be an object')):
            with self.assertRaises(ValueError) as e: T.save(bad)
            self.assertIn(why, str(e.exception))
        self.assertEqual(json.loads(read(TODAY)), dict(v=1, **TIDY), 'a refused save leaves the file as it was')

    def test_save_over_a_broken_file_sets_it_aside(self):
        write(TODAY, '{"hand": "edited", ')
        self.assertTrue(T.load()[1])
        T.save({'quiet': ['throne']})
        kept = asides()
        self.assertEqual(len(kept), 1, 'the broken file is moved aside, not overwritten')
        self.assertRegex(os.path.basename(kept[0]), r'^today\.set-aside-\d{8}-\d{4}\.json$')
        self.assertEqual(read(kept[0]), '{"hand": "edited", ', 'the same bytes')
        self.assertEqual(T.load(), ({'quiet': ['throne']}, None))
        T.save({})                                  # a good file is simply replaced: no second set-aside
        self.assertEqual(len(asides()), 1)

    def test_reset_keeps_a_file_with_the_default(self):
        T.save(GOOD); T.save({})
        self.assertEqual(json.loads(read(TODAY)), {'v': 1})
        self.assertEqual(T.load(), ({}, None))

    def test_mentor_is_quiet_whatever_the_file_says(self):
        T.save({'quiet': ['throne']})
        self.assertIn('mentor', a.quiet.quiet_sections())
        self.assertTrue(a.quiet.hushed({'section': 'throne', 'subject': 'x'}, [], {}), 'switched off: no buzz')
        self.assertTrue(a.quiet.hushed({'section': 'mentor', 'subject': 'x'}, [], {}))
        self.assertFalse(a.quiet.hushed({'section': 'argus', 'subject': 'x'}, [], {}), 'the others still buzz')


class Route(unittest.TestCase):
    """POST api/today and the state, on a real server."""
    @classmethod
    def setUpClass(cls):
        a.load_server_plugins()
        cls.srv = a.ThreadingHTTPServer(('127.0.0.1', 0), a.H)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
    @classmethod
    def tearDownClass(cls): cls.srv.shutdown(); cls.srv.server_close()
    def setUp(self): set_aside(TODAY); [set_aside(p) for p in asides()]

    def req(self, verb, path, login=OWNER, body=None, raw=None, **headers):
        c = http.client.HTTPConnection('127.0.0.1', self.srv.server_address[1], timeout=30)
        h = {'Host': '127.0.0.1', 'X-Forwarded-For': '192.0.2.20', 'Tailscale-User-Login': login, **headers}
        data = None
        if verb == 'POST': h.setdefault('Content-Type', 'application/json'); data = raw if raw is not None else json.dumps(body)
        c.request(verb, '/argus/' + path, body=data, headers=h)
        r = c.getresponse(); b = r.read(); c.close()
        return r.status, json.loads(b)
    def save(self, body, login=OWNER, **k): return self.req('POST', 'api/today', login, body, **k)
    def state(self, login=OWNER): return self.req('GET', 'api/state', login)[1]

    def test_owner_saves_and_resets(self):
        self.assertEqual((self.state()['today'], self.state()['today_problem']), ({}, None))
        code, d = self.save(GOOD)
        self.assertEqual((code, d), (200, {'ok': True, 'today': TIDY, 'msg': 'Today saved.'}))
        s = self.state()
        self.assertEqual(s['today'], TIDY); self.assertEqual(s['quiet'], ['mentor', 'throne'])
        code, d = self.save({'reset': True})
        self.assertEqual((code, d), (200, {'ok': True, 'today': {}, 'msg': 'Today is back to the default.'}))
        self.assertEqual(self.state()['quiet'], ['mentor'])

    def test_a_switched_off_section_never_needs_him(self):
        code, st = self.req('GET', 'api/throne/status')
        self.assertTrue(st['needs'])
        self.save({'quiet': ['throne']})
        code, st = self.req('GET', 'api/throne/status')
        self.assertEqual((st['needs'], st.get('action', ''), st.get('count')), (False, '', None), st)
        self.assertEqual(st['line'], '3 waiting', 'its tile keeps its own line')

    def test_bad_layout_is_400_with_the_reason(self):
        self.save(GOOD)
        code, d = self.save({'tiles': {'names': {'olympus': 'z' * 41}}})
        self.assertEqual((code, d['ok']), (400, False)); self.assertIn('longer than 40', d['msg'])
        self.assertEqual(self.state()['today'], TIDY, 'nothing saved')

    def test_a_broken_file_is_said_to_the_owner(self):
        write(TODAY, 'not json')
        s = self.state()
        self.assertEqual(s['today'], {}); self.assertIn('could not be used (it is not valid JSON)', s['today_problem'])

    def test_a_deeply_nested_file_still_opens_the_page(self):
        # tens of thousands of "[" (under the 64 KB cap): json.load gives up (RecursionError, or on a build that goes that deep,
        # not valid JSON at the end); either way the page and api/state must still answer, so Edit can repair it
        write(TODAY, '[' * 60000)
        code, s = self.req('GET', 'api/state')
        self.assertEqual(code, 200)
        self.assertEqual(s['today'], {})
        self.assertRegex(s['today_problem'] or '', r'could not be used \(it is (nested too deeply|not valid JSON)\)')
        self.assertEqual(self.save({'quiet': ['throne']})[0], 200, 'Edit can save over it')
        self.assertEqual(len(asides()), 1, 'the nested file is kept beside the new one')
        self.assertEqual(self.state()['today_problem'], None)

    def test_learner(self):
        code, d = self.save(GOOD, LEARNER)
        self.assertEqual(code, 403); self.assertFalse(d.get('ok', False))
        self.assertFalse(os.path.exists(TODAY), 'nothing saved for a learner')
        self.save({'quiet': ['throne'], 'tiles': {'names': {'olympus': 'Secret name'}}})
        s = self.state(LEARNER)
        self.assertNotIn('today', s); self.assertNotIn('today_problem', s); self.assertNotIn('Secret name', json.dumps(s))
        code, st = self.req('GET', 'api/throne/status', LEARNER)
        self.assertTrue(st['needs'], "a learner's page is not quiet")

    def test_protections(self):
        self.assertEqual(self.save(None, raw='quiet=throne', **{'Content-Type': 'application/x-www-form-urlencoded'})[0], 415)
        self.assertEqual(self.save(GOOD, **{'Sec-Fetch-Site': 'cross-site'})[0], 403)
        self.assertEqual(self.save(GOOD, Origin='http://evil.example')[0], 403)
        self.assertEqual(self.save(None, raw=json.dumps({'quiet': []}) + ' ' * (T.BODY_MAX + 1))[0], 413)
        self.assertEqual(self.save(None, raw=json.dumps(GOOD) + ' ' * (8 * 1024))[0], 200, 'a body over 4 KB but under 16 KB is fine')
        self.assertEqual(self.save([1])[0], 400)


if __name__ == '__main__':
    unittest.main()
