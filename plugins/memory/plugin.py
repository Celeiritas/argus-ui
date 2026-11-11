# Memory: are Mnemosyne's backups fresh, and how many copies exist? A bundled server plugin (docs/ui-plan.md §10,
# docs/memory.md). It only reads: the names and sizes of the snapshot files directly inside one folder, Elaia's task
# info (ctx.jobs), the PC's marker file and Medusa's game-guard state. Its one action starts the brain job's own unit,
# with fixed arguments that never come from the request. It never deletes, restores, or opens a snapshot (they hold
# passwords and keys).
# Since 1.1.0 each copy is told in one plain sentence (what it is, when it was last made, and what to do only when
# something is not fine); docs/memory.md lists every sentence, and tests/memory_test.py checks each one word for word.
import json, math, os, re, subprocess
from datetime import datetime

CONFIG = os.path.expanduser(os.environ.get('ARGUS_MEMORY_CONFIG', '~/.config/argus-ui/memory.json'))
MNEMOSYNE = os.path.expanduser(os.environ.get('ARGUS_MNEMOSYNE', '~/.mnemosyne'))     # where <Server>-brain/ is looked for
SYSTEMCTL = os.environ.get('ARGUS_SYSTEMCTL', 'systemctl')                            # the same one Elaia's powers use
GAMEGUARD = os.path.expanduser(os.environ.get('ARGUS_GAMEGUARD', '~/.local/state/medusa-gameguard/frozen-by-me.json'))
ALERTS = os.path.expanduser(os.environ.get('ARGUS_ALERTS', '~/.local/state/argus-ui/alerts'))
HOME = os.path.expanduser('~')

# <server>-brain_<YYYY-MM-DD>_<HHMM>[SS].tar.gz, as the brain job names them (date +%F_%H%M)
SNAP = re.compile(r'^(?P<host>[A-Za-z0-9][A-Za-z0-9.-]{0,62})-brain_(?P<d>\d{4}-\d{2}-\d{2})_(?P<t>\d{4})(?P<s>\d{2})?\.tar\.gz$')
BRAIN = re.compile(r'^mnemosyne-[a-z0-9][a-z0-9-]{0,40}-brain$')       # the only kind of unit Back up now may start
OFFSITE = re.compile(r'^mnemosyne-[a-z0-9][a-z0-9-]{0,40}-offsite$')
STALE_DAYS = 8          # the brain job runs weekly: a day of slack, then Home says it needs you
SHELF = 12              # jars on the shelf (the newest); the list under it has them all
NOTE = 'Jellyfin pauses for about a minute while the snapshot is made.'
AHEAD = 86400           # a marker up to a day ahead of this clock is another machine's clock: it reads "just now"
MAX_BYTES = 2 ** 44     # 16 TB: no weekly PC backup is bigger; a larger number is broken and is never shown
MAX_SETS = 999
MARKER_MAX = 65536      # the marker is a few dozen bytes; more than this is not read
# the row names (docs/memory.md): what each copy is, in plain words
NAMES = {'server': 'Snapshots the server keeps of itself', 'pc': "Your PC's own weekly backup", 'offsite': "The server's copy outside your home"}
KEYS = 'your passwords and keys are left out on purpose: you back those up by hand, typing the passphrase'
WATCH = 'look at its weekly job under Mnemosyne on the Watch page'

def init(ctx):
    global ALERTS
    if 'ARGUS_ALERTS' not in os.environ:      # the theme may move the alert folder (docs/alerts.md), as Elaia's server reads it
        try:
            with open(os.path.join(ctx.theme_dir, 'theme.json'), encoding='utf-8') as f: a = json.load(f).get('alerts')
            if isinstance(a, str) and a: ALERTS = os.path.expanduser(a)
        except (OSError, ValueError, AttributeError): pass

def config():
    """~/.config/argus-ui/memory.json, read on every call: {"folder", "unit", "pc_marker", "note"}, all optional."""
    try:
        with open(CONFIG, encoding='utf-8') as f: c = json.load(f)
    except (OSError, ValueError): c = {}
    return c if isinstance(c, dict) else {}

def tilde(p):
    return '~' + p[len(HOME):].replace('\\', '/') if p and p.startswith(HOME) else p

def folder(c, hint=''):
    """The snapshot folder: memory.json's "folder", else ARGUS_MEMORY_DIR, else the one ~/.mnemosyne/<Server>-brain/
    (when there are several, the one matching the brain unit's server, else the first by name). None when there is none."""
    f = c.get('folder') if isinstance(c.get('folder'), str) else ''
    f = f or os.environ.get('ARGUS_MEMORY_DIR', '')
    if f: return os.path.expanduser(f)
    try: found = sorted(n for n in os.listdir(MNEMOSYNE) if n.endswith('-brain') and os.path.isdir(os.path.join(MNEMOSYNE, n)))
    except OSError: return None
    pick = [n for n in found if hint and n.lower() == hint + '-brain'] or found
    return os.path.join(MNEMOSYNE, pick[0]) if pick else None

def snapshots(path):
    """The snapshot files directly inside path, newest first: name, time (from the name), size. Only regular files whose
    names match; never a symlink, a subfolder or anything outside path, and never their contents. None if unreadable."""
    if not path: return None
    out = []
    try: it = os.scandir(path)
    except OSError: return None
    with it:
        for e in it:
            m = SNAP.match(e.name)
            if not m: continue
            try:
                if e.is_symlink() or not e.is_file(follow_symlinks=False): continue
                at = datetime.strptime(f"{m['d']} {m['t']}{m['s'] or '00'}", '%Y-%m-%d %H%M%S')
                size = e.stat(follow_symlinks=False).st_size
            except (OSError, ValueError): continue
            out.append(dict(name=e.name, host=m['host'], at=at, size=size))
    return sorted(out, key=lambda s: (s['at'], s['name']), reverse=True)

def size_h(n):
    for u in ('bytes', 'KB', 'MB', 'GB', 'TB'):
        if n < 1024 or u == 'TB': return f'{n:.0f} {u}' if u == 'bytes' or n >= 10 else f'{n:.1f} {u}'
        n /= 1024

def age(at, now):
    """'just now', '5 min ago', '3 hours ago' within a day; after that by the calendar ('yesterday', '3 days ago'), so the
    age and the weekday beside it never disagree. A time ahead of now (another clock) is 'just now', never 'in 3 hours'."""
    s = (now - at).total_seconds()
    if s < 60: return 'just now'
    if s < 3600: return f'{int(s // 60)} min ago'
    if s < 86400: h = int(s // 3600); return f"{h} hour{'s' if h != 1 else ''} ago"
    d = days_between(at, now)
    return 'yesterday' if d == 1 else f'{d} days ago'

def days_between(at, now):
    """Whole calendar days from `at` to `now`: the number the age shows ('9 days ago'), so a rule using it can never
    disagree with the words beside it (midnight and daylight-saving hours do not matter)."""
    return (now.date() - at.date()).days

def when(at):
    return at.strftime('%b %d, %I:%M %p').replace(' 0', ' ')

def clock(at):
    return at.strftime('%I:%M %p').lstrip('0')         # '4:31 AM' on every system (%-I does not exist on Windows)

def stamp(at, now):
    """The clock time beside an age: '4:31 AM' today, 'Sunday, 4:31 AM' within the week, 'Oct 25, 4:00 AM' before that
    (with the year when it is another year's), and the date for a time that is still ahead."""
    d = (now.date() - at.date()).days
    if d == 0: return clock(at)
    if 0 < d < 7: return f"{at.strftime('%A')}, {clock(at)}"
    day = f"{at.strftime('%b')} {at.day}"
    return f'{day}, {clock(at)}' if at.year == now.year else f'{day}, {at.year}, {clock(at)}'

def ago(at, now):
    """'3 days ago (Sunday, 4:31 AM)'. A time ahead of now is 'just now', with no clock time that has not happened yet."""
    return 'just now' if at > now else f'{age(at, now)} ({stamp(at, now)})'

def mb_gb(n):
    """Bytes as MB or GB with at most one decimal ('117.7 MB', '4.1 GB', '12 GB'). None for anything that is not a
    believable size: not a number, true/false, not finite, zero, negative, or over MAX_BYTES."""
    if isinstance(n, bool) or not isinstance(n, (int, float)) or not math.isfinite(n) or n <= 0 or n > MAX_BYTES: return None
    v, u = n / 1024 ** 2, 'MB'
    if v >= 999.5: v, u = n / 1024 ** 3, 'GB'
    if v < 0.05: return 'under 0.1 MB'
    t = f'{v:.1f}'
    return f"{t[:-2] if t.endswith('.0') else t} {u}"

def count(n):
    """A believable number of sets: a whole number from 1 to MAX_SETS, else None."""
    return n if isinstance(n, int) and not isinstance(n, bool) and 0 < n <= MAX_SETS else None

def job_time(j):
    """When a task last started, from Elaia's sortable 'started' ('2026-11-08 04:00:00'); None when it has none."""
    try: return datetime.strptime(str(j.get('started') or ''), '%Y-%m-%d %H:%M:%S')
    except ValueError: return None

def jobs(ctx):
    try: return [j for j in ctx.jobs('mnemosyne-') if isinstance(j, dict)]
    except Exception: return []        # an older Elaia without ctx.jobs: the page still shows the snapshots

def brain_job(c, js, host=''):
    """The brain job's task: memory.json's "unit" if it names a mnemosyne-<server>-brain unit that exists, else the one
    such unit (the one matching the snapshots' server if there are several). None when there is none."""
    want = c.get('unit') if isinstance(c.get('unit'), str) and BRAIN.match(c.get('unit')) else ''
    found = [j for j in js if BRAIN.match(j.get('job', ''))]
    if want: return next((j for j in found if j['job'] == want), None)
    if host: found = [j for j in found if j['job'] == f'mnemosyne-{host.lower()}-brain'] or found
    return found[0] if found else None

def game():
    """True while Medusa's game guard says a game runs: its frozen-by-me.json lists what it froze, or its alert file is up."""
    try:
        with open(GAMEGUARD, encoding='utf-8') as f: mine = json.load(f)
        if isinstance(mine, list) and mine: return True
    except (OSError, ValueError): pass
    return os.path.isfile(os.path.join(ALERTS, 'medusa-gameguard.json'))

def parse_time(v):
    """An ISO time as this machine's local time without a zone; None for anything else (a number, a broken string)."""
    if not isinstance(v, str): return None
    try:
        t = datetime.fromisoformat(v.strip().replace('Z', '+00:00'))
        return t.astimezone().replace(tzinfo=None) if t.tzinfo else t
    except (ValueError, OverflowError, OSError): return None

def copy(key, state, kind, say, when_=None):
    """One row of the copies: its name, a mark's state (yes ✓, stale !, no ✕, unknown ?, running ↻), what happened
    (kind, for Home's line and the tests), the one sentence the page shows, and the plain age for Home's line."""
    return dict(key=key, label=NAMES[key], state=state, kind=kind, say=say, age=when_)

def server_copy(s, now, job, stale, total_h):
    """Copy 1: the snapshots the server keeps of itself, with what its weekly (brain) job is doing."""
    last = s[0]['at'] if s else None
    st = job.get('state') if job else ''
    a = age(last, now) if last else None
    if st == 'running':
        return copy('server', 'running', 'running', f'The server is taking a new snapshot of itself now; its newest finished one is from {ago(last, now)}.'
                    if last else 'The server is taking its first snapshot of itself now.', a)
    if st == 'failed':
        return copy('server', 'no', 'failed', f"The server's newest snapshot of itself is from {ago(last, now)}{', older than a week,' if stale else ','} and its last try failed, so {WATCH}."
                    if last else f"The server's first try to take a snapshot of itself failed, so {WATCH}.", a)
    if not last:
        return copy('server', 'no', 'none', 'The server has no snapshot of itself yet: its weekly job is paused; press Resume on its card on the Watch page first.'
                    if job and job.get('state') == 'frozen' else
                    'The server has no snapshot of itself yet: hold Back up now to take the first one.' if job else 'The server has no snapshot of itself yet, and no weekly job to take one was found.')
    if stale:
        return copy('server', 'stale', 'stale', f"The server's newest snapshot of itself is from {ago(last, now)}, older than a week, so {WATCH}.", a)
    n = len(s)
    keeps = f'only that one, {total_h}' if n == 1 else f'{n} of them, {total_h} in all'
    return copy('server', 'yes', 'fresh', f'The server took its newest snapshot of itself {ago(last, now)} and keeps {keeps}.', a)

def marker(c):
    """The PC's marker file, as (kind, value): ('none', None) when there is no file, ('unread', None) when it is not a
    JSON object, else ('ok', dict). A byte-order mark (Windows PowerShell 5 writes one) is fine."""
    p = os.path.expanduser(c['pc_marker']) if isinstance(c.get('pc_marker'), str) else os.path.join(MNEMOSYNE, 'last-backup.json')
    if not os.path.lexists(p): return 'none', None
    try:
        with open(p, encoding='utf-8-sig') as f: text = f.read(MARKER_MAX + 1)
        if len(text) > MARKER_MAX: return 'unread', None
        m = json.loads(text)
    except (OSError, ValueError, RecursionError): return 'unread', None
    return ('ok', m) if isinstance(m, dict) else ('unread', None)

def pc_copy(c, now):
    """Copy 2, the PC's own weekly backup: it writes last-backup.json ({"at", "sets", "bytes"}) and the file comes to the
    server. The PC's folder can't be seen from here, so without that file the row says so, never a guess. "sets" and
    "bytes" are shown only when they are believable; the sentence always says what the weekly run leaves out."""
    kind, m = marker(c)
    if kind == 'none':
        return copy('pc', 'unknown', 'none', f"No word has come from your PC's weekly backup yet (the PC sends word each time one finishes); {KEYS}.")
    at = parse_time(m.get('at')) if m else None
    if not at:
        return copy('pc', 'unknown', 'unread', f"Word came from your PC's weekly backup but could not be read, so this page cannot tell when it last ran (the next backup sends it again); {KEYS}.")
    if (at - now).total_seconds() > AHEAD:
        return copy('pc', 'unknown', 'ahead', f"Word came from your PC's weekly backup with a time still ahead of this server's clock ({stamp(at, now)}), so check the date and time on your PC; {KEYS}.")
    if days_between(at, now) > STALE_DAYS:
        return copy('pc', 'stale', 'stale', f"Your PC's weekly backup last finished {ago(at, now)}, older than a week, so check its scheduled task on your PC; {KEYS}.", age(at, now))
    sets, size = count(m.get('sets')), mb_gb(m.get('bytes'))
    parts = [f"{sets} set{'s' if sets != 1 else ''} of files"] if sets else []
    if size: parts.append(size if sets else f'{size} of files')
    what = f" with {', '.join(parts)}" if parts else ''
    return copy('pc', 'yes', 'fresh', f"Your PC's weekly backup finished {ago(at, now)}{what}; {KEYS}.", age(at, now))

def offsite_copy(js, now):
    """Copy 3, outside the home: the mnemosyne-<server>-offsite job, once it exists."""
    j = next((j for j in js if OFFSITE.match(j.get('job', ''))), None)
    if not j:
        return copy('offsite', 'no', 'missing', "The server's backups are not copied outside your home yet: the job that will do that is planned but not built.")
    st, t = j.get('state'), job_time(j)
    a = age(t, now) if t else None
    if st == 'never':
        return copy('offsite', 'unknown', 'never', "The job that copies the server's backups outside your home is set up but has not run yet: see when it runs under Mnemosyne on the Watch page.")
    if st == 'running':
        return copy('offsite', 'running', 'running', "The server's backups are being copied outside your home now.", a)
    if st == 'failed':
        return copy('offsite', 'no', 'failed', f"The last try to copy the server's backups outside your home failed{' ' + ago(t, now) if t else ''}, so look at its job under Mnemosyne on the Watch page.", a)
    return copy('offsite', 'yes', 'done', f"The server's backups were last copied outside your home {ago(t, now)}." if t
                else "The server's backups have been copied outside your home.", a)

def view(ctx, now=None):
    """Everything the page and Home's line show. Reads only."""
    now = now or datetime.now(); c = config(); js = jobs(ctx)
    pre = brain_job(c, js)                                   # the unit's server name picks the folder when there are several
    path = folder(c, pre['job'][len('mnemosyne-'):-len('-brain')] if pre else '')
    snaps = snapshots(path)
    job = brain_job(c, js, snaps[0]['host'] if snaps else '')
    s = snaps or []
    last = s[0] if s else None
    stale = bool(last) and days_between(last['at'], now) > STALE_DAYS
    total_h = size_h(sum(x['size'] for x in s))
    running = bool(job) and job.get('state') == 'running'
    why = ''
    if not job: why = 'No brain job found (a mnemosyne-<server>-brain unit), so there is nothing to start.'
    elif job.get('state') == 'frozen': why = 'The brain job is frozen: thaw it on the Watch page first.'
    elif running: why = 'A backup is running now.'
    elif game(): why = 'A game is running: Back up now waits until it has been closed for a minute.'
    biggest = max((x['size'] for x in s[:SHELF]), default=0)
    return dict(
        folder=tilde(path) if path else None, found=snaps is not None,
        snapshots=[dict(name=x['name'], iso=x['at'].isoformat(), date=x['at'].strftime('%b %d').replace(' 0', ' '),
                        day=x['at'].day, month=x['at'].strftime('%b'), when=when(x['at']), age=age(x['at'], now),
                        size=x['size'], size_h=size_h(x['size']), height=round(x['size'] / biggest, 3) if biggest else 0)
                   for x in s],
        shelf=min(len(s), SHELF), count=len(s), total=sum(x['size'] for x in s), total_h=total_h,
        last=dict(age=age(last['at'], now), when=when(last['at']), size_h=size_h(last['size']), size=last['size']) if last else None,
        stale=stale, stale_days=STALE_DAYS,
        job=dict(unit=job['job'], state=job.get('state', ''), last=job.get('last', ''), next=job.get('next', '')) if job else None,
        running=running, copies=[server_copy(s, now, job, stale, total_h), pc_copy(c, now), offsite_copy(js, now)],
        can_backup=not why, why_not=why, note=str(c.get('note') or NOTE)[:200])

def today(v):
    """Home's line, read in two seconds: the server and the PC first (a running backup said first), then the copy outside
    the home. Every combination is in docs/memory.md."""
    sv, pc, off = (next(x for x in v['copies'] if x['key'] == k) for k in ('server', 'pc', 'offsite'))
    if sv['kind'] == 'fresh' and pc['kind'] == 'fresh': first = f"Backups are fresh: the server {sv['age']}, your PC {pc['age']}."
    elif sv['kind'] == 'fresh' and pc['kind'] == 'stale':        # the PC is the problem: say so first, the card shows only the start
        first = f"Check your PC's backup: it last finished {pc['age']}; the server backed up {sv['age']}."
    else:
        head = {'running': 'Backing up the server now' + (f" (last one: {sv['age']})" if v['stale'] and sv['age'] else ''),
                'failed': "The server's last backup failed", 'none': 'The server has no backup yet',
                'stale': f"The server's backup is older than a week ({sv['age']})", 'fresh': f"The server backed up {sv['age']}"}[sv['kind']]
        first = head + '; ' + ({'fresh': f"your PC backed up {pc['age']}", 'stale': f"your PC's backup is older than a week ({pc['age']})",
                                'unread': "your PC's backup sent word this page cannot read", 'ahead': "your PC's clock looks wrong"}
                               .get(pc['kind'], "no word from your PC's backup yet")) + '.'
    second = {'running': "Copying the server's backups outside your home now.", 'failed': "The copy of the server's backups outside your home failed.",
              'done': f"The server's backups were copied outside your home {off['age']}." if off['age'] else "The server's backups were copied outside your home."
              }.get(off['kind'], "The server has no copy outside your home yet.")
    return f'{first} {second}'

def status(v):
    """Home's line (today()), and Needs you when the newest snapshot is older than STALE_DAYS or the last run failed."""
    j = v['job']
    failed = bool(j and j['state'] == 'failed')
    pc_old = any(x['key'] == 'pc' and x['kind'] == 'stale' for x in v['copies'])      # the PC's backup is older than a week
    no_snap = any(x['key'] == 'server' and x['kind'] == 'none' for x in v['copies'])  # nothing on the shelf: bigger than an old PC backup
    return {'line': today(v), 'needs': failed or v['stale'] or no_snap or pc_old,
            'action': 'Look at the failed backup' if failed else 'Check backups' if v['stale'] or no_snap else "Check the PC's backup" if pc_old else ''}

def get(path, query, ctx):
    if path == 'state': return 200, view(ctx)
    if path == 'status': return 200, status(view(ctx))
    return 404, {'ok': False, 'msg': 'not found'}

def run(argv):
    """Run one fixed command (an argument list, never a shell). Tests replace this."""
    try: p = subprocess.run(argv, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as e: return False, str(e)
    return p.returncode == 0, (p.stderr or p.stdout or '').strip()

def post(path, body, ctx):
    if path != 'backup': return 404, {'ok': False, 'msg': 'not found'}
    v = view(ctx)                             # nothing in the body is read: the unit is the brain job's, found here
    if not v['can_backup']: return 409, {'ok': False, 'msg': v['why_not']}
    unit = v['job']['unit']
    if not BRAIN.match(unit): return 409, {'ok': False, 'msg': 'not allowed'}
    ok, err = run([SYSTEMCTL, '--user', 'start', '--no-block', unit + '.service'])
    if not ok: return 500, {'ok': False, 'msg': f'Could not start the backup: {err[:160]}'}
    return 200, {'ok': True, 'msg': 'Backup started: a new snapshot appears on the shelf in a few minutes.'}
