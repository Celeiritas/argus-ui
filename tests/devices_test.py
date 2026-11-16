"""The device list (server/devices.py, docs/devices.md): the file, the Tailscale probe and GET api/devices. No browser.

    python tests/devices_test.py -v        (tests/run.sh runs it under "== devices")

  * the file: a good one, none (an empty list, silent), bad JSON (one stderr line, not repeated), each rule the file can
    break (names, kinds, probes, hosts, two "self", wake addresses, too many, too large); read again when it changes
  * the probe, with a stand-in for tailscale (tests/fixtures/fake_tailscale.py and its canned answer): online, offline with
    the time last seen, a host not on the list, a peer Tailscale says nothing about, a device Argus does not check, this
    machine by its own name; every way the probe can go wrong (no binary, an error, no answer in time, not JSON, Tailscale
    stopped) is "can't tell", never "offline"; ONE call for all devices, cached, Check again asks again only after 5 s
  * this machine: Desktop or Game mode when the mode probe says so, else Online; a mode probe that fails is Online
  * the route on a real server in this process: the owner gets the list, a learner 403, the MAC address never leaves
Who is asking comes from the real check on Linux; without /proc (Windows, macOS) the lookup is stood in for, as in
tests/gate_test.py. The page side is tests/devices.test.js."""
import contextlib, http.client, importlib.util, io, json, os, shutil, sys, tempfile, threading, time, unittest

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HAS_PROC = os.path.isfile('/proc/net/tcp')
ME = os.getuid() if hasattr(os, 'getuid') else 4242
TMP = tempfile.mkdtemp(prefix='argus-devices-test-')
HOME = os.path.join(TMP, 'home'); CONF = os.path.join(HOME, '.config', 'argus-ui')
STATIC, FX, STATE = os.path.join(TMP, 'static'), os.path.join(TMP, 'fx'), os.path.join(TMP, 'state')
PEOPLE, DEVICES = os.path.join(CONF, 'people.json'), os.path.join(TMP, 'devices.json')
MODEFILE = os.path.join(FX, 'devices', 'tailscale-mode')
for d in (STATIC, os.path.join(FX, 'devices'), STATE, CONF, os.path.join(TMP, 'alerts'), os.path.join(TMP, 'agents')): os.makedirs(d, exist_ok=True)

def put(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f: f.write(data if isinstance(data, str) else json.dumps(data))

def bump(path, n=[0]):
    # a new modification time on every write, even on a coarse clock: the server reads the file again when it changes
    n[0] += 1; st = os.stat(path); os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + n[0] * 1_000_000_000))

def write(path, data): put(path, data); bump(path)

def set_aside(path):
    # tests keep their own files in TMP; one that must be gone is moved aside, never deleted
    if os.path.exists(path): shutil.move(path, f'{path}.set-aside-{os.urandom(4).hex()}')

put(os.path.join(STATIC, 'theme.json'), {'title': 'Elaia', 'agents': [{'key': 'argus', 'name': 'Argus'}]})
put(os.path.join(STATIC, 'index.html'), '<!doctype html><title>the page</title><script>const STATE = /*STATE*/null;</script>')
put(os.path.join(STATIC, 'VERSION'), '9.9.9')
FAKE = os.path.join(FX, 'fake_tailscale.py')
shutil.copy(os.path.join(R, 'tests', 'fixtures', 'fake_tailscale.py'), FAKE)
shutil.copy(os.path.join(R, 'tests', 'fixtures', 'devices', 'tailscale-status.json'), os.path.join(FX, 'devices'))
FIXTURE = json.loads(open(os.path.join(R, 'tests', 'fixtures', 'devices', 'devices.json'), encoding='utf-8').read())

os.environ.update(HOME=HOME, USERPROFILE=HOME, ARGUS_STATIC=STATIC, ARGUS_PLUGINS=os.path.join(CONF, 'plugins'),
                  ARGUS_BUNDLED=os.path.join(TMP, 'bundled'), ARGUS_LINKS=os.path.join(CONF, 'links.json'),
                  ARGUS_REGISTRY=os.path.join(TMP, 'agents'), ARGUS_ALERTS=os.path.join(TMP, 'alerts'),
                  ARGUS_PEOPLE_LAST_GOOD=os.path.join(STATE, 'people.last-good.json'), ARGUS_KNOWN=os.path.join(STATE, 'known.json'),
                  ARGUS_SERVE_UID=str(ME), ARGUS_DEV='1', ARGUS_WATCH='0', ARGUS_DEVICES=DEVICES, ARGUS_DEVICES_CACHE='30',
                  ARGUS_MODES=os.path.join(TMP, 'no-modes.json'))
for k in ('ARGUS_BIND', 'ARGUS_WEATHER', 'ARGUS_PEOPLE', 'ARGUS_TAILSCALE'): os.environ.pop(k, None)
_spec = importlib.util.spec_from_file_location('argus_ui_devices_test', os.path.join(R, 'server', 'argus_ui.py'))
a = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(a)
D = a.devices                                       # the very module the server uses
if not HAS_PROC:                                    # no /proc: stand in for the lookup (as tests/gate_test.py does)
    a.identity.connection_uid = lambda peer, ours, proc='/proc', our_inode=None: ME
print(f'\n  [identity path: {"real /proc lookup" if HAS_PROC else "simulated (no /proc on this machine)"}]', file=sys.stderr)

OWNER, LEARNER = 'owner@example.com', 'learner@example.com'
put(PEOPLE, {'people': [{'id': 'owner-one', 'name': 'Owner One', 'role': 'owner', 'logins': [OWNER]},
                        {'id': 'learner-two', 'name': 'Learner Two', 'role': 'learner', 'logins': [LEARNER]}]})

# the fake runs straight under this interpreter (no wrapper: a timeout then kills the fake itself, on every system)
CALLS = []
REAL_COMMAND = D.command
def fake_command():
    CALLS.append(1); return [sys.executable, FAKE, 'status', '--json']
D.command = fake_command

def answer(mode='ok'):
    if mode == 'ok': set_aside(MODEFILE)
    else: put(MODEFILE, mode)
    D.clear_cache()

def reset(devices=FIXTURE):
    if devices is None: set_aside(DEVICES)
    else: write(DEVICES, devices)
    answer('ok'); CALLS.clear()

def by_name(v): return {d['name']: d for d in v['devices']}
EMPTY = {'set_up': False, 'problem': None, 'file': None, 'device': None, 'probe_problem': None, 'checked': None, 'devices': []}
DESKTOP = lambda: {'current': 'desktop', 'modes': [{'id': 'desktop', 'label': 'Desktop'}, {'id': 'game', 'label': 'Game'}]}
GAME = lambda: {'current': 'game', 'modes': [{'id': 'desktop', 'label': 'Desktop'}, {'id': 'game', 'label': 'Game'}]}


class Config(unittest.TestCase):
    def setUp(self): reset()

    def test_good_file(self):
        ds, problem = D.config()
        self.assertIsNone(problem)
        self.assertEqual([d['name'] for d in ds], ['Shelf', 'Desk PC', 'Spare PC', 'Phone', 'Tablet', 'Laptop', 'Old console'])
        self.assertEqual(ds[1], {'name': 'Desk PC', 'kind': 'pc', 'probe': 'tailscale', 'host': 'pc-one', 'wake': True})
        self.assertEqual(ds[0]['host'], None); self.assertFalse(ds[3]['wake'])

    def test_no_file_is_an_empty_list_and_silent(self):
        reset(None); err = io.StringIO()
        with contextlib.redirect_stderr(err): v = D.view()
        self.assertEqual(v, EMPTY)
        self.assertEqual(err.getvalue(), ''); self.assertEqual(CALLS, [], 'no file: Tailscale is not asked')

    def test_bad_json_says_so_once(self):
        write(DEVICES, '{"devices": [')
        err = io.StringIO()
        with contextlib.redirect_stderr(err): v1 = D.view(); v2 = D.view()
        self.assertTrue(v1['set_up']); self.assertEqual(v1['devices'], [])
        self.assertIn('not valid JSON', v1['problem']); self.assertEqual(v1, v2)
        self.assertEqual(err.getvalue().count('argus-ui:'), 1, 'one line, not one per request')

    def test_read_again_when_it_changes(self):
        self.assertEqual(len(D.view()['devices']), 7)
        write(DEVICES, {'devices': [{'name': 'Only one', 'kind': 'pc', 'probe': 'none'}]})
        self.assertEqual([d['name'] for d in D.view()['devices']], ['Only one'])

    def bad(self, devices, words):
        write(DEVICES, {'devices': devices} if isinstance(devices, list) else devices)
        with contextlib.redirect_stderr(io.StringIO()): v = D.view()
        self.assertEqual(v['devices'], []); self.assertIn(words, v['problem'] or '', v)

    def test_each_rule(self):
        ok = {'name': 'A', 'kind': 'pc', 'probe': 'tailscale', 'host': 'pc-a'}
        self.bad({'things': []}, 'needs a "devices" list')
        self.bad([ok] * 1 + ['x'], 'device 2 is not an object')
        self.bad([dict(ok, name='')], 'the name must be 1 to 40')
        self.bad([dict(ok, name='x' * 41)], 'the name must be 1 to 40')
        self.bad([dict(ok, name='tab\there')], 'the name must be 1 to 40')
        self.bad([ok, dict(ok, name='a')], 'two devices are called')
        self.bad([dict(ok, kind='toaster')], 'the kind must be one of')
        self.bad([dict(ok, probe='ping')], 'the probe must be one of')
        self.bad([dict(ok, host=None)], '"host" must be its Tailscale host name')
        for h in ('pc a', 'pc;reboot', '-pc', 'pc.example.ts.net', '$(id)', 'x' * 64):
            self.bad([dict(ok, host=h)], '"host" must be its Tailscale host name')
        self.bad([{'name': 'A', 'probe': 'self'}, {'name': 'B', 'probe': 'self'}], 'only one device can be "self"')
        for w in ('aa:bb:cc:dd:ee:ff', {'mac': 'aa:bb:cc:dd:ee'}, {'mac': 'aa:bb-cc:dd:ee:ff'}, {'mac': 'zz:bb:cc:dd:ee:ff'}, {}):
            self.bad([dict(ok, wake=w)], '"wake" must be')
        self.bad([dict(ok, name=f'D{i}') for i in range(D.MAX_DEVICES + 1)], f'the most is {D.MAX_DEVICES}')
        self.bad('{"devices": []}' + ' ' * D.MAX_FILE, 'too large')

    def test_the_problem_says_where(self):
        # the page names the file the server read and the device that is wrong, never a "line" it was not given
        ok = {'name': 'A', 'kind': 'pc', 'probe': 'tailscale', 'host': 'pc-a'}
        write(DEVICES, {'devices': [ok, dict(ok, name='B', host='pc b')]})
        with contextlib.redirect_stderr(io.StringIO()): v = D.view()
        self.assertEqual((v['file'], v['device']), (os.path.basename(DEVICES), 2), v)
        write(DEVICES, '{"devices": [')
        with contextlib.redirect_stderr(io.StringIO()): v = D.view()
        self.assertEqual((v['file'], v['device']), (os.path.basename(DEVICES), None), 'a file that is not JSON: no device number')
        reset(); v = D.view()
        self.assertEqual((v['problem'], v['file'], v['device']), (None, None, None))

    def test_kind_is_optional_and_names_are_trimmed(self):
        write(DEVICES, {'devices': [{'name': '  Box  ', 'probe': 'none'}]})
        self.assertEqual(D.config()[0], [{'name': 'Box', 'kind': 'other', 'probe': 'none', 'host': None, 'wake': False}])


class Probe(unittest.TestCase):
    def setUp(self): reset()

    def test_each_status(self):
        v = D.view(DESKTOP); d = by_name(v)
        self.assertEqual(d['Desk PC']['status'], 'online'); self.assertEqual(d['Desk PC']['label'], 'Online')
        self.assertEqual((d['Spare PC']['status'], d['Spare PC']['label'], d['Spare PC']['last_seen']), ('offline', 'Offline', '2026-11-15T21:04:00+00:00'))
        self.assertEqual(d['Phone']['status'], 'online', 'matched by the first part of DNSName, case folded')
        self.assertEqual((d['Tablet']['status'], d['Tablet']['label'], d['Tablet']['why']), ('unknown', "Can't tell", 'Tailscale did not say'))
        self.assertEqual((d['Laptop']['status'], d['Laptop']['why']), ('unknown', 'Not on the Tailscale list'))
        self.assertEqual((d['Old console']['status'], d['Old console']['why']), ('unknown', 'Argus does not check this one'))
        self.assertEqual((d['Shelf']['status'], d['Shelf']['label'], d['Shelf']['self']), ('desktop', 'Desktop mode', True))
        self.assertTrue(d['Desk PC']['wake']); self.assertFalse(d['Phone']['wake'])
        self.assertTrue(set(x['status'] for x in v['devices']) <= set(D.STATUSES))
        self.assertNotIn('aa:bb', json.dumps(v), 'the MAC address never leaves the server')
        self.assertTrue(v['checked'].endswith('+00:00'))

    def test_matched_by_host_name_too(self):
        write(DEVICES, {'devices': [{'name': 'A', 'probe': 'tailscale', 'host': 'pixel'}, {'name': 'B', 'probe': 'tailscale', 'host': 'pc-one'}]})
        self.assertEqual([x['status'] for x in D.view()['devices']], ['online', 'online'])

    def test_this_machine(self):
        self.assertEqual(by_name(D.view(GAME))['Shelf']['label'], 'Game mode')
        self.assertEqual(by_name(D.view(GAME))['Shelf']['status'], 'game')
        for m in (None, lambda: None, lambda: {'current': 'unknown', 'modes': []}):
            s = by_name(D.view(m))['Shelf']; self.assertEqual((s['status'], s['why']), ('online', 'This machine'))
        def boom(): raise RuntimeError('mode probe broke')
        self.assertEqual(by_name(D.view(boom))['Shelf']['status'], 'online')
        # this machine listed by its Tailscale name: online, from Self
        write(DEVICES, {'devices': [{'name': 'Me', 'probe': 'tailscale', 'host': 'this-server'}]})
        self.assertEqual((D.view()['devices'][0]['status'], D.view()['devices'][0]['why']), ('online', 'This machine'))

    def test_one_call_cached(self):
        D.view(); D.view(); D.view()
        self.assertEqual(len(CALLS), 1, 'one tailscale status for all devices, then the cache')
        D.status_doc(now=time.monotonic() + 31)
        self.assertEqual(len(CALLS), 2, 'asked again once the cache is 30 s old')

    def test_check_again_waits_five_seconds(self):
        t = time.monotonic(); D.status_doc(now=t)
        D.status_doc(now=t + 2, fresh=True); self.assertEqual(len(CALLS), 1, 'Check again within 5 s: the same answer')
        D.status_doc(now=t + 6, fresh=True); self.assertEqual(len(CALLS), 2, 'Check again after 5 s asks again')
        D.status_doc(now=t + 7); self.assertEqual(len(CALLS), 2)

    def cant_tell(self, why):
        v = D.view(DESKTOP); d = by_name(v)
        self.assertEqual(v['probe_problem'], why, 'the reason is said once, for the whole list')
        for n in ('Desk PC', 'Spare PC', 'Phone', 'Tablet', 'Laptop'):
            self.assertEqual((d[n]['status'], d[n]['label'], d[n]['why']), ('unknown', "Can't tell", None), f'{n}: no reason repeated on the row')
        self.assertEqual(d['Old console']['why'], 'Argus does not check this one', 'a device Argus never checks keeps its own reason')
        self.assertEqual(d['Shelf']['status'], 'desktop', 'this machine still knows itself')
        self.assertNotIn('offline', [x['status'] for x in v['devices']], 'never "offline" when the probe went wrong')

    def test_tailscale_fails(self):
        answer('fail'); self.cant_tell('Tailscale gave an error')

    def test_tailscale_not_json(self):
        answer('garbage'); self.cant_tell('Tailscale gave an answer Argus could not read')

    def test_tailscale_stopped(self):
        answer('stopped'); self.cant_tell('Tailscale is not running here (Stopped)')

    def test_tailscale_hangs(self):
        answer('hang'); old = D.TIMEOUT_S; D.TIMEOUT_S = 1
        try:
            t = time.monotonic(); self.cant_tell('Tailscale did not answer in time')
            self.assertLess(time.monotonic() - t, 10, 'the timeout holds')
        finally: D.TIMEOUT_S = old

    def test_a_runaway_answer_is_cut_while_reading(self):
        # the fake writes without end: the limit stops it as soon as it is passed, not at the timeout and not after reading it all
        answer('flood'); old = D.MAX_OUT, D.TIMEOUT_S; D.MAX_OUT, D.TIMEOUT_S = 256 * 1024, 20
        try:
            t = time.monotonic(); self.cant_tell('Tailscale gave an answer too large to read')
            self.assertLess(time.monotonic() - t, 10, 'stopped at the limit, long before the timeout')
        finally: D.MAX_OUT, D.TIMEOUT_S = old

    def test_an_answer_ok_is_ok_after_the_cap_code(self):
        self.assertEqual(by_name(D.view())['Desk PC']['status'], 'online')
        self.assertIsNone(D.view()['probe_problem'])

    def test_no_tailscale(self):
        D.command = lambda: [os.path.join(TMP, 'no-such-tailscale'), 'status', '--json']
        try: self.cant_tell('Tailscale is not installed on this machine')
        finally: D.command = fake_command

    def test_never_a_shell(self):
        self.assertEqual(REAL_COMMAND()[1:], ['status', '--json'])
        os.environ['ARGUS_TAILSCALE'] = '/opt/x/tailscale'
        try: self.assertEqual(REAL_COMMAND(), ['/opt/x/tailscale', 'status', '--json'])
        finally: os.environ.pop('ARGUS_TAILSCALE')
        src = open(os.path.join(R, 'server', 'devices.py'), encoding='utf-8').read()
        self.assertNotIn('shell=True', src); self.assertNotIn('os.system', src)

    def test_cache_seconds(self):
        for v, want in (('45', 45.0), ('-3', 0.0), ('9999', 300.0), ('soon', 30.0)):
            os.environ['ARGUS_DEVICES_CACHE'] = v; self.assertEqual(D.cache_s(), want)
        os.environ['ARGUS_DEVICES_CACHE'] = '30'


def node(dns, host, online=True, **kw): return dict({'DNSName': f'{dns}.example.ts.net.', 'HostName': host, 'Online': online}, **kw)

def status_of(peer_list, host, self_node=None):
    """The status one device with this host gets from a Tailscale answer listing these peers in this order."""
    doc = {'BackendState': 'Running', 'Self': self_node or node('this-server', 'this-server'),
           'Peer': {f'nodekey:{i}': n for i, n in enumerate(peer_list)}}
    r = D.one({'name': 'X', 'kind': 'pc', 'probe': 'tailscale', 'host': host, 'wake': False}, doc, None, None)
    return r['status'], r['why']


class Match(unittest.TestCase):
    """Which Tailscale machine a device is (review finding 1): DNS names first for every node, then host names; a name two
    nodes claim is "can't tell"; the answer never depends on the order Tailscale lists its peers."""
    def both_orders(self, peer_list, host, want, self_node=None):
        for order in (peer_list, peer_list[::-1]):
            self.assertEqual(status_of(order, host, self_node), want, f'{host} with peers in order {[n["HostName"] for n in order]}')

    def test_a_dns_name_wins_over_another_machines_host_name(self):
        # machine 1 is called "desk" by its DNS name; machine 2's HostName is also "desk" (its DNS name became "desk-1")
        one, two = node('desk', 'old-name', True), node('desk-1', 'desk', False)
        self.both_orders([one, two], 'desk', ('online', None))
        self.both_orders([one, two], 'desk-1', ('offline', None))

    def test_reinstalled_machine_with_dash_one(self):
        # the old entry keeps "pc" (offline), the reinstalled one is "pc-1" with HostName "pc": "pc" is the DNS name's
        old, new = node('pc', 'pc', False), node('pc-1', 'pc', True)
        self.both_orders([old, new], 'pc', ('offline', None))
        self.both_orders([old, new], 'pc-1', ('online', None))

    def test_two_phones_both_named_localhost(self):
        a1, a2 = node('phone-a', 'localhost', True), node('phone-b', 'localhost', False)
        self.both_orders([a1, a2], 'localhost', ('unknown', D.TWO))
        self.both_orders([a1, a2], 'phone-a', ('online', None))
        self.both_orders([a1, a2], 'phone-b', ('offline', None))

    def test_two_dns_names_alike_cant_tell(self):
        # Tailscale keeps DNS names unique; if an answer ever repeats one, neither machine is guessed
        self.both_orders([node('twin', 'a', True), node('twin', 'b', False)], 'twin', ('unknown', D.TWO))

    def test_a_peer_with_this_machines_name(self):
        # a peer whose HostName is this machine's DNS name: the DNS name (this machine) wins, in either order
        self.both_orders([node('other', 'this-server', False)], 'this-server', ('online', 'This machine'))

    def test_host_name_still_matches_when_no_dns_name_takes_it(self):
        self.both_orders([node('pixel', 'phone-one', True)], 'phone-one', ('online', None))


class Modes(unittest.TestCase):
    """This machine's row coloured and named as the mode pill does it (core.js modeHues())."""
    def row(self, mode):
        d = {'name': 'Me', 'kind': 'server', 'probe': 'self', 'host': None, 'wake': False}
        r = D.one(d, None, None, mode); return r['status'], r['label']

    def test_other_ids_and_labels(self):
        two = lambda cur, a, b: {'current': cur, 'modes': [a, b]}
        kde, steam = {'id': 'kde', 'label': 'KDE'}, {'id': 'steam', 'label': 'Steam'}
        self.assertEqual(self.row(two('kde', kde, steam)), ('desktop', 'KDE mode'), 'two other ids: the first is green')
        self.assertEqual(self.row(two('steam', kde, steam)), ('game', 'Steam mode'), 'the second is purple')
        g = {'id': 'game', 'label': 'Game Mode'}
        self.assertEqual(self.row(two('game', kde, g)), ('game', 'Game Mode'), 'never "Game Mode mode"')
        self.assertEqual(self.row(two('kde', kde, g)), ('desktop', 'KDE mode'), 'one other id gets the colour left over')
        self.assertEqual(self.row(two('kde', g, kde)), ('desktop', 'KDE mode'))
        d = {'id': 'desktop', 'label': 'Desktop'}
        self.assertEqual(self.row(two('steam', d, steam)), ('game', 'Steam mode'))
        self.assertEqual(self.row(two('desktop', d, steam)), ('desktop', 'Desktop mode'))
        self.assertEqual(self.row(two('x', kde, steam))[0], 'online', 'a current mode not in the list: Online')


class Fallback(unittest.TestCase):
    """When view() itself breaks: a plain message for the page and the real error in the log, once (finding 15a)."""
    def test_logged_once(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            for _ in range(3):
                try: raise KeyError('a bug in view')
                except KeyError as e: v = D.failed_view(e)
        self.assertEqual(err.getvalue().count('the device list failed'), 1, err.getvalue())
        self.assertIn('Traceback', err.getvalue()); self.assertIn("KeyError: 'a bug in view'", err.getvalue())
        self.assertEqual((v['set_up'], v['devices'], v['probe_problem']), (True, [], None))
        self.assertIn('could not read the device list', v['problem'])


class Route(unittest.TestCase):
    """GET api/devices on a real server."""
    @classmethod
    def setUpClass(cls):
        cls.srv = a.ThreadingHTTPServer(('127.0.0.1', 0), a.H)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
    @classmethod
    def tearDownClass(cls): cls.srv.shutdown(); cls.srv.server_close()
    def setUp(self): reset()

    def get(self, path, login=OWNER):
        c = http.client.HTTPConnection('127.0.0.1', self.srv.server_address[1], timeout=30)
        c.request('GET', '/argus/' + path, headers={'Host': '127.0.0.1', 'X-Forwarded-For': '192.0.2.20', 'Tailscale-User-Login': login})
        r = c.getresponse(); b = r.read(); c.close()
        return r.status, r.getheader('Cache-Control'), b

    def test_owner(self):
        code, cache, b = self.get('api/devices'); v = json.loads(b)
        self.assertEqual(code, 200); self.assertEqual(cache, 'no-store')
        self.assertEqual(len(v['devices']), 7); self.assertEqual(by_name(v)['Desk PC']['status'], 'online')
        self.assertNotIn(b'aa:bb', b); self.assertNotIn(b'pc-one', b, 'the host names stay on the server too')
        code, _, b = self.get('api/devices?fresh=1'); self.assertEqual(code, 200)
        self.assertEqual(len(CALLS), 1, 'fresh within 5 s of the last answer: not asked again')

    def test_no_file(self):
        reset(None); code, _, b = self.get('api/devices')
        self.assertEqual((code, json.loads(b)), (200, EMPTY))

    def test_a_bug_is_logged_not_hidden(self):
        real = D.view
        def broken(*a, **k): raise ZeroDivisionError('route test bug')
        D.view = broken; err = io.StringIO()
        try:
            with contextlib.redirect_stderr(err): code, _, b = self.get('api/devices')
        finally: D.view = real
        self.assertEqual(code, 200); self.assertIn('could not read the device list', json.loads(b)['problem'])
        self.assertIn('ZeroDivisionError: route test bug', err.getvalue())

    def test_learner(self):
        code, _, b = self.get('api/devices', LEARNER)
        self.assertEqual(code, 403); self.assertNotIn(b'Desk PC', b)
        self.assertEqual(CALLS, [], 'nothing asked for a learner')


if __name__ == '__main__':
    unittest.main()
