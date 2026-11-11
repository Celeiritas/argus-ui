"""Does it WORK, not just run? (docs/checks.md)

A background loop reads ~/.config/argus-ui/checks.json (no file: no checks) and, for each check, proves that a program can do
its job: the unit is active, its drive is in the mount table and writable, the container holds no dead copy of the drive and can
read a named file, an http address answers. Each program gets works: true | false | None (unknown) and a plain reason.
One event is raised per CHANGE of state (never per failed attempt) through notify.py.

Safety rules the code keeps:
  * The mount table (/proc/self/mountinfo, readable without sudo) is read first. No file is read on a drive the table
    shows missing, dropped (shutdown) or read-only; a check that names a file without naming its drive is refused.
  * Every subprocess and http call has a timeout. The loop runs in its own thread; state() only reads the last results,
    so a hung check can never block the server, and results that stop updating turn into "unknown".
  * Self-repair ships OFF: only a check whose id is in ~/.config/argus-ui/auto-fix.json is restarted by the server
    (the same `systemctl --user restart` the bolt uses). Otherwise a `needs-yes` event asks."""
import json, os, re, subprocess, sys, threading, time, urllib.request, urllib.error
from datetime import datetime

import notify

CHECKS = os.path.expanduser(os.environ.get('ARGUS_CHECKS') or '~/.config/argus-ui/checks.json')
AUTOFIX = os.path.expanduser(os.environ.get('ARGUS_AUTOFIX') or '~/.config/argus-ui/auto-fix.json')
MOUNTINFO = os.environ.get('ARGUS_MOUNTINFO') or '/proc/self/mountinfo'
STATEFILE = os.path.expanduser(os.environ.get('ARGUS_WATCH_STATE') or '~/.local/state/argus-ui/watch.json')
CALL_TIMEOUT = 6            # seconds for any one subprocess or http call
ID = re.compile(r'^[a-z][a-z0-9-]{0,60}$')
UNIT = re.compile(r'^[A-Za-z0-9_.@-]{1,80}$')
DEAD = ('shutdown', 'emergency_ro')    # words the kernel puts on a mount line when the drive under it is gone

# ---------- the words (plain, for a non-programmer) ----------
PROGRAM = {   # code -> (what follows "<Title> runs, but ", longer explanation)
    'drive-missing': ('its drive is not connected', 'The drive it needs is not mounted, so there is nothing for it to read.'),
    'drive-dropped': ('its drive has dropped out', 'The drive it needs was disconnected and the system marked it as gone.'),
    'drive-readonly': ('its drive is read-only', 'The system stopped writing to the drive it needs, usually after errors.'),
    'dead-copy': ('cannot read its drive', 'The drive was unplugged and came back, but {t} still holds the old connection, so every file it opens fails. Starting {t} again makes it pick the drive up.'),
    'cannot-read': ('cannot read its drive', 'The drive looks connected, but a test file inside {t} would not open.'),
    'no-answer': ('does not answer at its web address', 'It is running, but nothing answers at its web address.'),
}
DRIVE = {     # code -> (whole sentence about the drive, explanation)
    'drive-missing': ('{t} is not connected', 'It is not in the system\'s list of mounted drives. Programs that need it cannot work.'),
    'drive-dropped': ('{t} has dropped out', 'It was disconnected and the system marked it as gone. Plug it in again; programs that held it need a restart afterwards.'),
    'drive-readonly': ('{t} is read-only', 'The system stopped writing to it, usually after errors. Programs cannot save anything there.'),
}
UNIT_DOWN = ('is not running', 'The service is not running.')


def log(msg): print(f'argus-ui: watch: {msg}', file=sys.stderr, flush=True)


# ---------- the mount table ----------
def unescape(s): return re.sub(r'\\([0-7]{3})', lambda m: chr(int(m.group(1), 8)), s)


def parse_mountinfo(text):
    """-> list of dicts (dev 'major:minor', mount, opts, fstype, source, sup). Lines that don't parse are skipped."""
    rows = []
    for line in (text or '').splitlines():
        f = line.split()
        if '-' not in f[6:]: continue
        i = f.index('-', 6)
        if len(f) < i + 4: continue
        rows.append(dict(dev=f[2], mount=unescape(f[4]), opts=set(f[5].split(',')), fstype=f[i + 1], source=unescape(f[i + 2]), sup=set(f[i + 3].split(','))))
    return rows


def mount_status(table, path):
    """'missing' | 'dropped' | 'readonly' | 'ok' for the mount point `path` (the last mount on it wins)."""
    path = path.rstrip('/') or '/'
    hit = [r for r in table if r['mount'] == path]
    if not hit: return 'missing'
    r = hit[-1]
    if r['opts'] & set(DEAD) or r['sup'] & set(DEAD): return 'dropped'
    if 'ro' in r['opts'] or 'ro' in r['sup']: return 'readonly'
    return 'ok'


def dead_copies(inside, host):
    """Lines of a container's mount table that hold a drive the host no longer has: the line carries `shutdown`, or it is a
    block device (/dev/...) whose major:minor is not in the host's table (the drive came back under a new device)."""
    here = {r['dev'] for r in host}
    out = []
    for r in inside:
        if not r['source'].startswith('/dev/'): continue
        if r['opts'] & set(DEAD) or r['sup'] & set(DEAD) or (not r['dev'].startswith('0:') and r['dev'] not in here): out.append(r)
    return out


# ---------- how the checks look at the world (tests replace this) ----------
class Env:
    def __init__(self, is_active=None, is_frozen=None, restart=None):
        self._active, self._frozen, self._restart = is_active, is_frozen, restart

    def now(self): return time.time()
    def sleep(self, s): time.sleep(s)

    def mountinfo(self):
        try:
            with open(MOUNTINFO, encoding='utf-8', errors='replace') as f: return f.read()
        except OSError: return None

    def is_active(self, unit): return self._active(unit) if self._active else None
    def is_frozen(self, unit): return bool(self._frozen and self._frozen(unit))
    def restart(self, unit): return self._restart(unit) if self._restart else (False, 'no restart available')

    def run(self, argv, timeout=CALL_TIMEOUT):
        """-> (returncode, stdout bytes); (None, b'') when it timed out or could not start."""
        try:
            r = subprocess.run(argv, capture_output=True, timeout=timeout, stdin=subprocess.DEVNULL)
            return r.returncode, r.stdout
        except (subprocess.TimeoutExpired, OSError): return None, b''

    def http(self, url, timeout=CALL_TIMEOUT):
        """-> the status code, or None when nothing answered."""
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'argus-ui-watch'}), timeout=timeout) as r: return r.status
        except urllib.error.HTTPError as e: return e.code
        except Exception: return None


# ---------- the config ----------
def load_checks():
    """-> (list of valid checks, list of (id, why) for refused ones). No file: nothing."""
    try:
        with open(CHECKS, encoding='utf-8') as f: raw = json.load(f)
    except OSError: return [], []
    except ValueError as e: return [], [('checks.json', f'not valid JSON: {e}')]
    items = raw.get('checks') if isinstance(raw, dict) else raw
    good, bad, seen = [], [], set()
    for c in items if isinstance(items, list) else []:
        why = refuse(c, seen)
        if why: bad.append((str(c.get('id') if isinstance(c, dict) else c)[:40], why))
        else: good.append(c); seen.add(c['id'])
    return good, bad


def refuse(c, seen):
    if not isinstance(c, dict): return 'not an object'
    if not isinstance(c.get('id'), str) or not ID.match(c['id']): return 'id must be lowercase letters, digits and dashes'
    if c['id'] in seen: return 'duplicate id'
    if not isinstance(c.get('title'), str) or not c['title'].strip(): return 'needs a title'
    if c.get('unit') is not None and not (isinstance(c['unit'], str) and UNIT.match(c['unit'])): return 'bad unit name'
    if c.get('mount') is not None and not (isinstance(c['mount'], str) and c['mount'].startswith('/')): return 'mount must be an absolute path'
    ct = c.get('container')
    if ct is not None:
        if not isinstance(ct, dict) or not isinstance(ct.get('name'), str) or not UNIT.match(ct['name']): return 'container needs a name'
        rt = ct.get('runtime')
        if rt is not None and not (isinstance(rt, str) or (isinstance(rt, list) and rt and all(isinstance(x, str) for x in rt))): return 'container runtime must be a program name or a list'
        if (ct.get('file') or ct.get('dir')) and not c.get('mount'): return 'reading a file needs the drive named in "mount" (the mount table is checked first)'
        for k in ('file', 'dir'):
            if ct.get(k) is not None and not (isinstance(ct[k], str) and ct[k].startswith('/')): return f'container {k} must be an absolute path'
    h = c.get('http')
    for u in ([h] if isinstance(h, (str, dict)) else h or []):
        url = u if isinstance(u, str) else (u or {}).get('url')
        if not (isinstance(url, str) and re.match(r'^https?://', url)): return 'http needs an http:// or https:// address'
    if not (c.get('unit') or c.get('mount') or ct or h): return 'checks nothing'
    fx = c.get('fix')
    if fx is not None and not (isinstance(fx, dict) and isinstance(fx.get('restart'), list) and fx['restart'] and all(isinstance(u, str) and UNIT.match(u) for u in fx['restart'])): return 'fix needs {"restart": [unit, ...]}'
    return ''


def auto_fix_ids():
    """The ids the owner approved for self-repair. A missing, empty or broken file means none."""
    try:
        with open(AUTOFIX, encoding='utf-8') as f: raw = json.load(f)
    except (OSError, ValueError): return set()
    ids = raw.get('ids') if isinstance(raw, dict) else raw
    return {i for i in ids if isinstance(i, str)} if isinstance(ids, list) else set()


# ---------- one check ----------
def result(c, works, code, why='', **kw):
    return dict(id=c['id'], works=works, code=code, why=why, **kw)


def evaluate(c, env):
    """Prove that check c works. Order: frozen? -> unit -> mount table -> container (dead copy, then one file) -> http.
    Returns dict(id, works True|False|None, code, why). Never raises."""
    try: return _evaluate(c, env)
    except Exception as e:
        log(f'check {c.get("id")} failed to run: {e}')
        return result(c, None, 'error', 'The check itself could not run.')


def _evaluate(c, env):
    unit = c.get('unit')
    if unit and env.is_frozen(unit): return result(c, None, 'paused', 'Paused on purpose (frozen).')
    if unit:
        a = env.is_active(unit)
        if a is None: return result(c, None, 'unit-unknown', 'Could not ask the system whether it runs.')
        if not a: return result(c, False, 'unit-down')
    host = None
    if c.get('mount'):
        txt = env.mountinfo()
        if txt is None: return result(c, None, 'mounts-unreadable', 'Could not read the list of mounted drives.')
        host = parse_mountinfo(txt)
        st = mount_status(host, c['mount'])
        if st != 'ok': return result(c, False, 'drive-' + st)
    ct = c.get('container')
    if ct:
        rt = ct.get('runtime') or 'podman'
        rt = list(rt) if isinstance(rt, list) else [rt]      # a list lets a test use ["python", "fake_podman.py"]
        rc, out = env.run(rt + ['exec', ct['name'], 'cat', '/proc/self/mountinfo'])
        if rc != 0 or not out.strip(): return result(c, None, 'cannot-look', 'Could not look inside the container.')
        if host is None:
            txt = env.mountinfo()
            if txt is None: return result(c, None, 'mounts-unreadable', 'Could not read the list of mounted drives.')
            host = parse_mountinfo(txt)
        if dead_copies(parse_mountinfo(out.decode('utf-8', 'replace')), host): return result(c, False, 'dead-copy')
        # only now, with the drive present, writable and no dead copy, is a file read
        for k, argv in (('file', ['head', '-c', '4096', '--']), ('dir', ['ls', '-A', '--'])):
            if ct.get(k):
                rc, out = env.run(rt + ['exec', ct['name']] + argv + [ct[k]])
                if rc is None: return result(c, None, 'cannot-look', 'The test read took too long.')
                if rc != 0 or not out: return result(c, False, 'cannot-read')
    h = c.get('http')
    for u in [h] if isinstance(h, (str, dict)) else h or []:
        url, want = (u, None) if isinstance(u, str) else (u['url'], u.get('status'))
        s = env.http(url)
        ok = s is not None and ((s in want) if isinstance(want, list) else (s == want) if isinstance(want, int) else s < 500 if want == 'any' else 200 <= s < 300)
        if not ok: return result(c, False, 'no-answer')
    return result(c, True, 'ok')


def is_drive(c): return not (c.get('unit') or c.get('container') or c.get('http'))     # a check of the drive itself


def words(c, code, why=''):
    """(reason for the card, title of the event, explanation) for a failed check, in plain words."""
    t = c['title']
    if code == 'unit-down': return UNIT_DOWN[0].capitalize(), f'{t} {UNIT_DOWN[0]}', UNIT_DOWN[1]
    if is_drive(c) and code in DRIVE:
        s, e = DRIVE[code]; return s.format(t=t), s.format(t=t), e
    p, e = PROGRAM.get(code, (why or 'cannot do its job', why))
    return p, f'{t} runs, but {p}', e.format(t=t)


# ---------- the loop ----------
_lock = threading.Lock()
RESULTS = {}        # id -> public result (what state() shows)
PREV = {}           # id -> {works, code, since, tried}  what the last events were about
LAST_STEP = [0.0]
BAD = {}            # refused check -> why, logged once
STOP = threading.Event()


def load_prev():
    try:
        with open(STATEFILE, encoding='utf-8') as f: d = json.load(f)
        if isinstance(d, dict): PREV.update({k: v for k, v in d.items() if isinstance(v, dict)})
    except (OSError, ValueError): pass


def save_prev():
    try:
        os.makedirs(os.path.dirname(STATEFILE), exist_ok=True)
        tmp = STATEFILE + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f: json.dump(PREV, f)
        os.replace(tmp, STATEFILE)
    except OSError as e: log(f'could not save {STATEFILE}: {e}')


def iso(ts): return datetime.fromtimestamp(ts).astimezone().isoformat(timespec='seconds')


def step(env, settle=20):
    """One round over every check. Raises events on changes. Safe to call from a test with a fake Env."""
    checks, bad = load_checks()
    for name, why in bad:
        if BAD.get(name) != why: BAD[name] = why; log(f'ignored check {name}: {why}')
    auto = auto_fix_ids()
    now = env.now()
    drive_down = {}       # mount -> True while a drive check of its own is failing (its dependents stay quiet)
    results = [evaluate(c, env) for c in checks]
    for c, r in zip(checks, results):
        if not c.get('unit') and c.get('mount') and r['works'] is False: drive_down[c['mount']] = True
    for c, r in zip(checks, results):
        r = handle(c, r, env, auto, now, drive_down, settle)
        pub = dict(id=c['id'], title=c['title'], job=c.get('job') or '', unit=c.get('unit') or '', works=r['works'], code=r['code'], at=now,
                   since=iso(PREV.get(c['id'], {}).get('since', now)), fix=bool(c.get('fix')), autofix=c['id'] in auto, drive=is_drive(c))
        pub['reason'], pub['title_line'], pub['detail'] = words(c, r['code'], r.get('why', '')) if r['works'] is False else (r.get('why', ''), '', '')
        with _lock: RESULTS[c['id']] = pub
    with _lock:
        for k in list(RESULTS):
            if k not in {c['id'] for c in checks}: del RESULTS[k]
    LAST_STEP[0] = now
    save_prev()


def handle(c, r, env, auto, now, drive_down, settle):
    """Compare with the last known state; raise at most one event for a change. Returns the (maybe re-checked) result."""
    id_, p = c['id'], PREV.get(c['id'])
    if r['works'] is None: return r              # unknown never counts as a change
    if p and p.get('works') == r['works'] and p.get('code') == r['code']: return r
    # a change of state
    if r['works'] is True:
        PREV[id_] = dict(works=True, code='ok', since=now, tried=False)
        if p and p.get('works') is False:
            t = c['title']
            notify.notify(notify.make('recovered', id_, f'{t} works again', f'{t} can do its job again.', c.get('url', '')))
        return r
    reason, title, detail = words(c, r['code'], r.get('why', ''))
    quiet = bool(c.get('mount')) and c.get('unit') and r['code'].startswith('drive-') and drive_down.get(c['mount'])
    tried = bool(p and p.get('tried')) and p.get('works') is False
    PREV[id_] = dict(works=False, code=r['code'], since=now, tried=tried)
    if quiet: return r                           # the drive's own event already says it; this card still shows the reason
    fx = c.get('fix')
    say = (fx or {}).get('say') or ' and '.join((fx or {}).get('restart', []))
    url = c.get('url', '')
    if fx and id_ in auto and not tried and r['code'] in ('dead-copy', 'cannot-read', 'no-answer', 'unit-down'):
        PREV[id_]['tried'] = True
        for u in fx['restart']:
            if env.is_frozen(u): continue
            ok, msg = env.restart(u)
            if not ok: log(f'restart of {u} failed: {msg}')
        end = env.now() + settle
        r2 = evaluate(c, env)
        while r2['works'] is not True and env.now() < end:
            env.sleep(min(3, max(0.0, end - env.now()))); r2 = evaluate(c, env)
        if r2['works'] is True:
            PREV[id_] = dict(works=True, code='ok', since=env.now(), tried=True, tried_ok=True)
            notify.notify(notify.make('fixed', id_, f'{c["title"]} was restarted and works again', f'It could not do its job ({reason}). Argus restarted {say} as you allowed, and it works now.', url))
            return r2
        if r2['works'] is False:
            PREV[id_]['code'] = r2['code']
            reason, title, detail = words(c, r2['code'], r2.get('why', ''))
            r = r2
        notify.notify(notify.make('broke', id_, title, f'{detail} Argus restarted {say} once, and it did not help. It will not try again by itself.'.strip(), url))
        return r
    if fx:
        notify.notify(notify.make('needs-yes', id_, title, f'{detail} Restarting {say} should fix it. Waiting for your yes.'.strip(), url))
    else:
        notify.notify(notify.make('broke', id_, title, f'{detail} This one has no automatic fix.'.strip(), url))
    return r


def snapshot(interval=60):
    """The results for state(): a list. A result that has not been refreshed for a while is shown as unknown."""
    now = time.time()
    with _lock: rows = [dict(v) for v in RESULTS.values()]
    for v in rows:
        if now - v['at'] > 3 * interval + 30:
            v.update(works=None, code='stale', reason='Not checked for a while.', title_line='', detail='')
        v.pop('at', None)
    return sorted(rows, key=lambda v: v['id'])


def attach(jobs, rows):
    """Put works / works_reason on the task cards the checks name."""
    by = {}
    for r in rows:
        if r['job']: by.setdefault(r['job'], []).append(r)
    for j in jobs:
        rs = by.get(j['job']) or []
        bad = [r for r in rs if r['works'] is False]
        j['works'] = False if bad else None if not rs or any(r['works'] is None for r in rs) else True
        j['works_reason'] = bad[0]['reason'] if bad else ''
    return jobs


def alert_list(rows, allowed):
    """Failed checks as alert-file style entries (docs/alerts.md), so the existing card note, Argus's glare and the badge show them.
    `allowed(job)` says whether the job name belongs to an agent."""
    out = []
    for r in rows:
        if r['works'] is not False or not r['job'] or not allowed(r['job']): continue
        if r['code'] == 'unit-down': msg = 'Not running.'
        elif r['drive']: msg = r['reason'] + '.'
        else: msg = f"Running, but not working: {r['reason']}"
        out.append(dict(file='watch-' + r['id'], job=r['job'], level='alert', message=msg[:300], since=r['since'], link=''))
    return out


def start(env, interval=60, settle=20):
    """Run the loop in its own daemon thread. A round that fails is logged and the loop carries on."""
    load_prev()
    def loop():
        while not STOP.is_set():
            try: step(env, settle)
            except Exception as e: log(f'round failed: {e}')
            STOP.wait(interval)
    t = threading.Thread(target=loop, name='argus-watch', daemon=True); t.start()
    return t
