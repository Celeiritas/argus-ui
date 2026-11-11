"""Argus notices a program that RUNS but cannot DO ITS JOB (server/watch.py, server/notify.py, docs/checks.md). No browser.

    python3 tests/watch_works_test.py -v        (tests/run.sh runs it under "== watch works")

The real incident is the test case: a USB media drive dropped out and came back under a new device name; two containers kept the old,
dead mount (their mountinfo line carries `shutdown`, or points at a device that is gone), every file read inside failed with
Input/output error, while the units read "active" and one app's own health check said healthy. The mount tables are canned
(tests/fixtures/watch/*.mountinfo); the container runtime is tests/fixtures/fake_podman.py. Nothing real is touched."""
import json, os, shutil, socket, subprocess, sys, tempfile, time, unittest, urllib.request

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(R, 'server'))
import notify, watch
FX = os.path.join(R, 'tests', 'fixtures')
WFX = os.path.join(FX, 'watch')
def table(name):
    with open(os.path.join(WFX, name + '.mountinfo'), encoding='utf-8') as f: return f.read()


def jload(path):
    with open(path, encoding='utf-8') as f: return json.load(f)
def jdump(obj, path):
    with open(path, 'w', encoding='utf-8') as f: json.dump(obj, f)
def put(path, text):
    with open(path, 'w', encoding='utf-8', newline='') as f: f.write(text)


class FakeEnv(watch.Env):
    """A world with a mount table, containers, http answers and units; every call is written down in .calls."""
    def __init__(self, host='host-good', inside=None, http=None, active=True, frozen=(), reads=(), restart_fixes=None):
        super().__init__()
        self.host, self.inside, self.answers, self.up, self.frozen, self.reads = host, inside or {}, http or {}, active, set(frozen), set(reads)
        self.calls, self.restarts, self.t, self.restart_fixes = [], [], time.time(), restart_fixes
    def now(self): return self.t
    def sleep(self, s): self.t += s
    def mountinfo(self): return None if self.host is None else table(self.host)
    def is_active(self, unit): return self.up
    def is_frozen(self, unit): return unit in self.frozen
    def restart(self, unit):
        self.restarts.append(unit)
        if self.restart_fixes is not None: self.restart_fixes(self)
        return True, 'ok'
    def run(self, argv, timeout=6):
        self.calls.append(argv)
        name = argv[argv.index('exec') + 1]; cmd = argv[argv.index('exec') + 2:]
        if name not in self.inside: return 125, b''
        if cmd[:2] == ['cat', '/proc/self/mountinfo']: return 0, table(self.inside[name]).encode()
        if cmd[-1] in self.reads: return 0, b'data'
        return 1, b''
    def http(self, url, timeout=6): return self.answers.get(url)
    def file_reads(self): return [c for c in self.calls if 'head' in c or 'ls' in c]


JELLY = dict(id='jellyfin', title='Jellyfin', job='mnemosyne-jellyfin', unit='jellyfin', mount='/mnt/media', url='mnemosyne',
             container=dict(name='jellyfin', file='/media/Shows/test.mp4'), http='http://127.0.0.1:8096/health',
             fix=dict(restart=['jellyfin', 'audiobookshelf'], say='Jellyfin and Audiobookshelf'))
ABS = dict(id='audiobookshelf', title='Audiobookshelf', job='mnemosyne-audiobookshelf', unit='audiobookshelf', mount='/mnt/media',
           container=dict(name='audiobookshelf', dir='/audiobooks'), fix=dict(restart=['audiobookshelf']))
QBT = dict(id='qbittorrent', title='qBittorrent', job='hermes-qbittorrent', unit='qbittorrent', mount='/mnt/media',
           container=dict(name='qbittorrent'), http='http://127.0.0.1:8080/')        # no file, no fix
DRIVE = dict(id='media-drive', title='The media drive', job='mnemosyne-media-drive', mount='/mnt/media')


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='watch-test-')
        self.saved = {m: dict(vars(m)) for m in (watch, notify)}
        watch.CHECKS = os.path.join(self.tmp, 'checks.json'); watch.AUTOFIX = os.path.join(self.tmp, 'auto-fix.json')
        watch.STATEFILE = os.path.join(self.tmp, 'watch.json')
        os.environ['ARGUS_EVENTS'] = os.path.join(self.tmp, 'events.jsonl')
        watch.RESULTS.clear(); watch.PREV.clear(); watch.BAD.clear()
        self.events = []; notify.SINKS[:] = [self.events.append]
    def tearDown(self):
        for m, d in self.saved.items(): vars(m).update(d)
        os.environ.pop('ARGUS_EVENTS', None)
        shutil.rmtree(self.tmp, ignore_errors=True)
    def checks(self, *cs):
        with open(watch.CHECKS, 'w', encoding='utf-8') as f: json.dump({'checks': list(cs)}, f)
    def autofix(self, *ids):
        with open(watch.AUTOFIX, 'w', encoding='utf-8') as f: json.dump({'ids': list(ids)}, f)
    def result(self, id_): return {r['id']: r for r in watch.snapshot()}[id_]
    def kinds(self): return [e['kind'] for e in self.events]


class MountTable(unittest.TestCase):
    def test_status(self):
        for name, want in (('host-good', 'ok'), ('host-missing', 'missing'), ('host-readonly', 'readonly'), ('host-dropped', 'dropped')):
            self.assertEqual(watch.mount_status(watch.parse_mountinfo(table(name)), '/mnt/media'), want, name)

    def test_escaped_spaces_and_trailing_slash(self):
        t = watch.parse_mountinfo(table('host-good'))
        self.assertEqual(watch.mount_status(t, '/mnt/with space/'), 'ok')

    def test_dead_copy_by_the_word_shutdown(self):
        host = watch.parse_mountinfo(table('host-good'))
        self.assertEqual([r['source'] for r in watch.dead_copies(watch.parse_mountinfo(table('container-dead-shutdown')), host)], ['/dev/sdb1'])

    def test_dead_copy_by_a_device_that_is_gone(self):
        host = watch.parse_mountinfo(table('host-good'))
        self.assertEqual([r['dev'] for r in watch.dead_copies(watch.parse_mountinfo(table('container-dead-gone')), host)], ['8:17'])

    def test_a_good_container_has_none(self):
        host = watch.parse_mountinfo(table('host-good'))
        self.assertEqual(watch.dead_copies(watch.parse_mountinfo(table('container-good')), host), [])   # its overlay, proc and tmpfs lines are not drives


class Incident(Base):
    """The real one: drive replugged, containers dead, units active, health check 200."""
    def env(self, **kw):
        kw.setdefault('inside', {'jellyfin': 'container-dead-shutdown', 'audiobookshelf': 'container-dead-gone', 'qbittorrent': 'container-dead-gone'})
        kw.setdefault('http', {'http://127.0.0.1:8096/health': 200, 'http://127.0.0.1:8080/': 200})
        return FakeEnv(**kw)

    def test_runs_but_cannot_do_its_job(self):
        self.checks(JELLY, ABS, QBT); e = self.env(reads={'/media/Shows/test.mp4'})
        watch.step(e)
        j = self.result('jellyfin')
        self.assertIs(j['works'], False); self.assertEqual(j['code'], 'dead-copy'); self.assertEqual(j['reason'], 'cannot read its drive')
        self.assertTrue(e.is_active('jellyfin'))               # the unit really reads active ...
        self.assertEqual(e.http('http://127.0.0.1:8096/health'), 200)   # ... and the app's own health check says healthy
        self.assertEqual(e.file_reads(), [], 'no file may be read inside a container that holds a dead copy')

    def test_one_event_per_change_with_plain_words(self):
        self.checks(JELLY, ABS, QBT); e = self.env()
        watch.step(e); watch.step(e); watch.step(e)
        self.assertEqual(len(self.events), 3, 'one for each program, not one per round')
        by = {x['subject']: x for x in self.events}
        self.assertEqual(by['jellyfin']['title'], 'Jellyfin runs, but cannot read its drive')
        self.assertEqual(by['jellyfin']['kind'], 'needs-yes')
        self.assertIn('Jellyfin and Audiobookshelf', by['jellyfin']['body'])
        self.assertEqual(by['qbittorrent']['kind'], 'broke')          # no fix named: it can only tell
        self.assertIn('no automatic fix', by['qbittorrent']['body'])
        for x in self.events:
            self.assertEqual(sorted(x), ['at', 'body', 'id', 'kind', 'level', 'subject', 'title', 'url'])
            self.assertTrue(x['id'] and x['at'])
        self.assertEqual(len({x['id'] for x in self.events}), 3)

    def test_nothing_restarts_without_auto_fix_json(self):
        self.checks(JELLY, ABS); e = self.env()
        for _ in range(3): watch.step(e)
        self.assertEqual(e.restarts, [])
        self.assertEqual(self.kinds(), ['needs-yes', 'needs-yes'])

    def test_an_empty_auto_fix_file_changes_nothing(self):
        self.checks(JELLY); self.autofix(); e = self.env(); watch.step(e)
        self.assertEqual(e.restarts, []); self.assertEqual(self.kinds(), ['needs-yes'])
        with open(watch.AUTOFIX, 'w') as f: f.write('not json')
        watch.PREV.clear(); watch.step(self.env()); self.assertEqual(e.restarts, [])

    def test_the_view_the_next_round_after_a_yes_is_recovered_once(self):
        self.checks(JELLY); e = self.env(); watch.step(e)
        e.inside['jellyfin'] = 'container-good'; e.reads.add('/media/Shows/test.mp4')    # someone restarted it
        watch.step(e); watch.step(e)
        self.assertEqual(self.kinds(), ['needs-yes', 'recovered'])
        self.assertIs(self.result('jellyfin')['works'], True)
        self.assertEqual(e.file_reads()[-1][-1], '/media/Shows/test.mp4')     # the file was read only after the table said fine

    def test_auto_fix_restarts_checks_again_and_says_fixed(self):
        self.checks(JELLY); self.autofix('jellyfin')
        def heal(env): env.inside['jellyfin'] = 'container-good'; env.reads.add('/media/Shows/test.mp4')
        e = self.env(restart_fixes=heal); watch.step(e)
        self.assertEqual(e.restarts, ['jellyfin', 'audiobookshelf'])
        self.assertEqual(self.kinds(), ['fixed']); self.assertIn('restarted Jellyfin and Audiobookshelf', self.events[0]['body'])
        watch.step(e); self.assertEqual(self.kinds(), ['fixed'])
        self.assertIs(self.result('jellyfin')['works'], True)

    def test_auto_fix_that_does_not_help_is_tried_once_and_says_broke(self):
        self.checks(JELLY); self.autofix('jellyfin'); e = self.env()
        watch.step(e, settle=0); watch.step(e, settle=0); watch.step(e, settle=0)
        self.assertEqual(e.restarts, ['jellyfin', 'audiobookshelf'], 'one attempt per breakage, not one per round')
        self.assertEqual(self.kinds(), ['broke']); self.assertIn('did not help', self.events[0]['body'])

    def test_only_the_approved_ids_are_restarted(self):
        self.checks(JELLY, ABS); self.autofix('audiobookshelf'); e = self.env(); watch.step(e, settle=0)
        self.assertEqual(e.restarts, ['audiobookshelf'])
        self.assertEqual(sorted(x['kind'] for x in self.events), ['broke', 'needs-yes'])

    def test_a_frozen_unit_is_paused_not_broken(self):
        self.checks(JELLY); e = self.env(frozen={'jellyfin'}); watch.step(e)
        self.assertIsNone(self.result('jellyfin')['works']); self.assertEqual(self.events, [])


class Drive(Base):
    def test_no_file_is_read_on_a_missing_read_only_or_dropped_drive(self):
        for host, code in (('host-missing', 'drive-missing'), ('host-readonly', 'drive-readonly'), ('host-dropped', 'drive-dropped')):
            watch.RESULTS.clear(); watch.PREV.clear(); self.checks(JELLY, ABS)
            e = FakeEnv(host=host, inside={'jellyfin': 'container-good', 'audiobookshelf': 'container-good'}, reads={'/media/Shows/test.mp4', '/audiobooks'},
                        http={'http://127.0.0.1:8096/health': 200})
            watch.step(e)
            self.assertEqual(self.result('jellyfin')['code'], code, host)
            self.assertEqual(e.calls, [], f'{host}: nothing at all is run inside a container, so no file is read')

    def test_a_drive_check_speaks_for_its_dependents(self):
        self.checks(DRIVE, JELLY, ABS, QBT)
        e = FakeEnv(host='host-missing', inside={}); watch.step(e); watch.step(e)
        self.assertEqual(len(self.events), 1)
        self.assertEqual(self.events[0]['title'], 'The media drive is not connected'); self.assertEqual(self.events[0]['kind'], 'broke')
        self.assertIs(self.result('jellyfin')['works'], False)          # the cards still say why
        self.assertEqual(self.result('jellyfin')['reason'], 'its drive is not connected')

    def test_drive_back_then_the_dead_copies_get_their_own_event(self):
        self.checks(DRIVE, JELLY)
        e = FakeEnv(host='host-missing', inside={'jellyfin': 'container-dead-shutdown'}); watch.step(e)
        e.host = 'host-good'; watch.step(e)
        self.assertEqual(self.kinds(), ['broke', 'recovered', 'needs-yes'])
        self.assertEqual(self.events[-1]['title'], 'Jellyfin runs, but cannot read its drive')

    def test_unreadable_mount_table_is_unknown_not_broken(self):
        self.checks(DRIVE, JELLY); e = FakeEnv(host=None); watch.step(e)
        self.assertIsNone(self.result('media-drive')['works']); self.assertIsNone(self.result('jellyfin')['works']); self.assertEqual(self.events, [])

    def test_a_container_that_cannot_be_looked_into_is_unknown(self):
        self.checks(JELLY); e = FakeEnv(inside={}, http={'http://127.0.0.1:8096/health': 200}); watch.step(e)
        self.assertIsNone(self.result('jellyfin')['works']); self.assertEqual(e.file_reads(), []); self.assertEqual(self.events, [])

    def test_unit_down_and_no_answer(self):
        self.checks(JELLY); e = FakeEnv(active=False); watch.step(e)
        self.assertEqual(self.events[0]['title'], 'Jellyfin is not running')
        watch.RESULTS.clear(); watch.PREV.clear(); del self.events[:]
        e = FakeEnv(inside={'jellyfin': 'container-good'}, reads={'/media/Shows/test.mp4'}); watch.step(e)    # runs, drive fine, web address silent
        self.assertEqual(self.events[0]['title'], 'Jellyfin runs, but does not answer at its web address')

    def test_first_good_round_is_silent_and_a_restart_of_argus_does_not_repeat_an_event(self):
        self.checks(JELLY); e = FakeEnv(inside={'jellyfin': 'container-good'}, reads={'/media/Shows/test.mp4'}, http={'http://127.0.0.1:8096/health': 200})
        watch.step(e); self.assertEqual(self.events, [])
        e.inside['jellyfin'] = 'container-dead-gone'; watch.step(e); self.assertEqual(self.kinds(), ['needs-yes'])
        watch.PREV.clear(); watch.load_prev()                  # the server restarted: state comes back from the file
        watch.step(e); self.assertEqual(self.kinds(), ['needs-yes'])


class Config(Base):
    def test_no_file_no_checks(self):
        self.assertEqual(watch.load_checks(), ([], [])); watch.step(FakeEnv()); self.assertEqual(watch.snapshot(), [])

    def test_a_file_read_without_its_drive_is_refused(self):
        bad = dict(JELLY); del bad['mount']
        self.checks(bad, ABS)
        good, refused = watch.load_checks()
        self.assertEqual([c['id'] for c in good], ['audiobookshelf']); self.assertIn('mount', refused[0][1])

    def test_refusals(self):
        for c in (dict(id='X', title='t', unit='u'), dict(id='a', unit='u'), dict(id='a', title='t'), dict(id='a', title='t', mount='relative'),
                  dict(id='a', title='t', http='file:///etc/passwd'), dict(id='a', title='t', unit='u', fix=dict(restart=[])), 'x'):
            self.checks(c); self.assertEqual(watch.load_checks()[0], [], c)

    def test_broken_json(self):
        with open(watch.CHECKS, 'w') as f: f.write('{')
        self.assertEqual(watch.load_checks()[0], [])


class Hung(Base):
    def test_a_call_that_never_returns_ends_at_its_timeout(self):
        t = time.time(); rc, out = watch.Env().run([sys.executable, '-c', 'import time; time.sleep(30)'], timeout=1)
        self.assertIsNone(rc); self.assertLess(time.time() - t, 10)

    def test_a_program_that_does_not_exist_is_unknown(self):
        self.assertEqual(watch.Env().run(['no-such-program-here']), (None, b''))

    def test_http_that_nobody_answers(self):
        with socket.socket() as s: s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
        self.assertIsNone(watch.Env().http(f'http://127.0.0.1:{port}/', timeout=1))

    def test_old_results_turn_unknown(self):
        self.checks(DRIVE); watch.step(FakeEnv()); self.assertIs(self.result('media-drive')['works'], True)
        with watch._lock: watch.RESULTS['media-drive']['at'] -= 5000
        self.assertIsNone(self.result('media-drive')['works']); self.assertEqual(self.result('media-drive')['code'], 'stale')

    def test_a_check_that_crashes_is_unknown_and_the_others_still_run(self):
        class Boom(FakeEnv):
            def is_active(self, unit): raise RuntimeError('boom') if unit == 'jellyfin' else None
        self.checks(JELLY, DRIVE); watch.step(Boom())
        self.assertIsNone(self.result('jellyfin')['works']); self.assertIs(self.result('media-drive')['works'], True)


class Events(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='notify-test-'); os.environ['ARGUS_EVENTS'] = os.path.join(self.tmp, 'sub', 'events.jsonl')
        self.sinks = list(notify.SINKS); notify.SINKS[:] = [notify.file_sink]
    def tearDown(self):
        notify.SINKS[:] = self.sinks; os.environ.pop('ARGUS_EVENTS', None); shutil.rmtree(self.tmp, ignore_errors=True)

    def test_the_file_is_capped_and_newest_first_on_read(self):
        for i in range(notify.MAX_LINES + notify.SLACK + 5): notify.notify(notify.make('summary', 's', f'n{i}'))
        with open(notify.events_path(), encoding='utf-8') as f: n = len(f.readlines())
        self.assertLessEqual(n, notify.MAX_LINES + notify.SLACK); self.assertGreaterEqual(n, notify.MAX_LINES)
        self.assertEqual(notify.read_events(1)[0]['title'], f'n{notify.MAX_LINES + notify.SLACK + 4}')

    def test_a_broken_sink_does_not_stop_the_others(self):
        seen = []; notify.SINKS[:] = [lambda e: 1 / 0, seen.append]
        notify.notify(notify.make('broke', 'x', 'T')); self.assertEqual(len(seen), 1)

    def test_kinds_and_levels(self):
        with self.assertRaises(ValueError): notify.make('oops', 'x', 'T')
        self.assertEqual([notify.make(k, 'x', 'T')['level'] for k in notify.KINDS], ['alert', 'alert', 'info', 'info', 'info'])


class RealServer(unittest.TestCase):
    """The server in its own process: fake systemctl and container runtime, canned mount tables, a one-second loop."""
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='watch-server-')
        home = os.path.join(cls.tmp, 'home'); static = os.path.join(cls.tmp, 'static'); fx = os.path.join(cls.tmp, 'fx'); pod = os.path.join(cls.tmp, 'pod')
        for d in (home, static, pod): os.makedirs(d)
        shutil.copytree(FX, fx, ignore=shutil.ignore_patterns('controllers-sysfs', 'memory'))
        shutil.copy(os.path.join(R, 'themes', 'leafy-realm', 'theme.json'), static)
        units = jload(os.path.join(fx, 'units.json'))
        units['jellyfin'] = {'Result': 'success', 'ActiveState': 'active'}
        jdump(units, os.path.join(fx, 'units.json'))
        # a systemctl program that works on every OS: Windows needs a .cmd to run a .py
        if os.name == 'nt':
            sysctl = os.path.join(cls.tmp, 'systemctl.cmd'); put(sysctl, f'@"{sys.executable}" "{os.path.join(fx, "fake_systemctl.py")}" %*\r\n')
        else:
            sysctl = os.path.join(fx, 'fake_systemctl.py'); os.chmod(sysctl, 0o755)
        shutil.copy(os.path.join(WFX, 'container-dead-shutdown.mountinfo'), os.path.join(pod, 'jellyfin.mountinfo'))
        cls.checks = [dict(JELLY, container=dict(JELLY['container'], runtime=[sys.executable, os.path.join(fx, 'fake_podman.py')]), http=None, mount='/mnt/media'),
                      dict(DRIVE)]
        del cls.checks[0]['http']
        jdump({'checks': cls.checks}, os.path.join(cls.tmp, 'checks.json'))
        cls.events = os.path.join(cls.tmp, 'events.jsonl')
        with socket.socket() as s: s.bind(('127.0.0.1', 0)); cls.port = s.getsockname()[1]
        env = {k: v for k, v in os.environ.items() if not k.startswith('ARGUS_')}
        env.update(HOME=home, USERPROFILE=home, ARGUS_BIND='127.0.0.1', ARGUS_PORT=str(cls.port), ARGUS_STATIC=static, ARGUS_BUNDLED=os.path.join(cls.tmp, 'none'),
                   ARGUS_SYSTEMCTL=sysctl, ARGUS_CHECKS=os.path.join(cls.tmp, 'checks.json'), ARGUS_AUTOFIX=os.path.join(cls.tmp, 'auto-fix.json'),
                   ARGUS_MOUNTINFO=os.path.join(WFX, 'host-good.mountinfo'), ARGUS_EVENTS=cls.events, ARGUS_WATCH_STATE=os.path.join(cls.tmp, 'watch.json'),
                   ARGUS_WATCH_INTERVAL='1', FAKE_PODMAN_DIR=pod, ARGUS_ALERTS=os.path.join(cls.tmp, 'alerts'), ARGUS_REGISTRY=os.path.join(cls.tmp, 'reg'))
        cls.log = open(os.path.join(cls.tmp, 'server.log'), 'w')
        cls.proc = subprocess.Popen([sys.executable, os.path.join(R, 'server', 'argus_ui.py')], env=env, stdout=cls.log, stderr=cls.log)
        for _ in range(150):
            try: socket.create_connection(('127.0.0.1', cls.port), timeout=1).close(); break
            except OSError: time.sleep(.1)
        else: cls.tearDownClass(); raise RuntimeError('the server did not start; its log was in ' + cls.tmp)
        cls.units_file = os.path.join(fx, 'units.json')

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        try: cls.proc.wait(10)
        except subprocess.TimeoutExpired: cls.proc.kill(); cls.proc.wait(10)
        cls.log.close(); shutil.rmtree(cls.tmp, ignore_errors=True)

    def state(self):
        with urllib.request.urlopen(f'http://127.0.0.1:{self.port}/api/state', timeout=10) as r: return json.load(r)

    def test_state_says_it_runs_but_does_not_work_and_one_event_is_raised(self):
        for _ in range(60):
            s = self.state(); w = {x['id']: x for x in s['watch']}
            if w.get('jellyfin', {}).get('works') is False: break
            time.sleep(.2)
        else: self.fail('no verdict in 12 s; log: ' + os.path.join(self.tmp, 'server.log'))
        self.assertEqual((w['jellyfin']['code'], w['jellyfin']['reason']), ('dead-copy', 'cannot read its drive'))
        self.assertIs(w['media-drive']['works'], True)
        msgs = [a['message'] for a in s['alerts'] if a['job'] == 'mnemosyne-jellyfin']
        self.assertEqual(msgs, ['Running, but not working: cannot read its drive'])
        time.sleep(3.5)                                          # three more rounds of the loop
        with open(self.events, encoding='utf-8') as f: ev = [json.loads(l) for l in f]
        self.assertEqual([(e['kind'], e['subject']) for e in ev], [('needs-yes', 'jellyfin')], 'one event, not one per round')
        self.assertEqual(ev[0]['title'], 'Jellyfin runs, but cannot read its drive')
        units = jload(self.units_file); self.assertEqual(units['jellyfin']['ActiveState'], 'active')   # nothing was restarted


if __name__ == '__main__':
    unittest.main()
