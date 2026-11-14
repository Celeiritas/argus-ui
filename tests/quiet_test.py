"""What keeps quiet (server/quiet.py, docs/home.md "Quiet"): quiet sections (Mentor) and tasks marked "Known, low priority".
No browser.

    python3 tests/quiet_test.py -v        (tests/run.sh runs it under "== quiet and known")

  * quiet.py: the one quiet set {'mentor'}; the fingerprint of a failure (Result / ExecMainStatus / failing check codes);
    mark, unmark, a broken file; reconcile: the mark goes when the task works again (so a later failure counts again), when
    it fails another way, and stays while it is frozen, in the middle of a timer run, or missing from systemd's list
  * the server's state: `known` on a marked task, `quiet` in the owner's state and none in a learner's; marks_now() for the
    phone and the summary (no systemctl call while nothing is marked)
  * the phone: an event about a quiet section or a known task's check never buzzes (through notify, as watch.py sends it);
    other events still do; when the quiet look itself fails, the alert goes out
  * the daily summary: a quiet section's events and a known task's check are neither a need nor counted; tick() asks once
The routes (POST api/known for the owner and a learner, a quiet section's status) are in tests/gate_test.py; the page side
is tests/quiet.test.js. The server module runs in this process with a temporary HOME and fake units."""
import importlib.util, json, os, shutil, sys, tempfile, unittest
from datetime import datetime, timedelta, timezone

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = tempfile.mkdtemp(prefix='argus-quiet-test-')
HOME, STATIC, FX, REG = (os.path.join(TMP, d) for d in ('home', 'static', 'fx', 'agents'))
STATE = os.path.join(TMP, 'state'); KNOWN = os.path.join(STATE, 'known.json')
for d in (HOME, STATIC, FX, REG, STATE, os.path.join(TMP, 'alerts')): os.makedirs(d, exist_ok=True)

def put(path, data):
    with open(path, 'w', encoding='utf-8') as f: f.write(data if isinstance(data, str) else json.dumps(data))

def set_aside(path):
    # tests keep their own files in TMP; one that must be gone is moved aside, never deleted
    if os.path.exists(path): shutil.move(path, f'{path}.set-aside-{os.urandom(4).hex()}')

put(os.path.join(STATIC, 'theme.json'), {'title': 'Elaia', 'agents': [{'key': 'argus', 'name': 'Argus'}, {'key': 'hermes', 'name': 'Hermes'},
    {'key': 'mnemosyne', 'name': 'Mnemosyne'}, {'key': 'zeus', 'name': 'Zeus'}]})
shutil.copy(os.path.join(R, 'tests', 'fixtures', 'fake_systemctl.py'), FX)
UNITS = os.path.join(FX, 'units.json')
ON = {'ActiveState': 'active', 'Result': 'success'}
# hermes-mam: a timer task whose login ran out, as on 2026-10-24 (exit status 1)
FAIL = {'ActiveState': 'failed', 'Result': 'exit-code', 'ExecMainStatus': '1', 'ExecMainStartTimestamp': 'Sat 2026-10-24 04:00:00 MDT',
        'timer': True, 'timer_on': True}
OTHER = dict(FAIL, ExecMainStatus='2')                                       # the same task failing another way
WELL = {'ActiveState': 'inactive', 'Result': 'success', 'ExecMainStatus': '0', 'ExecMainExitTimestamp': 'Fri 2026-11-13 04:00:05 MST',
        'timer': True, 'timer_on': True}
MIDRUN = dict(WELL, ActiveState='active')                                    # a timer run in progress: not yet an answer

def units(mam): put(UNITS, {'argus-ui': dict(ON), 'hermes-mail': dict(ON), 'hermes-mam': dict(mam)})

def wrapper():
    if os.name == 'nt':
        put(os.path.join(FX, 'systemctl.cmd'), f'@"{sys.executable}" "{os.path.join(FX, "fake_systemctl.py")}" %*\n'); return os.path.join(FX, 'systemctl.cmd')
    put(os.path.join(FX, 'systemctl'), f'#!/bin/sh\nexec "{sys.executable}" "{os.path.join(FX, "fake_systemctl.py")}" "$@"\n'); os.chmod(os.path.join(FX, 'systemctl'), 0o755)
    return os.path.join(FX, 'systemctl')

os.environ.update(HOME=HOME, USERPROFILE=HOME, ARGUS_STATIC=STATIC, ARGUS_ALERTS=os.path.join(TMP, 'alerts'), ARGUS_REGISTRY=REG,
                  ARGUS_WATCH='0', ARGUS_DEV='1', ARGUS_PLUGINS=os.path.join(TMP, 'plugins'), ARGUS_BUNDLED=os.path.join(TMP, 'bundled'),
                  ARGUS_LINKS=os.path.join(TMP, 'links.json'), ARGUS_MEDIA=os.path.join(TMP, 'media.json'), LEAFY_REALM=os.path.join(TMP, 'realm.json'),
                  ARGUS_GAMEGUARD=os.path.join(TMP, 'guard.json'), ARGUS_SYSTEMCTL=wrapper(), ARGUS_KNOWN=KNOWN,
                  ARGUS_EVENTS=os.path.join(STATE, 'events.jsonl'), ARGUS_SUMMARY_STATE=os.path.join(STATE, 'summary.json'),
                  ARGUS_PUSH_DEVICES=os.path.join(STATE, 'push-devices.json'), ARGUS_PUSH_KEY=os.path.join(STATE, 'push-key.pem'))
for k in ('ARGUS_PEOPLE', 'ARGUS_WEATHER', 'ARGUS_SUMMARY', 'ARGUS_SUMMARY_AT'): os.environ.pop(k, None)
_spec = importlib.util.spec_from_file_location('argus_ui_quiet_test', os.path.join(R, 'server', 'argus_ui.py'))
a = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(a)
quiet, push, summary, notify = a.quiet, a.push, a.summary, a.notify

LEARNER = {'role': 'learner', 'person': 'learner-two', 'name': 'Learner Two'}
ROWS = [{'id': 'mam-login', 'title': 'MAM login', 'job': 'hermes-mam', 'works': False, 'code': 'no-answer', 'reason': 'The login ran out.'},
        {'id': 'media', 'title': 'Media player', 'job': 'hermes-media', 'works': True, 'code': 'ok', 'reason': ''}]


def mam(): return next(j for j in a.state()['jobs'] if j['job'] == 'hermes-mam')
def marks():
    try:
        with open(KNOWN, encoding='utf-8') as f: return json.load(f)
    except OSError: return None


class Base(unittest.TestCase):
    def setUp(self):
        units(FAIL); set_aside(KNOWN); set_aside(a.FROZEN)


class QuietSections(Base):
    def test_one_place_and_mentor_in_it(self):
        self.assertEqual(quiet.DEFAULT_QUIET, frozenset({'mentor'}))
        self.assertIs(quiet.quiet_sections(), quiet.DEFAULT_QUIET, 'everything reads the one place')
        self.assertTrue(quiet.is_quiet('mentor'))
        for other in ('memory', 'argus', 'zeus', '', None, ['mentor']): self.assertFalse(quiet.is_quiet(other), other)

    def test_the_owners_state_says_what_is_quiet_and_a_learners_does_not(self):
        self.assertEqual(a.state()['quiet'], ['mentor'])
        self.assertNotIn('quiet', a.state_for(LEARNER), "Mentor is what a learner studies: her page counts it")

    def test_a_quiet_section_never_buzzes_and_another_does(self):
        rows = []
        for subject, section in (('mentor', None), ('mentor-due', 'mentor')):
            self.assertTrue(quiet.hushed(dict(notify.make('needs-yes', subject, 'Study'), section=section), rows, {}), subject)
        self.assertFalse(quiet.hushed(notify.make('broke', 'media', 'Media player'), ROWS, {}))
        self.assertFalse(quiet.hushed(dict(notify.make('broke', 'media', 'x'), section='memory'), ROWS, {}))
        self.assertFalse(quiet.hushed('not an event'))


class Fingerprint(unittest.TestCase):
    def test_result_status_and_the_failing_check_codes(self):
        j = {'job': 'hermes-mam', 'state': 'failed', 'result': 'exit-code', 'status': '1'}
        self.assertEqual(quiet.fingerprint(j), 'exit-code/1/')
        rows = ROWS + [{'id': 'b', 'job': 'hermes-mam', 'works': False, 'code': 'bad-login'},
                       {'id': 'c', 'job': 'hermes-mam', 'works': True, 'code': 'fine'}, {'id': 'd', 'job': 'other', 'works': False, 'code': 'x'}]
        self.assertEqual(quiet.fingerprint(j, rows), 'exit-code/1/bad-login,no-answer', 'sorted, only this task, only failing checks')

    def test_running_but_not_working_has_one_and_working_has_none(self):
        self.assertEqual(quiet.fingerprint({'job': 'hermes-mam', 'state': 'running', 'works': False, 'result': 'success', 'status': '0'}, ROWS),
                         'success/0/no-answer')
        self.assertIsNone(quiet.fingerprint({'job': 'hermes-mam', 'state': 'ok', 'result': 'success', 'status': '0'}))

    def test_a_transient_task_is_kept_under_its_base(self):
        self.assertEqual(quiet.key({'job': 'zeus-deploy-20261113-090012-argus-ui-3fa9c1b', 'base': 'zeus-deploy'}), 'zeus-deploy')
        self.assertEqual(quiet.key({'job': 'hermes-mam', 'base': ''}), 'hermes-mam')


class Marks(Base):
    def test_mark_saves_the_fingerprint_and_the_state_shows_when(self):
        self.assertEqual(mam()['state'], 'failed'); self.assertNotIn('known', mam())
        ok, at = quiet.mark(mam(), [])
        self.assertTrue(ok)
        self.assertEqual(marks(), {'hermes-mam': {'fp': 'exit-code/1/', 'at': at}})
        self.assertEqual(mam()['known'], at, 'the page gets when it was marked')
        datetime.fromisoformat(at)                                             # a real time, for "marked <date>"

    def test_a_task_that_works_cannot_be_marked(self):
        units(WELL)
        ok, why = quiet.mark(mam(), [])
        self.assertFalse(ok); self.assertIn('works', why); self.assertIsNone(marks())

    def test_unmark_and_undo(self):
        quiet.mark(mam(), [])
        quiet.unmark('hermes-mam')
        self.assertEqual(marks(), {}); self.assertNotIn('known', mam())
        quiet.unmark('hermes-mam')                                             # twice is fine

    def test_back_after_success_then_fail(self):
        quiet.mark(mam(), [])
        units(WELL); self.assertNotIn('known', mam()); self.assertEqual(marks(), {}, 'it worked once: the mark is gone')
        units(FAIL); self.assertNotIn('known', mam(), 'the next failure counts again, even the same kind')
        self.assertEqual(mam()['state'], 'failed')

    def test_back_on_a_new_failure_kind(self):
        quiet.mark(mam(), [])
        units(OTHER)
        self.assertNotIn('known', mam()); self.assertEqual(marks(), {})

    def test_back_when_a_check_starts_failing_too(self):
        quiet.mark(mam(), [])
        self.assertEqual(quiet.reconcile([dict(mam(), works=False)], ROWS), {}, 'a new failing check is another way to fail')

    def test_kept_while_frozen_mid_run_or_missing(self):
        quiet.mark(mam(), [])
        units(MIDRUN); self.assertEqual(mam()['state'], 'running'); self.assertIn('known', mam(), 'a timer run is not an answer yet')
        put(a.FROZEN, {'hermes-mam': {'at': '2026-11-13T10:00:00'}}); self.assertEqual(mam()['state'], 'frozen'); self.assertIn('known', mam())
        set_aside(a.FROZEN)
        put(UNITS, {'argus-ui': dict(ON)}); a.state()
        self.assertIn('hermes-mam', marks(), 'a hiccup in the list never wakes every known failure')
        units(FAIL); self.assertIn('known', mam())

    def test_an_always_on_task_running_well_loses_its_mark(self):
        quiet.mark({'job': 'hermes-mail', 'state': 'failed', 'result': 'exit-code', 'status': '1'})
        self.assertEqual(quiet.reconcile([{'job': 'hermes-mail', 'state': 'running', 'next': 'always on'}]), {})

    def test_a_broken_file_is_no_marks(self):
        for bad in ('not json', '[1, 2]', '{"hermes-mam": "x", "a": {"fp": 3}}'):
            put(KNOWN, bad)
            self.assertEqual(quiet.load(), {}, bad); self.assertNotIn('known', mam())
        set_aside(KNOWN); self.assertEqual(quiet.load(), {})

    def test_marks_now_without_a_page_and_no_systemctl_when_nothing_is_marked(self):
        real = a.units
        try:
            a.units = lambda: self.fail('no marks: no systemctl call')
            self.assertEqual(a.marks_now(), {})
        finally: a.units = real
        quiet.mark(mam(), [])
        self.assertIn('hermes-mam', a.marks_now())
        units(WELL); self.assertEqual(a.marks_now(), {}, 'it ran well while no page was open: the phone counts it again')


class Phone(Base):
    """push.sink as watch.py reaches it (notify.notify), with a device of the owner's that wants every kind. The sending itself
    (encryption, the push service) is tests/push_test.py's; here to_devices only records."""
    def setUp(self):
        super().setUp(); set_aside(os.environ['ARGUS_EVENTS'])
        self.sent, self.saved = [], {k: getattr(push, k) for k in ('crypto', 'load_devices', 'to_devices', 'hushed', 'role_of')}
        push.crypto = lambda: object()
        push.load_devices = lambda: [{'id': 'd1', 'person': 'owner', 'kinds': list(push.KINDS)}]
        push.to_devices = lambda person, kinds, event, kind: self.sent.append((kind, event['subject']))
        push.gate.__init__()
        push.start(lambda person: 'owner', None, lambda e: a.hushed_now()(e))   # as the server's start passes it
    def tearDown(self):
        for k, v in self.saved.items(): setattr(push, k, v)

    def test_mentor_never_buzzes(self):
        notify.notify(notify.make('needs-yes', 'mentor', '6 cards due', 'Study 10 minutes'))
        notify.notify(dict(notify.make('broke', 'mentor-ai', 'x'), section='mentor'))
        self.assertEqual(self.sent, [])
        notify.notify(notify.make('broke', 'media', 'Media player stopped'))
        self.assertEqual(self.sent, [('broke', 'media')], 'another section still buzzes')

    def test_a_known_task_never_buzzes_and_buzzes_again_when_it_fails_another_way(self):
        rows, j = [dict(ROWS[0])], mam()
        quiet.mark(j, [])
        self.assertTrue(quiet.hushed(notify.make('broke', 'mam-login', 'x'), rows, quiet.load()))
        real = a.watch.snapshot
        try:
            a.watch.snapshot = lambda interval=60: [dict(r) for r in rows]
            quiet.mark(dict(j, works=False), rows)                           # marked with its failing check, as the page does
            notify.notify(notify.make('broke', 'mam-login', 'MAM login stopped working'))
            self.assertEqual(self.sent, [], 'no push for a task marked known')
            notify.notify(notify.make('broke', 'media', 'Media player stopped'))
            self.assertEqual(self.sent, [('broke', 'media')])
            units(OTHER)                                                       # it fails another way: the mark goes, it buzzes
            notify.notify(notify.make('needs-yes', 'mam-login', 'MAM login stopped working'))
            self.assertEqual(self.sent, [('broke', 'media'), ('needs-yes', 'mam-login')])
        finally: a.watch.snapshot = real
        self.assertTrue(any(e['subject'] == 'mam-login' for e in notify.read_events(10)), 'it still goes into what happened lately')

    def test_when_the_quiet_look_fails_the_alert_goes_out(self):
        def broken(e): raise OSError('disk')
        push.hushed = broken
        push.sink(notify.make('broke', 'mentor', 'x'))
        self.assertEqual(self.sent, [('broke', 'mentor')], 'better one alert too many than a silent failure')

    def test_the_summary_itself_is_never_hushed(self):
        push.hushed = lambda e: True
        push.sink(notify.make('summary', 'daily-summary', 'Yesterday'))
        self.assertEqual(self.sent, [('summary', 'daily-summary')])


class Summary(Base):
    NOW = datetime(2026, 11, 13, 8, 0, 30, tzinfo=timezone(timedelta(hours=-7)))

    def e(self, kind, subject, hours_ago): return notify.make(kind, subject, f'{subject} {kind}', '', at=self.NOW - timedelta(hours=hours_ago))

    def test_a_known_task_and_mentor_are_not_needs_and_not_counted(self):
        ev = [self.e('needs-yes', 'mentor', 1), self.e('broke', 'mam-login', 2)]
        loud = summary.compose(ev, ROWS, self.NOW)
        self.assertIn('MAM login', loud['title'] + loud['body'])
        hushed = lambda e: quiet.hushed(e, ROWS, {'hermes-mam': {'fp': 'exit-code/1/no-answer', 'at': '2026-11-13T07:00:00-07:00'}})
        self.assertEqual(summary.compose(ev, ROWS, self.NOW, '', hushed), summary.compose([], ROWS[1:], self.NOW))
        self.assertEqual(summary.compose(ev, ROWS, self.NOW, '', hushed)['title'], 'Yesterday: everything worked')

    def test_mentor_alone_is_a_calm_day(self):
        s = summary.compose([self.e('needs-yes', 'mentor', 3)], ROWS[1:], self.NOW, '', lambda e: quiet.hushed(e, ROWS[1:], {}))
        self.assertEqual(s['title'], 'Yesterday: everything worked')

    def test_tick_asks_once_and_a_failed_look_leaves_everything_in(self):
        set_aside(os.environ['ARGUS_SUMMARY_STATE']); set_aside(os.environ['ARGUS_EVENTS'])
        notify.notify(self.e('broke', 'mam-login', 2))
        asked = []
        def look(): asked.append(1); return lambda e: quiet.hushed(e, ROWS, {'hermes-mam': {'fp': 'x', 'at': 'y'}})
        sent = summary.tick(lambda: ROWS, self.NOW, quiet=look)
        self.assertEqual((asked, sent['title']), ([1], 'Yesterday: everything worked'))
        set_aside(os.environ['ARGUS_SUMMARY_STATE'])
        def broken(): raise OSError('disk')
        self.assertIn('MAM login', summary.tick(lambda: ROWS, self.NOW, quiet=broken)['body'])


def tearDownModule():
    shutil.rmtree(TMP, ignore_errors=True)

if __name__ == '__main__':
    unittest.main()
