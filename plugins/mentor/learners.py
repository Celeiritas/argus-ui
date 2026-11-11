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

FILE = os.path.expanduser(os.environ.get('ARGUS_PEOPLE', '~/.config/argus-ui/people.json'))
YOU = {'id': 'owner', 'name': 'You', 'role': 'owner'}
_cache = [None, None]               # (mtime, size) when last read, and (people, problem)
_told = set()

class Refused(Exception):
    """A request Mentor will not answer for this person: .code is the HTTP status, str() the sentence to show."""
    def __init__(self, code, msg):
        super().__init__(msg); self.code = code

def ident(s):
    """A person's id: lower case, letters a-z and digits kept, every run of anything else one "-" (safe in a file name)."""
    return re.sub(r'[^a-z0-9]+', '-', str(s or '').lower()).strip('-')[:40]

def log_once(msg):
    if msg not in _told:
        _told.add(msg); print(f'argus-ui: mentor people: {msg}', file=sys.stderr, flush=True)

def _read():
    """(people, problem). people: a list of {id, name, role, logins}; problem: '' or why the file was not used."""
    try:
        with open(FILE, encoding='utf-8') as f: doc = json.load(f)
        rows = doc.get('people') if isinstance(doc, dict) else None
        if not isinstance(rows, list): raise ValueError('it has no "people" list')
        out, seen = [], set()
        for p in rows:
            if not isinstance(p, dict) or not str(p.get('name') or '').strip(): continue
            pid = ident(p.get('id') or p['name'])
            if not pid: continue
            if pid in seen:            # the first entry with that id counts; the second is named once in the log (4.37)
                log_once(f'{FILE}: the id "{pid}" is used twice; only its first entry counts ({str(p["name"]).strip()[:60]} is left out)'); continue
            seen.add(pid)
            role = p.get('role') if p.get('role') in ('owner', 'learner') else 'learner'     # an unknown role gets the smaller one
            logins = [str(x).lower() for x in p.get('logins') or [] if isinstance(x, str)]
            out.append({'id': pid, 'name': str(p['name']).strip()[:60], 'role': role, 'logins': logins})
        if not any(p['role'] == 'owner' for p in out): raise ValueError('it names no owner')
        return out, ''
    except FileNotFoundError:
        return [dict(YOU, logins=[])], ''
    except (OSError, ValueError, TypeError) as e:
        log_once(f'{FILE}: {e} (read as "no file"; changes are refused until it is fixed)')
        return [dict(YOU, logins=[])], f'{FILE} cannot be read ({e}). Fix it on the server, then try again.'

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
    return os.path.isfile(FILE) and not people()[1]

def find(pid):
    return next((p for p in people()[0] if p['id'] == pid), None)

def studying(who, requested=None, write=False, holder=None):
    """The person whose lessons and progress this request reads or writes: {id, name, role, owner_db}. A learner is always
    themself; an owner (or a request the server told nothing about: who is None) may name anyone with `requested`.
    holder: whose history mentor.db is (plugin.holder(); None = the first owner, or the one person when there is no file).
    The role comes from the people file Mentor reads itself, never from `who` alone: a person the file does not know is
    refused, and the smaller of the two roles counts (4.37). With no people file every `who` but role none is the owner.
    Raises Refused: 403 for nobody (role none) or a stranger, 404 for an id that is not in the file, 503 for a write while
    the file is broken."""
    ps, problem = people()
    if write and problem: raise Refused(503, problem)
    first = holder if holder and find(holder) else owner_id()
    if who is None: me = find(first)                                  # not told: the owner, as before people existed
    else:
        role = who.get('role') if isinstance(who, dict) else None
        if role not in ('owner', 'learner'): raise Refused(403, 'Mentor is only for the people in the people file. Ask the owner to add you.')
        if not from_file(): me = find(first)                          # no people file: everybody let in is the one person
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

def listing(who, holder=None):
    """GET api/mentor/learners: {me, role, people: [{id, name, role}]}; a learner sees only their own entry."""
    me = studying(who, holder=holder)
    ps, problem = people()
    rows = [{'id': p['id'], 'name': p['name'], 'role': p['role']} for p in ps]
    if me['my_role'] == 'learner': rows = [r for r in rows if r['id'] == me['me']]
    return {'me': me['me'], 'role': me['my_role'], 'people': rows, 'problem': problem if me['my_role'] == 'owner' else ''}
