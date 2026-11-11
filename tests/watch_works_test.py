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
        self.sinks = list(notify.SINKS)          # a copy: SINKS is mutated in place below, so restoring vars() alone would not undo it
        watch.CHECKS = os.path.join(self.tmp, 'checks.json'); watch.AUTOFIX = os.path.join(self.tmp, 'auto-fix.json')
        watch.STATEFILE = os.path.join(self.tmp, 'watch.json')
        os.environ['ARGUS_EVENTS'] = os.path.join(self.tmp, 'events.jsonl')
        watch.RESULTS.clear(); watch.PREV.clear(); watch.BAD.clear(); watch._AUTOFIX_SAID[0] = None
        for x in (watch.PENDING, watch.FIXING, watch.ASKED, watch.RUNNING, watch.SENT, watch.OUTCOMES, watch.INFLIGHT): x.clear()
        watch.WAKE.clear()
        self.events = []; notify.SINKS[:] = [self.events.append]
    def tearDown(self):
        for m, d in self.saved.items(): vars(m).update(d)
        notify.SINKS[:] = self.sinks
        os.environ.pop('ARGUS_EVENTS', None)
        shutil.rmtree(self.tmp, ignore_errors=True)
    def checks(self, *cs):
        with open(watch.CHECKS, 'w', encoding='utf-8') as f: json.dump({'checks': list(cs)}, f)
    def autofix(self, *ids, trial=None):
        d = {'ids': list(ids)}
        if trial is not None: d['trial'] = trial
        with open(watch.AUTOFIX, 'w', encoding='utf-8') as f: json.dump(d, f)
    def rounds(self, e, n=watch.CONFIRM, **kw):
        for _ in range(n): watch.step(e, **kw)
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
        self.rounds(e)
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
        self.checks(JELLY); self.autofix(); e = self.env(); self.rounds(e)
        self.assertEqual(e.restarts, []); self.assertEqual(self.kinds(), ['needs-yes'])
        with open(watch.AUTOFIX, 'w') as f: f.write('not json')
        watch.PREV.clear(); e = self.env(); self.rounds(e); self.assertEqual(e.restarts, [])

    def test_the_view_the_next_round_after_a_yes_is_recovered_once(self):
        self.checks(JELLY); e = self.env(); self.rounds(e)
        e.inside['jellyfin'] = 'container-good'; e.reads.add('/media/Shows/test.mp4')    # someone restarted it
        watch.step(e); watch.step(e)
        self.assertEqual(self.kinds(), ['needs-yes', 'recovered'])
        self.assertIs(self.result('jellyfin')['works'], True)
        self.assertEqual(e.file_reads()[-1][-1], '/media/Shows/test.mp4')     # the file was read only after the table said fine

    def test_auto_fix_restarts_checks_again_and_says_fixed(self):
        self.checks(JELLY); self.autofix('jellyfin', trial=False)
        def heal(env): env.inside['jellyfin'] = 'container-good'; env.reads.add('/media/Shows/test.mp4')
        e = self.env(restart_fixes=heal); watch.step(e); self.assertEqual((e.restarts, self.events), ([], []), 'one bad round is not enough')
        watch.step(e)
        self.assertEqual(e.restarts, ['jellyfin', 'audiobookshelf'])
        self.assertEqual(self.kinds(), ['fixed']); self.assertIn('restarted Jellyfin and Audiobookshelf', self.events[0]['body'])
        watch.step(e); self.assertEqual(self.kinds(), ['fixed'])
        self.assertIs(self.result('jellyfin')['works'], True)

    def test_auto_fix_that_does_not_help_is_tried_once_and_says_broke(self):
        self.checks(JELLY); self.autofix('jellyfin', trial=False); e = self.env()
        for _ in range(4): watch.step(e, settle=0)
        self.assertEqual(e.restarts, ['jellyfin', 'audiobookshelf'], 'one attempt per breakage, not one per round')
        self.assertEqual(self.kinds(), ['broke']); self.assertIn('did not help', self.events[0]['body'])

    def test_only_the_approved_ids_are_restarted(self):
        self.checks(JELLY, ABS); self.autofix('audiobookshelf', trial=False); e = self.env(); self.rounds(e, settle=0)
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
            self.rounds(e)
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
        e = FakeEnv(host='host-missing', inside={'jellyfin': 'container-dead-shutdown'}); self.rounds(e)
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
        self.checks(JELLY); e = FakeEnv(active=False); self.rounds(e)
        self.assertEqual(self.events[0]['title'], 'Jellyfin is not running')
        watch.RESULTS.clear(); watch.PREV.clear(); del self.events[:]
        e = FakeEnv(inside={'jellyfin': 'container-good'}, reads={'/media/Shows/test.mp4'}); self.rounds(e)    # runs, drive fine, web address silent
        self.assertEqual(self.events[0]['title'], 'Jellyfin runs, but does not answer at its web address')

    def test_first_good_round_is_silent_and_a_restart_of_argus_does_not_repeat_an_event(self):
        self.checks(JELLY); e = FakeEnv(inside={'jellyfin': 'container-good'}, reads={'/media/Shows/test.mp4'}, http={'http://127.0.0.1:8096/health': 200})
        watch.step(e); self.assertEqual(self.events, [])
        e.inside['jellyfin'] = 'container-dead-gone'; self.rounds(e); self.assertEqual(self.kinds(), ['needs-yes'])
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


GOOD = dict(inside={'jellyfin': 'container-good', 'audiobookshelf': 'container-good', 'qbittorrent': 'container-good'},
            reads={'/media/Shows/test.mp4', '/audiobooks'}, http={'http://127.0.0.1:8096/health': 200, 'http://127.0.0.1:8080/': 200})
def good_env(**kw):
    d = {k: (dict(v) if isinstance(v, dict) else set(v)) for k, v in GOOD.items()}; d.update(kw); return FakeEnv(**d)


class SelfRepairLimits(Base):
    """B1: restarts only for "runs but cannot read its drive", once per check in 24 hours, the mark on disk first, a unit once per round."""
    def test_b1_no_restart_for_a_slow_web_answer_or_a_unit_that_is_down(self):
        self.checks(JELLY); self.autofix('jellyfin', trial=False)
        e = good_env(http={}); self.rounds(e, 3, settle=0)                        # R1 probe P2: the web address is slow
        self.assertEqual(e.restarts, []); self.assertEqual(self.kinds(), ['needs-yes'])
        watch.PREV.clear(); del self.events[:]
        e = good_env(active=False); self.rounds(e, 3, settle=0)                   # R1 probe P3: the unit is not running
        self.assertEqual(e.restarts, []); self.assertEqual(self.kinds(), ['needs-yes'])

    def test_b1_a_flapping_program_gets_one_restart_in_24_hours(self):
        self.checks(JELLY); self.autofix('jellyfin', trial=False)
        def heal(env): env.inside['jellyfin'] = 'container-good'
        e = good_env(restart_fixes=heal)
        def breaks(): e.inside['jellyfin'] = 'container-dead-shutdown'; self.rounds(e, settle=0)
        def works(): e.inside['jellyfin'] = 'container-good'; watch.step(e, settle=0)
        breaks(); self.assertEqual(e.restarts, ['jellyfin', 'audiobookshelf']); self.assertEqual(self.kinds(), ['fixed'])
        for _ in range(3): works(); breaks()                                       # R1 probe P4: it keeps flipping
        watch.PREV.clear(); watch.load_prev(); e.t += 3600; works(); breaks()     # and argus-ui itself restarted in between
        self.assertEqual(e.restarts, ['jellyfin', 'audiobookshelf'], 'one automatic try per check in 24 hours')
        self.assertEqual(self.kinds(), ['fixed'] + ['needs-yes', 'recovered'] * 3 + ['needs-yes'])
        self.assertIn('already restarted Jellyfin and Audiobookshelf by itself', self.events[1]['body'])
        e.t += 24 * 3600; works(); breaks()
        self.assertEqual(e.restarts, ['jellyfin', 'audiobookshelf'] * 2, 'a day later it may try again')
        self.assertEqual(self.kinds()[-2:], ['recovered', 'fixed'])

    def test_b1_the_mark_is_on_disk_before_the_restart(self):
        self.checks(JELLY); self.autofix('jellyfin', trial=False)
        seen = []
        def look(env): seen.append(jload(watch.STATEFILE)['jellyfin'])
        e = good_env(inside={'jellyfin': 'container-dead-shutdown'}, restart_fixes=look); self.rounds(e, settle=0)   # R1 probe P8
        self.assertTrue(seen); self.assertEqual(seen[0]['last_try'], e.t); self.assertIs(seen[0]['works'], False)

    def test_b1_a_unit_is_restarted_at_most_once_per_round(self):
        self.checks(JELLY, ABS); self.autofix('jellyfin', 'audiobookshelf', trial=False)        # both name audiobookshelf (R1 N5)
        e = good_env(inside={'jellyfin': 'container-dead-shutdown', 'audiobookshelf': 'container-dead-gone'}); self.rounds(e, settle=0)
        self.assertEqual(sorted(e.restarts), ['audiobookshelf', 'jellyfin'])

    def test_b1_unknown_codes_never_restart(self):
        self.assertEqual(watch.REPAIRABLE, ('dead-copy', 'cannot-read'))


class TrialDay(Base):
    """S1: note-only is the default; only "trial": false restarts; a file of another shape turns self-repair off."""
    def test_s1_trial_is_the_default_and_records_the_try(self):
        self.checks(JELLY); self.autofix('jellyfin'); e = good_env(inside={'jellyfin': 'container-dead-shutdown'})
        self.rounds(e, 4, settle=0)
        self.assertEqual(e.restarts, []); self.assertEqual(self.kinds(), ['needs-yes'])
        self.assertIn('Argus would have restarted Jellyfin and Audiobookshelf by itself, but it did not', self.events[0]['body'])
        self.assertIn('Waiting for your yes', self.events[0]['body'])
        saved = jload(watch.STATEFILE)['jellyfin']; self.assertEqual(saved['last_try'], e.t); self.assertIs(saved['last_try_trial'], True)
        e.inside['jellyfin'] = 'container-good'; watch.step(e); e.inside['jellyfin'] = 'container-dead-gone'; self.rounds(e, settle=0)
        self.assertEqual(e.restarts, []); self.assertIn('would have restarted', self.events[-1]['body'])   # within the day: no second try

    def test_s1_trial_true_and_false(self):
        self.checks(JELLY); self.autofix('jellyfin', trial=True); e = good_env(inside={'jellyfin': 'container-dead-shutdown'})
        self.rounds(e, settle=0); self.assertEqual(e.restarts, [])
        self.assertEqual(watch.auto_fix(), ({'jellyfin'}, True))
        self.autofix('jellyfin', trial=False); self.assertEqual(watch.auto_fix(), ({'jellyfin'}, False))

    def test_s1_a_file_of_another_shape_switches_self_repair_off_with_one_log_line(self):
        said = []; watch.log = said.append
        for text in ('not json', '["jellyfin"]', '{"ids": ["jellyfin"], "trial": "false"}', '{"ids": "jellyfin"}', '{"ids": ["jellyfin"], "live": true}'):
            del said[:]; watch._AUTOFIX_SAID[0] = None
            with open(watch.AUTOFIX, 'w') as f: f.write(text)
            for _ in range(3): self.assertEqual(watch.auto_fix(), (set(), True), text)
            self.assertEqual(len(said), 1, (text, said))           # one line, not one per round
        self.checks(JELLY); e = good_env(inside={'jellyfin': 'container-dead-shutdown'}); self.rounds(e, settle=0)
        self.assertEqual(e.restarts, []); self.assertNotIn('would have', self.events[0]['body'])
        os.remove(watch.AUTOFIX); self.assertEqual(watch.auto_fix(), (set(), True))


class Starting(Base):
    """S2: a unit that is starting, reloading or stopping is "cannot tell yet", unless it stays so for more than 3 rounds."""
    def test_s2_the_words_of_systemctl(self):
        for w, want in (('active\n', True), ('inactive', False), ('failed', False), ('activating', watch.BETWEEN),
                        ('reloading', watch.BETWEEN), ('deactivating', watch.BETWEEN), ('', None), ('maintenance', None)):
            self.assertEqual(watch.unit_state(w), want, w)

    def test_s2_a_starting_program_is_not_down(self):
        self.checks(JELLY); self.autofix('jellyfin', trial=False); e = good_env(active=watch.BETWEEN)
        self.rounds(e, 3, settle=0)
        self.assertEqual(self.events, []); self.assertEqual(e.restarts, []); self.assertIsNone(self.result('jellyfin')['works'])
        e.up = True; self.rounds(e, 5); self.assertEqual(self.events, [])      # it started: nothing to say

    def test_s2_a_program_that_stays_between_counts_as_not_running(self):
        self.checks(JELLY); e = good_env(active=watch.BETWEEN)
        self.rounds(e, 3); self.assertEqual(self.events, [])
        self.rounds(e, 2)
        self.assertEqual([(x['kind'], x['title']) for x in self.events], [('needs-yes', 'Jellyfin is not running')])

    def test_s2_the_server_reads_is_active_through_unit_state(self):
        a = import_server()
        saved = a.sc
        try:
            for word, want in (('activating\n', watch.BETWEEN), ('active\n', True), ('failed\n', False)):
                a.sc = lambda *x, w=word: w
                self.assertEqual(a.watch_env().is_active('jellyfin'), want)
        finally: a.sc = saved


class OneSlowAnswer(Base):
    """S3: a failure must be seen in 2 rounds in a row; recovery is immediate; the count survives a restart of argus-ui."""
    def test_s3_flapping_raises_nothing(self):
        self.checks(JELLY); e = good_env()
        for i in range(6):                                                           # R1 probe P5
            e.answers['http://127.0.0.1:8096/health'] = 200 if i % 2 == 0 else None; watch.step(e)
        self.assertEqual(self.events, [])

    def test_s3_two_in_a_row_count_and_the_count_is_saved(self):
        self.checks(JELLY); e = good_env(); watch.step(e)
        e.answers.clear(); watch.step(e)
        self.assertEqual(self.events, []); self.assertEqual(jload(watch.STATEFILE)['jellyfin']['pending'], 1)
        self.assertEqual(self.result('jellyfin')['code'], 'pending')
        watch.PREV.clear(); watch.load_prev(); watch.step(e)                         # argus-ui restarted in between
        self.assertEqual(self.kinds(), ['needs-yes'])
        e.answers['http://127.0.0.1:8096/health'] = 200; watch.step(e)
        self.assertEqual(self.kinds(), ['needs-yes', 'recovered'])


class HangingRead(Base):
    """S4: a test read that hangs is not repeated for 15 minutes or until the drive's line changes, and shows as a warning."""
    def env(self):
        e = good_env(); orig = e.run
        def run(argv, timeout=6):
            if argv[-1] == '/audiobooks': e.calls.append(argv); return None, b''
            return orig(argv, timeout)
        e.run = run; return e
    def reads(self, e): return len([c for c in e.calls if c[-1] == '/audiobooks'])

    def test_s4_a_hanging_read_does_not_pile_up_and_shows_as_a_warning(self):
        self.checks(ABS); self.autofix('audiobookshelf', trial=False); e = self.env()
        watch.step(e, settle=0); self.assertEqual(self.reads(e), 1); self.assertEqual(self.events, [])
        for _ in range(4): e.t += 60; watch.step(e, settle=0)                      # R1 probe P7
        self.assertEqual(self.reads(e), 1, 'no new read while the first one hung')
        self.assertEqual([(x['kind'], x['level'], x['title']) for x in self.events], [('broke', 'warn', 'Audiobookshelf does not answer when it reads its drive')])
        self.assertEqual(e.restarts, [], 'its own code: never a restart')
        al = watch.alert_list(watch.snapshot(), lambda j: True)
        self.assertEqual([(a['level'], a['message']) for a in al], [('warn', 'Audiobookshelf does not answer when it reads its drive.')])
        e.t += 15 * 60; watch.step(e, settle=0); self.assertEqual(self.reads(e), 2, 'after 15 minutes it reads again')
        e.host = 'host-good-remounted'; watch.step(e, settle=0); self.assertEqual(self.reads(e), 3, 'the drive line changed: it reads again')
        self.assertEqual(len(self.events), 1)
        e.run = FakeEnv.run.__get__(e); e.host = 'host-good'; watch.step(e, settle=0)
        self.assertEqual(self.kinds(), ['broke', 'recovered'])

    def test_s4_the_hold_survives_a_restart_of_argus(self):
        self.checks(ABS); e = self.env(); watch.step(e)
        watch.PREV.clear(); watch.load_prev(); e.t += 60; watch.step(e)
        self.assertEqual(self.reads(e), 1)


class StartedBeforeTheDrive(Base):
    """S5: container.mount: the container's line for that path must sit on the host's device for the check's mount."""
    QB = dict(QBT, container=dict(name='qbittorrent', mount='/downloads'), http=None)
    def setUp(self):
        super().setUp(); self.QB = {k: v for k, v in self.QB.items() if v is not None}

    def test_s5_a_container_that_bound_the_empty_folder_is_a_dead_copy(self):
        self.checks(self.QB); e = good_env(inside={'qbittorrent': 'container-early'}); self.rounds(e)
        r = self.result('qbittorrent'); self.assertEqual((r['works'], r['code'], r['reason']), (False, 'dead-copy', 'cannot read its drive'))
        self.assertEqual(e.file_reads(), [], 'only mount tables are read')
        self.assertEqual(self.kinds(), ['broke'])

    def test_s5_a_number_given_to_another_drive_is_a_dead_copy(self):
        self.checks(self.QB); e = good_env(inside={'qbittorrent': 'container-number-reused'}); self.rounds(e)
        self.assertEqual(self.result('qbittorrent')['code'], 'dead-copy')

    def test_s5_the_right_drive_works(self):
        self.checks(self.QB); e = good_env(inside={'qbittorrent': 'container-good-downloads'}); self.rounds(e)
        self.assertIs(self.result('qbittorrent')['works'], True); self.assertEqual(self.events, [])

    def test_s5_refused_without_the_drive_or_with_a_relative_path(self):
        for ct, mount in ((dict(name='q', mount='/downloads'), None), (dict(name='q', mount='downloads'), '/mnt/media')):
            c = dict(id='q', title='Q', container=ct)
            if mount: c['mount'] = mount
            self.checks(c); self.assertEqual(watch.load_checks()[0], [], c)


class QuietRecovery(Base):
    def test_s6_when_the_drive_returns_only_the_drive_recovers(self):
        self.checks(DRIVE, JELLY, ABS, QBT); e = good_env(); watch.step(e)        # R1 probe P1
        e.host = 'host-missing'; self.rounds(e); e.host = 'host-good'; watch.step(e)
        self.assertEqual([(x['kind'], x['subject']) for x in self.events], [('broke', 'media-drive'), ('recovered', 'media-drive')])


class RestartTrouble(Base):
    def test_s8_a_restart_that_raises_does_not_stop_the_round(self):
        self.checks(JELLY, ABS); self.autofix('jellyfin', trial=False)               # R1 probe P9
        e = good_env(inside={'jellyfin': 'container-dead-shutdown', 'audiobookshelf': 'container-good'})
        def boom(u): raise TimeoutError('systemctl took 20 s')
        e.restart = boom
        self.rounds(e, settle=0)
        self.assertEqual(sorted(r['id'] for r in watch.snapshot()), ['audiobookshelf', 'jellyfin'])
        self.assertEqual(self.kinds(), ['broke']); self.assertIn('the restart did not work', self.events[0]['body'])
        self.assertIn('last_try', jload(watch.STATEFILE)['jellyfin'])

    def test_s9_a_restart_gets_90_seconds_and_the_wait_stops_early(self):
        self.checks(JELLY); self.autofix('jellyfin', trial=False)
        e = good_env(inside={'jellyfin': 'container-dead-shutdown'}); start = []
        def slow(env):
            if not start: start.append(env.t)
        e.restart_fixes = slow; orig = e.mountinfo
        def later():
            if start and e.t - start[0] >= 60: e.inside['jellyfin'] = 'container-good'
            return orig()
        e.mountinfo = later
        self.rounds(e)                                                               # the default settle
        self.assertEqual(self.kinds(), ['fixed'], 'Jellyfin needed 60 s to start; 20 s would have called it a failure')
        self.assertLess(e.t - start[0], 70, 'it stopped waiting once it worked')

    def test_s9_the_wait_does_not_hold_the_power_lock(self):
        a = import_server(); held = []
        saved = a.sc_ok, a.frozen
        a.sc_ok = lambda *x: (held.append(('restart', a.LOCK.locked())), (True, ''))[1]
        a.frozen = lambda: []
        try:
            class E(FakeEnv):
                def restart(self, u): return a.watch_restart(u)
                def sleep(self, s): held.append(('wait', a.LOCK.locked())); self.t += s
            self.checks(JELLY); self.autofix('jellyfin', trial=False)
            self.rounds(E(inside={'jellyfin': 'container-dead-shutdown'}, http={'http://127.0.0.1:8096/health': 200}))
        finally: a.sc_ok, a.frozen = saved
        self.assertIn(('restart', True), held); self.assertIn(('wait', False), held); self.assertNotIn(('wait', True), held)


class EmptyFolder(Base):
    def test_s10_an_empty_folder_reads_as_cannot_read(self):
        self.checks(ABS); e = good_env(); orig = e.run
        e.run = lambda argv, timeout=6: (0, b'') if argv[-1] == '/audiobooks' else orig(argv, timeout)
        self.rounds(e); self.assertEqual(self.result('audiobookshelf')['code'], 'cannot-read')


class Names(Base):
    def test_n1_names_may_not_start_with_a_dash(self):
        for c in (dict(id='a', title='t', unit='-h'), dict(id='a', title='t', mount='/m', container=dict(name='--privileged')),
                  dict(id='a', title='t', unit='u', fix=dict(restart=['--all']))):
            self.checks(c); self.assertEqual(watch.load_checks()[0], [], c)
        self.checks(dict(id='a', title='t', unit='a-b@1.x')); self.assertEqual(len(watch.load_checks()[0]), 1)


class Helper(unittest.TestCase):
    def test_n6_the_test_helper_restores_the_sinks(self):
        before = list(notify.SINKS)
        class T(Base):
            def runTest(self): pass
        t = T(); t.setUp(); notify.register(lambda e: None); t.tearDown()
        self.assertEqual(notify.SINKS, before); self.assertIn(notify.file_sink, notify.SINKS)


def read_answers(e, path, rc, out=b''):
    """Make the test read of `path` inside a container end with exit code rc (None = it timed out)."""
    orig = FakeEnv.run.__get__(e)
    def run(argv, timeout=6):
        if argv[-1] == path: e.calls.append(argv); return rc, out
        return orig(argv, timeout)
    e.run = run


class PodmanTrouble(Base):
    """B2a: only a failed read (exit 1 or 2, or nothing read) is "cannot read its drive"; podman's own errors are "could not look"."""
    def test_b2a_exit_codes(self):
        self.checks(ABS)
        for rc, out, want in ((1, b'', (False, 'cannot-read')), (2, b'', (False, 'cannot-read')), (0, b'', (False, 'cannot-read')),
                              (0, b'a\n', (True, 'ok')), (125, b'', (None, 'cannot-look')), (126, b'', (None, 'cannot-look')),
                              (127, b'', (None, 'cannot-look')), (137, b'', (None, 'cannot-look')), (3, b'x', (None, 'cannot-look')),
                              (-9, b'', (None, 'cannot-look'))):
            e = good_env(); read_answers(e, '/audiobooks', rc, out)
            r = watch.evaluate(ABS, e); self.assertEqual((r['works'], r['code']), want, rc)

    def test_b2a_exit_125_never_restarts_from_healthy(self):
        self.checks(ABS); self.autofix('audiobookshelf', trial=False)
        e = good_env(); watch.step(e, settle=0); read_answers(e, '/audiobooks', 125)
        self.rounds(e, 5, settle=0)
        self.assertEqual(e.restarts, []); self.assertEqual(self.events, []); self.assertIsNone(self.result('audiobookshelf')['works'])

    def test_b2a_exit_125_never_restarts_after_a_confirmed_no_answer(self):
        self.checks(JELLY); self.autofix('jellyfin', trial=False)
        e = good_env(http={}); self.rounds(e, settle=0); self.assertEqual(self.kinds(), ['needs-yes'])      # web address silent: confirmed
        read_answers(e, '/media/Shows/test.mp4', 125); self.rounds(e, 4, settle=0)                       # R1b probe Q4c
        self.assertEqual(e.restarts, []); self.assertEqual(self.kinds(), ['needs-yes'])


class RepairNeedsTwoRounds(Base):
    """B2b: the repairable code itself must be seen CONFIRM rounds in a row, also when the check was already failing."""
    def test_b2b_one_round_of_cannot_read_after_a_confirmed_no_answer_does_not_restart(self):
        self.checks(JELLY); self.autofix('jellyfin', trial=False)
        e = good_env(http={}); self.rounds(e, settle=0)                                                  # confirmed no-answer
        read_answers(e, '/media/Shows/test.mp4', 1); watch.step(e, settle=0)                             # ONE round cannot-read
        self.assertEqual(e.restarts, [])
        e.run = FakeEnv.run.__get__(e); watch.step(e, settle=0)                                          # back to no-answer
        read_answers(e, '/media/Shows/test.mp4', 1); watch.step(e, settle=0)                             # one again, not in a row
        self.assertEqual(e.restarts, [])

    def test_b2b_two_in_a_row_restart_once_inside_the_24_hours(self):
        self.checks(JELLY); self.autofix('jellyfin', trial=False)
        e = good_env(http={}); self.rounds(e, settle=0)
        read_answers(e, '/media/Shows/test.mp4', 1); self.rounds(e, settle=0)
        self.assertEqual(e.restarts, ['jellyfin', 'audiobookshelf'])
        self.assertEqual(self.kinds(), ['needs-yes', 'broke'])                     # the restart did not help (nothing healed it)
        self.rounds(e, 3, settle=0)
        e.run = FakeEnv.run.__get__(e); self.rounds(e, settle=0); read_answers(e, '/media/Shows/test.mp4', 1); self.rounds(e, settle=0)
        self.assertEqual(e.restarts, ['jellyfin', 'audiobookshelf'], 'inside 24 hours: no second try')
        self.assertIn('already restarted', self.events[-1]['body'])

    def test_b2b_an_unknown_round_breaks_the_row(self):
        self.checks(JELLY); self.autofix('jellyfin', trial=False)
        e = good_env(http={}); self.rounds(e, settle=0)
        read_answers(e, '/media/Shows/test.mp4', 1); watch.step(e, settle=0)
        read_answers(e, '/media/Shows/test.mp4', 125); watch.step(e, settle=0)
        read_answers(e, '/media/Shows/test.mp4', 1); watch.step(e, settle=0)
        self.assertEqual(e.restarts, [])


class InARow(Base):
    """Point 5: "2 rounds in a row" means it; fail, unknown, fail is not two."""
    def test_fail_unknown_fail_raises_nothing(self):
        self.checks(JELLY); e = good_env(http={})
        watch.step(e)
        e.inside.pop('jellyfin'); watch.step(e)                                                           # cannot look inside: unknown
        e.inside['jellyfin'] = 'container-good'; watch.step(e)
        self.assertEqual(self.events, [])
        watch.step(e); self.assertEqual(self.kinds(), ['needs-yes'])


class CardSays(Base):
    """Point 3: the card says what Argus did about it, since the events file is not on any page yet."""
    def card(self, id_): return {a['file']: a['message'] for a in watch.alert_list(watch.snapshot(), lambda j: True)}['watch-' + id_]
    BASE = 'Running, but not working: cannot read its drive'

    def test_trial_day(self):
        self.checks(JELLY); self.autofix('jellyfin'); e = good_env(inside={'jellyfin': 'container-dead-shutdown'}); self.rounds(e, 3)
        self.assertEqual(self.card('jellyfin'), self.BASE + '. Argus would have restarted Jellyfin and Audiobookshelf by itself and did not,'
                         ' because for now it only notes what it would do.')

    def test_not_on_the_list(self):
        self.checks(JELLY); e = good_env(inside={'jellyfin': 'container-dead-shutdown'}); self.rounds(e, 3)
        self.assertEqual(self.card('jellyfin'), self.BASE + '. Argus did not restart it and waits for your yes.')

    def test_try_used_up(self):
        self.checks(JELLY); self.autofix('jellyfin', trial=False)
        def heal(env): env.inside['jellyfin'] = 'container-good'
        e = good_env(inside={'jellyfin': 'container-dead-shutdown'}, restart_fixes=heal); self.rounds(e, settle=0)
        self.assertEqual(self.kinds(), ['fixed'])
        e.inside['jellyfin'] = 'container-dead-gone'; self.rounds(e, settle=0)
        self.assertEqual(self.card('jellyfin'), self.BASE + '. Argus did not restart it and waits for your yes.')

    def test_a_restart_that_did_not_help(self):
        self.checks(JELLY); self.autofix('jellyfin', trial=False); e = good_env(inside={'jellyfin': 'container-dead-shutdown'}); self.rounds(e, settle=0)
        self.assertEqual(self.card('jellyfin'), self.BASE + '. Argus restarted Jellyfin and Audiobookshelf once by itself, and it did not help. It waits for your yes.')

    def test_without_a_fix_the_text_is_unchanged(self):
        self.checks(QBT); e = good_env(inside={'qbittorrent': 'container-dead-gone'}); self.rounds(e)
        self.assertEqual(self.card('qbittorrent'), self.BASE)

    def test_a_unit_that_is_down(self):
        self.checks(JELLY); e = good_env(active=False); self.rounds(e)
        self.assertEqual(self.card('jellyfin'), 'Not running. Argus did not restart it and waits for your yes.')


class DeadCopyWords(Base):
    """Point 4: a container that never had the drive gets a sentence that is true for it."""
    def test_the_two_stories(self):
        q = dict(QBT, container=dict(name='qbittorrent', mount='/downloads')); del q['http']
        self.checks(q, JELLY)
        e = good_env(inside={'qbittorrent': 'container-early', 'jellyfin': 'container-dead-shutdown'}); self.rounds(e)
        by = {x['subject']: x for x in self.events}
        self.assertIn('was started before the drive was there', by['qbittorrent']['body'])
        self.assertNotIn('unplugged', by['qbittorrent']['body'])
        self.assertIn('was unplugged and came back', by['jellyfin']['body'])
        self.assertEqual(self.result('qbittorrent')['reason'], 'cannot read its drive')


_SERVER = []
def import_server():
    """server/argus_ui.py as a module (its watch is this test's watch), with every path in a temp folder."""
    if _SERVER: return _SERVER[0]
    import importlib.util
    tmp = tempfile.mkdtemp(prefix='watch-import-'); os.makedirs(os.path.join(tmp, 'static'))
    jdump({}, os.path.join(tmp, 'static', 'theme.json'))
    for k, v in dict(ARGUS_PLUGINS=os.path.join(tmp, 'plugins'), ARGUS_BUNDLED=os.path.join(tmp, 'bundled'), ARGUS_STATIC=os.path.join(tmp, 'static'),
                     ARGUS_LINKS=os.path.join(tmp, 'links.json'), ARGUS_REGISTRY=os.path.join(tmp, 'agents'), ARGUS_ALERTS=os.path.join(tmp, 'alerts')).items():
        os.environ.setdefault(k, v)
    spec = importlib.util.spec_from_file_location('argus_ui_watch_test', os.path.join(R, 'server', 'argus_ui.py'))
    a = importlib.util.module_from_spec(spec); spec.loader.exec_module(a)
    assert a.watch is watch
    import atexit; atexit.register(shutil.rmtree, tmp, True)
    _SERVER.append(a); return a


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
        self.assertEqual(msgs, ['Running, but not working: cannot read its drive. Argus did not restart it and waits for your yes.'])
        time.sleep(3.5)                                          # three more rounds of the loop
        with open(self.events, encoding='utf-8') as f: ev = [json.loads(l) for l in f]
        self.assertEqual([(e['kind'], e['subject']) for e in ev], [('needs-yes', 'jellyfin')], 'one event, not one per round')
        self.assertEqual(ev[0]['title'], 'Jellyfin runs, but cannot read its drive')
        units = jload(self.units_file); self.assertEqual(units['jellyfin']['ActiveState'], 'active')   # nothing was restarted


if __name__ == '__main__':
    unittest.main()
