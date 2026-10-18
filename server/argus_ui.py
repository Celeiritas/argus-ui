#!/usr/bin/env python3
# Argus UI - a small web page that watches your systemd --user services ("tasks"), grouped by "agent".
#   Open it at http://<host>:8095, or anywhere on your tailnet with:  tailscale serve --bg --set-path /argus http://127.0.0.1:8095
# Powers on the page: Medusa freezes/thaws a task (stop + pause its timer; thaw restores it), Zeus's bolt runs/restarts it.
# Which agents exist, their names and the page title come from the theme (static/theme.json).
import json, os, re, subprocess, time, mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime

PORT = int(os.environ.get('ARGUS_PORT', 8095))
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
    return subprocess.run(a, capture_output=True, text=True).stdout

def sc(*a):
    return run(SYSTEMCTL, '--user', *a)

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

def frozen():
    try: return json.load(open(FROZEN))
    except Exception: return {}

def save_frozen(d):
    os.makedirs(REG, exist_ok=True)
    json.dump(d, open(FROZEN, 'w'), indent=2)

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
    if timer:
        sc('stop', u + '.timer')
        if rec['timer_enabled']: sc('disable', u + '.timer')
    sc('stop', u + '.service')
    if rec['service_enabled']: sc('disable', u + '.service')
    fz[u] = rec; save_frozen(fz)
    return True, 'frozen'

def bolt(u):
    # Zeus: a timer/oneshot agent gets Run; an always-on service gets Restart. Frozen agents must be thawed first.
    if u in frozen(): return False, 'frozen - thaw it first'
    if has_timer(u) or props(u + '.service', 'Type').get('Type') == 'oneshot':
        subprocess.Popen([SYSTEMCTL, '--user', 'start', '--no-block', u + '.service']); return True, 'struck - running now'
    subprocess.Popen([SYSTEMCTL, '--user', 'restart', '--no-block', u + '.service']); return True, 'struck - restarted'

def thaw(u):
    fz = frozen()
    rec = fz.get(u)
    if not rec: return True, 'not frozen'
    if rec.get('service_enabled'): sc('enable', u + '.service')
    if rec.get('timer'):
        if rec.get('timer_enabled'): sc('enable', '--now', u + '.timer')
        else: sc('start', u + '.timer')
    elif rec.get('service_active') or rec.get('service_enabled'):
        sc('start', '--no-block', u + '.service')
    del fz[u]; save_frozen(fz)
    return True, 'thawed'

PAGE = None
def page():
    global PAGE
    if PAGE is None or os.environ.get('ARGUS_DEV'):
        PAGE = open(os.path.join(STATIC, 'index.html'), encoding='utf-8').read()
    return PAGE.replace('/*STATE*/null', json.dumps(state()))

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
        p = self.path_parts()
        if p.startswith('static/'):
            f = os.path.normpath(os.path.join(STATIC, p[7:]))
            if not f.startswith(os.path.normpath(STATIC)) or not os.path.isfile(f): return self.out('not found', 'text/plain', 404)
            ct = mimetypes.guess_type(f)[0] or 'application/octet-stream'
            if f.endswith('.webmanifest'): ct = 'application/manifest+json'
            return self.out(open(f, 'rb').read(), ct, cache='max-age=300')
        if p in ('manifest.webmanifest', 'sw.js'):
            f = os.path.join(STATIC, p)
            return self.out(open(f, 'rb').read(), 'application/manifest+json' if p.endswith('manifest') else 'text/javascript')
        if p == 'api/state': return self.out(json.dumps(state()), 'application/json')
        if p.startswith('api/log/'):
            u = p[8:]
            return self.out(json.dumps({'log': log(u) if u in units() else ''}), 'application/json')
        if p == '' or p.split('/')[0] in PKEYS: return self.out(page())
        return self.out('not found', 'text/plain', 404)

    def do_POST(self):
        p = self.path_parts()
        n = int(self.headers.get('Content-Length', 0) or 0)
        try: body = json.loads(self.rfile.read(n) or b'{}')
        except Exception: body = {}
        u = str(body.get('job', ''))
        if u not in units(): return self.out(json.dumps({'ok': False, 'msg': 'unknown agent'}), 'application/json', 400)
        if p == 'api/run':
            if u in frozen(): return self.out(json.dumps({'ok': False, 'msg': 'frozen - thaw it first'}), 'application/json')
            subprocess.Popen([SYSTEMCTL, '--user', 'start', '--no-block', u + '.service'])
            ok, msg = True, 'started'
        elif p == 'api/freeze': ok, msg = freeze(u)
        elif p == 'api/thaw': ok, msg = thaw(u)
        elif p == 'api/bolt': ok, msg = bolt(u)
        else: return self.out('not found', 'text/plain', 404)
        self.out(json.dumps({'ok': ok, 'msg': msg}), 'application/json')

if __name__ == '__main__':
    ThreadingHTTPServer(('0.0.0.0', PORT), H).serve_forever()
