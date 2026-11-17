"""The Mealie section without a browser (plugins/mealie, docs/mealie.md). Runs on any OS, Windows included.

    python3 tests/mealie_test.py -v        (tests/run.sh runs it under "== mealie model")

Every check asks tests/fixtures/fake_mealie.py, a stand-in that answers in the shape of Mealie v3.30.0, never a real Mealie.
Settings: the token file and mealie.json are found where docs/mealie.md says. Plan: Today's line and the week for each
plan. Failures: no token, an empty or broken token file, a refused token, Mealie down, slow, answering garbage, too much,
or a redirect (not followed: the token never goes to another address). Cache: one ask a minute, a new token counts at
once, Check again. Secret: the token is in no answer and no log line. OnTheServer: the bundled plugin on a real server."""
import contextlib, datetime, http.client, importlib.util, io, json, os, shutil, socket, subprocess, sys, tempfile, time, unittest
from unittest import mock

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
ml = load('leafy_mealie', os.path.join(R, 'plugins', 'mealie', 'plugin.py'))
fake = load('fake_mealie', os.path.join(R, 'tests', 'fixtures', 'fake_mealie.py'))
TOKEN = 'eyJhbGciOiJIUzI1NiJ9.test-token-not-real.c2lnbmF0dXJl'
TODAY = datetime.date.today()

def free_port():
    with socket.socket() as s: s.bind(('127.0.0.1', 0)); return s.getsockname()[1]

class Base(unittest.TestCase):
    """A temporary settings folder (token file, mealie.json, media.json) and a fake Mealie on a free port."""
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='mealie-test-')
        self.tok, self.conf, self.media = (os.path.join(self.tmp, n) for n in ('mealie-token.txt', 'mealie.json', 'media.json'))
        self.scen = os.path.join(self.tmp, 'scenario.json')
        self.scenario(mode='ok', plan=[])
        self.srv = fake.start(self.scen)
        self.write(self.conf, json.dumps({'url': f'http://127.0.0.1:{self.srv.server_port}'}))
        self.write(self.tok, TOKEN + '\n')
        self.env = {'ARGUS_MEALIE_TOKEN': self.tok, 'ARGUS_MEALIE': self.conf, 'ARGUS_MEDIA': self.media}
        ml._cache.clear(); ml._slug.clear()
    def tearDown(self):
        self.srv.shutdown(); self.srv.server_close(); shutil.rmtree(self.tmp, ignore_errors=True)
    def write(self, p, text):
        with open(p, 'w', encoding='utf-8') as f: f.write(text)
    def scenario(self, **s):
        s.setdefault('token', TOKEN); self.write(self.scen, json.dumps(s))
    def fetch(self, **kw):
        return ml.fetch(TODAY, env=self.env, **kw)
    def line(self):
        return ml.line(self.fetch(), TODAY)
    def asks(self, path='/api/households/mealplans'):
        return [r for r in self.srv.seen if r['path'].startswith(path)]

def dish(name, slug, in_days=0, kind='dinner'):
    return {'in_days': in_days, 'entryType': kind, 'recipe': {'name': name, 'slug': slug}}

class Settings(unittest.TestCase):
    def test_defaults_and_settings(self):
        home = os.path.expanduser('~')
        self.assertEqual(ml.where({}), (os.path.join(home, '.config', 'argus-ui', 'mealie-token.txt'), os.path.join(home, '.config', 'argus-ui', 'mealie.json')))
        self.assertEqual(ml.where({'ARGUS_MEALIE_TOKEN': '', 'ARGUS_MEALIE': ''}), ml.where({}), 'an empty setting counts as unset')
        self.assertEqual(ml.where({'ARGUS_MEALIE_TOKEN': '/x/t', 'ARGUS_MEALIE': '/x/m.json'}), ('/x/t', '/x/m.json'))

    def test_address(self):
        with tempfile.TemporaryDirectory() as t:
            p = os.path.join(t, 'mealie.json')
            self.assertEqual(ml.settings(p), (ml.DEFAULT_URL, ''), 'no file: Mealie on this machine at its default port')
            for text, want in (('{"url": "http://127.0.0.1:9000/"}', ('http://127.0.0.1:9000', '')), ('{}', (ml.DEFAULT_URL, '')),
                               ('{"url": "file:///etc/passwd"}', ('', 'config')), ('{"url": "http://a b"}', ('', 'config')),
                               ('not json', ('', 'config')), ('[1]', ('', 'config'))):
                with open(p, 'w') as f: f.write(text)
                self.assertEqual(ml.settings(p), want, text)

    def test_open_address_from_media_json(self):
        with tempfile.TemporaryDirectory() as t:
            p = os.path.join(t, 'media.json')
            self.assertEqual(ml.open_address(p), '')
            with open(p, 'w') as f: f.write('{"Mealie": "https://food.example:9925/"}')
            self.assertEqual(ml.open_address(p), 'https://food.example:9925', 'the key in any case, the trailing slash dropped')
            with open(p, 'w') as f: f.write('{"mealie": "javascript:alert(1)"}')
            self.assertEqual(ml.open_address(p), '')

class TokenFile(Base):
    def test_no_file_is_not_set_up_and_nothing_is_asked(self):
        os.remove(self.tok)
        self.assertEqual(self.line(), 'Not set up yet: make an API token in Mealie')
        self.assertEqual(self.srv.seen, [], 'without a token Mealie is not asked at all')

    def test_empty_and_broken_files(self):
        self.write(self.tok, '\n  \n')
        self.assertEqual(self.line(), 'Not set up yet: the token file is empty')
        self.write(self.tok, 'two words\n')
        self.assertEqual(self.line(), 'The token file does not hold a token')
        self.assertEqual(self.srv.seen, [])

    def test_first_non_empty_line_is_the_token(self):
        self.write(self.tok, '\n  ' + TOKEN + '  \n# a note\n')
        self.scenario(mode='ok', plan=[dish('Lentil soup', 'lentil-soup')])
        self.assertEqual(self.line(), 'Tonight: Lentil soup')
        self.assertEqual(self.asks()[0]['auth'], 'Bearer ' + TOKEN)

    def test_broken_mealie_json_asks_nothing(self):
        self.write(self.conf, '{broken')
        self.assertEqual(self.line(), 'mealie.json could not be read')
        self.assertEqual(self.srv.seen, [])

class Plan(Base):
    def test_tonight(self):
        self.scenario(mode='ok', plan=[dish('Lentil soup', 'lentil-soup'), dish('Toast', 'toast', kind='breakfast'), dish('Pie', 'pie', 1)])
        self.assertEqual(self.line(), 'Tonight: Lentil soup')
        q = self.asks()[0]['path']
        self.assertIn(f'start_date={TODAY.isoformat()}', q); self.assertIn(f'end_date={(TODAY + datetime.timedelta(days=6)).isoformat()}', q)

    def test_two_dinners_and_a_titled_note(self):
        self.scenario(mode='ok', plan=[dish('Lentil soup', 'lentil-soup'), {'in_days': 0, 'entryType': 'dinner', 'title': 'Leftovers'}])
        self.assertEqual(self.line(), 'Tonight: Leftovers · Lentil soup')

    def test_no_dinner(self):
        self.scenario(mode='ok', plan=[dish('Toast', 'toast', kind='breakfast')])
        self.assertEqual(self.line(), 'No dinner planned · Breakfast: Toast')
        self.scenario(mode='ok', plan=[dish('Toast', 'toast', kind='breakfast'), dish('Salad', 'salad', kind='lunch')])
        ml._cache.clear()
        self.assertEqual(self.line(), 'No dinner planned · 2 other meals today')

    def test_nothing_today(self):
        self.scenario(mode='ok', plan=[dish('Pie', 'pie', 2)])
        self.assertEqual(self.line(), 'No meal planned today')

    def test_the_week(self):
        self.scenario(mode='ok', group='kitchen', plan=[dish('Pie', 'pie', 2), dish('Lentil soup', 'lentil-soup'), dish('Toast', 'toast', kind='breakfast'),
                                                     {'in_days': 0, 'entryType': 'lunch', 'title': 'Out with friends'}, dish('Late', 'late', 9)])
        self.write(self.media, '{"mealie": "https://food.example:9925/"}')
        p = ml.plan(self.fetch(), TODAY, ml.open_address(self.media))
        self.assertEqual(p['state'], 'ok'); self.assertEqual(p['open'], 'https://food.example:9925')
        self.assertEqual([d['label'] for d in p['days']], ['Today', ml.day_label(TODAY + datetime.timedelta(days=2), TODAY)], 'today, then only days with a meal')
        self.assertEqual([(m['type'], m['name']) for m in p['days'][0]['meals']], [('Breakfast', 'Toast'), ('Lunch', 'Out with friends'), ('Dinner', 'Lentil soup')])
        self.assertEqual(p['days'][0]['meals'][2]['href'], 'https://food.example:9925/g/kitchen/r/lentil-soup')
        self.assertNotIn('href', p['days'][0]['meals'][1], 'a note with no recipe has no link')

    def test_no_links_without_the_browser_address(self):
        self.scenario(mode='ok', plan=[dish('Lentil soup', 'lentil-soup')])
        p = ml.plan(self.fetch(), TODAY, ml.open_address(self.media))
        self.assertEqual(p['open'], ''); self.assertNotIn('href', p['days'][0]['meals'][0])

    def test_an_empty_week_still_shows_today(self):
        p = ml.plan(self.fetch(), TODAY, '')
        self.assertEqual(p['days'], [{'date': TODAY.isoformat(), 'label': 'Today', 'meals': []}])
        self.assertEqual(p['line'], 'No meal planned today')

    def test_labels(self):
        self.assertEqual(ml.day_label(TODAY, TODAY), 'Today')
        self.assertEqual(ml.day_label(TODAY + datetime.timedelta(days=1), TODAY), 'Tomorrow')
        self.assertEqual(ml.day_label(datetime.date(2026, 11, 18), datetime.date(2026, 11, 16)), 'Wednesday, Nov 18')

    def test_more_than_fit(self):
        self.scenario(mode='ok', plan=[dish('Pie', 'pie')], extra_total=200)
        self.assertTrue(ml.plan(self.fetch(), TODAY, '')['more'])

class Failures(Base):
    def test_refused(self):
        self.scenario(mode='refuse')
        self.assertEqual(self.line(), 'Mealie refused the token: make a new one')
        self.scenario(mode='ok', token='another')
        ml._cache.clear()
        self.assertEqual(self.line(), 'Mealie refused the token: make a new one', 'a token Mealie does not know')

    def test_down(self):
        self.write(self.conf, json.dumps({'url': f'http://127.0.0.1:{free_port()}'}))
        self.assertEqual(self.line(), 'Mealie is not answering')

    def test_slow(self):
        self.scenario(mode='slow', delay=1.5)
        with mock.patch.object(ml, 'TIMEOUT', .4):
            t = time.time(); self.assertEqual(self.line(), 'Mealie took too long to answer')
            self.assertLess(time.time() - t, 1.4, 'the timeout holds')

    def test_garbage_too_much_and_wrong_shape(self):
        for mode in ('garbage', 'huge'):
            self.scenario(mode=mode); ml._cache.clear()
            self.assertEqual(self.line(), 'Mealie answered something unexpected', mode)
        with self.assertRaises(ml.Failed): ml.entries({'items': 'no'})
        self.assertEqual(ml.entries({'items': [None, {'date': 'soon'}, {'date': TODAY.isoformat(), 'entryType': 'brunch', 'recipe': {'name': 'X', 'slug': '../x'}}]}),
                         [{'date': TODAY.isoformat(), 'type': 'other', 'name': 'X', 'slug': ''}], 'bad entries skipped, a strange slug dropped')

    def test_redirect_is_not_followed(self):
        self.scenario(mode='redirect')
        self.assertEqual(self.line(), 'Mealie answered something unexpected')
        self.assertEqual(self.asks('/caught'), [], 'the token never follows a redirect')

class Cache(Base):
    def test_one_ask_a_minute_and_a_new_token_counts_at_once(self):
        self.scenario(mode='ok', plan=[dish('Lentil soup', 'lentil-soup')])
        now = time.time()
        ml.fetch(TODAY, env=self.env, now=now); ml.fetch(TODAY, env=self.env, now=now + 30)
        self.assertEqual(len(self.asks()), 1)
        self.assertEqual(len(self.asks('/api/users/self')), 1, 'the group is asked once per token')
        ml.fetch(TODAY, env=self.env, now=now + 61)
        self.assertEqual(len(self.asks()), 2)
        time.sleep(.02); self.write(self.tok, TOKEN + 'x\n')
        ml.fetch(TODAY, env=self.env, now=now + 62)
        self.assertEqual(len(self.asks()), 3, 'a changed token file is used at once')

    def test_failures_are_kept_30_s_and_check_again_after_5(self):
        self.scenario(mode='refuse'); now = time.time()
        ml.fetch(TODAY, env=self.env, now=now); ml.fetch(TODAY, env=self.env, now=now + 20)
        self.assertEqual(len(self.asks()), 1)
        ml.fetch(TODAY, env=self.env, now=now + 21, max_age=ml.AGAIN)
        self.assertEqual(len(self.asks()), 2, 'Check again asks again')
        ml.fetch(TODAY, env=self.env, now=now + 22, max_age=ml.AGAIN)
        self.assertEqual(len(self.asks()), 2, 'but not twice within 5 s')

class Secret(Base):
    def test_the_token_is_in_no_answer_and_no_output(self):
        self.write(self.media, '{"mealie": "https://food.example:9925/"}')
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, self.env), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), mock.patch.object(ml, 'TIMEOUT', .4):
            for mode in ('ok', 'refuse', 'garbage', 'redirect', 'slow', 'huge'):
                self.scenario(mode=mode, delay=1, plan=[dish('Lentil soup', 'lentil-soup')]); ml._cache.clear()
                for path in ('status', 'plan', 'plan', 'nothing'):
                    code, obj = ml.get(path, {'again': ['1']} if path == 'plan' else {}, None)
                    text = json.dumps(obj)
                    self.assertNotIn('test-token', text, (mode, path)); self.assertNotIn('Bearer', text, (mode, path))
        self.assertEqual((out.getvalue(), err.getvalue()), ('', ''), 'the plugin prints nothing')

    def test_status_never_needs_him(self):
        with mock.patch.dict(os.environ, self.env):
            for mode in ('ok', 'refuse'):
                self.scenario(mode=mode); ml._cache.clear()
                self.assertIs(ml.get('status', {}, None)[1]['needs'], False)
            self.assertEqual(ml.get('nothing', {}, None)[0], 404)

    def test_a_bug_gives_a_line_not_a_traceback(self):
        with mock.patch.object(ml, 'fetch', side_effect=RuntimeError('Bearer ' + TOKEN)):
            self.assertEqual(ml.get('status', {}, None), (200, {'line': 'Mealie answered something unexpected', 'needs': False}))
            self.assertEqual(ml.get('plan', {}, None)[1]['state'], 'unexpected')

class OnTheServer(unittest.TestCase):
    """The real server (server/argus_ui.py in its own process) with the bundled plugin, the token file in
    ~/.config/argus-ui/ and mealie.json pointing at the fake. HOME and USERPROFILE point at a temporary folder."""
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='mealie-server-test-')
        home = os.path.join(cls.tmp, 'home'); conf = os.path.join(home, '.config', 'argus-ui'); os.makedirs(conf)
        cls.scen = os.path.join(cls.tmp, 'scenario.json')
        with open(cls.scen, 'w') as f: json.dump({'mode': 'ok', 'token': TOKEN, 'plan': [dish('Lentil soup', 'lentil-soup')]}, f)
        cls.srv = fake.start(cls.scen)
        with open(os.path.join(conf, 'mealie-token.txt'), 'w') as f: f.write(TOKEN + '\n')
        with open(os.path.join(conf, 'mealie.json'), 'w') as f: json.dump({'url': f'http://127.0.0.1:{cls.srv.server_port}'}, f)
        with open(os.path.join(conf, 'media.json'), 'w') as f: json.dump({'mealie': 'https://food.example:9925/'}, f)
        bundled, static = os.path.join(cls.tmp, 'bundled'), os.path.join(cls.tmp, 'static'); os.makedirs(static)
        shutil.copytree(os.path.join(R, 'plugins', 'mealie'), os.path.join(bundled, 'mealie'), ignore=shutil.ignore_patterns('__pycache__'))
        with open(os.path.join(static, 'theme.json'), 'w') as f: f.write('{}')
        with open(os.path.join(static, 'index.html'), 'w') as f: f.write('<!doctype html><title>the page</title><script>const STATE = /*STATE*/null;</script>')
        cls.port = free_port()
        env = {k: v for k, v in os.environ.items() if not k.startswith('ARGUS_')}
        env.update(HOME=home, USERPROFILE=home, ARGUS_BIND='127.0.0.1', ARGUS_PORT=str(cls.port), ARGUS_STATIC=static, ARGUS_BUNDLED=bundled,
                   ARGUS_SYSTEMCTL=sys.executable)
        cls.logpath = os.path.join(cls.tmp, 'server.log'); cls.log = open(cls.logpath, 'w')
        cls.proc = subprocess.Popen([sys.executable, os.path.join(R, 'server', 'argus_ui.py')], env=env, stdout=cls.log, stderr=cls.log)
        for _ in range(150):
            try: socket.create_connection(('127.0.0.1', cls.port), timeout=1).close(); break
            except OSError: time.sleep(.1)
        else:
            cls.tearDownClass(); raise RuntimeError('the server did not start')

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        try: cls.proc.wait(10)
        except subprocess.TimeoutExpired: cls.proc.kill(); cls.proc.wait(10)
        cls.log.close(); cls.srv.shutdown(); cls.srv.server_close(); shutil.rmtree(cls.tmp, ignore_errors=True)

    def get(self, path):
        c = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
        c.request('GET', '/' + path, headers={'Host': '127.0.0.1'}); r = c.getresponse(); body = r.read(); c.close()
        return r.status, body

    def test_status_plan_and_the_page_state(self):
        code, body = self.get('api/mealie/status')
        self.assertEqual((code, json.loads(body)), (200, {'line': 'Tonight: Lentil soup', 'needs': False, 'action': ''}))
        code, body = self.get('api/mealie/plan')
        d = json.loads(body)
        self.assertEqual(d['days'][0]['meals'][0]['href'], 'https://food.example:9925/g/kitchen/r/lentil-soup')
        code, state = self.get('api/state')
        self.assertEqual(code, 200)
        self.assertIn('mealie', [p['id'] for p in json.loads(state).get('plugins', [])], 'the bundled plugin is a section')
        for b in (body, state): self.assertNotIn(b'test-token', b)
        self.log.flush()
        with open(self.logpath, encoding='utf-8', errors='replace') as f: log = f.read()
        self.assertIn('mealie', log, 'the server says it loaded the plugin')
        self.assertNotIn('test-token', log, 'the token is never logged')
        self.assertTrue(all(r['auth'] == 'Bearer ' + TOKEN for r in self.srv.seen))

if __name__ == '__main__':
    unittest.main()
