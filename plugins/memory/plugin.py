# Memory: are Mnemosyne's backups fresh, and how many copies exist? A bundled server plugin (docs/ui-plan.md §10,
# docs/memory.md). It only reads: the names and sizes of the snapshot files directly inside one folder, Elaia's task
# info (ctx.jobs), the PC's marker file and Medusa's game-guard state. Its one action starts the brain job's own unit,
# with fixed arguments that never come from the request. It never deletes, restores, or opens a snapshot (they hold
# keys and passwords).
import json, os, re, subprocess
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
    s = (now - at).total_seconds()
    if s < 0: return 'just now'
    if s < 3600: return f'{max(1, int(s // 60))} min ago'
    if s < 86400: h = int(s // 3600); return f"{h} hour{'s' if h != 1 else ''} ago"
    d = int(s // 86400)
    return 'yesterday' if d == 1 else f'{d} days ago'

def when(at):
    return at.strftime('%b %d, %I:%M %p').replace(' 0', ' ')

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
    try: t = datetime.fromisoformat(str(v).replace('Z', '+00:00'))
    except ValueError: return None
    return t.astimezone().replace(tzinfo=None) if t.tzinfo else t

def pc_copy(c, now):
    """Copy 2, on the PC: the PC's backup writes last-backup.json ({"at": ISO time}) and a pull job brings it here.
    The PC's folder can't be seen from the server, so without that file the answer is 'unknown', never a guess."""
    p = os.path.expanduser(c['pc_marker']) if isinstance(c.get('pc_marker'), str) else os.path.join(MNEMOSYNE, 'last-backup.json')
    try:
        with open(p, encoding='utf-8') as f: m = json.load(f)
        at = parse_time(m.get('at')) if isinstance(m, dict) else None
    except (OSError, ValueError): at = None
    if not at: return dict(key='pc', label='On the PC', state='unknown', word='Unknown', detail='No word from the PC yet: its backup writes last-backup.json')
    if (now - at).days > STALE_DAYS: return dict(key='pc', label='On the PC', state='stale', word='Old', detail=f'Last copy {age(at, now)}')
    return dict(key='pc', label='On the PC', state='yes', word='Done', detail=f'Last copy {age(at, now)}')

def offsite_copy(js):
    j = next((j for j in js if OFFSITE.match(j.get('job', ''))), None)
    if not j: return dict(key='offsite', label='Off-site', state='no', word='Not yet', detail='Not built yet: the off-site job is planned')
    if j.get('state') == 'failed': return dict(key='offsite', label='Off-site', state='no', word='Failed', detail=f"Last run failed ({j.get('last', '')})")
    if j.get('state') == 'never': return dict(key='offsite', label='Off-site', state='unknown', word='Not run', detail='The off-site job has not run yet')
    return dict(key='offsite', label='Off-site', state='yes', word='Done', detail=f"Last run {j.get('last', '')}")

def view(ctx, now=None):
    """Everything the page and Home's line show. Reads only."""
    now = now or datetime.now(); c = config(); js = jobs(ctx)
    pre = brain_job(c, js)                                   # the unit's server name picks the folder when there are several
    path = folder(c, pre['job'][len('mnemosyne-'):-len('-brain')] if pre else '')
    snaps = snapshots(path)
    job = brain_job(c, js, snaps[0]['host'] if snaps else '')
    s = snaps or []
    last = s[0] if s else None
    stale = bool(last) and (now - last['at']).days > STALE_DAYS
    server = dict(key='server', label='On the server', state='yes' if s else 'no', word='Done' if s else 'None',
                  detail=f"{len(s)} snapshot{'s' if len(s) != 1 else ''}, newest {age(last['at'], now)}" if s else 'No snapshot yet')
    if s and stale: server.update(state='stale', word='Old')
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
        shelf=min(len(s), SHELF), count=len(s), total=sum(x['size'] for x in s), total_h=size_h(sum(x['size'] for x in s)),
        last=dict(age=age(last['at'], now), when=when(last['at']), size_h=size_h(last['size']), size=last['size']) if last else None,
        stale=stale, stale_days=STALE_DAYS,
        job=dict(unit=job['job'], state=job.get('state', ''), last=job.get('last', ''), next=job.get('next', '')) if job else None,
        running=running, copies=[server, pc_copy(c, now), offsite_copy(js)],
        can_backup=not why, why_not=why, note=str(c.get('note') or NOTE)[:200])

def status(v):
    """Home's line: the newest snapshot's age, the count and size, and what isn't done. Needs you when it is old or failed."""
    j = v['job']
    if not v['count']:
        return {'line': 'No snapshots yet' if j else 'No snapshots found', 'needs': bool(j and j['state'] == 'failed'),
                'action': 'Look at the failed backup' if j and j['state'] == 'failed' else ''}
    off = next(x for x in v['copies'] if x['key'] == 'offsite')
    line = f"Last snapshot {v['last']['age']} · {v['count']} on the server, {v['total_h']}" + (' · off-site not yet' if off['state'] != 'yes' else '')
    if j and j['state'] == 'running': line = 'Backing up now · ' + line
    failed = bool(j and j['state'] == 'failed')
    return {'line': line, 'needs': failed or v['stale'],
            'action': 'Look at the failed backup' if failed else 'Check backups' if v['stale'] else ''}

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
