"""The 4.48.0 naming on a real server, no browser. Runs on any OS, Windows included.

    python3 tests/naming_test.py -v        (tests/run.sh runs it under "== naming")

  * the Leafy Realm theme: the page is called LeafyGrove; ten agents with one verb each; the retired ones (Heracles, Chronos,
    Poseidon, Hephaestus, Elaia, the Apollo prefix) are not agents; every agent has a medallion
  * renamed_prefixes: a job still called apollo-<name> on the host shows as Calliope's task <name> (display only); a bad
    entry in the map (an agent's own key, an unknown agent, not a plain word) is ignored
  * the retired agents' old addresses land where their work went (302, relative, not cached), only while that place exists
  * nothing a person reads in web/ says Elaia any more (the lower-case storage and wire keys stay, so phones keep working)
The server runs in its own process with a temporary HOME and fake units (tests/fixtures/fake_systemctl.py)."""
import http.client, json, os, re, shutil, socket, subprocess, sys, tempfile, time, unittest

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
THEME = os.path.join(R, 'themes', 'leafy-realm')
TEN = ['argus', 'zeus', 'medusa', 'hermes', 'janus', 'mnemosyne', 'mentor', 'chiron', 'calliope', 'daedalus']
RETIRED = ['heracles', 'chronos', 'poseidon', 'hephaestus', 'elaia', 'apollo']
ON = {'ActiveState': 'active', 'Result': 'success'}


def put(path, data):
    with open(path, 'w', encoding='utf-8') as f: f.write(data if isinstance(data, str) else json.dumps(data))


class Theme(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(THEME, 'theme.json'), encoding='utf-8') as f: self.t = json.load(f)

    def test_the_page_is_called_leafygrove(self):
        self.assertEqual(self.t['title'], 'LeafyGrove')
        with open(os.path.join(R, 'web', 'manifest.webmanifest'), encoding='utf-8') as f: m = json.load(f)
        self.assertEqual((m['name'], m['short_name']), ('LeafyGrove', 'LeafyGrove'))

    def test_ten_agents_one_verb_each(self):
        self.assertEqual(sorted(a['key'] for a in self.t['agents']), sorted(TEN))
        verbs = {a['key']: a['domain'].split(' · ')[0] for a in self.t['agents']}
        self.assertEqual(verbs, {'argus': 'Watch', 'zeus': 'Decide', 'medusa': 'Pause', 'hermes': 'Carry', 'janus': 'Check',
                                 'mnemosyne': 'Keep', 'mentor': 'Teach', 'chiron': 'Train', 'calliope': 'Make music', 'daedalus': 'Build'})
        for k in RETIRED: self.assertNotIn(k, verbs, f'{k} is retired from the page')

    def test_every_agent_has_a_medallion(self):
        for k in TEN: self.assertTrue(os.path.isfile(os.path.join(THEME, 'icons', k + '.png')), k)

    def test_no_elaia_a_person_reads_in_web(self):
        for root, _, files in os.walk(os.path.join(R, 'web')):
            for n in files:
                if not n.endswith(('.html', '.js', '.css', '.webmanifest')): continue
                with open(os.path.join(root, n), encoding='utf-8') as f: text = f.read()
                self.assertEqual(re.findall(r'\bElaia\b', text), [], n)


class OnTheServer(unittest.TestCase):
    """The real server (server/argus_ui.py) with the Leafy Realm theme plus one old apollo- job and the map's bad entries."""
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='naming-test-')
        home, static, fx = (os.path.join(cls.tmp, d) for d in ('home', 'static', 'fx'))
        for d in (home, static, fx): os.makedirs(d)
        with open(os.path.join(THEME, 'theme.json'), encoding='utf-8') as f: t = json.load(f)
        t['renamed_prefixes'] = dict(t.get('renamed_prefixes', {}), zeus='argus', ghost='nowhere', nobody='poseidon', **{'Bad-Key': 'calliope'})
        put(os.path.join(static, 'theme.json'), t)
        put(os.path.join(static, 'index.html'), '<!doctype html><title>the page</title><script>const STATE = /*STATE*/null;</script>')
        shutil.copy(os.path.join(R, 'tests', 'fixtures', 'fake_systemctl.py'), fx)
        put(os.path.join(fx, 'units.json'), {'apollo-studio': dict(ON, Description='the Studio'), 'hermes-mail': dict(ON),
                                             'heracles-old': dict(ON), 'zeus-deploy': dict(ON)})
        if os.name == 'nt':
            sc = os.path.join(fx, 'systemctl.cmd'); put(sc, f'@"{sys.executable}" "{os.path.join(fx, "fake_systemctl.py")}" %*\n')
        else:
            sc = os.path.join(fx, 'systemctl'); put(sc, f'#!/bin/sh\nexec "{sys.executable}" "{os.path.join(fx, "fake_systemctl.py")}" "$@"\n'); os.chmod(sc, 0o755)
        with socket.socket() as s: s.bind(('127.0.0.1', 0)); cls.port = s.getsockname()[1]
        env = {k: v for k, v in os.environ.items() if not k.startswith('ARGUS_')}
        env.update(HOME=home, USERPROFILE=home, ARGUS_BIND='127.0.0.1', ARGUS_PORT=str(cls.port), ARGUS_STATIC=static, ARGUS_WATCH='0',
                   ARGUS_BUNDLED=os.path.join(cls.tmp, 'bundled'), ARGUS_SYSTEMCTL=sc)
        env.pop('ARGUS_PEOPLE', None)
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
        c = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
        c.request('GET', '/' + path, headers={'Host': '127.0.0.1'})
        r = c.getresponse(); body = r.read(); c.close()
        return r.status, {k.lower(): v for k, v in r.getheaders()}, body

    def state(self):
        code, _, body = self.get('api/state'); self.assertEqual(code, 200); return json.loads(body)

    def test_an_old_apollo_job_shows_as_calliopes(self):
        s = self.state()
        studio = [j for j in s['jobs'] if j['job'] == 'apollo-studio']
        self.assertEqual([(j['persona'], j['name']) for j in studio], [('calliope', 'studio')], 'the unit keeps its name, Calliope owns it')
        self.assertEqual(s['renamed'], {'apollo': 'calliope'}, 'only a plain old word that is no agent, onto an agent of this theme')
        self.assertEqual(sorted(p['key'] for p in s['personas']), sorted(TEN))

    def test_a_retired_agents_job_is_not_watched(self):
        self.assertNotIn('heracles-old', [j['job'] for j in self.state()['jobs']], 'heracles- is no agent and not renamed: not on the page')

    def test_a_job_of_an_agent_named_in_the_map_stays_its_own(self):
        self.assertEqual([j['persona'] for j in self.state()['jobs'] if j['job'] == 'zeus-deploy'], ['zeus'])

    def test_old_addresses_land_where_the_work_went(self):
        for path, want in (('heracles', 'chiron'), ('chronos', 'home'), ('poseidon', 'home'),
                           ('argus/heracles', 'chiron'), ('heracles/', '../chiron'), ('poseidon?from=bookmark', 'home?from=bookmark')):
            code, headers, body = self.get(path)
            self.assertEqual((code, headers.get('location'), body), (302, want, b''), path)
            self.assertEqual(headers.get('cache-control'), 'no-store', path)
        # hephaestus goes to Controllers (the section Daedalus names) only while that plugin is installed (controllers_test.py
        # checks the move); this server has no Controllers, so the old address is a plain 404, never a server error
        self.assertEqual(self.get('hephaestus')[0], 404)

    def test_the_new_places_open(self):
        for path in ('chiron', 'daedalus', 'calliope', 'home'):
            self.assertEqual(self.get(path)[0], 200, path)

    def test_an_old_api_address_is_not_found_while_no_plugin_lives_at_the_new_one(self):
        self.assertEqual(self.get('api/heracles/status')[0], 404, 'no Chiron plugin here: nothing to say "reload" for, and never a 500')


if __name__ == '__main__':
    unittest.main()
