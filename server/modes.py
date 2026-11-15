"""Desktop / Game mode: the pill at the top of every section, and POST api/mode (docs/modes.md).

The host's two modes and their units live in one file on the host, never in the repo: ARGUS_MODES, else
~/.config/argus-ui/modes.json:
    {"modes": [{"id": "desktop", "label": "Desktop", "active_unit": "<unit>", "switch_unit": "<unit>"},
               {"id": "game",    "label": "Game",    "active_unit": "<unit>", "switch_unit": "<unit>"}]}
  - exactly two modes, in the order the pill shows them; each id is a-z, 0-9 and '-', starting with a letter, at most 16
    characters, and the two differ; each label is 1 to 16 characters
  - active_unit runs while the host is in that mode; switch_unit is the unit that switches the host INTO that mode (a
    oneshot that ends when it is done). Unit names may leave out ".service"; the four names must all differ.
  - no file: the feature is off (no pill, POST api/mode is 404). A bad file: off too, and one line on stderr each time the
    file changes. It is read again when its modification time or size changes.

The host rule: Argus only ever starts a switch unit (start --no-block), never a session unit itself. Starting a game session
from a script while the desktop runs makes a hidden second session (a black screen until a reboot).

probe(sc, name)              -> {"current": id | "unknown", "switching": id | None, "modes": [{"id", "label"}], "name"},
                                or None when off. ONE systemctl call for all four units, cached for CACHE_S seconds.
switch(to, sc, sc_ok, name)  -> (HTTP code, ok, msg): one switch at a time, re-probed under its own lock.
`sc` / `sc_ok` are the server's systemctl --user helpers (argus_ui.sc / sc_ok, with their 20 s timeout)."""
import json, os, re, subprocess, sys, threading, time

ID = re.compile(r'^[a-z][a-z0-9-]{0,15}$')
UNIT = re.compile(r'^[A-Za-z0-9@._:-]+$')
OTHER_KINDS = ('.target', '.timer', '.socket', '.scope', '.slice', '.mount', '.automount', '.path', '.device', '.swap')
PENDING_S = 120          # a switch Argus started counts as "switching" this long, unless the target mode shows up first
CACHE_S = 2.0            # one systemctl call per this many seconds, however many pages ask
MAX_FILE = 64 * 1024
ON = ('active', 'reloading')              # an active_unit in one of these: the host is in that mode
BUSY = ('activating', 'active', 'reloading')   # a switch_unit in one of these: a switch is under way

_cfg_lock = threading.Lock()
_cfg = {'key': None, 'modes': None}
_probe_lock = threading.Lock()            # the cache and the pending switch; never the server's LOCK
_cache = {'at': None, 'modes': None, 'states': None}
_pending = {}                             # {'to': id, 'at': monotonic seconds} after a start this server sent
_switch_lock = threading.Lock()           # one switch at a time


def modes_path(): return os.path.expanduser(os.environ.get('ARGUS_MODES') or '~/.config/argus-ui/modes.json')


def unit_name(v):
    """A unit name from the file, normalised to end in .service. ValueError with a short reason when it cannot be used."""
    if not isinstance(v, str) or not v: raise ValueError('a unit name is missing')
    if v.startswith('-'): raise ValueError(f'the unit name {v[:40]!r} starts with "-"')
    if len(v) > 240 or not UNIT.fullmatch(v): raise ValueError(f'the unit name {v[:40]!r} has characters a unit name cannot have')
    if v.endswith(OTHER_KINDS): raise ValueError(f'{v!r} is not a service: only .service units can be used')
    if not v.endswith('.service'): v += '.service'
    if v.endswith('@.service'): raise ValueError(f'{v!r} is a template: name one instance of it, with its part after "@" filled in')
    return v


def parse(doc):
    """The two modes from the file's JSON, checked: [{id, label, active_unit, switch_unit}]. ValueError says what is wrong."""
    ms = doc.get('modes') if isinstance(doc, dict) else None
    if not isinstance(ms, list): raise ValueError('it needs a "modes" list')
    if len(ms) != 2: raise ValueError(f'it needs exactly two modes, not {len(ms)}')
    out = []
    for i, m in enumerate(ms, 1):
        if not isinstance(m, dict): raise ValueError(f'mode {i} is not an object')
        id_, label = m.get('id'), m.get('label')
        if not isinstance(id_, str) or not ID.fullmatch(id_): raise ValueError(f'mode {i}: the id must be a-z, 0-9 and "-", start with a letter, at most 16 characters')
        label = label.strip() if isinstance(label, str) else ''
        if not 1 <= len(label) <= 16 or not label.isprintable(): raise ValueError(f'mode {i}: the label must be 1 to 16 characters')
        out.append({'id': id_, 'label': label, 'active_unit': unit_name(m.get('active_unit')), 'switch_unit': unit_name(m.get('switch_unit'))})
    if out[0]['id'] == out[1]['id']: raise ValueError('the two modes have the same id')
    if len(set(unit_list(out))) != 4: raise ValueError('the four unit names must all differ')
    return out


def load(path):
    """The checked modes in the file at path. OSError when it cannot be read, ValueError when it is not right."""
    with open(path, encoding='utf-8') as f: text = f.read(MAX_FILE + 1)
    if len(text) > MAX_FILE: raise ValueError('the file is too large')
    return parse(json.loads(text))


def config():
    """The modes now, or None when the feature is off. One stat per call; the file is read again only when it changes."""
    path = modes_path()
    try:
        st = os.stat(path); key = (path, st.st_mtime_ns, st.st_size)
    except (FileNotFoundError, NotADirectoryError): key = (path, None, None)
    except OSError as e: key = (path, 'error', str(e))
    with _cfg_lock:
        if _cfg['key'] == key: return _cfg['modes']
        modes = None
        if key[1] is not None:
            try: modes = load(path)
            except Exception as e:
                why = e.strerror if isinstance(e, OSError) and e.strerror else e
                print(f'argus-ui: {os.path.basename(path)}: {why}; the Desktop / Game pill is off', file=sys.stderr, flush=True)
        _cfg.update(key=key, modes=modes)
    with _probe_lock: _cache.update(at=None, modes=None, states=None); _pending.clear()
    return modes


def unit_list(modes):
    return [m[k] for m in modes for k in ('active_unit', 'switch_unit')]


def parse_show(text, units):
    """{unit: ActiveState} from `systemctl show A B C D -p Id -p ActiveState`: one block per unit, in the order asked,
    with a blank line between. Read by position when the count matches (an alias's Id is its real name), else by Id."""
    blocks = []
    for chunk in re.split(r'\n\s*\n', (text or '').strip()):
        d = {}
        for line in chunk.splitlines():
            k, sep, v = line.partition('=')
            if sep: d[k.strip()] = v.strip()
        if d: blocks.append(d)
    if len(blocks) == len(units): return {u: d.get('ActiveState', '') for u, d in zip(units, blocks)}
    return {d['Id']: d.get('ActiveState', '') for d in blocks if d.get('Id') in units}


def show(modes, sc):
    """The four units' states in ONE systemctl call; {} when systemctl fails or hangs (then the mode is unknown)."""
    us = unit_list(modes)
    try: return parse_show(sc('show', *us, '-p', 'Id', '-p', 'ActiveState'), us)
    except Exception: return {}


def compute(modes, states, now):
    """(current, switching) from the units' states and the pending switch. Call with _probe_lock held.
    A note newer than `now` (age below 0) counts as fresh: it is never cleared for being written a moment after `now` was read."""
    on = [m['id'] for m in modes if states.get(m['active_unit']) in ON]
    current = on[0] if len(on) == 1 else 'unknown'          # both or neither: Argus can't tell
    switching = next((m['id'] for m in modes if states.get(m['switch_unit']) in BUSY), None)
    p = dict(_pending)
    if p:
        if p['to'] == current or now - p['at'] >= PENDING_S or p['to'] not in [m['id'] for m in modes]: _pending.clear()
        elif switching is None: switching = p['to']
    return current, switching


def probe(sc, name, now=None):
    """What the pill shows, or None when the feature is off. Cached for CACHE_S seconds; never holds the server's LOCK."""
    modes = config()
    if not modes: return None
    with _probe_lock:
        t = time.monotonic() if now is None else now     # read under the lock: a note switch() wrote meanwhile is never newer
        fresh = _cache['modes'] is modes and _cache['at'] is not None and 0 <= t - _cache['at'] < CACHE_S
        if not fresh: _cache.update(at=t, modes=modes, states=show(modes, sc))
        current, switching = compute(modes, _cache['states'], t)
    return {'current': current, 'switching': switching, 'modes': [{'id': m['id'], 'label': m['label']} for m in modes], 'name': name}


def clear_cache():
    with _probe_lock: _cache.update(at=None, modes=None, states=None)


def short(err):
    line = next((x.strip() for x in str(err or '').splitlines() if x.strip()), '')
    return (line[:157] + '...') if len(line) > 160 else (line or 'systemctl gave no reason')


def switch(to, sc, sc_ok, name, now=None):
    """POST api/mode {"to": id}. -> (HTTP code, ok, msg). Starts the target's switch unit and nothing else (the host rule)."""
    modes = config()
    if not modes: return 404, False, 'Desktop / Game mode is not set up on this server.'
    m = next((m for m in modes if m['id'] == to), None) if isinstance(to, str) else None
    if m is None: return 400, False, 'There is no mode with that name. Reload the page.'
    if not _switch_lock.acquire(timeout=45): return 409, False, f'{name} is already switching modes.'
    try:
        clear_cache()                          # look again inside the lock: another press may have just started one
        p = probe(sc, name, now)
        if p is None: return 404, False, 'Desktop / Game mode is not set up on this server.'
        label = {x['id']: x['label'] for x in p['modes']}
        if p['switching']: return 409, False, f'{name} is already switching to {label.get(p["switching"], p["switching"])} mode.'
        if p['current'] == 'unknown': return 409, False, f"Can't tell which mode {'the server' if name == 'The server' else name} is in right now. Try again in a minute."
        if p['current'] == to: return 200, True, f'Already in {m["label"]} mode.'
        at = time.monotonic() if now is None else now
        with _probe_lock:                      # the note goes in BEFORE the start: no page ever sees the unit started and no note
            _cache.update(at=None, modes=None, states=None); _pending.clear(); _pending.update(to=to, at=at)
        timed_out = False
        try: ok, err = sc_ok('start', '--no-block', m['switch_unit'])
        except subprocess.TimeoutExpired: ok, err, timed_out = False, '', True
        except Exception: ok, err = False, 'systemctl could not be run'
        with _probe_lock:
            _cache.update(at=None, modes=None, states=None)
            # refused: nothing is switching. No answer in 20 s: the start may still have been queued (--no-block), so the note
            # stays and a second press is refused until the mode shows up or PENDING_S pass.
            if not ok and not timed_out and _pending.get('to') == to and _pending.get('at') == at: _pending.clear()
        if timed_out: return 200, False, f'{name} may be switching to {m["label"]} mode: systemctl did not answer in time. Check the TV before you try again.'
        if not ok: return 200, False, f'{name} could not start the switch to {m["label"]} mode: {short(err)}'
        return 200, True, f'Switching to {m["label"]} mode. The TV goes dark for a few seconds.'
    finally: _switch_lock.release()
