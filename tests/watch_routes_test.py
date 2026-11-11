"""Watch that points at the trouble, server side (docs/checks.md "Your yes from the page", "What happened lately"). No browser.

    python3 tests/watch_routes_test.py -v        (tests/run.sh runs it under "== watch works")

  * the owner's yes: ask_fix() refuses in plain words, or queues exactly the declared fix, which the loop runs through repair()
  * api/events (newest first, at most 100), api/watch/fix (refusals and one real fix), api/<id>/status passing `count`,
    `restarts` on each task, and podman called with --events-backend=none (a real server in its own process)
  * the seams with phone alerts (4.40): one buzz for a gone drive that names the programs on it, no buzz for what the owner's own
    press caused a moment ago, the daily summary saying who restarted it; a server restart during a repair (R1)"""
import json, os, shutil, socket, subprocess, sys, tempfile, threading, time, unittest, urllib.error, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from watch_works_test import Base, FakeEnv, JELLY, ABS, QBT, DRIVE, GOOD, good_env, put, jload, jdump, R, FX, WFX
from datetime import datetime
import notify, push, summary, watch


def d2_msg(t):
    code, d = t.post('api/watch/fix', {'id': 'jellyfin'}); t.assertEqual(code, 409, 'a second press at once is refused'); t.assertIn('Give it 2 minutes', d['msg'])
    return d['msg']


class PodmanFlag(unittest.TestCase):
    """--events-backend=none: without it each `podman exec` writes 2 journal lines (about 14,000 a day from the watch)."""
    def test_podman_gets_the_flag_before_exec(self):
        self.assertEqual(watch.runtime({'name': 'x'}), ['podman', '--events-backend=none'])
        self.assertEqual(watch.runtime({'name': 'x', 'runtime': ['python', '/t/fake_podman.py']}), ['python', '/t/fake_podman.py', '--events-backend=none'])
        self.assertEqual(watch.runtime({'name': 'x', 'runtime': '/usr/bin/podman'}), ['/usr/bin/podman', '--events-backend=none'])

    def test_another_runtime_gets_no_flag_it_does_not_know(self):
        self.assertEqual(watch.runtime({'name': 'x', 'runtime': 'docker'}), ['docker'])

    def test_every_exec_of_a_round_carries_it(self):
        e = FakeEnv(inside={'jellyfin': 'container-good'}, reads={'/media/Shows/test.mp4'})
        watch.evaluate(dict(JELLY, http=None), e)
        self.assertTrue(e.calls)
        for argv in e.calls: self.assertEqual(argv[argv.index('exec') - 1], '--events-backend=none', argv)


class OwnerYes(Base):
    """POST api/watch/fix, as the watch sees it: ask_fix() checks and queues, the next round runs the declared fix."""
    def setUp(self):
        super().setUp()
        for x in (watch.PENDING, watch.FIXING, watch.ASKED): x.clear()
        watch.WAKE.clear()

    def broken(self, **kw):
        self.checks(JELLY, QBT, DRIVE)
        e = good_env(inside={'jellyfin': 'container-dead-shutdown', 'audiobookshelf': 'container-good', 'qbittorrent': 'container-good'}, **kw)
        self.rounds(e, settle=0)
        self.assertIs(self.result('jellyfin')['works'], False); self.assertEqual(self.kinds(), ['needs-yes'])
        return e

    def test_refusals_in_plain_words(self):
        e = self.broken()
        ok, code, msg = watch.ask_fix('nothing-here', now=e.t); self.assertEqual((ok, code), (False, 404)); self.assertIn('no check with that name', msg)
        ok, code, msg = watch.ask_fix('qbittorrent', now=e.t); self.assertEqual((ok, code), (False, 409)); self.assertIn('has no fix', msg)
        ok, code, msg = watch.ask_fix('media-drive', now=e.t); self.assertEqual((ok, code), (False, 409))   # the drive check has no fix either
        ok, code, msg = watch.ask_fix('jellyfin', frozen={'mnemosyne-jellyfin': {}}, now=e.t); self.assertEqual((ok, code), (False, 409)); self.assertIn('paused (frozen)', msg)
        ok, code, msg = watch.ask_fix('jellyfin', frozen={'audiobookshelf': {}}, now=e.t); self.assertIn('paused (frozen)', msg)   # a unit its fix restarts
        ok, code, msg = watch.ask_fix('jellyfin', on=False, now=e.t); self.assertEqual((ok, code), (False, 409)); self.assertIn('switched off', msg)
        self.assertEqual(watch.PENDING, set()); self.assertEqual(e.restarts, [])
        e.inside['jellyfin'] = 'container-good'; watch.step(e, settle=0)
        ok, code, msg = watch.ask_fix('jellyfin', now=e.t); self.assertEqual((ok, code), (False, 409)); self.assertIn('works right now', msg)

    def test_a_second_press_within_two_minutes_is_refused(self):
        e = self.broken()
        ok, code, msg = watch.ask_fix('jellyfin', now=e.t); self.assertTrue(ok, msg); self.assertIn('Restarting Jellyfin and Audiobookshelf', msg)
        ok, code, msg = watch.ask_fix('jellyfin', now=e.t + 30); self.assertEqual((ok, code), (False, 409)); self.assertIn('Give it 2 minutes', msg)
        watch.step(e, settle=0)                                   # it runs, and does not help
        ok, code, msg = watch.ask_fix('jellyfin', now=e.t + 60); self.assertFalse(ok)
        ok, code, msg = watch.ask_fix('jellyfin', now=e.t + 121); self.assertTrue(ok, msg)

    def test_argus_real_try_counts_but_a_trial_does_not(self):
        e = self.broken()
        watch.PREV['jellyfin'].update(last_try=e.t - 10, last_try_trial=False)
        self.assertFalse(watch.ask_fix('jellyfin', now=e.t)[0])
        watch.PREV['jellyfin'].update(last_try_trial=True)
        self.assertTrue(watch.ask_fix('jellyfin', now=e.t)[0])

    def test_the_fix_runs_exactly_once_and_it_works_again(self):
        def heal(env): env.inside['jellyfin'] = 'container-good'
        e = self.broken(restart_fixes=heal)
        self.assertTrue(watch.ask_fix('jellyfin', now=e.t)[0])
        self.assertTrue(watch.WAKE.is_set(), 'the loop is woken at once')
        row = {r['id']: r for r in watch.snapshot()}['jellyfin']
        self.assertEqual((row['queued'], row['fixing']), (True, False), 'queued: the page says so, not "Restarting it now", until the restart is sent')
        watch.step(e, settle=6)
        self.assertEqual(e.restarts, ['jellyfin', 'audiobookshelf'], 'exactly the units its fix declares, once each')
        self.assertEqual(self.kinds(), ['needs-yes', 'fixed'], 'one event for your fix')
        self.assertIn('You restarted Jellyfin and Audiobookshelf from the page at', self.events[-1]['body'])
        j = self.result('jellyfin'); self.assertIs(j['works'], True); self.assertIs(j['again'], True); self.assertIs(j['fixing'], False)
        for _ in range(3): watch.step(e, settle=0)
        self.assertEqual(e.restarts, ['jellyfin', 'audiobookshelf'], 'nothing more is restarted'); self.assertEqual(self.kinds(), ['needs-yes', 'fixed'])

    def test_a_fix_that_does_not_help_says_when_you_tried(self):
        e = self.broken()
        self.autofix('jellyfin', trial=False)                    # even with self-repair on, it does not restart again right after you
        self.assertTrue(watch.ask_fix('jellyfin', now=e.t)[0])
        t0 = e.t; watch.step(e, settle=6)                       # the restart is sent at t0; the 6 s look comes after it
        self.assertEqual(e.restarts, ['jellyfin', 'audiobookshelf'])
        self.assertEqual(self.kinds(), ['needs-yes', 'broke'])
        at = watch.clock(t0)
        self.assertRegex(at, r'^\d{1,2}:\d\d [AP]M$', 'a time as the page writes it')
        self.assertIn(f'You restarted Jellyfin and Audiobookshelf at {at}, and it did not help.', self.events[-1]['body'])
        j = self.result('jellyfin'); self.assertIs(j['works'], False)
        self.assertEqual(j['note'], f'You restarted Jellyfin and Audiobookshelf at {at}, and it did not help.')
        for _ in range(3): watch.step(e, settle=0)
        self.assertEqual(e.restarts, ['jellyfin', 'audiobookshelf'], 'no second restart'); self.assertEqual(self.kinds(), ['needs-yes', 'broke'])

    def test_it_worked_again_before_the_fix_ran(self):
        e = self.broken()
        self.assertTrue(watch.ask_fix('jellyfin', now=e.t)[0])
        e.inside['jellyfin'] = 'container-good'; watch.step(e, settle=0)
        self.assertEqual(e.restarts, []); self.assertEqual(self.kinds(), ['needs-yes', 'recovered'])

    def test_a_frozen_unit_is_never_restarted(self):
        e = self.broken()
        self.assertTrue(watch.ask_fix('jellyfin', now=e.t)[0])
        e.frozen = {'audiobookshelf'}                            # paused between the press and the round
        watch.step(e, settle=0)
        self.assertEqual(e.restarts, ['jellyfin'])

    def test_the_rows_say_what_the_page_needs(self):
        self.broken()
        j = self.result('jellyfin')
        self.assertEqual(j['fix_say'], 'Jellyfin and Audiobookshelf'); self.assertIs(j['fixing'], False); self.assertIs(j['again'], False)
        self.assertEqual(j['title_line'], 'Jellyfin runs, but cannot read its drive')
        self.assertEqual(self.result('qbittorrent')['fix_say'], '')
        d = self.result('media-drive'); self.assertIs(d['works'], True); self.assertTrue(d['since'])


class KnownBrokenStays(Base):
    """W2 point 1: an unknown round, or a result gone stale, never makes a known breakage look fine (R7 finding 1)."""
    def setUp(self):
        super().setUp()
        for x in (watch.PENDING, watch.FIXING, watch.ASKED): x.clear()

    def test_an_unknown_round_keeps_the_last_verdict_and_says_when_argus_last_looked(self):
        self.checks(JELLY); e = good_env(inside={'jellyfin': 'container-dead-shutdown'}); self.rounds(e)
        before = self.result('jellyfin'); self.assertIs(before['works'], False)
        del e.inside['jellyfin']; e.t += 60; watch.step(e, settle=0)          # podman cannot look this round (exit 125)
        j = self.result('jellyfin')
        self.assertIs(j['works'], False, 'still not working'); self.assertEqual((j['code'], j['reason']), ('dead-copy', 'cannot read its drive'))
        self.assertEqual(j['unsure'], f'Argus has not been able to look again since {watch.clock(e.t - 60)}.')
        self.assertEqual(self.kinds(), ['needs-yes'], 'no event for the unknown round')
        e.inside['jellyfin'] = 'container-dead-shutdown'; e.t += 60; watch.step(e, settle=0)
        self.assertEqual(self.result('jellyfin')['unsure'], '', 'a real look again: the sentence goes')

    def test_a_working_check_that_goes_unknown_is_not_trouble(self):
        self.checks(JELLY); e = good_env(); self.rounds(e)
        del e.inside['jellyfin']; watch.step(e, settle=0)
        j = self.result('jellyfin'); self.assertIsNone(j['works']); self.assertEqual(j['code'], 'cannot-look'); self.assertEqual(j['unsure'], '')

    def test_a_stale_result_stays_broken_and_a_stale_good_one_becomes_unknown(self):
        self.checks(JELLY, DRIVE); e = good_env(inside={'jellyfin': 'container-dead-shutdown'}); self.rounds(e)
        for v in watch.RESULTS.values(): v['at'] -= 1000                           # nobody looked for 1000 s (the loop was held)
        rows = {r['id']: r for r in watch.snapshot(interval=60)}
        j, d = rows['jellyfin'], rows['media-drive']
        self.assertIs(j['works'], False); self.assertTrue(j['stale']); self.assertRegex(j['unsure'], r'^Argus has not been able to look again since \d{1,2}:\d\d [AP]M\.$')
        self.assertIsNone(d['works']); self.assertEqual(d['code'], 'stale')


class AfterAStart(Base):
    """W3 N1: between a server start and the end of its first round, state() shows the saved verdicts, never an empty list."""
    def test_a_known_breakage_is_there_before_the_first_round(self):
        self.checks(JELLY, DRIVE)
        watch.PREV.update({'jellyfin': {'works': False, 'code': 'dead-copy', 'since': time.time() - 600, 'looked': time.time() - 70}})
        watch.LOOP[0] = True; watch.LAST_STEP[0] = 0.0
        rows = {r['id']: r for r in watch.snapshot()}
        j = rows['jellyfin']
        self.assertIs(j['works'], False); self.assertEqual(j['reason'], 'cannot read its drive')
        self.assertRegex(j['unsure'], r'^Argus has not been able to look again since \d{1,2}:\d\d [AP]M\.$')
        self.assertIsNone(rows['media-drive']['works'], 'nothing known about it yet: unknown, not trouble')
        self.assertFalse(watch.ready())

    def test_without_the_loop_there_are_no_rows(self):
        self.checks(JELLY); watch.LOOP[0] = False; watch.LAST_STEP[0] = 0.0
        self.assertEqual(watch.snapshot(), [])


class SelfRepairShows(Base):
    """W3 N3: while Argus's own repair runs, its row is the confirmed failure, says it restarts, and says who (him)."""
    def test_his_own_repair_is_published_as_a_failure_being_fixed_by_him(self):
        self.checks(JELLY); self.autofix('jellyfin', trial=False)
        gate = threading.Event(); e = good_env(inside={'jellyfin': 'container-dead-shutdown'})
        def slow(sec): gate.wait(5); e.t += sec
        e.sleep = slow; watch.JOIN = 0.3
        self.rounds(e, settle=30)                                 # round 2 confirms the failure and starts his repair
        t = watch.RUNNING.get('jellyfin'); self.assertIsNotNone(t, 'his repair runs in its thread')
        j = self.result('jellyfin')
        self.assertIs(j['works'], False, 'the confirmed failure, not the pending row of the round before')
        self.assertEqual((j['fixing'], j['by']), (True, 'argus'))
        gate.set(); t.join(5); watch.step(e, settle=0)
        self.assertEqual(self.result('jellyfin')['by'], '')
        self.assertEqual(e.restarts, ['jellyfin', 'audiobookshelf'])


class DriveGone(Base):
    """W2 point 4: a program whose drive is gone is not promised a fix; its event is true on a lock screen."""
    def test_no_yes_is_asked_and_no_restart_promised(self):
        self.checks(JELLY); e = good_env(host='host-missing'); self.rounds(e)
        j = self.result('jellyfin'); self.assertEqual(j['code'], 'drive-missing'); self.assertEqual(j['note'], '')
        self.assertEqual(self.kinds(), ['broke'])
        body = self.events[0]['body']
        self.assertIn('Argus waits for the drive: a restart would not help until it is back.', body)
        self.assertNotIn('should fix it', body); self.assertNotIn('yes', body)


def server_env(tmp, port):
    home = os.path.join(tmp, 'home')
    env = {k: v for k, v in os.environ.items() if not k.startswith('ARGUS_')}
    env.update(HOME=home, USERPROFILE=home, ARGUS_BIND='127.0.0.1', ARGUS_PORT=str(port), ARGUS_STATIC=os.path.join(tmp, 'static'),
               ARGUS_BUNDLED=os.path.join(tmp, 'none'), ARGUS_PLUGINS=os.path.join(tmp, 'plugins'), ARGUS_CHECKS=os.path.join(tmp, 'checks.json'),
               ARGUS_AUTOFIX=os.path.join(tmp, 'auto-fix.json'), ARGUS_MOUNTINFO=os.path.join(WFX, 'host-good.mountinfo'),
               ARGUS_EVENTS=os.path.join(tmp, 'events.jsonl'), ARGUS_WATCH_STATE=os.path.join(tmp, 'watch.json'), ARGUS_WATCH_INTERVAL='1',
               FAKE_PODMAN_DIR=os.path.join(tmp, 'pod'), ARGUS_ALERTS=os.path.join(tmp, 'alerts'), ARGUS_REGISTRY=os.path.join(tmp, 'reg'),
               ARGUS_SUMMARY='0')          # no daily summary event in the events file (between 08:00 and 12:00 it would go out at start)
    return env


COUNT_PLUGIN = '''
def get(path, query, ctx):
    if path == 'status': return 200, {'line': '3 waiting', 'needs': True, 'action': 'Open it', 'count': 3}
    if path == 'status-bool': return 200, {}
    return 404, {}
'''


class Routes(unittest.TestCase):
    """The server in its own process: fake systemctl and podman, canned mount tables, a one-second loop."""
    @classmethod
    def setUpClass(cls):
        cls.tmp = t = tempfile.mkdtemp(prefix='watch-routes-')
        for d in ('home', 'static', 'pod', 'plugins/countdemo'): os.makedirs(os.path.join(t, d))
        fx = os.path.join(t, 'fx'); shutil.copytree(FX, fx, ignore=shutil.ignore_patterns('controllers-sysfs', 'memory'))
        shutil.copy(os.path.join(R, 'themes', 'leafy-realm', 'theme.json'), os.path.join(t, 'static'))
        units = jload(os.path.join(fx, 'units.json'))
        units['hermes-once'] = {'Result': 'success', 'ActiveState': 'inactive', 'Type': 'oneshot'}     # no timer, but it runs and ends
        units['jellyfin'] = {'Result': 'success', 'ActiveState': 'active'}
        jdump(units, os.path.join(fx, 'units.json'))
        if os.name == 'nt':
            sysctl = os.path.join(t, 'systemctl.cmd'); put(sysctl, f'@"{sys.executable}" "{os.path.join(fx, "fake_systemctl.py")}" %*\r\n')
        else:
            sysctl = os.path.join(fx, 'fake_systemctl.py'); os.chmod(sysctl, 0o755)
        jdump({'id': 'countdemo', 'name': 'Count demo', 'kind': 'server'}, os.path.join(t, 'plugins/countdemo/plugin.json'))
        put(os.path.join(t, 'plugins/countdemo/plugin.py'), COUNT_PLUGIN); put(os.path.join(t, 'plugins/countdemo/page.js'), '')
        shutil.copy(os.path.join(WFX, 'container-dead-shutdown.mountinfo'), os.path.join(t, 'pod', 'jellyfin.mountinfo'))
        put(os.path.join(t, 'pod', 'jellyfin.readable'), '/media/Shows/test.mp4\n')
        pod = [sys.executable, os.path.join(fx, 'fake_podman.py')]
        jdump({'checks': [dict(JELLY, container=dict(JELLY['container'], runtime=pod), http=None),
                          dict(QBT, container=dict(QBT['container'], runtime=pod), http=None, unit=None)]}, os.path.join(t, 'checks.json'))
        with socket.socket() as s: s.bind(('127.0.0.1', 0)); cls.port = s.getsockname()[1]
        env = server_env(t, cls.port); env['ARGUS_SYSTEMCTL'] = sysctl
        cls.events = env['ARGUS_EVENTS']; cls.fx = fx; cls.env = env
        cls.log = open(os.path.join(t, 'server.log'), 'w')
        cls.proc = subprocess.Popen([sys.executable, os.path.join(R, 'server', 'argus_ui.py')], env=env, stdout=cls.log, stderr=cls.log)
        for _ in range(150):
            try: socket.create_connection(('127.0.0.1', cls.port), timeout=1).close(); break
            except OSError: time.sleep(.1)
        else: cls.tearDownClass(); raise RuntimeError('the server did not start')

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        try: cls.proc.wait(10)
        except subprocess.TimeoutExpired: cls.proc.kill(); cls.proc.wait(10)
        cls.log.close(); shutil.rmtree(cls.tmp, ignore_errors=True)

    def url(self, p): return f'http://127.0.0.1:{self.port}/argus/{p}'

    def get(self, p):
        try:
            with urllib.request.urlopen(self.url(p), timeout=10) as r: return r.status, json.load(r)
        except urllib.error.HTTPError as e: return e.code, json.load(e)

    def post(self, p, body, ctype='application/json', headers=None):
        h = {'Content-Type': ctype, **(headers or {})}
        req = urllib.request.Request(self.url(p), data=json.dumps(body).encode(), headers=h, method='POST')
        try:
            with urllib.request.urlopen(req, timeout=10) as r: return r.status, json.load(r)
        except urllib.error.HTTPError as e: return e.code, json.load(e)

    def wait_for(self, fn, secs=20):
        end = time.time() + secs
        while time.time() < end:
            v = fn()
            if v: return v
            time.sleep(.25)
        self.fail('waited %d s; log: %s' % (secs, os.path.join(self.tmp, 'server.log')))

    def row(self, id_): return {w['id']: w for w in self.get('api/state')[1]['watch']}.get(id_, {})

    def test_1_events_newest_first_and_capped(self):
        code, d = self.get('api/events'); self.assertEqual(code, 200); self.assertIn('since', d); self.assertIsInstance(d['events'], list)
        with open(self.events, 'a', encoding='utf-8') as f:
            for i in range(120): f.write(json.dumps({'id': f'e{i}', 'at': '2026-11-11T04:%02d:00-07:00' % (i % 60), 'kind': 'recovered', 'subject': 's', 'title': f'Event {i}', 'body': '', 'url': '', 'level': 'info', 'extra': 'x'}) + '\n')
            f.write('not json\n')
        code, d = self.get('api/events?limit=2'); self.assertEqual(code, 200)
        self.assertEqual([e['title'] for e in d['events']], ['Event 119', 'Event 118'], 'newest first; a damaged line is skipped')
        self.assertEqual(sorted(d['events'][0]), sorted(['id', 'at', 'kind', 'subject', 'title', 'body', 'url', 'level']), 'only the event fields go out')
        self.assertEqual(len(self.get('api/events?limit=500')[1]['events']), 100, 'at most 100')
        self.assertEqual(len(self.get('api/events')[1]['events']), 10, 'ten by default')
        for bad in ('abc', '-3', '2.5', '%C2%B2', '12345', '9' * 5000, '', '%20'): self.assertEqual(self.get('api/events?limit=' + bad)[0], 400, bad[:9])
        self.assertEqual(len(self.get('api/events?limit=0')[1]['events']), 1, '0 is a number: at least one')

    def test_2_status_passes_count(self):
        code, d = self.get('api/countdemo/status'); self.assertEqual(code, 200)
        self.assertEqual(d, {'line': '3 waiting', 'needs': True, 'action': 'Open it', 'count': 3})

    def test_3_each_task_says_whether_its_button_restarts(self):
        jobs = {j['job']: j for j in self.get('api/state')[1]['jobs']}
        self.assertIs(jobs['hermes-mail']['restarts'], True, 'always on: Restart')
        self.assertIs(jobs['hermes-sort']['restarts'], False, 'a timer: Run')
        self.assertIs(jobs['hermes-once']['restarts'], False, 'oneshot: Run')

    def test_4_podman_is_called_with_events_off(self):
        log = os.path.join(self.tmp, 'pod', 'calls.log')
        self.wait_for(lambda: os.path.exists(log))
        with open(log) as f: calls = [l.split() for l in f if l.strip()]
        self.assertTrue(calls)
        for c in calls: self.assertEqual(c[:2], ['--events-backend=none', 'exec'], c)

    def test_5_fix_refusals(self):
        self.wait_for(lambda: self.row('jellyfin').get('works') is False)
        self.assertEqual(self.post('api/watch/fix', {'id': 'jellyfin'}, ctype='text/plain')[0], 415, 'JSON only')
        self.assertEqual(self.post('api/watch/fix', {'id': 'jellyfin'}, headers={'Sec-Fetch-Site': 'cross-site'})[0], 403)
        self.assertEqual(self.post('api/watch/fix', {'id': 'jellyfin'}, headers={'Origin': 'http://evil.example'})[0], 403)
        for body in ({}, {'id': 5}, {'id': '../x'}, {'id': 'Jellyfin'}): self.assertEqual(self.post('api/watch/fix', body)[0], 400, body)
        code, d = self.post('api/watch/fix', {'id': 'nothing-here'}); self.assertEqual((code, d['ok']), (404, False)); self.assertIn('no check', d['msg'])
        code, d = self.post('api/watch/fix', {'id': 'qbittorrent'}); self.assertEqual(code, 409); self.assertIn('has no fix', d['msg'])
        fz = os.path.join(self.tmp, 'reg', 'frozen.json'); os.makedirs(os.path.dirname(fz), exist_ok=True); jdump({'mnemosyne-jellyfin': {'at': 'x'}}, fz)
        try:
            code, d = self.post('api/watch/fix', {'id': 'jellyfin'}); self.assertEqual(code, 409); self.assertIn('paused (frozen)', d['msg'])
        finally: os.remove(fz)
        self.assertFalse(os.path.exists(os.path.join(self.fx, 'restarts.log')), 'nothing was restarted')

    def test_6_the_owner_fix_runs_once_and_works_again(self):
        self.wait_for(lambda: self.row('jellyfin').get('works') is False)
        code, d = self.post('api/watch/fix', {'id': 'jellyfin'}); self.assertEqual((code, d['ok']), (200, True), d)
        self.assertIn('Restarting Jellyfin and Audiobookshelf', d['msg'])
        self.assertRegex(d2_msg(self), r'started at \d{1,2}:\d\d [AP]M\.')
        self.wait_for(lambda: os.path.exists(os.path.join(self.fx, 'restarts.log')))                                     # the restart ran ...
        shutil.copy(os.path.join(WFX, 'container-good.mountinfo'), os.path.join(self.tmp, 'pod', 'jellyfin.mountinfo'))   # ... and helped
        self.wait_for(lambda: self.row('jellyfin').get('works') is True and not self.row('jellyfin').get('fixing'))
        self.assertIs(self.row('jellyfin')['again'], True)
        with open(os.path.join(self.fx, 'restarts.log')) as f: self.assertEqual(f.read().split(), ['jellyfin.service', 'audiobookshelf.service'])
        evs = self.get('api/events?limit=5')[1]['events']
        mine = [e for e in evs if e['subject'] == 'jellyfin']
        self.assertEqual(mine[0]['kind'], 'fixed'); self.assertIn('You restarted Jellyfin and Audiobookshelf from the page', mine[0]['body'])
        code, d = self.post('api/watch/fix', {'id': 'jellyfin'}); self.assertEqual(code, 409); self.assertIn('works right now', d['msg'])


class TwoFixes(Routes):
    """W2 point 2: two fixes asked one after another. The second unit is restarted within seconds of its request (not after the
    first one's 90-second wait), and every other check keeps its rounds meanwhile (nothing goes stale)."""
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        t = cls.tmp; pod = [sys.executable, os.path.join(cls.fx, 'fake_podman.py')]
        shutil.copy(os.path.join(WFX, 'container-dead-gone.mountinfo'), os.path.join(t, 'pod', 'abs.mountinfo'))
        jdump({'checks': [dict(JELLY, container=dict(JELLY['container'], runtime=pod), http=None, fix=dict(restart=['jellyfin'], say='Jellyfin')),
                          dict(ABS, unit=None, container=dict(name='abs', dir='/audiobooks', runtime=pod), fix=dict(restart=['abs-unit'], say='Audiobookshelf')),
                          dict(DRIVE)]}, os.path.join(t, 'checks.json'))
        units = jload(os.path.join(cls.fx, 'units.json')); units['abs-unit'] = {'Result': 'success', 'ActiveState': 'active'}
        jdump(units, os.path.join(cls.fx, 'units.json'))

    def test_1_events_newest_first_and_capped(self): pass
    def test_2_status_passes_count(self): pass
    def test_3_each_task_says_whether_its_button_restarts(self): pass
    def test_4_podman_is_called_with_events_off(self): pass
    def test_5_fix_refusals(self): pass
    def test_6_the_owner_fix_runs_once_and_works_again(self): pass

    def restarted(self):
        f = os.path.join(self.fx, 'restarts.log')
        return open(f).read().split() if os.path.exists(f) else []

    def test_7_the_second_fix_does_not_wait_for_the_first(self):
        self.wait_for(lambda: self.row('jellyfin').get('works') is False and self.row('audiobookshelf').get('works') is False)
        self.assertEqual(self.post('api/watch/fix', {'id': 'jellyfin'})[0], 200)
        self.wait_for(lambda: 'jellyfin.service' in self.restarted(), 10)
        q = self.row('jellyfin'); self.assertIs(q['fixing'], True, 'sent: now it says "Restarting it now"')
        t0 = time.time(); self.assertEqual(self.post('api/watch/fix', {'id': 'audiobookshelf'})[0], 200)
        self.wait_for(lambda: 'abs-unit.service' in self.restarted(), 8)
        self.assertLess(time.time() - t0, 8, 'the second unit is restarted within seconds, while the first still waits')
        self.assertIs(self.row('jellyfin')['fixing'], True, 'the first one is still looking (it does not get better here)')
        for _ in range(12):                                   # 6 s: the drive check keeps its rounds, nothing goes stale
            r = self.row('media-drive'); self.assertIs(r.get('works'), True, r)
            time.sleep(.5)
        self.assertEqual(self.restarted().count('jellyfin.service'), 1); self.assertEqual(self.restarted().count('abs-unit.service'), 1)

    def test_8_the_loop_keeps_its_rounds_while_a_repair_waits(self):
        # the drive check's last real look keeps moving while both repairs above are still waiting (they do not heal here)
        a = self.row('media-drive').get('looked'); time.sleep(3.5); b = self.row('media-drive').get('looked')
        self.assertTrue(a and b and b > a, f'looked {a} -> {b}')


class ServerRestart(Routes):
    """W3 N1 on a real server: Jellyfin is broken, the server starts again with a slow first round (3 s per podman call). Its very
    first answer already shows Jellyfin broken (from watch.json), and says the first round has not finished."""
    def test_1_events_newest_first_and_capped(self): pass
    def test_2_status_passes_count(self): pass
    def test_3_each_task_says_whether_its_button_restarts(self): pass
    def test_4_podman_is_called_with_events_off(self): pass
    def test_5_fix_refusals(self): pass
    def test_6_the_owner_fix_runs_once_and_works_again(self): pass

    def test_9_a_restart_never_shows_an_empty_watch(self):
        self.wait_for(lambda: self.row('jellyfin').get('works') is False)
        time.sleep(1.5)                                           # one more round, so watch.json holds it
        cls = type(self); cls.proc.terminate(); cls.proc.wait(10)
        cls.proc = subprocess.Popen([sys.executable, os.path.join(R, 'server', 'argus_ui.py')], env=dict(cls.env, FAKE_PODMAN_DELAY='3'), stdout=cls.log, stderr=cls.log)
        first = None
        for _ in range(150):
            try: first = self.get('api/state')[1]; break
            except OSError: time.sleep(.1)
        self.assertIsNotNone(first, 'the server came back')
        self.assertIs(first['watch_ready'], False, 'its first round has not finished')
        j = {w['id']: w for w in first['watch']}.get('jellyfin', {})
        self.assertIs(j.get('works'), False, f'Jellyfin is still shown broken, not missing: {first["watch"]}')
        self.assertTrue(j.get('unsure'))
        self.wait_for(lambda: self.get('api/state')[1]['watch_ready'] is True, 30)
        self.assertIs(self.row('jellyfin')['works'], False)


class Recorder:
    def __init__(self): self.jobs = []
    def put(self, job): self.jobs.append(job)


class PhoneSeams(Base):
    """4.40: what the phone alerts (#47, server/push.py) and the daily summary (server/summary.py) make of the watch's events.
    push.sink decides on one device of the owner; the encryption package is stubbed out, because nothing is encrypted or sent
    here: the Recorder takes the jobs the sink would hand the sender."""
    def setUp(self):
        super().setUp()
        for x in (watch.PENDING, watch.FIXING, watch.ASKED): x.clear()
        self.push = {k: getattr(push, k) for k in ('sender', 'crypto', 'role_of', 'gate', 'name_of')}
        os.environ['ARGUS_PUSH_DEVICES'] = os.path.join(self.tmp, 'push-devices.json')
        push.save_devices([{'id': 'phone-1', 'person': 'owner', 'label': 'Phone', 'endpoint': 'https://fcm.googleapis.com/fcm/send/x',
                            'keys': {}, 'kinds': list(push.KINDS), 'made': '', 'last_ok': '', 'last_error': ''}])
        push.sender, push.crypto, push.gate = Recorder(), (lambda: {'stub': True}), push.Gate()
        push.role_of = lambda person: 'owner' if person == 'owner' else 'none'
        notify.SINKS[:] = [self.events.append, push.sink]

    def tearDown(self):
        for k, v in self.push.items(): setattr(push, k, v)
        os.environ.pop('ARGUS_PUSH_DEVICES', None)
        super().tearDown()

    def buzzes(self): return [json.loads(j['raw']) for j in push.sender.jobs]

    # ---- 2b: one unplugged drive, one buzz ----
    def test_2b_one_gone_drive_buzzes_once_and_names_the_programs(self):
        # R7c's setup: the media programs have no unit of their own (they are containers), and the drive has its own check
        self.checks(DRIVE, dict(JELLY, unit=None), dict(ABS, unit=None), QBT)
        e = good_env(host='host-missing'); self.rounds(e)
        self.assertEqual([(x['kind'], x['subject']) for x in self.events], [('broke', 'media-drive')], 'one event for the drive, none per program')
        self.assertEqual(self.events[0]['title'], 'The media drive is not connected; Jellyfin, Audiobookshelf and 1 more cannot read it')
        self.assertEqual([(b['kind'], b['title']) for b in self.buzzes()],
                         [('broke', 'The media drive is not connected; Jellyfin, Audiobookshelf and 1 more cannot read it')], 'one buzz')
        for id_ in ('jellyfin', 'audiobookshelf', 'qbittorrent'):
            r = self.result(id_); self.assertIs(r['works'], False, id_); self.assertEqual(r['code'], 'drive-missing', id_)   # the rows still say why
        for _ in range(3): watch.step(e)
        self.assertEqual(len(self.events), 1, 'nothing more while it stays gone')
        e.host = 'host-good'; watch.step(e)
        self.assertEqual([(x['kind'], x['subject']) for x in self.events], [('broke', 'media-drive'), ('recovered', 'media-drive')],
                         'it comes back: one recovered, for the drive (the quiet programs were never said to be broken)')
        self.assertEqual(len(self.buzzes()), 1, 'a recovery never buzzes')

    def test_2b_a_second_check_of_the_same_drive_is_folded_too(self):
        backup = dict(DRIVE, id='media-backup-drive', title='The media drive (backup check)', job='mnemosyne-backup-drive')
        self.checks(DRIVE, backup, dict(JELLY, unit=None))
        self.rounds(good_env(host='host-dropped'))
        self.assertEqual([(x['kind'], x['subject'], x['title']) for x in self.events],
                         [('broke', 'media-drive', 'The media drive has dropped out; Jellyfin cannot read it')])
        self.assertEqual(len(self.buzzes()), 1)

    def test_2b_read_only_and_two_names(self):
        self.checks(dict(JELLY, unit=None), DRIVE, ABS)                         # the drive need not come first in the file
        self.rounds(good_env(host='host-readonly'))
        self.assertEqual([x['title'] for x in self.events], ['The media drive is read-only; Jellyfin and Audiobookshelf cannot save to it'])

    def test_2b_without_programs_on_it_the_words_are_as_before(self):
        self.checks(DRIVE); self.rounds(good_env(host='host-missing'))
        self.assertEqual([x['title'] for x in self.events], ['The media drive is not connected'])

    # ---- 2c: his own press ----
    def broken_jellyfin(self, **kw):
        self.checks(dict(JELLY, http=None))
        e = good_env(inside={'jellyfin': 'container-dead-shutdown'}, **kw); self.rounds(e, settle=0)
        self.assertEqual([b['kind'] for b in self.buzzes()], ['needs-yes'], 'the breakage itself buzzes, as before')
        return e

    def test_2c_his_own_try_that_did_not_help_does_not_buzz_right_after_his_press(self):
        e = self.broken_jellyfin()
        self.assertTrue(watch.ask_fix('jellyfin', now=e.t)[0]); watch.step(e, settle=6)
        ev = self.events[-1]
        self.assertEqual((ev['kind'], ev['by']), ('broke', 'owner')); self.assertIn('You restarted Jellyfin and Audiobookshelf at', ev['body'])
        self.assertEqual(ev['pressed'], watch.iso(watch.PREV['jellyfin']['owner_try']), 'when he pressed')
        self.assertEqual([b['kind'] for b in self.buzzes()], ['needs-yes'], 'his own try did not help: the page says so, the phone keeps still')
        self.assertEqual(self.kinds(), ['needs-yes', 'broke'], 'it is still an event: the events file, the page and the summary have it')
        pressed = datetime.fromisoformat(ev['pressed']).timestamp()
        self.assertTrue(push.own_press(ev, now=pressed + 100), '100 s after the press: no buzz (a 90-second look ends about here)')
        self.assertFalse(push.own_press(ev, now=pressed + 121), 'more than 2 minutes after his press: it buzzes as any other')
        push.sink(dict(ev, pressed=watch.iso(time.time() - 180)))
        self.assertEqual([b['kind'] for b in self.buzzes()], ['needs-yes', 'broke'], 'an outcome 3 minutes after the press buzzes')

    def test_2c_a_restart_command_that_failed_from_his_press_does_not_buzz_either(self):
        e = self.broken_jellyfin()
        e.restart = lambda u: (False, 'Failed to restart')
        self.assertTrue(watch.ask_fix('jellyfin', now=e.t)[0]); watch.step(e, settle=6)
        self.assertEqual((self.events[-1]['kind'], self.events[-1]['by']), ('broke', 'owner'))
        self.assertIn('but the restart did not work', self.events[-1]['body'])
        self.assertEqual([b['kind'] for b in self.buzzes()], ['needs-yes'])

    def test_2c_argus_own_repair_that_did_not_help_still_buzzes(self):
        self.checks(dict(JELLY, http=None)); self.autofix('jellyfin', trial=False)
        e = good_env(inside={'jellyfin': 'container-dead-shutdown'}); self.rounds(e, settle=6)
        self.assertEqual([(x['kind'], x.get('by')) for x in self.events], [('broke', 'argus')])
        self.assertNotIn('pressed', self.events[-1])
        self.assertEqual([b['kind'] for b in self.buzzes()], ['broke'], 'nobody pressed anything: it buzzes')

    # ---- 2a: the daily summary says who restarted it ----
    def summary_of(self):
        return summary.compose(list(reversed(self.events)), watch.snapshot(), datetime.now().astimezone())

    def test_2a_his_own_restart_reads_as_his(self):
        def heal(env): env.inside['jellyfin'] = 'container-good'
        e = self.broken_jellyfin(restart_fixes=heal)
        self.assertTrue(watch.ask_fix('jellyfin', now=e.t)[0]); watch.step(e, settle=6)
        self.assertEqual((self.events[-1]['kind'], self.events[-1]['by']), ('fixed', 'owner'))
        self.assertEqual([b['kind'] for b in self.buzzes()], ['needs-yes'], 'a fixed never buzzes')
        s = self.summary_of()
        self.assertEqual(s['title'], 'Yesterday: 1 thing stopped working, you fixed it')
        self.assertEqual(s['body'], 'You restarted Jellyfin from the page, and it works now. Nothing waits for you.')
        self.assertNotIn('as you allowed', s['body'])

    def test_2a_argus_own_restart_still_reads_as_his(self):
        def heal(env): env.inside['jellyfin'] = 'container-good'
        self.checks(dict(JELLY, http=None)); self.autofix('jellyfin', trial=False)
        e = good_env(inside={'jellyfin': 'container-dead-shutdown'}, restart_fixes=heal); self.rounds(e, settle=6)
        self.assertEqual([(x['kind'], x.get('by')) for x in self.events], [('fixed', 'argus')])
        self.assertEqual(self.buzzes(), [], 'he fixed it before anyone was told: nothing buzzes')

    def test_2a_both_on_one_day(self):
        now = datetime.now().astimezone()
        ev = [notify.make('fixed', 'jellyfin', 'x', '', at=now), dict(notify.make('fixed', 'backup', 'x', '', at=now), by='owner'),
              notify.make('needs-yes', 'jellyfin', 'x', '', at=now), notify.make('broke', 'backup', 'x', '', at=now)]
        rows = [{'id': 'jellyfin', 'title': 'Jellyfin', 'works': True}, {'id': 'backup', 'title': 'Backups', 'works': True}]
        s = summary.compose(ev, rows, now)
        self.assertEqual(s['title'], 'Yesterday: 2 things stopped working, and all work again')
        self.assertEqual(s['body'], 'You restarted Backups from the page, and it works now. Argus restarted Jellyfin as you allowed, and it works now. Nothing waits for you.')


class RepairLostInARestart(Base):
    """R7c R1: the server restarts while a repair runs (a deploy inside the 90 seconds). The repair's thread dies with it and its
    outcome never arrives. The row then says what is known, never "Did not restart it": the restart was sent."""
    def setUp(self):
        super().setUp()
        for x in (watch.PENDING, watch.FIXING, watch.ASKED): x.clear()
        self.gate = threading.Event()

    def held(self, **kw):
        e = good_env(inside={'jellyfin': 'container-dead-shutdown'}, **kw)
        def slow(sec): self.gate.wait(10); e.t += sec      # the 90-second look waits here until the "old process" is gone
        e.sleep = slow; watch.JOIN = 0.3
        return e

    def restart_the_server(self):
        t = watch.RUNNING.get('jellyfin'); self.assertIsNotNone(t, 'the repair is running')
        self.gate.set(); t.join(10)                            # the old thread ends; its outcome is lost with the old process
        watch.RESULTS.clear(); watch.PREV.clear()
        for x in (watch.PENDING, watch.FIXING, watch.ASKED, watch.RUNNING, watch.SENT, watch.OUTCOMES, watch.INFLIGHT, watch.BY): x.clear()
        watch.WAKE.clear(); watch.load_prev(); watch.LOOP[0] = True; watch.LAST_STEP[0] = 0.0

    def test_r1_his_own_press(self):
        self.checks(dict(JELLY, http=None)); e = self.held(); self.rounds(e, settle=90)
        self.assertTrue(watch.ask_fix('jellyfin', now=e.t)[0]); t0 = e.t
        watch.step(e, settle=90)
        j = self.result('jellyfin'); self.assertEqual((j['fixing'], j['by']), (True, 'owner')); self.assertEqual(j['note'], '', 'while it runs: the page says "Restarting it now"')
        self.restart_the_server()
        want = f'You restarted Jellyfin and Audiobookshelf at {watch.clock(t0)}, but Argus himself was restarted before he could see whether it helped.'
        j = self.result('jellyfin')
        self.assertIs(j['works'], False); self.assertEqual(j['note'], want, 'before the first round after the start (saved rows)')
        self.assertFalse(j['fixing']); self.assertFalse(j['queued'])
        e.t += 30; watch.step(e, settle=0)
        self.assertEqual(self.result('jellyfin')['note'], want, 'and after it, while it still does not work')
        self.assertEqual(self.kinds(), ['needs-yes'], 'no event is made up for the lost try')
        self.assertFalse(watch.ask_fix('jellyfin', now=t0 + 60)[0], 'the 2-minute rule holds across the restart')
        e.inside['jellyfin'] = 'container-good'; e.t += 30; watch.step(e, settle=0)
        self.assertEqual(self.kinds(), ['needs-yes', 'recovered'], 'when it works again, the usual recovered event')

    def test_r1_his_own_repair(self):
        self.checks(dict(JELLY, http=None)); self.autofix('jellyfin', trial=False)
        e = self.held(); self.rounds(e, settle=90)
        t0 = watch.PREV['jellyfin']['last_try']
        self.assertEqual(self.result('jellyfin')['note'], '', 'while it runs: the page says "Restarting it now by himself"')
        self.restart_the_server()
        want = (f'Argus restarted Jellyfin and Audiobookshelf by himself at {watch.clock(t0)}, but was restarted himself before he could '
                'see whether it helped. It waits for your yes.')
        self.assertEqual(self.result('jellyfin')['note'], want)
        n = len(e.restarts); e.t += 30; watch.step(e, settle=0)
        self.assertEqual(self.result('jellyfin')['note'], want)
        self.assertEqual(len(e.restarts), n, 'he does not try again by himself (once a day)')


class ServerRestartDuringRepair(Routes):
    """R7c R1 on a real server: the owner's restart is sent, then the server restarts during its 90-second look."""
    def test_1_events_newest_first_and_capped(self): pass
    def test_2_status_passes_count(self): pass
    def test_3_each_task_says_whether_its_button_restarts(self): pass
    def test_4_podman_is_called_with_events_off(self): pass
    def test_5_fix_refusals(self): pass
    def test_6_the_owner_fix_runs_once_and_works_again(self): pass

    def test_9_the_block_says_his_restart_was_sent(self):
        self.wait_for(lambda: self.row('jellyfin').get('works') is False)
        self.assertEqual(self.post('api/watch/fix', {'id': 'jellyfin'})[0], 200)
        self.wait_for(lambda: os.path.exists(os.path.join(self.fx, 'restarts.log')), 10)       # sent; the 90-second look begins
        self.wait_for(lambda: self.row('jellyfin').get('fixing') is True, 10)
        cls = type(self); cls.proc.terminate(); cls.proc.wait(10)
        cls.proc = subprocess.Popen([sys.executable, os.path.join(R, 'server', 'argus_ui.py')], env=cls.env, stdout=cls.log, stderr=cls.log)
        self.wait_for(lambda: self.state_or_none() and self.state_or_none()['watch_ready'] is True, 30)
        j = self.row('jellyfin')
        self.assertIs(j['works'], False); self.assertFalse(j['fixing']); self.assertFalse(j['queued'])
        self.assertRegex(j['note'], r'^You restarted Jellyfin and Audiobookshelf at \d{1,2}:\d\d [AP]M, but Argus himself was restarted before he could see whether it helped\.$')
        self.assertNotIn('Did not restart it', j['note']); self.assertNotIn('did not restart it', j['note'])
        with open(self.events, encoding='utf-8') as f: mine = [json.loads(l) for l in f if '"jellyfin"' in l]
        self.assertEqual([e['kind'] for e in mine], ['needs-yes'], 'no event is made up for the lost try')
        code, d = self.post('api/watch/fix', {'id': 'jellyfin'}); self.assertEqual(code, 409); self.assertIn('Give it 2 minutes', d['msg'])

    def state_or_none(self):
        try: return self.get('api/state')[1]
        except OSError: return None


if __name__ == '__main__':
    unittest.main()
