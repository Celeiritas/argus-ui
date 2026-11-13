#!/usr/bin/env python3
# Argus UI - a small web page that watches your systemd --user services ("tasks"), grouped by "agent".
#   Open it at http://<host>:8095, or anywhere on your tailnet with:  tailscale serve --bg --set-path /argus http://127.0.0.1:8095
# Powers on the page: Medusa freezes/thaws a task (stop + pause its timer; thaw restores it), Zeus's bolt runs/restarts it.
# Which agents exist, their names and the page title come from the theme (static/theme.json).
import json, os, re, socket, subprocess, sys, threading, mimetypes, ipaddress, importlib.util, inspect, traceback, types
from urllib.parse import urlsplit, parse_qs, unquote, quote
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime, timezone
from email.utils import formatdate, parsedate_to_datetime

PORT = int(os.environ.get('ARGUS_PORT', 8095))
BIND = os.environ.get('ARGUS_BIND', '127.0.0.1')        # this machine only (tailscale serve passes requests on); 0.0.0.0 only on purpose
MAX_BODY = 4096
PLUGIN_MAX_BODY = 64 * 1024 * 1024   # the most a server plugin may ask for with "max_body" (4.23.0)
HOME = os.path.expanduser('~')
STATIC = os.environ.get('ARGUS_STATIC', f'{HOME}/.local/share/argus-ui/static')
SYSTEMCTL = os.environ.get('ARGUS_SYSTEMCTL', 'systemctl')
JOURNALCTL = os.environ.get('ARGUS_JOURNALCTL', 'journalctl')

# sky.py lives next to this file, or in ~/.local/share/argus-ui when installed. Mentor is a bundled plugin (plugins/mentor/).
sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)), os.path.expanduser('~/.local/share/argus-ui')]
import sky          # weather for the background scene (sky.py; fetched server-side, cached 20 min)
import watch        # "works, not just runs": checks.json, the mount table, one event per change (watch.py, docs/checks.md)
import identity     # who is asking: Tailscale Serve's login (trusted only from Serve's own connection) and the people file (docs/people.md)
import push, summary  # phone alerts (Web Push) and the daily summary (docs/phone-alerts.md)
import notify       # the events file those changes go to (notify.py); api/events reads it for Watch's "What happened lately"
SHARE = os.path.expanduser('~/.local/share/argus-ui')

def load_theme():
    try: return json.load(open(os.path.join(STATIC, 'theme.json'), encoding='utf-8'))
    except Exception: return {}
THEME = load_theme()
REG = os.path.expanduser(os.environ.get('ARGUS_REGISTRY') or THEME.get('registry') or '~/.config/argus-ui/agents')
FROZEN = f'{REG}/frozen.json'
PERSONAS = [(a['key'], a['name'], a.get('domain', '')) for a in THEME.get('agents', [])] or [('argus', 'Argus', 'Watchman · monitoring')]
NEVER_FREEZE = set(THEME.get('never_freeze', ['argus-ui']))
PKEYS = [p[0] for p in PERSONAS]
PAGES = ['olympus', 'home', 'phone']   # sections that are not agents: the Olympus playground, Home (docs/home.md), Phone alerts (docs/phone-alerts.md)
MOVED = {'pads': 'controllers'}  # sections that changed their address: <base>/pads still lands on Controllers (4.33.0, for one release)

# ---------- LeafyPlugins (docs/leafy-plugin.md) ----------
# A plugin is a folder ~/.config/argus-ui/plugins/<id>/ with a plugin.json manifest. "static" plugins
# (a browser game, a tool) are plain files shown in a sandboxed frame on their own section <base>/<id>.
# "server" plugins are trusted code the owner installed: a Python side (plugin.py, loaded once at startup,
# answering api/<id>/...) and a page script that runs inside Elaia's own page (Mentor is one, bundled).
# Yours live outside the install, so upgrades keep them, like the sounds. Bundled plugins ship with Elaia (the repo's
# plugins/ folder, installed to ~/.local/share/argus-ui/bundled/) and are replaced by each install; yours win on the same id.
PLUGINS = os.path.expanduser(os.environ.get('ARGUS_PLUGINS', '~/.config/argus-ui/plugins'))
# Links to other pages on the same machine (a studio, a dashboard), shown in the section bar and on Home: a list of
# {"name", "what", "href"} in ~/.config/argus-ui/links.json; href must be a same-host path ("/studio/") or https://.
LINKS = os.path.expanduser(os.environ.get('ARGUS_LINKS', '~/.config/argus-ui/links.json'))
BUNDLED = os.path.expanduser(os.environ.get('ARGUS_BUNDLED', '~/.local/share/argus-ui/bundled'))
PLUGIN_ID = re.compile(r'^[a-z][a-z0-9-]{0,31}$')
RESERVED = {'api', 'static', 'plugins', 'play', 'all', 'argus', 'sw.js', 'manifest.webmanifest',   # 'play' means Olympus in the page
            'state', 'sky', 'health', 'log', 'freeze', 'thaw', 'bolt', 'run', 'whoami', 'push', 'events', 'watch'}   # built-in api/<name> routes
mimetypes.add_type('text/javascript', '.js'); mimetypes.add_type('text/javascript', '.mjs')
mimetypes.add_type('model/gltf-binary', '.glb'); mimetypes.add_type('application/json', '.json')
mimetypes.add_type('application/wasm', '.wasm')
SERVER_PLUGINS = {}      # id -> the loaded plugin.py module (load_server_plugins, at startup)
PLUGIN_LOCKS = {}        # id -> lock: one POST at a time per plugin, like the powers' LOCK
PLUGIN_DIR = {}          # id -> the folder its plugin.py was loaded from (bundled or yours)
PLUGIN_BODY = {}         # id -> its POST size limit ("max_body" in plugin.json, 4.23.0)

# ---------- People and roles (docs/people.md) ----------
# ~/.config/argus-ui/people.json (ARGUS_PEOPLE) says which Tailscale login is which person and their role: owner (everything)
# or learner (Today and the study pages). No file: everyone is the owner, as before. Read again whenever it changes.
PEOPLE = identity.People(os.path.expanduser(os.environ.get('ARGUS_PEOPLE') or '~/.config/argus-ui/people.json'),
                         last_good=os.path.expanduser(os.environ.get('ARGUS_PEOPLE_LAST_GOOD') or '~/.local/state/argus-ui/people.last-good.json'),
                         must_exist=bool(os.environ.get('ARGUS_PEOPLE')))   # a path set on purpose that is missing: broken, not "no file"
SERVE_UID = identity.serve_uid()          # the user Tailscale Serve's connections come from (ARGUS_SERVE_UID, default 0; never our own)

def safe_file(d, name):
    # a file named in a manifest: relative, inside the folder, and there
    name = str(name or '')
    return name if name and '..' not in name and not name.startswith('/') and os.path.isfile(os.path.join(d, name)) else ''

def plugin_dirs():
    """id -> folder of every plugin folder: the bundled ones, then yours (yours win on the same id)."""
    found = {}
    for root in (BUNDLED, PLUGINS):
        try: names = os.listdir(root)
        except OSError: continue
        for n in names:
            if os.path.isdir(os.path.join(root, n)): found[n] = os.path.join(root, n)
    return found

def manifest(pid, d):
    """The checked manifest of one plugin folder, or None when it isn't a valid plugin.
    A server plugin with "agent": true takes over the section of the theme's agent with the same id (Mentor)."""
    if not PLUGIN_ID.match(pid) or pid in RESERVED or pid in PAGES: return None
    try: m = json.load(open(os.path.join(d, 'plugin.json'), encoding='utf-8'))
    except Exception: return None
    if not isinstance(m, dict) or m.get('id') != pid: return None
    agent = next((x for x in PERSONAS if x[0] == pid), None)
    if agent and not (m.get('agent') is True and m.get('kind') == 'server'): return None   # an agent's name only by claiming it
    if m.get('agent') is True and not agent: return None
    p = dict(id=pid, kind=m.get('kind', 'static'), name=str(m.get('name') or (agent and agent[1]) or pid)[:40],
             subtitle=str(m.get('subtitle') or (agent and agent[2].split('·')[0].strip()) or '')[:40],
             icon=safe_file(d, m.get('icon')), version=str(m.get('version') or '')[:20], agent=bool(agent), dir=d,
             bundled=os.path.dirname(d) == BUNDLED, order=m.get('order', 100) if isinstance(m.get('order'), int) else 100)
    # which of its api/<id>/<path> a learner may call ("roles", docs/people.md); undeclared = the owner's. Only a server
    # plugin can open anything: a static plugin stays the owner's, files and all.
    p['roles'] = identity.plugin_roles(m.get('roles') if p['kind'] == 'server' else None)
    p['learner'] = bool(p['roles']['get'] or p['roles']['post'])
    if p['kind'] == 'static':
        p['entry'] = safe_file(d, m.get('entry') or 'index.html')
        return p if p['entry'] else None
    if p['kind'] == 'server':
        p['server'], p['page'] = safe_file(d, m.get('server') or 'plugin.py'), safe_file(d, m.get('page') or 'page.js')
        p['style'] = safe_file(d, m.get('style'))
        # a larger POST limit for its own api/<id>/... (a page that saves records or uploads images), never below the
        # default and never above PLUGIN_MAX_BODY; every other check on a POST stays the same
        mb = m.get('max_body')
        p['max_body'] = min(max(mb, MAX_BODY), PLUGIN_MAX_BODY) if isinstance(mb, int) and not isinstance(mb, bool) else MAX_BODY
        return p if p['server'].endswith('.py') and p['page'] else None
    return None                                                        # an unknown kind is skipped

def plugins():
    """Valid plugins, read fresh each call (a static plugin's deploy shows up without a restart). Bad ones are skipped.
    A server plugin is listed only once its plugin.py has loaded, so its page never meets a missing API."""
    found = [p for p in (manifest(i, d) for i, d in plugin_dirs().items()) if p and (p['kind'] == 'static' or p['id'] in SERVER_PLUGINS)]
    return sorted(found, key=lambda p: (p['order'], p['name']))

def plugin_ctx(pid, d):
    # what a server plugin gets at init(ctx); each request gets a copy with .headers added (H.plugin_call)
    try:
        with open(os.path.join(STATIC, 'VERSION')) as f: v = f.read().strip()
    except OSError: v = 'dev'
    return types.SimpleNamespace(id=pid, data_dir=os.path.join(SHARE, 'plugins', pid), config_dir=d, theme_dir=STATIC,
                                 base_url=os.environ.get('ARGUS_BASE_URL', '/argus/'), version=v, headers={}, jobs=plugin_jobs)

def plugin_jobs(prefix=''):
    """ctx.jobs(prefix): the tasks Watch shows (state, last, next, frozen ...) whose unit starts with prefix, so a server
    plugin reads what Elaia already collects instead of running systemctl itself (Memory reads mnemosyne-*)."""
    fz = frozen()
    return collapse([info(u, fz) for u in units() if u.startswith(str(prefix))])

def load_server_plugins():
    """Import each server plugin's plugin.py by path and call its init(ctx) once. One that fails is logged and
    skipped; the rest of Elaia starts. A newly installed server plugin needs a restart (static ones don't)."""
    for pid, d in sorted(plugin_dirs().items()):
        p = manifest(pid, d)
        if not p or p['kind'] != 'server': continue
        try:
            spec = importlib.util.spec_from_file_location('leafy_plugin_' + pid.replace('-', '_'), os.path.join(d, p['server']))
            mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
            ctx = plugin_ctx(pid, d); os.makedirs(ctx.data_dir, exist_ok=True)
            if hasattr(mod, 'init'): mod.init(ctx)
        except Exception:
            print(f'argus-ui: skipped server plugin {pid}: it failed to load\n{traceback.format_exc()}', file=sys.stderr, flush=True)
            continue
        SERVER_PLUGINS[pid] = mod; PLUGIN_LOCKS[pid] = threading.Lock(); PLUGIN_DIR[pid] = d; PLUGIN_BODY[pid] = p['max_body']
        print(f'argus-ui: loaded server plugin {pid} {p["version"]}'.rstrip() + (' (bundled)' if p['bundled'] else ''), file=sys.stderr, flush=True)

# Headers on every plugin file: a sandboxed, opaque origin (even when opened in its own tab) that can't
# read Argus's state or post to its powers, plus CORS so its own module scripts and fetches still load.
PLUGIN_HEADERS = {'Content-Security-Policy': "sandbox allow-scripts allow-pointer-lock allow-popups; frame-ancestors 'self'",
                  'Access-Control-Allow-Origin': '*', 'X-Content-Type-Options': 'nosniff',
                  'Referrer-Policy': 'no-referrer', 'Cross-Origin-Resource-Policy': 'cross-origin'}
# Caching plugin files (4.27.0): every file carries Last-Modified and an ETag, and a conditional GET answers 304, so a
# reload re-checks a file instead of downloading it again. A content-hashed name (models/ares.1a2b3c4d.glb) never
# changes, so it is kept a year; every unhashed text file (page, script, stylesheet, JSON, source map) may point to
# those names or change with a deploy, so it is checked every time; the rest (unhashed binaries) for an hour.
HASHED = re.compile(r'\.[0-9a-f]{8}\.[A-Za-z0-9]+$')
FRESH = re.compile(r'\.(html|js|mjs|css|json|map)$')

def plugin_cache(rel):
    """Cache-Control for a plugin file, by its path inside the plugin folder (forward slashes)."""
    if HASHED.search(rel): return 'public, max-age=31536000, immutable'
    if FRESH.search(rel): return 'no-cache'
    return 'max-age=3600'

def not_modified(headers, etag, mtime):
    """True when the browser's copy is current: If-None-Match names this ETag (or *), or, only when there is no
    If-None-Match, If-Modified-Since is at or after the file's time (HTTP dates have whole seconds)."""
    inm = headers.get('If-None-Match')
    if inm is not None:
        tags = [t.strip() for t in inm.split(',')]
        return '*' in tags or etag in (t[2:] if t.startswith('W/') else t for t in tags)
    ims = headers.get('If-Modified-Since')
    if not ims: return False
    try: d = parsedate_to_datetime(ims)
    except (TypeError, ValueError, IndexError): return False
    if d.tzinfo is None: d = d.replace(tzinfo=timezone.utc)
    return int(mtime) <= d.timestamp()

# ---------- A static plugin on its own address (4.42.0, docs/leafy-plugin.md "Its own address") ----------
# The sandbox gives a plugin an opaque origin: no cache it can keep, no storage, no nested frames, no downloads. A game
# that needs those gets its own address instead: a second listener on this machine only, published on its own HTTPS port
# by tailscale serve. A different port is a different origin, so the browser keeps it out of Argus's answers and its POSTs
# fail do_POST's checks, without a sandbox. Cookies are the exception (per host name, not port): it can set some that the
# browser sends here too, and Argus reads none and skips them whatever their size (NoCookies). The host file (never in git)
# says which plugins and which ports:
#   {"<id>": {"port": <local port>, "public": <https port>, "links": [{"name": "Frame data", "path": "frames/"}]}}
# No file: nothing changes. It is read once, at startup (a change needs a restart).
OWN_ORIGIN = os.path.expanduser(os.environ.get('ARGUS_OWN_ORIGIN') or '~/.config/argus-ui/own-origin.json')
OWN = {}                 # id -> its checked entry, for each own listener that started (start_own_origins)
OWN_LINK = re.compile(r'^[A-Za-z0-9._~-][A-Za-z0-9._~/-]{0,199}$')     # a relative path inside the plugin, nothing else
# A game on its own origin: its own files, inline scripts and styles (an import map), blob and data URLs for loaded models
# and exports, WebAssembly, frames of its own pages. Framed by nobody else. No sandbox, so storage and the cache work.
OWN_HEADERS = {'Content-Security-Policy': "default-src 'self'; script-src 'self' 'unsafe-inline' 'wasm-unsafe-eval'; "
                                          "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; media-src 'self' data: blob:; "
                                          "font-src 'self' data:; connect-src 'self' data: blob:; worker-src 'self' blob:; "
                                          "frame-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'self'",
               'X-Frame-Options': 'SAMEORIGIN', 'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'same-origin',
               'Cross-Origin-Resource-Policy': 'same-origin', 'Cross-Origin-Opener-Policy': 'same-origin'}

def load_own_origin(path=None):
    """The checked own-origin.json: {id: {port, public, links}}. A missing file is {}; a broken file or entry is logged
    and left out, so a mistake there never stops Elaia."""
    say = lambda m: print(f'argus-ui: own-origin.json: {m}', file=sys.stderr, flush=True)
    try:
        with open(path or OWN_ORIGIN, encoding='utf-8') as f: raw = json.load(f)
    except FileNotFoundError: return {}
    except (OSError, ValueError, RecursionError):     # RecursionError: nested thousands deep
        say('cannot be read as JSON, so no plugin gets its own address'); return {}
    if not isinstance(raw, dict): say('must be an object of plugin ids, so no plugin gets its own address'); return {}
    num = lambda v, lo: isinstance(v, int) and not isinstance(v, bool) and lo <= v <= 65535
    found, used, published = {}, {PORT}, {80, 443}
    for pid, c in raw.items():
        if not (isinstance(pid, str) and PLUGIN_ID.match(pid) and pid not in RESERVED and pid not in PAGES and isinstance(c, dict)):
            say(f'skipped {str(pid)[:40]!r}: not a plugin id with settings'); continue
        port, public = c.get('port'), c.get('public')
        if not num(port, 1024) or port in used:
            say(f'skipped {pid}: "port" must be a local port from 1024 to 65535 that nothing else here uses'); continue
        if not num(public, 1) or public in published:
            say(f'skipped {pid}: "public" must be its own HTTPS port on tailscale serve, never 443 (Argus\'s address) or another plugin\'s'); continue
        links = []
        for ln in (c.get('links') if isinstance(c.get('links'), list) else []):
            name, rel = (ln.get('name'), ln.get('path')) if isinstance(ln, dict) else (None, None)
            if isinstance(name, str) and 0 < len(name.strip()) <= 40 and isinstance(rel, str) and OWN_LINK.match(rel) and '..' not in rel.split('/'):
                links.append({'name': name.strip(), 'path': rel})
            else: say(f'{pid}: skipped a link (it needs a "name" and a "path" inside the plugin, like "frames/")')
        found[pid] = {'port': port, 'public': public, 'links': links[:4]}; used.add(port); published.add(public)
    return found

GODS = re.compile(r'^(%s)-' % '|'.join(PKEYS))

# ---------- Alert files (docs/alerts.md) ----------
# Any agent can make Argus glare without a failed unit: a JSON file in ~/.local/state/argus-ui/alerts/
# {"job", "level": "warn"|"alert", "message", "since", "link"}. Read on every refresh; the file going away calms him.
ALERTS = os.path.expanduser(os.environ.get('ARGUS_ALERTS') or THEME.get('alerts') or '~/.local/state/argus-ui/alerts')
ALERT_JOB = re.compile(r'^[a-z][a-z0-9-]{0,80}$')
_told = set()                    # (file, mtime) of malformed files already logged: one line each, not one per refresh

def alerts(sections):
    """The alerts up now, oldest first. A malformed file is skipped with one log line; a link to a section that
    isn't installed is dropped (the alert still shows)."""
    try: names = sorted(n for n in os.listdir(ALERTS) if n.endswith('.json'))
    except OSError: return []
    found = []
    for n in names:
        f = os.path.join(ALERTS, n)
        try:
            with open(f, encoding='utf-8') as fh: a = json.load(fh)
            if not isinstance(a, dict): raise ValueError('not a JSON object')
            job, level, msg = a.get('job'), a.get('level'), a.get('message')
            if not isinstance(job, str) or not ALERT_JOB.match(job) or not GODS.match(job): raise ValueError(f'job {job!r} is not an agent task name')
            if level not in ('warn', 'alert'): raise ValueError(f'level {level!r} is not warn or alert')
            if not isinstance(msg, str) or not msg.strip(): raise ValueError('no message')
        except Exception as e:
            try: key = (n, os.path.getmtime(f))
            except OSError: continue                     # gone between listdir and open: nothing to say
            if key not in _told:
                _told.add(key); print(f'argus-ui: ignored alert file {n}: {e}', file=sys.stderr, flush=True)
            continue
        link = a.get('link') if isinstance(a.get('link'), str) and a.get('link') in sections else ''
        found.append(dict(file=n, job=job, level=level, message=msg.strip()[:300], since=str(a.get('since') or '')[:40], link=link))
    return sorted(found, key=lambda a: (a['since'], a['file']))

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

def registry(u):
    """A task's registry entry and the name it was found under: <task>.json, else the longest prefix before a '-'
    (zeus-deploy-20261021-090012-argus-ui-3fa9c1b -> zeus-deploy.json), stopping above the god's own prefix.
    That way a unit with a new name every run (Zeus's deploys) still gets its card's notes."""
    parts = u.split('-')
    for i in range(len(parts), 1, -1):
        name = '-'.join(parts[:i])
        try:
            with open(f'{REG}/{name}.json', encoding='utf-8') as f: e = json.load(f)
        except Exception: continue
        if isinstance(e, dict): return e, name
    return {}, u

def started(ts):
    # "Sun 2026-10-18 09:20:44 MDT" -> "2026-10-18 09:20:44", sortable; '' when it never ran
    return ' '.join(ts.split()[1:3]) if ts else ''

def has_timer(u):
    return props(u + '.timer', 'LoadState').get('LoadState') == 'loaded'

def info(u, fz):
    p = props(u + '.service', 'Result', 'ActiveState', 'ExecMainExitTimestamp', 'ExecMainStartTimestamp',
              'MemoryPeak', 'IOWriteBytes', 'Description', 'Type')
    timer = has_timer(u)
    t = props(u + '.timer', 'NextElapseUSecRealtime', 'ActiveState') if timer else {}
    if u in fz: state = 'frozen'
    elif p.get('ActiveState') in ('active', 'activating', 'reloading'): state = 'running'
    elif p.get('ActiveState') == 'failed' or p.get('Result') not in ('success', '', None): state = 'failed'
    elif not p.get('ExecMainExitTimestamp') and not p.get('ExecMainStartTimestamp'): state = 'never'
    else: state = 'ok'
    reg, base = registry(u)
    persona = u.split('-')[0]
    if u in fz: nxt = 'paused by Medusa'
    elif timer: nxt = when(t.get('NextElapseUSecRealtime', '')) or 'paused'
    else: nxt = 'always on' if state == 'running' else 'manual'
    return dict(job=u, persona=persona, name=u[len(persona) + 1:], state=state,
                last=when(p.get('ExecMainExitTimestamp') or p.get('ExecMainStartTimestamp', '')) or '—',
                next=nxt, mem=hb(p.get('MemoryPeak')), wrote=hb(p.get('IOWriteBytes')),
                notes=reg.get('notes', '') or p.get('Description', ''), canfreeze=u not in NEVER_FREEZE, canrun=True,
                restarts=bolt_verb(timer, p.get('Type')) == 'restart',     # its button says Restart (always on) or Run: bolt()'s own choice
                frozen_at=fz.get(u, {}).get('at', ''), base=base if reg.get('transient') is True and base != u else '',
                started=started(p.get('ExecMainStartTimestamp', '')))

def collapse(jobs):
    """Transient units (registry "transient": true, e.g. zeus-deploy-<id>): one card per base name showing the latest run
    (a running one first), not one card per run. Its log is the latest run's; it can't be frozen or run again."""
    out, runs = [], {}
    for j in jobs: (runs.setdefault(j['base'], []) if j['base'] else out).append(j)
    for base, rs in runs.items():
        last = max(rs, key=lambda j: (j['state'] == 'running', j['started'], j['job']))
        out.append(dict(last, name=base[len(last['persona']) + 1:], runs=len(rs), canfreeze=False, canrun=False))
    return sorted(out, key=lambda j: (j['persona'], j['name']))

def links():
    try:
        with open(LINKS, encoding='utf-8') as f: raw = json.load(f)
    except (OSError, ValueError):
        return []
    out = []
    for x in raw if isinstance(raw, list) else []:
        if not isinstance(x, dict): continue
        name, what, href = str(x.get('name') or '').strip()[:40], str(x.get('what') or '').strip()[:40], str(x.get('href') or '').strip()
        if name and (re.fullmatch(r'/[\w./~%+-]*', href) and not href.startswith('//') or re.fullmatch(r'https://[^\s"\'<>]+', href)):
            out.append(dict(name=name, what=what, href=href))
    return out[:8]

WATCH_INTERVAL = int(os.environ.get('ARGUS_WATCH_INTERVAL', 60))   # seconds between rounds; 0 turns the loop off (the tests do, unless they ask)
WATCH_ON = os.environ.get('ARGUS_WATCH') != '0' and WATCH_INTERVAL > 0

def watch_restart(u):
    # the same restart the bolt uses (never for a frozen task), one at a time with the powers. LOCK is held only for this
    # one systemctl call (20 s limit); watch.py waits for the program to come back outside it, so the power buttons never wait on that.
    if u in frozen(): return False, 'frozen'
    with LOCK: return sc_ok('restart', '--no-block', u + '.service')

def watch_env():
    # the watch's own reading of `systemctl is-active`: activating / reloading / deactivating are "cannot tell yet" (watch.unit_state);
    # the task cards keep their own idea of running
    return watch.Env(lambda u: watch.unit_state(sc('is-active', u + '.service')), lambda u: u in frozen(), watch_restart)

def state(reach=None):
    fz = frozen()
    ws = watch.snapshot(WATCH_INTERVAL or 60)
    jobs = watch.attach(collapse([info(u, fz) for u in units()]), ws)
    ps = plugins()
    return dict(updated=datetime.now().strftime('%I:%M %p').lstrip('0'), jobs=jobs,
                title=THEME.get('title', 'Argus'), subtitle=THEME.get('subtitle', 'tasks'),
                personas=[dict(key=k, name=n, domain=d) for k, n, d in PERSONAS],
                soon=THEME.get('coming_soon', []), links=links(),
                plugins=[plugin_view(p, reach) for p in ps], watch=ws, watch_ready=not WATCH_ON or watch.ready(),   # until its first round: the saved rows
                alerts=sorted(alerts(set(PKEYS) | set(PAGES) | {p['id'] for p in ps}) + watch.alert_list(ws, lambda j: bool(GODS.match(j) and ALERT_JOB.match(j))), key=lambda a: (a['since'], a['file'])))

def state_for(who, people_problem=None, reach=None):
    """api/state (and the state inside the page) for this person. The owner gets everything, as before. A learner gets a
    list built from nothing (so a key added to state() later never leaks to her): her role and name, the plugins that open
    at least one path to learners and the agents they take over, the title, and empty lists for everything else (no tasks,
    alerts, links, watch rows or coming-later pills: nothing that names the owner's programs)."""
    me = {'role': who['role'], 'person': who['person'], 'name': who['name']}
    if who['role'] == 'owner': return dict(state(reach), **me, people_problem=people_problem)
    ps = [p for p in plugins() if p['kind'] == 'server' and p['learner']]
    ids = {p['id'] for p in ps}
    return dict(updated=datetime.now().strftime('%I:%M %p').lstrip('0'), jobs=[], watch=[], alerts=[], links=[], soon=[],
                title=THEME.get('title', 'Argus'), subtitle=THEME.get('subtitle', 'tasks'),
                personas=[dict(key=k, name=n, domain=d) for k, n, d in PERSONAS if k in ids],
                plugins=[plugin_view(p) for p in ps], **me)

def plugin_view(p, reach=None):
    # what the page needs about a plugin; a server plugin's script and style URLs carry their file times, so a redeploy is fetched fresh
    v = {k: p[k] for k in ('id', 'kind', 'name', 'subtitle', 'icon', 'version', 'agent')}
    if p['kind'] == 'server':
        for k in ('page', 'style'):
            try: v[k] = f"plugins/{p['id']}/{p[k]}?v={int(os.path.getmtime(os.path.join(p['dir'], p[k])))}" if p[k] else ''
            except OSError: v[k] = ''
    if p['kind'] == 'static' and p['id'] in OWN and reach in ('serve', 'here'):
        # its own address, only where this browser can reach it (H.own_reach): through Serve, https at the host name the
        # page was opened at with the public port; on this machine, http://127.0.0.1 with the local port. Elsewhere: the frame.
        c = OWN[p['id']]
        v['own'] = {'secure': reach == 'serve', 'port': c['public'] if reach == 'serve' else c['port'],
                    'links': [x for x in c['links'] if own_link_ok(p['dir'], x['path'])]}
    return v

def own_link_ok(d, rel):
    # a link of an own address is shown only while it points at a page inside the plugin (a file, or a folder with index.html)
    f = plugin_target(d, rel)[1]
    return bool(f) and os.path.basename(f) != 'plugin.json'

def plugin_target(d, rel):
    """(root, file) for a path inside plugin folder d: the file it serves, with every link resolved, or None when that is
    not a file inside the folder. A folder serves its index.html, and that name is resolved again after it is added, so an
    index.html that is a link to somewhere else leads nowhere."""
    root = os.path.realpath(d); f = os.path.realpath(os.path.join(root, rel))
    if os.path.isdir(f): f = os.path.realpath(os.path.join(f, 'index.html'))
    try: inside = os.path.commonpath([root, f]) == root
    except ValueError: inside = False                  # another drive (Windows)
    return root, (f if inside and os.path.isfile(f) else None)

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

def bolt_verb(timer, type_):
    # Zeus: a timer/oneshot agent gets Run (start); an always-on service gets Restart. One rule for the bolt and for api/state.
    return 'start' if timer or type_ == 'oneshot' else 'restart'

def bolt(u):
    # Frozen agents must be thawed first.
    if u in frozen(): return False, 'frozen - thaw it first'
    verb = bolt_verb(has_timer(u), props(u + '.service', 'Type').get('Type'))
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
def page(st):
    global PAGE
    if PAGE is None or os.environ.get('ARGUS_DEV'):
        PAGE = open(os.path.join(STATIC, 'index.html'), encoding='utf-8').read()
    # "</" is escaped so text from a unit's Description can never close the <script> tag
    return PAGE.replace('/*STATE*/null', json.dumps(st).replace('</', '<\\/'))

# Only answer to this machine's own names, IP addresses and Tailscale names (blocks DNS-rebinding attacks),
# plus anything listed in ARGUS_ALLOWED_HOSTS (comma separated).
_hn = socket.gethostname().lower()
ALLOWED = {'localhost', _hn, _hn.split('.')[0]} | {h.strip().lower() for h in os.environ.get('ARGUS_ALLOWED_HOSTS', '').split(',') if h.strip()}
def host_name(host):
    # a Host header without its port, lower case ('[::1]:8080' -> '::1')
    h = (host or '').strip().lower()
    if h.startswith('['): return h[1:h.find(']')]
    return h.rsplit(':', 1)[0] if h.count(':') == 1 else h

def host_ok(host):
    h = host_name(host)
    if h in ALLOWED or h.endswith('.ts.net') or h.endswith('.local'): return True
    try: ipaddress.ip_address(h); return True
    except ValueError: return False

def loopback(h):
    # the name localhost or a loopback address (an IPv4 one written as IPv6 too)
    if h.lower() == 'localhost': return True
    try: ip = ipaddress.ip_address(h)
    except ValueError: return False
    return ip.is_loopback or bool(getattr(ip, 'ipv4_mapped', None) and ip.ipv4_mapped.is_loopback)

PROTECT = {'X-Frame-Options': 'SAMEORIGIN', 'Content-Security-Policy': "frame-ancestors 'self'",   # on every answer that is
           'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'same-origin'}                # not a plugin file (those carry their own)
# A server plugin's files run inside Elaia's own page, so they need no CORS header; only a static plugin's sandboxed frame
# (an opaque origin) does. Identity here rides on the network path, not on a cookie: any web site open in the owner's
# browser can make it send a GET that carries his identity. What stops that site from READING the answer is the browser's
# same-origin rule, and "Access-Control-Allow-Origin: *" would give that away.
SERVER_FILE_HEADERS = {k: v for k, v in PLUGIN_HEADERS.items() if k != 'Access-Control-Allow-Origin'}
OPEN = {'api/health', 'api/whoami'}                       # anyone may ask these, also a person without a role

class NoCookies:
    """The request's reader while its header lines are read: every Cookie line is left out, whatever its length. Cookies
    belong to a host name, not a port, so a page on another port of the same name (a game on its own address, or any other
    service there) can set up to about a megabyte of them that the browser then sends here too. Argus reads no cookie, and
    the standard library refuses a header line over 64 KB (431), so without this one page could shut Elaia for that browser.
    Past CAP bytes of cookies the line comes back too long and the request is refused as before (431), so reading stays bounded."""
    CAP = 4 << 20

    def __init__(self, f): self.f, self.dropped, self.dropping = f, 0, False

    def readline(self, limit=-1):
        while True:
            line = self.f.readline(limit)
            # a Cookie line, or a folded continuation of one (a line that starts with a space or tab)
            if not (line[:7].lower() == b'cookie:' or (self.dropping and line[:1] in (b' ', b'\t'))):
                self.dropping = False
                return line
            self.dropping = True
            self.dropped += len(line)
            while line and not line.endswith(b'\n') and self.dropped <= self.CAP:     # the rest of a line longer than limit
                line = self.f.readline(limit); self.dropped += len(line)
            if self.dropped > self.CAP: return b'x' * (limit if limit and limit > 0 else 1 << 17)   # too long: 431
            if not line: return line                                                  # the connection ended

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def parse_request(self):
        # the header lines are read without their Cookie lines (NoCookies); everything else as the standard library does it
        real = self.rfile; self.rfile = NoCookies(real)
        try: return super().parse_request()
        finally: self.rfile = real

    def path_parts(self):
        p = self.path.split('?', 1)[0]
        if p.startswith('/argus'): p = p[6:]          # works whether or not Tailscale strips /argus
        return p.lstrip('/')

    def send_header(self, k, v):
        self._sent = getattr(self, '_sent', set()); self._sent.add(k.lower())
        super().send_header(k, v)

    def end_headers(self):
        # the protective headers (clickjacking, type sniffing, referrer) on every answer that is not a plugin file
        if not getattr(self, '_plugin_file', False):
            for k, v in PROTECT.items():
                if k.lower() not in getattr(self, '_sent', set()): self.send_header(k, v)
        super().end_headers()

    def out(self, body, ctype='text/html; charset=utf-8', code=200, cache='no-store', headers=None):
        b = body if isinstance(body, bytes) else body.encode()
        self.send_response(code)
        self.send_header('Content-Type', ctype); self.send_header('Content-Length', str(len(b)))
        for k, v in (headers or {}).items(): self.send_header(k, v)
        self.send_header('Cache-Control', cache); self.end_headers()
        if self.command != 'HEAD': self.wfile.write(b)          # HEAD: the same headers, no body (only an own address answers it)

    # ---------- who is asking (docs/people.md) ----------
    def identify(self):
        """Once per request: the login as sent, whether it came through Tailscale Serve, the person (who) and the people
        file's state. The login header counts only when the connection's other end belongs to the Serve user."""
        login = identity.header_value(self.headers.get('Tailscale-User-Login')) or None
        try: inode = os.fstat(self.connection.fileno()).st_ino or None     # our own end, to match in the tables (Linux)
        except (OSError, ValueError, AttributeError): inode = None
        try: uid = identity.connection_uid(self.client_address[:2], self.connection.getsockname()[:2], our_inode=inode)
        except (OSError, TypeError, ValueError): uid = None
        self.via_serve = SERVE_UID is not None and uid == SERVE_UID
        # through Serve, but sent from this machine itself (a program here using Serve's front door): no person
        self.from_self = self.via_serve and identity.from_this_machine(self.headers.get('X-Forwarded-For'))
        self.login, self.trusted = login, bool(self.via_serve and login and not self.from_self)
        self.people = PEOPLE.current()
        self.who = identity.resolve(self.people, login, self.trusted)

    def own_reach(self):
        """Where this browser can reach a plugin's own address (own-origin.json): 'serve' when the request came through
        tailscale serve (its HTTPS port at the same host name), 'here' when it came from this machine to a loopback name
        (the local port, which listens on 127.0.0.1 only), else None: from another device over plain http
        (ARGUS_BIND=0.0.0.0) the local port cannot be reached and the public one may not exist, so the frame stays."""
        if self.via_serve: return 'serve'
        return 'here' if loopback(str(self.client_address[0])) and loopback(host_name(self.headers.get('Host'))) else None

    def need(self, verb, p):
        """The role a route needs: 'none' (anyone), 'learner' or 'owner'. Everything is the owner's unless listed here or
        opened by a plugin's "roles" (docs/people.md has the table)."""
        pid, _, rest = p[4:].partition('/')
        if verb == 'post':
            return self.plugin_need(pid, 'post', rest) if p.startswith('api/') and pid in SERVER_PLUGINS else 'owner'
        if p in OPEN: return 'none'
        if p.startswith('api/'):
            if pid in SERVER_PLUGINS: return self.plugin_need(pid, 'get', rest)
            return 'learner' if p in ('api/state', 'api/sky') else 'owner'
        if p.startswith('plugins/'):                       # a plugin's files: open to a learner only if it opens a path to her
            fid = p[8:].split('/')[0]                     # only a loaded server plugin can open its files (PLUGIN_DIR)
            x = manifest(fid, PLUGIN_DIR[fid]) if fid in PLUGIN_DIR else None
            return 'learner' if x and x['kind'] == 'server' and x['learner'] else 'owner'
        return 'learner'                                   # the page itself (any address: the page sends her to Today) and its files

    def plugin_need(self, pid, verb, path):
        m = manifest(pid, PLUGIN_DIR[pid])                 # read fresh, like every manifest; a broken one opens nothing
        return 'learner' if m and m['roles'][verb].get(path) == 'learner' else 'owner'

    def refuse(self, verb, p, need):
        """403 with one plain sentence; a page address opened by someone without a role gets the small private page."""
        role = self.who['role']
        if role == 'none' and verb == 'get' and not p.startswith('api/'):
            html = identity.private_page(self.login, self.trusted, '../' * p.count('/') + 'api/whoami', self.from_self,
                                         closed=self.people[0] == 'broken')
            return self.out(html, code=403, headers={'Content-Security-Policy': identity.PRIVATE_CSP})
        if role == 'none' and self.people[0] == 'broken': msg = identity.CLOSED
        elif role == 'none':
            msg = (f'This page is private and {self.login} is not on its list of people. Ask the owner to add this Tailscale login.'
                   if self.trusted else 'This page is private, and a request from the server itself never counts as a person.'
                   if self.from_self else 'This page is private, and this request did not come through Tailscale, so the server cannot tell who you are.')
        else:
            msg = f'Only the owner of this page can {"do" if verb == "post" else "open"} this. You are signed in as {self.who["name"]}.'
        return self.out(json.dumps({'ok': False, 'error': msg, 'msg': msg}), 'application/json', 403)

    def whoami(self):
        problem = self.people[2] if self.who['role'] == 'owner' else identity.CLOSED if self.people[0] == 'broken' else None
        note = ('This request came from the server itself, so it has no person.' if self.from_self else
                'This request did not come through Tailscale Serve, so it has no person.' if not self.via_serve else
                'This request came through Tailscale Serve without a login (a tagged device), so it has no person.' if not self.login else None)
        return self.out(json.dumps({'login': self.login, 'trusted': self.trusted, 'through_serve': self.via_serve,
                                    'from_this_server': self.from_self, 'note': note,
                                    **self.who, 'problem': problem}), 'application/json')

    def plugin_file(self, rest):
        # plugins/<id>/<path>: files of a plugin, inside its folder only (same guard as static/).
        # A server plugin's Python side is never served, only its page script, style and whatever they load.
        self._plugin_file = True
        pid, _, sub = rest.partition('/')
        p = next((x for x in plugins() if x['id'] == pid), None)
        if not p: return self.out('not found', 'text/plain', 404)
        if '/' not in rest:                                   # plugins/<id> -> plugins/<id>/ so relative URLs resolve
            self.send_response(301); self.send_header('Location', self.path.split('?', 1)[0] + '/')
            self.send_header('Content-Length', '0'); self.end_headers(); return
        return self.send_plugin_file(p, sub, PLUGIN_HEADERS if p['kind'] == 'static' else SERVER_FILE_HEADERS)

    def send_plugin_file(self, p, sub, own):
        # one file of plugin p by its path inside the folder (sub; '' is the entry page), with the headers own: the
        # sandbox in Elaia (plugin_file), the plugin's own origin on its own address (OwnH). Nothing outside the folder.
        root, f = plugin_target(p['dir'], sub or p.get('entry', ''))     # resolved after index.html is added (a link there leads out)
        hidden = not f or os.path.basename(f) == 'plugin.json' or (p['kind'] == 'server' and (f.endswith(('.py', '.pyc')) or '__pycache__' in f))
        if hidden: return self.out('not found', 'text/plain', 404, headers=own)
        ct = mimetypes.guess_type(f)[0] or 'application/octet-stream'
        if ct.startswith('text/') or ct in ('application/json',): ct += '; charset=utf-8'
        with open(f, 'rb') as fh:
            st = os.fstat(fh.fileno())              # the file actually opened, so the ETag matches the bytes sent
            etag = f'"{st.st_mtime_ns:x}-{st.st_size:x}"'
            headers = {**own, 'ETag': etag, 'Last-Modified': formatdate(st.st_mtime, usegmt=True)}
            cache = plugin_cache(os.path.relpath(f, root).replace(os.sep, '/'))
            if not_modified(self.headers, etag, st.st_mtime):   # 304: no body, the same validators and sandbox headers
                self.send_response(304)
                for k, v in headers.items(): self.send_header(k, v)
                self.send_header('Cache-Control', cache); self.end_headers(); return
            return self.out(fh.read(), ct, cache=cache, headers=headers)

    # Request headers a server plugin may read (ctx.headers). They say who is asking only when the request came through
    # `tailscale serve` (the connection belongs to the Serve user); from anywhere else every one of them is dropped, so a
    # plugin is never handed a faked name. A plugin that decides on them still asks Janus (docs/leafy-plugin.md).
    PASS_HEADERS = ('Tailscale-User-Login', 'Tailscale-User-Name', 'X-Forwarded-For')
    TAKES_WHO = {}                                     # function -> True when it takes a fourth parameter (who)

    @classmethod
    def takes_who(cls, fn):
        """'kw' when fn has a parameter named who it can take by name (also keyword-only), 'pos' when it takes a fourth
        positional parameter, '' when it takes no who (an old plugin, called as before)."""
        if fn not in cls.TAKES_WHO:
            try:
                ps = inspect.signature(fn).parameters
                if 'who' in ps and ps['who'].kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY): way = 'kw'
                elif any(x.kind == x.VAR_POSITIONAL for x in ps.values()) or \
                        len([x for x in ps.values() if x.kind in (x.POSITIONAL_ONLY, x.POSITIONAL_OR_KEYWORD)]) >= 4: way = 'pos'
                else: way = ''
            except (TypeError, ValueError): way = ''
            cls.TAKES_WHO[fn] = way
        return cls.TAKES_WHO[fn]

    def plugin_call(self, pid, verb, path, arg):
        # api/<id>/<path> -> the plugin's get(path, query, ctx[, who]) or post(path, body, ctx[, who]), which answers (status, obj).
        # The role was checked before this; who is passed on every call to a function that takes it, never None.
        fn = getattr(SERVER_PLUGINS[pid], verb, None)
        ctx = plugin_ctx(pid, PLUGIN_DIR[pid])
        ctx.headers = {k: self.headers[k] for k in self.PASS_HEADERS if self.headers.get(k)} if self.via_serve and not self.from_self else {}
        r = None
        if callable(fn):
            way = self.takes_who(fn)
            args, kw = (path, arg, ctx) + ((dict(self.who),) if way == 'pos' else ()), ({'who': dict(self.who)} if way == 'kw' else {})
            try:
                if verb == 'post':
                    with PLUGIN_LOCKS[pid]: code, obj = fn(*args, **kw)
                else: code, obj = fn(*args, **kw)
                if not isinstance(code, int) or not 100 <= code <= 599: raise ValueError(f'status {code!r} is not an HTTP status')
                r = code, obj, json.dumps(obj)
            except Exception:
                print(f'argus-ui: server plugin {pid} failed on {verb.upper()} {path}\n{traceback.format_exc()}', file=sys.stderr, flush=True)
                if path != 'status': return self.deny(500, 'plugin error')
        if verb == 'get' and path == 'status':        # reserved: Home's line (+ needs, a verb-first action), or null; never an error
            d = r[1] if r and 200 <= r[0] < 300 and isinstance(r[1], dict) else {}
            line, act, n = d.get('line'), d.get('action'), d.get('count')
            out = {'line': str(line)[:160] if line else None, 'needs': bool(line) and d.get('needs') is True, 'action': str(act)[:32] if line and act else ''}
            if line and isinstance(n, int) and not isinstance(n, bool) and n >= 0: out['count'] = min(n, 9999)   # how many wait (the bar shows "2")
            return self.out(json.dumps(out), 'application/json')
        if not r: return self.deny(404, 'not found')
        self.out(r[2], 'application/json', r[0])

    def do_GET(self):
        self._plugin_file = False; self._sent = set()
        if not host_ok(self.headers.get('Host')): return self.out('unknown host', 'text/plain', 421)
        try:
            self.identify(); p = self.path_parts(); need = self.need('get', p)
            if not identity.allows(self.who['role'], need): return self.refuse('get', p, need)
            self.get()
        except Exception as e: self.out(json.dumps({'ok': False, 'msg': 'server error'}), 'application/json', 500)

    def get(self):
        p = self.path_parts()
        pid, _, rest = p[4:].partition('/')
        if p == 'api/health': return self.out(json.dumps(health()), 'application/json', cache='no-store')
        if p == 'api/whoami': return self.whoami()
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
        if p == 'api/state': return self.out(json.dumps(state_for(self.who, self.people[2], self.own_reach())), 'application/json')
        if p == 'api/sky': return self.out(json.dumps(sky.current()), 'application/json')
        if p == 'api/push/status':                          # the owner's (need()); never an endpoint or a key of a device
            return self.out(json.dumps(push.status(self.who, self.trusted, parse_qs(urlsplit(self.path).query).get('device', [''])[0])), 'application/json')
        if p == 'api/events': return self.events(parse_qs(urlsplit(self.path).query, keep_blank_values=True))   # the owner's (the role gate: every api/ route not listed)
        if p.startswith('api/log/'):
            u = p[8:]
            return self.out(json.dumps({'log': log(u) if u in units() else ''}), 'application/json')
        if p.startswith('plugins/'): return self.plugin_file(p[8:])
        first = p.split('/')[0]
        live = plugins(); ids = {x['id'] for x in live}
        moved = lambda old: MOVED.get(old) in ids and old not in ids       # the old id of a moved section, unless a plugin of yours has taken it
        if moved(first):                                                    # an old bookmark lands on the new address
            q = urlsplit(self.path).query                                   # relative, so it is right at /, at /argus/ and behind a proxy that strips the prefix
            self.send_response(302); self.send_header('Location', '../' * p.count('/') + MOVED[first] + ('?' + q if q else ''))
            self.send_header('Cache-Control', 'no-store'); self.send_header('Content-Length', '0'); self.end_headers(); return  # for now, and not remembered: the old id is free again later
        if p.startswith('api/') and moved(pid):                             # a page left open since before the move still asks the old api:
            name = next(x['name'] for x in live if x['id'] == MOVED[pid])   # it shows "problem" in place of its list and "line" on Home, both true
            return self.out(json.dumps({'ok': False, 'moved': MOVED[pid], 'line': f'Now called {name}: reload this page',
                                        'problem': f'This section is now called {name}. Reload this page to open it.'}), 'application/json')
        if p == '' or first in PKEYS or first in PAGES or first in ids: return self.out(page(state_for(self.who, self.people[2], self.own_reach())))
        return self.out('not found', 'text/plain', 404)

    EVENT_KEYS = ('id', 'at', 'kind', 'subject', 'title', 'body', 'url', 'level')

    def events(self, q):
        # api/events?limit=N: the newest events of the watch (notify.py), newest first, at most 100 (default 10). `since`: when the
        # server started, so an empty list can say "Nothing has happened since ...". Only the event's own fields go out, as text.
        raw = (q.get('limit') or ['10'])[0]
        if not (raw.isascii() and raw.isdigit() and 1 <= len(raw) <= 4): return self.deny(400, 'limit must be a whole number from 1 to 100')   # '²' is a digit to isdigit(), not to int()
        n = max(1, min(100, int(raw)))
        evs = [{k: str(e.get(k) or '') for k in self.EVENT_KEYS} for e in notify.read_events(n)]
        return self.out(json.dumps({'events': evs, 'since': STARTED.astimezone().isoformat(timespec='seconds')}), 'application/json')

    def watch_fix(self, body):
        # POST api/watch/fix {"id": "<check id>"}: the owner's yes from the page (docs/checks.md "Your yes from the page"). Only the
        # fix that checks.json declares for that check runs, through the watch's own repair(); no unit name is taken from the request.
        # Checked and queued under the powers' lock; the restart itself takes that lock again only for its one systemctl call.
        id_ = body.get('id')
        if not isinstance(id_, str) or not watch.ID.match(id_): return self.deny(400, 'There is no check with that name. Reload the page.')
        try:
            with LOCK: ok, code, msg = watch.ask_fix(id_, frozen(), WATCH_ON)
        except Exception: ok, code, msg = False, 500, 'Argus could not start the fix. Try again in a moment.'
        return self.out(json.dumps({'ok': ok, 'msg': msg}), 'application/json', code)

    def deny(self, code, msg): return self.out(json.dumps({'ok': False, 'msg': msg}), 'application/json', code)

    def do_POST(self):
        # Cross-site protection: right host, JSON only (a plain HTML form can't send it), and the browser must say the
        # request came from this page itself. Then the role (docs/people.md): every POST is the owner's unless a plugin opens it.
        self._plugin_file = False; self._sent = set()
        if not host_ok(self.headers.get('Host')): return self.deny(421, 'unknown host')
        if (self.headers.get('Content-Type') or '').split(';')[0].strip() != 'application/json': return self.deny(415, 'json only')
        site = self.headers.get('Sec-Fetch-Site'); origin = self.headers.get('Origin')
        if site and site not in ('same-origin', 'none'): return self.deny(403, 'cross-site request blocked')
        if origin and origin.split('://', 1)[-1] != self.headers.get('Host'): return self.deny(403, 'cross-site request blocked')
        p = self.path_parts()
        pid, _, rest = p[4:].partition('/')
        try: self.identify(); need = self.need('post', p)
        except Exception: return self.deny(500, 'server error')
        if not identity.allows(self.who['role'], need): return self.refuse('post', p, need)   # a closed page (people file broken, no good copy) ends here too
        try: n = int(self.headers.get('Content-Length', 0) or 0)
        except ValueError: n = -1
        limit = PLUGIN_BODY.get(pid, MAX_BODY) if p.startswith('api/') and pid in SERVER_PLUGINS else MAX_BODY
        if n < 0 or n > limit: return self.deny(413, 'request too large')
        try: body = json.loads(self.rfile.read(n) or b'{}')
        except Exception: return self.deny(400, 'bad json')
        if not isinstance(body, dict): return self.deny(400, 'bad json')
        if p.startswith('api/') and pid in SERVER_PLUGINS: return self.plugin_call(pid, 'post', rest, body)   # after every check above
        if p in ('api/push/subscribe', 'api/push/kinds', 'api/push/forget', 'api/push/test'):   # phone alerts, the owner's (need())
            try: code, obj = push.route(p[9:], body, self.who, self.trusted)
            except Exception: return self.deny(500, 'server error')
            return self.out(json.dumps(obj), 'application/json', code)
        if p == 'api/watch/fix': return self.watch_fix(body)
        u = str(body.get('job', ''))
        actions = {'api/freeze': freeze, 'api/thaw': thaw, 'api/bolt': bolt, 'api/run': bolt}
        if p not in actions: return self.deny(404, 'not found')
        if u not in units(): return self.deny(400, 'unknown task')
        try:
            with LOCK: ok, msg = actions[p](u)
        except subprocess.TimeoutExpired: ok, msg = False, 'systemctl timed out'
        except Exception: ok, msg = False, 'server error'
        self.out(json.dumps({'ok': ok, 'msg': msg}), 'application/json')

class OwnH(H):
    """A static plugin on its own address (own-origin.json): that one plugin's files at the root, to GET and HEAD only.
    The same host check, identity and role as opening plugins/<id>/ inside Elaia, the same caching, no API and no POST.
    No sandbox header: its own origin is the wall (OWN_HEADERS). start_own_origins() makes one subclass per plugin (pid)."""
    pid = ''

    def parse_request(self):
        # every method but GET and HEAD ends here, before any handler: 405, never a route
        if not super().parse_request(): return False
        self._plugin_file = True; self._sent = set()
        if self.command not in ('GET', 'HEAD'):
            self.close_connection = True
            self.out('method not allowed', 'text/plain; charset=utf-8', 405, headers={'Allow': 'GET, HEAD'})
            return False
        return True

    def end_headers(self):
        # the own origin's headers on every answer (errors and refusals too), never Elaia's PROTECT or the sandbox
        for k, v in OWN_HEADERS.items():
            if k.lower() not in getattr(self, '_sent', set()): self.send_header(k, v)
        BaseHTTPRequestHandler.end_headers(self)

    def refuse(self, verb, path, need):
        # the private page without its API link (there is none here), or one plain sentence for a learner
        if self.who['role'] == 'none':
            html = identity.private_page(self.login, self.trusted, None, self.from_self, closed=self.people[0] == 'broken')
            return self.out(html, code=403, headers={'Content-Security-Policy': identity.PRIVATE_CSP})
        return self.out(f'Only the owner of this page can open this. You are signed in as {self.who["name"]}.',
                        'text/plain; charset=utf-8', 403)

    def do_GET(self):
        self._plugin_file = True; self._sent = set()
        if not host_ok(self.headers.get('Host')): return self.out('unknown host', 'text/plain', 421)
        try:
            self.identify()
            raw = self.path.split('?', 1)[0].split('#', 1)[0]
            sub = unquote(raw[1:]) if raw.startswith('/') else None
            # only a plain path inside the folder: no .., no empty or backslash segment, no NUL, no drive (send_plugin_file checks again)
            if sub is None or sub.startswith('/') or '//' in sub or '\\' in sub or '\x00' in sub or '..' in sub.split('/') or os.path.splitdrive(sub)[0]:
                return self.out('not found', 'text/plain', 404)
            need = self.need('get', f'plugins/{self.pid}/{sub}')         # what Elaia asks for this plugin's files
            if not identity.allows(self.who['role'], need): return self.refuse('get', sub, need)
            plug = next((x for x in plugins() if x['id'] == self.pid and x['kind'] == 'static'), None)
            if not plug: return self.out('not found', 'text/plain', 404)
            root = os.path.realpath(plug['dir']); f = os.path.realpath(os.path.join(root, sub))
            if sub and not sub.endswith('/') and os.path.isdir(f) and os.path.commonpath([root, f]) == root:
                self.send_response(301); self.send_header('Location', '/' + quote(sub) + '/')   # frames -> frames/ so relative URLs resolve
                self.send_header('Content-Length', '0'); self.end_headers(); return
            return self.send_plugin_file(plug, sub, OWN_HEADERS)
        except Exception: self.out('server error', 'text/plain', 500)

    do_HEAD = do_GET

def start_own_origins(path=None):
    """One listener on 127.0.0.1 for each plugin in own-origin.json. One that cannot start is logged and skipped, and Elaia
    keeps the sandboxed frame for it. Returns {id: server} (the tests stop them)."""
    started, busy = {}, []
    for pid, c in load_own_origin(path).items():
        try: srv = ThreadingHTTPServer(('127.0.0.1', c['port']), type('OwnH_' + pid.replace('-', '_'), (OwnH,), {'pid': pid}))
        except OSError as e:
            print(f'argus-ui: {pid} gets no own address: its port cannot be used ({e.strerror or e})', file=sys.stderr, flush=True)
            busy.append((pid, c)); continue
        threading.Thread(target=srv.serve_forever, name='own-' + pid, daemon=True).start()
        OWN[pid] = c; started[pid] = srv
        print(f'argus-ui: {pid} has its own address (127.0.0.1:{c["port"]}, HTTPS port {c["public"]})', file=sys.stderr, flush=True)
    own_alert(busy)
    return started

OWN_ALERT = 'argus-own-origin.json'

def own_alert(busy):
    """A taken own port is loud: an alert file in ALERTS (docs/alerts.md), so Watch glares, because tailscale serve still
    forwards that plugin's HTTPS port to whatever holds the local one. A start where every own listener started (or there
    is no own-origin.json) takes this file away again. busy: [(id, entry)] whose port could not be used."""
    f = os.path.join(ALERTS, OWN_ALERT)
    try:
        if not busy:
            if os.path.exists(f): os.remove(f)
            return
        if len(busy) == 1:
            pid, c = busy[0]
            msg = (f'{pid} has no own address: port {c["port"]} was taken at start, so it opens in its frame, and tailscale serve still '
                   f'sends HTTPS port {c["public"]} to whatever holds it. Turn that off (sudo tailscale serve --https={c["public"]} off), '
                   'free the port, restart Argus, then publish the port again.')
        else:
            which = ', '.join(f"{pid} {c['port']}" for pid, c in busy)
            msg = (f'{len(busy)} plugins have no own address: their local ports were taken when Argus started ({which}), so they '
                   'open in their frames. Turn off their HTTPS ports on tailscale serve, free the ports, then restart Argus.')
        os.makedirs(ALERTS, exist_ok=True)
        tmp = f + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as fh:
            json.dump({'job': 'argus-own-origin', 'level': 'alert', 'since': datetime.now().astimezone().isoformat(timespec='seconds'),
                       'message': msg, 'link': busy[0][0]}, fh)
        os.replace(tmp, f)
    except OSError as e:
        print(f'argus-ui: could not {"write" if busy else "clear"} the alert file {f}: {e.strerror or e}', file=sys.stderr, flush=True)

if __name__ == '__main__':
    load_server_plugins()
    try: start_own_origins()                     # a mistake in own-origin.json never stops Argus: the frames stay
    except Exception: print(f'argus-ui: no plugin gets its own address:\n{traceback.format_exc()}', file=sys.stderr, flush=True)
    if WATCH_ON: watch.start(watch_env(), WATCH_INTERVAL)
    push.start(lambda person: push.role_in(PEOPLE.current(), person),      # phone alerts: owners' devices only (docs/phone-alerts.md)
               lambda s: next((w.get('title', '') for w in watch.snapshot(WATCH_INTERVAL or 60) if w.get('id') == s), ''))
    summary.start(lambda: watch.snapshot(WATCH_INTERVAL or 60))            # the daily summary, its own small thread
    ThreadingHTTPServer((BIND, PORT), H).serve_forever()
