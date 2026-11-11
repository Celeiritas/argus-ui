"""Who is asking (docs/people.md). Pure functions, standard library only; argus_ui.py calls them for every request.

1. Is the connection from Tailscale Serve?  `tailscale serve` adds `Tailscale-User-Login` to each request it passes on and
   removes a client's own copy. But any program on this machine can connect to the page's port directly and send that
   header itself. So the header counts only when the other end of the TCP connection belongs to the Serve process: the
   kernel's tables /proc/net/tcp and /proc/net/tcp6 list the owner (a user id) of every socket, and the row whose local end
   is our peer and whose remote end is our socket is the client's own socket. Its owner must be the Serve user: 0 (root,
   where tailscaled runs) unless ARGUS_SERVE_UID says otherwise. No /proc (Windows, macOS), no such row, an unreadable
   table, or another owner: the request has no identity.
2. Who is it?  ~/.config/argus-ui/people.json (ARGUS_PEOPLE gives another path):
       {"people": [{"id": "owner-one", "name": "Owner One", "role": "owner", "logins": ["owner@example.com"]}, ...]}
   No file: everyone is the one person {"person": "owner", "name": "You", "role": "owner"}, as before people existed.
   With a file: a trusted login that is listed is that person; anything else is role "none".
"""
import email.header, ipaddress, json, os, re, socket, sys, threading, time

ROLES = ('none', 'learner', 'owner')                 # each may do what the ones before it may
RANK = {r: i for i, r in enumerate(ROLES)}
YOU = {'person': 'owner', 'name': 'You', 'role': 'owner'}
NOBODY = {'person': None, 'name': None, 'role': 'none'}
ESTABLISHED = 1                                      # the "st" column of /proc/net/tcp: TCP_ESTABLISHED

# ---------- 1. the kernel's connection tables ----------

def _ip(h, byteorder):
    # the kernel prints an address as 32-bit words, each in the machine's own byte order (%08X of the in-memory value)
    if len(h) not in (8, 32): raise ValueError('not an address')
    raw = b''.join(int(h[i:i + 8], 16).to_bytes(4, byteorder) for i in range(0, len(h), 8))
    return norm(ipaddress.ip_address(raw))

def norm(ip):
    """An address as one comparable value: an IPv4 address seen through an IPv6 socket (::ffff:127.0.0.1) is the IPv4 one."""
    ip = ipaddress.ip_address(ip)
    return ip.ipv4_mapped if ip.version == 6 and ip.ipv4_mapped else ip

def _end(field, byteorder):
    h, port = field.split(':')
    return _ip(h, byteorder), int(port, 16)

def parse_table(text, byteorder=sys.byteorder):
    """The rows of /proc/net/tcp or /proc/net/tcp6: [{local: (ip, port), remote: (ip, port), state, uid, inode}].
    The heading and any line that does not parse are skipped."""
    rows = []
    for line in (text or '').splitlines():
        f = line.split()
        try:
            if len(f) < 10 or not f[0].endswith(':'): continue
            rows.append({'local': _end(f[1], byteorder), 'remote': _end(f[2], byteorder), 'state': int(f[3], 16),
                         'uid': int(f[7]), 'inode': int(f[9])})
        except (ValueError, IndexError):
            continue
    return rows

def owner_uid(rows, peer, ours, our_inode=None):
    """The user id that owns the client's end of the connection peer -> ours, or None when there is no such row.
    Only an ESTABLISHED row with a real socket behind it counts: a closed socket waiting out its last packets (TIME_WAIT,
    or FIN_WAIT2 after the client closed) is printed with user id 0 and inode 0, which would look like root.
    With our_inode (the inode of the socket this server holds), our own end must be in the same tables too, so a row left
    by an earlier connection on the same two ports can never be mistaken for this one."""
    want_l, want_r = (norm(peer[0]), int(peer[1])), (norm(ours[0]), int(ours[1]))
    live = lambda r: r['state'] == ESTABLISHED and r['inode'] != 0
    if our_inode is not None and not any(r['local'] == want_r and r['remote'] == want_l and live(r) and r['inode'] == our_inode for r in rows):
        return None
    for r in rows:
        if r['local'] == want_l and r['remote'] == want_r and live(r):
            return r['uid']
    return None

def connection_uid(peer, ours, proc='/proc', our_inode=None):
    """owner_uid() over this machine's own tables; None when they cannot be read (no /proc) or hold no such row."""
    rows = []
    for name in ('tcp', 'tcp6'):
        try:
            with open(os.path.join(proc, 'net', name), encoding='ascii', errors='replace') as f: rows += parse_table(f.read())
        except OSError:
            continue
    try: return owner_uid(rows, peer, ours, our_inode)
    except (ValueError, TypeError, IndexError): return None

def serve_uid(env=os.environ, own=None, log=None):
    """The user id Tailscale Serve's connections come from: ARGUS_SERVE_UID, else 0 (tailscaled runs as root).
    Never the page's own user: then every program of that user could claim any login. That value is refused (None: no
    connection counts as Serve's) with one loud log line, unless ARGUS_DEV is set (the tests run as their own Serve)."""
    try: uid = int(env.get('ARGUS_SERVE_UID', '0'))
    except ValueError: uid = 0
    own = own if own is not None else (os.getuid() if hasattr(os, 'getuid') else None)
    if uid == own and not env.get('ARGUS_DEV'):
        (log or (lambda m: print(f'argus-ui: {m}', file=sys.stderr, flush=True)))(
            f'ARGUS_SERVE_UID={uid} is the page\'s own user: then every program of yours could claim any Tailscale login. '
            'Ignored: no request has an identity until it names the user Tailscale Serve runs as (usually 0).')
        return None
    return uid

_own = {}                                            # address -> (is it this machine's, when we asked)

def is_own_address(ip, ttl=60):
    """True when ip is an address of this machine: loopback, unspecified, or one this machine can bind a socket to (the
    kernel only lets a program bind to its own addresses, the tailnet one included). Something that is not an address
    is not this machine's: a wrong guess must never lock out a phone."""
    try: ip = norm(str(ip).strip().strip('[]'))
    except ValueError: return False
    if ip.is_loopback or ip.is_unspecified: return True
    hit = _own.get(ip)
    if hit and time.monotonic() - hit[1] < ttl: return hit[0]
    try:
        with socket.socket(socket.AF_INET6 if ip.version == 6 else socket.AF_INET, socket.SOCK_STREAM) as sk:
            sk.bind((str(ip), 0)); mine = True
    except OSError: mine = False
    _own[ip] = (mine, time.monotonic())
    return mine

def from_this_machine(xff):
    """Serve sets X-Forwarded-For to the address that sent the request. When ANY address in it is this machine's own, a
    program here went in through Serve's front door and Serve stamped it with this machine's own login: it proves
    nobody's identity. No header, or entries that are not addresses, change nothing."""
    return any(is_own_address(x) for x in str(xff or '').split(',') if x.strip())

def header_value(v):
    """A Tailscale header as text: Serve sends non-ASCII values MIME-encoded (=?utf-8?q?...?=)."""
    v = str(v or '').strip()
    if v.startswith('=?'):
        try: v = str(email.header.make_header(email.header.decode_header(v)))
        except Exception: pass
    return v[:254]

# ---------- 2. the people file ----------

def ident(s):
    """A person's id: lower case, letters a-z and digits kept, every run of anything else one "-" (Mentor's rule, so the
    two agree on who is who)."""
    return re.sub(r'[^a-z0-9]+', '-', str(s or '').lower()).strip('-')[:40]

def shown(path, home=None):
    """A path as a sentence may name it: ~/... for one under the home folder (never the user's name in a public answer)."""
    home = home or os.path.expanduser('~')
    return '~' + path[len(home):].replace(os.sep, '/') if home and path.startswith(home + os.sep) else path

def parse_people(doc):
    """The people of a parsed file, or ValueError with the reason in plain words. Strict on purpose: a typo must not
    quietly change what someone may do, so anything unclear makes the whole file unusable (the last good copy is kept).
    The reason names entries by number, never a login or a name: the sentence may be shown to whoever is asking."""
    rows = doc.get('people') if isinstance(doc, dict) else None
    if not isinstance(rows, list): raise ValueError('it has no "people" list')
    out, ids, logins = [], {}, {}                # ids and logins -> the number of the entry that has them
    for n, p in enumerate(rows, 1):
        if not isinstance(p, dict): raise ValueError(f'entry {n} is not an object')
        name = str(p.get('name') or '').strip()
        if not name: raise ValueError(f'entry {n} has no name')
        if p.get('role') not in ('owner', 'learner'): raise ValueError(f'entry {n} has a role that is not "owner" or "learner"')
        pid = ident(p.get('id') or name)
        if not pid: raise ValueError(f'entry {n} has no usable id')
        if pid in ids: raise ValueError(f'entry {n} uses the id of entry {ids[pid]}')
        ls = p.get('logins', [])
        if not isinstance(ls, list) or not all(isinstance(x, str) and x.strip() for x in ls): raise ValueError(f'the logins of entry {n} are not a list of names')
        mine = {x.strip().lower() for x in ls}
        for x in mine:
            if x in logins: raise ValueError(f'entry {n} repeats a login of entry {logins[x]}')
            logins[x] = n
        ids[pid] = n; out.append({'person': pid, 'name': name[:60], 'role': p['role'], 'logins': sorted(mine)})
    if not any(p['role'] == 'owner' for p in out): raise ValueError('it names no owner')
    if not any(p['role'] == 'owner' and p['logins'] for p in out): raise ValueError('no owner has a login, so nobody could open the page as the owner')
    return out

def _why(e):
    """An error as a short reason that never carries a path (an OSError's own text names the file, and so the home folder)."""
    if isinstance(e, OSError): return (e.strerror or type(e).__name__).lower()
    if isinstance(e, RecursionError): return 'it is nested too deeply'
    return (str(e).split('\n')[0][:200]) or type(e).__name__

class People:
    """The people file as the server uses it, read again whenever it changes on disk (no restart).
    mode: 'absent' (no file: everyone is YOU), 'ok', 'stale' (broken now, the last good copy is used) or 'broken'
    (broken and no good copy known: closed, nobody is a person; the detail goes to the log only).
    Each good read is also saved to `last_good` (~/.local/state/argus-ui/people.last-good.json, mode 600), so a restart or
    a deploy with a broken file still has the last good copy: only a file that was never good can be 'broken'."""
    def __init__(self, path, log=None, last_good=None, must_exist=False):
        # must_exist: the path was set on purpose (ARGUS_PEOPLE), so somebody meant a file to be there: missing = broken
        self.path, self.last_good, self.must_exist = path, last_good, must_exist
        self.log = log or (lambda m: print(f'argus-ui: {m}', file=sys.stderr, flush=True))
        self.lock, self.key = threading.Lock(), ()       # () = never looked
        self.mode, self.problem, self._told = 'absent', None, set()
        self.good = self._load_saved()

    def _load_saved(self):
        if not self.last_good: return None
        try:
            with open(self.last_good, encoding='utf-8') as f: return parse_people(json.load(f))
        except FileNotFoundError: return None
        except Exception as e:
            self.log(f'the saved copy of the people file {self.last_good} is not used: {_why(e)}'); return None

    def _save(self, raw):
        # the bytes of the last good file, written atomically, for this user only; a failure is logged, never fatal
        if not self.last_good: return
        try:
            try:
                with open(self.last_good, 'rb') as f:
                    if f.read() == raw: return
            except OSError: pass
            os.makedirs(os.path.dirname(self.last_good) or '.', exist_ok=True)
            tmp = self.last_good + '.tmp'
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, 'wb') as f: f.write(raw)
            os.replace(tmp, self.last_good)
        except OSError as e:
            self.log(f'could not save the last good people file to {self.last_good}: {_why(e)}')

    def current(self):
        """(mode, people or None, problem sentence or None), up to date with the file."""
        try: st = os.stat(self.path); key = (st.st_mtime_ns, st.st_size, st.st_ino)
        except FileNotFoundError:
            # a link whose target is gone (an unmounted drive, a moved folder) is a broken file, never "no file"
            key = ('dangling',) if os.path.lexists(self.path) else ('missing',) if self.must_exist else None
        except OSError as e: key = ('error', _why(e))
        with self.lock:
            if key != self.key:
                self.key = key
                try: self._read(key)
                except Exception as e: self._broken(key, e)      # never leave the old mode standing after a failed read
            return self.mode, (self.good if self.mode in ('ok', 'stale') else None), self.problem

    def _read(self, key):
        if key is None:                                   # no file (or it was taken away): today's behaviour again
            self.mode, self.problem = 'absent', None; return
        try:
            if key == ('dangling',): raise ValueError('it is a link to a file that is not there')
            if key == ('missing',): raise ValueError('it is not there, but ARGUS_PEOPLE names it')
            if key[0] == 'error': raise ValueError(key[1])
            with open(self.path, 'rb') as f: raw = f.read()
            people = parse_people(json.loads(raw.decode('utf-8')))
        except FileNotFoundError:
            self.mode, self.problem = 'absent', None; return
        except Exception as e:                            # anything at all makes the file unusable; never a crash
            return self._broken(key, e)
        self.good, self.mode, self.problem = people, 'ok', None
        self._save(raw)

    def _broken(self, key, e):
        why, where = _why(e), shown(self.path)
        if self.good is not None:
            self.mode = 'stale'
            self.problem = f'The people file {where} cannot be used ({why}). The page keeps the last good copy until you fix it.'
        else:
            self.mode = 'broken'
            self.problem = f'The people file {where} cannot be used ({why}). The page is closed to everyone until it is fixed.'
        if (key, why) not in self._told:
            self._told.add((key, why))
            self.log(f'people file {self.path}: {why} ({"kept the last good copy" if self.mode == "stale" else "no good copy known: the page is closed to everyone"})')

def resolve(people_state, login, trusted):
    """who = {person, name, role} for a request. people_state is People.current()."""
    mode, people, _ = people_state
    if mode == 'absent': return dict(YOU)                 # no file: everyone is the owner, as before people existed
    if mode == 'broken': return dict(NOBODY)              # unusable and no good copy known: closed (the hub's decision)
    if trusted and login:
        l = login.strip().lower()
        for p in people:
            if l in p['logins']: return {'person': p['person'], 'name': p['name'], 'role': p['role']}
    return dict(NOBODY)

def allows(role, need):
    """True when role may reach something that needs `need` ('none' = anyone, 'learner', 'owner')."""
    return RANK.get(role, 0) >= RANK.get(need, 2)

def plugin_roles(manifest_roles):
    """A plugin's "roles" from plugin.json, cleaned: {'get': {path: 'learner'}, 'post': {...}}. Only "learner" opens a path;
    anything else (missing, "owner", a typo) leaves it to the owner."""
    out = {'get': {}, 'post': {}}
    if not isinstance(manifest_roles, dict): return out
    for verb in out:
        d = manifest_roles.get(verb)
        if isinstance(d, dict):
            out[verb] = {str(k): 'learner' for k, v in d.items() if isinstance(k, str) and v == 'learner'}
    return out

# ---------- 3. the page a stranger gets ----------

def _esc(s):
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&#39;')

PRIVATE_CSP = "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'self'; base-uri 'none'; form-action 'none'"

CLOSED = ('The list of people this page uses cannot be read, so the page is closed to everyone for now. '
          'If you are the owner: on the server, move the people file aside to a dated name; the page then works as it '
          'did before the file existed.')

def private_page(login, trusted, whoami_href='api/whoami', from_self=False, closed=False):
    """The small page a person without a role gets at any page address: no script, nothing loaded from elsewhere."""
    if from_self:
        seen = ('<p>This request came from the server itself, through its own Tailscale address. A program on the server '
                'cannot use the page as a person, so the server does not count the login it carries.</p>'
                '<p>Open the page from your phone or computer instead.</p>')
    elif trusted and login:
        seen = (f'<p>Tailscale says you are signed in as <b class="login">{_esc(login)}</b>. That login is not on this page\'s list of people.</p>'
                '<p>If you should be able to use it, ask the owner to add this login to the people file on the server. '
                'Then reload this page.</p>')
    else:
        seen = ('<p>This request did not come through Tailscale, so the server cannot tell who you are.</p>'
                '<p>Open the page from a device signed in to Tailscale, at its https address on your tailnet. '
                'If you are already doing that and you are the owner, see "Locked out" in the page\'s docs (docs/people.md).</p>')
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark"><title>This page is private</title>
<style>
:root {{ --bg: #F4F1EA; --card: #FFFFFF; --ink: #1C2127; --soft: #4A5560; --line: #C9C2B4; --accent: #1F6F66; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg: #14181C; --card: #1C2127; --ink: #E8EDF2; --soft: #A7B6C4; --line: #33404C; --accent: #6CC4B8; }} }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 16px;
  background: var(--bg); color: var(--ink); font: 400 16px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }}
main {{ max-width: 32rem; width: 100%; background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 24px; }}
h1 {{ font-size: 16px; font-weight: 600; margin: 0 0 12px; }}
p {{ margin: 0 0 12px; }}
.login {{ font-weight: 600; overflow-wrap: anywhere; }}
.small, .owner {{ font-size: 14px; color: var(--soft); margin: 16px 0 0; }}
.owner {{ color: var(--ink); }}
a {{ color: var(--accent); display: inline-block; min-height: 44px; line-height: 44px; }}
a:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
</style></head>
<body><main>
<h1>This page is private</h1>
{seen}
<p class="owner">{_esc(CLOSED) if closed else 'If you are the owner and this is your own device: on the server, move the people file aside to a dated name, and the page opens for you again at once.'}</p>
<p class="small"><a href="{_esc(whoami_href)}">Show what the server sees</a></p>
</main></body></html>
'''
