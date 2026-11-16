"""The device list: Argus's panel of the owner's devices on Watch, and the short line on Today (docs/devices.md).

The devices live in one file on the host, never in the repo: ARGUS_DEVICES, else ~/.config/argus-ui/devices.json:
    {"devices": [{"name": "{{SERVER}}", "kind": "server", "probe": "self"},
                 {"name": "{{PC}}",     "kind": "pc",     "probe": "tailscale", "host": "<tailscale host name>",
                  "wake": {"mac": "aa:bb:cc:dd:ee:ff"}},
                 {"name": "{{PHONE}}",  "kind": "phone",  "probe": "tailscale", "host": "<tailscale host name>"}]}
  - at most MAX_DEVICES devices, in the order the list shows them; each name 1 to 40 characters, no two the same
  - kind: one of KINDS (only the word shown under the name)
  - probe: "self" (this machine: online, and Desktop or Game when modes.json sets that up; at most one), "tailscale" (the
    peer whose host name is `host` in `tailscale status --json`) or "none" (not checked: always "can't tell")
  - host: a host name as Tailscale shows it (letters, digits and "-", at most 63), needed for "tailscale"
  - wake: optional, the place for Wake on LAN later: {"mac": "<six pairs of hex digits>"}. Nothing uses it yet; the page
    only learns that it is there ("wake": true), never the address.
  - no file: the list is empty (the page says how to add one). A bad file: the page says what is wrong, and stderr gets one
    line each time the file changes. It is read again when its modification time or size changes.

The probe: ONE `tailscale status --json` for all devices (a fixed argument list, never a shell, nothing from the file in it),
with a TIMEOUT_S timeout, cached for CACHE_S seconds. When it cannot be run, hangs, fails, says Tailscale is not running or
gives no answer for a device, that device is "unknown" ("can't tell"), never "offline".

view(mode_probe, fresh) -> {"set_up", "problem", "file", "device", "probe_problem", "checked", "devices": [{"name", "kind",
  "status", "label", "self", "last_seen", "why", "wake"}]}; mode_probe() is the server's modes.probe for this machine (None
  when off). "file" and "device" say where a bad file is wrong (its name, and the device's number when one device is);
  "probe_problem" is why Tailscale could not be asked, said once for the list (its rows then say only "can't tell")."""
import json, os, re, subprocess, sys, threading, time, traceback
from datetime import datetime, timezone

KINDS = ('pc', 'laptop', 'server', 'phone', 'tablet', 'console', 'other')
PROBES = ('self', 'tailscale', 'none')
HOST = re.compile(r'^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$')
MAC = re.compile(r'^[0-9A-Fa-f]{2}([:-])[0-9A-Fa-f]{2}(?:\1[0-9A-Fa-f]{2}){4}$')
MAX_FILE = 64 * 1024
MAX_DEVICES = 24
MAX_OUT = 4 * 1024 * 1024          # the most of tailscale's answer that is read, held to while reading (a big tailnet is a few hundred KB)
TIMEOUT_S = 5
FRESH_S = 5.0                     # Check again asks Tailscale again only if the last answer is this old
# the status set, fixed: each one has its own colour in the page (argus.css --dev-*) and a word, never colour alone
STATUSES = ('online', 'offline', 'unknown', 'desktop', 'game')
LABEL = {'online': 'Online', 'offline': 'Offline', 'unknown': "Can't tell"}
TWO = 'Two machines on the Tailscale list have this name'


class Bad(ValueError):
    """What is wrong with the file, and the number of the device it is wrong in (None: the file as a whole)."""
    def __init__(self, msg, device=None): super().__init__(msg); self.device = device


def cache_s():
    try: return max(0.0, min(300.0, float(os.environ.get('ARGUS_DEVICES_CACHE', 30))))
    except ValueError: return 30.0


def devices_path(): return os.path.expanduser(os.environ.get('ARGUS_DEVICES') or '~/.config/argus-ui/devices.json')


def command():
    """The probe's argument list: a fixed list, run without a shell. ARGUS_TAILSCALE names another binary (the tests' fake)."""
    return [os.environ.get('ARGUS_TAILSCALE') or 'tailscale', 'status', '--json']


def parse(doc):
    """The devices from the file's JSON, checked. ValueError says what is wrong, in words the page can show."""
    ds = doc.get('devices') if isinstance(doc, dict) else None
    if not isinstance(ds, list): raise Bad('it needs a "devices" list')
    if len(ds) > MAX_DEVICES: raise Bad(f'it lists {len(ds)} devices; the most is {MAX_DEVICES}')
    out, names, selves = [], set(), 0
    for i, d in enumerate(ds, 1):
        if not isinstance(d, dict): raise Bad(f'device {i} is not an object', i)
        name = d.get('name').strip() if isinstance(d.get('name'), str) else ''
        if not 1 <= len(name) <= 40 or not name.isprintable(): raise Bad(f'device {i}: the name must be 1 to 40 characters', i)
        if name.casefold() in names: raise Bad(f'device {i}: two devices are called {name!r}', i)
        names.add(name.casefold())
        kind = d.get('kind', 'other')
        if kind not in KINDS: raise Bad(f'device {i} ({name}): the kind must be one of {", ".join(KINDS)}', i)
        probe = d.get('probe')
        if probe not in PROBES: raise Bad(f'device {i} ({name}): the probe must be one of {", ".join(PROBES)}', i)
        host = d.get('host')
        if probe == 'tailscale':
            if not isinstance(host, str) or not HOST.fullmatch(host):
                raise Bad(f'device {i} ({name}): "host" must be its Tailscale host name (letters, digits and "-")', i)
        else: host = None
        if probe == 'self':
            selves += 1
            if selves > 1: raise Bad(f'device {i}: only one device can be "self" (this machine)', i)
        wake = d.get('wake')
        if wake is not None and not (isinstance(wake, dict) and isinstance(wake.get('mac'), str) and MAC.fullmatch(wake['mac'])):
            raise Bad(f'device {i} ({name}): "wake" must be {{"mac": "aa:bb:cc:dd:ee:ff"}}', i)
        out.append({'name': name, 'kind': kind, 'probe': probe, 'host': host, 'wake': wake is not None})
    return out


def load(path):
    """The checked devices in the file at path. OSError when it cannot be read, ValueError when it is not right."""
    with open(path, encoding='utf-8') as f: text = f.read(MAX_FILE + 1)
    if len(text) > MAX_FILE: raise ValueError('the file is too large')
    try: doc = json.loads(text)
    except ValueError as e: raise ValueError(f'it is not valid JSON (line {getattr(e, "lineno", "?")})') from None
    return parse(doc)


_cfg_lock = threading.Lock()
_cfg = {'key': None, 'devices': None, 'problem': None, 'where': None}


def config(where=False):
    """(devices, problem): the list now (None: no file) and what is wrong with the file (None: nothing). One stat per call.
    where=True adds a third: {"file": its name, "device": the number of the device that is wrong, or None} for a bad file."""
    path = devices_path()
    try:
        st = os.stat(path); key = (path, st.st_mtime_ns, st.st_size)
    except (FileNotFoundError, NotADirectoryError): key = (path, None, None)
    except OSError as e: key = (path, 'error', str(e))
    with _cfg_lock:
        if _cfg['key'] != key:
            devices, problem, at = None, None, None
            if key[1] is not None:
                try: devices = load(path)
                except Exception as e:
                    why = e.strerror if isinstance(e, OSError) and e.strerror else e
                    problem = f'{os.path.basename(path)} could not be used: {why}'
                    at = {'file': os.path.basename(path), 'device': getattr(e, 'device', None)}
                    print(f'argus-ui: {problem}; the device list is empty', file=sys.stderr, flush=True)
            _cfg.update(key=key, devices=devices, problem=problem, where=at)
        out = (_cfg['devices'], _cfg['problem'])
        return out + (_cfg['where'],) if where else out


def read_capped(cmd, timeout, cap):
    """(exit code, output bytes, cut): cmd run without a shell, at most `cap` bytes of its output read: past that it is
    stopped at once (the limit holds while reading, so a runaway answer never fills the memory). cut: None, 'big' or 'slow'."""
    p = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    buf, over = bytearray(), []
    def pump():
        try:
            while True:
                chunk = p.stdout.read1(65536)
                if not chunk: return
                buf.extend(chunk)
                if len(buf) > cap: over.append(1); p.kill(); return
        except (OSError, ValueError): return
    t = threading.Thread(target=pump, daemon=True); t.start()
    deadline = time.monotonic() + timeout
    t.join(timeout)
    try:
        if t.is_alive(): p.kill(); return None, b'', 'slow'
        if over: return None, b'', 'big'
        try: rc = p.wait(timeout=max(0.1, deadline - time.monotonic()))
        except subprocess.TimeoutExpired: p.kill(); return None, b'', 'slow'
        return rc, bytes(buf), None
    finally:
        t.join(1)
        try: p.wait(timeout=1)
        except subprocess.TimeoutExpired: pass
        try: p.stdout.close()
        except OSError: pass


def run_status():
    """(answer dict, None) or (None, why): one `tailscale status --json`, never through a shell."""
    try: rc, out, cut = read_capped(command(), TIMEOUT_S, MAX_OUT)
    except FileNotFoundError: return None, 'Tailscale is not installed on this machine'
    except OSError: return None, 'Tailscale could not be run'
    if cut == 'slow': return None, 'Tailscale did not answer in time'
    if cut == 'big': return None, 'Tailscale gave an answer too large to read'
    if rc != 0: return None, 'Tailscale gave an error'
    try: doc = json.loads(out.decode('utf-8', 'replace'))
    except ValueError: return None, 'Tailscale gave an answer Argus could not read'
    if not isinstance(doc, dict): return None, 'Tailscale gave an answer Argus could not read'
    state = doc.get('BackendState')
    if isinstance(state, str) and state and state != 'Running': return None, f'Tailscale is not running here ({state[:20]})'
    return doc, None


_probe_lock = threading.Lock()
_cache = {'at': None, 'doc': None, 'why': None, 'checked': None}


def status_doc(now=None, fresh=False):
    """(answer, why, checked): the cached `tailscale status --json`, asked again after cache_s() seconds, or after
    FRESH_S when the owner pressed Check again (fresh), so a held key cannot run it many times a second."""
    with _probe_lock:
        t = time.monotonic() if now is None else now
        if _cache['at'] is None or not 0 <= t - _cache['at'] < (min(FRESH_S, cache_s()) if fresh else cache_s()):
            doc, why = run_status()
            _cache.update(at=t, doc=doc, why=why, checked=datetime.now(timezone.utc).isoformat(timespec='seconds'))
        return _cache['doc'], _cache['why'], _cache['checked']


def clear_cache():
    with _probe_lock: _cache.update(at=None, doc=None, why=None, checked=None)


def label(h):
    return h.split('.')[0].casefold() if isinstance(h, str) else ''


AMBIGUOUS = {'_two': True}             # two nodes answer to one name: Argus can't tell which one the device is


def peers(doc):
    """{host name, case folded: node}: every peer and this machine itself. Two passes, so the answer never depends on the
    order Tailscale lists its peers: first the first part of each node's DNSName (Self too; Tailscale keeps these unique,
    adding "-1" to a re-added machine), then each HostName that no DNS name took. A name two nodes claim in the same pass
    (two phones both called "localhost") is AMBIGUOUS, never either one's status."""
    nodes = list((doc.get('Peer') or {}).values()) if isinstance(doc.get('Peer'), dict) else []
    if isinstance(doc.get('Self'), dict): nodes.append(dict(doc['Self'], _self=True))
    nodes = [n for n in nodes if isinstance(n, dict)]
    out = {}
    for field in ('DNSName', 'HostName'):
        claims = {}
        for n in nodes:
            k = label(n.get(field))
            if k and k not in out: claims.setdefault(k, []).append(n)
        out.update({k: ns[0] if len(ns) == 1 else AMBIGUOUS for k, ns in claims.items()})
    return out


def seen(v):
    """LastSeen as an ISO time, or None (Tailscale writes the year 1 for a peer that is online now or never seen)."""
    if not isinstance(v, str): return None
    try: t = datetime.fromisoformat(v.replace('Z', '+00:00'))
    except ValueError: return None
    if t.year < 2000: return None
    return (t if t.tzinfo else t.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).isoformat(timespec='seconds')


def hues(ids):
    """The colour of each of the two modes, as the pill picks it (core.js modeHues()): an id "game" or "desktop" keeps its
    own, one other id gets the colour left over, two other ids are green then purple."""
    h = [i if i in ('game', 'desktop') else None for i in ids]
    if len(h) != 2 or h[0] == h[1]: return ['desktop', 'game'][:len(h)]
    other = lambda k: 'desktop' if k == 'game' else 'game'
    return [h[0] or other(h[1]), h[1] or other(h[0])]


def mode_row(mode):
    """(status, label) for this machine in its mode, coloured as the pill colours it, or None when there is no mode to show.
    The label is the mode's own; " mode" is added unless it already ends with it."""
    if not isinstance(mode, dict): return None
    ms = [m for m in mode.get('modes') or [] if isinstance(m, dict)]
    ids = [m.get('id') for m in ms]
    cur = mode.get('current')
    if len(ms) != 2 or cur not in ids: return None
    lab = ms[ids.index(cur)].get('label')
    if not isinstance(lab, str) or not lab.strip(): return None
    lab = lab.strip()
    return hues(ids)[ids.index(cur)], lab if lab.casefold().endswith('mode') else f'{lab} mode'


def one(d, doc, why, mode):
    """One device's row for the page. When Tailscale could not be asked (doc None), a Tailscale device's row is "can't
    tell" with no reason of its own: view() says that reason once, for the whole list."""
    row = {'name': d['name'], 'kind': d['kind'], 'self': d['probe'] == 'self', 'last_seen': None, 'why': None, 'wake': d['wake']}
    if d['probe'] == 'self':
        m = mode_row(mode)
        if m: return dict(row, status=m[0], label=m[1])
        return dict(row, status='online', label='Online', why='This machine')
    if d['probe'] == 'none': return dict(row, status='unknown', label=LABEL['unknown'], why='Argus does not check this one')
    if doc is None: return dict(row, status='unknown', label=LABEL['unknown'])
    n = peers(doc).get(d['host'].casefold())
    if n is None: return dict(row, status='unknown', label=LABEL['unknown'], why='Not on the Tailscale list')
    if n is AMBIGUOUS: return dict(row, status='unknown', label=LABEL['unknown'], why=TWO)
    if n.get('_self'): return dict(row, status='online', label='Online', why='This machine')
    on = n.get('Online')
    if on is True: return dict(row, status='online', label='Online')
    if on is False: return dict(row, status='offline', label='Offline', last_seen=seen(n.get('LastSeen')))
    return dict(row, status='unknown', label=LABEL['unknown'], why='Tailscale did not say')


def view(mode_probe=None, now=None, fresh=False):
    """What GET api/devices answers (the owner's): the list with each device's status, or why there is none."""
    devices, problem, where = config(where=True)
    if not devices:
        return {'set_up': devices is not None or problem is not None, 'problem': problem, 'file': (where or {}).get('file'),
                'device': (where or {}).get('device'), 'probe_problem': None, 'checked': None, 'devices': []}
    doc, why, checked = status_doc(now, fresh) if any(d['probe'] == 'tailscale' for d in devices) else (None, None, None)
    mode = None
    if any(d['probe'] == 'self' for d in devices) and mode_probe:
        try: mode = mode_probe()
        except Exception: mode = None
    rows = [one(d, doc, why, mode) for d in devices]
    return {'set_up': True, 'problem': None, 'file': None, 'device': None, 'probe_problem': why if doc is None else None,
            'checked': checked or datetime.now(timezone.utc).isoformat(timespec='seconds'), 'devices': rows}


_logged = set()


def failed_view(exc):
    """What GET api/devices answers when view() itself went wrong (a bug, not the file): a plain problem for the page, and
    the real error with its traceback in the log, once for each different error, so it never hides behind the message."""
    sig = (type(exc).__name__, str(exc)[:200])
    if sig not in _logged:
        if len(_logged) >= 100:      # an error text with a changing time or path must not grow the set without end
            _logged.clear()
        _logged.add(sig)
        print('argus-ui: the device list failed:\n' + ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
              file=sys.stderr, flush=True)
    return {'set_up': True, 'problem': 'Argus could not read the device list. It tries again in a moment.', 'file': None,
            'device': None, 'probe_problem': None, 'checked': None, 'devices': []}
