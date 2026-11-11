"""The role gate on a real server (docs/people.md): every route of server/argus_ui.py against owner, learner and a person
without a role, the cut-down state, `who` for plugins, the people file's failure cases and the protective headers.

    python3 tests/gate_test.py -v        (tests/run.sh runs it under "== people and roles")

The server runs in this process (GATE_PORT, default a free port) with a temporary HOME, fake units, fixture plugins and a
people file; nothing outside a temporary folder is touched. Who is asking comes from the real check: Tailscale Serve's
login counts only when the connection belongs to the Serve user. On Linux the test sets ARGUS_SERVE_UID to its own user id,
so its requests ARE the Serve process and the real /proc lookup runs. Without /proc (Windows, macOS) that lookup cannot
work, so the test stands in for it and says so ("simulated"); the Linux run in CI is the one that counts.
Set ROLE_TABLE=<file> to write the route-by-role table as this test found it."""
import http.client, importlib.util, json, os, re, shutil, socket, subprocess, sys, tempfile, textwrap, threading, time, unittest

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HAS_PROC = os.path.isfile('/proc/net/tcp')
ME = os.getuid() if hasattr(os, 'getuid') else 4242      # the user id the Serve process "is" in this test
TMP = tempfile.mkdtemp(prefix='argus-gate-test-')
HOME = os.path.join(TMP, 'home'); CONF = os.path.join(HOME, '.config', 'argus-ui')
STATIC, PLUG, FX = os.path.join(TMP, 'static'), os.path.join(CONF, 'plugins'), os.path.join(TMP, 'fx')
PEOPLE = os.path.join(CONF, 'people.json')
for d in (STATIC, PLUG, FX, os.path.join(TMP, 'alerts'), os.path.join(TMP, 'agents')): os.makedirs(d, exist_ok=True)

def put(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f: f.write(text if isinstance(text, str) else json.dumps(text))

# ---- the theme, the page and its files ----
put(os.path.join(STATIC, 'theme.json'), {'title': 'Elaia', 'agents': [{'key': 'argus', 'name': 'Argus', 'domain': 'Watchman'},
    {'key': 'hermes', 'name': 'Hermes', 'domain': 'Delivery'}, {'key': 'mnemosyne', 'name': 'Mnemosyne', 'domain': 'Memory'},
    {'key': 'heracles', 'name': 'Heracles', 'domain': 'Study · lessons'}], 'coming_soon': [{'name': 'Workouts', 'what': 'Soon'}]})
put(os.path.join(STATIC, 'index.html'), '<!doctype html><title>the page</title><script>const STATE = /*STATE*/null;</script>')
put(os.path.join(STATIC, 'VERSION'), '9.9.9'); put(os.path.join(STATIC, 'sw.js'), '// sw'); put(os.path.join(STATIC, 'manifest.webmanifest'), '{}')
put(os.path.join(STATIC, 'icons', 'argus.png'), 'png')
# ---- what only the owner may see: tasks, an alert, a link ----
UNITS = {'hermes-secretsort': {'Result': 'success', 'ActiveState': 'inactive', 'ExecMainExitTimestamp': 'Sun 2026-10-18 09:20:44 MDT',
                               'Description': 'Hermes sorting the private downloads'},
         'mnemosyne-backup': {'Result': 'failed', 'ActiveState': 'failed', 'ExecMainStartTimestamp': 'Sun 2026-10-18 09:20:44 MDT',
                              'Description': 'Mnemosyne weekly backup'}}
put(os.path.join(FX, 'units.json'), UNITS)
shutil.copy(os.path.join(R, 'tests', 'fixtures', 'fake_systemctl.py'), FX)
put(os.path.join(FX, 'fake_journal.py'), 'print("2026-10-18T09:20:01 host hermes-secretsort[1]: a private log line")\n')
def wrapper(name, script):
    if os.name == 'nt':
        put(os.path.join(FX, name + '.cmd'), f'@"{sys.executable}" "{os.path.join(FX, script)}" %*\n'); return os.path.join(FX, name + '.cmd')
    put(os.path.join(FX, name), f'#!/bin/sh\nexec "{sys.executable}" "{os.path.join(FX, script)}" "$@"\n'); os.chmod(os.path.join(FX, name), 0o755)
    return os.path.join(FX, name)
put(os.path.join(TMP, 'alerts', 'hermes.json'), {'job': 'hermes-secretsort', 'level': 'alert', 'message': 'Private alert about the drive'})
put(os.path.join(CONF, 'links.json'), [{'name': 'Private Studio', 'what': 'music', 'href': '/studio/'}])
# ---- plugins: one that opens paths to learners and takes who (it takes over the agent heracles), one that opens a path
# but does not take who, one with no "roles" that takes who, a static one, and a static "controllers" (so <base>/pads moves) ----
WHO_PLUGIN = textwrap.dedent('''
    def get(path, query, ctx, who=None):
        if path == 'status': return 200, {'line': 'line of ' + ctx.id}
        return 200, {'path': path, 'who': who, 'headers': ctx.headers}
    def post(path, body, ctx, who=None):
        return 200, {'path': path, 'who': who, 'headers': ctx.headers}
''')
OLD_PLUGIN = textwrap.dedent('''
    def get(path, query, ctx):
        if path == 'status': return 200, {'line': 'line of ' + ctx.id}
        return 200, {'path': path, 'headers': ctx.headers, 'three': True}
    def post(path, body, ctx):
        return 200, {'path': path, 'three': True}
''')
for pid, code, extra in (('heracles', WHO_PLUGIN, {'agent': True, 'roles': {'get': {'lessons': 'learner', 'status': 'learner'}, 'post': {'answer': 'learner'}}}),
                         ('quiet', OLD_PLUGIN, {'name': 'Quiet', 'roles': {'get': {'ping': 'learner'}, 'post': {'note': 'learner'}}}),
                         ('closed', WHO_PLUGIN, {'name': 'Closed'})):
    put(os.path.join(PLUG, pid, 'plugin.json'), dict(id=pid, kind='server', page='page.js', **extra))
    put(os.path.join(PLUG, pid, 'plugin.py'), code); put(os.path.join(PLUG, pid, 'page.js'), f'// {pid}')
put(os.path.join(PLUG, 'kwonly', 'plugin.json'), {'id': 'kwonly', 'kind': 'server', 'page': 'page.js'})
put(os.path.join(PLUG, 'kwonly', 'page.js'), '// kwonly')
put(os.path.join(PLUG, 'kwonly', 'plugin.py'), 'def get(path, query, ctx, *, who=None):\n    return 200, {"who": who}\n')
for pid in ('spartamelee', 'controllers'):
    put(os.path.join(PLUG, pid, 'plugin.json'), {'id': pid, 'name': pid.title()}); put(os.path.join(PLUG, pid, 'index.html'), '<p>game</p>')

os.environ.update(HOME=HOME, USERPROFILE=HOME, ARGUS_STATIC=STATIC, ARGUS_PLUGINS=PLUG, ARGUS_BUNDLED=os.path.join(TMP, 'bundled'),
                  ARGUS_LINKS=os.path.join(CONF, 'links.json'), ARGUS_REGISTRY=os.path.join(TMP, 'agents'), ARGUS_ALERTS=os.path.join(TMP, 'alerts'),
                  ARGUS_PEOPLE_LAST_GOOD=os.path.join(TMP, 'state', 'people.last-good.json'),   # the people file: the default, in HOME
                  ARGUS_SERVE_UID=str(ME), ARGUS_DEV='1', ARGUS_WATCH='0',          # ARGUS_DEV: our own uid may stand in for Serve
                  ARGUS_SYSTEMCTL=wrapper('systemctl', 'fake_systemctl.py'), ARGUS_JOURNALCTL=wrapper('journalctl', 'fake_journal.py'))
for k in ('ARGUS_BIND', 'ARGUS_WEATHER', 'ARGUS_PEOPLE'): os.environ.pop(k, None)
_spec = importlib.util.spec_from_file_location('argus_ui_gate_test', os.path.join(R, 'server', 'argus_ui.py'))
a = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(a)
if not HAS_PROC:                                     # no /proc: stand in for the lookup (see the top of this file)
    a.identity.connection_uid = lambda peer, ours, proc='/proc', our_inode=None: ME
print(f'\n  [identity path: {"real /proc lookup, ARGUS_SERVE_UID=" + str(ME) if HAS_PROC else "simulated (no /proc on this machine)"}]', file=sys.stderr)

OWNER, LEARNER, STRANGER = 'owner@example.com', 'learner@example.com', 'stranger@example.com'
GOOD = {'people': [{'id': 'owner-one', 'name': 'Owner One', 'role': 'owner', 'logins': [OWNER]},
                   {'id': 'learner-two', 'name': 'Learner Two', 'role': 'learner', 'logins': [LEARNER]}]}
def write_people(doc):
    put(PEOPLE, doc); st = os.stat(PEOPLE); write_people.n = getattr(write_people, 'n', 0) + 1
    os.utime(PEOPLE, ns=(st.st_atime_ns, st.st_mtime_ns + write_people.n * 1_000_000_000))   # a new time even on a coarse clock
def no_people():
    if os.path.exists(PEOPLE): shutil.move(PEOPLE, os.path.join(TMP, f'people-set-aside-{time.time_ns()}.json'))
    a.PEOPLE = a.identity.People(PEOPLE)           # as at start, with no saved copy

# ---- every route of the server, from H.get() and H.do_POST() (and what each should answer per role) ----
G, P = 'GET', 'POST'
ROUTES = [  # (verb, path, what it is, owner, learner, none)
    (G, '', 'the page (Today)', 200, 200, 'page'),
    (G, 'argus', 'the page at an agent address (Watch)', 200, 200, 'page'),
    (G, 'olympus', 'the page at a section address (Olympus)', 200, 200, 'page'),
    (G, 'closed', "the page at an owner's plugin section", 200, 200, 'page'),
    (G, 'heracles', "the page at the learner's plugin section", 200, 200, 'page'),
    (G, 'spartamelee/sub', 'the page at a nested section address', 200, 200, 'page'),
    (G, 'pads', 'a moved section address (redirect)', 302, 302, 'page'),
    (G, 'nope', 'an unknown address', 404, 404, 'page'),
    (G, 'static/theme.json', 'a static file of the page', 200, 200, 'page'),
    (G, 'sw.js', 'the service worker', 200, 200, 'page'),
    (G, 'manifest.webmanifest', 'the app manifest', 200, 200, 'page'),
    (G, 'api/health', 'version probe', 200, 200, 200),
    (G, 'api/whoami', 'who the server thinks you are', 200, 200, 200),
    (G, 'api/state', 'the state (cut down for a learner)', 200, 200, 403),
    (G, 'api/sky', 'the weather', 200, 200, 403),
    (G, 'api/log/hermes-secretsort', 'a program log', 200, 403, 403),
    (G, 'api/pads/list', "a moved section's old api", 200, 403, 403),
    (G, 'api/nothing', 'an unknown api', 404, 403, 403),
    (G, 'plugins/heracles/page.js', 'files of a plugin that opens a path to learners', 200, 200, 'page'),
    (G, 'plugins/quiet/page.js', 'files of another such plugin', 200, 200, 'page'),
    (G, 'plugins/closed/page.js', 'files of a server plugin without "roles"', 200, 403, 'page'),
    (G, 'plugins/spartamelee/index.html', 'files of a static plugin', 200, 403, 'page'),
    (G, 'api/heracles/lessons', 'a plugin GET opened to learners (takes who)', 200, 200, 403),
    (G, 'api/heracles/secret', 'a plugin GET not opened (same plugin)', 200, 403, 403),
    (G, 'api/heracles/status', "Home's line, opened to learners", 200, 200, 403),
    (G, 'api/quiet/ping', 'a plugin GET opened to learners (no who)', 200, 200, 403),
    (G, 'api/closed/data', 'a plugin GET, no "roles"', 200, 403, 403),
    (G, 'api/closed/status', "Home's line, no \"roles\"", 200, 403, 403),
    (P, 'api/freeze', 'freeze a task', 200, 403, 403),
    (P, 'api/thaw', 'thaw a task', 200, 403, 403),
    (P, 'api/bolt', 'restart / run a task', 200, 403, 403),
    (P, 'api/run', 'run a task', 200, 403, 403),
    (P, 'api/heracles/answer', 'a plugin POST opened to learners', 200, 200, 403),
    (P, 'api/heracles/wipe', 'a plugin POST not opened', 200, 403, 403),
    (P, 'api/quiet/note', 'a plugin POST opened to learners (no who)', 200, 200, 403),
    (P, 'api/closed/act', 'a plugin POST, no "roles"', 200, 403, 403),
    (P, 'api/nothing', 'an unknown POST', 404, 403, 403),
]

class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        a.load_server_plugins()
        cls.srv = a.ThreadingHTTPServer(('127.0.0.1', int(os.environ.get('GATE_PORT') or 0)), a.H)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown(); cls.srv.server_close()

    def req(self, verb, path, login=None, body=None, **headers):
        # as Serve passes a request on: the sender's address in X-Forwarded-For (a documentation address: not this machine)
        c = http.client.HTTPConnection('127.0.0.1', self.srv.server_address[1], timeout=20)
        h = {'Host': '127.0.0.1', 'X-Forwarded-For': '192.0.2.20', **headers}
        if login: h['Tailscale-User-Login'] = login
        data = None
        if verb == P: h.setdefault('Content-Type', 'application/json'); data = json.dumps(body if body is not None else {'job': 'hermes-secretsort'})
        c.request(verb, '/argus/' + path, body=data, headers=h)
        r = c.getresponse(); b = r.read(); c.close()
        return r.status, {k.lower(): v for k, v in r.getheaders()}, b
    def js(self, *a, **k):
        code, h, b = self.req(*a, **k); return code, json.loads(b)

class NoPeopleFile(Base):
    """No people file: everything as before, whoever asks (with a login, without, faked)."""
    def setUp(self): no_people()
    def test_whoami_says_owner(self):
        for login in (OWNER, None, 'anyone@example.com'):
            code, d = self.js(G, 'api/whoami', login)
            self.assertEqual((code, d['person'], d['name'], d['role'], d['problem']), (200, 'owner', 'You', 'owner', None), login)
            self.assertEqual((d['login'], d['trusted']), (login, bool(login)), login)
    def test_every_route_as_before(self):
        for verb, path, what, owner, *_ in ROUTES:
            self.assertEqual(self.req(verb, path)[0], owner, f'{verb} {path} ({what})')
        code, d = self.js(G, 'api/state')
        self.assertEqual((d['role'], d['person'], d['name'], d['people_problem']), ('owner', 'owner', 'You', None))
        self.assertIn('hermes-secretsort', json.dumps(d))
        code, d = self.js(G, 'api/heracles/lessons')
        self.assertEqual(d['who'], {'person': 'owner', 'name': 'You', 'role': 'owner'}, 'who is never None, also without a file')

class Roles(Base):
    def setUp(self): write_people(GOOD)

    def expect(self, role, want, code, h, body, verb, path):
        if want == 'page':                     # the small private page, for a person without a role at a page address
            self.assertEqual(code, 403, f'{role} {verb} {path}')
            self.assertTrue(body.startswith(b'<!doctype html>') and b'This page is private' in body, f'{role} {verb} {path}')
            self.assertNotIn(b'<script', body); self.assertIn("default-src 'none'", h.get('content-security-policy', ''))
            return 'private page'
        self.assertEqual(code, want, f'{role} {verb} {path}')
        if code == 403:
            self.assertEqual(h['content-type'], 'application/json', f'{role} {verb} {path}')
            d = json.loads(body); self.assertTrue(d['error'] and d['error'].endswith('.') and d['msg'] == d['error'])
        return str(code)

    def test_every_route_for_every_role(self):
        table = ['| Route | What | owner | learner | none (trusted login not listed) | none (no identity) |', '|---|---|---|---|---|---|']
        for verb, path, what, owner, learner, none in ROUTES:
            got = []
            for role, login, want in (('owner', OWNER, owner), ('learner', LEARNER, learner), ('none', STRANGER, none), ('none-direct', None, none)):
                code, h, body = self.req(verb, path, login)
                got.append(self.expect(role, want, code, h, body, verb, path))
            if verb == P and path in ('api/freeze',): self.req(P, 'api/thaw', OWNER)        # put the task back
            table.append(f'| `{verb} {path or "/"}` | {what} | ' + ' | '.join(got) + ' |')
        if os.environ.get('ROLE_TABLE'):
            with open(os.environ['ROLE_TABLE'], 'w', encoding='utf-8') as f: f.write('\n'.join(table) + '\n')

    def test_learner_state_names_none_of_the_owners_things(self):
        code, h, body = self.req(G, 'api/state', LEARNER); d = json.loads(body)
        self.assertEqual((d['role'], d['person'], d['name']), ('learner', 'learner-two', 'Learner Two'))
        for secret in (b'hermes', b'secretsort', b'mnemosyne', b'Private alert', b'Private Studio', b'/studio/', b'Workouts',
                       b'closed', b'spartamelee', b'controllers', b'people_problem', b'Owner One'):
            self.assertNotIn(secret, body, secret)
        self.assertEqual((d['jobs'], d['alerts'], d['links'], d['watch'], d['soon']), ([], [], [], [], []))
        self.assertEqual(sorted(p['id'] for p in d['plugins']), ['heracles', 'quiet'])
        self.assertEqual([p['key'] for p in d['personas']], ['heracles'], 'only the agents whose section she may open')
        code, h, page = self.req(G, '', LEARNER)
        self.assertIn(b'"role": "learner"', page); self.assertNotIn(b'secretsort', page, 'the state inside the page is cut too')
        code, d = self.js(G, 'api/state', OWNER)
        self.assertEqual((d['role'], d['person'], d['name'], d['people_problem']), ('owner', 'owner-one', 'Owner One', None))
        self.assertIn('hermes-secretsort', json.dumps(d)); self.assertTrue(d['links'] and d['alerts'])

    def test_who_for_plugins(self):
        self.assertEqual(self.js(G, 'api/heracles/lessons', LEARNER)[1]['who'], {'person': 'learner-two', 'name': 'Learner Two', 'role': 'learner'})
        self.assertEqual(self.js(G, 'api/heracles/secret', OWNER)[1]['who'], {'person': 'owner-one', 'name': 'Owner One', 'role': 'owner'})
        self.assertEqual(self.js(P, 'api/heracles/answer', LEARNER, {'x': 1})[1]['who']['role'], 'learner')
        self.assertEqual(self.js(G, 'api/quiet/ping', LEARNER)[1], {'path': 'ping', 'headers': {'Tailscale-User-Login': LEARNER, 'X-Forwarded-For': '192.0.2.20'}, 'three': True},
                         'a plugin with three parameters is called as before')
        self.assertEqual(self.js(G, 'api/heracles/lessons', LEARNER)[1]['headers'], {'Tailscale-User-Login': LEARNER, 'X-Forwarded-For': '192.0.2.20'},
                         'a trusted login is passed on')
        self.assertEqual(self.js(G, 'api/kwonly/x', OWNER)[1]['who'], {'person': 'owner-one', 'name': 'Owner One', 'role': 'owner'},
                         'a keyword-only who is found too')

    def test_home_status_lines(self):
        self.assertEqual(self.js(G, 'api/heracles/status', LEARNER), (200, {'line': 'line of heracles', 'needs': False, 'action': ''}))
        self.assertEqual(self.req(G, 'api/closed/status', LEARNER)[0], 403)
        self.assertEqual(self.js(G, 'api/closed/status', OWNER)[1]['line'], 'line of closed')

    def test_none_page_names_the_login_escaped(self):
        code, h, body = self.req(G, 'heracles', '<b>evil</b>@example.com')
        self.assertEqual(code, 403); self.assertIn(b'&lt;b&gt;evil&lt;/b&gt;@example.com', body); self.assertNotIn(b'<b>evil', body)
        self.assertIn(b'not on this page', body)
        code, h, body = self.req(G, 'heracles/sub/page')
        self.assertIn(b'did not come through Tailscale', body); self.assertIn(b'href="../../api/whoami"', body)
        code, d = self.js(G, 'api/whoami', STRANGER)
        self.assertEqual((code, d['role'], d['login'], d['trusted'], d['problem']), (200, 'none', STRANGER, True, None))

    def test_refusals_say_what_happened(self):
        self.assertIn('Only the owner', self.js(P, 'api/bolt', LEARNER)[1]['error'])
        self.assertIn(STRANGER, self.js(G, 'api/state', STRANGER)[1]['error'])
        self.assertIn('did not come through Tailscale', self.js(G, 'api/state')[1]['error'])

    def test_a_request_from_the_server_itself_is_nobody(self):
        # a program on the server that goes in through Serve's front door: Serve stamps it with the machine's own login
        for own in ('127.0.0.1', '::1', '::ffff:127.0.0.1', '127.0.0.1, 192.0.2.20', '192.0.2.20, 127.0.0.1'):
            code, d = self.js(G, 'api/whoami', OWNER, **{'X-Forwarded-For': own})
            self.assertEqual((d['trusted'], d['through_serve'], d['from_this_server'], d['role']), (False, True, True, 'none'), own)
            self.assertEqual(d['note'], 'This request came from the server itself, so it has no person.')
        for other in ('192.0.2.20', '2001:db8::7, 192.0.2.21', 'garbage'):
            d = self.js(G, 'api/whoami', OWNER, **{'X-Forwarded-For': other})[1]
            self.assertEqual((d['trusted'], d['role'], d['note']), (True, 'owner', None), other + ': another device, or unreadable: unchanged')
        self.assertEqual(self.req(P, 'api/bolt', OWNER, **{'X-Forwarded-For': '127.0.0.1'})[0], 403)
        code, h, body = self.req(G, '', OWNER, **{'X-Forwarded-For': '127.0.0.1'})
        self.assertEqual(code, 403); self.assertIn(b'came from the server itself', body)
        no_people()
        code, d = self.js(G, 'api/closed/data', OWNER, **{'X-Forwarded-For': '127.0.0.1'})
        self.assertEqual((code, d['headers']), (200, {}), 'no people file: still the owner, but no login is passed to a plugin')
        self.assertEqual(self.js(G, 'api/whoami', OWNER, **{'X-Forwarded-For': '192.0.2.20'})[1]['from_this_server'], False)

    def test_upper_and_lower_case_logins(self):
        self.assertEqual(self.js(G, 'api/whoami', 'Learner@EXAMPLE.com')[1]['role'], 'learner')

    def test_changed_on_disk_is_used_without_a_restart(self):
        self.assertEqual(self.js(G, 'api/whoami', 'new@example.com')[1]['role'], 'none')
        doc = json.loads(json.dumps(GOOD)); doc['people'][1]['logins'].append('new@example.com'); write_people(doc)
        self.assertEqual(self.js(G, 'api/whoami', 'new@example.com')[1]['role'], 'learner')

    def test_two_owners(self):
        doc = json.loads(json.dumps(GOOD)); doc['people'].append({'name': 'Owner Three', 'role': 'owner', 'logins': ['three@example.com']}); write_people(doc)
        self.assertEqual(self.js(G, 'api/whoami', 'three@example.com')[1]['role'], 'owner')
        self.assertEqual(self.req(P, 'api/thaw', 'three@example.com')[0], 200)

class BrokenPeopleFile(Base):
    def test_restart_with_a_broken_file_keeps_the_saved_copy(self):
        no_people(); a.PEOPLE = a.identity.People(PEOPLE, last_good=os.environ['ARGUS_PEOPLE_LAST_GOOD'])
        write_people(GOOD); self.assertEqual(self.js(G, 'api/whoami', LEARNER)[1]['role'], 'learner')
        write_people('{"people": [ oops')
        a.PEOPLE = a.identity.People(PEOPLE, last_good=os.environ['ARGUS_PEOPLE_LAST_GOOD'])     # a restart
        code, d = self.js(G, 'api/whoami', STRANGER)
        self.assertEqual(d['role'], 'none', 'after a restart a stranger still is nobody')
        self.assertEqual(self.req(G, 'api/log/hermes-secretsort', LEARNER)[0], 403, 'and a learner still gets no logs')
        self.assertIn('last good copy', self.js(G, 'api/whoami', OWNER)[1]['problem'])

    def test_broken_at_first_start_is_closed(self):
        # no good copy known (the hub's decision): nobody is a person; health and whoami stay open; the private page and
        # every refusal carry one plain way back for the owner, never the detail (that goes to the log)
        deep = '{"people": ' + '[' * 100000 + ']' * 100000 + '}'
        for doc in ('{"people": [', {'people': [{'name': 'Learner Two', 'role': 'learner', 'logins': [LEARNER]}]},
                    {'people': [GOOD['people'][0], {'name': 'Learner Two', 'role': 'learner', 'logins': [OWNER.upper()]}]}, deep):
            write_people(doc); a.PEOPLE = a.identity.People(PEOPLE)     # as if the server had just started, no saved copy
            for login in (OWNER, LEARNER, STRANGER, None):
                code, d = self.js(G, 'api/whoami', login)
                self.assertEqual((code, d['role'], d['person']), (200, 'none', None), f'{login}: closed')
                self.assertEqual(d['problem'], a.identity.CLOSED, 'whoami says what happened in general words')
                self.assertEqual(self.req(G, 'api/health', login)[0], 200)
                self.assertEqual(self.req(G, 'api/state', login)[0], 403)
                code, d2 = self.js(P, 'api/bolt', login, {'job': 'hermes-secretsort'})
                self.assertEqual((code, d2['error']), (403, a.identity.CLOSED))
                code, h, body = self.req(G, '', login)
                self.assertEqual(code, 403); self.assertIn(b'move the people file aside to a dated name', body)
            for secret in (OWNER, 'entry', 'line 1', HOME):
                self.assertNotIn(secret, a.identity.CLOSED)
        os.makedirs(os.path.join(CONF, 'aside'), exist_ok=True)
        shutil.move(PEOPLE, os.path.join(CONF, 'aside', 'people.json.set-aside-20261111-0430'))
        self.assertEqual(self.js(G, 'api/whoami', STRANGER)[1]['role'], 'owner', 'the file moved aside: no-file behaviour at once, no restart')

    def test_broken_after_a_good_read(self):
        no_people(); write_people(GOOD)
        self.assertEqual(self.js(G, 'api/whoami', LEARNER)[1]['role'], 'learner')
        write_people('{"people": [ oops')
        code, d = self.js(G, 'api/whoami', LEARNER)
        self.assertEqual((d['role'], d['problem']), ('learner', None), 'the last good copy is used; only the owner is told')
        code, d = self.js(G, 'api/whoami', OWNER); self.assertIn('last good copy', d['problem'])
        self.assertEqual(self.js(G, 'api/state', OWNER)[1]['people_problem'], d['problem'])
        self.assertNotIn('people_problem', self.js(G, 'api/state', LEARNER)[1])
        self.assertEqual(self.req(P, 'api/thaw', OWNER)[0], 200, 'the owner can still act')
        self.assertEqual(self.req(P, 'api/thaw', LEARNER)[0], 403)
        self.assertEqual(self.req(G, 'api/state', STRANGER)[0], 403)
    def tearDown(self): no_people()

class RoutesAreAllListed(unittest.TestCase):
    def test_every_route_in_the_router_is_in_ROUTES(self):
        src = open(os.path.join(R, 'server', 'argus_ui.py'), encoding='utf-8').read()
        body = src[src.index('    def get(self):'):src.index("if __name__ == '__main__':")]
        found = set(re.findall(r"p == '([^']+)'", body)) | set(re.findall(r"p\.startswith\('([^']+)'\)", body))
        found |= {x for t in re.findall(r"p in \(([^)]*)\)", body) for x in re.findall(r"'([^']+)'", t)}
        found |= set(re.findall(r"'(api/[a-z]+)': ", body))           # the powers' table in do_POST
        listed = {path for _, path, *_ in ROUTES}
        missing = sorted(r for r in found if not any(x == r or x.startswith(r) for x in listed))
        self.assertEqual(missing, [], 'a route in H.get() / H.do_POST() that ROUTES does not try')
        self.assertGreater(len(found), 10, found)

class Headers(Base):
    def setUp(self): no_people()
    PROTECT = {'x-frame-options': 'SAMEORIGIN', 'content-security-policy': "frame-ancestors 'self'",
               'x-content-type-options': 'nosniff', 'referrer-policy': 'same-origin'}
    def test_protective_headers_on_every_answer_but_plugin_files(self):
        for verb, path in ((G, ''), (G, 'api/state'), (G, 'api/health'), (G, 'static/theme.json'), (G, 'nope'), (G, 'api/heracles/lessons'),
                           (G, 'pads'), (P, 'api/thaw'), (P, 'api/nothing')):
            h = self.req(verb, path)[1]
            for k, v in self.PROTECT.items(): self.assertEqual(h.get(k), v, f'{verb} {path} {k}')
        h = self.req(G, 'plugins/spartamelee/index.html')[1]
        self.assertIsNone(h.get('x-frame-options')); self.assertIn('sandbox', h['content-security-policy'])
    def test_wildcard_cors_only_on_static_plugin_files(self):
        self.assertEqual(self.req(G, 'plugins/spartamelee/index.html')[1].get('access-control-allow-origin'), '*')
        for path in ('plugins/heracles/page.js', 'plugins/closed/page.js', 'plugins/closed/nothing.js'):
            h = self.req(G, path)[1]
            self.assertNotIn('access-control-allow-origin', h, path); self.assertEqual(h['x-content-type-options'], 'nosniff')
        code, h, _ = self.req(G, 'plugins/heracles/page.js'); etag = h['etag']
        code, h, _ = self.req(G, 'plugins/heracles/page.js', **{'If-None-Match': etag})
        self.assertEqual(code, 304); self.assertNotIn('access-control-allow-origin', h)

    def test_bind_default(self):
        self.assertEqual(a.BIND, '127.0.0.1', 'without ARGUS_BIND the server listens on this machine only')

class FakedHeaderOnADirectConnection(unittest.TestCase):
    """The server in its own process, started with ARGUS_SERVE_UID set to a user id that is NOT this test's: the test's own
    connection then is "a program on this machine", and the Tailscale-User-Login it sends must count for nothing."""
    SERVE_UID = ME + 1
    @classmethod
    def setUpClass(cls):
        with socket.socket() as s: s.bind(('127.0.0.1', int(os.environ.get('GATE_PORT2') or 0))); cls.port = s.getsockname()[1]
        env = {k: v for k, v in os.environ.items() if not k.startswith('ARGUS_')}
        home = os.path.join(TMP, f'home-{cls.SERVE_UID}'); os.makedirs(home, exist_ok=True)     # its own HOME: no people file
        env.update(HOME=home, USERPROFILE=home, ARGUS_PORT=str(cls.port), ARGUS_STATIC=STATIC, ARGUS_PLUGINS=PLUG,
                   ARGUS_BUNDLED=os.path.join(TMP, 'bundled'), ARGUS_SERVE_UID=str(cls.SERVE_UID),
                   ARGUS_SYSTEMCTL=os.environ['ARGUS_SYSTEMCTL'], ARGUS_WATCH='0')
        cls.log = open(os.path.join(TMP, f'direct-{cls.SERVE_UID}.log'), 'w')
        cls.proc = subprocess.Popen([sys.executable, '-B', os.path.join(R, 'server', 'argus_ui.py')], env=env, stdout=cls.log, stderr=cls.log)
        for _ in range(150):
            try: socket.create_connection(('127.0.0.1', cls.port), timeout=1).close(); break
            except OSError: time.sleep(.1)
    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        try: cls.proc.wait(10)
        except subprocess.TimeoutExpired: cls.proc.kill(); cls.proc.wait(10)
        cls.log.close()
    def get(self, path, **h):
        c = http.client.HTTPConnection('127.0.0.1', self.port, timeout=20)
        c.request(G, '/' + path, headers={'Host': '127.0.0.1', **h}); r = c.getresponse(); b = r.read(); c.close()
        return r.status, json.loads(b)
    def test_faked_login_is_not_trusted_and_not_passed_on(self):
        faked = {'Tailscale-User-Login': OWNER, 'Tailscale-User-Name': 'Owner One', 'X-Forwarded-For': '192.0.2.1'}
        code, d = self.get('api/whoami', **faked)
        self.assertEqual((code, d['login'], d['trusted'], d['through_serve']), (200, OWNER, False, False))
        code, d = self.get('api/closed/data', **faked)
        self.assertEqual((code, d['headers']), (200, {}), "ctx.headers carries none of the faked headers")

class ServeUidIsThePagesOwnUser(FakedHeaderOnADirectConnection):
    """Started with ARGUS_SERVE_UID = its own user (and no ARGUS_DEV): refused with a loud line, nothing counts as Serve."""
    SERVE_UID = ME
    def test_refused_with_a_loud_line(self):
        if not hasattr(os, 'getuid'): self.skipTest('no user ids here')
        self.log.flush()
        with open(self.log.name) as f: self.assertIn("is the page's own user", f.read())

def tearDownModule():
    shutil.rmtree(TMP, ignore_errors=True)

if __name__ == '__main__':
    unittest.main()
