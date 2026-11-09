"""Leafy Pads without a browser: the probe over fixture sysfs trees (docs/pads.md). Runs on any OS, Windows included.

    python3 tests/pads_test.py -v        (tests/run.sh runs it under "== pads model")

tests/fixtures/pads-sysfs/four holds an OpenPuck in SInput mode, a puck in Steam mode (with its keyboard and mouse
parts, which are not pads), a Steam-virtual Xbox pad and a GameCube adapter without rumble; .../none has a keyboard only.
Real sysfs paths have colons (pci0000:00); the fixtures use dashes so a Windows checkout can hold them."""
import importlib.util, json, os, shutil, tempfile, unittest

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location('leafy_pads', os.path.join(R, 'plugins', 'pads', 'plugin.py'))
pads = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(pads)
FX = os.path.join(R, 'tests', 'fixtures')
FOUR, NONE, REG = os.path.join(FX, 'pads-sysfs', 'four'), os.path.join(FX, 'pads-sysfs', 'none'), os.path.join(FX, 'pads.json')

class Probe(unittest.TestCase):
    def setUp(self):
        self.s = pads.scan(FOUR, REG)
        self.by = {p['name']: p for p in self.s['pads']}

    def test_four_pads_and_not_the_pucks_mouse_or_keyboard(self):
        self.assertTrue(self.s['ok'])
        self.assertEqual(sorted(self.by), ['Generic GameCube Adapter Port 1', 'Microsoft X-Box 360 pad 0', 'OpenPuck SInput', 'Valve Software Steam Controller'])

    def test_mode_from_usb_ids(self):
        self.assertEqual(self.by['OpenPuck SInput']['mode'], 'SInput')
        self.assertEqual(self.by['Valve Software Steam Controller']['mode'], 'Steam')
        self.assertEqual(self.by['Microsoft X-Box 360 pad 0']['mode'], 'Xbox 360')
        self.assertEqual(self.by['Generic GameCube Adapter Port 1']['mode'], 'Unknown (2dc8:3019)')
        self.assertFalse(self.by['Generic GameCube Adapter Port 1']['known_mode'])
        self.assertEqual(pads.MODES['0f0d:0092'], 'Switch')

    def test_real_or_steam_virtual(self):
        self.assertEqual(self.by['Microsoft X-Box 360 pad 0']['kind'], 'steam-virtual')
        for n in ('OpenPuck SInput', 'Valve Software Steam Controller', 'Generic GameCube Adapter Port 1'):
            self.assertEqual(self.by[n]['kind'], 'real', n)
        # the Steam name on a real USB parent is a real pad (the OpenPuck in Xbox mode); another program's virtual pad is 'virtual'
        d = dict(name='Microsoft X-Box 360 pad 3', sysfs='/devices/pci0000:00/usb1/1-1/input/input5', handlers=[])
        self.assertEqual(pads.kind(d), 'real')
        self.assertEqual(pads.kind(dict(d, name='Jelly pad', sysfs='/devices/virtual/input/input9')), 'virtual')

    def test_rumble(self):
        self.assertTrue(self.by['OpenPuck SInput']['rumble'])
        self.assertTrue(self.by['Microsoft X-Box 360 pad 0']['rumble'])
        self.assertFalse(self.by['Generic GameCube Adapter Port 1']['rumble'])       # capabilities/ff is 0

    def test_slots_from_registry(self):
        self.assertEqual([(p['slot'], p['label']) for p in self.s['pads']],
                         [('P1', 'Main pad'), ('P2', ''), ('Retro', 'GameCube pad'), (None, '')])   # registry order, then the rest
        self.assertIsNone(self.by['Microsoft X-Box 360 pad 0']['slot'], 'a virtual pad never takes a slot, even when its ids match')

    def test_counts_line_and_hint(self):
        self.assertEqual((self.s['connected'], self.s['virtual']), (3, 1))
        self.assertEqual(pads.line(self.s), '3 connected · 1 Steam virtual')
        self.assertEqual(self.s['wake_hint'], 'Test hint: press the Home button.')

    def test_no_pads(self):
        s = pads.scan(NONE, REG)
        self.assertTrue(s['ok']); self.assertEqual(s['pads'], [])
        self.assertEqual(pads.line(s), 'No pads connected')

    def test_not_linux(self):
        s = pads.scan(os.path.join(FX, 'no-such-root'), REG)
        self.assertFalse(s['ok']); self.assertIn("Can't read", s['problem'])
        self.assertEqual(pads.line(s), "Can't read pads here")

class Registry(unittest.TestCase):
    def setUp(self): self.tmp = tempfile.mkdtemp(prefix='pads-test-')
    def tearDown(self): shutil.rmtree(self.tmp, ignore_errors=True)
    def reg(self, text):
        p = os.path.join(self.tmp, 'pads.json')
        with open(p, 'w', encoding='utf-8') as f: f.write(text)
        return p

    def test_no_registry_still_lists_pads(self):
        s = pads.scan(FOUR, os.path.join(self.tmp, 'missing.json'))
        self.assertEqual(len(s['pads']), 4); self.assertEqual(s['problem'], '')
        self.assertTrue(all(p['slot'] is None for p in s['pads']))
        self.assertEqual(s['wake_hint'], pads.WAKE_HINT)

    def test_broken_registry_is_named_not_fatal(self):
        s = pads.scan(FOUR, self.reg('{not json'))
        self.assertEqual(len(s['pads']), 4); self.assertIn('pads.json could not be read', s['problem'])
        s = pads.scan(FOUR, self.reg('[1, 2]'))
        self.assertIn('pads.json could not be read', s['problem'])

    def test_own_mode_names_and_bad_entries(self):
        s = pads.scan(FOUR, self.reg(json.dumps({'modes': {'2dc8:3019': 'GameCube adapter'}, 'slots': ['x', {'match': ['puck']}, {'slot': 'P4', 'match': ['', 5]}]})))
        by = {p['name']: p for p in s['pads']}
        self.assertEqual(by['Generic GameCube Adapter Port 1']['mode'], 'GameCube adapter')
        self.assertTrue(all(p['slot'] is None for p in s['pads']), 'entries without a slot or a usable match are ignored')

    def test_example_file_parses_and_has_placeholders_only(self):
        r, problem = pads.registry(os.path.join(R, 'docs', 'pads.example.json'))
        self.assertEqual(problem, ''); self.assertTrue(r['slots'])
        for e in r['slots']: self.assertTrue(e['slot'] and e['match'])

class Parsing(unittest.TestCase):
    def setUp(self): self.tmp = tempfile.mkdtemp(prefix='pads-test-')
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
        s = pads.scan(root, os.path.join(self.tmp, 'none.json'))
        by = {p['name']: p for p in s['pads']}
        self.assertTrue(by['Microsoft X-Box 360 pad']['rumble'], "the 'B: FF=' line counts when capabilities/ff can't be read")
        self.assertEqual(by['Microsoft X-Box 360 pad']['mode'], 'Xbox 360')
        self.assertFalse(by['Plain Gamepad']['rumble'], 'no event node: nothing can send rumble')

    def test_pad_without_joydev_needs_axes_and_a_pad_name(self):
        root = self.root('I: Bus=0003 Vendor=2e8a Product=10c6\nN: Name="SInput Gamepad"\nS: Sysfs=/devices/a/input/input1\nH: Handlers=event1\nB: EV=1b\n\n'
                         'I: Bus=0003 Vendor=054c Product=0ce6\nN: Name="Sony DualSense Touchpad"\nS: Sysfs=/devices/a/input/input2\nH: Handlers=event2 mouse0\nB: EV=b\n\n'
                         'I: Bus=0003 Vendor=dead Product=beef\nN: Name="Some Tablet"\nS: Sysfs=/devices/a/input/input3\nH: Handlers=event3\nB: EV=b\n')
        self.assertEqual([p['name'] for p in pads.scan(root, os.path.join(self.tmp, 'none.json'))['pads']], ['SInput Gamepad'])

    def test_sysfs_path_cannot_leave_sysroot(self):
        self.assertIsNone(pads._sys_path(self.tmp, '/../../etc'))

    def test_api(self):
        old = pads.SYSROOT, pads.REGISTRY
        try:
            pads.SYSROOT, pads.REGISTRY = FOUR, REG
            code, r = pads.get('list', {}, None); self.assertEqual((code, len(r['pads'])), (200, 4))
            self.assertEqual(pads.get('status', {}, None), (200, {'line': '3 connected · 1 Steam virtual'}))
            self.assertEqual(pads.get('nope', {}, None)[0], 404)
        finally: pads.SYSROOT, pads.REGISTRY = old

if __name__ == '__main__':
    unittest.main()
