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
import email.header, ipaddress, json, os, re, sys, threading

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

def owner_uid(rows, peer, ours):
    """The user id that owns the client's end of the connection peer -> ours, or None when there is no such row.
    Only an ESTABLISHED row with a real socket behind it counts: a closed socket waiting out its last packets (TIME_WAIT,
    or FIN_WAIT2 after the client closed) is printed with user id 0 and inode 0, which would look like root."""
    want_l, want_r = (norm(peer[0]), int(peer[1])), (norm(ours[0]), int(ours[1]))
    for r in rows:
        if r['local'] == want_l and r['remote'] == want_r and r['state'] == ESTABLISHED and r['inode'] != 0:
            return r['uid']
    return None

def connection_uid(peer, ours, proc='/proc'):
    """owner_uid() over this machine's own tables; None when they cannot be read (no /proc) or hold no such row."""
    rows = []
    for name in ('tcp', 'tcp6'):
        try:
            with open(os.path.join(proc, 'net', name), encoding='ascii', errors='replace') as f: rows += parse_table(f.read())
        except OSError:
            continue
    try: return owner_uid(rows, peer, ours)
    except (ValueError, TypeError, IndexError): return None

def serve_uid(env=os.environ):
    """The user id Tailscale Serve's connections come from: ARGUS_SERVE_UID, else 0 (tailscaled runs as root)."""
    try: return int(env.get('ARGUS_SERVE_UID', '0'))
    except ValueError: return 0

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
    quietly change what someone may do, so anything unclear makes the whole file unusable (the last good copy is kept)."""
    rows = doc.get('people') if isinstance(doc, dict) else None
    if not isinstance(rows, list): raise ValueError('it has no "people" list')
    out, ids, logins = [], set(), {}
    for n, p in enumerate(rows, 1):
        if not isinstance(p, dict): raise ValueError(f'entry {n} is not an object')
        name = str(p.get('name') or '').strip()
        if not name: raise ValueError(f'entry {n} has no name')
        if p.get('role') not in ('owner', 'learner'): raise ValueError(f'{name} has the role {p.get("role")!r}; it must be "owner" or "learner"')
        pid = ident(p.get('id') or name)
        if not pid: raise ValueError(f'{name} has no usable id')
        if pid in ids: raise ValueError(f'the id "{pid}" is used twice')
        ls = p.get('logins', [])
        if not isinstance(ls, list) or not all(isinstance(x, str) and x.strip() for x in ls): raise ValueError(f'the logins of {name} are not a list of names')
        mine = {x.strip().lower() for x in ls}
        for x in mine:
            if x in logins: raise ValueError(f'the login {x} is listed under both {logins[x]} and {name}')
            logins[x] = name
        ids.add(pid); out.append({'person': pid, 'name': name[:60], 'role': p['role'], 'logins': sorted(mine)})
    if not any(p['role'] == 'owner' for p in out): raise ValueError('it names no owner')
    return out

class People:
    """The people file as the server uses it, read again whenever it changes on disk (no restart).
    mode: 'absent' (no file: everyone is YOU), 'ok', 'stale' (broken now, the last good copy is used) or 'broken'
    (broken and never read well since it appeared: viewing as if there were no file, every POST refused)."""
    def __init__(self, path, log=None):
        self.path = path
        self.log = log or (lambda m: print(f'argus-ui: {m}', file=sys.stderr, flush=True))
        self.lock, self.key = threading.Lock(), ()       # () = never looked
        self.good, self.mode, self.problem, self._told = None, 'absent', None, set()

    def current(self):
        """(mode, people or None, problem sentence or None), up to date with the file."""
        try: st = os.stat(self.path); key = (st.st_mtime_ns, st.st_size, st.st_ino)
        except FileNotFoundError: key = None
        except OSError as e: key = ('error', str(e))
        with self.lock:
            if key != self.key:
                self.key = key; self._read(key)
            return self.mode, self.good, self.problem

    def _read(self, key):
        if key is None:                                   # no file (or it was taken away): today's behaviour again
            self.good, self.mode, self.problem = None, 'absent', None; return
        try:
            with open(self.path, encoding='utf-8') as f: people = parse_people(json.load(f))
        except FileNotFoundError:
            self.good, self.mode, self.problem = None, 'absent', None; return
        except (OSError, ValueError, TypeError) as e:
            why = str(e).split('\n')[0][:200]
            where = shown(self.path)
            if self.good is not None:
                self.mode = 'stale'
                self.problem = f'The people file {where} cannot be used ({why}). The page keeps the last good copy until you fix it.'
            else:
                self.mode = 'broken'
                self.problem = f'The people file {where} cannot be used ({why}). Until it is fixed, nothing on this page can be changed.'
            if (key, why) not in self._told:
                self._told.add((key, why)); self.log(f'people file {self.path}: {why} ({"kept the last good copy" if self.mode == "stale" else "every POST is refused"})')
            return
        self.good, self.mode, self.problem = people, 'ok', None

def resolve(people_state, login, trusted):
    """who = {person, name, role} for a request. people_state is People.current()."""
    mode, people, _ = people_state
    if mode in ('absent', 'broken'): return dict(YOU)     # no usable file: everyone is the owner, as before people existed
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

def private_page(login, trusted, whoami_href='api/whoami'):
    """The small page a person without a role gets at any page address: no script, nothing loaded from elsewhere."""
    if trusted and login:
        seen = (f'<p>Tailscale says you are signed in as <b class="login">{_esc(login)}</b>. That login is not on this page\'s list of people.</p>'
                '<p>If you should be able to use it, ask the owner to add this login to the people file on the server. '
                'Then reload this page.</p>')
    else:
        seen = ('<p>This request did not come through Tailscale, so the server cannot tell who you are.</p>'
                '<p>Open the page from a device signed in to Tailscale, at its https address on your tailnet. '
                'If you are already doing that, ask the owner: the server may need to be told which program passes Tailscale\'s requests on.</p>')
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
.small {{ font-size: 14px; color: var(--soft); margin: 16px 0 0; }}
a {{ color: var(--accent); display: inline-block; min-height: 44px; line-height: 44px; }}
a:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
</style></head>
<body><main>
<h1>This page is private</h1>
{seen}
<p class="small">The owner can see what the server sees for any device here: <a href="{_esc(whoami_href)}">Show what the server sees</a></p>
</main></body></html>
'''
