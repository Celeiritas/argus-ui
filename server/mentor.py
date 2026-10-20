"""Mentor - the study coach behind the Practice page: learn the code you build with an AI. Python standard library only.

What it teaches (see docs/mentor.md): each "code module" is a Cognitive Task Analysis of real code, written by the
/mentor command in Claude Code (docs/mentor-command.md) as JSON. A module has three tiers of cards:
  Tier 1  drill    faded worked examples: a 5-15 line snippet with blanks, level 1 (endings) -> 2 (logic) -> 3 (whole body)
  Tier 2  explain  self-explanation: find the bug (pre-mortem), why this design (trade-off), human factors link
  Tier 3  term     vocabulary: a cloze sentence; the feedback shows the definition, where it is in your code, its look-alike
Plain decks (kind "define", the older format) still work and mix in with the modules.

Order of study: inside a module, new cards unlock terms -> drills -> explain cards (pre-training first, Mayer & Pilegard
2014). Reviews interleave: the next due card comes from a different module or deck when one is due (Bjork & Bjork 2011).
Drills move up a level when you get every blank right fast, or right twice in a row; "Needs work" moves them down.

Grading roadmap (each stage keeps the data the next one learns from):
  A    rubric grader (this file): key ideas + accepted wordings; drill blanks compared as code; whole bodies parsed with ast.
  B    local similarity model: adds a meaning-based score as one more feature.
  Bv2  learned grader: a small model trained on YOUR attempts (features + final rating + "grade was wrong" flags).
Every attempt is stored with its features and your labels in the `attempts` table, from day one. Code you type is
only parsed, never run.

Code modules arrive in the inbox folder (~/.local/share/argus-ui/inbox, or ARGUS_MENTOR_INBOX). It is checked every
time the page asks for a card, so a copied-in file shows up without a restart. Files are read, never moved or deleted.

The server's routes are fixed (decks, next, stats, answer, rate); a drill's blanks arrive in `answer` as a JSON list.
Scheduling: FSRS-4.5 (Free Spaced Repetition Scheduler) with its published default weights.
"""
import ast, io, json, math, os, re, sqlite3, textwrap, threading, time, glob, tokenize
from difflib import SequenceMatcher

DB_LOCK = threading.Lock()
INBOX = os.path.expanduser(os.environ.get('ARGUS_MENTOR_INBOX', '~/.local/share/argus-ui/inbox'))
TIER = {'term': 3, 'drill': 1, 'explain': 2, 'define': 3}
FUNNEL = {'term': 0, 'drill': 1, 'explain': 2}       # new cards in a module unlock in this order
LEVELS = {1: 'Fill in the endings', 2: 'Fill in the logic', 3: 'Write the body'}

# ---------- storage ----------
SCHEMA = """
CREATE TABLE IF NOT EXISTS cards(
  id TEXT PRIMARY KEY, deck TEXT, kind TEXT, prompt TEXT, answer TEXT, points TEXT, tags TEXT, updated REAL);
CREATE TABLE IF NOT EXISTS sched(
  card_id TEXT PRIMARY KEY, stability REAL, difficulty REAL, due REAL, last REAL, reps INTEGER, lapses INTEGER);
CREATE TABLE IF NOT EXISTS attempts(
  id INTEGER PRIMARY KEY AUTOINCREMENT, card_id TEXT, at REAL, answer TEXT, confidence INTEGER, ms INTEGER,
  coverage REAL, hits TEXT, missed TEXT, features TEXT, suggested INTEGER, rating INTEGER, grade_wrong INTEGER,
  grader TEXT);
CREATE TABLE IF NOT EXISTS modules(
  id TEXT PRIMARY KEY, name TEXT, project TEXT, built_in INTEGER, at REAL, summary TEXT, concepts TEXT, files TEXT, source TEXT);
CREATE TABLE IF NOT EXISTS imports(
  path TEXT PRIMARY KEY, mtime REAL, size INTEGER, ok INTEGER, msg TEXT, module TEXT, at REAL);
"""
# columns added after 4.5 (older databases get them on start; nothing is lost)
ADDED = [('cards', 'data', "TEXT DEFAULT '{}'"), ('cards', 'ord', 'INTEGER DEFAULT 0'),
         ('sched', 'level', 'INTEGER DEFAULT 1'), ('attempts', 'kind', 'TEXT'), ('attempts', 'level', 'INTEGER')]

def connect(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    db = sqlite3.connect(path, check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    for table, col, decl in ADDED:
        if col not in {r[1] for r in db.execute(f"PRAGMA table_info({table})")}:
            db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
    db.commit()
    try: os.makedirs(INBOX, exist_ok=True)
    except OSError: pass
    return db

def load_decks(db, folder):
    """Upsert every deck JSON file in folder (plain decks and built-in code modules). History stays."""
    n = 0
    for f in sorted(glob.glob(os.path.join(folder, '*.json'))):
        try:
            with open(f, encoding='utf-8') as fh: deck = json.load(fh)
        except Exception:
            continue
        if is_module(deck):
            with DB_LOCK: n += import_module(db, deck, slug(os.path.basename(f)[:-5]), f, True)[0]
            continue
        for c in deck.get('cards', []):
            cid = f"{deck['id']}:{c['id']}"
            upsert_card(db, cid, deck['id'], c.get('kind', 'define'), c['prompt'], c['answer'], c.get('points', []), {},
                        c.get('tags', []), 0)
            n += 1
    db.commit()
    return n

def upsert_card(db, cid, deck, kind, prompt, answer, points, data, tags, ord_):
    db.execute("INSERT INTO cards(id,deck,kind,prompt,answer,points,tags,updated,data,ord) VALUES(?,?,?,?,?,?,?,?,?,?) "
               "ON CONFLICT(id) DO UPDATE SET deck=excluded.deck,kind=excluded.kind,prompt=excluded.prompt,"
               "answer=excluded.answer,points=excluded.points,tags=excluded.tags,updated=excluded.updated,"
               "data=excluded.data,ord=excluded.ord",
               (cid, deck, kind, prompt, answer, json.dumps(points), json.dumps(tags), time.time(), json.dumps(data), ord_))

def deck_list(folder):
    """Plain decks only; code modules are listed by stats() (they also come from the inbox)."""
    out = []
    for f in sorted(glob.glob(os.path.join(folder, '*.json'))):
        try:
            with open(f, encoding='utf-8') as fh: d = json.load(fh)
            if is_module(d): continue
            out.append({'id': d['id'], 'name': d.get('name', d['id']), 'blurb': d.get('blurb', ''), 'count': len(d.get('cards', []))})
        except Exception:
            pass
    return out

# ---------- code modules (the /mentor command's JSON) ----------
def slug(s):
    return re.sub(r'[^a-z0-9_-]+', '-', str(s).lower()).strip('-')[:80] or 'module'

def is_module(doc):
    return isinstance(doc, dict) and any(k in doc for k in ('tier_1_faded_code_drills', 'tier_2_self_explanation_cards',
                                                             'tier_3_terminology_cards', 'faded_code_drills', 'cta_summary'))

BLANK = re.compile(r'\{\{\s*BLANK(?:_(\d+))?\s*\}\}')

def blanks_in(code):
    return [int(m.group(1) or 1) for m in BLANK.finditer(code or '')]

def as_list(v):
    return v if isinstance(v, list) else [] if v is None else [v]

def import_module(db, doc, mid, source, built_in):
    """Turn one module JSON into cards. Returns (cards added, notes about anything skipped). Caller holds DB_LOCK."""
    meta = doc.get('metadata') if isinstance(doc.get('metadata'), dict) else {}
    name = str(meta.get('module_name') or doc.get('module_name') or mid).replace('_', ' ')
    summary = doc.get('cta_summary') if isinstance(doc.get('cta_summary'), dict) else {}
    cards, notes = [], []
    terms = as_list(doc.get('tier_3_terminology_cards'))
    for i, t in enumerate(terms):
        if not isinstance(t, dict) or not str(t.get('term', '')).strip():
            notes.append(f'term {i + 1}: no term'); continue
        term = str(t['term']).strip()
        cloze = str(t.get('cloze_prompt') or '')
        if not BLANK.search(cloze):
            cloze = f"{t.get('concise_definition') or 'Name the term.'} This is called {{{{BLANK}}}}."
        data = {k: str(t.get(src) or '') for k, src in (('category', 'category'), ('definition', 'concise_definition'),
                ('anchor', 'project_anchor'), ('contrast', 'contrast_anchor'))}
        cards.append((t.get('id') or f'term_{i + 1:02}', 'term', cloze, term, [], data, i))
    for i, d in enumerate(as_list(doc.get('tier_1_faded_code_drills') or doc.get('faded_code_drills'))):
        if not isinstance(d, dict) or not d.get('full_canonical_code'):
            notes.append(f'drill {i + 1}: no code'); continue
        ans = d.get('answers') if isinstance(d.get('answers'), dict) else {}
        fades = {}
        for lv in (1, 2, 3):
            code, a = d.get(f'level_{lv}_fade'), as_list(ans.get(f'level_{lv}'))
            n = len(set(blanks_in(code)))
            if code and n and n == len(a) and (lv < 3 or n == 1):
                fades[lv] = {'code': str(code), 'answers': [x if isinstance(x, list) else str(x) for x in a]}
            elif code:
                notes.append(f"drill {i + 1} level {lv}: {n} blank{'s' if n != 1 else ''} but {len(a)} answer{'s' if len(a) != 1 else ''}")
        if not fades:
            notes.append(f'drill {i + 1}: no usable level'); continue
        data = {'breadcrumb': str(d.get('file_breadcrumb') or ''), 'context': str(d.get('context_comment') or ''),
                'note': str(d.get('python_fluency_note') or ''), 'fades': fades}
        cards.append((d.get('id') or f'drill_{i + 1:02}', 'drill', str(d.get('context_comment') or 'Complete the code.'),
                      str(d['full_canonical_code']), [], data, 100 + i))
    for i, c in enumerate(as_list(doc.get('tier_2_self_explanation_cards') or doc.get('self_explanation_flashcards'))):
        if not isinstance(c, dict) or not c.get('front_prompt') or not c.get('back_explanation'):
            notes.append(f'explain card {i + 1}: needs a front prompt and a back explanation'); continue
        pts = rubric_points(as_list(c.get('eval_rubric')))
        data = {'type': str(c.get('card_type') or ''), 'breadcrumb': str(c.get('file_breadcrumb') or '')}
        cards.append((c.get('id') or f'card_{i + 1:02}', 'explain', str(c['front_prompt']), str(c['back_explanation']), pts, data, 200 + i))
    keep = set()
    for item_id, kind, prompt, answer, pts, data, o in cards:
        cid = f'{mid}:{slug(item_id)}'
        if cid in keep: cid = f'{cid}-{o}'
        keep.add(cid)
        upsert_card(db, cid, mid, kind, prompt, answer, pts, data, as_list(meta.get('concepts_covered')), o)
    for (old,) in db.execute("SELECT id FROM cards WHERE deck=?", (mid,)).fetchall():
        if old not in keep: db.execute("DELETE FROM cards WHERE id=?", (old,))     # attempts and schedule rows are kept
    db.execute("INSERT INTO modules(id,name,project,built_in,at,summary,concepts,files,source) VALUES(?,?,?,?,?,?,?,?,?) "
               "ON CONFLICT(id) DO UPDATE SET name=excluded.name,project=excluded.project,built_in=excluded.built_in,"
               "summary=excluded.summary,concepts=excluded.concepts,files=excluded.files,source=excluded.source",
               (mid, name, str(meta.get('project') or ''), 1 if built_in else 0, stamp(meta.get('timestamp'), mid),
                json.dumps({k: str(summary.get(k) or '') for k in ('schematic_mental_model', 'design_rules_heuristics',
                            'hard_rules_invariants', 'hci_human_factors_bridge')}),
                json.dumps([str(x) for x in as_list(meta.get('concepts_covered'))]),
                json.dumps([str(x) for x in as_list(meta.get('source_files'))]), os.path.basename(source)))
    db.commit()
    return len(cards), notes

def stamp(iso, mid):
    """When the module was written: its ISO timestamp, else the YYYYMMDD_HHMMSS file name, else now."""
    for s, fmt in ((str(iso or '')[:19], '%Y-%m-%dT%H:%M:%S'), (mid[:15], '%Y%m%d_%H%M%S')):
        try: return time.mktime(time.strptime(s, fmt))
        except ValueError: pass
    return time.time()

def scan_inbox(db):
    """Import new or changed files from the inbox. Cheap when nothing changed (one directory listing)."""
    try: entries = [e for e in os.scandir(INBOX) if e.name.endswith('.json') and e.is_file()]
    except OSError: return
    seen = {r['path']: r for r in db.execute("SELECT path, mtime, size FROM imports")}
    for e in entries:
        st = e.stat(); old = seen.get(e.name)
        if old and old['mtime'] == st.st_mtime and old['size'] == st.st_size: continue
        mid, ok, msg = slug(e.name[:-5]), 0, ''
        try:
            with open(e.path, encoding='utf-8') as fh: doc = json.load(fh)
            if not is_module(doc): raise ValueError('not a Mentor module (no tier_1/2/3 lists or cta_summary)')
            with DB_LOCK:
                n, notes = import_module(db, doc, mid, e.path, False)
            ok, msg = (1 if n else 0), (f'{n} card{"s" if n != 1 else ""}' + (f'; skipped: {"; ".join(notes[:6])}' if notes else ''))
        except json.JSONDecodeError as x:
            msg = f'not valid JSON (line {x.lineno}: {x.msg})'
        except (ValueError, KeyError, TypeError) as x:
            msg = str(x)[:200]
        with DB_LOCK:
            db.execute("INSERT INTO imports(path,mtime,size,ok,msg,module,at) VALUES(?,?,?,?,?,?,?) ON CONFLICT(path) DO UPDATE SET "
                       "mtime=excluded.mtime,size=excluded.size,ok=excluded.ok,msg=excluded.msg,module=excluded.module,at=excluded.at",
                       (e.name, st.st_mtime, st.st_size, ok, msg, mid, time.time()))
            db.commit()

# ---------- A: rubric grader (typed explanations) ----------
STOP = set('a an the of to in on for and or is are be it its that this with as by from at your you their they them can'.split())
# words in a written rubric line ("Key causal mechanism: the list is shared") that say nothing about the answer itself
GENERIC = set('key causal mechanism mention must should explain explanation concept idea point why how what which when will would '
              'could does do not more less into than also because so then there here such about using use used invariant '
              'consequence system mechanic python hci 1 2 3'.split())

def norm(s):
    return re.sub(r"[^a-z0-9\s]", " ", s.lower().replace("'", ''))

def stem(w):
    for suf in ('ingly', 'edly', 'ing', 'ed', 'es', 's', 'ly'):
        if len(w) > len(suf) + 2 and w.endswith(suf):
            return w[:-len(suf)]
    return w

def tokens(s):
    return [stem(w) for w in norm(s).split() if w not in STOP]

def word_in(word, ans_tokens):
    """A rubric word counts if it, or a close spelling of it (typos), is in the answer."""
    if word in ans_tokens: return True
    if len(word) < 5: return False
    return any(abs(len(t) - len(word)) <= 2 and SequenceMatcher(None, t, word).ratio() >= 0.84 for t in ans_tokens)

def phrase_hit(phrase, ans_tokens):
    ws = tokens(phrase)
    return bool(ws) and all(word_in(w, ans_tokens) for w in ws)

def rubric_points(items):
    """eval_rubric lines -> key ideas. {"idea", "any": [wordings]} is graded like a deck card; a plain sentence is
    graded on its own content words (about 40% of them must appear), which is rougher, so the coach says so."""
    pts = []
    for it in items:
        if isinstance(it, dict) and it.get('any'):
            pts.append({'idea': str(it.get('idea') or it['any'][0]), 'any': [str(a) for a in as_list(it['any'])],
                        'weight': it.get('weight', 1)})
            continue
        idea = it if isinstance(it, str) else str(it.get('idea', '')) if isinstance(it, dict) else ''
        idea = re.sub(r'^\s*(key\s+)?[\w /&-]{0,40}?\d?\s*:\s*', '', idea) if ':' in idea[:45] else idea
        words = [w for w in dict.fromkeys(tokens(idea)) if w not in GENERIC and len(w) > 2]
        if words: pts.append({'idea': idea.strip(), 'auto': words})
    return pts

def point_hit(p, at):
    if p.get('any'): return any(phrase_hit(k, at) for k in p['any'])
    words = p.get('auto', [])
    return bool(words) and sum(word_in(w, at) for w in words) >= max(1, math.ceil(len(words) * 0.4))

def grade(card, answer):
    """Returns coverage 0..1, which key ideas were hit/missed, and the features a later learned grader uses."""
    points = json.loads(card['points']) if isinstance(card['points'], str) else card['points']
    at = set(tokens(answer))
    hits, missed, per = [], [], []
    for p in points:
        ok = point_hit(p, at)
        per.append(1 if ok else 0)
        (hits if ok else missed).append(p['idea'])
    total = sum(p.get('weight', 1) for p in points) or 1
    coverage = sum(p.get('weight', 1) for p, h in zip(points, per) if h) / total
    ref = set(tokens(card['answer']))
    overlap = len(at & ref) / (len(ref) or 1)
    features = {'coverage': round(coverage, 3), 'points': per, 'n_points': len(points),
                'words': len(answer.split()), 'ref_overlap': round(overlap, 3),
                'auto_points': sum(1 for p in points if 'auto' in p)}
    return coverage, hits, missed, features

# ---------- drills: blanks and whole bodies ----------
def squash(code):
    """Code compared loosely: quotes, spacing around symbols and repeated spaces don't matter."""
    s = re.sub(r'\s+', ' ', str(code).strip().replace('"', "'"))
    return re.sub(r'\s*([()\[\]{}:,.=+\-*/<>!%|&@])\s*', r'\1', s).rstrip(':; ')

def same_code(typed, expected):
    for e in as_list(expected):
        if squash(typed) == squash(e): return True
        try:      # same expression written differently: (a) vs a, 'x' vs "x"
            if ast.dump(ast.parse(typed.strip(), mode='eval')) == ast.dump(ast.parse(str(e).strip(), mode='eval')): return True
        except (SyntaxError, ValueError, RecursionError, MemoryError):
            pass
    return False

def fill_body(fade, body):
    """Put a typed function body where {{BLANK_1}} sits, indented to match the placeholder's line."""
    lines = fade.split('\n')
    for i, line in enumerate(lines):
        if BLANK.search(line) and not BLANK.sub('', line).strip():
            indent = line[:len(line) - len(line.lstrip())]
            lines[i:i + 1] = textwrap.indent(textwrap.dedent(body.replace('\t', '    ')).strip('\n'), indent, lambda l: True).split('\n')
            return '\n'.join(lines)
    return BLANK.sub(lambda m: body, fade, count=1)

def code_tokens(src):
    try:
        skip = (tokenize.COMMENT, tokenize.NL, tokenize.ENCODING, tokenize.ENDMARKER)
        return [(t.type, t.string.replace('"', "'")) for t in tokenize.generate_tokens(io.StringIO(src).readline) if t.type not in skip]
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return re.findall(r"\w+|[^\w\s]", src)

def syntax_problem(src):
    try: ast.parse(src); return None
    except SyntaxError as e: return f"line {e.lineno}: {e.msg}"
    except (ValueError, RecursionError, MemoryError): return 'too deeply nested to read'

def grade_body(fade, typed, expected):
    mine, model = fill_body(fade, typed), fill_body(fade, expected)
    problem = syntax_problem(mine)
    same = False
    if not problem and not syntax_problem(model):
        same = ast.dump(ast.parse(mine)) == ast.dump(ast.parse(model))
    sim = SequenceMatcher(None, code_tokens(mine), code_tokens(model), autojunk=False).ratio()
    cov = 1.0 if same else min(0.95, sim) * (0.7 if problem else 1)
    return cov, {'syntax_ok': problem is None, 'same_structure': same, 'token_sim': round(sim, 3), 'problem': problem}

def grade_drill(card, level, text):
    fade = json.loads(card['data'])['fades'][str(level)]
    expected = fade['answers']
    if level == 3:
        cov, f = grade_body(fade['code'], text, str(expected[0]))
        return cov, f, [{'n': 1, 'ok': cov >= 0.99, 'expected': str(expected[0])}]
    try: typed = json.loads(text) if text.strip().startswith('[') else [text]
    except ValueError: typed = [text]
    typed = [str(x) for x in as_list(typed)] + [''] * len(expected)
    order = sorted(set(blanks_in(fade['code'])))
    per = [{'n': n, 'ok': bool(typed[i].strip()) and same_code(typed[i], expected[i]), 'typed': typed[i],
            'expected': expected[i] if isinstance(expected[i], str) else expected[i][0]} for i, n in enumerate(order)]
    cov = sum(p['ok'] for p in per) / (len(per) or 1)
    return cov, {'blanks': len(per), 'right': sum(p['ok'] for p in per)}, per

def grade_term(card, text):
    want, got = norm(card['answer']).split(), norm(text).split()
    w, g = ' '.join(w for w in want if w != 'the'), ' '.join(x for x in got if x != 'the')
    if not g: return 0.0
    r = SequenceMatcher(None, w, g).ratio()
    if w == g or r >= 0.86: return 1.0
    return 0.5 if set(want) & set(got) - {'the', 'a'} else 0.0

def suggest_rating(coverage, confidence):
    # 1 Again, 2 Hard, 3 Good, 4 Easy. Low confidence nudges a full answer from Easy down to Good.
    if coverage < 0.34: return 1
    if coverage < 0.67: return 2
    if coverage < 0.99 or (confidence or 4) <= 2: return 3
    return 4

# ---------- FSRS-4.5 scheduler ----------
W = [0.4872, 1.4003, 3.7145, 13.8206, 5.1618, 1.2298, 0.8975, 0.031, 1.6474, 0.1367, 1.0461,
     2.1072, 0.0793, 0.3246, 1.587, 0.2272, 2.8755]
DECAY, FACTOR, RETAIN = -0.5, 19 / 81, 0.9
DAY = 86400

def retrievability(elapsed_days, s):
    return (1 + FACTOR * elapsed_days / s) ** DECAY

def interval_days(s):
    return max(1, round(s / FACTOR * (RETAIN ** (1 / DECAY) - 1)))

def init_d(g):
    return min(10, max(1, W[4] - (g - 3) * W[5]))

def schedule(row, g, now):
    """row = previous sched row or None; g = rating 1..4. Returns new (stability, difficulty, due, reps, lapses)."""
    if row is None or not row['reps']:
        s, d = W[g - 1], init_d(g)
        due = now + (600 if g == 1 else 3600 if g == 2 else interval_days(s) * DAY)
        return s, d, due, 1, 1 if g == 1 else 0
    s, d = row['stability'], row['difficulty']
    r = retrievability(max(0, (now - (row['last'] or now)) / DAY), s)
    d = d - W[6] * (g - 3)
    d = min(10, max(1, W[7] * init_d(3) + (1 - W[7]) * d))
    if g == 1:
        s = W[11] * d ** -W[12] * ((s + 1) ** W[13] - 1) * math.exp(W[14] * (1 - r))
        return s, d, now + 600, row['reps'] + 1, row['lapses'] + 1
    hard = W[15] if g == 2 else 1
    easy = W[16] if g == 4 else 1
    s = s * (1 + math.exp(W[8]) * (11 - d) * s ** -W[9] * (math.exp(W[10] * (1 - r)) - 1) * hard * easy)
    return s, d, now + interval_days(s) * DAY, row['reps'] + 1, row['lapses']

# Expertise reversal (Kalyuga et al. 2003): blanks that help a beginner slow down someone who knows the code.
def fast_ms(level, blanks):
    return (15_000 + 5_000 * max(0, blanks - 1)) if level == 1 else 30_000 + 5_000 * max(0, blanks - 1)

def next_level(db, card, srow, attempt, g):
    """The drill level after this rating, and whether that is a step up."""
    fades = json.loads(card['data'] or '{}').get('fades', {})
    lv = (srow['level'] if srow and srow['level'] else None) or min(int(k) for k in fades)
    if g == 1:
        lower = [int(k) for k in fades if int(k) < lv]
        return (max(lower) if lower else lv), False
    if g < 3 or attempt['coverage'] < 0.99 or lv >= 3: return lv, False
    feats = json.loads(attempt['features'] or '{}')
    prev = db.execute("SELECT coverage FROM attempts WHERE card_id=? AND id<? AND level=? AND rating IS NOT NULL ORDER BY id DESC LIMIT 1",
                      (card['id'], attempt['id'], lv)).fetchone()
    if attempt['ms'] <= fast_ms(lv, feats.get('blanks', 1)) or (prev and prev['coverage'] >= 0.99):
        higher = [int(k) for k in fades if int(k) > lv]
        if higher: return min(higher), True
    return lv, False

def plan(db, card, srow, attempt, g, now):
    s, d, due, reps, lapses = schedule(srow, g, now)
    level, up = (next_level(db, card, srow, attempt, g) if card['kind'] == 'drill' else (1, False))
    if up: due = min(due, now + DAY)          # try the harder level soon instead of after a long gap
    return s, d, due, reps, lapses, level, up

# ---------- API helpers ----------
_recent = []        # modules/decks in the order their cards were last served (most recent last)

def interleave(pool):
    """The first card in pool from the module or deck that has waited longest (never served counts as longest)."""
    rank = {d: i for i, d in enumerate(_recent)}
    c = min(enumerate(pool), key=lambda x: (rank.get(x[1]['deck'], -1), x[0]))[1]
    if c['deck'] in _recent: _recent.remove(c['deck'])
    _recent.append(c['deck'])
    return c

def card_level(card, srow_level):
    fades = json.loads(card['data'] or '{}').get('fades', {})
    if not fades: return None
    lv = srow_level or min(int(k) for k in fades)
    return lv if str(lv) in fades else min(int(k) for k in fades)

def card_payload(db, c):
    """What the page needs to ask the question - never the answer."""
    data = json.loads(c['data'] or '{}')
    mod = db.execute("SELECT name, project FROM modules WHERE id=?", (c['deck'],)).fetchone()
    out = {'id': c['id'], 'deck': c['deck'], 'kind': c['kind'], 'tier': TIER.get(c['kind'], 3), 'prompt': c['prompt'],
           'reps': c['reps'] or 0, 'module': mod['name'] if mod else None, 'project': mod['project'] if mod else None}
    if c['kind'] == 'drill':
        lv = card_level(c, c['level'])
        fade = data['fades'][str(lv)]
        out.update({'level': lv, 'levels': sorted(int(k) for k in data['fades']), 'level_name': LEVELS[lv], 'code': fade['code'],
                    'breadcrumb': data.get('breadcrumb', ''), 'context': data.get('context', ''),
                    'widths': [max(len(x if isinstance(x, str) else x[0]), 3) for x in fade['answers']]})
    elif c['kind'] == 'explain':
        out.update({'type': data.get('type', ''), 'breadcrumb': data.get('breadcrumb', '')})
    elif c['kind'] == 'term':
        out.update({'category': data.get('category', '')})
    return out

def next_card(db, deck=None, extra=False):
    scan_inbox(db)
    now = time.time()
    q = ("SELECT c.*, s.due, s.reps, s.level, m.at AS mat FROM cards c LEFT JOIN sched s ON s.card_id=c.id "
         "LEFT JOIN modules m ON m.id=c.deck")
    args = []
    if deck: q += " WHERE c.deck=?"; args.append(deck)
    rows = db.execute(q, args).fetchall()
    # funnel: a module's drills wait until its terms have been seen once, its explain cards until its drills have
    stage = {}
    for r in rows:
        if r['kind'] in FUNNEL and not r['reps']:
            stage[r['deck']] = min(stage.get(r['deck'], 9), FUNNEL[r['kind']])
    due = sorted((r for r in rows if r['due'] is not None and r['due'] <= now), key=lambda r: r['due'])
    new = sorted((r for r in rows if r['due'] is None and FUNNEL.get(r['kind'], 0) <= stage.get(r['deck'], 9)),
                 key=lambda r: (r['mat'] or 0, r['deck'], r['ord'] or 0, r['id']))
    pool = due or new
    if pool: c = interleave(pool)
    elif extra and rows: c = min(rows, key=lambda r: r['due'] or now)                # practise ahead: the soonest-due card
    else: return None, min((r['due'] for r in rows if r['due']), default=None)
    return card_payload(db, c), None

def answer(db, card_id, text, confidence, ms):
    c = db.execute("SELECT c.*, s.level FROM cards c LEFT JOIN sched s ON s.card_id=c.id WHERE c.id=?", (card_id,)).fetchone()
    if not c: return None
    data = json.loads(c['data'] or '{}')
    level, per, extra = None, None, {}
    if c['kind'] == 'drill':
        level = card_level(c, c['level'])
        cov, feats, per = grade_drill(c, level, text)
        hits = [f"Blank {p['n']}" for p in per if p['ok']]; missed = [f"Blank {p['n']}" for p in per if not p['ok']]
        grader = 'drill-A'
        extra = {'level': level, 'canonical': c['answer'], 'note': data.get('note', ''), 'blanks': per,
                 'problem': feats.get('problem'), 'same_structure': feats.get('same_structure')}
        if level == 3: extra['yours'] = fill_body(data['fades']['3']['code'], text)
    elif c['kind'] == 'term':
        cov = grade_term(c, text)
        hits, missed = ([c['answer']], []) if cov >= 0.99 else ([], [c['answer']])
        feats, grader = {'coverage': cov, 'words': len(text.split())}, 'term-A'
        extra = {k: data.get(k, '') for k in ('definition', 'anchor', 'contrast', 'category')}
    else:
        cov, hits, missed, feats = grade(c, text)
        grader = 'rubric-A-auto' if feats.get('auto_points') else 'rubric-A'
        extra = {'breadcrumb': data.get('breadcrumb', ''), 'rough': bool(feats.get('auto_points'))}
    feats.update({'confidence': confidence, 'ms': ms, 'kind': c['kind'], 'level': level})
    sug = suggest_rating(cov, confidence)
    with DB_LOCK:
        cur = db.execute("INSERT INTO attempts(card_id,at,answer,confidence,ms,coverage,hits,missed,features,suggested,grader,kind,level) "
                         "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (card_id, time.time(), text, confidence, ms, cov,
                         json.dumps(hits), json.dumps(missed), json.dumps(feats), sug, grader, c['kind'], level))
        db.commit()
    att = db.execute("SELECT * FROM attempts WHERE id=?", (cur.lastrowid,)).fetchone()
    srow = db.execute("SELECT * FROM sched WHERE card_id=?", (card_id,)).fetchone()
    now = time.time()
    plans = {g: plan(db, c, srow, att, g, now) for g in (1, 2, 3, 4)}
    previews = {g: round((p[2] - now) / DAY, 3) for g, p in plans.items()}      # days until it returns
    level_after = {g: p[5] for g, p in plans.items()} if c['kind'] == 'drill' else None
    n = len(hits) + len(missed)
    return {'attempt': cur.lastrowid, 'kind': c['kind'], 'coverage': round(cov, 2), 'hits': hits, 'missed': missed,
            'previews': previews, 'level_after': level_after, 'reference': c['answer'], 'suggested': sug,
            'coach': coach_line(c['kind'], cov, confidence, n, extra), **extra}

def coach_line(kind, cov, conf, n, extra):
    k = round(cov * n)
    if conf and conf >= 3 and cov < 0.5:
        return f"You felt sure but got {k} of {n}. Cards like this are where overconfidence hides: slow down on it next time."
    if conf and conf <= 2 and cov >= 0.99:
        return "You knew more than you thought: it's all there. Trust that answer next time."
    if kind == 'drill':
        if extra.get('level') == 3:
            if extra.get('problem'): return f"Python can't read your version ({extra['problem']}). Compare the two, then fix that line in your head."
            if extra.get('same_structure'): return "Same structure as the model answer. You wrote it from memory."
            return "It runs differently from the model answer. Spot the line that differs, then say why the model does it that way."
        if cov >= 0.99: return f"All {n} blank{'s' if n != 1 else ''} right."
        return f"{k} of {n} blanks right. Read the full code below and trace what each missing piece does."
    if kind == 'term':
        if cov >= 0.99: return "Right term. Read where it lives in your code, so you'll spot it next time."
        if cov > 0: return "Close, but not the exact term. Compare your wording with the one below."
        return "Not this time. Read the definition and the look-alike term, then say the term out loud."
    rough = ' (this card checks content words only, so judge for yourself)' if extra.get('rough') else ''
    if cov >= 0.99: return f"All {n} key ideas. Solid."
    if cov == 0: return "None of the key ideas yet. Read the model answer, then say it back in your own words before rating." + rough
    return f"{k} of {n} key ideas{rough}. Look at what's missing and add it to your own version."

def rate(db, attempt_id, rating, grade_wrong):
    a = db.execute("SELECT * FROM attempts WHERE id=?", (attempt_id,)).fetchone()
    if not a or rating not in (1, 2, 3, 4): return None
    c = db.execute("SELECT * FROM cards WHERE id=?", (a['card_id'],)).fetchone()
    now = time.time()
    with DB_LOCK:
        srow = db.execute("SELECT * FROM sched WHERE card_id=?", (a['card_id'],)).fetchone()
        if c is None: s, d, due, reps, lapses, level, up = (*schedule(srow, rating, now), 1, False)
        else: s, d, due, reps, lapses, level, up = plan(db, c, srow, a, rating, now)
        db.execute("INSERT INTO sched(card_id,stability,difficulty,due,last,reps,lapses,level) VALUES(?,?,?,?,?,?,?,?) "
                   "ON CONFLICT(card_id) DO UPDATE SET stability=excluded.stability,difficulty=excluded.difficulty,"
                   "due=excluded.due,last=excluded.last,reps=excluded.reps,lapses=excluded.lapses,level=excluded.level",
                   (a['card_id'], s, d, due, now, reps, lapses, level))
        db.execute("UPDATE attempts SET rating=?, grade_wrong=? WHERE id=?", (rating, 1 if grade_wrong else 0, attempt_id))
        db.commit()
    old = a['level']
    return {'due': due, 'days': round((due - now) / DAY, 1), 'level': level if c and c['kind'] == 'drill' else None,
            'level_change': (level - old) if old and c and c['kind'] == 'drill' else 0}

def modules(db):
    """Code modules for the Modules view: the CTA summary, what's in them and how far along you are."""
    out = []
    counts = db.execute("SELECT c.deck, c.kind, COUNT(*) n, SUM(CASE WHEN s.reps>0 THEN 1 ELSE 0 END) seen, "
                        "SUM(CASE WHEN c.kind='drill' AND s.level=3 THEN 1 ELSE 0 END) top "
                        "FROM cards c LEFT JOIN sched s ON s.card_id=c.id GROUP BY c.deck, c.kind").fetchall()
    by = {}
    for r in counts: by.setdefault(r['deck'], {})[r['kind']] = {'n': r['n'], 'seen': r['seen'] or 0, 'top': r['top'] or 0}
    for m in db.execute("SELECT * FROM modules ORDER BY built_in, at DESC").fetchall():
        out.append({'id': m['id'], 'name': m['name'], 'project': m['project'], 'built_in': bool(m['built_in']), 'at': m['at'],
                    'summary': json.loads(m['summary'] or '{}'), 'concepts': json.loads(m['concepts'] or '[]'),
                    'files': json.loads(m['files'] or '[]'), 'cards': by.get(m['id'], {})})
    return out

def stats(db, deck=None):
    scan_inbox(db)
    now = time.time(); day0 = now - (now % DAY)
    w, args = ("WHERE c.deck=?", [deck]) if deck else ("", [])
    cards = db.execute(f"SELECT c.id, c.kind, s.due, s.reps FROM cards c LEFT JOIN sched s ON s.card_id=c.id {w}", args).fetchall()
    aw = "WHERE a.card_id LIKE ?" if deck else ""
    att = db.execute(f"SELECT a.* FROM attempts a {aw} ORDER BY a.id DESC LIMIT 500", [deck + ':%'] if deck else []).fetchall()
    rated = [a for a in att if a['rating']]
    conf = [a for a in rated if a['confidence']]
    # calibration: confidence (1-4 -> 0..1) minus coverage; positive = overconfident
    cal = round(sum((a['confidence'] - 1) / 3 - a['coverage'] for a in conf) / len(conf), 2) if conf else None
    imports = [dict(r) for r in db.execute("SELECT path, ok, msg, module, at FROM imports ORDER BY at DESC LIMIT 8")]
    return {'cards': len(cards), 'new': sum(1 for c in cards if c['due'] is None),
            'due': sum(1 for c in cards if c['due'] is not None and c['due'] <= now),
            'learned': sum(1 for c in cards if (c['reps'] or 0) > 0),
            'today': sum(1 for a in att if a['at'] >= day0),
            'avg_coverage': round(sum(a['coverage'] for a in rated) / len(rated), 2) if rated else None,
            'calibration': cal, 'labels': len(rated),
            'grade_disputes': sum(1 for a in rated if a['grade_wrong']),
            'modules': modules(db), 'imports': imports,
            'inbox': INBOX.replace(os.path.expanduser('~'), '~', 1)}
