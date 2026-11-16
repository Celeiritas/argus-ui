"""The owner's own Today (docs/home.md "Edit Today", 4.50.0): which tiles show and in what order, their names, Open's links
(shown, order, names, groups) and which sections may remind him. Saved on the server, so every device he opens Elaia on
shows the same Today, and in ~/.config/argus-ui/ (ARGUS_TODAY), next to links.json and media.json, because an install
replaces ~/.local/share/argus-ui/ but never touches the config folder: the layout is kept through updates.

The file, version 1 (every part may be left out; an empty object {} is the default layout, which is what Reset writes):
  {"v": 1,
   "tiles": {"order": [section id], "hidden": [section id], "names": {section id: name}},
   "open":  {"order": [key], "hidden": [key], "names": {key: name}, "groups": {key: group label, "" = no group}},
   "quiet": [section id]}
A section id is the one in its address ("controllers"); an Open key is "link:<its href>" or "media:<its id>". Names and
labels are plain text of at most 40 characters (the page escapes them); at most 64 entries in each list or map.

Missing file: the default layout, nothing said. Broken file (not JSON, the wrong shape, too big): the default layout, and
problem() says so in one plain line on the owner's Today; the next save from Edit first moves the broken file aside
(today.set-aside-<YYYYMMDD-HHMM>.json beside it), so nothing he wrote by hand is lost. A save writes a new file and swaps
it in (os.replace): a crash mid-write never leaves half a file.

Only the owner's page reads or saves it (POST api/today is the owner's, like every POST; a learner's state has no `today`).
Mentor never reminds him whatever the file says (quiet.py adds 'mentor' to quiet() every time)."""
import json, os, re, threading
from datetime import datetime

NAME_MAX, ITEMS_MAX, KEY_MAX = 40, 64, 300
FILE_MAX = 64 * 1024                       # the file: far more than 64 entries of everything need
BODY_MAX = 16 * 1024                       # POST api/today: one whole layout (argus_ui.py), more than the 4 KB of other POSTs
SECTION = re.compile(r'[a-z][a-z0-9-]{0,63}')
KEY = re.compile(r'(link:[^\x00-\x1f\x7f]{1,295}|media:[a-z0-9][a-z0-9-]{0,63})')
_lock = threading.Lock()
_cache = {'sig': None, 'val': ({}, None)}


def path(): return os.path.expanduser(os.environ.get('ARGUS_TODAY') or '~/.config/argus-ui/today.json')


def _name(v, what, empty_ok=False):
    if not isinstance(v, str): raise ValueError(f'{what} must be text.')
    v = ' '.join(v.split())               # one line: no tabs, newlines or runs of spaces
    if not v and not empty_ok: raise ValueError(f'{what} is empty.')
    if len(v) > NAME_MAX: raise ValueError(f'{what} is longer than {NAME_MAX} characters.')
    return v


def _ids(v, what, pat):
    if not isinstance(v, list): raise ValueError(f'{what} must be a list.')
    if len(v) > ITEMS_MAX: raise ValueError(f'{what} has more than {ITEMS_MAX} entries.')
    out = []
    for x in v:
        if not (isinstance(x, str) and len(x) <= KEY_MAX and pat.fullmatch(x)): raise ValueError(f'{what} has an entry that is not a section or link.')
        if x not in out: out.append(x)
    return out


def _map(v, what, pat, empty_ok=False):
    if not isinstance(v, dict): raise ValueError(f'{what} must be an object.')
    if len(v) > ITEMS_MAX: raise ValueError(f'{what} has more than {ITEMS_MAX} entries.')
    out = {}
    for k, x in v.items():
        if not (len(k) <= KEY_MAX and pat.fullmatch(k)): raise ValueError(f'{what} has an entry that is not a section or link.')
        x = _name(x, f'A name in {what}', empty_ok)
        if x or empty_ok: out[k] = x
    return out


def _part(v, what, fields):
    if not isinstance(v, dict): raise ValueError(f'"{what}" must be an object.')
    extra = sorted(set(v) - set(fields))
    if extra: raise ValueError(f'"{what}" has a field this version does not know: {extra[0][:40]}.')
    out = {}
    for f, check in fields.items():
        if f in v:
            c = check(v[f], f'{what}.{f}')
            if c: out[f] = c
    return out


def clean(d):
    """A layout as the page or the file gives it -> the same layout, checked and tidied (duplicates dropped, names on one
    line). Anything this version cannot use raises ValueError with a plain reason; nothing is guessed."""
    if not isinstance(d, dict): raise ValueError('The layout must be an object.')
    extra = sorted(set(d) - {'v', 'tiles', 'open', 'quiet'})
    if extra: raise ValueError(f'The layout has a field this version does not know: {extra[0][:40]}.')
    if 'v' in d and d['v'] != 1: raise ValueError('The layout is from another version (v must be 1).')
    out = {}
    if 'tiles' in d:
        t = _part(d['tiles'], 'tiles', {'order': lambda v, w: _ids(v, w, SECTION), 'hidden': lambda v, w: _ids(v, w, SECTION),
                                        'names': lambda v, w: _map(v, w, SECTION)})
        if 'home' in t.get('names', {}): raise ValueError('Today itself cannot be renamed.')
        if t: out['tiles'] = t
    if 'open' in d:
        o = _part(d['open'], 'open', {'order': lambda v, w: _ids(v, w, KEY), 'hidden': lambda v, w: _ids(v, w, KEY),
                                      'names': lambda v, w: _map(v, w, KEY), 'groups': lambda v, w: _map(v, w, KEY, empty_ok=True)})
        if o: out['open'] = o
    if 'quiet' in d:
        q = _ids(d['quiet'], 'quiet', SECTION)
        if q: out['quiet'] = q
    return out


def load():
    """-> (layout, problem). The layout is {} (the default) when the file is missing or broken; problem is None, or one plain
    sentence for the owner when the file is there but cannot be used. Read again only when the file changes."""
    p = path()
    try: st = os.stat(p); sig = (st.st_mtime_ns, st.st_size)
    except OSError: return {}, None
    if _cache['sig'] == sig: return _cache['val']
    why = None
    if st.st_size > FILE_MAX: why = f'it is larger than {FILE_MAX // 1024} KB'
    else:
        try:
            with open(p, encoding='utf-8') as f: d = clean(json.load(f))
        except OSError: return {}, None              # gone or unreadable for a moment: the default, ask again next time
        except (json.JSONDecodeError, UnicodeDecodeError): why = 'it is not valid JSON'
        except ValueError as e: why = str(e).rstrip('.')
    val = ({}, f'Your Today settings (today.json) could not be used ({why[:1].lower() + why[1:]}), so Today shows the default layout. '
               'Save from Edit to replace them; the old file is kept beside it.') if why else (d, None)
    _cache.update(sig=sig, val=val)
    return val


def problem(): return load()[1]


def quiet():
    """The sections he switched reminders off for (quiet.py adds Mentor)."""
    return set(load()[0].get('quiet', ()))


def _aside(p):
    stamp = datetime.now().strftime('%Y%m%d-%H%M')
    base, ext = os.path.splitext(p)
    dest = f'{base}.set-aside-{stamp}{ext}'
    n = 2
    while os.path.exists(dest): dest = f'{base}.set-aside-{stamp}-{n}{ext}'; n += 1
    os.replace(p, dest)
    return dest


def save(d):
    """Check and save a layout ({} = Reset to default). -> the layout as saved. ValueError: not saved, with the reason.
    A file that was broken is moved aside first, never overwritten."""
    d = clean(d)
    p = path()
    with _lock:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        if os.path.exists(p) and load()[1]: _aside(p)
        tmp = p + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f: json.dump(dict(v=1, **d), f, indent=1, ensure_ascii=False)
        os.replace(tmp, p)                 # atomic: a crash mid-write never leaves half a file
        _cache['sig'] = None
    return d
