"""Does it WORK, not just run? (docs/checks.md)

A background loop reads ~/.config/argus-ui/checks.json (no file: no checks) and, for each check, proves that a program can do
its job: the unit is active, its drive is in the mount table and writable, the container holds no dead copy of the drive and can
read a named file, an http address answers. Each program gets works: true | false | None (unknown) and a plain reason.
One event is raised per CHANGE of state (never per failed attempt) through notify.py.

Safety rules the code keeps:
  * The mount table (/proc/self/mountinfo, readable without sudo) is read first. No file is read on a drive the table
    shows missing, dropped (shutdown) or read-only; a check that names a file without naming its drive is refused.
  * Every call has a time limit (6 s for a read or an http call here; systemctl goes through the server's 20 s limit). The
    loop runs in its own thread; state() only reads the last results, so a hung check can never block the server, and
    results that stop updating turn into "unknown". A test read that hangs is not repeated for 15 minutes.
  * A failure counts only once it is seen in 2 rounds in a row; a unit that is starting or stopping is not "down".
  * Self-repair ships OFF, and when it is on it is narrow: only a check whose id is in ~/.config/argus-ui/auto-fix.json,
    only for the codes in REPAIRABLE (the program runs but cannot read its drive), at most once per check in 24 hours
    (the time is saved to disk before the restart), and in trial mode (the default) it only notes what it would have
    done and asks. Everything else raises `needs-yes` and waits for the owner."""
import json, os, re, subprocess, sys, threading, time, urllib.request, urllib.error
from datetime import datetime

import notify

CHECKS = os.path.expanduser(os.environ.get('ARGUS_CHECKS') or '~/.config/argus-ui/checks.json')
AUTOFIX = os.path.expanduser(os.environ.get('ARGUS_AUTOFIX') or '~/.config/argus-ui/auto-fix.json')
MOUNTINFO = os.environ.get('ARGUS_MOUNTINFO') or '/proc/self/mountinfo'
STATEFILE = os.path.expanduser(os.environ.get('ARGUS_WATCH_STATE') or '~/.local/state/argus-ui/watch.json')
CALL_TIMEOUT = 6            # seconds for one read inside a container or one http call
ID = re.compile(r'^[a-z][a-z0-9-]{0,60}$')
UNIT = re.compile(r'^[A-Za-z0-9_.@][A-Za-z0-9_.@-]{0,79}$')    # never starts with '-', so a name can't be read as an option
DEAD = ('shutdown', 'emergency_ro')    # words the kernel puts on a mount line when the drive under it is gone
REPAIRABLE = ('dead-copy', 'cannot-read')   # the ONLY codes self-repair acts on: the program runs but cannot read its drive
RETRY_AFTER = 24 * 3600     # one automatic try per check in this many seconds, across recovery and server restarts
CONFIRM = 2                 # rounds in a row a failure must be seen before it counts (one slow answer is not a breakage)
BETWEEN_ROUNDS = 3          # a unit starting or stopping for more rounds in a row than this counts as not running
HOLD = 15 * 60              # after a test read timed out: no read for this long, or until the drive's mount line changes
READ_FAILED = (1, 2)        # exit codes of `head` and `ls` (GNU and busybox) when the read itself failed; podman's own
                            # errors (125, 126, 127), a signal (137 ...) or anything else is "could not look", never cannot-read
NOT_ON_DRIVE = 'not-on-drive'   # dead-copy found through container.mount: its own explanation
SETTLE = 90                 # seconds a restarted program gets before "the restart did not help"
BETWEEN = 'between'         # is_active(): starting, reloading or stopping, cannot tell yet

# ---------- the words (plain, for a non-programmer) ----------
PROGRAM = {   # code -> (what follows "<Title> runs, but ", longer explanation)
    'drive-missing': ('its drive is not connected', 'The drive it needs is not mounted, so there is nothing for it to read.'),
    'drive-dropped': ('its drive has dropped out', 'The drive it needs was disconnected and the system marked it as gone.'),
    'drive-readonly': ('its drive is read-only', 'The system stopped writing to the drive it needs, usually after errors.'),
    'dead-copy': ('cannot read its drive', 'The drive was unplugged and came back, but {t} still holds the old connection, so every file it opens fails. Starting {t} again makes it pick the drive up.'),
    NOT_ON_DRIVE: ('cannot read its drive', 'Inside {t}, the folder for the drive is not on the drive. Most likely {t} was started before the drive was there and holds the empty folder underneath. Starting {t} again makes it pick the drive up.'),
    'cannot-read': ('cannot read its drive', 'The drive looks connected, but a test file inside {t} would not open.'),
    'no-answer': ('does not answer at its web address', 'It is running, but nothing answers at its web address.'),
    'read-hung': ('does not answer when it reads its drive', 'A test read inside {t} did not finish in time. Argus waits 15 minutes, or until the drive changes, before it reads again, so the reads do not pile up.'),
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
        rows.append(dict(mid=f[0], dev=f[2], mount=unescape(f[4]), opts=set(f[5].split(',')), fstype=f[i + 1], source=unescape(f[i + 2]), sup=set(f[i + 3].split(','))))
    return rows


def mount_line(table, path):
    """The last mount on `path` (the one that is seen), or None."""
    path = path.rstrip('/') or '/'
    hit = [r for r in table if r['mount'] == path]
    return hit[-1] if hit else None


def line_sig(table, path):
    """A short text that changes whenever the host's line for `path` changes (a re-mount gets a new mount id)."""
    r = mount_line(table, path)
    if not r: return ''
    return ' '.join((r['mid'], r['dev'], r['source'], r['fstype'], ','.join(sorted(r['opts'])), ','.join(sorted(r['sup']))))


def mount_status(table, path):
    """'missing' | 'dropped' | 'readonly' | 'ok' for the mount point `path` (the last mount on it wins)."""
    r = mount_line(table, path)
    if not r: return 'missing'
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


def wrong_drive(inside, host, inner, outer):
    """container.mount: the container's line for `inner` must exist and sit on the same device as the host's line for `outer`.
    False when it does; True when it is missing or on another device (the container was started before the drive was there,
    or it holds a drive that went away while its number was given to something else). Only mount tables, nothing is read."""
    i, o = mount_line(inside, inner), mount_line(host, outer)
    return not (i and o and i['dev'] == o['dev'])


def unit_state(word):
    """`systemctl is-active` words -> True (running) | False (not running) | BETWEEN (starting, reloading, stopping) | None."""
    w = (word or '').strip()
    if w == 'active': return True
    if w in ('inactive', 'failed'): return False
    if w in ('activating', 'reloading', 'deactivating'): return BETWEEN
    return None


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
        if ct.get('mount') is not None and not c.get('mount'): return 'container mount needs the drive named in "mount"'
        for k in ('file', 'dir', 'mount'):
            if ct.get(k) is not None and not (isinstance(ct[k], str) and ct[k].startswith('/')): return f'container {k} must be an absolute path'
    h = c.get('http')
    for u in ([h] if isinstance(h, (str, dict)) else h or []):
        url = u if isinstance(u, str) else (u or {}).get('url')
        if not (isinstance(url, str) and re.match(r'^https?://', url)): return 'http needs an http:// or https:// address'
    if not (c.get('unit') or c.get('mount') or ct or h): return 'checks nothing'
    fx = c.get('fix')
    if fx is not None and not (isinstance(fx, dict) and isinstance(fx.get('restart'), list) and fx['restart'] and all(isinstance(u, str) and UNIT.match(u) for u in fx['restart'])): return 'fix needs {"restart": [unit, ...]}'
    return ''


_AUTOFIX_SAID = [None]      # the last problem logged about auto-fix.json, so it is logged once, not every round


def auto_fix():
    """-> (ids the owner approved for self-repair, trial). The file is {"ids": [...], "trial": true|false}.
    No file: none. A file that is not JSON or has another shape: none, and one log line. trial (note only, restart nothing)
    is the default: only "trial": false, in so many words, lets the server restart for real."""
    try:
        with open(AUTOFIX, encoding='utf-8') as f: raw = json.load(f)
    except FileNotFoundError: _AUTOFIX_SAID[0] = None; return set(), True
    except (OSError, ValueError) as e: return _autofix_off(f'cannot be read as JSON ({e})')
    if not (isinstance(raw, dict) and isinstance(raw.get('ids'), list) and all(isinstance(i, str) for i in raw['ids'])
            and set(raw) <= {'ids', 'trial'} and isinstance(raw.get('trial', True), bool)):
        return _autofix_off('has another shape than {"ids": ["<check id>", ...], "trial": true|false}')
    _AUTOFIX_SAID[0] = None
    return set(raw['ids']), raw.get('trial', True) is not False


def _autofix_off(why):
    if _AUTOFIX_SAID[0] != why: _AUTOFIX_SAID[0] = why; log(f'self-repair is off: {AUTOFIX} {why}')
    return set(), True


def auto_fix_ids(): return auto_fix()[0]


# ---------- one check ----------
def result(c, works, code, why='', **kw):
    return dict(id=c['id'], works=works, code=code, why=why, **kw)


def evaluate(c, env, hold=None):
    """Prove that check c works. Order: frozen? -> unit -> mount table -> container (dead copy, its mount, then one file) -> http.
    `hold` = [mount line, until]: a test read timed out before; no read while the line is the same and the time not up.
    Returns dict(id, works True|False|None, code, why). Never raises."""
    try: return _evaluate(c, env, hold)
    except Exception as e:
        log(f'check {c.get("id")} failed to run: {e}')
        return result(c, None, 'error', 'The check itself could not run.')


def _evaluate(c, env, hold=None):
    unit = c.get('unit')
    if unit and env.is_frozen(unit): return result(c, None, 'paused', 'Paused on purpose (frozen).')
    if unit:
        a = env.is_active(unit)
        if a == BETWEEN: return result(c, None, 'unit-between', 'Starting or stopping; looking again next round.')
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
        inside = parse_mountinfo(out.decode('utf-8', 'replace'))
        if dead_copies(inside, host): return result(c, False, 'dead-copy')
        if ct.get('mount') and wrong_drive(inside, host, ct['mount'], c['mount']): return result(c, False, 'dead-copy', NOT_ON_DRIVE)
        # only now, with the drive present, writable and no dead copy, is a file read
        for k, argv in (('file', ['head', '-c', '4096', '--']), ('dir', ['ls', '-A', '--'])):
            if ct.get(k):
                sig = line_sig(host, c['mount'])
                if hold and hold[0] == sig and env.now() < hold[1]:
                    return result(c, False, 'read-hung', 'The last test read did not finish; no new read until the drive changes or 15 minutes pass.', held=True)
                rc, out = env.run(rt + ['exec', ct['name']] + argv + [ct[k]])
                if rc is None: return result(c, False, 'read-hung', 'The test read took too long.', line=sig)
                if rc in READ_FAILED or (rc == 0 and not out): return result(c, False, 'cannot-read')   # an empty folder too: what a container sees when it missed its drive
                if rc != 0: return result(c, None, 'cannot-look', f'The test read could not run (exit code {rc}).')   # podman's own trouble, not the drive's
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
    if code == 'read-hung': p, e = PROGRAM[code]; return p, f'{t} {p}', e.format(t=t)
    if code == 'dead-copy' and why == NOT_ON_DRIVE: code = NOT_ON_DRIVE
    if is_drive(c) and code in DRIVE:
        s, e = DRIVE[code]; return s.format(t=t), s.format(t=t), e
    p, e = PROGRAM.get(code, (why or 'cannot do its job', why))
    return p, f'{t} runs, but {p}', e.format(t=t)


# ---------- the loop ----------
_lock = threading.Lock()
RESULTS = {}        # id -> public result (what state() shows)
PREV = {}           # id -> {works, code, since, told, pending, streak, decided, outcome, last_try, last_try_trial, between, hold}: saved
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


def step(env, settle=SETTLE):
    """One round over every check. Raises events on changes. Safe to call from a test with a fake Env."""
    checks, bad = load_checks()
    for name, why in bad:
        if BAD.get(name) != why: BAD[name] = why; log(f'ignored check {name}: {why}')
    auto, trial = auto_fix()
    now = env.now()
    drive_down = {}       # mount -> True while a drive check of its own is failing (its dependents stay quiet)
    results = [track(c, evaluate(c, env, hold_of(c['id'])), now) for c in checks]
    for c, r in zip(checks, results):
        if not c.get('unit') and c.get('mount') and r['works'] is False: drive_down[c['mount']] = True
    restarted = set()     # units restarted this round: each at most once, also when two checks name it
    for c, r in zip(checks, results):
        try: r = handle(c, r, env, auto, trial, now, drive_down, settle, restarted)
        except Exception as e: log(f'check {c["id"]}: handling the result failed: {e}')
        pub = dict(id=c['id'], title=c['title'], job=c.get('job') or '', unit=c.get('unit') or '', works=r['works'], code=r['code'], at=now,
                   since=iso(PREV.get(c['id'], {}).get('since', now)), fix=bool(c.get('fix')), autofix=c['id'] in auto, drive=is_drive(c))
        pub['reason'], pub['title_line'], pub['detail'] = words(c, r['code'], r.get('why', '')) if r['works'] is False else (r.get('why', ''), '', '')
        pub['note'] = card_note(c, r, PREV.get(c['id']) or {}, auto)
        with _lock: RESULTS[c['id']] = pub
    with _lock:
        for k in list(RESULTS):
            if k not in {c['id'] for c in checks}: del RESULTS[k]
    LAST_STEP[0] = now
    save_prev()


def hold_of(id_):
    h = (PREV.get(id_) or {}).get('hold')
    return h if isinstance(h, list) and len(h) == 2 and isinstance(h[0], str) and isinstance(h[1], (int, float)) else None


def track(c, r, now):
    """What has to be remembered across rounds before a result is judged: a unit that stays between states, a read that hung."""
    p = PREV.setdefault(c['id'], {})
    if r['code'] == 'unit-between':
        p['between'] = p.get('between', 0) + 1
        if p['between'] > BETWEEN_ROUNDS: r = result(c, False, 'unit-down')     # starting and crashing in a loop looks like this
    else: p.pop('between', None)
    if r['code'] == 'read-hung' and 'line' in r: p['hold'] = [r['line'], now + HOLD]   # a fresh timeout, not a held round
    if r['works'] is True: p.pop('hold', None)
    return r


def handle(c, r, env, auto, trial, now, drive_down, settle, restarted):
    """Compare with the last known state; raise at most one event for a change. Returns the (maybe re-checked) result.
    "In a row" means in a row: an unknown round breaks the count, for a new failure and for self-repair alike."""
    id_ = c['id']
    p = PREV.setdefault(id_, {})
    if r['works'] is None:                       # unknown never counts as a change, and it breaks "in a row"
        p.pop('pending', None); p.pop('streak', None)
        return r
    if r['works'] is True:                       # recovery is immediate
        for k in ('pending', 'streak', 'decided', 'outcome'): p.pop(k, None)
        if p.get('works') is True: return r
        was_bad, told = p.get('works') is False, p.get('told', True)
        p.update(works=True, code='ok', since=now, told=False)
        if was_bad and told:                     # only when he was told it broke (a quiet dependent says nothing either way)
            t = c['title']
            notify.notify(notify.make('recovered', id_, f'{t} works again', f'{t} can do its job again.', c.get('url', '')))
        return r
    s = p.get('streak')                          # [code, rounds in a row with exactly this code]
    p['streak'] = [r['code'], s[1] + 1] if isinstance(s, list) and len(s) == 2 and s[0] == r['code'] and isinstance(s[1], int) else [r['code'], 1]
    changed = True
    if p.get('works') is not False:              # a new failure counts only once it is seen in CONFIRM rounds in a row
        p['pending'] = p.get('pending', 0) + 1
        if p['pending'] < CONFIRM: return result(c, None, 'pending', 'Saw a problem once; looking again next round.')
        p.update(works=False, code=r['code'], since=now, told=False)
        p.pop('decided', None); p.pop('outcome', None)
    elif p.get('code') != r['code']:
        p.update(code=r['code'], since=now); p.pop('outcome', None); p.pop('decided', None)
    else: changed = False
    p.pop('pending', None)
    reason, title, detail = words(c, r['code'], r.get('why', ''))
    if changed and bool(c.get('mount')) and c.get('unit') and r['code'].startswith('drive-') and drive_down.get(c['mount']):
        return r                                 # quiet: the drive's own event already says it; this card still shows the reason
    fx = c.get('fix')
    say = (fx or {}).get('say') or ' and '.join((fx or {}).get('restart', []))
    url = c.get('url', '')
    if fx and id_ in auto and r['code'] in REPAIRABLE and r['code'] != 'read-hung':
        # Self-repair decides once per code of a failure, and only after that code was seen CONFIRM rounds in a row, also when
        # the check was already failing for another reason (a single odd round never restarts anything). Its event waits with it.
        if p.get('decided') == r['code'] or p['streak'][1] < CONFIRM: return r
        p['decided'] = r['code']; p['told'] = True
        last = p.get('last_try')
        if isinstance(last, (int, float)) and now - last < RETRY_AFTER:
            p['outcome'] = 'held'
            done = 'would have restarted' if p.get('last_try_trial') else 'already restarted'
            notify.notify(notify.make('needs-yes', id_, title, f'{detail} Argus {done} {say} by itself at {iso(last)[11:16]}, and it does that only once a day. Restarting {say} should fix it. Waiting for your yes.', url))
            return r
        p.update(last_try=now, last_try_trial=trial, outcome='trial' if trial else 'tried')
        save_prev()                              # the "already tried" mark and its time are on disk BEFORE anything is restarted
        if trial:
            notify.notify(notify.make('needs-yes', id_, title, f'{detail} Argus would have restarted {say} by itself, but it did not: for now it only notes what it would do. Waiting for your yes.', url))
            return r
        return repair(c, r, env, settle, restarted, say, reason, url)
    if not changed: return r
    p['told'] = True
    if r['code'] == 'read-hung':                 # its own code: never a restart, a warning
        notify.notify(notify.make('broke', id_, title, f'{detail} It may come back by itself; if it does not, look at the drive.', url, level='warn'))
    elif fx:
        notify.notify(notify.make('needs-yes', id_, title, f'{detail} Restarting {say} should fix it. Waiting for your yes.'.strip(), url))
    else:
        notify.notify(notify.make('broke', id_, title, f'{detail} This one has no automatic fix.'.strip(), url))
    return r


def repair(c, r, env, settle, restarted, say, reason, url):
    """The approved restart, once: each unit at most once per round, never a frozen one. A restart call that hangs or raises
    counts as a restart that did not work. Then up to `settle` seconds for the program to work again (stops early)."""
    id_, p = c['id'], PREV[c['id']]
    went = []
    for u in c['fix']['restart']:
        if u in restarted: went.append(u); continue          # another check restarted it this round
        if env.is_frozen(u): continue
        restarted.add(u)
        try: ok, msg = env.restart(u)
        except Exception as e: ok, msg = False, f'{type(e).__name__}: {e}'
        if ok: went.append(u)
        else: log(f'restart of {u} failed: {msg}')
    if not went:
        p['outcome'] = 'cmdfail'
        notify.notify(notify.make('broke', id_, words(c, r['code'], r.get('why', ''))[1], f'It could not do its job ({reason}). Argus tried to restart {say} by itself, but the restart did not work. It will not try again by itself for a day.', url))
        return r
    end = env.now() + settle
    r2 = evaluate(c, env)
    while r2['works'] is not True and env.now() < end:
        env.sleep(min(3, max(0.0, end - env.now()))); r2 = evaluate(c, env)
    if r2['works'] is True:
        for k in ('streak', 'decided', 'outcome'): p.pop(k, None)
        p.update(works=True, code='ok', since=env.now(), told=False)
        notify.notify(notify.make('fixed', id_, f'{c["title"]} was restarted and works again', f'It could not do its job ({reason}). Argus restarted {say} as you allowed, and it works now.', url))
        return r2
    p['outcome'] = 'nohelp'
    if r2['works'] is False and r2['code'] != r['code']: p['code'] = r2['code']; r = r2
    title, detail = words(c, r['code'], r.get('why', ''))[1:]
    notify.notify(notify.make('broke', id_, title, f'{detail} Argus restarted {say} once, and it did not help. It will not try again by itself for a day.'.strip(), url))
    return r


def card_note(c, r, p, auto):
    """What Argus did about a failed check, for its card (the events file is not on any page yet). '' when there is nothing to
    say: no fix, the drive is the problem, a hung read, or self-repair may still act next round. Never claims a restart that
    did not happen."""
    fx = c.get('fix')
    if not fx or r['works'] is not False or r['code'].startswith('drive-') or r['code'] == 'read-hung': return ''
    say = fx.get('say') or ' and '.join(fx.get('restart', []))
    o = p.get('outcome')
    if o == 'trial': return f'Argus would have restarted {say} by itself and did not, because for now it only notes what it would do.'
    if o == 'nohelp': return f'Argus restarted {say} once by itself, and it did not help. It waits for your yes.'
    if o == 'cmdfail': return f'Argus tried to restart {say} by itself, but the restart did not work. It waits for your yes.'
    if o is None and c['id'] in auto and r['code'] in REPAIRABLE and p.get('decided') != r['code']: return ''
    return 'Argus did not restart it and waits for your yes.'


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
        level = 'alert'
        if r['code'] == 'unit-down': msg = 'Not running.'
        elif r['code'] == 'read-hung': msg, level = f"{r['title']} does not answer when it reads its drive.", 'warn'
        elif r['drive']: msg = r['reason'] + '.'
        else: msg = f"Running, but not working: {r['reason']}" + ('.' if r.get('note') else '')
        if r.get('note'): msg += ' ' + r['note']          # what Argus did about it (docs/checks.md, "What the card says")
        out.append(dict(file='watch-' + r['id'], job=r['job'], level=level, message=msg[:300], since=r['since'], link=''))
    return out


def start(env, interval=60, settle=SETTLE):
    """Run the loop in its own daemon thread. A round that fails is logged and the loop carries on."""
    load_prev()
    def loop():
        while not STOP.is_set():
            try: step(env, settle)
            except Exception as e: log(f'round failed: {e}')
            STOP.wait(interval)
    t = threading.Thread(target=loop, name='argus-watch', daemon=True); t.start()
    return t
