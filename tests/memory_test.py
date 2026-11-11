"""The Memory page's server side without a browser (plugins/memory/plugin.py, docs/memory.md).

    python3 tests/memory_test.py -v        (tests/run.sh runs it under "== memory model")

The fixture folder tests/fixtures/memory/Server-brain/ holds three snapshots plus decoys the plugin must never list.
Each test gets its own temporary folders; the fixture itself is never changed, and no systemctl is ever run."""
import importlib.util, json, os, re, shutil, sys, tempfile, types, unittest
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
        self.assertEqual(m.status(v)['line'], "The server has no backup yet; no word from your PC's backup yet. No copy outside your home yet.")
        os.remove(m.CONFIG); shutil.rmtree(self.mn); os.makedirs(self.mn)
        v = self.view(); self.assertIsNone(v['folder'])
        self.assertEqual(m.status(v)['line'], "The server has no backup yet; no word from your PC's backup yet. No copy outside your home yet.")

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

KEYS = 'it leaves out your passwords and keys, which need you at the keyboard to type the passphrase'
WATCH = 'look at its weekly job under Mnemosyne on the Watch page'
STATUS_WORDS = re.compile(r'\b(Done|Old|None|Unknown|Not yet|Failed|Not run)\b')   # 1.1.0: never in what the owner reads

class Copies(Base):
    """Every state of the three rows, word for word (docs/memory.md lists the same sentences). NOW is Tuesday, Nov 10,
    12:00; the newest fixture snapshot is Sunday, Nov 8, 4:00 AM."""
    def copy(self, key, v=None): return next(c for c in (v or self.view())['copies'] if c['key'] == key)
    def say(self, key, v=None): return self.copy(key, v)['say']
    def marker(self, obj=None, text=None, bom=False):
        p = os.path.join(self.mn, 'last-backup.json')
        with open(p, 'w', encoding='utf-8-sig' if bom else 'utf-8') as f: f.write(text if text is not None else json.dumps(obj))

    def test_row_names(self):
        self.assertEqual([(c['key'], c['label']) for c in self.view()['copies']],
                         [('server', 'Snapshots the server keeps of itself'), ('pc', "Your PC's own weekly backup"), ('offsite', 'A copy outside your home')])

    # ---- the server's snapshots of itself
    def test_server_fresh(self):
        c = self.copy('server')
        self.assertEqual((c['state'], c['kind']), ('yes', 'fresh'))
        self.assertEqual(c['say'], 'The server took its newest snapshot of itself 2 days ago (Sunday, 4:00 AM) and keeps 3 of them, 2.6 KB in all.')
        one = os.path.join(self.tmp, 'one'); os.makedirs(one); shutil.copy(os.path.join(FIX, SNAPS[0]), one)
        self.write(m.CONFIG, {'folder': one})
        self.assertEqual(self.say('server'), 'The server took its newest snapshot of itself 2 days ago (Sunday, 4:00 AM) and keeps only that one, 900 bytes.')

    def test_server_older_than_eight_days(self):
        v = self.view(datetime(2026, 11, 20)); c = self.copy('server', v)
        self.assertTrue(v['stale']); self.assertEqual((c['state'], c['kind']), ('stale', 'stale'))
        self.assertEqual(c['say'], f"The server's newest snapshot of itself is from 12 days ago (Nov 8, 4:00 AM), older than a week, so {WATCH}.")

    def test_server_eight_day_rule_edge(self):
        self.assertEqual(self.copy('server', self.view(datetime(2026, 11, 16, 5)))['kind'], 'fresh')    # 8 days and an hour: still fresh
        self.assertEqual(self.copy('server', self.view(datetime(2026, 11, 17, 5)))['kind'], 'stale')    # 9 days

    def test_server_none(self):
        os.makedirs(os.path.join(self.tmp, 'empty')); self.write(m.CONFIG, {'folder': os.path.join(self.tmp, 'empty')})
        c = self.copy('server')
        self.assertEqual((c['state'], c['kind']), ('no', 'none'))
        self.assertEqual(c['say'], 'The server has no snapshot of itself yet: hold Back up now to take the first one.')
        self.jobs[1:] = []
        self.assertEqual(self.say('server'), 'The server has no snapshot of itself yet, and no weekly job to take one was found.')

    def test_server_failed_run(self):
        self.jobs[1]['state'] = 'failed'
        c = self.copy('server')
        self.assertEqual((c['state'], c['kind']), ('no', 'failed'))
        self.assertEqual(c['say'], f"The server's newest snapshot of itself is from 2 days ago (Sunday, 4:00 AM), and its last try failed, so {WATCH}.")
        self.assertEqual(self.say('server', self.view(datetime(2026, 11, 20))),
                         f"The server's newest snapshot of itself is from 12 days ago (Nov 8, 4:00 AM), older than a week, and its last try failed, so {WATCH}.")
        self.write(m.CONFIG, {'folder': os.path.join(self.tmp, 'empty')})
        self.assertEqual(self.say('server'), f"The server's first try to take a snapshot of itself failed, so {WATCH}.")

    def test_server_running(self):
        self.jobs[1]['state'] = 'running'
        c = self.copy('server')
        self.assertEqual((c['state'], c['kind']), ('running', 'running'))
        self.assertEqual(c['say'], 'The server is taking a new snapshot of itself now; its newest finished one is from 2 days ago (Sunday, 4:00 AM).')
        self.write(m.CONFIG, {'folder': os.path.join(self.tmp, 'empty')})
        self.assertEqual(self.say('server'), 'The server is taking its first snapshot of itself now.')

    # ---- the PC's own weekly backup, from its marker file
    def test_pc_no_marker(self):
        c = self.copy('pc')
        self.assertEqual((c['state'], c['kind']), ('unknown', 'none'))     # never a guess
        self.assertEqual(c['say'], f"No word has come from your PC's weekly backup yet (the PC sends word each time one finishes); {KEYS}.")

    def test_pc_marker_with_only_at(self):
        self.marker({'at': '2026-11-09T03:00:00'})
        c = self.copy('pc')
        self.assertEqual((c['state'], c['kind']), ('yes', 'fresh'))
        self.assertEqual(c['say'], f"Your PC's weekly backup finished yesterday (Monday, 3:00 AM); {KEYS}.")

    def test_pc_marker_with_sets_and_bytes(self):
        self.marker({'at': '2026-11-09T03:00:00', 'sets': 6, 'bytes': 123456789})
        self.assertEqual(self.say('pc'), f"Your PC's weekly backup finished yesterday (Monday, 3:00 AM) with 6 sets of files, 117.7 MB; {KEYS}.")
        self.marker({'at': '2026-11-09T03:00:00', 'sets': 1, 'bytes': 4.4e9})
        self.assertEqual(self.say('pc'), f"Your PC's weekly backup finished yesterday (Monday, 3:00 AM) with 1 set of files, 4.1 GB; {KEYS}.")
        self.marker({'at': '2026-11-09T03:00:00', 'sets': 4, 'bytes': 12 * 1024 ** 3})
        self.assertEqual(self.say('pc'), f"Your PC's weekly backup finished yesterday (Monday, 3:00 AM) with 4 sets of files, 12 GB; {KEYS}.")

    def test_pc_sets_missing_or_not_a_count(self):
        want = f"Your PC's weekly backup finished yesterday (Monday, 3:00 AM) with 117.7 MB of files; {KEYS}."
        self.marker({'at': '2026-11-09T03:00:00', 'bytes': 123456789})
        self.assertEqual(self.say('pc'), want)
        for bad in ('6', 0, -1, 6.5, True, 10 ** 9, None):                    # not a believable count: left out, never shown as is
            self.marker({'at': '2026-11-09T03:00:00', 'sets': bad, 'bytes': 123456789})
            self.assertEqual(self.say('pc'), want, bad)

    def test_pc_bytes_zero_negative_string_or_broken(self):
        want = f"Your PC's weekly backup finished yesterday (Monday, 3:00 AM) with 6 sets of files; {KEYS}."
        for bad in (0, -5, '123456789', True, 1e300, 2 ** 60, None, [1], {'n': 1}):
            self.marker({'at': '2026-11-09T03:00:00', 'sets': 6, 'bytes': bad})
            self.assertEqual(self.say('pc'), want, bad)
        for raw in ('NaN', 'Infinity', '-Infinity'):                          # Python's json reads these: never "nan MB"
            self.marker(text='{"at": "2026-11-09T03:00:00", "sets": 6, "bytes": %s}' % raw)
            self.assertEqual(self.say('pc'), want, raw)

    def test_pc_older_than_eight_days(self):
        self.marker({'at': '2026-10-01T03:00:00', 'sets': 6, 'bytes': 123456789})
        c = self.copy('pc')
        self.assertEqual((c['state'], c['kind']), ('stale', 'stale'))
        self.assertEqual(c['say'], f"Your PC's weekly backup last finished 40 days ago (Oct 1, 3:00 AM), older than a week, so check its scheduled task on your PC; {KEYS}.")
        self.marker({'at': '2026-10-01T03:00:00+00:00'})                       # a time with a zone is read in this machine's zone
        self.assertEqual(self.copy('pc')['kind'], 'stale')

    def test_pc_marker_not_json(self):
        unread = f"Word came from your PC's weekly backup but could not be read, so this page cannot tell when it last ran (the next backup sends it again); {KEYS}."
        for text in ('not json {', '', '[1, 2]', '{}', '"2026-11-09T03:00:00"', '{"at": "2026-11-09T03:00:00"' + ' ' * m.MARKER_MAX + '}'):
            self.marker(text=text)
            c = self.copy('pc')
            self.assertEqual((c['state'], c['kind'], c['say']), ('unknown', 'unread', unread), text[:40])

    def test_pc_marker_with_a_bom(self):                                     # what Windows PowerShell 5 writes with -Encoding UTF8
        self.marker({'at': '2026-11-09T03:00:00', 'sets': 6, 'bytes': 123456789}, bom=True)
        c = self.copy('pc')
        self.assertEqual((c['state'], c['kind']), ('yes', 'fresh'))
        self.assertEqual(c['say'], f"Your PC's weekly backup finished yesterday (Monday, 3:00 AM) with 6 sets of files, 117.7 MB; {KEYS}.")

    def test_pc_at_not_a_time(self):
        for at in ('not a time', '', 1731000000, None, ['2026-11-09'], '2026-13-45T99:00:00'):
            self.marker({'at': at, 'sets': 6})
            self.assertEqual((self.copy('pc')['state'], self.copy('pc')['kind']), ('unknown', 'unread'), at)

    def test_pc_at_in_the_future(self):
        self.marker({'at': '2026-11-10T15:00:00', 'sets': 6, 'bytes': 123456789})     # three hours ahead: another clock
        c = self.copy('pc')
        self.assertEqual((c['state'], c['kind']), ('yes', 'fresh'))
        self.assertEqual(c['say'], f"Your PC's weekly backup finished just now with 6 sets of files, 117.7 MB; {KEYS}.")
        self.assertNotIn('in 3 hours', c['say'])
        self.marker({'at': '2026-11-20T03:00:00'})                              # ten days ahead: that clock is wrong, so it is not fresh
        c = self.copy('pc')
        self.assertEqual((c['state'], c['kind']), ('unknown', 'ahead'))
        self.assertEqual(c['say'], f"Word came from your PC's weekly backup with a time still ahead of this server's clock (Nov 20, 3:00 AM), so check the date and time on your PC; {KEYS}.")

    # ---- the copy outside the home
    def test_offsite_no_job(self):
        c = self.copy('offsite')
        self.assertEqual((c['state'], c['kind']), ('no', 'missing'))
        self.assertEqual(c['say'], 'No copy of your backups is kept outside your home yet: the job that will keep one is planned but not built.')

    def test_offsite_never_run(self):
        self.jobs.append(dict(job('mnemosyne-server-offsite', 'never', last='—'), started=''))
        c = self.copy('offsite')
        self.assertEqual((c['state'], c['kind']), ('unknown', 'never'))
        self.assertEqual(c['say'], 'The job that keeps a copy of your backups outside your home is set up but has not run yet: see when it runs under Mnemosyne on the Watch page.')

    def test_offsite_failed(self):
        self.jobs.append(dict(job('mnemosyne-server-offsite', 'failed'), started='2026-11-08 04:30:00'))
        c = self.copy('offsite')
        self.assertEqual((c['state'], c['kind']), ('no', 'failed'))
        self.assertEqual(c['say'], 'The last try to copy your backups outside your home failed 2 days ago (Sunday, 4:30 AM), so look at its job under Mnemosyne on the Watch page.')

    def test_offsite_done(self):
        self.jobs.append(dict(job('mnemosyne-server-offsite'), started='2026-11-08 04:30:00'))
        c = self.copy('offsite')
        self.assertEqual((c['state'], c['kind']), ('yes', 'done'))
        self.assertEqual(c['say'], 'Your backups were last copied outside your home 2 days ago (Sunday, 4:30 AM).')
        del self.jobs[-1]['started']                                           # an older Elaia without "started"
        self.assertEqual(self.say('offsite'), 'Your backups have been copied outside your home.')

    def test_offsite_running(self):
        self.jobs.append(dict(job('mnemosyne-server-offsite', 'running'), started='2026-11-10 11:55:00'))
        self.assertEqual((self.copy('offsite')['state'], self.say('offsite')), ('running', 'Your backups are being copied outside your home now.'))

class Times(Base):
    def test_ages_and_clock_times(self):
        cases = [(datetime(2026, 11, 10, 11, 59, 30), 'just now (11:59 AM)'), (datetime(2026, 11, 10, 11, 15), '45 min ago (11:15 AM)'),
                 (datetime(2026, 11, 10, 9, 0), '3 hours ago (9:00 AM)'), (datetime(2026, 11, 9, 23, 0), '13 hours ago (Monday, 11:00 PM)'),
                 (datetime(2026, 11, 8, 13, 0), '2 days ago (Sunday, 1:00 PM)'),        # 47 hours, two calendar days: never "yesterday (Sunday)"
                 (datetime(2026, 11, 3, 4, 0), '7 days ago (Nov 3, 4:00 AM)'), (datetime(2025, 10, 1, 3, 0), '405 days ago (Oct 1, 2025, 3:00 AM)'),
                 (datetime(2026, 11, 10, 15, 0), 'just now')]
        for at, want in cases: self.assertEqual(m.ago(at, NOW), want)

    def test_sizes(self):
        for n, want in ((123456789, '117.7 MB'), (4.4e9, '4.1 GB'), (12 * 1024 ** 3, '12 GB'), (5000, 'under 0.1 MB'), (1048000000, '999.5 MB'), (1048500000, '1 GB'),
                        (0, None), (-1, None), ('5', None), (float('nan'), None), (float('inf'), None), (2 ** 60, None), (True, None)):
            self.assertEqual(m.mb_gb(n), want, n)

class Status(Base):
    """Home's line: one plain sentence for the server and the PC, then one for the copy outside the home."""
    def marker(self, obj): self.write(os.path.join(self.mn, 'last-backup.json'), obj)

    def test_line_and_needs(self):
        code, s = m.get('status', {}, self.ctx)                              # the endpoint, on today's clock
        self.assertEqual((code, sorted(s)), (200, ['action', 'line', 'needs']))
        s = m.status(self.view())
        self.assertEqual(s['line'], "The server backed up 2 days ago; no word from your PC's backup yet. No copy outside your home yet.")
        self.assertFalse(s['needs']); self.assertEqual(s['action'], '')
        s = m.status(self.view(datetime(2026, 11, 20)))
        self.assertTrue(s['needs']); self.assertEqual(s['action'], 'Check backups')
        self.jobs[1]['state'] = 'failed'
        s = m.status(self.view())
        self.assertTrue(s['needs']); self.assertEqual(s['action'], 'Look at the failed backup')
        self.jobs[1]['state'] = 'running'
        self.assertTrue(m.status(self.view())['line'].startswith('Backing up the server now'))

    def test_every_combination(self):
        fresh, old = {'at': '2026-11-09T03:00:00', 'sets': 6, 'bytes': 123456789}, {'at': '2026-10-01T03:00:00'}
        line = lambda now=NOW: m.status(self.view(now))['line']
        self.marker(fresh)
        self.assertEqual(line(), 'Backups are fresh: the server 2 days ago, your PC yesterday. No copy outside your home yet.')
        self.marker(old)
        self.assertEqual(line(), "The server backed up 2 days ago; your PC's backup is older than a week (40 days ago). No copy outside your home yet.")
        self.marker({'at': '2026-11-19T03:00:00'})
        self.assertEqual(line(datetime(2026, 11, 20)), "The server's backup is older than a week (12 days ago); your PC backed up 21 hours ago. No copy outside your home yet.")
        self.marker(old)
        self.assertEqual(line(datetime(2026, 11, 20)), "The server's backup is older than a week (12 days ago); your PC's backup is older than a week (50 days ago). No copy outside your home yet.")
        self.marker(fresh); self.jobs[1]['state'] = 'failed'
        self.assertEqual(line(), "The server's last backup failed; your PC backed up yesterday. No copy outside your home yet.")
        self.jobs[1]['state'] = 'running'
        self.assertEqual(line(), 'Backing up the server now; your PC backed up yesterday. No copy outside your home yet.')
        self.jobs[1]['state'] = 'ok'
        self.jobs.append(dict(job('mnemosyne-server-offsite'), started='2026-11-08 04:30:00'))
        self.assertEqual(line(), 'Backups are fresh: the server 2 days ago, your PC yesterday. Copied outside your home 2 days ago.')
        self.jobs[-1]['state'] = 'failed'
        self.assertEqual(line(), 'Backups are fresh: the server 2 days ago, your PC yesterday. The copy outside your home failed.')
        self.jobs[-1]['state'] = 'running'
        self.assertEqual(line(), 'Backups are fresh: the server 2 days ago, your PC yesterday. Copying outside your home now.')
        self.jobs[-1]['state'] = 'never'
        self.assertEqual(line(), 'Backups are fresh: the server 2 days ago, your PC yesterday. No copy outside your home yet.')
        self.write(m.CONFIG, {'folder': os.path.join(self.tmp, 'empty')})
        self.assertEqual(line(), 'The server has no backup yet; your PC backed up yesterday. No copy outside your home yet.')
        self.jobs[1]['state'] = 'running'          # said first, also before the first snapshot
        self.assertEqual(line(), 'Backing up the server now; your PC backed up yesterday. No copy outside your home yet.')

class Words(Base):
    """1.1.0: what the owner reads has no status words and never the word 'secrets', in every state the tests can make."""
    def test_no_status_words_anywhere(self):
        markers = [None, {'at': '2026-11-09T03:00:00', 'sets': 6, 'bytes': 123456789}, {'at': '2026-10-01T03:00:00'}, {'at': 'x'}, {'at': '2026-11-20T03:00:00'}]
        p, seen = os.path.join(self.mn, 'last-backup.json'), 0
        for state in ('ok', 'failed', 'running', 'never', 'frozen'):
            for mk in markers:
                if mk is None:
                    if os.path.exists(p): os.remove(p)
                else: self.write(p, mk)
                for off in (None, 'ok', 'failed', 'never', 'running'):
                    for now in (NOW, datetime(2026, 11, 20)):
                        self.jobs[1]['state'] = state
                        self.jobs[2:] = [dict(job('mnemosyne-server-offsite', off), started='2026-11-08 04:30:00')] if off else []
                        v = self.view(now); line = m.status(v)['line']
                        for t in [c['say'] for c in v['copies']] + [c['label'] for c in v['copies']] + [line]:
                            self.assertIsNone(STATUS_WORDS.search(t), t); self.assertNotIn('secret', t.lower())
                        self.assertTrue(all(c['say'].endswith('.') and 'word' not in c and 'detail' not in c for c in v['copies']))
                        self.assertLessEqual(len(line), 160, line)
                        seen += 1
        self.assertEqual(seen, 5 * 5 * 5 * 2)

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
