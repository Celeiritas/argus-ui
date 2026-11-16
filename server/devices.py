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

view(mode_probe, fresh) -> {"set_up", "problem", "checked", "devices": [{"name", "kind", "status", "label", "self", "last_seen",
                     "why", "wake"}]}; mode_probe() is the server's modes.probe for this machine (None when off)."""
import json, os, re, subprocess, sys, threading, time
from datetime import datetime, timezone

KINDS = ('pc', 'laptop', 'server', 'phone', 'tablet', 'console', 'other')
PROBES = ('self', 'tailscale', 'none')
HOST = re.compile(r'^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$')
MAC = re.compile(r'^[0-9A-Fa-f]{2}([:-])[0-9A-Fa-f]{2}(?:\1[0-9A-Fa-f]{2}){4}$')
MAX_FILE = 64 * 1024
MAX_DEVICES = 24
MAX_OUT = 4 * 1024 * 1024          # the most of tailscale's answer that is read (a big tailnet is a few hundred KB)
TIMEOUT_S = 5
FRESH_S = 5.0                     # Check again asks Tailscale again only if the last answer is this old
# the status set, fixed: each one has its own colour in the page (argus.css --dev-*) and a word, never colour alone
STATUSES = ('online', 'offline', 'unknown', 'desktop', 'game')
LABEL = {'online': 'Online', 'offline': 'Offline', 'unknown': "Can't tell"}


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
    if not isinstance(ds, list): raise ValueError('it needs a "devices" list')
    if len(ds) > MAX_DEVICES: raise ValueError(f'it lists {len(ds)} devices; the most is {MAX_DEVICES}')
    out, names, selves = [], set(), 0
    for i, d in enumerate(ds, 1):
        if not isinstance(d, dict): raise ValueError(f'device {i} is not an object')
        name = d.get('name').strip() if isinstance(d.get('name'), str) else ''
        if not 1 <= len(name) <= 40 or not name.isprintable(): raise ValueError(f'device {i}: the name must be 1 to 40 characters')
        if name.casefold() in names: raise ValueError(f'device {i}: two devices are called {name!r}')
        names.add(name.casefold())
        kind = d.get('kind', 'other')
        if kind not in KINDS: raise ValueError(f'device {i} ({name}): the kind must be one of {", ".join(KINDS)}')
        probe = d.get('probe')
        if probe not in PROBES: raise ValueError(f'device {i} ({name}): the probe must be one of {", ".join(PROBES)}')
        host = d.get('host')
        if probe == 'tailscale':
            if not isinstance(host, str) or not HOST.fullmatch(host):
                raise ValueError(f'device {i} ({name}): "host" must be its Tailscale host name (letters, digits and "-")')
        else: host = None
        if probe == 'self':
            selves += 1
            if selves > 1: raise ValueError('only one device can be "self" (this machine)')
        wake = d.get('wake')
        if wake is not None and not (isinstance(wake, dict) and isinstance(wake.get('mac'), str) and MAC.fullmatch(wake['mac'])):
            raise ValueError(f'device {i} ({name}): "wake" must be {{"mac": "aa:bb:cc:dd:ee:ff"}}')
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
_cfg = {'key': None, 'devices': None, 'problem': None}


def config():
    """(devices, problem): the list now (None: no file) and what is wrong with the file (None: nothing). One stat per call."""
    path = devices_path()
    try:
        st = os.stat(path); key = (path, st.st_mtime_ns, st.st_size)
    except (FileNotFoundError, NotADirectoryError): key = (path, None, None)
    except OSError as e: key = (path, 'error', str(e))
    with _cfg_lock:
        if _cfg['key'] == key: return _cfg['devices'], _cfg['problem']
        devices, problem = None, None
        if key[1] is not None:
            try: devices = load(path)
            except Exception as e:
                why = e.strerror if isinstance(e, OSError) and e.strerror else e
                problem = f'{os.path.basename(path)} could not be used: {why}'
                print(f'argus-ui: {problem}; the device list is empty', file=sys.stderr, flush=True)
        _cfg.update(key=key, devices=devices, problem=problem)
    return devices, problem


def run_status():
    """(answer dict, None) or (None, why): one `tailscale status --json`, never through a shell."""
    try:
        r = subprocess.run(command(), stdin=subprocess.DEVNULL, capture_output=True, timeout=TIMEOUT_S)
    except FileNotFoundError: return None, 'Tailscale is not installed on this machine'
    except subprocess.TimeoutExpired: return None, 'Tailscale did not answer in time'
    except OSError: return None, 'Tailscale could not be run'
    if r.returncode != 0: return None, 'Tailscale gave an error'
    try: doc = json.loads(r.stdout[:MAX_OUT].decode('utf-8', 'replace'))
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


def peers(doc):
    """{host name, case folded: node}: every peer and this machine itself, by HostName and by the first part of DNSName."""
    out = {}
    nodes = list((doc.get('Peer') or {}).values()) if isinstance(doc.get('Peer'), dict) else []
    if isinstance(doc.get('Self'), dict): nodes.append(dict(doc['Self'], _self=True))
    for n in nodes:
        if not isinstance(n, dict): continue
        for k in (label(n.get('DNSName')), label(n.get('HostName'))):
            if k and k not in out: out[k] = n
    return out


def seen(v):
    """LastSeen as an ISO time, or None (Tailscale writes the year 1 for a peer that is online now or never seen)."""
    if not isinstance(v, str): return None
    try: t = datetime.fromisoformat(v.replace('Z', '+00:00'))
    except ValueError: return None
    if t.year < 2000: return None
    return (t if t.tzinfo else t.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).isoformat(timespec='seconds')


def one(d, doc, why, mode):
    """One device's row for the page."""
    row = {'name': d['name'], 'kind': d['kind'], 'self': d['probe'] == 'self', 'last_seen': None, 'why': None, 'wake': d['wake']}
    if d['probe'] == 'self':
        cur = mode.get('current') if isinstance(mode, dict) else None
        lab = next((m.get('label') for m in (mode or {}).get('modes', []) if m.get('id') == cur), None) if cur else None
        if cur in ('desktop', 'game') and lab: return dict(row, status=cur, label=f'{lab} mode')
        return dict(row, status='online', label='Online', why='This machine')
    if d['probe'] == 'none': return dict(row, status='unknown', label=LABEL['unknown'], why='Argus does not check this one')
    if doc is None: return dict(row, status='unknown', label=LABEL['unknown'], why=why)
    n = peers(doc).get(d['host'].casefold())
    if n is None: return dict(row, status='unknown', label=LABEL['unknown'], why='Not on the Tailscale list')
    if n.get('_self'): return dict(row, status='online', label='Online', why='This machine')
    on = n.get('Online')
    if on is True: return dict(row, status='online', label='Online')
    if on is False: return dict(row, status='offline', label='Offline', last_seen=seen(n.get('LastSeen')))
    return dict(row, status='unknown', label=LABEL['unknown'], why='Tailscale did not say')


def view(mode_probe=None, now=None, fresh=False):
    """What GET api/devices answers (the owner's): the list with each device's status, or why there is none."""
    devices, problem = config()
    if not devices:
        return {'set_up': devices is not None or problem is not None, 'problem': problem, 'checked': None, 'devices': []}
    doc, why, checked = status_doc(now, fresh) if any(d['probe'] == 'tailscale' for d in devices) else (None, None, None)
    mode = None
    if any(d['probe'] == 'self' for d in devices) and mode_probe:
        try: mode = mode_probe()
        except Exception: mode = None
    rows = [one(d, doc, why, mode) for d in devices]
    return {'set_up': True, 'problem': None, 'checked': checked or datetime.now(timezone.utc).isoformat(timespec='seconds'), 'devices': rows}
