"""The Memory page's server side without a browser (plugins/memory/plugin.py, docs/memory.md).

    python3 tests/memory_test.py -v        (tests/run.sh runs it under "== memory model")

The fixture folder tests/fixtures/memory/Server-brain/ holds three snapshots plus decoys the plugin must never list.
Each test gets its own temporary folders; the fixture itself is never changed, and no systemctl is ever run."""
import importlib.util, json, os, shutil, sys, tempfile, types, unittest
from datetime import datetime

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = os.path.join(R, 'tests', 'fixtures', 'memory', 'Server-brain')
_spec = importlib.util.spec_from_file_location('leafy_memory', os.path.join(R, 'plugins', 'memory', 'plugin.py'))
m = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(m)
NOW = datetime(2026, 11, 10, 12, 0)           # two days after the newest fixture snapshot
SNAPS = ['Server-brain_2026-11-08_0400.tar.gz', 'Server-brain_2026-11-01_0400.tar.gz', 'Server-brain_2026-10-25_0400.tar.gz']

def job(unit, state='ok', nxt='Sun 4:00 AM', last='Sun 4:03 AM'):
    return dict(job=unit, state=state, next=nxt, last=last)

class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='memory-test-')
        self.mn = os.path.join(self.tmp, 'mnemosyne'); os.makedirs(self.mn)
        shutil.copytree(FIX, os.path.join(self.mn, 'Server-brain'))
        self.saved = {k: getattr(m, k) for k in ('CONFIG', 'MNEMOSYNE', 'GAMEGUARD', 'ALERTS', 'run')}
        m.CONFIG = os.path.join(self.tmp, 'memory.json'); m.MNEMOSYNE = self.mn
        m.GAMEGUARD = os.path.join(self.tmp, 'gameguard', 'frozen-by-me.json'); m.ALERTS = os.path.join(self.tmp, 'alerts')
        os.environ.pop('ARGUS_MEMORY_DIR', None)
        self.ran = []
        m.run = lambda argv: (self.ran.append(list(argv)) or (True, ''))
        self.jobs = [job('mnemosyne-backup'), job('mnemosyne-server-brain')]
        self.ctx = types.SimpleNamespace(jobs=lambda prefix='': [j for j in self.jobs if j['job'].startswith(prefix)], theme_dir=self.tmp)
    def tearDown(self):
        for k, v in self.saved.items(): setattr(m, k, v)
        shutil.rmtree(self.tmp, ignore_errors=True)
    def view(self, now=NOW): return m.view(self.ctx, now)
    def write(self, path, obj):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f: json.dump(obj, f)

class Snapshots(Base):
    def test_three_listed_newest_first_with_sizes(self):
        v = self.view()
        self.assertEqual([s['name'] for s in v['snapshots']], SNAPS)
        sizes = [os.path.getsize(os.path.join(FIX, n)) for n in SNAPS]
        self.assertEqual([s['size'] for s in v['snapshots']], sizes)          # the same numbers as ls -l
        self.assertEqual((v['count'], v['total'], v['shelf']), (3, sum(sizes), 3))
        self.assertEqual(v['last']['age'], '2 days ago'); self.assertEqual(v['last']['size'], sizes[0])
        self.assertEqual(v['folder'], m.tilde(os.path.join(self.mn, 'Server-brain')))
        self.assertEqual(max(s['height'] for s in v['snapshots']), 1.0)        # the biggest bar is full height

    def test_decoys_are_never_listed(self):
        names = [s['name'] for s in self.view()['snapshots']]
        for decoy in ('notes.txt', 'Server-brain_latest.tar.gz', 'Server-brain_2026-11-09_0400.tar.gz'):   # a file, a bad name, a folder
            self.assertNotIn(decoy, names)

    def test_never_outside_the_folder(self):
        outside = os.path.join(self.tmp, 'Server-brain_2026-11-09_0400.tar.gz')
        with open(outside, 'w') as f: f.write('outside the folder')
        link = os.path.join(self.mn, 'Server-brain', 'Server-brain_2026-11-10_0400.tar.gz')
        try: os.symlink(outside, link)
        except (OSError, NotImplementedError): link = None                  # Windows without the symlink right: the rest still runs
        names = [s['name'] for s in self.view()['snapshots']]
        self.assertEqual(names, SNAPS)                                       # neither the symlink nor the file it points at
        q = {'folder': [self.tmp], 'path': ['..']}                            # nothing in a request can move the folder
        self.assertEqual([s['name'] for s in m.get('state', q, self.ctx)[1]['snapshots']], SNAPS)
        if link is None: print('  (symlink check skipped: this system would not make one)', file=sys.stderr)

    def test_reading_changes_nothing(self):
        before = sorted(os.walk(self.tmp))
        m.get('state', {}, self.ctx); m.get('status', {}, self.ctx)
        self.assertEqual(sorted(os.walk(self.tmp)), before)

    def test_folder_from_config_and_missing(self):
        self.write(m.CONFIG, {'folder': os.path.join(self.tmp, 'nowhere')})
        v = self.view(); self.assertFalse(v['found']); self.assertEqual(v['count'], 0)
        self.assertEqual(m.status(v)['line'], 'No snapshots yet')
        os.remove(m.CONFIG); shutil.rmtree(self.mn); os.makedirs(self.mn)
        v = self.view(); self.assertIsNone(v['folder'])

    def test_several_folders_pick_the_brain_units_server(self):
        other = os.path.join(self.mn, 'Aaa-brain'); os.makedirs(other)
        self.assertEqual(self.view()['count'], 3)                            # Server-brain matches mnemosyne-server-brain

class Job(Base):
    def test_next_run_and_unit(self):
        v = self.view()
        self.assertEqual(v['job'], {'unit': 'mnemosyne-server-brain', 'state': 'ok', 'last': 'Sun 4:03 AM', 'next': 'Sun 4:00 AM'})
        self.assertTrue(v['can_backup'])

    def test_older_elaia_without_jobs(self):
        self.ctx = types.SimpleNamespace(theme_dir=self.tmp)
        v = self.view(); self.assertEqual(v['count'], 3); self.assertIsNone(v['job']); self.assertFalse(v['can_backup'])

class Copies(Base):
    def copy(self, key, v=None): return next(c for c in (v or self.view())['copies'] if c['key'] == key)

    def test_three_two_one_honestly(self):
        self.assertEqual(self.copy('server')['state'], 'yes')
        self.assertEqual(self.copy('pc')['state'], 'unknown')               # no marker: unknown, never a guess
        self.assertEqual((self.copy('offsite')['state'], self.copy('offsite')['word']), ('no', 'Not yet'))

    def test_pc_marker(self):
        self.write(os.path.join(self.mn, 'last-backup.json'), {'at': '2026-11-09T03:00:00'})
        self.assertEqual((self.copy('pc')['state'], self.copy('pc')['detail']), ('yes', 'Last copy yesterday'))
        self.write(os.path.join(self.mn, 'last-backup.json'), {'at': '2026-10-01T03:00:00+00:00'})
        self.assertEqual(self.copy('pc')['state'], 'stale')
        self.write(os.path.join(self.mn, 'last-backup.json'), {'at': 'not a time'})
        self.assertEqual(self.copy('pc')['state'], 'unknown')

    def test_offsite_job_when_it_exists(self):
        self.jobs.append(job('mnemosyne-server-offsite'))
        self.assertEqual(self.copy('offsite')['state'], 'yes')
        self.jobs[-1]['state'] = 'failed'
        self.assertEqual((self.copy('offsite')['state'], self.copy('offsite')['word']), ('no', 'Failed'))

    def test_stale_server_copy(self):
        v = self.view(datetime(2026, 11, 20))
        self.assertTrue(v['stale']); self.assertEqual(self.copy('server', v)['state'], 'stale')

class Status(Base):
    def test_line_and_needs(self):
        code, s = m.get('status', {}, self.ctx)                              # the endpoint, on today's clock
        self.assertEqual((code, sorted(s)), (200, ['action', 'line', 'needs']))
        s = m.status(self.view())
        self.assertEqual(s['line'],'Last snapshot 2 days ago · 3 on the server, 2.6 KB · off-site not yet')
        self.assertFalse(s['needs'])
        self.assertLessEqual(len(s['line']), 160)
        s = m.status(self.view(datetime(2026, 11, 20)))
        self.assertTrue(s['needs']); self.assertEqual(s['action'], 'Check backups')
        self.jobs[1]['state'] = 'failed'
        s = m.status(self.view())
        self.assertTrue(s['needs']); self.assertEqual(s['action'], 'Look at the failed backup')
        self.jobs[1]['state'] = 'running'
        self.assertTrue(m.status(self.view())['line'].startswith('Backing up now · '))

class BackUpNow(Base):
    START = [m.SYSTEMCTL, '--user', 'start', '--no-block', 'mnemosyne-server-brain.service']

    def test_starts_the_fixed_unit_only(self):
        code, r = m.post('backup', {'unit': 'evil; rm -rf /', 'job': 'hermes-sort'}, self.ctx)   # the body is never read
        self.assertEqual((code, r['ok']), (200, True))
        self.assertEqual(self.ran, [self.START])

    def test_refused_while_a_game_runs(self):
        self.write(m.GAMEGUARD, ['mnemosyne-library', 'mnemosyne-ollama'])
        code, r = m.post('backup', {}, self.ctx)
        self.assertEqual(code, 409); self.assertIn('game is running', r['msg']); self.assertEqual(self.ran, [])
        self.write(m.GAMEGUARD, [])                                           # the guard thawed: allowed again
        self.assertEqual(m.post('backup', {}, self.ctx)[0], 200)

    def test_refused_while_the_game_alert_is_up(self):
        self.write(os.path.join(m.ALERTS, 'medusa-gameguard.json'), {'job': 'medusa-gameguard', 'level': 'warn', 'message': 'x'})
        self.assertEqual(m.post('backup', {}, self.ctx)[0], 409); self.assertEqual(self.ran, [])

    def test_refused_when_running_frozen_or_missing(self):
        for state, words in (('running', 'running now'), ('frozen', 'frozen')):
            self.jobs[1]['state'] = state
            code, r = m.post('backup', {}, self.ctx)
            self.assertEqual(code, 409); self.assertIn(words, r['msg'])
        self.jobs[1:] = []
        self.assertEqual(m.post('backup', {}, self.ctx)[0], 409)
        self.assertEqual(self.ran, [])

    def test_config_unit_must_be_a_brain_unit(self):
        self.jobs.append(job('mnemosyne-other-brain'))
        self.write(m.CONFIG, {'unit': 'mnemosyne-other-brain'})
        m.post('backup', {}, self.ctx)
        self.write(m.CONFIG, {'unit': 'hermes-sort'})                       # not a brain unit: falls back to the one found
        m.post('backup', {}, self.ctx)
        self.assertEqual([a[-1] for a in self.ran], ['mnemosyne-other-brain.service', 'mnemosyne-server-brain.service'])

    def test_only_backup_is_a_post(self):
        self.assertEqual(m.post('delete', {}, self.ctx)[0], 404)
        self.assertEqual(m.post('restore', {}, self.ctx)[0], 404)
        self.assertEqual(m.get('contents', {}, self.ctx)[0], 404)
        self.assertEqual(self.ran, [])

if __name__ == '__main__':
    unittest.main()
