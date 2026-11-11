"""Who is studying (docs/mentor.md, "People"): the people file, and which person's database a request reads and writes.

The people file is ONE file on the host, outside git: ~/.config/argus-ui/people.json (ARGUS_PEOPLE gives another path).
    {"people": [{"id": "owner-one", "name": "Owner One", "role": "owner", "logins": ["owner@example.com"]},
                {"id": "learner-two", "name": "Learner Two", "role": "learner", "logins": ["learner@example.com"]}]}
`id` is optional (the name in lower case, every run of other characters one "-"); `role` is owner or learner.
No file: one person, the owner ("You"), as before people existed. A file that is not JSON: read as "no file", one log
line, and every POST is refused with a sentence that names the file (fail closed for actions).

The server tells a plugin who is asking with `who` = {"person", "name", "role"} (None: not told, which means the owner, as
before). A learner always studies as themself; an owner may study as any person in the file by sending learner=<id>.
Standard library only; the file is read again when it changes.
"""
import json, os, re, sys

# the path exactly as the server reads it (server/argus_ui.py): ARGUS_PEOPLE when set and not empty, else the default.
# When ARGUS_PEOPLE names a file, that file must be there: missing, it is unusable (the server keeps its last good copy
# and still names people), never "no people file". A link whose target is gone is unusable the same way (4.38, R4b F1).
FILE = os.path.expanduser(os.environ.get('ARGUS_PEOPLE') or '~/.config/argus-ui/people.json')
MUST_EXIST = bool(os.environ.get('ARGUS_PEOPLE'))
YOU = {'id': 'owner', 'name': 'You', 'role': 'owner'}
# what a learner reads when the people file cannot be used: never a path on the server (4.38, R4b S-b)
GENERAL = 'The list of people cannot be read right now. Ask the owner.'
_cache = [None, None]               # (mtime, size) when last read, and (people, problem)
_told = set()

class Refused(Exception):
    """A request Mentor will not answer for this person: .code is the HTTP status, str() the sentence to show."""
    def __init__(self, code, msg):
        super().__init__(msg); self.code = code

def ident(s):
    """A person's id: lower case, letters a-z and digits kept, every run of anything else one "-" (safe in a file name)."""
    return re.sub(r'[^a-z0-9]+', '-', str(s or '').lower()).strip('-')[:40]

def shown(path, home=None):
    """A path as a sentence may name it: ~/... under the home folder (the server's identity.shown())."""
    home, path = os.path.normpath(home or os.path.expanduser('~')), os.path.normpath(path)
    return '~' + path[len(home):].replace(os.sep, '/') if home and path.startswith(home + os.sep) else path

def log_once(msg):
    if msg not in _told:
        _told.add(msg); print(f'argus-ui: mentor people: {msg}', file=sys.stderr, flush=True)

def _read():
    """(people, problem). people: a list of {id, name, role, logins}; problem: '' or why the file was not used."""
    try:
        with open(FILE, encoding='utf-8') as f: doc = json.load(f)
        rows = doc.get('people') if isinstance(doc, dict) else None
        if not isinstance(rows, list): raise ValueError('it has no "people" list')
        # fail closed (4.38), as strict as the server's own reader: one bad entry makes the whole file unusable
        out, seen = [], set()
        for i, p in enumerate(rows, 1):
            if not isinstance(p, dict): raise ValueError(f'entry {i} is not an object')
            if not isinstance(p.get('name'), str) or not p['name'].strip(): raise ValueError(f'entry {i} has no name')
            pid = ident(p.get('id') or p['name'])
            if not pid: raise ValueError(f'entry {i} ({p["name"].strip()[:60]}) has no usable id')
            if pid in seen: raise ValueError(f'the id "{pid}" is used twice')
            if p.get('role') not in ('owner', 'learner'): raise ValueError(f'entry {i} ({p["name"].strip()[:60]}) has the role {p.get("role")!r}, not owner or learner')
            lg = p.get('logins', [])
            if not isinstance(lg, list) or not all(isinstance(x, str) and x.strip() for x in lg): raise ValueError(f'entry {i} ({p["name"].strip()[:60]}) has logins that are not a list of names')
            seen.add(pid)
            out.append({'id': pid, 'name': p['name'].strip()[:60], 'role': p['role'], 'logins': [x.strip().lower() for x in lg]})
        if not any(p['role'] == 'owner' for p in out): raise ValueError('it names no owner')
        return out, ''
    except FileNotFoundError:
        if not MUST_EXIST and not os.path.islink(FILE): return [dict(YOU, logins=[])], ''      # truly no people file
        e = 'it is not there' + (' (a link whose target is gone)' if os.path.islink(FILE) else '')
    except RecursionError: e = 'it is nested too deeply'      # as the server's reader: unusable, not an error for everyone
    except (OSError, ValueError, TypeError) as x: e = str(x)
    log_once(f'{FILE}: {e} (read as "no file"; changes are refused until it is fixed)')
    return [dict(YOU, logins=[])], f'{shown(FILE)} cannot be read ({e}). Fix it on the server, then try again.'

def people():
    """Every person, and the problem with the file ('' when it is fine or absent). Read again when the file changes."""
    try: st = os.stat(FILE); key = (st.st_mtime, st.st_size)
    except OSError: key = None
    if _cache[0] != key or _cache[1] is None: _cache[:] = [key, _read()]
    return _cache[1]

def owner_id():
    """The first owner in the file (mentor.db goes to them when it does not say whose it is: plugin.holder())."""
    return next(p['id'] for p in people()[0] if p['role'] == 'owner')

def from_file():
    """True when a people file was read; False with no file or a file that cannot be read (one person: the owner)."""
    return not people()[1] and os.path.isfile(FILE)

def find(pid):
    return next((p for p in people()[0] if p['id'] == pid), None)

def studying(who, requested=None, write=False, holder=None, stored=None):
    """The person whose lessons and progress this request reads or writes: {id, name, role, owner_db}. A learner is always
    themself; an owner (or a request the server told nothing about: who is None) may name anyone with `requested`.
    holder: whose history mentor.db is (plugin.holder(); None = the first owner, or the one person when there is no file).
    The role comes from the people file Mentor reads itself, never from `who` alone: a person the file does not know is
    refused, and the smaller of the two roles counts (4.38). With no people file every `who` but role none is the owner.
    Mentor never decides by itself that someone is the owner (4.38, R4b F1): when the server names a person and Mentor has
    no usable people file (missing where ARGUS_PEOPLE points, a dead link, unreadable), a learner is refused, and an owner
    is let in only as the person mentor.db belongs to (`stored`, the id written in it); anybody else is refused too.
    Raises Refused: 403 for nobody (role none) or a stranger, 404 for an id that is not in the file, 503 while the file
    cannot be used (a learner reads a general sentence, never a path)."""
    ps, problem = people()
    role = who.get('role') if isinstance(who, dict) else None
    if who is not None and role not in ('owner', 'learner'): raise Refused(403, 'Mentor is only for the people in the people file. Ask the owner to add you.')
    if problem and (role == 'learner' or write): raise Refused(503, GENERAL if role == 'learner' else problem)
    first = holder or owner_id()        # whose mentor.db is; nobody's while that id is not in the file (two owners, plugin.holder())
    if who is None: me = find(first) or find(owner_id())              # not told: the owner, as before people existed
    else:
        if not from_file():
            if role == 'learner': raise Refused(503, GENERAL)          # the server has people, Mentor cannot read them
            if problem and (not stored or ident(who.get('person')) != stored): raise Refused(503, problem)
            me = find(first)            # no people file: the one person, the owner; or, while it is unusable, mentor.db's own
        else:
            me = find(ident(who.get('person')))
            if me is None: raise Refused(403, 'Mentor does not know you yet. Ask the owner to add you to the people file.')
            if role == 'learner' and me['role'] != 'learner': me = dict(me, role='learner')    # the smaller role counts
    if me['role'] == 'learner': p = me                                # learner=... from a learner is ignored
    elif requested:
        p = find(ident(requested))
        if p is None: raise Refused(404, f'Nobody with the id "{ident(requested) or requested}" is in the people file. Pick a name from the list.')
    else: p = me
    return {'id': p['id'], 'name': p['name'], 'role': p['role'], 'owner_db': p['id'] == first, 'me': me['id'], 'my_role': me['role']}

def listing(who, holder=None, stored=None):
    """GET api/mentor/learners: {me, role, people: [{id, name, role}]}; a learner sees only their own entry."""
    me = studying(who, holder=holder, stored=stored)
    ps, problem = people()
    rows = [{'id': p['id'], 'name': p['name'], 'role': p['role']} for p in ps]
    if me['my_role'] == 'learner': rows = [r for r in rows if r['id'] == me['me']]
    return {'me': me['me'], 'role': me['my_role'], 'people': rows, 'problem': problem if me['my_role'] == 'owner' else ''}
