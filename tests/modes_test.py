"""Desktop / Game mode (server/modes.py, docs/modes.md): the config file, the probe and POST api/mode. No browser.

    python tests/modes_test.py -v        (tests/run.sh runs it under "== Desktop / Game mode")

  * the file: a good one (unit names with and without ".service"), none (off, silent), bad JSON (off, one stderr line, not
    repeated), the wrong number of modes, bad ids and labels, bad unit names (a leading "-", spaces, other unit kinds, a
    template), the same unit twice; read again when it changes
  * the probe, with a stand-in for systemctl: Game, Desktop, both and neither (unknown), switching because a switch unit
    runs (not once it has run and stays active), switching because this server started one (until the target shows up,
    its switch unit fails, or 120 s pass; a probe racing the switch never wipes the note), a failed switch reported, ONE
    call for all four units, cached for 2 s, and a systemctl that fails
  * after a restart or a new file: a switch unit that ended well a moment ago counts as a switch under way, once
  * switch(): one at a time, the start is `start --no-block <switch unit>`, a start that fails, a start that times out
    (it may still run: the note stays), a switch unit that stays active (refused)
  * the route, end to end on a real server in this process against the fake systemctl (tests/fixtures/fake_systemctl.py):
    the owner switches, a learner gets 403 and no "modes" in her state, off is 404, an unknown id 400, an unknown mode 409,
    already there 200, a second press while it switches 409 (also two at once: one start), and only switch units are ever
    started (the host rule)
The page side is tests/modes.test.js. Who is asking comes from the real check on Linux; without /proc (Windows, macOS) the
lookup is stood in for, as in tests/gate_test.py."""
import contextlib, http.client, importlib.util, io, json, os, shutil, subprocess, sys, tempfile, threading, time, unittest

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HAS_PROC = os.path.isfile('/proc/net/tcp')
ME = os.getuid() if hasattr(os, 'getuid') else 4242
TMP = tempfile.mkdtemp(prefix='argus-modes-test-')
HOME = os.path.join(TMP, 'home'); CONF = os.path.join(HOME, '.config', 'argus-ui')
STATIC, FX, STATE = os.path.join(TMP, 'static'), os.path.join(TMP, 'fx'), os.path.join(TMP, 'state')
PEOPLE, MODES, REALM = os.path.join(CONF, 'people.json'), os.path.join(TMP, 'modes.json'), os.path.join(TMP, 'realm.json')
UNITS, STARTS = os.path.join(FX, 'units.json'), os.path.join(FX, 'starts.log')
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
    if os.path.exists(path): shutil.move(path, f'{path}.set-aside-{os.urandom(4).hex()}')

put(os.path.join(STATIC, 'theme.json'), {'title': 'LeafyGrove', 'agents': [{'key': 'argus', 'name': 'Argus'}, {'key': 'hermes', 'name': 'Hermes'}]})
put(os.path.join(STATIC, 'index.html'), '<!doctype html><title>the page</title><script>const STATE = /*STATE*/null;</script>')
put(os.path.join(STATIC, 'VERSION'), '9.9.9')
put(REALM, {'SERVER': 'Box'})                      # the server's name in the messages
shutil.copy(os.path.join(R, 'tests', 'fixtures', 'fake_systemctl.py'), FX)
put(os.path.join(FX, 'fake_journal.py'), 'print("")\n')
def wrapper(name, script):
    if os.name == 'nt':
        put(os.path.join(FX, name + '.cmd'), f'@"{sys.executable}" "{os.path.join(FX, script)}" %*\n'); return os.path.join(FX, name + '.cmd')
    put(os.path.join(FX, name), f'#!/bin/sh\nexec "{sys.executable}" "{os.path.join(FX, script)}" "$@"\n'); os.chmod(os.path.join(FX, name), 0o755)
    return os.path.join(FX, name)

# the fixture's generic names (tests/fixtures/modes.json): Desktop first, then Game
FIXTURE = json.loads(read(os.path.join(R, 'tests', 'fixtures', 'modes.json')))
DESK, GAME, TO_DESK, TO_GAME = 'fake-desktop-shell.service', 'fake-game-session.service', 'fake-to-desktop.service', 'fake-to-game.service'
def units(desk='active', game='inactive', to_desk='inactive', to_game='inactive'):
    put(UNITS, {'fake-desktop-shell': {'ActiveState': desk}, 'fake-game-session': {'ActiveState': game},
                'fake-to-desktop': {'ActiveState': to_desk}, 'fake-to-game': {'ActiveState': to_game}})
units()

os.environ.update(HOME=HOME, USERPROFILE=HOME, ARGUS_STATIC=STATIC, ARGUS_PLUGINS=os.path.join(CONF, 'plugins'),
                  ARGUS_BUNDLED=os.path.join(TMP, 'bundled'), ARGUS_LINKS=os.path.join(CONF, 'links.json'),
                  ARGUS_REGISTRY=os.path.join(TMP, 'agents'), ARGUS_ALERTS=os.path.join(TMP, 'alerts'),
                  ARGUS_PEOPLE_LAST_GOOD=os.path.join(STATE, 'people.last-good.json'), ARGUS_KNOWN=os.path.join(STATE, 'known.json'),
                  ARGUS_SERVE_UID=str(ME), ARGUS_DEV='1', ARGUS_WATCH='0', LEAFY_REALM=REALM, ARGUS_MODES=MODES,
                  ARGUS_SYSTEMCTL=wrapper('systemctl', 'fake_systemctl.py'), ARGUS_JOURNALCTL=wrapper('journalctl', 'fake_journal.py'))
for k in ('ARGUS_BIND', 'ARGUS_WEATHER', 'ARGUS_PEOPLE'): os.environ.pop(k, None)
_spec = importlib.util.spec_from_file_location('argus_ui_modes_test', os.path.join(R, 'server', 'argus_ui.py'))
a = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(a)
M = a.modes                                         # the very module the server uses
if not HAS_PROC:                                    # no /proc: stand in for the lookup (as tests/gate_test.py does)
    a.identity.connection_uid = lambda peer, ours, proc='/proc', our_inode=None: ME
print(f'\n  [identity path: {"real /proc lookup" if HAS_PROC else "simulated (no /proc on this machine)"}]', file=sys.stderr)

OWNER, LEARNER = 'owner@example.com', 'learner@example.com'
put(PEOPLE, {'people': [{'id': 'owner-one', 'name': 'Owner One', 'role': 'owner', 'logins': [OWNER]},
                        {'id': 'learner-two', 'name': 'Learner Two', 'role': 'learner', 'logins': [LEARNER]}]})

def doc(**change):
    """The fixture's two modes, with some fields of either changed: doc(m0={'id': 'X'})."""
    ms = [dict(m) for m in FIXTURE['modes']]
    for i in (0, 1): ms[i].update(change.get(f'm{i}', {}))
    return {'modes': ms}

def reset(seed=False):
    # seed=False: no look for a switch that ended a moment ago (that is tested on its own, in Restart)
    with M._probe_lock: M._pending.clear(); M._seed[0] = seed
    M.clear_cache()

PROPS = ('-p', 'Id', '-p', 'ActiveState', '-p', 'SubState', '-p', 'InactiveEnterTimestampMonotonic')

class FakeSC:
    """systemctl --user for the probe: states by unit, each an ActiveState or a dict of properties; answers
    `show A B C D -p Id -p ActiveState ...` as systemctl does: one block per unit, the asked properties, a blank line between."""
    def __init__(self, **by): self.set(**{'desk': 'active', **by}); self.calls = []; self.fail = None
    def __call__(self, *args):
        self.calls.append(args)
        if self.fail: raise self.fail
        props = [args[i + 1] for i, x in enumerate(args[:-1]) if x == '-p']
        def prop(u, k):
            s = self.states.get(u, 'inactive'); s = s if isinstance(s, dict) else {'ActiveState': s}
            return u if k == 'Id' else str(s.get(k, 'inactive' if k == 'ActiveState' else ''))
        return '\n\n'.join('\n'.join(f'{k}={prop(u, k)}' for k in props) for u in args if u.endswith('.service')) + '\n'
    def set(self, **by):
        names = {'desk': DESK, 'game': GAME, 'to_desk': TO_DESK, 'to_game': TO_GAME}
        self.states = {names[k]: v for k, v in by.items()}

def stopped(at, state='inactive'):
    """A switch unit that stopped (went inactive, or failed) at `at` seconds on the monotonic clock, as systemd gives it."""
    return {'ActiveState': state, 'SubState': 'dead' if state == 'inactive' else 'failed', 'InactiveEnterTimestampMonotonic': int(at * 1e6)}


class Config(unittest.TestCase):
    def setUp(self): os.environ['ARGUS_MODES'] = MODES; reset()
    def tearDown(self): os.environ['ARGUS_MODES'] = MODES

    def test_good_file(self):
        write(MODES, FIXTURE)
        ms = M.config()
        self.assertEqual([m['id'] for m in ms], ['desktop', 'game'], 'in the order of the file')
        self.assertEqual([(m['active_unit'], m['switch_unit']) for m in ms], [(DESK, TO_DESK), (GAME, TO_GAME)],
                         'unit names with and without ".service" both end in ".service"')
        self.assertEqual(M.load(os.path.join(R, 'tests', 'fixtures', 'modes.json')), ms)

    def test_missing_file_is_off_and_silent(self):
        os.environ['ARGUS_MODES'] = os.path.join(TMP, 'no-such-modes.json')
        err = io.StringIO()
        with contextlib.redirect_stderr(err): self.assertIsNone(M.config()); self.assertIsNone(M.config())
        self.assertEqual(err.getvalue(), '')
        self.assertIsNone(M.probe(FakeSC(), 'Box'), 'no file: no pill')
        self.assertEqual(M.switch('game', FakeSC(), lambda *a: (True, ''), 'Box')[0], 404)

    def test_bad_json_is_off_with_one_line(self):
        write(MODES, '{"modes": [')
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertIsNone(M.config()); self.assertIsNone(M.config()); self.assertIsNone(M.probe(FakeSC(), 'Box'))
        lines = err.getvalue().splitlines()
        self.assertEqual(len(lines), 1, 'one line, not one per request')
        self.assertTrue(lines[0].startswith('argus-ui: modes.json: ') and lines[0].endswith('the Desktop / Game pill is off'), lines)

    def test_read_again_when_it_changes(self):
        write(MODES, FIXTURE); self.assertEqual(M.config()[1]['label'], 'Game')
        write(MODES, doc(m1={'label': 'Couch'})); self.assertEqual(M.config()[1]['label'], 'Couch')
        with contextlib.redirect_stderr(io.StringIO()):
            write(MODES, {'modes': []}); self.assertIsNone(M.config(), 'now bad: off')
        write(MODES, FIXTURE); self.assertEqual(len(M.config()), 2, 'good again: on')

    def test_wrong_count(self):
        for ms in ([], FIXTURE['modes'][:1], FIXTURE['modes'] + [dict(FIXTURE['modes'][0], id='third')]):
            with self.assertRaisesRegex(ValueError, 'exactly two modes'): M.parse({'modes': ms})
        for bad in (None, [], 'modes', {'modes': 'two'}, {'mode': FIXTURE['modes']}):
            with self.assertRaises(ValueError): M.parse(bad)
        with self.assertRaisesRegex(ValueError, 'not an object'): M.parse({'modes': ['desktop', 'game']})

    def test_ids(self):
        for bad in ('Game', '1game', '-game', 'game_mode', 'game mode', 'g' * 17, '', None, 7):
            with self.assertRaisesRegex(ValueError, 'mode 2: the id', msg=repr(bad)): M.parse(doc(m1={'id': bad}))
        self.assertEqual(M.parse(doc(m1={'id': 'g' + 'a1-' * 5}))[1]['id'], 'ga1-a1-a1-a1-a1-', '16 characters are fine')
        with self.assertRaisesRegex(ValueError, 'same id'): M.parse(doc(m1={'id': 'desktop'}))

    def test_labels(self):
        for bad in ('', '   ', 'L' * 17, 'Two\nlines', None, 3):
            with self.assertRaisesRegex(ValueError, 'the label', msg=repr(bad)): M.parse(doc(m0={'label': bad}))
        self.assertEqual(M.parse(doc(m0={'label': '  Sofa  '}))[0]['label'], 'Sofa', 'spaces around it are dropped')
        self.assertEqual(M.parse(doc(m0={'label': 'L' * 16}))[0]['label'], 'L' * 16)

    def test_unit_names(self):
        for bad, why in (('-fake-to-game', 'starts with "-"'), ('--now', 'starts with "-"'), ('fake to game', 'characters'),
                         ('fake;reboot', 'characters'), ('fake/../x', 'characters'), ('fake$(x)', 'characters'),
                         ('fake.target', 'not a service'), ('fake.timer', 'not a service'), ('fake@.service', 'template'),
                         ('fake@', 'template'), ('', 'missing'), (None, 'missing'), (['fake'], 'missing'), ('x' * 241, 'characters')):
            with self.assertRaisesRegex(ValueError, why, msg=repr(bad)): M.parse(doc(m1={'switch_unit': bad}))
        for v, want in (('fake-to-game', TO_GAME), (TO_GAME, TO_GAME), ('fake@one_two', 'fake@one_two.service'), ('a.b:c_d', 'a.b:c_d.service')):
            self.assertEqual(M.unit_name(v), want)
        with self.assertRaisesRegex(ValueError, 'must all differ'): M.parse(doc(m1={'switch_unit': 'fake-desktop-shell'}))
        with self.assertRaisesRegex(ValueError, 'must all differ'): M.parse(doc(m0={'switch_unit': 'fake-to-game.service'}))

    def test_too_large(self):
        write(MODES, json.dumps(FIXTURE) + ' ' * (64 * 1024))
        with self.assertRaisesRegex(ValueError, 'too large'): M.load(MODES)


class Probe(unittest.TestCase):
    def setUp(self):
        os.environ['ARGUS_MODES'] = MODES; write(MODES, FIXTURE); M.config(); reset()

    def look(self, sc, now): return M.probe(sc, 'Box', now=now)

    def test_desktop_and_game(self):
        sc = FakeSC()
        p = self.look(sc, 100)
        self.assertEqual(p, {'current': 'desktop', 'switching': None, 'failed': None, 'name': 'Box',
                             'modes': [{'id': 'desktop', 'label': 'Desktop'}, {'id': 'game', 'label': 'Game'}]}, 'only ids and labels: no unit names')
        sc.set(game='active'); self.assertEqual(self.look(sc, 110)['current'], 'game')
        sc.set(game='reloading'); self.assertEqual(self.look(sc, 120)['current'], 'game')

    def test_both_or_neither_is_unknown(self):
        sc = FakeSC(); sc.set(desk='active', game='active'); self.assertEqual(self.look(sc, 100)['current'], 'unknown')
        sc.set(); self.assertEqual(self.look(sc, 110)['current'], 'unknown')
        sc.set(desk='failed', game='activating'); self.assertEqual(self.look(sc, 120)['current'], 'unknown', 'starting is not in it yet')

    def test_switching_by_unit(self):
        sc = FakeSC()
        for state in ('activating', 'active'):
            sc.set(desk='active', to_game=state); p = self.look(sc, 100 + len(state))
            self.assertEqual((p['current'], p['switching']), ('desktop', 'game'), state)
        sc.set(desk='active', to_game='inactive'); self.assertIsNone(self.look(sc, 200)['switching'])
        sc.set(desk='active', to_game='failed'); self.assertIsNone(self.look(sc, 210)['switching'], 'a failed switch is not switching')

    def test_a_switch_unit_that_stays_active_is_done(self):
        # RemainAfterExit=yes: a oneshot stays "active" (SubState exited) once it has run. That is not a switch under way.
        sc = FakeSC(); sc.set(game='active', to_game={'ActiveState': 'active', 'SubState': 'exited'})
        p = self.look(sc, 100); self.assertEqual((p['current'], p['switching']), ('game', None))
        sc.set(desk='active', to_game={'ActiveState': 'active', 'SubState': 'start'}); M.clear_cache()
        self.assertEqual(self.look(sc, 101)['switching'], 'game', 'still running its commands: switching')

    def test_one_call_for_all_four_cached_two_seconds(self):
        sc = FakeSC()
        self.look(sc, 100); self.look(sc, 101); self.look(sc, 101.9)
        self.assertEqual(sc.calls, [('show', DESK, TO_DESK, GAME, TO_GAME) + PROPS])
        self.look(sc, 102.1); self.assertEqual(len(sc.calls), 2, 'asked again after 2 s')
        M.clear_cache(); self.look(sc, 102.2); self.assertEqual(len(sc.calls), 3, 'and after the cache is cleared (a POST)')

    def test_systemctl_fails_or_hangs(self):
        sc = FakeSC()
        for e in (subprocess.TimeoutExpired('systemctl', 20), OSError('no systemctl'), RuntimeError('odd')):
            sc.fail = e; M.clear_cache(); p = self.look(sc, 100)
            self.assertEqual((p['current'], p['switching']), ('unknown', None), repr(e))

    def test_show_read_by_id_when_blocks_are_missing(self):
        us = [DESK, TO_DESK, GAME, TO_GAME]
        self.assertEqual(M.parse_show(f'Id={GAME}\nActiveState=active\n\nId={DESK}\nActiveState=inactive\n', us),
                         {GAME: {'Id': GAME, 'ActiveState': 'active'}, DESK: {'Id': DESK, 'ActiveState': 'inactive'}})
        self.assertEqual(M.parse_show('', us), {})
        self.assertEqual(M.ended({'InactiveEnterTimestampMonotonic': '1500250000'}), 1500.25)
        for v in ('0', '', 'n/a', None): self.assertIsNone(M.ended({'InactiveEnterTimestampMonotonic': v}), repr(v))

    def test_pending_switch(self):
        sc, starts = FakeSC(), []
        code, ok, msg = M.switch('game', sc, lambda *a: (starts.append(a), (True, ''))[1], 'Box', now=1000)
        self.assertEqual((code, ok, starts), (200, True, [('start', '--no-block', TO_GAME)]))
        p = self.look(sc, 1001)            # the switch unit has not shown up yet (a --no-block start), the desktop still runs
        self.assertEqual((p['current'], p['switching']), ('desktop', 'game'), 'switching: this server started it')
        p = self.look(sc, 1000 + 119); self.assertEqual(p['switching'], 'game', 'for up to 120 s')
        p = self.look(sc, 1000 + 121); self.assertIsNone(p['switching'], 'then it gives up')
        self.assertEqual(M._pending, {})

    def test_pending_ends_when_the_target_shows_up(self):
        sc = FakeSC()
        M.switch('game', sc, lambda *a: (True, ''), 'Box', now=1000)
        sc.set(game='active'); p = self.look(sc, 1003)
        self.assertEqual((p['current'], p['switching']), ('game', None)); self.assertEqual(M._pending, {})
        sc.set(desk='active'); self.assertIsNone(self.look(sc, 1006)['switching'], 'gone back to Desktop later: not switching')

    def test_pending_newer_than_now_stays(self):
        # a page's probe read its clock, then the switch wrote its note a moment later: the note is not wiped as "too old"
        sc = FakeSC()
        with M._probe_lock: M._pending.update(to='game', at=1005)
        p = self.look(sc, 1000)
        self.assertEqual((p['current'], p['switching']), ('desktop', 'game'))
        self.assertEqual(M._pending, {'to': 'game', 'at': 1005}, 'the note is kept')

    def test_no_gap_around_the_start(self):
        # the note is written before the start: a page that asks while systemctl starts the unit already sees "switching"
        sc, seen = FakeSC(), []
        def start(*a): seen.append(M.probe(sc, 'Box', now=1000.5)['switching']); return True, ''
        self.assertEqual(M.switch('game', sc, start, 'Box', now=1000)[:2], (200, True))
        self.assertEqual(seen, ['game'])
        self.assertEqual(self.look(sc, 1001)['switching'], 'game')

    def test_pending_while_neither_runs(self):
        sc = FakeSC()
        M.switch('game', sc, lambda *a: (True, ''), 'Box', now=1000)
        sc.set(); p = self.look(sc, 1003)            # the desktop stopped, the game is not up yet: the dark seconds
        self.assertEqual((p['current'], p['switching']), ('unknown', 'game'))

    def test_a_failed_switch_is_reported(self):
        sc = FakeSC(to_game=stopped(900, 'failed'))   # an old failure, from before this switch
        M.switch('game', sc, lambda *a: (True, ''), 'Box', now=1000)
        p = self.look(sc, 1001); self.assertEqual((p['switching'], p['failed']), ('game', None), 'an old failure does not end a new switch')
        sc.set(desk='active', to_game='activating'); M.clear_cache(); self.assertEqual(self.look(sc, 1002)['switching'], 'game')
        sc.set(desk='active', to_game=stopped(1004, 'failed')); M.clear_cache()
        p = self.look(sc, 1005)
        self.assertEqual((p['current'], p['switching'], p['failed']), ('desktop', None, 'game'), 'it failed: not switching any more, and the pill says so')
        self.assertEqual(M._pending, {}, 'the note is gone at once, not after 120 s')
        M.clear_cache(); self.assertEqual(self.look(sc, 1004 + 119)['failed'], 'game', 'said for up to 120 s')
        M.clear_cache(); self.assertIsNone(self.look(sc, 1004 + 121)['failed'], 'then it is history')
        sc.set(game='active', to_game=stopped(1004, 'failed')); M.clear_cache()
        self.assertIsNone(self.look(sc, 1006)['failed'], 'the host got into that mode after all: nothing to report')
        sc.set(desk='active', to_game=stopped(1004)); M.clear_cache()
        self.assertIsNone(self.look(sc, 1006)['failed'], 'a switch that ended well is no failure')


class Restart(unittest.TestCase):
    """The switch note lives in memory. Started again (a deploy) or given a new file mid-switch, Argus looks once for a switch
    unit that ended well a moment ago into a mode the host is not in yet: that switch is still under way."""
    def setUp(self):
        os.environ['ARGUS_MODES'] = MODES; write(MODES, FIXTURE); M.config(); reset(seed=True)

    def look(self, sc, now): return M.probe(sc, 'Box', now=now)

    def test_a_switch_that_just_ended(self):
        sc = FakeSC(desk='inactive', to_game=stopped(1000))   # the dark seconds: the desktop stopped, the game not up yet
        p = self.look(sc, 1010)
        self.assertEqual((p['current'], p['switching']), ('unknown', 'game'))
        self.assertEqual(M._pending, {'to': 'game', 'at': 1000}, 'counted from when the switch unit ended')
        starts = []
        self.assertEqual(M.switch('desktop', sc, lambda *a: (starts.append(a), (True, ''))[1], 'Box', now=1011)[0], 409, 'a second press is refused')
        self.assertEqual(starts, [])
        sc.set(game='active', to_game=stopped(1000)); M.clear_cache()
        self.assertEqual((self.look(sc, 1015)['current'], self.look(sc, 1015)['switching']), ('game', None), 'and it ends when the game shows up')

    def test_only_once_and_only_recent(self):
        sc = FakeSC(to_game=stopped(1000))
        self.assertEqual(self.look(sc, 1000 + 121)['switching'], None, 'ended more than 120 s ago: history')
        reset(seed=True); sc.set(desk='active', to_game=stopped(1000, 'failed'))
        p = self.look(sc, 1010); self.assertEqual((p['switching'], p['failed']), (None, 'game'), 'a failed one is a failure, not a switch')
        reset(seed=True); sc.set(game='active', to_game=stopped(1000))
        self.assertIsNone(self.look(sc, 1010)['switching'], 'already in that mode: done')
        reset(seed=True); sc.fail = OSError('no systemctl'); self.look(sc, 1010); sc.fail = None
        self.assertTrue(M._seed[0], 'no answer from systemctl: it looks again next time')
        sc.set(desk='active'); M.clear_cache(); self.look(sc, 1012)
        self.assertFalse(M._seed[0], 'it looked')
        sc.set(desk='active', to_game=stopped(1013)); M.clear_cache()
        self.assertIsNone(self.look(sc, 1014)['switching'], 'only once: a switch it did not start is not noted later')

    def test_a_new_file_looks_again(self):
        self.look(FakeSC(), 1000); self.assertFalse(M._seed[0])
        write(MODES, doc(m1={'label': 'Couch'})); M.config()
        self.assertTrue(M._seed[0])


class Switch(unittest.TestCase):
    def setUp(self):
        os.environ['ARGUS_MODES'] = MODES; write(MODES, FIXTURE); M.config(); reset()

    def test_answers(self):
        sc, ok = FakeSC(), lambda *a: (True, '')
        self.assertEqual(M.switch('tv', sc, ok, 'Box')[:2], (400, False))
        self.assertEqual(M.switch(None, sc, ok, 'Box')[:2], (400, False))
        self.assertEqual(M.switch(['game'], sc, ok, 'Box')[:2], (400, False))
        self.assertEqual(M.switch('desktop', sc, ok, 'Box', now=10), (200, True, 'Already in Desktop mode.'))
        sc.set(desk='active', game='active')
        self.assertEqual(M.switch('game', sc, ok, 'Box', now=20), (409, False, "Can't tell which mode Box is in right now. Try again in a minute."))
        self.assertEqual(M.switch('game', sc, ok, 'The server', now=30)[2], "Can't tell which mode the server is in right now. Try again in a minute.")
        sc.set(desk='active', to_game='active')
        self.assertEqual(M.switch('desktop', sc, ok, 'Box', now=40), (409, False, 'Box is already switching to Game mode.'))

    def test_a_switch_unit_that_stays_active_is_refused(self):
        # RemainAfterExit=yes: the unit is still active from its last run, so a start would do nothing and the pill would
        # say "switching" for two minutes. Refused, with the reason; nothing started.
        sc, starts = FakeSC(), []
        sc.set(desk='active', to_game={'ActiveState': 'active', 'SubState': 'exited'})
        self.assertEqual(M.switch('game', sc, lambda *a: (starts.append(a), (True, ''))[1], 'Box', now=10),
                         (409, False, "Box can't switch to Game mode: its switch unit stays active after it runs (RemainAfterExit=yes), so a start would do nothing."))
        self.assertEqual((starts, M._pending), ([], {}))

    def test_start_fails_or_hangs(self):
        sc = FakeSC()
        self.assertEqual(M.switch('game', sc, lambda *a: (False, 'Failed to start fake-to-game.service: Unit not found.\nmore'), 'Box', now=10),
                         (200, False, 'Box could not start the switch to Game mode: Failed to start fake-to-game.service: Unit not found.'))
        self.assertEqual(M._pending, {}, 'nothing pending after a failed start')
        self.assertEqual(M.switch('game', sc, lambda *a: (False, ''), 'Box', now=15)[2], 'Box could not start the switch to Game mode: systemctl gave no reason')
        def oops(*a): raise OSError('no systemctl')
        self.assertEqual(M.switch('game', sc, oops, 'Box', now=18)[1:], (False, 'Box could not start the switch to Game mode: systemctl could not be run'))
        self.assertEqual(M._pending, {})

    def test_start_that_times_out_may_still_run(self):
        # with --no-block, no answer in 20 s means a busy manager: the start may still have been queued, so the note stays
        # and a second press is refused until the mode shows up or 120 s pass
        sc, starts = FakeSC(), []
        def hang(*a): starts.append(a); raise subprocess.TimeoutExpired('systemctl', 20)
        self.assertEqual(M.switch('game', sc, hang, 'Box', now=20),
                         (200, False, 'Box may be switching to Game mode: systemctl did not answer in time. Check the TV before you try again.'))
        self.assertEqual(M._pending, {'to': 'game', 'at': 20})
        self.assertEqual(self.look_switching(sc, 25), 'game')
        self.assertEqual(M.switch('game', sc, hang, 'Box', now=30), (409, False, 'Box is already switching to Game mode.'))
        self.assertEqual(len(starts), 1, 'the second press started nothing')
        self.assertIsNone(self.look_switching(sc, 141), 'after 120 s it gives up')

    def look_switching(self, sc, now): return M.probe(sc, 'Box', now=now)['switching']

    def test_one_at_a_time(self):
        sc, starts, gate = FakeSC(), [], threading.Event()
        def slow(*a):
            starts.append(a); gate.wait(5); return True, ''
        out = []
        t = threading.Thread(target=lambda: out.append(M.switch('game', sc, slow, 'Box')))
        t.start()
        for _ in range(200):
            if starts: break
            time.sleep(0.01)
        t2 = threading.Thread(target=lambda: out.append(M.switch('game', sc, slow, 'Box')))
        t2.start(); time.sleep(0.2)
        self.assertEqual(len(starts), 1, 'the second press waits for the first')
        gate.set(); t.join(5); t2.join(5)
        self.assertEqual(len(starts), 1, 'and then finds a switch under way')
        self.assertEqual(sorted(o[0] for o in out), [200, 409])


class Route(unittest.TestCase):
    """POST api/mode and the state, on a real server against the fake systemctl."""
    @classmethod
    def setUpClass(cls):
        a.load_server_plugins()
        cls.srv = a.ThreadingHTTPServer(('127.0.0.1', 0), a.H)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown(); cls.srv.server_close()
        if os.path.exists(STARTS):
            started = [l.split() for l in read(STARTS).splitlines() if l.strip()]
            # the host rule: only ever a switch unit, never a session unit itself, and never waiting for it
            assert started and all(l[0] == 'start' and '--no-block' in l and DESK not in l and GAME not in l for l in started), started

    def setUp(self):
        os.environ['ARGUS_MODES'] = MODES; write(MODES, FIXTURE); units(); reset()
        self.before = self.starts()

    def starts(self):
        try: return read(STARTS).splitlines()
        except FileNotFoundError: return []
    def new_starts(self): return self.starts()[len(self.before):]

    def req(self, verb, path, login=OWNER, body=None):
        c = http.client.HTTPConnection('127.0.0.1', self.srv.server_address[1], timeout=30)
        h = {'Host': '127.0.0.1', 'X-Forwarded-For': '192.0.2.20', 'Tailscale-User-Login': login}
        data = None
        if verb == 'POST': h['Content-Type'] = 'application/json'; data = json.dumps(body)
        c.request(verb, '/argus/' + path, body=data, headers=h)
        r = c.getresponse(); b = r.read(); c.close()
        return r.status, json.loads(b)
    def mode(self, to, login=OWNER): return self.req('POST', 'api/mode', login, {'to': to})
    def state(self, login=OWNER): return self.req('GET', 'api/state', login)[1]

    def test_owner_switches(self):
        self.assertEqual(self.state()['modes'], {'current': 'desktop', 'switching': None, 'failed': None, 'name': 'Box',
                                                 'modes': [{'id': 'desktop', 'label': 'Desktop'}, {'id': 'game', 'label': 'Game'}]})
        code, d = self.mode('game')
        self.assertEqual((code, d), (200, {'ok': True, 'msg': 'Switching to Game mode. The TV goes dark for a few seconds.'}))
        self.assertEqual(self.new_starts(), [f'start --no-block {TO_GAME}'], 'the switch unit, without waiting for it, and nothing else')
        self.assertEqual(self.state()['modes']['switching'], 'game')
        code, d = self.mode('game')
        self.assertEqual((code, d), (409, {'ok': False, 'msg': 'Box is already switching to Game mode.'}), 'a second press while it switches')
        self.assertEqual(self.mode('desktop')[0], 409, 'also the other way')
        self.assertEqual(len(self.new_starts()), 1, 'still one start')
        units(desk='inactive', game='active'); M.clear_cache()            # the switch is done
        self.assertEqual((self.state()['modes']['current'], self.state()['modes']['switching']), ('game', None))
        self.assertEqual(self.mode('game'), (200, {'ok': True, 'msg': 'Already in Game mode.'}))
        self.assertEqual(len(self.new_starts()), 1, 'already there: nothing started')

    def test_two_presses_at_once_start_one_switch(self):
        out = []
        ts = [threading.Thread(target=lambda: out.append(self.mode('game')[0])) for _ in range(2)]
        for t in ts: t.start()
        for t in ts: t.join(30)
        self.assertEqual(sorted(out), [200, 409]); self.assertEqual(len(self.new_starts()), 1)

    def test_learner(self):
        code, d = self.mode('game', LEARNER)
        self.assertEqual(code, 403); self.assertFalse(d.get('ok', False))
        self.assertEqual(self.new_starts(), [], 'nothing started for a learner')
        s = self.state(LEARNER)
        self.assertEqual(s['role'], 'learner'); self.assertNotIn('modes', s, "a learner's state has no modes")
        self.assertNotIn('fake-', json.dumps(s))
        self.assertNotIn('modes', a.state_for({'role': 'learner', 'person': 'learner-two', 'name': 'Learner Two'}))
        self.assertIn('modes', a.state_for({'role': 'owner', 'person': 'owner-one', 'name': 'Owner One'}))

    def test_off(self):
        os.environ['ARGUS_MODES'] = os.path.join(TMP, 'no-such-modes.json')
        self.assertNotIn('modes', self.state(), 'no file: no pill')
        self.assertEqual(self.mode('game'), (404, {'ok': False, 'msg': 'Desktop / Game mode is not set up on this server.'}))
        bad = os.path.join(TMP, 'bad-modes.json'); write(bad, '{"modes": [{"id": "game"}]}'); os.environ['ARGUS_MODES'] = bad
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertNotIn('modes', self.state(), 'a bad file: no pill, and the state still comes')
            self.assertEqual(self.mode('game')[0], 404)
        self.assertEqual(self.new_starts(), [])

    def test_unknown_id(self):
        for body in ({'to': 'tv'}, {'to': ''}, {'to': 3}, {}):
            code, d = self.req('POST', 'api/mode', OWNER, body)
            self.assertEqual((code, d['ok']), (400, False), body)
        self.assertEqual(self.new_starts(), [])

    def test_unknown_mode(self):
        for desk, game in (('active', 'active'), ('inactive', 'inactive')):
            units(desk=desk, game=game); M.clear_cache()
            self.assertEqual(self.state()['modes']['current'], 'unknown')
            self.assertEqual(self.mode('game'), (409, {'ok': False, 'msg': "Can't tell which mode Box is in right now. Try again in a minute."}))
        self.assertEqual(self.new_starts(), [])

    def test_start_fails(self):
        write(MODES, doc(m1={'switch_unit': 'fake-not-there'}))          # the fake systemctl cannot start a unit it does not know
        code, d = self.mode('game')
        self.assertEqual((code, d['ok']), (200, False)); self.assertTrue(d['msg'].startswith('Box could not start the switch to Game mode: '), d)
        self.assertIsNone(self.state()['modes']['switching'], 'nothing pending after a failed start')


if __name__ == '__main__':
    unittest.main()
