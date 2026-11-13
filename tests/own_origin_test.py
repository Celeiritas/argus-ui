"""A static plugin on its own address (4.42.0, docs/leafy-plugin.md "Its own address"), without a browser: the host file,
the second listener (GET and HEAD only, that plugin's files only, the same people and roles as inside Elaia, the same
caching, no sandbox) and the walls that keep a game on its own origin away from Elaia's powers.

    python3 tests/own_origin_test.py -v        (tests/run.sh runs it under "== own origin"; runs on Windows too)

Elaia and the plugin's own listener run in this process on free ports, with a temporary HOME, fake units, fixture plugins
and an own-origin.json written here; no port number or host name is fixed in this file. Who is asking comes from the real
check, as in tests/gate_test.py: on Linux the real /proc lookup runs, elsewhere the test stands in for it ("simulated")."""
import http.client, importlib.util, io, json, os, re, shutil, socket, sys, tempfile, threading, time, types, unittest

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HAS_PROC = os.path.isfile('/proc/net/tcp')
ME = os.getuid() if hasattr(os, 'getuid') else 4242      # the user id the Serve process "is" in this test
TMP = tempfile.mkdtemp(prefix='argus-own-origin-test-')
HOME = os.path.join(TMP, 'home'); CONF = os.path.join(HOME, '.config', 'argus-ui')
STATIC, PLUG, FX = os.path.join(TMP, 'static'), os.path.join(CONF, 'plugins'), os.path.join(TMP, 'fx')
PEOPLE, OWN_FILE = os.path.join(CONF, 'people.json'), os.path.join(CONF, 'own-origin.json')
for d in (STATIC, PLUG, FX, os.path.join(TMP, 'alerts'), os.path.join(TMP, 'agents')): os.makedirs(d, exist_ok=True)

def put(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f: f.write(text if isinstance(text, str) else json.dumps(text))

def free_port():
    with socket.socket() as s: s.bind(('127.0.0.1', 0)); return s.getsockname()[1]

def ports(n):
    # n different free ports, picked now (none is written in this file)
    out = []
    while len(out) < n:
        p = free_port()
        if p not in out: out.append(p)
    return out

put(os.path.join(STATIC, 'theme.json'), {'title': 'Elaia', 'agents': [{'key': 'argus', 'name': 'Argus', 'domain': 'Watchman'},
    {'key': 'hermes', 'name': 'Hermes', 'domain': 'Delivery'}]})
put(os.path.join(STATIC, 'index.html'), '<!doctype html><title>the page</title><script>const STATE = /*STATE*/null;</script>')
put(os.path.join(STATIC, 'VERSION'), '9.9.9')
put(os.path.join(FX, 'units.json'), {'hermes-sort': {'Result': 'success', 'ActiveState': 'inactive', 'Description': 'Hermes sorting'}})
shutil.copy(os.path.join(R, 'tests', 'fixtures', 'fake_systemctl.py'), FX)
put(os.path.join(FX, 'fake_journal.py'), 'print("2026-10-18T09:20:01 host hermes-sort[1]: a log line")\n')
def wrapper(name, script):
    if os.name == 'nt':
        put(os.path.join(FX, name + '.cmd'), f'@"{sys.executable}" "{os.path.join(FX, script)}" %*\n'); return os.path.join(FX, name + '.cmd')
    put(os.path.join(FX, name), f'#!/bin/sh\nexec "{sys.executable}" "{os.path.join(FX, script)}" "$@"\n'); os.chmod(os.path.join(FX, name), 0o755)
    return os.path.join(FX, name)

# ---- plugins: the game (a copy of the fixture), another static plugin, a server plugin; secrets next to them ----
GAME = os.path.join(PLUG, 'spartamelee')
shutil.copytree(os.path.join(R, 'tests', 'plugin-fixtures', 'spartamelee'), GAME)
put(os.path.join(PLUG, 'other', 'plugin.json'), {'id': 'other', 'name': 'Other'}); put(os.path.join(PLUG, 'other', 'index.html'), 'OTHER-PLUGIN')
put(os.path.join(PLUG, 'srv', 'plugin.json'), {'id': 'srv', 'kind': 'server', 'name': 'Srv', 'page': 'page.js'})
put(os.path.join(PLUG, 'srv', 'page.js'), '// srv page')
put(os.path.join(PLUG, 'srv', 'plugin.py'), 'def get(path, query, ctx):\n    return 200, {"srv": path}\n'
                                           'def post(path, body, ctx):\n    return 200, {"srv-post": path}\n')
put(os.path.join(PLUG, 'secret.txt'), 'TOP-SECRET'); put(os.path.join(TMP, 'secret.txt'), 'TOP-SECRET')
LINKS = {}                                           # symlinks out of the game's folder (skipped where they cannot be made)
for name, target in (('escape', PLUG), ('leak.txt', os.path.join(PLUG, 'secret.txt')), ('far', TMP)):
    try: os.symlink(target, os.path.join(GAME, name), target_is_directory=os.path.isdir(target)); LINKS[name] = target
    except (OSError, NotImplementedError): pass
INDEX_LINKS = {}                                     # real folders of the game whose index.html is a link: out, or to its manifest
for name, target in (('inner', os.path.join(TMP, 'secret.txt')), ('inner-manifest', os.path.join(GAME, 'plugin.json'))):
    os.makedirs(os.path.join(GAME, name), exist_ok=True)
    try: os.symlink(target, os.path.join(GAME, name, 'index.html')); INDEX_LINKS[name] = target
    except (OSError, NotImplementedError): pass

MAIN_PORT, LOCAL, PUBLIC, SRV_LOCAL, SRV_PUBLIC = ports(5)
FRAMES = {'name': 'Frame data', 'path': 'frames/'}
put(OWN_FILE, {'spartamelee': {'port': LOCAL, 'public': PUBLIC, 'links': [FRAMES, {'name': 'Missing', 'path': 'nope/'}]},
               'srv': {'port': SRV_LOCAL, 'public': SRV_PUBLIC}})

os.environ.update(HOME=HOME, USERPROFILE=HOME, ARGUS_STATIC=STATIC, ARGUS_PLUGINS=PLUG, ARGUS_BUNDLED=os.path.join(TMP, 'bundled'),
                  ARGUS_LINKS=os.path.join(CONF, 'links.json'), ARGUS_REGISTRY=os.path.join(TMP, 'agents'), ARGUS_ALERTS=os.path.join(TMP, 'alerts'),
                  ARGUS_PEOPLE_LAST_GOOD=os.path.join(TMP, 'state', 'people.last-good.json'), ARGUS_PORT=str(MAIN_PORT),
                  ARGUS_SERVE_UID=str(ME), ARGUS_DEV='1', ARGUS_WATCH='0', ARGUS_OWN_ORIGIN=OWN_FILE,
                  ARGUS_EVENTS=os.path.join(TMP, 'state', 'events.jsonl'),
                  ARGUS_SYSTEMCTL=wrapper('systemctl', 'fake_systemctl.py'), ARGUS_JOURNALCTL=wrapper('journalctl', 'fake_journal.py'))
for k in ('ARGUS_BIND', 'ARGUS_WEATHER', 'ARGUS_PEOPLE', 'ARGUS_ALLOWED_HOSTS'): os.environ.pop(k, None)
_spec = importlib.util.spec_from_file_location('argus_ui_own_origin_test', os.path.join(R, 'server', 'argus_ui.py'))
a = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(a)
if not HAS_PROC:                                     # no /proc: stand in for the lookup (as tests/gate_test.py does)
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
    a.PEOPLE = a.identity.People(PEOPLE)

TS = 'host.tailnet.ts.net'                           # a placeholder Tailscale name: the browser's Host for Elaia (443)
GAME_ORIGIN = f'https://{TS}:{PUBLIC}'               # where the game runs, as the browser names it
YEAR, FRESH = 'public, max-age=31536000, immutable', 'no-cache'
MAIN = OWNS = None

def setUpModule():
    global MAIN, OWNS
    a.load_server_plugins()
    MAIN = a.ThreadingHTTPServer(('127.0.0.1', 0), a.H)
    threading.Thread(target=MAIN.serve_forever, daemon=True).start()
    OWNS = a.start_own_origins()

def tearDownModule():
    for s in [MAIN, *(OWNS or {}).values()]:
        if s: s.shutdown(); s.server_close()
    shutil.rmtree(TMP, ignore_errors=True)

def send(port, verb, path, host='127.0.0.1', login=None, body=None, **headers):
    # a raw request, as Serve passes one on (the sender's address in X-Forwarded-For, a documentation address): the path
    # goes out exactly as written, dots and percent signs included
    c = http.client.HTTPConnection('127.0.0.1', port, timeout=20)
    h = {'Host': host, 'X-Forwarded-For': '192.0.2.20', **{k.replace('_', '-'): v for k, v in headers.items()}}
    if login: h['Tailscale-User-Login'] = login
    c.request(verb, path, body=body, headers=h)
    r = c.getresponse(); b = r.read(); c.close()
    return r.status, {k.lower(): v for k, v in r.getheaders()}, b

def own(path, verb='GET', **k): return send(LOCAL, verb, path, **k)
def main(path, verb='GET', **k): return send(MAIN.server_address[1], verb, '/argus/' + path, **k)

class Config(unittest.TestCase):
    """own-origin.json: no file changes nothing, a broken file or entry is left out with a line in the log."""
    def conf(self, doc):
        f = os.path.join(TMP, f'conf-{time.time_ns()}.json'); put(f, doc); return f

    def test_no_file_is_nothing(self):
        self.assertEqual(a.load_own_origin(os.path.join(TMP, 'no-such-file.json')), {})

    def test_broken_files_are_nothing(self):
        for doc in ('{"spartamelee": ', '[]', '"x"', '7', 'null'):
            self.assertEqual(a.load_own_origin(self.conf(doc)), {}, doc)

    def test_bad_entries_are_left_out(self):
        p1, p2, p3, p4, p5, q1, q2, q3 = ports(8)
        ok = lambda port, public: {'port': port, 'public': public}
        doc = {'Bad_ID': ok(p2, q2), 'api': ok(p2, q2), 'plugins': ok(p2, q2), 'home': ok(p2, q2), '-x': ok(p2, q2),
               'notdict': [p2, q2], 'b-bool': ok(True, q2), 'b-argus': ok(a.PORT, q2), 'b-low': ok(1023, q2), 'b-high': ok(65536, q2),
               'b-str': ok(str(p2), q2), 'b-float': ok(float(p2), q2), 'b-none': {'public': q2},
               'good': ok(p1, q1),
               'dup-port': ok(p1, q2), 'pub-443': ok(p3, 443), 'pub-80': ok(p3, 80), 'pub-dup': ok(p3, q1), 'pub-zero': ok(p3, 0),
               'pub-str': ok(p3, str(q2)), 'pub-none': {'port': p3},
               'second': ok(p4, q2), 'third': dict(ok(p5, q3), links='frames/')}
        got = a.load_own_origin(self.conf(doc))
        self.assertEqual(got, {'good': {'port': p1, 'public': q1, 'links': []}, 'second': {'port': p4, 'public': q2, 'links': []},
                               'third': {'port': p5, 'public': q3, 'links': []}})

    def test_only_links_inside_the_plugin(self):
        p1, q1 = ports(2)
        good = [{'name': f' Page {i} ', 'path': f'page{i}/'} for i in range(5)]
        bad = [{'name': 'Up', 'path': '../x'}, {'name': 'Abs', 'path': '/etc/x'}, {'name': 'Web', 'path': 'https://evil.example/'},
               {'name': 'Proto', 'path': '//evil.example/'}, {'name': 'Deep', 'path': 'a/../../b'}, {'name': 'Back', 'path': 'a\\b'},
               {'name': '', 'path': 'a/'}, {'name': '   ', 'path': 'a/'}, {'name': 'x' * 41, 'path': 'a/'}, {'name': 'Q', 'path': 'a/?x=<b>'},
               {'name': 'Js', 'path': 'javascript:alert(1)'}, {'name': 'Empty', 'path': ''}, {'name': 7, 'path': 'a/'}, 'frames/', None]
        got = a.load_own_origin(self.conf({'game': {'port': p1, 'public': q1, 'links': bad + good}}))
        self.assertEqual(got['game']['links'], [{'name': f'Page {i}', 'path': f'page{i}/'} for i in range(4)], 'the valid ones, at most 4')

    def test_what_the_page_gets(self):
        # api/state: the game has "own" with both ports and only the links that point at a page inside it
        no_people()
        d = json.loads(main('api/state')[2]); ps = {p['id']: p for p in d['plugins']}
        self.assertEqual(ps['spartamelee']['own'], {'public': PUBLIC, 'local': LOCAL, 'links': [FRAMES]})
        self.assertNotIn('own', ps['other'], 'a static plugin without an entry keeps the sandboxed frame')
        self.assertNotIn('own', ps['srv'], 'a server plugin never gets an own address')
        self.assertEqual(sorted(OWNS), ['spartamelee', 'srv'])
        self.assertEqual(OWNS['spartamelee'].server_address[0], '127.0.0.1', 'this machine only; tailscale serve publishes it')
        write_people(GOOD)
        self.assertNotIn(b'"own"', main('api/state', login=LEARNER)[2], "a learner's cut-down state names no own address")
        no_people()

    def test_a_busy_port_is_skipped(self):
        busy, q = ports(2)
        s = socket.socket()
        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'): s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        s.bind(('127.0.0.1', busy)); s.listen(1)
        before = dict(a.OWN)
        try: self.assertEqual(a.start_own_origins(self.conf({'busy-game': {'port': busy, 'public': q}})), {})
        finally: s.close()
        self.assertEqual(a.OWN, before, 'Elaia keeps the sandboxed frame for it')

class Cookies(unittest.TestCase):
    """Cookies belong to a host name, not a port: the game on its own address can set up to about a megabyte of them, and
    the browser then sends them to Elaia too. Argus reads none, so a Cookie header of any size a browser sends changes
    nothing on either listener (the standard library alone answers 431 past 64 KB)."""
    BIG = 'a=' + 'x' * 900_000                           # 900 KB in one Cookie line, as Serve passes the browser's on
    def setUp(self): no_people()
    def tearDown(self): no_people()

    def test_a_huge_cookie_changes_nothing(self):
        for what, (code, h, b) in (('the own address', own('/', Cookie=self.BIG)), ('a file there', own('/app.js', Cookie=self.BIG)),
                                   ('Elaia api/state', main('api/state', host=TS, Cookie=self.BIG)),
                                   ('Elaia page', main('spartamelee', host=TS, Cookie=self.BIG)),
                                   ("Elaia's framed copy", main('plugins/spartamelee/', Cookie=self.BIG))):
            self.assertEqual(code, 200, what)
        code, h, b = main('api/thaw', 'POST', body=json.dumps({'job': 'hermes-sort'}).encode(), Content_Type='application/json',
                          host=TS, Origin=f'https://{TS}', Sec_Fetch_Site='same-origin', Cookie=self.BIG, login=OWNER)
        self.assertEqual(code, 200, 'a POST from Elaia itself'); self.assertTrue(json.loads(b)['ok'])
        # the lines after the cookie still count: the login (sent after it) names the owner, a cross-site POST is still refused
        write_people(GOOD)
        who = json.loads(main('api/whoami', host=TS, Cookie=self.BIG, login=OWNER)[2])
        self.assertEqual((who['role'], who['login']), ('owner', OWNER))
        self.assertEqual(own('/', Cookie=self.BIG, login=LEARNER)[0], 403, 'and on the own address the role check still runs')
        code, h, b = main('api/freeze', 'POST', body=b'{"job": "hermes-sort"}', Content_Type='application/json', host=TS,
                          Origin=GAME_ORIGIN, Sec_Fetch_Site='same-site', Cookie=self.BIG, login=OWNER)
        self.assertEqual(code, 403); self.assertNotIn('hermes-sort', a.frozen())

    def test_the_reader(self):
        # NoCookies alone: Cookie lines in any case and of any length (and a folded line of one) are left out, the rest
        # comes through unchanged; past CAP bytes of cookies the line comes back too long, so the request still ends in 431
        raw = (b'Host: x\r\nCookie: a=1\r\ncOOKIE: ' + b'y' * 200_000 + b'\r\n\tfolded\r\nX-Other: 2\r\nCookie2: kept\r\n'
               b'Cookie:\r\n\r\nbody')
        r, lines = a.NoCookies(io.BytesIO(raw)), []
        while not lines or lines[-1] not in (b'\r\n', b''): lines.append(r.readline(65537))
        self.assertEqual(lines, [b'Host: x\r\n', b'X-Other: 2\r\n', b'Cookie2: kept\r\n', b'\r\n'])
        self.assertEqual(r.f.read(), b'body', 'the body is untouched')
        over = a.NoCookies(io.BytesIO(b'Cookie: ' + b'z' * (a.NoCookies.CAP + 10) + b'\r\n\r\n'))
        self.assertGreater(len(over.readline(65537)), 65536, 'more than CAP: a line too long, 431 as before')
        self.assertEqual(a.NoCookies(io.BytesIO(b'Cookie: a=1')).readline(65537), b'', 'the connection ended inside a cookie')

class Listener(unittest.TestCase):
    """The game's files at the root of its own address, with Elaia's caching and its own origin's headers."""
    def setUp(self): no_people()

    def own_headers(self, h, what):
        csp = h.get('content-security-policy', '')
        self.assertNotIn('sandbox', csp, what); self.assertIn("frame-ancestors 'self'", csp, what)
        self.assertNotIn('frame-ancestors *', csp, what); self.assertNotRegex(csp, r"frame-ancestors[^;]*\*", what)
        self.assertEqual((h.get('x-frame-options'), h.get('cross-origin-opener-policy'), h.get('x-content-type-options')),
                         ('SAMEORIGIN', 'same-origin', 'nosniff'), what)
        for k in ('access-control-allow-origin', 'access-control-allow-credentials', 'set-cookie'): self.assertNotIn(k, h, what)

    def test_the_game_at_the_root(self):
        code, h, b = own('/')
        self.assertEqual(code, 200); self.assertIn(b'<p id="out">loading</p>', b)
        self.assertEqual(h['content-security-policy'], a.OWN_HEADERS['Content-Security-Policy']); self.own_headers(h, '/')
        for path in ('/index.html', '/app.js', '/data.json', '/frames/', '/frames/index.html', '/?v=2', '/models/ares.1a2b3c4d.glb'):
            code, h, b = own(path); self.assertEqual(code, 200, path); self.own_headers(h, path)
        self.assertIn(b'Frame data', own('/frames/')[2])
        self.assertTrue(own('/app.js')[1]['content-type'].startswith('text/javascript'))

    def test_caching_as_inside_elaia(self):
        code, h, _ = own('/models/ares.1a2b3c4d.glb')
        self.assertRegex(h['etag'], r'^"[0-9a-f]+-[0-9a-f]+"$'); self.assertTrue(h['last-modified'].endswith(' GMT'))
        self.assertEqual(h['cache-control'], YEAR, 'a content-hashed name is kept a year')
        for path in ('/', '/index.html', '/app.js', '/data.json'): self.assertEqual(own(path)[1]['cache-control'], FRESH, path)
        code, h2, b = own('/models/ares.1a2b3c4d.glb', If_None_Match=h['etag'])
        self.assertEqual((code, b, h2['etag'], h2['cache-control']), (304, b'', h['etag'], YEAR)); self.own_headers(h2, '304')
        lm = own('/index.html')[1]['last-modified']
        self.assertEqual(own('/index.html', If_Modified_Since=lm)[0], 304)
        same = main('plugins/spartamelee/models/ares.1a2b3c4d.glb')[1]
        self.assertEqual((same['etag'], same['cache-control']), (h['etag'], YEAR), 'the same validators as inside Elaia')

    def test_head(self):
        g, h = own('/'), own('/', 'HEAD')
        self.assertEqual((h[0], h[2]), (200, b'')); self.assertEqual(h[1]['content-length'], str(len(g[2])))
        self.assertEqual(h[1]['etag'], g[1]['etag']); self.own_headers(h[1], 'HEAD')
        self.assertEqual(own('/nope.js', 'HEAD')[:3:2], (404, b''))

    def test_a_folder_gets_its_slash(self):
        code, h, b = own('/frames')
        self.assertEqual((code, h['location'], b), (301, '/frames/', b'')); self.own_headers(h, '301')
        self.assertEqual(own('/frames?x=1')[1]['location'], '/frames/')
        self.assertEqual(own('/models')[1]['location'], '/models/')
        self.assertEqual(own('/models/')[0], 404, 'a folder without index.html is not listed')

    def test_host_check(self):
        self.assertEqual(own('/', host=f'{TS}:{PUBLIC}')[0], 200, 'its Tailscale name with the public port')
        self.assertEqual(own('/', host=f'127.0.0.1:{LOCAL}')[0], 200)
        for bad in ('evil.example', f'evil.example:{PUBLIC}', 'ts.net.evil.example', ''):
            code, h, b = own('/', host=bad)
            self.assertEqual(code, 421, bad); self.assertNotIn(b'loading', b); self.own_headers(h, bad)

    def test_unknown_files(self):
        for path in ('/nope.js', '/frames/nope.html', '/plugin.json', '/%70lugin.json', '/frames/../plugin.json', '/PLUGIN.JSON' if os.name != 'nt' else '/nope'):
            code, h, b = own(path)
            self.assertEqual(code, 404, path); self.assertNotIn(b'"id"', b, path); self.own_headers(h, path)

class Paths(unittest.TestCase):
    """Nothing outside the game's folder: dots plain and encoded, backslashes, NUL, other plugins, symlinks out."""
    def setUp(self): no_people()
    SECRETS = (b'TOP-SECRET', b'OTHER-PLUGIN', b'owner@example.com', b'"people"', b'Hermes', b'hermes-sort', b'srv page')

    def refused(self, path, *codes):
        code, h, b = own(path, login=OWNER)              # as the owner: the folder check, not the role check, must refuse it
        self.assertIn(code, codes or (404,), path)
        for s in self.SECRETS: self.assertNotIn(s, b, f'{path} leaked {s!r}')
        self.assertNotIn('access-control-allow-origin', h, path)

    def test_dots(self):
        write_people(GOOD)                               # so ../../people.json would have something to leak
        for path in ('/../secret.txt', '/../../secret.txt', '/../../../secret.txt', '/../other/index.html', '/../../people.json',
                     '/..%2fsecret.txt', '/%2e%2e/secret.txt', '/%2E%2E%2Fsecret.txt', '/%2e%2e%2f%2e%2e%2fpeople.json',
                     '/.%2e/secret.txt', '/%2e./secret.txt', '/frames/../../secret.txt', '/frames/%2e%2e/%2e%2e/secret.txt',
                     '/frames/..%2f..%2fsecret.txt', '/%252e%252e/secret.txt', '/..;/secret.txt', '/../srv/page.js',
                     '/../srv/plugin.py', '/frames/../../other/index.html', '/./../secret.txt'):
            with self.subTest(path=path): self.refused(path)
        no_people()

    def test_backslashes_nul_and_odd_forms(self):
        for path in ('/..%5csecret.txt', '/..\\secret.txt', '/frames\\..\\..\\secret.txt', '/%5c%5cevil.example/x',
                     '/%00', '/index.html%00.js', '/index.html%00', '/%2fsecret.txt', '/%2f%2fevil.example/', '//secret.txt',
                     '/frames//index.html', '/C:/secret.txt', '/c%3a%5csecret.txt', f'http://127.0.0.1:{LOCAL}/../secret.txt',
                     'secret.txt', '*'):
            with self.subTest(path=path): self.refused(path)

    def test_no_open_redirect(self):
        # the only redirect is a folder of the game to itself with a slash, always a path that starts with one /
        for path in ('/frames', '/%2fevil.example', '/%2f%2fevil.example', '//evil.example', '/%5cevil.example', '/frames%2f..%2f..'):
            code, h, b = own(path)
            loc = h.get('location')
            if loc is not None: self.assertTrue(loc.startswith('/') and not loc.startswith('//') and '\\' not in loc, f'{path} -> {loc}')

    def test_symlinks_out(self):
        if not LINKS: self.skipTest('symbolic links cannot be made here')
        for path in ('/escape/secret.txt', '/escape', '/escape/', '/escape/other/index.html', '/leak.txt', '/far/secret.txt', '/far/'):
            with self.subTest(path=path): self.refused(path)
        self.assertNotEqual(own('/escape')[1].get('location'), '/escape/', 'a link to a folder outside is no folder of the game')

    def test_an_index_that_is_a_link(self):
        # a real folder of the game whose index.html links out of it, or to the plugin's own manifest: the folder's address
        # serves nothing, on the own address and inside Elaia, and no link of the page points there
        if not INDEX_LINKS: self.skipTest('symbolic links cannot be made here')
        for path in ('/inner/', '/inner/index.html', '/inner-manifest/', '/inner-manifest/index.html', '/inner/?v=1'):
            with self.subTest(path=path):
                self.refused(path); self.assertNotIn(b'"id"', own(path, login=OWNER)[2], path)
        for path in ('plugins/spartamelee/inner/', 'plugins/spartamelee/inner/index.html', 'plugins/spartamelee/inner-manifest/'):
            with self.subTest(path=path):
                code, h, b = main(path, login=OWNER)
                self.assertEqual(code, 404, path); self.assertNotIn(b'TOP-SECRET', b, path); self.assertNotIn(b'"id"', b, path)
        for rel in ('inner/', 'inner', 'inner-manifest/', 'inner/index.html'): self.assertFalse(a.own_link_ok(GAME, rel), rel)
        self.assertTrue(a.own_link_ok(GAME, 'frames/'), 'the control: a real page')

class Methods(unittest.TestCase):
    """GET and HEAD only: every other method is 405 before any route, also with a body or on a path that exists."""
    def test_only_get_and_head(self):
        for verb in ('POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'TRACE', 'CONNECT', 'PROPFIND', 'MKCOL', 'FOO'):
            for path in ('/', '/app.js', '/api/freeze', '/nope'):
                code, h, b = own(path, verb)
                self.assertEqual((code, h.get('allow')), (405, 'GET, HEAD'), f'{verb} {path}')
                self.assertNotIn('access-control-allow-origin', h); self.assertNotIn(b'loading', b)
        code, h, b = own('/', 'POST', body=b'{"job": "hermes-sort"}', Content_Type='application/json')
        self.assertEqual(code, 405)
        self.assertNotIn('hermes-sort', a.frozen())

    def test_no_api_here(self):
        no_people()
        for path in ('/api/state', '/api/whoami', '/api/health', '/argus/api/state', '/argus/', '/static/theme.json',
                     '/plugins/spartamelee/index.html', '/plugins/other/index.html', '/api/srv/ping', '/sw.js'):
            code, h, b = own(path)
            self.assertEqual(code, 404, path); self.assertNotIn(b'hermes', b, path); self.assertNotIn(b'Elaia', b, path)

    def test_a_server_plugin_listener_serves_nothing(self):
        no_people()
        for path in ('/', '/page.js', '/plugin.py', '/plugin.json'):
            self.assertEqual(send(SRV_LOCAL, 'GET', path)[0], 404, path)

class Roles(unittest.TestCase):
    """The same people and roles as opening plugins/<id>/ inside Elaia: each case answers the same on both addresses."""
    def tearDown(self): no_people(); a.SERVE_UID = ME

    def both(self, what, **k):
        mine, theirs = own('/', **k), main('plugins/spartamelee/', **k)
        self.assertEqual(mine[0], theirs[0], f'{what}: the own address and Elaia agree')
        return mine

    def private(self, r, what):
        code, h, b = r
        self.assertEqual(code, 403, what)
        self.assertTrue(b.startswith(b'<!doctype html>') and b'This page is private' in b, what)
        self.assertNotIn(b'<script', b, what); self.assertNotIn(b'api/whoami', b, f'{what}: no API link, there is none here')
        self.assertIn("default-src 'none'", h['content-security-policy'], what); self.assertNotIn(b'loading', b, what)

    def test_each_role(self):
        write_people(GOOD)
        self.assertEqual(self.both('owner', login=OWNER)[0], 200)
        code, h, b = self.both('learner', login=LEARNER)
        self.assertEqual(code, 403); self.assertIn(b'Only the owner', b); self.assertNotIn(b'loading', b)
        self.private(self.both('a login not on the list', login=STRANGER), 'stranger')
        self.private(self.both('no login'), 'no login')
        self.private(self.both('from the server itself', login=OWNER, X_Forwarded_For='127.0.0.1'), 'from the server itself')
        self.assertIn(b'came from the server itself', own('/', login=OWNER, X_Forwarded_For='127.0.0.1')[2])
        for path in ('/app.js', '/frames/', '/models/ares.1a2b3c4d.glb', '/nope.js', '/frames'):
            self.assertEqual(own(path, login=LEARNER)[0], 403, f'learner {path}: refused before the file is looked up')
            self.assertEqual(own(path, login=STRANGER)[0], 403, f'stranger {path}')

    def test_no_people_file(self):
        no_people()
        for login in (OWNER, None, STRANGER): self.assertEqual(self.both(f'no file, {login}', login=login)[0], 200)

    def test_broken_file_is_closed(self):
        write_people('{"people": ['); a.PEOPLE = a.identity.People(PEOPLE)      # as at a first start, no saved copy
        for login in (OWNER, LEARNER, STRANGER, None):
            code, h, b = self.both(f'closed, {login}', login=login)
            self.assertEqual(code, 403, login); self.assertIn(b'move the people file aside to a dated name', b)

    def test_a_faked_login_counts_for_nothing(self):
        # the connection does not belong to Tailscale Serve's user: the login header it carries is not believed
        write_people(GOOD); a.SERVE_UID = ME + 1
        self.private(self.both('faked owner login', login=OWNER), 'faked')

class ElaiaStaysShut(unittest.TestCase):
    """What a page on the game's origin could try against Elaia (a different port of the same name: same site, not same
    origin): every POST is refused before it runs, and no answer of Elaia lets it read anything."""
    POSTS = ('api/freeze', 'api/thaw', 'api/bolt', 'api/run', 'api/watch/fix', 'api/push/subscribe', 'api/push/kinds',
             'api/push/forget', 'api/push/test', 'api/srv/echo', 'api/nothing')
    def setUp(self): no_people()                       # everyone is the owner: only the cross-site checks stand in the way
    def tearDown(self): no_people()

    def post(self, path, ctype='application/json', **h):
        return main(path, 'POST', body=json.dumps({'job': 'hermes-sort', 'id': 'x'}).encode(), Content_Type=ctype, login=OWNER, **h)

    def test_every_post_from_the_game_is_refused(self):
        local_game = f'http://127.0.0.1:{LOCAL}'
        cases = (('origin and fetch metadata', dict(host=TS, Origin=GAME_ORIGIN, Sec_Fetch_Site='same-site')),
                 ('origin only (no fetch metadata)', dict(host=TS, Origin=GAME_ORIGIN)),
                 ('fetch metadata only', dict(host=TS, Sec_Fetch_Site='same-site')),
                 ('Elaia on a port of its own too', dict(host=f'{TS}:{PUBLIC + 1}', Origin=GAME_ORIGIN)),
                 ('plain http on this machine', dict(host=f'127.0.0.1:{MAIN.server_address[1]}', Origin=local_game, Sec_Fetch_Site='same-site')),
                 ('plain http, origin only', dict(host=f'127.0.0.1:{MAIN.server_address[1]}', Origin=local_game)))
        for path in self.POSTS:
            for what, h in cases:
                code, hh, b = self.post(path, **h)
                self.assertEqual(code, 403, f'{path}: {what}'); self.assertIn(b'cross-site request blocked', b, f'{path}: {what}')
                self.assertNotIn('access-control-allow-origin', hh)
            # a "simple" request (no question asked first): not JSON, refused before anything else
            self.assertEqual(self.post(path, 'text/plain', host=TS, Origin=GAME_ORIGIN, Sec_Fetch_Site='same-site')[0], 415, path)
            self.assertEqual(self.post(path, 'application/x-www-form-urlencoded', host=TS, Origin=GAME_ORIGIN)[0], 415, path)
        self.assertNotIn('hermes-sort', a.frozen(), 'the task the game tried to freeze is untouched')

    def test_the_same_checks_let_elaia_itself_through(self):
        # the control: Elaia's own page (same origin) passes the very checks the game fails
        for h in (dict(host=TS, Origin=f'https://{TS}', Sec_Fetch_Site='same-origin'), dict(host=TS)):
            code, hh, b = self.post('api/thaw', **h)
            self.assertEqual(code, 200, h); self.assertTrue(json.loads(b)['ok'])

    def test_no_question_first_gets_a_yes(self):
        # the browser asks first (OPTIONS) before a JSON POST from another origin; Elaia answers no such method
        for path in self.POSTS + ('api/state', ''):
            code, h, b = main(path, 'OPTIONS', host=TS, Origin=GAME_ORIGIN, Access_Control_Request_Method='POST',
                              Access_Control_Request_Headers='content-type')
            self.assertFalse(200 <= code < 300, f'OPTIONS {path} -> {code}')
            self.assertFalse([k for k in h if k.startswith('access-control-')], f'OPTIONS {path}: {h}')

    def test_no_api_answer_lets_another_origin_read_it(self):
        for path in ('api/state', 'api/whoami', 'api/health', 'api/sky', 'api/events', 'api/log/hermes-sort', 'api/push/status',
                     'api/srv/ping', 'api/nothing', '', 'spartamelee', 'static/theme.json', 'plugins/srv/page.js', 'nope'):
            for h in (dict(host=TS, Origin=GAME_ORIGIN, Sec_Fetch_Site='same-site'), dict(host=TS)):
                code, hh, b = main(path, login=OWNER, **h)
                self.assertFalse([k for k in hh if k.startswith('access-control-')], f'GET {path} {code}: {hh}')

    def test_cors_header_only_on_sandboxed_plugin_files(self):
        # in the source, "Access-Control-Allow-Origin" appears in PLUGIN_HEADERS (the sandboxed frame's files) and in the line
        # that takes it out again for a server plugin's files; nowhere else, and never in the own address's headers
        for name in sorted(os.listdir(os.path.join(R, 'server'))):
            if not name.endswith('.py'): continue
            src = open(os.path.join(R, 'server', name), encoding='utf-8').read()
            code = [l for l in src.splitlines() if 'access-control-allow' in l.lower() and not l.lstrip().startswith('#')]
            if name == 'argus_ui.py':
                self.assertEqual(len(code), 2, code)
                self.assertTrue(code[0].lstrip().startswith("'Access-Control-Allow-Origin': '*'"), code[0])
                self.assertTrue(code[1].startswith('SERVER_FILE_HEADERS = ') and "if k != 'Access-Control-Allow-Origin'" in code[1], code[1])
            else: self.assertEqual(code, [], name)
        self.assertFalse([k for k in a.OWN_HEADERS if k.lower().startswith('access-control-')])
        self.assertEqual(main('plugins/spartamelee/index.html')[1].get('access-control-allow-origin'), '*', 'the sandboxed frame keeps its own')

    def test_the_sandbox_stays_as_it_was(self):
        # Elaia's copy of the game is still sandboxed, and no page code gives a frame allow-same-origin
        code, h, b = main('plugins/spartamelee/index.html')
        self.assertEqual(h['content-security-policy'], a.PLUGIN_HEADERS['Content-Security-Policy'])
        self.assertIn('sandbox allow-scripts allow-pointer-lock allow-popups;', h['content-security-policy'])
        web = os.path.join(R, 'web', 'js')
        for name in os.listdir(web):
            self.assertNotIn('allow-same-origin', open(os.path.join(web, name), encoding='utf-8').read(), name)
        src = open(os.path.join(web, 'plugins.js'), encoding='utf-8').read()
        self.assertEqual(re.findall(r'sandbox="([^"]*)"', src), ['allow-scripts allow-pointer-lock allow-popups'])
        self.assertNotIn('<iframe', src[src.index('function showOwn'):src.index('function api(')], 'the own address is never framed')

if __name__ == '__main__':
    unittest.main()
