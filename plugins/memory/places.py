"""Mnemosyne reading places kept on the server, per person (4.67.0, docs/mnemosyne-library.md).

One JSON file, {person: {'recent': [...], 'saved': [...]}}. A row is {'id', 'revision', 'offset', 'at'}: ids and a
section number only, never a title or text. `at` is the server's UTC time, so the newest save wins on every device.
Recent is newest first (10 rows), saved places newest last (100 rows). Writes go to a temp file and replace the old one
under one lock; a file that cannot be read is moved aside as mnemosyne-places.broken-<time>.json and treated as empty."""
import json, os, re, tempfile, threading
from datetime import datetime, timezone

NAME = 'mnemosyne-places.json'
LIMITS = {'recent': 10, 'saved': 100}
HEX = re.compile(r'^[a-f0-9]{64}$')
MAX_OFFSET = 100000
_lock = threading.Lock()


def _row(raw):
    """A clean row, or None when anything about it is wrong."""
    if not isinstance(raw, dict): return None
    id_, rev, off, at = raw.get('id'), raw.get('revision'), raw.get('offset'), raw.get('at')
    if not (isinstance(id_, str) and HEX.match(id_) and isinstance(rev, str) and HEX.match(rev)): return None
    if type(off) is not int or not 0 <= off <= MAX_OFFSET: return None
    if not isinstance(at, str) or len(at) > 40: return None
    return {'id': id_, 'revision': rev, 'offset': off, 'at': at}


def _read(path):
    try:
        with open(path, encoding='utf-8') as f: data = json.load(f)
        if not isinstance(data, dict): raise ValueError('not an object')
        return data
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        try: os.replace(path, os.path.join(os.path.dirname(path), f'mnemosyne-places.broken-{stamp}.json'))
        except OSError: pass
        return {}


def _lists(data, person):
    mine = data.get(person) if isinstance(data.get(person), dict) else {}
    out = {}
    for kind, limit in LIMITS.items():
        rows = mine.get(kind) if isinstance(mine.get(kind), list) else []
        out[kind] = [r for r in map(_row, rows) if r][:limit] if kind == 'recent' else [r for r in map(_row, rows) if r][-limit:]
    return out


def load(path, person):
    with _lock: return _lists(_read(path), person)


def put(path, person, kind, row):
    """Store one row for this person and return their new lists. ValueError on a bad kind or row."""
    if not isinstance(kind, str) or kind not in LIMITS or not isinstance(row, dict): raise ValueError('kind')
    clean = _row({**row, 'at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')})
    if not clean: raise ValueError('row')
    with _lock:
        data = _read(path)
        lists = _lists(data, person)
        rows = [r for r in lists[kind] if r['id'] != clean['id']]
        rows = ([clean] + rows)[:LIMITS[kind]] if kind == 'recent' else (rows + [clean])[-LIMITS[kind]:]
        lists[kind] = rows
        data[person] = lists
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix='.mnemosyne-places-', suffix='.json', dir=os.path.dirname(path) or '.')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f: json.dump(data, f, separators=(',', ':'))
            os.replace(tmp, path)
        except BaseException:
            try: os.unlink(tmp)
            except OSError: pass
            raise
        return lists
