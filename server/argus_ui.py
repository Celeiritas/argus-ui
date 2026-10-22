#!/usr/bin/env python3
# Argus UI - a small web page that watches your systemd --user services ("tasks"), grouped by "agent".
#   Open it at http://<host>:8095, or anywhere on your tailnet with:  tailscale serve --bg --set-path /argus http://127.0.0.1:8095
# Powers on the page: Medusa freezes/thaws a task (stop + pause its timer; thaw restores it), Zeus's bolt runs/restarts it.
# Which agents exist, their names and the page title come from the theme (static/theme.json).
import json, os, re, socket, subprocess, sys, threading, mimetypes, ipaddress, importlib.util, traceback, types
from urllib.parse import urlsplit, parse_qs
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime

PORT = int(os.environ.get('ARGUS_PORT', 8095))
BIND = os.environ.get('ARGUS_BIND', '0.0.0.0')          # e.g. 127.0.0.1 to allow only tailscale serve / this machine
MAX_BODY = 4096
HOME = os.path.expanduser('~')
STATIC = os.environ.get('ARGUS_STATIC', f'{HOME}/.local/share/argus-ui/static')
SYSTEMCTL = os.environ.get('ARGUS_SYSTEMCTL', 'systemctl')
JOURNALCTL = os.environ.get('ARGUS_JOURNALCTL', 'journalctl')

# Mentor (the Learn section) lives in mentor.py next to this file, or in ~/.local/share/argus-ui when installed
sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)), os.path.expanduser('~/.local/share/argus-ui')]
import mentor
import sky          # weather for the background scene (sky.py; fetched server-side, cached 20 min)
SHARE = os.path.expanduser('~/.local/share/argus-ui')
MENTOR_DB = os.environ.get('ARGUS_MENTOR_DB', f'{SHARE}/mentor.db')
DECK_DIRS = [os.path.join(STATIC, 'decks'), os.environ.get('ARGUS_DECKS', f'{SHARE}/decks')]   # built-in + your own
MDB = mentor.connect(MENTOR_DB)
for _d in DECK_DIRS: mentor.load_decks(MDB, _d)

def load_theme():
    try: return json.load(open(os.path.join(STATIC, 'theme.json'), encoding='utf-8'))
    except Exception: return {}
THEME = load_theme()
REG = os.path.expanduser(os.environ.get('ARGUS_REGISTRY') or THEME.get('registry') or '~/.config/argus-ui/agents')
FROZEN = f'{REG}/frozen.json'
PERSONAS = [(a['key'], a['name'], a.get('domain', '')) for a in THEME.get('agents', [])] or [('argus', 'Argus', 'Watchman · monitoring')]
NEVER_FREEZE = set(THEME.get('never_freeze', ['argus-ui']))
PKEYS = [p[0] for p in PERSONAS]
PAGES = ['olympus']      # sections that are not agents (the Olympus playground)

# ---------- LeafyPlugins (docs/leafy-plugin.md) ----------
# A plugin is a folder ~/.config/argus-ui/plugins/<id>/ with a plugin.json manifest. "static" plugins
# (a browser game, a tool) are plain files shown in a sandboxed frame on their own section <base>/<id>.
# "server" plugins are trusted code the owner installed: a Python side (plugin.py, loaded once at startup,
# answering api/<id>/...) and a page script that runs inside Elaia's own page, like Mentor.
# Both live outside the install, so upgrades keep them, like the sounds.
PLUGINS = os.path.expanduser(os.environ.get('ARGUS_PLUGINS', '~/.config/argus-ui/plugins'))
PLUGIN_ID = re.compile(r'^[a-z][a-z0-9-]{0,31}$')
RESERVED = {'api', 'static', 'plugins', 'play', 'all', 'argus', 'sw.js', 'manifest.webmanifest',   # 'play' means Olympus in the page
            'state', 'sky', 'health', 'log', 'freeze', 'thaw', 'bolt', 'run'}                     # built-in api/<name> routes
mimetypes.add_type('text/javascript', '.js'); mimetypes.add_type('text/javascript', '.mjs')
mimetypes.add_type('model/gltf-binary', '.glb'); mimetypes.add_type('application/json', '.json')
mimetypes.add_type('application/wasm', '.wasm')
SERVER_PLUGINS = {}      # id -> the loaded plugin.py module (load_server_plugins, at startup)
PLUGIN_LOCKS = {}        # id -> lock: one POST at a time per plugin, like the powers' LOCK

def safe_file(d, name):
    # a file named in a manifest: relative, inside the folder, and there
    name = str(name or '')
    return name if name and '..' not in name and not name.startswith('/') and os.path.isfile(os.path.join(d, name)) else ''

def manifest(pid):
    """The checked manifest of one plugin folder, or None when it isn't a valid plugin."""
    d = os.path.join(PLUGINS, pid)
    if not PLUGIN_ID.match(pid) or pid in RESERVED or pid in PKEYS or pid in PAGES: return None
    try: m = json.load(open(os.path.join(d, 'plugin.json'), encoding='utf-8'))
    except Exception: return None
    if not isinstance(m, dict) or m.get('id') != pid: return None
    p = dict(id=pid, kind=m.get('kind', 'static'), name=str(m.get('name') or pid)[:40], subtitle=str(m.get('subtitle') or '')[:40],
             icon=safe_file(d, m.get('icon')), version=str(m.get('version') or '')[:20],
             order=m.get('order', 100) if isinstance(m.get('order'), int) else 100)
    if p['kind'] == 'static':
        p['entry'] = safe_file(d, m.get('entry') or 'index.html')
        return p if p['entry'] else None
    if p['kind'] == 'server':
        p['server'], p['page'] = safe_file(d, m.get('server') or 'plugin.py'), safe_file(d, m.get('page') or 'page.js')
        p['style'] = safe_file(d, m.get('style'))
        return p if p['server'].endswith('.py') and p['page'] else None
    return None                                                        # an unknown kind is skipped

def plugins():
    """Valid plugins, read fresh each call (a static plugin's deploy shows up without a restart). Bad ones are skipped.
    A server plugin is listed only once its plugin.py has loaded, so its page never meets a missing API."""
    try: names = sorted(os.listdir(PLUGINS))
    except OSError: return []
    found = [p for p in map(manifest, names) if p and (p['kind'] == 'static' or p['id'] in SERVER_PLUGINS)]
    return sorted(found, key=lambda p: (p['order'], p['name']))

def plugin_ctx(pid):
    # what a server plugin gets at init(ctx); each request gets a copy with .headers added (H.plugin_call)
    try:
        with open(os.path.join(STATIC, 'VERSION')) as f: v = f.read().strip()
    except OSError: v = 'dev'
    return types.SimpleNamespace(id=pid, data_dir=os.path.join(SHARE, 'plugins', pid), config_dir=os.path.join(PLUGINS, pid),
                                 base_url=os.environ.get('ARGUS_BASE_URL', '/argus/'), version=v, headers={})

def load_server_plugins():
    """Import each server plugin's plugin.py by path and call its init(ctx) once. One that fails is logged and
    skipped; the rest of Elaia starts. A newly installed server plugin needs a restart (static ones don't)."""
    try: names = sorted(os.listdir(PLUGINS))
    except OSError: return
    for pid in names:
        p = manifest(pid)
        if not p or p['kind'] != 'server': continue
        try:
            spec = importlib.util.spec_from_file_location('leafy_plugin_' + pid.replace('-', '_'), os.path.join(PLUGINS, pid, p['server']))
            mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
            ctx = plugin_ctx(pid); os.makedirs(ctx.data_dir, exist_ok=True)
            if hasattr(mod, 'init'): mod.init(ctx)
        except Exception:
            print(f'argus-ui: skipped server plugin {pid}: it failed to load\n{traceback.format_exc()}', file=sys.stderr, flush=True)
            continue
        SERVER_PLUGINS[pid] = mod; PLUGIN_LOCKS[pid] = threading.Lock()
        print(f'argus-ui: loaded server plugin {pid} {p["version"]}'.rstrip(), file=sys.stderr, flush=True)

# Headers on every plugin file: a sandboxed, opaque origin (even when opened in its own tab) that can't
# read Argus's state or post to its powers, plus CORS so its own module scripts and fetches still load.
PLUGIN_HEADERS = {'Content-Security-Policy': "sandbox allow-scripts allow-pointer-lock allow-popups; frame-ancestors 'self'",
                  'Access-Control-Allow-Origin': '*', 'X-Content-Type-Options': 'nosniff',
                  'Referrer-Policy': 'no-referrer', 'Cross-Origin-Resource-Policy': 'cross-origin'}
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

STARTED = datetime.now()
def health():
    # for a deploy tool (Zeus) and Janus's door probe: is this version up and answering? Nothing personal in it.
    try:
        with open(os.path.join(STATIC, 'VERSION')) as f: v = f.read().strip()
    except OSError: v = 'dev'
    return {'ok': True, 'version': v, 'uptime_s': int((datetime.now() - STARTED).total_seconds())}

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
                personas=[dict(key=k, name=n, domain=d) for k, n, d in PERSONAS],
                soon=THEME.get('coming_soon', []),
                plugins=[plugin_view(p) for p in plugins()])

def plugin_view(p):
    # what the page needs about a plugin; a server plugin's script and style URLs carry their file times, so a redeploy is fetched fresh
    v = {k: p[k] for k in ('id', 'kind', 'name', 'subtitle', 'icon', 'version')}
    if p['kind'] == 'server':
        for k in ('page', 'style'):
            try: v[k] = f"plugins/{p['id']}/{p[k]}?v={int(os.path.getmtime(os.path.join(PLUGINS, p['id'], p[k])))}" if p[k] else ''
            except OSError: v[k] = ''
    return v

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

    def out(self, body, ctype='text/html; charset=utf-8', code=200, cache='no-store', headers=None):
        b = body if isinstance(body, bytes) else body.encode()
        self.send_response(code)
        self.send_header('Content-Type', ctype); self.send_header('Content-Length', str(len(b)))
        for k, v in (headers or {}).items(): self.send_header(k, v)
        self.send_header('Cache-Control', cache); self.end_headers(); self.wfile.write(b)

    def plugin_file(self, rest):
        # plugins/<id>/<path>: files of a plugin, inside its folder only (same guard as static/).
        # A server plugin's Python side is never served, only its page script, style and whatever they load.
        pid, _, sub = rest.partition('/')
        p = next((x for x in plugins() if x['id'] == pid), None)
        if not p: return self.out('not found', 'text/plain', 404)
        if '/' not in rest:                                   # plugins/<id> -> plugins/<id>/ so relative URLs resolve
            self.send_response(301); self.send_header('Location', self.path.split('?', 1)[0] + '/')
            self.send_header('Content-Length', '0'); self.end_headers(); return
        root = os.path.realpath(os.path.join(PLUGINS, pid)); f = os.path.realpath(os.path.join(root, sub or p.get('entry', '')))
        if os.path.isdir(f): f = os.path.join(f, 'index.html')
        hidden = os.path.basename(f) == 'plugin.json' or (p['kind'] == 'server' and (f.endswith(('.py', '.pyc')) or '__pycache__' in f))
        if os.path.commonpath([root, f]) != root or not os.path.isfile(f) or hidden:
            return self.out('not found', 'text/plain', 404, headers=PLUGIN_HEADERS)
        ct = mimetypes.guess_type(f)[0] or 'application/octet-stream'
        if ct.startswith('text/') or ct in ('application/json',): ct += '; charset=utf-8'
        with open(f, 'rb') as fh:
            return self.out(fh.read(), ct, cache='no-cache' if f.endswith('.html') else 'max-age=300', headers=PLUGIN_HEADERS)

    # Request headers a server plugin may read (ctx.headers). Behind `tailscale serve` they say who is asking; they can
    # only be trusted when Elaia binds to 127.0.0.1, so a plugin that decides on them asks Janus (docs/leafy-plugin.md).
    PASS_HEADERS = ('Tailscale-User-Login', 'Tailscale-User-Name', 'X-Forwarded-For')

    def plugin_call(self, pid, verb, path, arg):
        # api/<id>/<path> -> the plugin's get(path, query, ctx) or post(path, body, ctx), which answers (status, obj)
        fn = getattr(SERVER_PLUGINS[pid], verb, None)
        ctx = plugin_ctx(pid); ctx.headers = {k: self.headers[k] for k in self.PASS_HEADERS if self.headers.get(k)}
        r = None
        if callable(fn):
            try:
                if verb == 'post':
                    with PLUGIN_LOCKS[pid]: code, obj = fn(path, arg, ctx)
                else: code, obj = fn(path, arg, ctx)
                if not isinstance(code, int) or not 100 <= code <= 599: raise ValueError(f'status {code!r} is not an HTTP status')
                r = code, obj, json.dumps(obj)
            except Exception:
                print(f'argus-ui: server plugin {pid} failed on {verb.upper()} {path}\n{traceback.format_exc()}', file=sys.stderr, flush=True)
                if path != 'status': return self.deny(500, 'plugin error')
        if verb == 'get' and path == 'status':        # reserved: one line for the Home page, or null; never an error
            line = r[1].get('line') if r and 200 <= r[0] < 300 and isinstance(r[1], dict) else None
            return self.out(json.dumps({'line': str(line)[:160] if line else None}), 'application/json')
        if not r: return self.deny(404, 'not found')
        self.out(r[2], 'application/json', r[0])

    def do_GET(self):
        if not host_ok(self.headers.get('Host')): return self.out('unknown host', 'text/plain', 421)
        try: self.get()
        except Exception as e: self.out(json.dumps({'ok': False, 'msg': 'server error'}), 'application/json', 500)

    def get(self):
        p = self.path_parts()
        if p.startswith('api/mentor/'): return self.mentor_get(p[11:], parse_qs(urlsplit(self.path).query))
        pid, _, rest = p[4:].partition('/')
        if p.startswith('api/') and pid in SERVER_PLUGINS: return self.plugin_call(pid, 'get', rest, parse_qs(urlsplit(self.path).query))
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
        if p == 'api/sky': return self.out(json.dumps(sky.current()), 'application/json')
        if p == 'api/health': return self.out(json.dumps(health()), 'application/json', cache='no-store')
        if p.startswith('api/log/'):
            u = p[8:]
            return self.out(json.dumps({'log': log(u) if u in units() else ''}), 'application/json')
        if p.startswith('plugins/'): return self.plugin_file(p[8:])
        first = p.split('/')[0]
        if p == '' or first in PKEYS or first in PAGES or first in {x['id'] for x in plugins()}: return self.out(page())
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
        if not isinstance(body, dict): return self.deny(400, 'bad json')
        p = self.path_parts()
        if p.startswith('api/mentor/'): return self.mentor_post(p[11:], body)
        pid, _, rest = p[4:].partition('/')
        if p.startswith('api/') and pid in SERVER_PLUGINS: return self.plugin_call(pid, 'post', rest, body)   # after every check above
        u = str(body.get('job', ''))
        actions = {'api/freeze': freeze, 'api/thaw': thaw, 'api/bolt': bolt, 'api/run': bolt}
        if p not in actions: return self.deny(404, 'not found')
        if u not in units(): return self.deny(400, 'unknown task')
        try:
            with LOCK: ok, msg = actions[p](u)
        except subprocess.TimeoutExpired: ok, msg = False, 'systemctl timed out'
        except Exception: ok, msg = False, 'server error'
        self.out(json.dumps({'ok': ok, 'msg': msg}), 'application/json')

    # ---------- Mentor ----------
    def mentor_get(self, what, q):
        deck = (q.get('deck') or [None])[0] or None
        if what == 'decks':
            decks = []
            for d in DECK_DIRS: decks += mentor.deck_list(d)
            return self.out(json.dumps({'decks': decks}), 'application/json')
        if what == 'next':
            if q.get('card'):                      # one Learn card to read again (Lessons view); never a practice card
                return self.out(json.dumps({'card': mentor.one_card(MDB, q['card'][0])}), 'application/json')
            card, next_due = mentor.next_card(MDB, deck, (q.get('extra') or ['0'])[0] == '1')
            return self.out(json.dumps({'card': card, 'next_due': next_due}), 'application/json')
        if what == 'stats': return self.out(json.dumps(mentor.stats(MDB, deck)), 'application/json')
        return self.deny(404, 'not found')

    def mentor_post(self, what, body):
        try:
            if what == 'answer' and body.get('hint'):       # one rung of the hint ladder; no attempt is written yet
                r = mentor.hint(MDB, str(body.get('card', '')), int(body['hint']))
            elif what == 'answer':
                text = str(body.get('text', ''))[:2000]
                conf = body.get('confidence'); conf = int(conf) if conf in (1, 2, 3, 4, '1', '2', '3', '4') else None
                ms = int(body.get('ms') or 0)
                r = mentor.answer(MDB, str(body.get('card', '')), text, conf, max(0, min(ms, 3_600_000)),
                                  int(body.get('hints') or 0), body.get('reflections') or [], bool(body.get('skipped')))
            elif what == 'rate':
                r = mentor.rate(MDB, int(body.get('attempt') or 0), int(body.get('rating') or 0), bool(body.get('grade_wrong')))
            else: return self.deny(404, 'not found')
        except (ValueError, TypeError): return self.deny(400, 'bad request')
        if r is None: return self.deny(400, 'unknown card or attempt')
        self.out(json.dumps({'ok': True, **r}), 'application/json')

if __name__ == '__main__':
    load_server_plugins()
    ThreadingHTTPServer((BIND, PORT), H).serve_forever()
