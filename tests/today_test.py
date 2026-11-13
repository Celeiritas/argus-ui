"""Today's line on what the server is doing now, and its Open rows for the media players (docs/home.md, 4.44.0). No browser.

    python3 tests/today_test.py -v        (tests/run.sh runs it under "== today model"; tests/home.test.js is the page side)

  * now_line(): "calm"; "busy with" for a timer's run or a transient job's run, never for an always-on service; the watch's restarts;
    "a game is running" from the game guard's record (and what it paused, the local AI by name) or its alert file alone
  * the server's name from ~/.config/leafy/realm.json (SERVER, any case), "The server" without a usable one
  * media(): media.json's jellyfin and audiobookshelf, http(s) addresses only; no file or a broken one, no rows
  * only the owner's state carries `now` and `media`; a learner's has neither
The server module runs in this process with a temporary HOME and fake units (tests/fixtures/fake_systemctl.py)."""
import importlib.util, json, os, shutil, sys, tempfile, unittest

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = tempfile.mkdtemp(prefix='argus-today-test-')
HOME, STATIC, FX = os.path.join(TMP, 'home'), os.path.join(TMP, 'static'), os.path.join(TMP, 'fx')
ALERTS, REG = os.path.join(TMP, 'alerts'), os.path.join(TMP, 'agents')
MEDIA, REALM, GUARD = os.path.join(TMP, 'media.json'), os.path.join(TMP, 'realm.json'), os.path.join(TMP, 'guard', 'frozen-by-me.json')
for d in (HOME, STATIC, FX, ALERTS, REG, os.path.dirname(GUARD)): os.makedirs(d, exist_ok=True)

def put(path, data):
    with open(path, 'w', encoding='utf-8') as f: f.write(data if isinstance(data, str) else json.dumps(data))

def set_aside(path):
    # tests keep their own files in TMP; one that must be gone is moved aside, never deleted
    if os.path.exists(path): shutil.move(path, f'{path}.set-aside-{os.urandom(4).hex()}')

put(os.path.join(STATIC, 'theme.json'), {'title': 'Elaia', 'agents': [{'key': 'argus', 'name': 'Argus'}, {'key': 'hermes', 'name': 'Hermes'},
    {'key': 'mnemosyne', 'name': 'Mnemosyne'}, {'key': 'zeus', 'name': 'Zeus'}, {'key': 'medusa', 'name': 'Medusa'}]})
put(os.path.join(REG, 'zeus-deploy.json'), {'transient': True, 'notes': 'one run per deploy'})
shutil.copy(os.path.join(R, 'tests', 'fixtures', 'fake_systemctl.py'), FX)
UNITS = os.path.join(FX, 'units.json')
ON, OFF = {'ActiveState': 'active', 'Result': 'success'}, {'ActiveState': 'inactive', 'Result': 'success'}
QUIET = {'argus-ui': dict(ON), 'hermes-mail': dict(ON), 'mnemosyne-backup': dict(OFF, timer=True, timer_on=True)}     # always-on and idle
BUSY = dict(QUIET, **{'hermes-media': dict(ON, timer=True, timer_on=True),                            # a timer's run in progress
                      'zeus-deploy-20261113-090012-argus-ui-3fa9c1b': dict(ON),                         # a transient run in progress
                      'zeus-deploy-20261112-210000-argus-ui-0aa0aa0': dict(OFF)})

def wrapper():
    if os.name == 'nt':
        put(os.path.join(FX, 'systemctl.cmd'), f'@"{sys.executable}" "{os.path.join(FX, "fake_systemctl.py")}" %*\n'); return os.path.join(FX, 'systemctl.cmd')
    put(os.path.join(FX, 'systemctl'), f'#!/bin/sh\nexec "{sys.executable}" "{os.path.join(FX, "fake_systemctl.py")}" "$@"\n'); os.chmod(os.path.join(FX, 'systemctl'), 0o755)
    return os.path.join(FX, 'systemctl')

os.environ.update(HOME=HOME, USERPROFILE=HOME, ARGUS_STATIC=STATIC, ARGUS_ALERTS=ALERTS, ARGUS_REGISTRY=REG, ARGUS_WATCH='0',
                  ARGUS_PLUGINS=os.path.join(TMP, 'plugins'), ARGUS_BUNDLED=os.path.join(TMP, 'bundled'), ARGUS_LINKS=os.path.join(TMP, 'links.json'),
                  ARGUS_MEDIA=MEDIA, LEAFY_REALM=REALM, ARGUS_GAMEGUARD=GUARD, ARGUS_SYSTEMCTL=wrapper(), ARGUS_EVENTS=os.path.join(TMP, 'events.jsonl'))
for k in ('ARGUS_PEOPLE', 'ARGUS_WEATHER'): os.environ.pop(k, None)
_spec = importlib.util.spec_from_file_location('argus_ui_today_test', os.path.join(R, 'server', 'argus_ui.py'))
a = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(a)

OWNER = {'role': 'owner', 'person': 'owner-one', 'name': 'Owner One'}
LEARNER = {'role': 'learner', 'person': 'learner-two', 'name': 'Learner Two'}


class Base(unittest.TestCase):
    def setUp(self):
        put(UNITS, QUIET)
        for f in (MEDIA, REALM, GUARD, os.path.join(ALERTS, 'medusa-gameguard.json')): set_aside(f)

    def now(self): return a.state()['now']


class NowLine(Base):
    def test_calm_when_only_always_on_services_run(self):
        self.assertEqual(self.now(), 'The server: calm')

    def test_busy_names_a_timer_run_and_a_transient_run_but_never_an_always_on_service(self):
        put(UNITS, BUSY)
        self.assertEqual(self.now(), 'The server: busy with Hermes media and Zeus deploy')

    def test_the_watch_restarting_a_program_is_busy(self):
        self.assertEqual(a.now_line([], [{'id': 'jellyfin', 'title': 'Jellyfin', 'fixing': True}, {'id': 'abs', 'title': 'Audiobookshelf', 'queued': True},
                                         {'id': 'qbt', 'title': 'qBittorrent', 'works': False}]),
                         'The server: restarting Jellyfin and Audiobookshelf')

    def test_more_than_three_runs_are_counted_not_listed(self):
        jobs = [dict(persona='hermes', name=f'job{i}', state='running', next='Sun 4:00 AM', base='') for i in range(5)]
        self.assertEqual(a.now_line(jobs, []), 'The server: busy with Hermes job0, Hermes job1, Hermes job2 and 2 more')

    def test_one_colon_only_after_the_name(self):
        # the review of 4.44.0's first draft read "The server: busy: Hermes media": two colons
        put(GUARD, ['mnemosyne-ollama']); put(UNITS, BUSY)
        ws = [{'id': 'jellyfin', 'title': 'Jellyfin', 'fixing': True}]
        for line in (self.now(), a.now_line([dict(persona='hermes', name='media', state='running', next='Sun 4:00 AM', base='')], ws)):
            with self.subTest(line=line):
                self.assertEqual(line.count(':'), 1, line)
        self.assertEqual(a.now_line([dict(persona='hermes', name='media', state='running', next='Sun 4:00 AM', base='')], ws),
                         'The server: a game is running, the local AI is paused; busy with Hermes media; restarting Jellyfin')

    def test_a_game_with_the_local_ai_paused(self):
        put(GUARD, ['mnemosyne-ollama'])
        self.assertEqual(self.now(), 'The server: a game is running, the local AI is paused')

    def test_a_game_that_paused_two_tasks_while_a_run_goes_on(self):
        put(GUARD, ['mnemosyne-ollama', 'mnemosyne-library']); put(UNITS, BUSY)
        self.assertEqual(self.now(), 'The server: a game is running, the local AI and Mnemosyne library are paused; busy with Hermes media and Zeus deploy')

    def test_the_guards_alert_file_alone_says_a_game_runs(self):
        put(GUARD, []); put(os.path.join(ALERTS, 'medusa-gameguard.json'), {'job': 'medusa-gameguard', 'level': 'warn', 'message': 'A game is running'})
        self.assertEqual(self.now(), 'The server: a game is running')

    def test_an_empty_or_broken_record_is_no_game(self):
        for doc in ([], 'not json', {'mnemosyne-ollama': True}, [3, None, '']):
            with self.subTest(doc=doc):
                put(GUARD, doc if isinstance(doc, str) else json.dumps(doc))
                self.assertEqual(self.now(), 'The server: calm')


class ServerName(Base):
    def test_the_name_comes_from_realm_json_in_any_case(self):
        put(REALM, {'server': 'Testbox', 'PC': 'desk'})
        self.assertEqual(self.now(), 'Testbox: calm')
        put(REALM, {'SERVER': '  Shelf  '})
        self.assertEqual(self.now(), 'Shelf: calm')

    def test_without_a_usable_name_it_says_the_server(self):
        for doc in ('not json', [], {'SERVER': ''}, {'SERVER': True}, {'SERVER': {'a': 1}}, {'PC': 'desk'}):
            with self.subTest(doc=doc):
                put(REALM, doc if isinstance(doc, str) else json.dumps(doc))
                self.assertEqual(self.now(), 'The server: calm')


class Media(Base):
    def test_no_file_no_rows(self):
        self.assertEqual(a.state()['media'], [])

    def test_the_two_players_in_order_with_http_or_https(self):
        put(MEDIA, {'Audiobookshelf': 'http://media.example:13378/', 'jellyfin': 'https://films.example/web/', 'qbittorrent': 'https://x.example/'})
        self.assertEqual(a.state()['media'], [
            {'id': 'jellyfin', 'name': 'Jellyfin', 'what': 'Films and shows', 'href': 'https://films.example/web/'},
            {'id': 'audiobookshelf', 'name': 'Audiobookshelf', 'what': 'Audiobooks and podcasts', 'href': 'http://media.example:13378/'}])

    def test_anything_but_an_http_address_is_dropped(self):
        for href in ('javascript:alert(1)', '//films.example/', '/jellyfin/', 'ftp://films.example/', 'https://films example/', 'https://x.example/"onmouseover="x',
                     'https://' + 'a' * 300, 42, None, ['https://films.example/']):
            with self.subTest(href=href):
                put(MEDIA, {'jellyfin': href})
                self.assertEqual(a.state()['media'], [])

    def test_a_broken_file_is_no_rows(self):
        for doc in ('not json', '["https://films.example/"]', '"https://films.example/"'):
            with self.subTest(doc=doc):
                put(MEDIA, doc)
                self.assertEqual(a.state()['media'], [])


class OwnerOnly(Base):
    def test_the_owner_gets_both_and_a_learner_neither(self):
        put(MEDIA, {'jellyfin': 'https://films.example/'}); put(UNITS, BUSY)
        mine = a.state_for(OWNER)
        self.assertEqual(mine['now'], 'The server: busy with Hermes media and Zeus deploy')
        self.assertEqual([m['id'] for m in mine['media']], ['jellyfin'])
        hers = a.state_for(LEARNER)
        self.assertNotIn('now', hers); self.assertNotIn('media', hers)


if __name__ == '__main__':
    unittest.main()
