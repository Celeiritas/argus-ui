"""Mentor's exam-style items without a screen: the format "mentor-items/1", its rules, and scoring (docs/mentor-items.md).

Pure functions, standard library only, no file or network access. A screen, the importer and scripts/check-deck.py all
call this one module, so there is one set of rules.

    score(item, response)          -> {"points", "max", "per_part": [...]}   (a case adds "per_step")
    to_rating(points, max, ms, hints) -> "again" | "hard" | "good" | "easy"
    validate(item, sources=None)   -> [plain sentences]                       (empty = fine)
    validate_doc(doc)              -> [(item id or None, "N1".."N8", sentence)]   (a whole file)
    max_points(item)               -> the most score() can award, or None if the item's shape is broken

Every number is a whole number, so totals have no floating-point surprises. A bad response never raises out of score();
a bad item does (ItemError), because guessing at a broken item would hand out wrong marks."""
import datetime
import math
import re
from fractions import Fraction

FORMAT = 'mentor-items/1'
TYPES = ('mcq', 'sata', 'dropdown', 'matrix', 'bowtie', 'trend', 'case')
ANSWER_TYPES = ('mcq', 'sata', 'dropdown', 'matrix', 'bowtie')       # what a trend item may carry as its response format
STATUSES = ('unverified', 'source-checked', 'retired')
STEPS = ('recognize-cues', 'analyze-cues', 'prioritize-hypotheses', 'generate-solutions', 'take-action', 'evaluate-outcomes')
SCORING = {'mcq': ('zero_one',), 'sata': ('plus_minus', 'zero_one'), 'dropdown': ('zero_one', 'rationale'),
           'matrix': ('zero_one', 'plus_minus'), 'bowtie': ('zero_one',)}
BOWTIE = (('condition', 1), ('actions', 2), ('parameters', 2))       # group, how many to pick
RATINGS = ('again', 'hard', 'good', 'easy')
EASY_MS = 120_000
DATE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
MARK = re.compile(r'\{([^{}]+)\}')


class ItemError(ValueError):
    """The item itself is broken (its rules said so); there is no fair way to score it."""


# ---- small helpers ------------------------------------------------------------------------------------------------

def _dl(x):
    """The dicts of a list (anything else gives an empty list)."""
    return [e for e in x if isinstance(e, dict)] if isinstance(x, list) else []

def _s(x):
    """A non-empty text, or None."""
    return x if isinstance(x, str) and x.strip() else None

def _int(x):
    return x if isinstance(x, int) and not isinstance(x, bool) else None

def _kind(item):
    """The response format an item is scored as: its own type, or what a trend item carries."""
    t = item.get('type')
    return item.get('answer_type') if t == 'trend' else t

def _ids(entries):
    return [e['id'] for e in entries if _s(e.get('id'))]

def _keys(options):
    return [o['id'] for o in options if o.get('key') is True and _s(o.get('id'))]

def _bow(item, group):
    g = item.get(group)
    return g if isinstance(g, dict) else {}


# ---- how many points an item is worth -----------------------------------------------------------------------------

def max_points(item):
    """The most score() can award for this item, or None when the item's shape is too broken to say."""
    if not isinstance(item, dict): return None
    t = item.get('type')
    if t == 'case':
        parts = [max_points(i) for i in _dl(item.get('items'))]
        return None if not parts or None in parts else sum(parts)
    k = _kind(item)
    if k in ('mcq',): return 1 if _keys(_dl(item.get('options'))) else None
    if k == 'sata':
        n = len(_keys(_dl(item.get('options'))))
        return n or None
    if k == 'dropdown':
        lists = _dl(item.get('dropdowns'))
        if not lists: return None
        n = len(lists)
        if item.get('scoring') == 'rationale':
            for p in _dl(item.get('pairs')): n -= len(set(p.get('of') or [])) - 1 if isinstance(p.get('of'), list) else 0
        return n
    if k == 'matrix':
        rows = _dl(item.get('rows'))
        if not rows: return None
        if item.get('scoring') == 'plus_minus':
            return sum(len([c for c in r.get('keys') if _s(c)]) if isinstance(r.get('keys'), list) else 0 for r in rows) or None
        return len(rows)
    if k == 'bowtie':
        return sum(pick for _, pick in BOWTIE)
    return None


# ---- scoring ------------------------------------------------------------------------------------------------------

def _picks(v):
    """What a response put in one pick field: (distinct text ids in order, notes). A bare text is one pick; anything
    that is not text or a list of text is ignored (note "wrong type"); repeats count once (note "repeated pick")."""
    notes = []
    if v is None: return [], notes
    if isinstance(v, str): v = [v]
    if not isinstance(v, (list, tuple)): return [], ['wrong type']
    out = []
    for x in v:
        if not isinstance(x, str): notes.append('wrong type'); continue
        if x in out: notes.append('repeated pick'); continue
        out.append(x)
    return out, notes

def _group(part, options, picks, mode, limit=None):
    """Score one group of options. mode "plus_minus": +1 per right pick, -1 per wrong one. mode "zero_one": +1 per right
    pick; with limit n, more than n picks earn nothing. Unknown ids are ignored. Returns (sum of credits, per_part rows)."""
    known = {o['id']: o for o in options}
    rows, over = [], limit is not None and len([p for p in picks if p in known]) > limit
    total = 0
    for p in picks:
        if p not in known:
            rows.append({'part': part, 'pick': p, 'credit': 0, 'correct': False, 'reason': None, 'note': 'unknown option'})
            continue
        right = known[p].get('key') is True
        credit = 0 if over else (1 if right else (-1 if mode == 'plus_minus' else 0))
        total += credit
        rows.append({'part': part, 'pick': p, 'credit': credit, 'correct': right, 'reason': p, **({'note': 'too many picks'} if over else {})})
    for o in options:
        if o.get('key') is True and o['id'] not in picks:
            rows.append({'part': part, 'pick': None, 'credit': 0, 'correct': False, 'reason': o['id'], 'note': 'missed'})
    return total, rows

def _flag(rows, notes, part):
    for n in dict.fromkeys(notes):
        rows.append({'part': part, 'pick': None, 'credit': 0, 'correct': None, 'reason': None, 'note': n})

def _score_choice(item, picks_value):
    options = _dl(item.get('options'))
    picks, notes = _picks(picks_value)
    kind = _kind(item)
    if kind == 'mcq': pts, rows = _group('options', options, picks, 'zero_one', 1)
    elif item.get('scoring') == 'plus_minus': pts, rows = _group('options', options, picks, 'plus_minus')
    else: pts, rows = _group('options', options, picks, 'zero_one', _int(item.get('pick')))
    _flag(rows, notes, 'options')
    return max(0, pts), rows

def _score_dropdown(item, picks_value):
    resp = picks_value if isinstance(picks_value, dict) else {}
    lists, rows, right = _dl(item.get('dropdowns')), [], {}
    paired = {}
    if item.get('scoring') == 'rationale':
        for p in _dl(item.get('pairs')):
            for d in p.get('of') or []: paired[d] = p.get('id')
    pts = 0
    for d in lists:
        picks, notes = _picks(resp.get(d['id']))
        options = _dl(d.get('options'))
        known = {o['id']: o for o in options}
        good = len(picks) == 1 and picks[0] in known and known[picks[0]].get('key') is True
        right[d['id']] = good
        credit = 0 if d['id'] in paired else (1 if good else 0)
        pts += credit
        pick = picks[0] if picks and picks[0] in known and len(picks) == 1 else None
        key = next((o['id'] for o in options if o.get('key') is True), None)
        note = 'too many picks' if len(picks) > 1 else ('unknown option' if picks and picks[0] not in known else ('missed' if not picks else None))
        rows.append({'part': d['id'], 'pick': pick, 'credit': credit, 'correct': good, 'reason': pick or key,
                     **({'note': note} if note else {})})
        _flag(rows, [n for n in notes if n != 'wrong type' or not picks], d['id'])
    if item.get('scoring') == 'rationale':
        for p in _dl(item.get('pairs')):
            ok = all(right.get(d) for d in p['of'])
            pts += 1 if ok else 0
            rows.append({'part': p['id'], 'pick': None, 'credit': 1 if ok else 0, 'correct': ok, 'reason': None, 'of': list(p['of'])})
    return pts, rows

def _score_matrix(item, picks_value):
    resp = picks_value if isinstance(picks_value, dict) else {}
    cols = set(_ids(_dl(item.get('columns'))))
    pm = item.get('scoring') == 'plus_minus'
    pts, rows = 0, []
    for r in _dl(item.get('rows')):
        picks, notes = _picks(resp.get(r['id']))
        known = [p for p in picks if p in cols]
        note = 'unknown option' if len(known) < len(picks) else None
        keys = set(r.get('keys') or [])
        if pm:
            hit, wrong = len([p for p in known if p in keys]), len([p for p in known if p not in keys])
            credit, good = max(0, hit - wrong), hit == len(keys) and wrong == 0
        else:
            if len(known) > 1: credit, good, note = 0, False, 'too many picks'
            else: good = bool(known) and known[0] in keys; credit = 1 if good else 0
        if not known and not note: note = 'missed'
        pts += credit
        rows.append({'part': r['id'], 'pick': known, 'credit': credit, 'correct': good, 'reason': r['id'], **({'note': note} if note else {})})
        _flag(rows, [n for n in notes if n == 'repeated pick'], r['id'])
    return pts, rows

def _score_bowtie(item, picks_value):
    resp = picks_value if isinstance(picks_value, dict) else {}
    pts, rows = 0, []
    for group, pick in BOWTIE:
        picks, notes = _picks(resp.get(group))
        p, r = _group(group, _dl(_bow(item, group).get('options')), picks, 'zero_one', pick)
        pts += p; rows += r
        _flag(rows, notes, group)
    return pts, rows

def _score_one(item, response):
    resp = response if isinstance(response, dict) else {}
    value, kind = resp.get('picks'), _kind(item)
    if kind in ('mcq', 'sata'): pts, rows = _score_choice(item, value)
    elif kind == 'dropdown': pts, rows = _score_dropdown(item, value)
    elif kind == 'matrix': pts, rows = _score_matrix(item, value)
    else: pts, rows = _score_bowtie(item, value)
    if not isinstance(response, dict) or 'picks' not in resp:
        rows.append({'part': 'response', 'pick': None, 'credit': 0, 'correct': None, 'reason': None,
                     'note': 'no response' if response is None or not isinstance(response, dict) else 'no picks'})
    return pts, rows

def _structure(item, inner=False):
    """What scoring needs from an item (not its reasons or sources): the N2, N3, N6, N7 and N8 problems."""
    return [m for r, m in _problems(item, None, inner) if r in ('N2', 'N3', 'N6', 'N7', 'N8')]

def score(item, response, _inner=False):
    """Score one answer. item: a mentor-items/1 item. response: {"picks": ...} (a case: {"items": {item id: response}}).
    Returns {"points", "max", "per_part": [...]}: whole numbers; per_part rows say what was picked and whether it earned
    credit (docs/mentor-items.md). Raises ItemError only for a broken item; a bad response gets a defined result."""
    if not isinstance(item, dict): raise ItemError('The item is not an object.')
    bad = _structure(item, _inner)
    if bad: raise ItemError(bad[0] + (f' ({len(bad)} problems in all.)' if len(bad) > 1 else ''))
    if item['type'] == 'case':
        resp = response.get('items') if isinstance(response, dict) else None
        resp = resp if isinstance(resp, dict) else {}
        parts, steps, total, top = [], {s: {'points': 0, 'max': 0} for s in STEPS}, 0, 0
        for it in _dl(item.get('items')):
            r = score(it, resp.get(it['id']), True)
            total += r['points']; top += r['max']
            st = steps[it['ncjmm_step']]; st['points'] += r['points']; st['max'] += r['max']
            parts.append({'part': it['id'], 'step': it['ncjmm_step'], 'credit': r['points'], 'max': r['max'], 'per_part': r['per_part']})
        return {'points': total, 'max': top, 'per_part': parts, 'per_step': {s: v for s, v in steps.items() if v['max']}}
    pts, rows = _score_one(item, response)
    return {'points': pts, 'max': max_points(item), 'per_part': rows}


def _num(x):
    return Fraction(x) if isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) else None

def to_rating(points, max, ms, hints):
    """The memory-schedule rating for a score: under 50 % "again"; 50 % up to under 100 % "hard"; 100 % "good"; 100 %
    with no hint in under 120 000 ms "easy" (a time of 0 or less means the timer did not run: it counts as unknown). Not a number, or nothing to score: "again". (mentor.py calls them 1 to 4.)"""
    p, m = _num(points), _num(max)
    if p is None or m is None or m <= 0: return 'again'
    p = min(max_(p, 0), m)
    if p * 2 < m: return 'again'
    if p < m: return 'hard'
    t, h = _num(ms), _num(hints)
    return 'easy' if h == 0 and t is not None and 0 < t < EASY_MS else 'good'

def max_(a, b):      # to_rating's own argument is called max, as the brief writes it
    return a if a > b else b


# ---- rules --------------------------------------------------------------------------------------------------------

def _problems(item, sources, inner=False, seen=None):
    """Every problem of one item as (rule, plain sentence). sources: the file's {id: {url, read}} or None (not checked)."""
    out = []
    if not isinstance(item, dict): return [('N2', 'An item is not an object.')]
    iid, t = _s(item.get('id')), item.get('type')
    who = f'Item "{iid}"' if iid else 'An item with no id'
    add = lambda rule, msg: out.append((rule, f'{who}: {msg}'))
    if not iid: add('N2', 'has no id.')
    elif seen is not None:
        if iid in seen: add('N3', 'its id is used by another item in this file.')
        seen.add(iid)
    if t not in TYPES: add('N2', f'its type "{t}" is not one of {", ".join(TYPES)}.'); return out
    if not inner:
        if item.get('status') not in STATUSES: add('N2', f'its status must be one of {", ".join(STATUSES)}.')
        if not _s(item.get('client_needs')): add('N2', 'has no client_needs (the test-plan area it belongs to).')
    if t == 'case':
        if item.get('ncjmm_step') not in STEPS + ('all',): add('N2', 'its ncjmm_step must be "all" or one of the six steps.')
    elif item.get('ncjmm_step') not in STEPS + (('all',) if t == 'bowtie' else ()):
        add('N2', f'its ncjmm_step must be one of {", ".join(STEPS)}' + (' (or "all")' if t == 'bowtie' else '') + '.')
    if t == 'case': return out + _case(item, sources, who, seen)
    if not _s(item.get('stem')): add('N2', 'has no stem (the question).')
    kind = t
    if t == 'trend':
        kind = item.get('answer_type')
        if kind not in ANSWER_TYPES: add('N2', f'a trend item needs answer_type, one of {", ".join(ANSWER_TYPES)}.'); return out
        ex = item.get('exhibit')
        cols = ex.get('columns') if isinstance(ex, dict) else None
        rows = ex.get('rows') if isinstance(ex, dict) else None
        if not (isinstance(cols, list) and cols and isinstance(rows, list) and rows):
            add('N2', 'a trend item needs an exhibit with columns and rows.')
        elif any(not isinstance(r, list) or len(r) != len(cols) for r in rows):
            add('N2', 'every row of its exhibit needs one cell for each column.')
    if item.get('scoring') not in SCORING[kind]:
        add('N2', f'scoring "{item.get("scoring")}" does not fit a {kind} item (use {" or ".join(SCORING[kind])}).')
    if _int(item.get('max_points')) is None: add('N2', 'has no max_points (a whole number).')
    shape = _shape(item, kind, who, out)
    if shape:
        want = max_points(item)
        if want is not None and _int(item.get('max_points')) is not None and item['max_points'] != want:
            add('N7', f'max_points says {item["max_points"]} but the scoring can award {want}.')
    _reasons(item, kind, who, sources, out)
    return out

def _shape(item, kind, who, out):
    """N2/N3/N6 for the answer structure of one item. Returns False when it is too broken to compute points."""
    add = lambda rule, msg: out.append((rule, f'{who}: {msg}'))
    ok = True
    def options(label, opts, need, ids_seen=None):
        nonlocal ok
        raw = opts
        opts = _dl(opts)
        if not isinstance(raw, list) or len(opts) != len(raw) or len(opts) < need:
            add('N2', f'{label} needs a list of at least {need} options, each an object.'); ok = False; return []
        ids = [o.get('id') for o in opts]
        if any(not _s(i) for i in ids): add('N3', f'every option in {label} needs an id.'); ok = False
        elif len(set(ids)) != len(ids): add('N3', f'option ids repeat in {label}.'); ok = False
        if any(not isinstance(o.get('key'), bool) for o in opts): add('N2', f'every option in {label} needs "key": true or false.'); ok = False
        return opts
    if kind in ('mcq', 'sata'):
        opts = options('options', item.get('options'), 2)
        keys = len([o for o in opts if o.get('key') is True])
        if opts and ok:
            if keys == 0: add('N6', 'has no right answer.')
            elif kind == 'mcq' and keys != 1: add('N6', f'a multiple-choice item has exactly one right answer, not {keys}.')
            elif kind == 'sata' and keys == len(opts): add('N6', 'every option is marked right; a select-all item with all options right is refused.')
            if kind == 'sata' and item.get('scoring') == 'zero_one' and _int(item.get('pick')) != keys:
                add('N6', f'with zero_one scoring, "pick" must equal the number of right options ({keys}).')
    elif kind == 'dropdown':
        lists, tpl = item.get('dropdowns'), item.get('template')
        if not _s(tpl): add('N2', 'has no template (the sentence with {list-id} marks).'); ok = False
        if not isinstance(lists, list) or not _dl(lists) or len(_dl(lists)) != len(lists):
            add('N2', 'needs a list of dropdowns, each an object.'); return False
        ids = [d.get('id') for d in lists]
        if any(not _s(i) for i in ids): add('N3', 'every drop-down list needs an id.'); ok = False
        elif len(set(ids)) != len(ids): add('N3', 'drop-down list ids repeat.'); ok = False
        if _s(tpl) and ok:
            marks = MARK.findall(tpl)
            if sorted(marks) != sorted(ids): add('N2', 'the template must mark each list exactly once, as {list-id}.')
        for d in lists:
            opts = options(f'drop-down list "{d.get("id")}"', d.get('options'), 2)
            if opts and ok:
                k = len([o for o in opts if o.get('key') is True])
                if k != 1: add('N6', f'list "{d.get("id")}" needs exactly one right answer, not {k}.')
        pairs = item.get('pairs')
        if item.get('scoring') == 'rationale':
            ps = _dl(pairs)
            if not isinstance(pairs, list) or not ps or len(ps) != len(pairs): add('N2', 'rationale scoring needs "pairs", a list of {id, of: [list id, list id]}.'); ok = False
            else:
                used = []
                for p in ps:
                    of = p.get('of')
                    if not _s(p.get('id')): add('N3', 'every pair needs an id.'); ok = False
                    if not (isinstance(of, list) and len(of) == 2 and len(set(map(str, of))) == 2 and all(x in ids for x in of)):
                        add('N2', 'every pair joins two different drop-down lists of this item.'); ok = False
                    else: used += of
                if len(used) != len(set(used)): add('N2', 'a drop-down list can be in only one pair.'); ok = False
        elif pairs is not None: add('N2', 'has pairs, but only rationale scoring uses them.')
    elif kind == 'matrix':
        cols, rows = item.get('columns'), item.get('rows')
        if not isinstance(cols, list) or len(_dl(cols)) != len(cols) or len(cols) < 2: add('N2', 'needs a list of at least two columns, each an object.'); return False
        if not isinstance(rows, list) or not _dl(rows) or len(_dl(rows)) != len(rows): add('N2', 'needs a list of rows, each an object.'); return False
        cid, rid = [c.get('id') for c in cols], [r.get('id') for r in rows]
        for label, ids in (('column', cid), ('row', rid)):
            if any(not _s(i) for i in ids): add('N3', f'every {label} needs an id.'); ok = False
            elif len(set(ids)) != len(ids): add('N3', f'{label} ids repeat.'); ok = False
        if ok:
            for r in rows:
                k = r.get('keys')
                if not (isinstance(k, list) and k and all(x in cid for x in k) and len(set(k)) == len(k)):
                    add('N6', f'row "{r["id"]}" needs "keys", a list of one or more of its column ids.'); ok = False
                elif item.get('scoring') == 'zero_one' and len(k) != 1:
                    add('N6', f'row "{r["id"]}" has {len(k)} right columns; zero_one scoring allows one tick per row (use plus_minus).'); ok = False
    elif kind == 'bowtie':
        for g, pick in BOWTIE:
            grp = item.get(g)
            if not isinstance(grp, dict): add('N2', f'needs a "{g}" group.'); ok = False; continue
            if grp.get('pick') != pick: add('N2', f'"{g}" must say "pick": {pick}.'); ok = False
            opts = options(f'"{g}"', grp.get('options'), pick + 1)
            k = len([o for o in opts if o.get('key') is True])
            if opts and ok and k == 0: add('N6', f'"{g}" has no right answer.')
            elif opts and ok and k != pick: add('N6', f'"{g}" picks {pick} but marks {k} options right.')
    return ok

def _reasons(item, kind, who, sources, out):
    """N4 (a reason on every option and row) and N5 (src ids that resolve)."""
    add = lambda rule, msg: out.append((rule, f'{who}: {msg}'))
    units = []
    if kind in ('mcq', 'sata'): units = [('option', o) for o in _dl(item.get('options'))]
    elif kind == 'dropdown': units = [('option', o) for d in _dl(item.get('dropdowns')) for o in _dl(d.get('options'))]
    elif kind == 'matrix': units = [('row', r) for r in _dl(item.get('rows'))]
    elif kind == 'bowtie': units = [('option', o) for g, _ in BOWTIE for o in _dl(_bow(item, g).get('options'))]
    for what, u in units:
        name = f'{what} "{u.get("id")}"'
        if not _s(u.get('reason')): add('N4', f'{name} has no reason (every option, right or wrong, needs one).')
        src = u.get('src')
        if not (isinstance(src, list) and src and all(_s(x) for x in src)):
            add('N5', f'{name} has no src (a list of source ids).')
        elif sources is not None:
            for sid in src:
                e = sources.get(sid) if isinstance(sources, dict) else None
                if not isinstance(e, dict): add('N5', f'{name} cites source "{sid}", which is not in the file\'s sources.')
                elif not (_s(e.get('url')) and _s(e.get('read'))): add('N5', f'{name} cites source "{sid}", which lacks a url or a read date.')

def _case(item, sources, who, seen):
    out = []
    add = lambda rule, msg: out.append((rule, f'{who}: {msg}'))
    items = item.get('items')
    if item.get('scoring') is not None: add('N2', 'a case is scored item by item and has no scoring of its own.')
    if _int(item.get('max_points')) is None: add('N2', 'has no max_points (a whole number).')
    if not _s(item.get('scenario')): add('N2', 'has no scenario.')
    if not isinstance(items, list) or not _dl(items) or len(_dl(items)) != len(items):
        add('N8', 'needs "items", a list of the case\'s items.'); return out
    free = item.get('order') == 'free'
    if len(items) != 6 and not free: add('N8', f'a case has 6 items, one for each step (this one has {len(items)}); set "order": "free" to allow another number.')
    steps = [i.get('ncjmm_step') for i in items]
    if not free and steps != list(STEPS): add('N8', 'its items must follow the six steps in order: ' + ', '.join(STEPS) + '.')
    elif free and any(s not in STEPS for s in steps): add('N8', 'every item of a case needs one of the six steps as ncjmm_step.')
    ids = [i.get('id') for i in items if _s(i.get('id'))]
    if len(set(ids)) != len(ids): add('N3', 'two of its items have the same id (answers are stored by item id).')
    for i in items:
        if i.get('type') == 'case': add('N8', 'a case cannot contain another case.'); continue
        out += _problems(i, sources, True, seen)
    total = max_points(item)
    if item.get('max_points') is not None and total is not None and item['max_points'] != total:
        add('N7', f'max_points says {item["max_points"]} but its items add up to {total}.')
    return out

def validate(item, sources=None):
    """Every problem with one item, as plain sentences; an empty list means the item is fine. sources: the file's sources
    ({id: {url, read}}); when given, src ids are looked up there (N5)."""
    return [m for _, m in _problems(item, sources)]


def _date(s):
    if not (isinstance(s, str) and DATE.match(s)): return False
    try: datetime.date.fromisoformat(s)
    except ValueError: return False
    return True

def validate_doc(doc):
    """A whole file: [(item id or None, rule, sentence)]. N1 is the file itself; the rest are per item (docs/mentor-items.md)."""
    out = []
    if not isinstance(doc, dict): return [(None, 'N1', 'The file is not an object.')]
    if doc.get('format') != FORMAT: out.append((None, 'N1', f'"format" must be "{FORMAT}".'))
    if not _s(doc.get('disclaimer')): out.append((None, 'N1', 'The file has no disclaimer (the line every screen shows).'))
    sources = doc.get('sources')
    if not isinstance(sources, dict) or not sources:
        out.append((None, 'N5', 'The file has no sources (an object of {id: {title, url, read}}).')); sources = {}
    for sid, e in sources.items():
        if not isinstance(e, dict) or not _s(e.get('url')): out.append((None, 'N5', f'Source "{sid}" has no url.'))
        elif not _date(e.get('read')): out.append((None, 'N5', f'Source "{sid}" needs "read", the date it was read, as YYYY-MM-DD.'))
    items = doc.get('items')
    if not isinstance(items, list) or not items: return out + [(None, 'N1', 'The file has no items (a list).')]
    seen = set()
    for it in items:
        iid = it.get('id') if isinstance(it, dict) else None
        for rule, msg in _problems(it, sources, False, seen): out.append((iid if _s(iid) else None, rule, msg))
    return out
