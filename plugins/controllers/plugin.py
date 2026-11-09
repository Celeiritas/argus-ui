# Leafy Controllers: which game controllers this machine sees right now, read-only (docs/controllers.md).
# A bundled server plugin (docs/leafy-plugin.md): GET api/controllers/list (the rows) and api/controllers/status (Home's line).
# Everything comes from two kernel views, read on every request, never written and never through a shell:
#   /proc/bus/input/devices          one block per input device: ids, name, phys, sysfs path, handlers (event, js)
#   /sys/<that sysfs path>/capabilities/ff   force-feedback bits: non-zero means rumble can reach the controller
# The probe is a port of the owner's read-only shell check (controllers section): name, real or virtual, rumble.
# `sysroot` points both at a copy for tests (tests/fixtures/controllers-sysfs/); ARGUS_CONTROLLERS_SYSROOT does it for the server.
# Until 4.33.0 this section was called Pads: where() still reads the old names for one release (docs/controllers.md).
import json, os, re

# The names from before 4.33.0 and what each is called now. An old one is read only while its new one is absent.
RENAMED = {'ARGUS_PADS_SYSROOT': 'ARGUS_CONTROLLERS_SYSROOT', 'ARGUS_PADS': 'ARGUS_CONTROLLERS', 'pads.json': 'controllers.json'}

# The OpenPuck (a Steam Controller dongle) changes its USB ids with its mode, so the ids name the mode.
MODES = {'28de:1304': 'Steam', '045e:028e': 'Xbox 360', '2e8a:10c6': 'SInput', '0f0d:0092': 'Switch'}
# Steam Input's virtual controllers: Steam makes one "Microsoft X-Box 360 pad N" per controller it takes over, under /sys/devices/virtual/
STEAM_VIRTUAL = re.compile(r'^Microsoft X-Box 360 pad \d+$')
# names that are controllers even without a js handler (the shell check's list); their mouse and keyboard parts have no ABS axes
CONTROLLER_NAME = re.compile(r'steam|x-?box|puck|pro controller|sony|dualsense|hori|sinput|gamepad|joy-?con|8bitdo', re.I)
NOT_CONTROLLER = re.compile(r'(touchpad|motion sensors|mouse|keyboard|consumer control|system control)$', re.I)
WAKE_HINT = "Press a controller's Home or Steam button to wake it. Still missing? Check that its cable or dongle is in the hub."
EV_ABS = 0x08

def where(env=None, config=None):
    """(sysroot, slot map path, old names in use), asked on every request so a renamed file counts without a restart.
    Settings: ARGUS_CONTROLLERS_SYSROOT (default /) and ARGUS_CONTROLLERS (default controllers.json in ~/.config/argus-ui/).
    Old names, read for one release when the new one is absent: ARGUS_PADS_SYSROOT, ARGUS_PADS, and pads.json in that folder."""
    env = os.environ if env is None else env
    old = []
    def setting(new):
        was = next(o for o, n in RENAMED.items() if n == new)
        if env.get(new): return env[new]
        if env.get(was): old.append(was); return env[was]
        return ''
    sysroot = setting('ARGUS_CONTROLLERS_SYSROOT') or '/'
    path = os.path.expanduser(setting('ARGUS_CONTROLLERS'))
    if not path:
        config = config or os.path.join(os.path.expanduser('~'), '.config', 'argus-ui')
        path, was = os.path.join(config, 'controllers.json'), os.path.join(config, 'pads.json')
        if not os.path.exists(path) and os.path.exists(was): path = was; old.append('pads.json')
    return sysroot, path, old

def notice(old):
    """One line for the page while a name from before 4.33.0 is still in use; '' when none is."""
    if not old: return ''
    return (f"Old name{'s' if len(old) > 1 else ''} still in use: " + ', '.join(f'{o} (now {RENAMED[o]})' for o in old)
            + '. This is the last release that reads old names.')

def _read(path):
    try:
        with open(path, encoding='utf-8', errors='replace') as f: return f.read()
    except OSError: return None

def _bits(words):
    """A capability bitmap as the kernel prints it (hex words, highest first) -> int; '' or garbage -> 0."""
    try: return int(''.join(w.rjust(16, '0') for w in words.split()) or '0', 16)
    except ValueError: return 0

def devices(sysroot='/'):
    """Every input device in /proc/bus/input/devices as a dict, or None when the file can't be read (not Linux)."""
    text = _read(os.path.join(sysroot, 'proc', 'bus', 'input', 'devices'))
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

def is_controller(d):
    # joydev gives every controller a jsN; one without joydev still has ABS axes and a controller-like name
    if any(re.fullmatch(r'js\d+', h) for h in d['handlers']): return True
    return bool(CONTROLLER_NAME.search(d['name'])) and not NOT_CONTROLLER.search(d['name']) and bool(d['ev'] & EV_ABS)

def _sys_path(sysroot, sysfs):
    # the device's own sysfs folder, kept inside sysroot (the path comes from the kernel, but a test copy is just files)
    root = os.path.realpath(os.path.join(sysroot, 'sys'))
    p = os.path.realpath(os.path.join(root, sysfs.lstrip('/')))
    return p if os.path.commonpath([root, p]) == root else None

def rumble(d, sysroot='/'):
    """True when an event node exists and the device's capabilities/ff is non-zero (falls back to /proc's 'B: FF=' line)."""
    if not any(re.fullmatch(r'event\d+', h) for h in d['handlers']): return False
    p = _sys_path(sysroot, d['sysfs']) if d['sysfs'] else None
    ff = _read(os.path.join(p, 'capabilities', 'ff')) if p else None
    if ff is None: ff = d['ff_line'] or ''
    return _bits(ff) != 0

def kind(d):
    """'steam-virtual' (Steam Input's copy of a controller), 'virtual' (another program's), or 'real' (on a cable or dongle)."""
    virtual = d['sysfs'].startswith('/devices/virtual/')
    if virtual and STEAM_VIRTUAL.match(d['name']): return 'steam-virtual'
    return 'virtual' if virtual else 'real'

def registry(path):
    """The owner's slot map (~/.config/argus-ui/controllers.json, docs/controllers.example.json): (dict, problem or '')."""
    if not os.path.exists(path): return {}, ''
    try:
        with open(path, encoding='utf-8') as f: r = json.load(f)
        if not isinstance(r, dict): raise ValueError('not a JSON object')
    except (OSError, ValueError) as e: return {}, f'{os.path.basename(path)} could not be read ({type(e).__name__})'
    return r, ''

def _ids(d): return f"{d['vid']}:{d['pid']}" if d['vid'] and d['pid'] else ''

def slot_for(d, reg):
    """(slot, label, order) from the registry's first matching entry. Matches: 'vvvv:pppp' (USB ids), 'phys:<text>'
    (part of the USB port path: the hub port is the player slot), anything else = part of the name. Case is ignored.
    Virtual controllers never take a slot: they are copies of a real one, which has it."""
    if kind(d) != 'real': return None, '', 999
    for i, e in enumerate(reg.get('slots') or []):
        if not isinstance(e, dict) or not e.get('slot'): continue
        ms = e.get('match')
        ms = [ms] if isinstance(ms, str) else (ms if isinstance(ms, list) else [])  # "match": "puck" = one pattern, never per letter
        for m in ms:
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

def scan(sysroot, registry_path, old=()):
    """Everything the page shows: {ok, controllers: [...], connected, virtual, wake_hint, problem, notice}.
    The three arguments are what where() returns."""
    reg, problem = registry(registry_path)
    devs = devices(sysroot)
    hint = str(reg.get('wake_hint') or WAKE_HINT)[:200]
    if devs is None:
        return {'ok': False, 'controllers': [], 'connected': 0, 'virtual': 0, 'wake_hint': hint, 'notice': notice(old),
                'problem': "Can't read /proc/bus/input/devices here: controllers are read on the machine Elaia runs on (Linux)."}
    found = []
    for d in devs:
        if not is_controller(d): continue
        slot, label, order = slot_for(d, reg)
        k = kind(d)
        found.append({'slot': slot, 'label': label, 'name': d['name'] or 'Unnamed controller', 'ids': _ids(d), 'mode': mode_for(d, reg),
                      'known_mode': _ids(d) in MODES, 'kind': k, 'rumble': rumble(d, sysroot),
                      'nodes': [h for h in d['handlers'] if re.fullmatch(r'(js|event)\d+', h)], '_order': order})
    # slots in the registry's order, then the rest (real before virtual), each by name
    found.sort(key=lambda c: (c['_order'], c['kind'] != 'real', c['name'].lower()))
    for c in found: del c['_order']
    real = sum(c['kind'] == 'real' for c in found)
    return {'ok': True, 'controllers': found, 'connected': real, 'virtual': len(found) - real, 'wake_hint': hint, 'problem': problem,
            'notice': notice(old)}

def line(s):
    """Home's one line under the Controllers place."""
    if not s['ok']: return "Can't read controllers here"
    if not s['controllers']: return 'No controllers connected'
    t = f"{s['connected']} connected"
    steam = sum(c['kind'] == 'steam-virtual' for c in s['controllers'])
    other = s['virtual'] - steam
    if steam: t += f' · {steam} Steam virtual'
    if other: t += f' · {other} virtual'
    return t

def get(path, query, ctx):
    if path == 'list': return 200, scan(*where())
    if path == 'status': return 200, {'line': line(scan(*where()))}
    return 404, {'ok': False, 'msg': 'not found'}
