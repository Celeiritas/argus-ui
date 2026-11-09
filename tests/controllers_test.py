"""Leafy Controllers without a browser: the probe over fixture sysfs trees (docs/controllers.md). Runs on any OS, Windows included.

    python3 tests/controllers_test.py -v        (tests/run.sh runs it under "== controllers model")

tests/fixtures/controllers-sysfs/four holds an OpenPuck in SInput mode, a puck in Steam mode (with its keyboard and mouse
parts, which are not controllers), a Steam-virtual Xbox controller and a GameCube adapter without rumble; .../none has a
keyboard only. Real sysfs paths have colons (pci0000:00); the fixtures use dashes so a Windows checkout can hold them.

OldNames and OldNamesOnTheServer: until 4.33.0 the section was called Pads. For one release the old names (pads.json,
ARGUS_PADS, ARGUS_PADS_SYSROOT, the address <base>/pads) still work when the new ones are absent."""
import http.client, importlib.util, json, os, shutil, socket, subprocess, sys, tempfile, time, unittest
from unittest import mock

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location('leafy_controllers', os.path.join(R, 'plugins', 'controllers', 'plugin.py'))
ctl = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(ctl)
FX = os.path.join(R, 'tests', 'fixtures')
FOUR, NONE, REG = os.path.join(FX, 'controllers-sysfs', 'four'), os.path.join(FX, 'controllers-sysfs', 'none'), os.path.join(FX, 'controllers.json')

class Probe(unittest.TestCase):
    def setUp(self):
        self.s = ctl.scan(FOUR, REG)
        self.by = {c['name']: c for c in self.s['controllers']}

    def test_four_controllers_and_not_the_pucks_mouse_or_keyboard(self):
        self.assertTrue(self.s['ok'])
        self.assertEqual(sorted(self.by), ['Generic GameCube Adapter Port 1', 'Microsoft X-Box 360 pad 0', 'OpenPuck SInput', 'Valve Software Steam Controller'])

    def test_mode_from_usb_ids(self):
        self.assertEqual(self.by['OpenPuck SInput']['mode'], 'SInput')
        self.assertEqual(self.by['Valve Software Steam Controller']['mode'], 'Steam')
        self.assertEqual(self.by['Microsoft X-Box 360 pad 0']['mode'], 'Xbox 360')
        self.assertEqual(self.by['Generic GameCube Adapter Port 1']['mode'], 'Unknown (2dc8:3019)')
        self.assertFalse(self.by['Generic GameCube Adapter Port 1']['known_mode'])
        self.assertEqual(ctl.MODES['0f0d:0092'], 'Switch')

    def test_real_or_steam_virtual(self):
        self.assertEqual(self.by['Microsoft X-Box 360 pad 0']['kind'], 'steam-virtual')
        for n in ('OpenPuck SInput', 'Valve Software Steam Controller', 'Generic GameCube Adapter Port 1'):
            self.assertEqual(self.by[n]['kind'], 'real', n)
        # the Steam name on a real USB parent is a real controller (the OpenPuck in Xbox mode); another program's virtual one is 'virtual'
        d = dict(name='Microsoft X-Box 360 pad 3', sysfs='/devices/pci0000:00/usb1/1-1/input/input5', handlers=[])
        self.assertEqual(ctl.kind(d), 'real')
        self.assertEqual(ctl.kind(dict(d, name='Jelly controller', sysfs='/devices/virtual/input/input9')), 'virtual')

    def test_rumble(self):
        self.assertTrue(self.by['OpenPuck SInput']['rumble'])
        self.assertTrue(self.by['Microsoft X-Box 360 pad 0']['rumble'])
        self.assertFalse(self.by['Generic GameCube Adapter Port 1']['rumble'])       # capabilities/ff is 0

    def test_slots_from_registry(self):
        self.assertEqual([(c['slot'], c['label']) for c in self.s['controllers']],
                         [('P1', 'Main controller'), ('P2', ''), ('Retro', 'GameCube controller'), (None, '')])   # registry order, then the rest
        self.assertIsNone(self.by['Microsoft X-Box 360 pad 0']['slot'], 'a virtual controller never takes a slot, even when its ids match')

    def test_counts_line_and_hint(self):
        self.assertEqual((self.s['connected'], self.s['virtual']), (3, 1))
        self.assertEqual(ctl.line(self.s), '3 connected · 1 Steam virtual')
        self.assertEqual(self.s['wake_hint'], 'Test hint: press the Home button.')
        self.assertEqual(self.s['notice'], '', 'no old name in use: nothing to say')

    def test_no_controllers(self):
        s = ctl.scan(NONE, REG)
        self.assertTrue(s['ok']); self.assertEqual(s['controllers'], [])
        self.assertEqual(ctl.line(s), 'No controllers connected')

    def test_not_linux(self):
        s = ctl.scan(os.path.join(FX, 'no-such-root'), REG)
        self.assertFalse(s['ok']); self.assertIn("Can't read", s['problem'])
        self.assertEqual(ctl.line(s), "Can't read controllers here")

    def test_the_words_say_controller_never_pad(self):
        # "pad" only stays inside names the kernel gives ("Microsoft X-Box 360 pad 0"): a Pad is a synth sound, not a game controller
        said = [ctl.WAKE_HINT, ctl.line(self.s), ctl.line(ctl.scan(NONE, REG)), ctl.line(ctl.scan(os.path.join(FX, 'no-such-root'), REG)),
                ctl.scan(os.path.join(FX, 'no-such-root'), REG)['problem']]
        for text in said: self.assertNotRegex(text, r'(?i)\bpads?\b', text)
        self.assertNotIn('pads', self.s)

class Registry(unittest.TestCase):
    def setUp(self): self.tmp = tempfile.mkdtemp(prefix='controllers-test-')
    def tearDown(self): shutil.rmtree(self.tmp, ignore_errors=True)
    def reg(self, text, name='controllers.json'):
        p = os.path.join(self.tmp, name)
        with open(p, 'w', encoding='utf-8') as f: f.write(text)
        return p

    def test_no_registry_still_lists_controllers(self):
        s = ctl.scan(FOUR, os.path.join(self.tmp, 'missing.json'))
        self.assertEqual(len(s['controllers']), 4); self.assertEqual(s['problem'], '')
        self.assertTrue(all(c['slot'] is None for c in s['controllers']))
        self.assertEqual(s['wake_hint'], ctl.WAKE_HINT)

    def test_broken_registry_is_named_not_fatal(self):
        s = ctl.scan(FOUR, self.reg('{not json'))
        self.assertEqual(len(s['controllers']), 4); self.assertIn('controllers.json could not be read', s['problem'])
        s = ctl.scan(FOUR, self.reg('[1, 2]'))
        self.assertIn('controllers.json could not be read', s['problem'])
        s = ctl.scan(FOUR, self.reg('{not json', 'pads.json'))
        self.assertIn('pads.json could not be read', s['problem'], 'the problem names the file that was read, old name or new')

    def test_own_mode_names_and_bad_entries(self):
        s = ctl.scan(FOUR, self.reg(json.dumps({'modes': {'2dc8:3019': 'GameCube adapter'}, 'slots': ['x', {'match': ['puck']}, {'slot': 'P4', 'match': ['', 5]}]})))
        by = {c['name']: c for c in s['controllers']}
        self.assertEqual(by['Generic GameCube Adapter Port 1']['mode'], 'GameCube adapter')
        self.assertTrue(all(c['slot'] is None for c in s['controllers']), 'entries without a slot or a usable match are ignored')
        s = ctl.scan(FOUR, self.reg(json.dumps({'slots': [{'slot': 'P3', 'match': {'x': 1}}, {'slot': 'P1', 'match': 'puck'}]})))
        by = {c['name']: c['slot'] for c in s['controllers']}
        self.assertEqual([n for n, v in by.items() if v == 'P1'], ['OpenPuck SInput'], 'a string match is one pattern, never letter by letter')
        self.assertNotIn('P3', by.values(), 'a match that is neither a list nor a string is ignored')

    def test_example_file_parses_and_has_placeholders_only(self):
        r, problem = ctl.registry(os.path.join(R, 'docs', 'controllers.example.json'))
        self.assertEqual(problem, ''); self.assertTrue(r['slots'])
        for e in r['slots']: self.assertTrue(e['slot'] and e['match'])
        self.assertEqual([e['label'] for e in r['slots']], ['{{CONTROLLER_1}}', '{{CONTROLLER_2}}', '{{CONTROLLER_3}}', '{{CONTROLLER_4}}'])

class Parsing(unittest.TestCase):
    def setUp(self): self.tmp = tempfile.mkdtemp(prefix='controllers-test-')
    def tearDown(self): shutil.rmtree(self.tmp, ignore_errors=True)
    def root(self, devices):
        os.makedirs(os.path.join(self.tmp, 'proc', 'bus', 'input'))
        with open(os.path.join(self.tmp, 'proc', 'bus', 'input', 'devices'), 'w') as f: f.write(devices)
        return self.tmp

    def test_ff_from_proc_when_sysfs_is_missing(self):
        root = self.root('I: Bus=0003 Vendor=045e Product=028e Version=0110\nN: Name="Microsoft X-Box 360 pad"\nP: Phys=usb-x-1.3/input0\n'
                         'S: Sysfs=/devices/pci/usb1/input/input7\nH: Handlers=event7 js0\nB: EV=20001b\nB: FF=107030000 0\n\n'
                         'I: Bus=0003 Vendor=1234 Product=abcd Version=0110\nN: Name="Plain Gamepad"\nP: Phys=usb-x-1.5/input0\n'
                         'S: Sysfs=/devices/pci/usb1/input/input8\nH: Handlers=js1\nB: EV=1b\nB: FF=107030000 0\n')
        s = ctl.scan(root, os.path.join(self.tmp, 'none.json'))
        by = {c['name']: c for c in s['controllers']}
        self.assertTrue(by['Microsoft X-Box 360 pad']['rumble'], "the 'B: FF=' line counts when capabilities/ff can't be read")
        self.assertEqual(by['Microsoft X-Box 360 pad']['mode'], 'Xbox 360')
        self.assertFalse(by['Plain Gamepad']['rumble'], 'no event node: nothing can send rumble')

    def test_controller_without_joydev_needs_axes_and_a_controller_name(self):
        root = self.root('I: Bus=0003 Vendor=2e8a Product=10c6\nN: Name="SInput Gamepad"\nS: Sysfs=/devices/a/input/input1\nH: Handlers=event1\nB: EV=1b\n\n'
                         'I: Bus=0003 Vendor=054c Product=0ce6\nN: Name="Sony DualSense Touchpad"\nS: Sysfs=/devices/a/input/input2\nH: Handlers=event2 mouse0\nB: EV=b\n\n'
                         'I: Bus=0003 Vendor=dead Product=beef\nN: Name="Some Tablet"\nS: Sysfs=/devices/a/input/input3\nH: Handlers=event3\nB: EV=b\n')
        self.assertEqual([c['name'] for c in ctl.scan(root, os.path.join(self.tmp, 'none.json'))['controllers']], ['SInput Gamepad'])

    def test_sysfs_path_cannot_leave_sysroot(self):
        self.assertIsNone(ctl._sys_path(self.tmp, '/../../etc'))

    def test_api(self):
        with mock.patch.dict(os.environ, {'ARGUS_CONTROLLERS_SYSROOT': FOUR, 'ARGUS_CONTROLLERS': REG}):
            code, r = ctl.get('list', {}, None); self.assertEqual((code, len(r['controllers']), r['notice']), (200, 4, ''))
            self.assertEqual(ctl.get('status', {}, None), (200, {'line': '3 connected · 1 Steam virtual'}))
            self.assertEqual(ctl.get('nope', {}, None)[0], 404)

class OldNames(unittest.TestCase):
    """4.33.0 renamed Pads to Controllers. For one release an old name is read when its new one is absent; the new one wins."""
    def setUp(self): self.tmp = tempfile.mkdtemp(prefix='controllers-test-')
    def tearDown(self): shutil.rmtree(self.tmp, ignore_errors=True)
    def put(self, name, label='Main controller'):
        with open(REG, encoding='utf-8') as f: text = f.read().replace('Main controller', label)
        with open(os.path.join(self.tmp, name), 'w', encoding='utf-8') as f: f.write(text)
        return os.path.join(self.tmp, name)

    def test_env_old_names_are_read_when_the_new_ones_are_absent(self):
        old = self.put('elsewhere.json', 'From the old setting')
        self.assertEqual(ctl.where({'ARGUS_PADS_SYSROOT': NONE, 'ARGUS_PADS': old}, self.tmp), (NONE, old, ['ARGUS_PADS_SYSROOT', 'ARGUS_PADS']))
        self.assertEqual(ctl.where({'ARGUS_PADS': old}, self.tmp), ('/', old, ['ARGUS_PADS']))
        self.assertEqual(ctl.where({'ARGUS_PADS_SYSROOT': NONE}, self.tmp), (NONE, os.path.join(self.tmp, 'controllers.json'), ['ARGUS_PADS_SYSROOT']))

    def test_env_new_names_win(self):
        new, old = self.put('new.json'), self.put('old.json')
        env = {'ARGUS_CONTROLLERS_SYSROOT': FOUR, 'ARGUS_PADS_SYSROOT': NONE, 'ARGUS_CONTROLLERS': new, 'ARGUS_PADS': old}
        self.assertEqual(ctl.where(env, self.tmp), (FOUR, new, []))
        self.assertEqual(ctl.where(dict(env, ARGUS_CONTROLLERS='', ARGUS_CONTROLLERS_SYSROOT=''), self.tmp), (NONE, old, ['ARGUS_PADS_SYSROOT', 'ARGUS_PADS']),
                         'an empty new setting counts as absent')
        self.assertEqual(ctl.where({}, self.tmp), ('/', os.path.join(self.tmp, 'controllers.json'), []), 'nothing set: the defaults, new names')

    def test_file_pads_json_is_read_only_while_controllers_json_is_absent(self):
        new, old = os.path.join(self.tmp, 'controllers.json'), os.path.join(self.tmp, 'pads.json')
        self.assertEqual(ctl.where({}, self.tmp)[1:], (new, []), 'neither file: the new name, nothing old in use')
        self.put('pads.json')
        self.assertEqual(ctl.where({}, self.tmp)[1:], (old, ['pads.json']))
        self.put('controllers.json')
        self.assertEqual(ctl.where({}, self.tmp)[1:], (new, []), 'both files: the new one wins, the old one is ignored')
        self.assertEqual(ctl.where({'ARGUS_CONTROLLERS': os.path.join(self.tmp, 'x.json')}, self.tmp)[1:], (os.path.join(self.tmp, 'x.json'), []),
                         'a path from the environment is used as written')

    def test_default_folder_is_the_config_folder(self):
        with mock.patch.dict(os.environ, {'HOME': self.tmp, 'USERPROFILE': self.tmp}):
            self.assertEqual(ctl.where({})[1], os.path.join(self.tmp, '.config', 'argus-ui', 'controllers.json'))

    def test_old_file_still_gives_slots_and_the_page_is_told(self):
        self.put('pads.json', 'From pads.json')
        s = ctl.scan(*ctl.where({'ARGUS_PADS_SYSROOT': FOUR}, self.tmp))
        self.assertEqual([(c['slot'], c['label']) for c in s['controllers']][:2], [('P1', 'From pads.json'), ('P2', '')])
        self.assertEqual(s['notice'], 'Old names still in use: ARGUS_PADS_SYSROOT (now ARGUS_CONTROLLERS_SYSROOT), pads.json (now controllers.json). '
                                      'This is the last release that reads old names.')
        self.put('controllers.json', 'From controllers.json')          # the copy the owner makes: it counts on the next request
        s = ctl.scan(*ctl.where({'ARGUS_CONTROLLERS_SYSROOT': FOUR}, self.tmp))
        self.assertEqual((s['controllers'][0]['label'], s['notice']), ('From controllers.json', ''))
        self.assertEqual(ctl.notice(['pads.json']), 'Old name still in use: pads.json (now controllers.json). This is the last release that reads old names.')

    def test_api_through_the_old_environment_names(self):
        old = self.put('elsewhere.json', 'From the old setting')
        env = {k: v for k, v in os.environ.items() if not k.startswith('ARGUS_')}
        with mock.patch.dict(os.environ, dict(env, ARGUS_PADS_SYSROOT=FOUR, ARGUS_PADS=old), clear=True):
            code, r = ctl.get('list', {}, None)
            self.assertEqual((code, r['controllers'][0]['label']), (200, 'From the old setting'))
            self.assertIn('ARGUS_PADS (now ARGUS_CONTROLLERS)', r['notice'])
            self.assertEqual(ctl.get('status', {}, None), (200, {'line': '3 connected · 1 Steam virtual'}), "Home's line stays the same: no nagging there")

class OldNamesOnTheServer(unittest.TestCase):
    """The real server (server/argus_ui.py in its own process, on a free port) started the way an install untouched since
    4.32 runs: the slot map still named pads.json in ~/.config/argus-ui/, and only the old ARGUS_PADS_SYSROOT set.
    HOME and USERPROFILE point at a temporary folder; nothing outside it is touched."""
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='controllers-server-test-')
        home = os.path.join(cls.tmp, 'home'); cls.conf = os.path.join(home, '.config', 'argus-ui'); os.makedirs(cls.conf)
        shutil.copyfile(REG, os.path.join(cls.conf, 'pads.json'))
        bundled, static = os.path.join(cls.tmp, 'bundled'), os.path.join(cls.tmp, 'static'); os.makedirs(static)
        shutil.copytree(os.path.join(R, 'plugins', 'controllers'), os.path.join(bundled, 'controllers'), ignore=shutil.ignore_patterns('__pycache__'))
        with open(os.path.join(static, 'theme.json'), 'w') as f: f.write('{}')
        with socket.socket() as s: s.bind(('127.0.0.1', 0)); cls.port = s.getsockname()[1]
        env = {k: v for k, v in os.environ.items() if not k.startswith('ARGUS_')}
        env.update(HOME=home, USERPROFILE=home, ARGUS_BIND='127.0.0.1', ARGUS_PORT=str(cls.port), ARGUS_STATIC=static, ARGUS_BUNDLED=bundled,
                   ARGUS_PADS_SYSROOT=FOUR)
        cls.log = open(os.path.join(cls.tmp, 'server.log'), 'w')
        cls.proc = subprocess.Popen([sys.executable, os.path.join(R, 'server', 'argus_ui.py')], env=env, stdout=cls.log, stderr=cls.log)
        for _ in range(150):
            try: socket.create_connection(('127.0.0.1', cls.port), timeout=1).close(); break
            except OSError: time.sleep(.1)
        else:
            cls.tearDownClass()
            raise RuntimeError('the server did not start; its log was in ' + cls.tmp)

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        try: cls.proc.wait(10)
        except subprocess.TimeoutExpired: cls.proc.kill(); cls.proc.wait(10)
        cls.log.close(); shutil.rmtree(cls.tmp, ignore_errors=True)

    def get(self, path):
        # a raw request, nothing followed: the status, the headers and the body exactly as the server sent them
        c = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
        c.request('GET', '/' + path, headers={'Host': '127.0.0.1'})
        r = c.getresponse(); body = r.read(); c.close()
        return r.status, {k.lower(): v for k, v in r.getheaders()}, body

    def test_old_file_and_old_setting_still_give_the_slots(self):
        code, _, body = self.get('api/controllers/list'); d = json.loads(body)
        self.assertEqual(code, 200)
        self.assertEqual([c['slot'] for c in d['controllers']], ['P1', 'P2', 'Retro', None], 'four controllers through ARGUS_PADS_SYSROOT, slots from pads.json')
        self.assertIn('ARGUS_PADS_SYSROOT (now ARGUS_CONTROLLERS_SYSROOT)', d['notice']); self.assertIn('pads.json (now controllers.json)', d['notice'])
        self.assertEqual(json.loads(self.get('api/controllers/status')[2])['line'], '3 connected · 1 Steam virtual')

    def test_copying_the_file_to_its_new_name_needs_no_restart(self):
        new = os.path.join(self.conf, 'controllers.json')
        with open(REG, encoding='utf-8') as f: text = f.read().replace('Main controller', 'From controllers.json')
        with open(new, 'w', encoding='utf-8') as f: f.write(text)
        try:
            d = json.loads(self.get('api/controllers/list')[2])
            self.assertEqual(d['controllers'][0]['label'], 'From controllers.json')
            self.assertNotIn('pads.json', d['notice'])
        finally: os.remove(new)

    def test_old_address_lands_on_the_new_section(self):
        # relative on purpose: right at <base>/pads whether the server is mounted at /, at /argus/, or behind a proxy that strips the prefix
        for path, want in (('pads', 'controllers'), ('argus/pads', 'controllers'), ('pads/', '../controllers'),
                           ('argus/pads/anything', '../controllers'), ('pads?from=bookmark', 'controllers?from=bookmark')):
            code, headers, body = self.get(path)
            self.assertEqual((code, headers.get('location'), body), (301, want, b''), path)
            self.assertEqual(headers.get('cache-control'), 'no-store', 'browsers must not remember the move: the id pads is free again after this release')

    def test_old_api_address_is_gone(self):
        self.assertEqual(self.get('api/pads/list')[0], 404, 'only the section address moved with a redirect; the page script asks the new api')

    def test_server_log_names_the_plugin_by_its_new_id(self):
        self.log.flush()
        with open(self.log.name) as f: text = f.read()
        self.assertRegex(text, r'loaded server plugin controllers [\d.]+ \(bundled\)')

if __name__ == '__main__':
    unittest.main()
