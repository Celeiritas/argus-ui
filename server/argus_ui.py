#!/usr/bin/env python3
# Argus UI - a small web page that watches your systemd --user services ("tasks"), grouped by "agent".
#   Open it at http://<host>:8095, or anywhere on your tailnet with:  tailscale serve --bg --set-path /argus http://127.0.0.1:8095
# Powers on the page: Medusa freezes/thaws a task (stop + pause its timer; thaw restores it), Zeus's bolt runs/restarts it.
# Which agents exist, their names and the page title come from the theme (static/theme.json).
import json, os, re, socket, subprocess, threading, mimetypes, ipaddress
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime

PORT = int(os.environ.get('ARGUS_PORT', 8095))
BIND = os.environ.get('ARGUS_BIND', '0.0.0.0')          # e.g. 127.0.0.1 to allow only tailscale serve / this machine
MAX_BODY = 4096
HOME = os.path.expanduser('~')
STATIC = os.environ.get('ARGUS_STATIC', f'{HOME}/.local/share/argus-ui/static')
SYSTEMCTL = os.environ.get('ARGUS_SYSTEMCTL', 'systemctl')
JOURNALCTL = os.environ.get('ARGUS_JOURNALCTL', 'journalctl')

def load_theme():
    try: return json.load(open(os.path.join(STATIC, 'theme.json'), encoding='utf-8'))
    except Exception: return {}
THEME = load_theme()
REG = os.path.expanduser(os.environ.get('ARGUS_REGISTRY') or THEME.get('registry') or '~/.config/argus-ui/agents')
FROZEN = f'{REG}/frozen.json'
PERSONAS = [(a['key'], a['name'], a.get('domain', '')) for a in THEME.get('agents', [])] or [('argus', 'Argus', 'Watchman · monitoring')]
NEVER_FREEZE = set(THEME.get('never_freeze', ['argus-ui']))
PKEYS = [p[0] for p in PERSONAS]
GODS = re.compile(r'^(%s)-' % '|'.join(PKEYS))

def run(*a):
    return subprocess.run(a, capture_output=True, text=True, timeout=20).stdout

def run_ok(*a):
    r = subprocess.run(a, capture_output=True, text=True, timeout=20)
    return r.returncode == 0, (r.stderr or r.stdout).strip()

def sc(*a):
    return run(SYSTEMCTL, '--user', *a)

def sc_ok(*a):
    return run_ok(SYSTEMCTL, '--user', *a)

def units():
    out = sc('list-unit-files', '--type=service', '--no-legend')
    us = set()
    for l in out.splitlines():
        if not l.strip(): continue
        n = l.split()[0]
        if n.endswith('.service'): n = n[:-8]
        if GODS.match(n) and not n.endswith('@'): us.add(n)
    return sorted(us)

def props(unit, *p):
    return dict(l.split('=', 1) for l in sc('show', unit, '-p', ','.join(p)).splitlines() if '=' in l)

def hb(n):
    try: n = int(n)
    except Exception: return '-'
    if n < 0 or n >= 2**63: return '-'
    for u in 'BKMGT':
        if n < 1024: return f'{n:.0f}{u}'
        n /= 1024
    return '-'

def when(ts):
    # compact: "9:20 AM" today, "Sat 8:52 PM" within a week, "Oct 25" further out
    try:
        d = datetime.strptime(' '.join(ts.split()[1:3]), '%Y-%m-%d %H:%M:%S')
    except Exception: return ''
    now = datetime.now(); t = d.strftime('%I:%M %p').lstrip('0')
    if d.date() == now.date(): return t
    if abs((d - now).days) < 6: return d.strftime('%a ') + t
    return d.strftime('%b %d').replace(' 0', ' ')

LOCK = threading.Lock()          # one freeze/thaw/bolt at a time, so two clicks can't overwrite each other's record

def frozen():
    try:
        with open(FROZEN) as f: return json.load(f)
    except Exception: return {}

def save_frozen(d):
    os.makedirs(REG, exist_ok=True)
    tmp = FROZEN + '.tmp'
    with open(tmp, 'w') as f: json.dump(d, f, indent=2)
    os.replace(tmp, FROZEN)        # atomic: a crash mid-write can't leave a half-written file

def has_timer(u):
    return props(u + '.timer', 'LoadState').get('LoadState') == 'loaded'

def info(u, fz):
    p = props(u + '.service', 'Result', 'ActiveState', 'ExecMainExitTimestamp', 'ExecMainStartTimestamp',
              'MemoryPeak', 'IOWriteBytes', 'Description')
    timer = has_timer(u)
    t = props(u + '.timer', 'NextElapseUSecRealtime', 'ActiveState') if timer else {}
    if u in fz: state = 'frozen'
    elif p.get('ActiveState') in ('active', 'activating', 'reloading'): state = 'running'
    elif p.get('ActiveState') == 'failed' or p.get('Result') not in ('success', '', None): state = 'failed'
    elif not p.get('ExecMainExitTimestamp') and not p.get('ExecMainStartTimestamp'): state = 'never'
    else: state = 'ok'
    reg = {}
    try: reg = json.load(open(f'{REG}/{u}.json'))
    except Exception: pass
    persona = u.split('-')[0]
    if u in fz: nxt = 'paused by Medusa'
    elif timer: nxt = when(t.get('NextElapseUSecRealtime', '')) or 'paused'
    else: nxt = 'always on' if state == 'running' else 'manual'
    return dict(job=u, persona=persona, name=u[len(persona) + 1:], state=state,
                last=when(p.get('ExecMainExitTimestamp') or p.get('ExecMainStartTimestamp', '')) or '—',
                next=nxt, mem=hb(p.get('MemoryPeak')), wrote=hb(p.get('IOWriteBytes')),
                notes=reg.get('notes', '') or p.get('Description', ''), canfreeze=u not in NEVER_FREEZE,
                frozen_at=fz.get(u, {}).get('at', ''))

def state():
    fz = frozen()
    jobs = [info(u, fz) for u in units()]
    return dict(updated=datetime.now().strftime('%I:%M %p').lstrip('0'), jobs=jobs,
                title=THEME.get('title', 'Argus'), subtitle=THEME.get('subtitle', 'tasks'),
                personas=[dict(key=k, name=n, domain=d) for k, n, d in PERSONAS])

def log(u):
    return run(JOURNALCTL, '--user', '-u', u, '-n', '40', '--no-pager', '-o', 'short-iso')

def freeze(u):
    if u in NEVER_FREEZE or u not in units(): return False, 'not allowed'
    fz = frozen()
    if u in fz: return True, 'already frozen'
    timer = has_timer(u)
    rec = dict(at=datetime.now().strftime('%Y-%m-%d %H:%M'), timer=timer,
               timer_enabled=timer and sc('is-enabled', u + '.timer').strip() == 'enabled',
               service_enabled=sc('is-enabled', u + '.service').strip() == 'enabled',
               service_active=sc('is-active', u + '.service').strip() == 'active')
    fz[u] = rec; save_frozen(fz)          # record first, so a thaw can always restore what we change below
    steps = ([('stop', u + '.timer')] + ([('disable', u + '.timer')] if rec['timer_enabled'] else []) if timer else []) \
        + [('stop', u + '.service')] + ([('disable', u + '.service')] if rec['service_enabled'] else [])
    for verb, unit in steps:
        ok, err = sc_ok(verb, unit)
        if not ok: return False, f'{verb} {unit} failed: {err[:120]}'
    return True, 'frozen'

def bolt(u):
    # Zeus: a timer/oneshot agent gets Run; an always-on service gets Restart. Frozen agents must be thawed first.
    if u in frozen(): return False, 'frozen - thaw it first'
    verb = 'start' if has_timer(u) or props(u + '.service', 'Type').get('Type') == 'oneshot' else 'restart'
    ok, err = sc_ok(verb, '--no-block', u + '.service')
    if not ok: return False, f'{verb} failed: {err[:120]}'
    return True, 'struck - running now' if verb == 'start' else 'struck - restarted'

def thaw(u):
    fz = frozen()
    rec = fz.get(u)
    if not rec: return True, 'not frozen'
    steps = ([('enable', u + '.service')] if rec.get('service_enabled') else [])
    if rec.get('timer'): steps.append(('enable', '--now', u + '.timer') if rec.get('timer_enabled') else ('start', u + '.timer'))
    elif rec.get('service_active') or rec.get('service_enabled'): steps.append(('start', '--no-block', u + '.service'))
    for st in steps:
        ok, err = sc_ok(*st)
        if not ok: return False, f'{st[0]} {st[-1]} failed: {err[:120]}'   # stays frozen, so it can be retried
    del fz[u]; save_frozen(fz)
    return True, 'thawed'

PAGE = None
def page():
    global PAGE
    if PAGE is None or os.environ.get('ARGUS_DEV'):
        PAGE = open(os.path.join(STATIC, 'index.html'), encoding='utf-8').read()
    # "</" is escaped so text from a unit's Description can never close the <script> tag
    return PAGE.replace('/*STATE*/null', json.dumps(state()).replace('</', '<\\/'))

# Only answer to this machine's own names, IP addresses and Tailscale names (blocks DNS-rebinding attacks),
# plus anything listed in ARGUS_ALLOWED_HOSTS (comma separated).
_hn = socket.gethostname().lower()
ALLOWED = {'localhost', _hn, _hn.split('.')[0]} | {h.strip().lower() for h in os.environ.get('ARGUS_ALLOWED_HOSTS', '').split(',') if h.strip()}
def host_ok(host):
    h = (host or '').strip().lower()
    if h.startswith('['): h = h[1:h.find(']')]
    elif h.count(':') == 1: h = h.rsplit(':', 1)[0]
    if h in ALLOWED or h.endswith('.ts.net') or h.endswith('.local'): return True
    try: ipaddress.ip_address(h); return True
    except ValueError: return False

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def path_parts(self):
        p = self.path.split('?', 1)[0]
        if p.startswith('/argus'): p = p[6:]          # works whether or not Tailscale strips /argus
        return p.lstrip('/')

    def out(self, body, ctype='text/html; charset=utf-8', code=200, cache='no-store'):
        b = body if isinstance(body, bytes) else body.encode()
        self.send_response(code)
        self.send_header('Content-Type', ctype); self.send_header('Content-Length', str(len(b)))
        self.send_header('Cache-Control', cache); self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        if not host_ok(self.headers.get('Host')): return self.out('unknown host', 'text/plain', 421)
        try: self.get()
        except Exception as e: self.out(json.dumps({'ok': False, 'msg': 'server error'}), 'application/json', 500)

    def get(self):
        p = self.path_parts()
        if p.startswith('static/'):
            root = os.path.realpath(STATIC); f = os.path.realpath(os.path.join(root, p[7:]))
            if os.path.commonpath([root, f]) != root or not os.path.isfile(f): return self.out('not found', 'text/plain', 404)
            ct = mimetypes.guess_type(f)[0] or 'application/octet-stream'
            if f.endswith('.webmanifest'): ct = 'application/manifest+json'
            with open(f, 'rb') as fh: return self.out(fh.read(), ct, cache='max-age=300')
        if p in ('manifest.webmanifest', 'sw.js'):
            f = os.path.join(STATIC, p)
            if not os.path.isfile(f): return self.out('not found', 'text/plain', 404)
            with open(f, 'rb') as fh: return self.out(fh.read(), 'application/manifest+json' if p.endswith('manifest') else 'text/javascript')
        if p == 'api/state': return self.out(json.dumps(state()), 'application/json')
        if p.startswith('api/log/'):
            u = p[8:]
            return self.out(json.dumps({'log': log(u) if u in units() else ''}), 'application/json')
        if p == '' or p.split('/')[0] in PKEYS: return self.out(page())
        return self.out('not found', 'text/plain', 404)

    def deny(self, code, msg): return self.out(json.dumps({'ok': False, 'msg': msg}), 'application/json', code)

    def do_POST(self):
        # Cross-site protection (there is no login): right host, JSON only (a plain HTML form can't send it),
        # and the browser must say the request came from this page itself.
        if not host_ok(self.headers.get('Host')): return self.deny(421, 'unknown host')
        if (self.headers.get('Content-Type') or '').split(';')[0].strip() != 'application/json': return self.deny(415, 'json only')
        site = self.headers.get('Sec-Fetch-Site'); origin = self.headers.get('Origin')
        if site and site not in ('same-origin', 'none'): return self.deny(403, 'cross-site request blocked')
        if origin and origin.split('://', 1)[-1] != self.headers.get('Host'): return self.deny(403, 'cross-site request blocked')
        try: n = int(self.headers.get('Content-Length', 0) or 0)
        except ValueError: n = -1
        if n < 0 or n > MAX_BODY: return self.deny(413, 'request too large')
        try: body = json.loads(self.rfile.read(n) or b'{}')
        except Exception: return self.deny(400, 'bad json')
        u = str(body.get('job', '')) if isinstance(body, dict) else ''
        p = self.path_parts()
        actions = {'api/freeze': freeze, 'api/thaw': thaw, 'api/bolt': bolt, 'api/run': bolt}
        if p not in actions: return self.deny(404, 'not found')
        if u not in units(): return self.deny(400, 'unknown task')
        try:
            with LOCK: ok, msg = actions[p](u)
        except subprocess.TimeoutExpired: ok, msg = False, 'systemctl timed out'
        except Exception: ok, msg = False, 'server error'
        self.out(json.dumps({'ok': ok, 'msg': msg}), 'application/json')

if __name__ == '__main__':
    ThreadingHTTPServer((BIND, PORT), H).serve_forever()
