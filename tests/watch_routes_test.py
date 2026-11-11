"""Watch that points at the trouble, server side (docs/checks.md "Your yes from the page", "What happened lately"). No browser.

    python3 tests/watch_routes_test.py -v        (tests/run.sh runs it under "== watch works")

  * the owner's yes: ask_fix() refuses in plain words, or queues exactly the declared fix, which the loop runs through repair()
  * api/events (newest first, at most 100), api/watch/fix (refusals and one real fix), api/<id>/status passing `count`,
    `restarts` on each task, and podman called with --events-backend=none (a real server in its own process)."""
import json, os, shutil, socket, subprocess, sys, tempfile, time, unittest, urllib.error, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from watch_works_test import Base, FakeEnv, JELLY, ABS, QBT, DRIVE, GOOD, good_env, put, jload, jdump, R, FX, WFX
import watch


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
        self.assertTrue({r['id']: r for r in watch.snapshot()}['jellyfin']['fixing'], 'the page can say "Restarting" until it ran')
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
        watch.step(e, settle=6)
        self.assertEqual(e.restarts, ['jellyfin', 'audiobookshelf'])
        self.assertEqual(self.kinds(), ['needs-yes', 'broke'])
        at = watch.iso(e.t)[11:16]
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


def server_env(tmp, port):
    home = os.path.join(tmp, 'home')
    env = {k: v for k, v in os.environ.items() if not k.startswith('ARGUS_')}
    env.update(HOME=home, USERPROFILE=home, ARGUS_BIND='127.0.0.1', ARGUS_PORT=str(port), ARGUS_STATIC=os.path.join(tmp, 'static'),
               ARGUS_BUNDLED=os.path.join(tmp, 'none'), ARGUS_PLUGINS=os.path.join(tmp, 'plugins'), ARGUS_CHECKS=os.path.join(tmp, 'checks.json'),
               ARGUS_AUTOFIX=os.path.join(tmp, 'auto-fix.json'), ARGUS_MOUNTINFO=os.path.join(WFX, 'host-good.mountinfo'),
               ARGUS_EVENTS=os.path.join(tmp, 'events.jsonl'), ARGUS_WATCH_STATE=os.path.join(tmp, 'watch.json'), ARGUS_WATCH_INTERVAL='1',
               FAKE_PODMAN_DIR=os.path.join(tmp, 'pod'), ARGUS_ALERTS=os.path.join(tmp, 'alerts'), ARGUS_REGISTRY=os.path.join(tmp, 'reg'))
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
        cls.events = env['ARGUS_EVENTS']; cls.fx = fx
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
        for bad in ('abc', '-3', '2.5'): self.assertEqual(self.get('api/events?limit=' + bad)[0], 400, bad)

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
        code, d2 = self.post('api/watch/fix', {'id': 'jellyfin'}); self.assertEqual(code, 409, 'a second press at once is refused'); self.assertIn('Give it 2 minutes', d2['msg'])
        self.wait_for(lambda: os.path.exists(os.path.join(self.fx, 'restarts.log')))                                     # the restart ran ...
        shutil.copy(os.path.join(WFX, 'container-good.mountinfo'), os.path.join(self.tmp, 'pod', 'jellyfin.mountinfo'))   # ... and helped
        self.wait_for(lambda: self.row('jellyfin').get('works') is True and not self.row('jellyfin').get('fixing'))
        self.assertIs(self.row('jellyfin')['again'], True)
        with open(os.path.join(self.fx, 'restarts.log')) as f: self.assertEqual(f.read().split(), ['jellyfin.service', 'audiobookshelf.service'])
        evs = self.get('api/events?limit=5')[1]['events']
        mine = [e for e in evs if e['subject'] == 'jellyfin']
        self.assertEqual(mine[0]['kind'], 'fixed'); self.assertIn('You restarted Jellyfin and Audiobookshelf from the page', mine[0]['body'])
        code, d = self.post('api/watch/fix', {'id': 'jellyfin'}); self.assertEqual(code, 409); self.assertIn('works right now', d['msg'])


if __name__ == '__main__':
    unittest.main()
