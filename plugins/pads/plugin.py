# Leafy Pads: which game pads this machine sees right now, read-only (docs/pads.md).
# A bundled server plugin (docs/leafy-plugin.md): GET api/pads/list (the rows) and api/pads/status (Home's line).
# Everything comes from two kernel views, read on every request, never written and never through a shell:
#   /proc/bus/input/devices          one block per input device: ids, name, phys, sysfs path, handlers (event, js)
#   /sys/<that sysfs path>/capabilities/ff   force-feedback bits: non-zero means rumble can reach the pad
# The probe is a port of the owner's read-only shell check (pads section): name, real or virtual, rumble.
# `sysroot` points both at a copy for tests (tests/fixtures/pads-sysfs/); ARGUS_PADS_SYSROOT does it for the server.
import json, os, re

SYSROOT = os.environ.get('ARGUS_PADS_SYSROOT', '/')
REGISTRY = os.path.expanduser(os.environ.get('ARGUS_PADS', '~/.config/argus-ui/pads.json'))

# The OpenPuck (a Steam Controller dongle) changes its USB ids with its mode, so the ids name the mode.
MODES = {'28de:1304': 'Steam', '045e:028e': 'Xbox 360', '2e8a:10c6': 'SInput', '0f0d:0092': 'Switch'}
# Steam Input's virtual pads: Steam makes one "Microsoft X-Box 360 pad N" per pad it takes over, under /sys/devices/virtual/
STEAM_VIRTUAL = re.compile(r'^Microsoft X-Box 360 pad \d+$')
# names that are pads even without a js handler (the shell check's list); their mouse and keyboard parts have no ABS axes
PAD_NAME = re.compile(r'steam|x-?box|puck|pro controller|sony|dualsense|hori|sinput|gamepad|joy-?con|8bitdo', re.I)
NOT_PAD = re.compile(r'(touchpad|motion sensors|mouse|keyboard|consumer control|system control)$', re.I)
WAKE_HINT = "Press a pad's Home or Steam button to wake it. Still missing? Check that its cable or dongle is in the hub."
EV_ABS = 0x08

def _read(path):
    try:
        with open(path, encoding='utf-8', errors='replace') as f: return f.read()
    except OSError: return None

def _bits(words):
    """A capability bitmap as the kernel prints it (hex words, highest first) -> int; '' or garbage -> 0."""
    try: return int(''.join(w.rjust(16, '0') for w in words.split()) or '0', 16)
    except ValueError: return 0

def devices(sysroot=None):
    """Every input device in /proc/bus/input/devices as a dict, or None when the file can't be read (not Linux)."""
    text = _read(os.path.join(sysroot or SYSROOT, 'proc', 'bus', 'input', 'devices'))
    if text is None: return None
    out = []
    for block in re.split(r'\n\s*\n', text.strip()):
        d = {'name': '', 'vid': '', 'pid': '', 'phys': '', 'sysfs': '', 'handlers': [], 'ev': 0, 'ff_line': None}
        for ln in block.splitlines():
            tag, _, val = ln.partition(': ')
            if tag == 'I':
                kv = dict(x.split('=', 1) for x in val.split() if '=' in x)
                d['vid'], d['pid'] = kv.get('Vendor', '').lower(), kv.get('Product', '').lower()
            elif tag == 'N': d['name'] = val.partition('=')[2].strip().strip('"')
            elif tag == 'P': d['phys'] = val.partition('=')[2].strip()
            elif tag == 'S': d['sysfs'] = val.partition('=')[2].strip()
            elif tag == 'H': d['handlers'] = val.partition('=')[2].split()
            elif tag == 'B' and val.startswith('EV='): d['ev'] = _bits(val[3:])
            elif tag == 'B' and val.startswith('FF='): d['ff_line'] = val[3:].strip()
        if d['name'] or d['sysfs']: out.append(d)
    return out

def is_pad(d):
    # joydev gives every pad a jsN; a pad without joydev still has ABS axes and a pad-like name
    if any(re.fullmatch(r'js\d+', h) for h in d['handlers']): return True
    return bool(PAD_NAME.search(d['name'])) and not NOT_PAD.search(d['name']) and bool(d['ev'] & EV_ABS)

def _sys_path(sysroot, sysfs):
    # the device's own sysfs folder, kept inside sysroot (the path comes from the kernel, but a test copy is just files)
    root = os.path.realpath(os.path.join(sysroot or SYSROOT, 'sys'))
    p = os.path.realpath(os.path.join(root, sysfs.lstrip('/')))
    return p if os.path.commonpath([root, p]) == root else None

def rumble(d, sysroot=None):
    """True when an event node exists and the device's capabilities/ff is non-zero (falls back to /proc's 'B: FF=' line)."""
    if not any(re.fullmatch(r'event\d+', h) for h in d['handlers']): return False
    p = _sys_path(sysroot, d['sysfs']) if d['sysfs'] else None
    ff = _read(os.path.join(p, 'capabilities', 'ff')) if p else None
    if ff is None: ff = d['ff_line'] or ''
    return _bits(ff) != 0

def kind(d):
    """'steam-virtual' (Steam Input's copy of a pad), 'virtual' (another program's), or 'real' (a pad on a cable or dongle)."""
    virtual = d['sysfs'].startswith('/devices/virtual/')
    if virtual and STEAM_VIRTUAL.match(d['name']): return 'steam-virtual'
    return 'virtual' if virtual else 'real'

def registry(path=None):
    """The owner's slot map (~/.config/argus-ui/pads.json, docs/pads.example.json): (dict, problem or '')."""
    path = path or REGISTRY
    if not os.path.exists(path): return {}, ''
    try:
        with open(path, encoding='utf-8') as f: r = json.load(f)
        if not isinstance(r, dict): raise ValueError('not a JSON object')
    except (OSError, ValueError) as e: return {}, f'pads.json could not be read ({type(e).__name__})'
    return r, ''

def _ids(d): return f"{d['vid']}:{d['pid']}" if d['vid'] and d['pid'] else ''

def slot_for(d, reg):
    """(slot, label, order) from the registry's first matching entry. Matches: 'vvvv:pppp' (USB ids), 'phys:<text>'
    (part of the USB port path: the hub port is the player slot), anything else = part of the name. Case is ignored.
    Virtual pads never take a slot: they are copies of a real one, which has it."""
    if kind(d) != 'real': return None, '', 999
    for i, e in enumerate(reg.get('slots') or []):
        if not isinstance(e, dict) or not e.get('slot'): continue
        for m in e.get('match') or []:
            m = str(m).strip().lower()
            if not m: continue
            if re.fullmatch(r'[0-9a-f]{4}:[0-9a-f]{4}', m): hit = m == _ids(d)
            elif m.startswith('phys:'): hit = bool(m[5:]) and m[5:] in d['phys'].lower()
            else: hit = m in d['name'].lower()
            if hit: return str(e['slot'])[:12], str(e.get('label') or '')[:60], i
    return None, '', 999

def mode_for(d, reg):
    ids = _ids(d)
    extra = reg.get('modes') if isinstance(reg.get('modes'), dict) else {}
    name = MODES.get(ids) or (str(extra.get(ids))[:30] if extra.get(ids) else '')
    return name or f"Unknown ({ids or 'no ids'})"

def scan(sysroot=None, registry_path=None):
    """Everything the page shows: {ok, pads: [...], connected, virtual, wake_hint, problem}."""
    reg, problem = registry(registry_path)
    devs = devices(sysroot)
    hint = str(reg.get('wake_hint') or WAKE_HINT)[:200]
    if devs is None:
        return {'ok': False, 'pads': [], 'connected': 0, 'virtual': 0, 'wake_hint': hint,
                'problem': "Can't read /proc/bus/input/devices here: pads are read on the machine Elaia runs on (Linux)."}
    pads = []
    for d in devs:
        if not is_pad(d): continue
        slot, label, order = slot_for(d, reg)
        k = kind(d)
        pads.append({'slot': slot, 'label': label, 'name': d['name'] or 'Unnamed pad', 'ids': _ids(d), 'mode': mode_for(d, reg),
                     'known_mode': _ids(d) in MODES, 'kind': k, 'rumble': rumble(d, sysroot),
                     'nodes': [h for h in d['handlers'] if re.fullmatch(r'(js|event)\d+', h)], '_order': order})
    # slots in the registry's order, then the rest (real before virtual), each by name
    pads.sort(key=lambda p: (p['_order'], p['kind'] != 'real', p['name'].lower()))
    for p in pads: del p['_order']
    real = sum(p['kind'] == 'real' for p in pads)
    return {'ok': True, 'pads': pads, 'connected': real, 'virtual': len(pads) - real, 'wake_hint': hint, 'problem': problem}

def line(s):
    """Home's one line under the Pads place."""
    if not s['ok']: return "Can't read pads here"
    if not s['pads']: return 'No pads connected'
    t = f"{s['connected']} connected"
    steam = sum(p['kind'] == 'steam-virtual' for p in s['pads'])
    other = s['virtual'] - steam
    if steam: t += f' · {steam} Steam virtual'
    if other: t += f' · {other} virtual'
    return t

def get(path, query, ctx):
    if path == 'list': return 200, scan()
    if path == 'status': return 200, {'line': line(scan())}
    return 404, {'ok': False, 'msg': 'not found'}
