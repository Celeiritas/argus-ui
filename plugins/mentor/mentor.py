"""Mentor - the study coach behind the Learn page: learn the code you build with an AI. Python standard library only.

What it teaches (see docs/mentor.md): each "lesson" is a Cognitive Task Analysis of real code, written by the
/mentor command in Claude Code (docs/mentor-command.md) as JSON. A lesson has three tiers of practice cards:
  Tier 1  drill    faded worked examples: a 5-15 line snippet with blanks, level 1 (endings) -> 2 (logic) -> 3 (whole body)
  Tier 2  explain  self-explanation: find the bug (pre-mortem), why this design (trade-off), human factors link
  Tier 3  term     vocabulary: a cloze sentence; the feedback shows the definition, where it is in your code, its look-alike
and, since 4.8, a Learn card in front of each one (teach before test):
  orientation  one screen: what the code does and why this lesson      teach    a term, its anchor, its look-alike, spot it
  level0       the drill's full code, annotated line by line, self-explained    preread  the key ideas an explain card assumes
Learn cards are seen once (never scheduled); they come back only when you are stuck. Plain decks (kind "define", the
older format) still work and mix in with the lessons.

Order of study: inside a lesson, new cards unlock orientation -> teach -> terms -> worked examples -> drills -> pre-reads
-> explain cards (pre-training first, Mayer & Pilegard 2014; worked examples before problems, Sweller & Cooper 1985).
Reviews interleave: the next due card comes from a different lesson or deck when one is due (Bjork & Bjork 2011).
Drills move up a level when you get every blank right fast, or right twice in a row; "Needs work" moves them down.
Every practice card has a hint ladder (nudge -> the expert's first move -> a near example -> the answer); each rung
caps the rating Mentor suggests, and the rung reached is stored with the attempt.

Grading roadmap (each stage keeps the data the next one learns from):
  A    rubric grader (this file): key ideas + accepted wordings; drill blanks compared as code; whole bodies parsed with ast.
  B    local similarity model: adds a meaning-based score as one more feature.
  Bv2  learned grader: a small model trained on YOUR attempts (features + final rating + "grade was wrong" flags).
Every attempt is stored with its features and your labels in the `attempts` table, from day one. Code you type is
only parsed, never run.

Courses (4.26, docs/mentor.md): course -> modules -> lessons -> notes -> cards with learning objectives; a course lesson is a
lesson in this format plus LO / note / role / check fields (import_course). Older lessons form the Loose lessons course.

Code modules arrive in the inbox folder (~/.local/share/argus-ui/inbox, or ARGUS_MENTOR_INBOX). It is checked every
time the page asks for a card, so a copied-in file shows up without a restart. Files are read, never moved or deleted.

The server's routes are fixed (decks, next, stats, answer, rate, undo, settings); a drill's blanks arrive in `answer` as a JSON list.
Scheduling: FSRS-4.5 (Free Spaced Repetition Scheduler) with its published default weights, plus Anki's behaviours on top
(4.29): learning steps (1 min, 10 min; relearning 10 min), undo of the last rating, and bury siblings (same note, until tomorrow).
"""
import ast, io, json, math, os, re, sqlite3, textwrap, threading, time, glob, tokenize
from difflib import SequenceMatcher

DB_LOCK = threading.Lock()
INBOX = os.path.expanduser(os.environ.get('ARGUS_MENTOR_INBOX', '~/.local/share/argus-ui/inbox'))
TIER = {'term': 3, 'drill': 1, 'explain': 2, 'define': 3, 'orientation': 0, 'teach': 0, 'level0': 0, 'preread': 0,
        'predict': 2, 'trace': 2, 'parsons': 1, 'write': 1}
# new cards in a lesson unlock in this order; a practice card also waits for its own Learn card (cards.learn_of).
# 4.32: reading code (predict, trace) comes before writing it (parsons, write), as Xie et al. (2019) order them
FUNNEL = {'orientation': 0, 'teach': 1, 'term': 2, 'predict': 3, 'trace': 4, 'level0': 5, 'drill': 6, 'parsons': 7, 'write': 8,
          'preread': 9, 'explain': 10}
CODE_KINDS = ('predict', 'trace', 'parsons', 'write')      # the 4.32 card roles (spec section 5), each its own card kind
LEARN = ('orientation', 'teach', 'level0', 'preread')
LEVELS = {1: 'Fill in the endings', 2: 'Fill in the logic', 3: 'Write the body'}
RUNGS = ('Nudge', "The expert's first move", 'A near example', 'The answer')
# what an expert looks at first, when the lesson doesn't say (rung 2 of the hint ladder and the coach line)
MOVE = {'drill': 'Look at what the function already returns and what each name holds by then.',
        'term': 'Name what it does before you name it.',
        'explain': 'Start from what can go wrong, then say why the code prevents it.',
        'define': 'Say what it is for before you say what it is.',
        'predict': 'Run it in your head one line at a time, and note each name\'s value as it changes.',
        'trace': 'Keep a small table: one row per line, one column per name.',
        'parsons': 'Find the first line and the last one first, then fill in the middle.',
        'write': 'Write what goes in and what comes out first, then the steps between.'}
WORDS = re.compile(r"[A-Za-z0-9_']+")
STUCK_WINDOW, LAPSE_WINDOW = 2 * 3600, 7 * 86400

# ---------- placeholders: a lesson says {{SERVER}}, never a real machine name or path ----------
# Filled in from ~/.config/leafy/realm.json (yours, never committed) every time a card is shown or graded; the database
# keeps the {{...}} form, so a lesson moves between people unchanged and an edit to realm.json shows up at once.
REALM_FILE = os.path.expanduser(os.environ.get('LEAFY_REALM', '~/.config/leafy/realm.json'))
REALM_DEFAULTS = {'SERVER': 'homeserver', 'PC': 'desktop', 'PHONE': 'phone', 'SSH': 'server',
                  'HOME_PC': 'C:\\Users\\you', 'HOME_SERVER': '~', 'REPO_URL': 'https://github.com/you/argus-ui'}
PLACE = re.compile(r'\{\{\s*(' + '|'.join(REALM_DEFAULTS) + r')\s*\}\}')
_realm = [None, {}]        # realm.json's mtime when last read, and its values

def realm():
    """The placeholder values: realm.json over the public defaults. A missing or broken file means the defaults."""
    try: mt = os.stat(REALM_FILE).st_mtime
    except OSError: return dict(REALM_DEFAULTS)
    if _realm[0] != mt:
        try:
            with open(REALM_FILE, encoding='utf-8') as fh: doc = json.load(fh)
        except (OSError, ValueError): doc = {}
        _realm[:] = [mt, {str(k).upper(): str(v) for k, v in (doc.items() if isinstance(doc, dict) else [])
                          if str(k).upper() in REALM_DEFAULTS and isinstance(v, (str, int, float)) and str(v).strip()}]
    return {**REALM_DEFAULTS, **_realm[1]}

def fill(s, vals=None, as_json=False):
    """Put the realm's values where {{SERVER}} etc. sit. as_json: s is JSON text, so each value goes in escaped."""
    if not isinstance(s, str) or '{{' not in s: return s
    vals = vals or realm()
    return PLACE.sub(lambda m: json.dumps(vals[m.group(1)])[1:-1] if as_json else vals[m.group(1)], s)

def filled(c):
    """A card row with its placeholders filled in: what the page shows and what grading compares against."""
    if c is None: return None
    vals, d = realm(), dict(c)
    for k in ('prompt', 'answer'): d[k] = fill(d.get(k), vals)
    for k in ('points', 'data'): d[k] = fill(d.get(k), vals, as_json=True)
    return d

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
-- 4.26: courses (docs/plans/2026-10-25-mentor-courses-spec.md). The modules table above holds lessons; a course's
-- modules are cmodules. LO ids are course/LOid, note ids lesson:note.
CREATE TABLE IF NOT EXISTS courses(
  id TEXT PRIMARY KEY, name TEXT, summary TEXT, requires TEXT, retention REAL, data TEXT, source TEXT, at REAL);
CREATE TABLE IF NOT EXISTS cmodules(
  id TEXT PRIMARY KEY, course TEXT, name TEXT, ord INTEGER, requires TEXT);
CREATE TABLE IF NOT EXISTS los(
  id TEXT PRIMARY KEY, course TEXT, owner TEXT, scope TEXT, text TEXT, verb TEXT, bloom TEXT, mode TEXT, knowledge TEXT,
  condition TEXT, standard TEXT, parent TEXT);
CREATE TABLE IF NOT EXISTS notes(
  id TEXT PRIMARY KEY, lesson TEXT, kind TEXT, source_ref TEXT);
-- 4.29: study settings chosen on the page (bury siblings); one row per key, JSON values
CREATE TABLE IF NOT EXISTS settings(
  key TEXT PRIMARY KEY, value TEXT);
"""
# columns added after 4.5 (older databases get them on start; nothing is lost)
ADDED = [('cards', 'data', "TEXT DEFAULT '{}'"), ('cards', 'ord', 'INTEGER DEFAULT 0'),
         ('sched', 'level', 'INTEGER DEFAULT 1'), ('attempts', 'kind', 'TEXT'), ('attempts', 'level', 'INTEGER'),
         # 4.8: Learn cards and the hint ladder
         ('cards', 'learn_of', 'TEXT'), ('sched', 'refresh', 'INTEGER DEFAULT 0'),
         ('attempts', 'hints', 'INTEGER DEFAULT 0'), ('attempts', 'reflections', 'TEXT'), ('attempts', 'stuck', 'TEXT'),
         ('attempts', 'skipped', 'INTEGER DEFAULT 0'),
         # 4.17: the local AI's part of an attempt (docs/mentor-ai.md), JSON; empty when it was off
         ('attempts', 'ai', 'TEXT'),
         # 4.26: courses; a lesson's place in one, a card's LO, note, role and whether it is a check item
         ('modules', 'course', 'TEXT'), ('modules', 'cmodule', 'TEXT'), ('modules', 'ord', 'INTEGER DEFAULT 0'),
         ('cards', 'lo', 'TEXT'), ('cards', 'note', 'TEXT'), ('cards', 'role', 'TEXT'), ('cards', 'is_check', 'INTEGER DEFAULT 0'),
         # 4.26: the review log (Anki's revlog): learn/review/relearn/manual, interval before and after (days), time capped at 60 s
         ('attempts', 'review', 'TEXT'), ('attempts', 'ivl_before', 'REAL'), ('attempts', 'ivl_after', 'REAL'), ('attempts', 'took', 'INTEGER'),
         # 4.29: learning steps (the step a card is at, None once it is in review; relearn = the steps after a lapse),
         # undo (the schedule before a rating, and whether that rating was undone; a log row is never deleted)
         ('sched', 'step', 'INTEGER'), ('sched', 'relearn', 'INTEGER DEFAULT 0'),
         ('attempts', 'prev_json', 'TEXT'), ('attempts', 'undone', 'INTEGER DEFAULT 0'),
         # 4.32: a course lesson's `requires` (the lesson ids in its course that unlock it), JSON
         ('modules', 'requires', "TEXT DEFAULT '[]'")]
LOOSE = 'loose'          # the course every lesson in the old format belongs to, one module per project
# card roles (spec section 5) and the card kind that runs each; `make` (tasks and the capstone) comes later
ROLE_KIND = {'term': ('term',), 'recall': ('define', 'term'), 'explain': ('explain',), 'find-bug': ('explain',),
             'choose-design': ('explain',), 'drill': ('drill',), **{k: (k,) for k in CODE_KINDS}}
DEFAULT_ROLE = {'term': 'term', 'drill': 'drill', 'explain': 'explain', 'define': 'recall', **{k: k for k in CODE_KINDS}}
LATER_ROLES = ('make',)
# a lesson is mastered (and unlocks the lessons that require it) when this share of its practice cards was answered right;
# a module check passes at the same share (spec section 15.3: module pass 80%)
PASS = 0.8

class Conn(sqlite3.Connection):
    """A database connection that knows whether it reads the inbox (people: only the owner's database does)."""
    own_inbox = True

def connect(path, inbox=True):
    """Open (and upgrade) one person's database. inbox=False: this database never imports from the inbox folder
    (a learner's database holds only their own lessons, docs/mentor.md "People")."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    db = sqlite3.connect(path, check_same_thread=False, factory=Conn)
    db.own_inbox = bool(inbox)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    for table, col, decl in ADDED:
        if col not in {r[1] for r in db.execute(f"PRAGMA table_info({table})")}:
            db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
    ensure_loose(db)
    db.commit()
    if inbox:
        try: os.makedirs(INBOX, exist_ok=True)
        except OSError: pass
    return db

def loose_module(project):
    return f'{LOOSE}/{slug(project or "lessons")}'

def ensure_loose(db):
    """The Loose lessons course: every lesson not in a course, one module per project (named as the project). Idempotent."""
    db.execute("INSERT INTO courses(id,name,summary,requires,retention,data,source,at) VALUES(?,?,?,'[]',0.9,'{}','',0) "
               "ON CONFLICT(id) DO NOTHING", (LOOSE, 'Loose lessons', 'Lessons made before courses, one module per project.'))
    for r in db.execute("SELECT id, project FROM modules WHERE course IS NULL OR course=?", (LOOSE,)).fetchall():
        db.execute("UPDATE modules SET course=?, cmodule=? WHERE id=?", (LOOSE, loose_module(r['project']), r['id']))
    projects = {r['cmodule']: r['project'] or 'Lessons' for r in db.execute("SELECT cmodule, project FROM modules WHERE course=?", (LOOSE,))}
    db.execute(f"DELETE FROM cmodules WHERE course=? AND id NOT IN ({','.join('?' * len(projects))})", (LOOSE, *projects))
    for i, (cm, name) in enumerate(sorted(projects.items(), key=lambda x: x[1].lower())):
        db.execute("INSERT INTO cmodules(id,course,name,ord,requires) VALUES(?,?,?,?,'[]') ON CONFLICT(id) DO UPDATE SET "
                   "name=excluded.name, ord=excluded.ord", (cm, LOOSE, name, i))

def load_decks(db, folder):
    """Upsert every deck JSON file in folder (plain decks and built-in code modules). History stays."""
    n = 0
    for f in sorted(glob.glob(os.path.join(folder, '*.json'))):
        try:
            with open(f, encoding='utf-8') as fh: deck = json.load(fh)
        except Exception:
            continue
        if is_course(deck):
            try:
                with DB_LOCK: n += import_course(db, deck, f, True)[0]
            except ValueError: pass
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

def upsert_card(db, cid, deck, kind, prompt, answer, points, data, tags, ord_, learn_of=None, lo=None, note=None, role=None, is_check=0):
    db.execute("INSERT INTO cards(id,deck,kind,prompt,answer,points,tags,updated,data,ord,learn_of,lo,note,role,is_check) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
               "ON CONFLICT(id) DO UPDATE SET deck=excluded.deck,kind=excluded.kind,prompt=excluded.prompt,"
               "answer=excluded.answer,points=excluded.points,tags=excluded.tags,updated=excluded.updated,"
               "data=excluded.data,ord=excluded.ord,learn_of=excluded.learn_of,lo=excluded.lo,note=excluded.note,"
               "role=excluded.role,is_check=excluded.is_check",
               (cid, deck, kind, prompt, answer, json.dumps(points), json.dumps(tags), time.time(), json.dumps(data), ord_, learn_of,
                lo, note, role, is_check))

def deck_list(folder):
    """Plain decks only; code modules are listed by stats() (they also come from the inbox)."""
    out = []
    for f in sorted(glob.glob(os.path.join(folder, '*.json'))):
        try:
            with open(f, encoding='utf-8') as fh: d = json.load(fh)
            if is_module(d): continue
            out.append({'id': d['id'], 'name': fill(d.get('name', d['id'])), 'blurb': fill(d.get('blurb', '')), 'count': len(d.get('cards', []))})
        except Exception:
            pass
    return out

# ---------- code modules (the /mentor command's JSON) ----------
def slug(s):
    return re.sub(r'[^a-z0-9_-]+', '-', str(s).lower()).strip('-')[:80] or 'module'

def is_module(doc):
    return isinstance(doc, dict) and any(k in doc for k in ('tier_1_faded_code_drills', 'tier_2_self_explanation_cards',
                                                             'tier_3_terminology_cards', 'faded_code_drills', 'cta_summary',
                                                             'code_cards'))

def code_card(k, role):
    """One 4.32 code card (`code_cards` in a lesson, docs/mentor.md) -> (prompt, answer, points, data), or a string saying
    what is missing. predict: code + the model answer, graded by key ideas; trace: code + the value after each step's line,
    each step graded by key ideas; parsons: the lines in their right order, graded by position; write: the model code,
    graded by key ideas (the local AI may add a meaning score in shadow mode, never the rating)."""
    prompt = str(k.get('front_prompt') or '').strip()
    if not prompt: return 'needs a front_prompt'
    data = {'breadcrumb': str(k.get('file_breadcrumb') or ''), 'lang': str(k.get('lang') or 'python')}
    code = k.get('code') if isinstance(k.get('code'), str) else ''
    if role in ('predict', 'trace'):
        if not code.strip(): return 'needs the code to read'
        data['code'] = code
    if role in ('predict', 'write'):
        ans = k.get('answer')
        if not isinstance(ans, str) or not ans.strip(): return 'needs the model answer'
        pts = rubric_points(as_list(k.get('eval_rubric')))
        if not pts and role == 'write': return 'needs eval_rubric key ideas (how a written answer is graded)'
        pts = pts or [{'idea': ans.strip(), 'any': [ans.strip()]}]      # a predict card without key ideas: its output as one
        if role == 'write': data['starter'] = str(k.get('starter') or '')
        return prompt, ans, pts, data
    if role == 'trace':
        n, steps = len(code.split('\n')), []
        for s in as_list(k.get('steps')):
            if not isinstance(s, dict) or not str(s.get('state') or '').strip() or not isinstance(s.get('line'), int) \
               or isinstance(s.get('line'), bool) or not 1 <= s['line'] <= n: return 'every step needs a line of the code and its state'
            steps.append({'line': s['line'], 'state': str(s['state']).strip(), 'accept': [str(a) for a in as_list(s.get('accept'))]})
        if not steps: return 'needs steps: the value after each line'
        data['steps'] = [s['line'] for s in steps]
        pts = [{'idea': f"After line {s['line']}: {s['state']}", 'any': [s['state'], *s['accept']]} for s in steps]
        return prompt, '\n'.join(f"After line {s['line']}: {s['state']}" for s in steps), pts, data
    lines = [str(x) for x in as_list(k.get('lines')) if isinstance(x, str) and x.strip()]     # parsons
    if len(lines) < 3 or len(lines) != len(as_list(k.get('lines'))): return 'needs at least 3 lines, each a line of code'
    data['lines'] = lines
    return prompt, '\n'.join(lines), [], data

BLANK = re.compile(r'\{\{\s*BLANK(?:_(\d+))?\s*\}\}')

def blanks_in(code):
    return [int(m.group(1) or 1) for m in BLANK.finditer(code or '')]

def as_list(v):
    return v if isinstance(v, list) else [] if v is None else [v]

def hints_of(item, levels=False):
    """The authored hint ladder: rungs 1 and 3 (a nudge, a near example) as 1-2 strings, per drill level or one list."""
    h = item.get('hints')
    if levels:
        if isinstance(h, dict): return {str(lv): [str(x) for x in as_list(h.get(f'level_{lv}') or h.get(str(lv)))][:2] for lv in (1, 2, 3)}
        return {str(lv): [str(x) for x in as_list(h)][:2] for lv in (1, 2, 3)}
    return [str(x) for x in as_list(h)][:2]

def worked(d):
    """A drill's level-0 worked example: authored (`level_0_worked`), else one annotation made from what the drill has."""
    w = d.get('level_0_worked') if isinstance(d.get('level_0_worked'), dict) else {}
    ann = [{'line': int(a.get('line') or 1), 'note': str(a.get('note') or ''), 'why': str(a.get('why') or '')}
           for a in as_list(w.get('annotations')) if isinstance(a, dict) and (a.get('why') or a.get('note'))][:8]
    se = w.get('self_explain') if isinstance(w.get('self_explain'), dict) else {}
    if not ann:
        ann = [{'line': 1, 'note': str(d.get('context_comment') or 'What this does'), 'why': str(d.get('python_fluency_note') or d.get('context_comment') or '')}]
    prompt = str(se.get('prompt') or 'In your words: what does this code do, and why is it written this way?')
    return ann, prompt, rubric_points(as_list(se.get('rubric'))), bool(w)

def import_module(db, doc, mid, source, built_in, course=None, cmodule=None, ord_=0, los=None, note_ids=None):
    """Turn one lesson JSON into cards: the practice cards, and a Learn card in front of each (and one orientation).
    course/cmodule: where it sits in a course (import_course); without them it is a Loose lesson. los / note_ids: the
    lesson's LO and note ids, which an item's `lo` and `note` must name.
    Returns (cards added, notes about anything skipped). Caller holds DB_LOCK."""
    meta = doc.get('metadata') if isinstance(doc.get('metadata'), dict) else {}
    name = str(meta.get('module_name') or doc.get('module_name') or mid).replace('_', ' ')
    summary = doc.get('cta_summary') if isinstance(doc.get('cta_summary'), dict) else {}
    move = str(summary.get('expert_move') or '')
    cards, notes = [], []          # (item id, kind, prompt, answer, points, data, ord, learn_of item id)
    tags = {}                      # item id -> (lo, note, role, is_check); a Learn card gets its practice card's lo and note
    def tag(item, kind, iid, learn_id):
        role = str(item.get('role') or DEFAULT_ROLE[kind])
        if role in LATER_ROLES: notes.append(f'{iid}: role {role} arrives in a later phase'); return False
        if kind not in ROLE_KIND.get(role, ()): notes.append(f'{iid}: role {role} is not a {kind} card'); role = DEFAULT_ROLE[kind]
        lo, note = str(item.get('lo') or '') or None, str(item.get('note') or '') or None
        if lo and los is not None and lo not in los: notes.append(f"{iid}: LO {lo} is not one of this lesson's"); lo = None
        if note and note_ids is not None and note not in note_ids: notes.append(f"{iid}: note {note} is not one of this lesson's"); note = None
        lo, note = (f'{course}/{lo}' if lo and course else lo), (f'{mid}:{note}' if note else None)
        chk = 1 if item.get('check') is True else 0
        tags[iid] = (lo, note, role, chk); tags[learn_id] = (lo, note, None, chk)    # a check item's Learn card would show its answer
        return True
    orient = str(summary.get('orientation') or summary.get('schematic_mental_model') or '')
    terms = as_list(doc.get('tier_3_terminology_cards'))
    if orient:
        cards.append(('orientation', 'orientation', orient, '', [], {'files': [str(x) for x in as_list(meta.get('source_files'))],
                      'terms': [str(t.get('term')) for t in terms if isinstance(t, dict) and t.get('term')],
                      'bridge': str(summary.get('hci_human_factors_bridge') or ''), 'authored': bool(summary.get('orientation'))}, -1, None))
    for i, t in enumerate(terms):
        if not isinstance(t, dict) or not str(t.get('term', '')).strip():
            notes.append(f'term {i + 1}: no term'); continue
        term, tid = str(t['term']).strip(), t.get('id') or f'term_{i + 1:02}'
        if not tag(t, 'term', tid, f'teach-{tid}'): continue
        cloze = str(t.get('cloze_prompt') or '')
        if not BLANK.search(cloze):
            cloze = f"{t.get('concise_definition') or 'Name the term.'} This is called {{{{BLANK}}}}."
        data = {k: str(t.get(src) or '') for k, src in (('category', 'category'), ('definition', 'concise_definition'),
                ('anchor', 'project_anchor'), ('contrast', 'contrast_anchor'))}
        data.update({'move': str(t.get('expert_move') or move), 'hints': hints_of(t)})
        o = int(t.get('teach_order') or i + 1) * 2
        cards.append((tid, 'term', cloze, term, [], data, o + 1, None))
        spot = t.get('spot_it') if isinstance(t.get('spot_it'), dict) and t['spot_it'].get('snippet') else None
        td = {k: data[k] for k in ('category', 'definition', 'anchor', 'contrast', 'move')}
        td['try'] = str(t.get('try_first') or '')          # a question to try before the teach card explains (not graded)
        td['spot'] = {'snippet': str(spot['snippet']), 'line': int(spot.get('line') or 1), 'why': str(spot.get('why') or '')} if spot else None
        cards.append((f'teach-{tid}', 'teach', term, str(td['spot']['line']) if spot else '', [], td, o, tid))
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
        did = d.get('id') or f'drill_{i + 1:02}'
        if not tag(d, 'drill', did, f'level0-{did}'): continue
        look = d.get('look_at') if isinstance(d.get('look_at'), dict) else {}
        data = {'breadcrumb': str(d.get('file_breadcrumb') or ''), 'context': str(d.get('context_comment') or ''),
                'note': str(d.get('python_fluency_note') or ''), 'fades': fades, 'move': str(d.get('expert_move') or move),
                'hints': hints_of(d, levels=True), 'look': {str(lv): [str(x) for x in as_list(look.get(f'level_{lv}'))] for lv in (1, 2, 3)}}
        cards.append((did, 'drill', str(d.get('context_comment') or 'Complete the code.'), str(d['full_canonical_code']), [], data, 100 + 2 * i + 1, None))
        ann, prompt, pts, authored = worked(d)
        cards.append((f'level0-{did}', 'level0', prompt, str(d['full_canonical_code']), pts,
                      {'breadcrumb': data['breadcrumb'], 'context': data['context'], 'annotations': ann, 'authored': authored}, 100 + 2 * i, did))
    for i, c in enumerate(as_list(doc.get('tier_2_self_explanation_cards') or doc.get('self_explanation_flashcards'))):
        if not isinstance(c, dict) or not c.get('front_prompt') or not c.get('back_explanation'):
            notes.append(f'explain card {i + 1}: needs a front prompt and a back explanation'); continue
        pts = rubric_points(as_list(c.get('eval_rubric')))
        cid_ = c.get('id') or f'card_{i + 1:02}'
        if not tag(c, 'explain', cid_, f'preread-{cid_}'): continue
        data = {'type': str(c.get('card_type') or ''), 'breadcrumb': str(c.get('file_breadcrumb') or ''),
                'move': str(c.get('expert_move') or move), 'hints': hints_of(c)}
        cards.append((cid_, 'explain', str(c['front_prompt']), str(c['back_explanation']), pts, data, 200 + 2 * i + 1, None))
        pre = c.get('preread') if isinstance(c.get('preread'), dict) else {}
        ideas = [str(x) for x in as_list(pre.get('key_ideas'))] or [p['idea'] for p in pts]
        near = pre.get('near_example') if isinstance(pre.get('near_example'), dict) and pre['near_example'].get('code') else None
        pd = {'type': data['type'], 'breadcrumb': data['breadcrumb'], 'ideas': ideas, 'authored': bool(pre), 'try': str(pre.get('try_first') or ''),
              'near': {'code': str(near['code']), 'ask': str(near.get('ask') or 'What would break here?')} if near else None}
        cards.append((f'preread-{cid_}', 'preread', str(near.get('ask') or 'What would break here?') if near else '',
                      str(near.get('answer') or '') if near else '', [], pd, 200 + 2 * i, cid_))
    for i, k in enumerate(as_list(doc.get('code_cards'))):          # 4.32: predict, trace, parsons, write
        if not isinstance(k, dict): notes.append(f'code card {i + 1}: not a card'); continue
        kid, role = k.get('id') or f'code_{i + 1:02}', str(k.get('role') or '')
        if role not in CODE_KINDS and role not in LATER_ROLES:
            notes.append(f'{kid}: role "{role}" is not one of {", ".join(CODE_KINDS)}'); continue
        made = code_card(k, role) if role in CODE_KINDS else None
        if isinstance(made, str): notes.append(f'{kid}: {made}'); continue
        if not tag(k, role, kid, f'learn-{kid}'): continue
        prompt, answer_, pts, data = made
        data.update({'move': str(k.get('expert_move') or move), 'hints': hints_of(k)})
        cards.append((kid, role, prompt, answer_, pts, data, 300 + i, None))
    keep, ids = set(), {}
    for item_id, kind, prompt, answer, pts, data, o, learn_of in cards:
        cid = f'{mid}:{slug(item_id)}'
        if cid in keep: cid = f'{cid}-{o}'
        keep.add(cid); ids[item_id] = cid
    for item_id, kind, prompt, answer, pts, data, o, learn_of in cards:
        upsert_card(db, ids[item_id], mid, kind, prompt, answer, pts, data, as_list(meta.get('concepts_covered')), o,
                    ids.get(learn_of) if learn_of else None, *tags.get(item_id, (None, None, None, 0)))
    # a practice card points at its Learn card too, so the page can offer "read the lesson again"
    for item_id, kind, prompt, answer, pts, data, o, learn_of in cards:
        if learn_of: db.execute("UPDATE cards SET learn_of=? WHERE id=? AND kind NOT IN (?,?,?,?)", (ids[item_id], ids[learn_of], *LEARN))
    for (old,) in db.execute("SELECT id FROM cards WHERE deck=?", (mid,)).fetchall():
        if old not in keep: db.execute("DELETE FROM cards WHERE id=?", (old,))     # attempts and schedule rows are kept
    lint = [str(x) for x in as_list(meta.get('lint'))]
    db.execute("INSERT INTO modules(id,name,project,built_in,at,summary,concepts,files,source,course,cmodule,ord) VALUES(?,?,?,?,?,?,?,?,?,?,?,?) "
               "ON CONFLICT(id) DO UPDATE SET name=excluded.name,project=excluded.project,built_in=excluded.built_in,"
               "summary=excluded.summary,concepts=excluded.concepts,files=excluded.files,source=excluded.source,"
               "course=excluded.course,cmodule=excluded.cmodule,ord=excluded.ord",
               (mid, name, str(meta.get('project') or ''), 1 if built_in else 0, stamp(meta.get('timestamp'), mid),
                json.dumps({**{k: str(summary.get(k) or '') for k in ('schematic_mental_model', 'design_rules_heuristics',
                            'hard_rules_invariants', 'hci_human_factors_bridge')}, 'lint': lint}),
                json.dumps([str(x) for x in as_list(meta.get('concepts_covered'))]),
                json.dumps([str(x) for x in as_list(meta.get('source_files'))]), os.path.basename(source), course, cmodule, ord_))
    if course is None: ensure_loose(db)
    db.commit()
    return sum(1 for c in cards if c[1] not in LEARN), notes

def is_course(doc):
    return isinstance(doc, dict) and str(doc.get('format') or '').startswith('mentor-course/')

def import_course(db, doc, source, built_in):
    """One course file (format mentor-course/1, docs/mentor.md): the course, its modules, LOs and notes, and each lesson
    through import_module. Lenient: anything broken is skipped and named in the notes (check-deck.py is the strict one).
    What the file no longer has goes; attempts and schedule rows stay. Returns (cards added, notes). Caller holds DB_LOCK."""
    cid = slug(doc.get('id') or os.path.basename(source).rsplit('.', 1)[0])
    if cid == LOOSE: raise ValueError(f'the course id "{LOOSE}" is kept for lessons outside courses')
    name, notes, n = str(doc.get('name') or cid), [], 0
    for (old,) in db.execute("SELECT id FROM courses WHERE source=? AND id NOT IN (?,?)", (os.path.abspath(source), cid, LOOSE)).fetchall():
        drop_course(db, old)                     # the same file under a new id: one course, not two
    db.execute("INSERT INTO courses(id,name,summary,requires,retention,data,source,at) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET "
               "name=excluded.name,summary=excluded.summary,requires=excluded.requires,retention=excluded.retention,"
               "data=excluded.data,source=excluded.source,at=excluded.at",
               (cid, name, str(doc.get('summary') or ''), json.dumps([slug(r) for r in as_list(doc.get('requires'))]),
                float(doc['retention']) if isinstance(doc.get('retention'), (int, float)) else 0.9,
                json.dumps({'capstone': doc.get('capstone'), 'sources': as_list(doc.get('sources'))}), os.path.abspath(source), time.time()))
    keep = {'cmodules': set(), 'modules': set(), 'los': set(), 'notes': set()}
    def put_los(items, scope, owner):
        ids = set()
        for lo in as_list(items):
            if not isinstance(lo, dict) or not lo.get('id'): notes.append(f'{owner}: an LO without an id'); continue
            lid, parent = f"{cid}/{lo['id']}", lo.get('parent')
            ids.add(str(lo['id'])); keep['los'].add(lid)
            db.execute("INSERT OR REPLACE INTO los(id,course,owner,scope,text,verb,bloom,mode,knowledge,condition,standard,parent) "
                       "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (lid, cid, owner, scope, *(str(lo.get(k) or '') for k in
                       ('text', 'verb', 'bloom', 'mode', 'knowledge', 'condition', 'standard')), f'{cid}/{parent}' if parent else None))
        return ids
    put_los(doc.get('los'), 'course', cid)
    for i, mod in enumerate(as_list(doc.get('modules'))):
        if not isinstance(mod, dict) or not mod.get('id'): notes.append(f'module {i + 1}: not a module with an id'); continue
        cm = f"{cid}/{slug(mod['id'])}"; keep['cmodules'].add(cm)
        db.execute("INSERT OR REPLACE INTO cmodules(id,course,name,ord,requires) VALUES(?,?,?,?,?)",
                   (cm, cid, str(mod.get('name') or mod['id']), i, json.dumps([f'{cid}/{slug(r)}' for r in as_list(mod.get('requires'))])))
        put_los(mod.get('los'), 'module', cm)
        for j, les in enumerate(as_list(mod.get('lessons'))):
            if not isinstance(les, dict) or not les.get('id'): notes.append(f"{mod['id']} lesson {j + 1}: not a lesson with an id"); continue
            lid = slug(f"{cid}--{les['id']}")
            if lid in keep['modules']: notes.append(f"lesson id {les['id']} is used twice in the course: the second one (in {mod['id']}) is skipped"); continue
            keep['modules'].add(lid)
            los, nids = put_los(les.get('los'), 'lesson', lid), set()
            for nt in as_list(les.get('notes')):
                if not isinstance(nt, dict) or not nt.get('id'): notes.append(f"{les['id']}: a note without an id"); continue
                nids.add(str(nt['id'])); keep['notes'].add(f"{lid}:{nt['id']}")
                db.execute("INSERT OR REPLACE INTO notes(id,lesson,kind,source_ref) VALUES(?,?,?,?)",
                           (f"{lid}:{nt['id']}", lid, str(nt.get('kind') or ''), json.dumps(nt.get('source_ref') or {})))
            meta = {**(les.get('metadata') if isinstance(les.get('metadata'), dict) else {}), 'project': name}
            meta.setdefault('module_name', str(les.get('name') or les['id']))
            k, nn = import_module(db, {**les, 'metadata': meta}, lid, source, built_in, course=cid, cmodule=cm, ord_=i * 100 + j, los=los, note_ids=nids)
            # 4.32: the lessons in this course that must reach PASS before this one unlocks
            db.execute("UPDATE modules SET requires=? WHERE id=?", (json.dumps([slug(f"{cid}--{r}") for r in as_list(les.get('requires'))
                                                                              if isinstance(r, (str, int))]), lid))
            n += k; notes += [f"{les['id']}: {x}" for x in nn]
    lessons = [r[0] for r in db.execute("SELECT id FROM modules WHERE course=?", (cid,))]
    for old in lessons:
        if old not in keep['modules']: db.execute("DELETE FROM cards WHERE deck=?", (old,)); db.execute("DELETE FROM modules WHERE id=?", (old,))
    for old, les in db.execute("SELECT id, lesson FROM notes").fetchall():
        if les in lessons and old not in keep['notes']: db.execute("DELETE FROM notes WHERE id=?", (old,))
    for table in ('cmodules', 'los'):
        for (old,) in db.execute(f"SELECT id FROM {table} WHERE course=?", (cid,)).fetchall():
            if old not in keep[table]: db.execute(f"DELETE FROM {table} WHERE id=?", (old,))
    db.execute("UPDATE modules SET at=? WHERE course=?", (time.time(), cid))     # one course, one time: Lessons orders them by ord
    db.commit()
    return n, notes

def drop_course(db, cid):
    """A course and everything it imported, except attempts and schedule rows (your history stays)."""
    lessons = [r[0] for r in db.execute("SELECT id FROM modules WHERE course=?", (cid,))]
    for les in lessons:
        db.execute("DELETE FROM cards WHERE deck=?", (les,)); db.execute("DELETE FROM notes WHERE lesson=?", (les,))
    for table, col in (('modules', 'course'), ('los', 'course'), ('cmodules', 'course'), ('courses', 'id')):
        db.execute(f"DELETE FROM {table} WHERE {col}=?", (cid,))

def stamp(iso, mid):
    """When the module was written: its ISO timestamp, else the YYYYMMDD_HHMMSS file name, else now."""
    for s, fmt in ((str(iso or '')[:19], '%Y-%m-%dT%H:%M:%S'), (mid[:15], '%Y%m%d_%H%M%S')):
        try: return time.mktime(time.strptime(s, fmt))
        except ValueError: pass
    return time.time()

def scan_inbox(db):
    """Import new or changed files from the inbox. Cheap when nothing changed (one directory listing)."""
    if not getattr(db, 'own_inbox', True): return
    try: entries = [e for e in os.scandir(INBOX) if e.name.endswith('.json') and e.is_file()]
    except OSError: return
    seen = {r['path']: r for r in db.execute("SELECT path, mtime, size FROM imports")}
    for e in entries:
        st = e.stat(); old = seen.get(e.name)
        if old and old['mtime'] == st.st_mtime and old['size'] == st.st_size: continue
        mid, ok, msg = slug(e.name[:-5]), 0, ''
        try:
            with open(e.path, encoding='utf-8') as fh: doc = json.load(fh)
            if is_course(doc):
                with DB_LOCK:
                    n, notes = import_course(db, doc, e.path, False)
                mid = slug(doc.get('id') or e.name[:-5])
                where = f" in {db.execute('SELECT COUNT(*) FROM modules WHERE course=?', (mid,)).fetchone()[0]} lessons"
            elif is_module(doc):
                with DB_LOCK:
                    n, notes = import_module(db, doc, mid, e.path, False)
                where = ''
            else: raise ValueError('not a Mentor lesson or course (no tier_1/2/3 lists, cta_summary or "format": "mentor-course/1")')
            ok, msg = (1 if n else 0), (f'{n} card{"s" if n != 1 else ""}{where}' + (f'; skipped: {"; ".join(notes[:6])}' if notes else ''))
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

def code_tokens_words(s):
    """Words of code or program output (4.32 code cards): like tokens(), but `for`, `in`, `is`, `and`, `or` count, as they do in code."""
    return [stem(w) for w in norm(s).split()]

def phrase_hit(phrase, ans_tokens, tok=tokens):
    ws = tok(phrase)
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

def point_hit(p, at, tok=tokens):
    if p.get('any'): return any(phrase_hit(k, at, tok) for k in p['any'])
    words = p.get('auto', [])
    return bool(words) and sum(word_in(w, at) for w in words) >= max(1, math.ceil(len(words) * 0.4))

def grade(card, answer, tok=tokens):
    """Returns coverage 0..1, which key ideas were hit/missed, and the features a later learned grader uses."""
    points = json.loads(card['points']) if isinstance(card['points'], str) else card['points']
    at = set(tok(answer))
    hits, missed, per = [], [], []
    for p in points:
        ok = point_hit(p, at, tok)
        per.append(1 if ok else 0)
        (hits if ok else missed).append(p['idea'])
    total = sum(p.get('weight', 1) for p in points) or 1
    coverage = sum(p.get('weight', 1) for p, h in zip(points, per) if h) / total
    ref = set(tok(card['answer']))
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
    typed = [str(x) for x in typed_boxes(text)] + [''] * len(expected)
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

def typed_boxes(text):
    """The page's per-box answer: a flat JSON list of strings (numbers accepted). Anything else is one typed answer, [text]:
    plain text, broken JSON, JSON nested deeper than the parser goes (RecursionError), or a list holding lists or objects."""
    if not text.strip().startswith('['): return [text]
    try: got = json.loads(text)
    except (ValueError, RecursionError): return [text]
    ok = isinstance(got, list) and all(isinstance(x, (str, int, float)) and not isinstance(x, bool) for x in got)
    return got if ok else [text]

def typed_list(text, n):
    """A card's per-box answer (typed_boxes), as strings, padded or cut to n boxes."""
    got = [str(x) for x in typed_boxes(text)]
    return got[:max(n, 0) or None] + [''] * max(0, n - len(got))

def grade_trace(card, text):
    """A trace card: the value after each step's line, each step graded on its own by the key-idea grader (its state, or an
    accepted wording). Returns coverage, features, one row per step."""
    pts, data = json.loads(card['points'] or '[]'), json.loads(card['data'] or '{}')
    typed = typed_list(text, len(pts))
    per = [{'n': i + 1, 'line': ln, 'ok': bool(typed[i].strip()) and point_hit(p, set(code_tokens_words(typed[i])), code_tokens_words), 'typed': typed[i],
            'expected': p['any'][0]} for i, (p, ln) in enumerate(zip(pts, data.get('steps') or [0] * len(pts)))]
    cov = sum(p['ok'] for p in per) / (len(per) or 1)
    return cov, {'steps': len(per), 'right': sum(p['ok'] for p in per)}, per

def grade_parsons(card, text):
    """A Parsons card: exact order, one point per line in its right place (trailing spaces don't matter)."""
    want = json.loads(card['data'] or '{}').get('lines') or []
    typed = typed_list(text, len(want))
    per = [{'n': i + 1, 'ok': typed[i].rstrip() == w.rstrip(), 'typed': typed[i], 'expected': w} for i, w in enumerate(want)]
    cov = sum(p['ok'] for p in per) / (len(per) or 1)
    return cov, {'lines': len(per), 'right': sum(p['ok'] for p in per)}, per

def shuffled(lines, seed):
    """A Parsons card's lines in a mixed order that is never the right one; the same seed gives the same order."""
    import random
    order = list(range(len(lines))); random.Random(seed).shuffle(order)
    if len(set(lines)) > 1 and [lines[i] for i in order] == lines: order = order[1:] + order[:1]
    return [lines[i] for i in order]

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

# Learning steps (Anki's behaviour on FSRS, spec section 7): a new card comes back after 1 min, then 10 min, before FSRS
# schedules it in days; a lapsed card (Again on a review) relearns with one 10 min step. Seconds.
LEARN_STEPS, RELEARN_STEPS = (60, 600), (600,)

def hard_delay(steps, i):
    """Hard on a learning step: on the first of two or more steps, halfway between the first two (whole minutes, so the
    button's preview is exact); with one step, half as long again; otherwise the current step once more."""
    if i == 0 and len(steps) > 1: return round((steps[0] + steps[1]) / 2 / 60) * 60
    if len(steps) == 1: return round(steps[0] * 1.5)
    return steps[i]

def schedule(row, g, now):
    """row = previous sched row or None; g = rating 1..4. Returns the new (stability, difficulty, due, reps, lapses, step,
    relearn). step: the learning step the card is now at (0-based), None once FSRS schedules it in days.
    A new card's first rating sets its FSRS memory (stability, difficulty); answers on the same day's steps leave it as it
    is (FSRS-4.5 learns from one review a day), and graduating gives the interval that memory earns."""
    new = row is None or not row['reps']
    step = None if new else row['step']
    if new:
        s, d, reps, lapses, step, relearn = W[g - 1], init_d(g), 1, 0, 0, 0
    elif step is not None:
        s, d, reps, lapses, relearn = row['stability'], row['difficulty'], row['reps'] + 1, row['lapses'] or 0, row['relearn'] or 0
    else:
        s, d = row['stability'], row['difficulty']
        r = retrievability(max(0, (now - (row['last'] or now)) / DAY), s)
        d = d - W[6] * (g - 3)
        d = min(10, max(1, W[7] * init_d(3) + (1 - W[7]) * d))
        if g == 1:                # a lapse: FSRS's new stability, then the relearning steps
            s = W[11] * d ** -W[12] * ((s + 1) ** W[13] - 1) * math.exp(W[14] * (1 - r))
            if RELEARN_STEPS: return s, d, now + RELEARN_STEPS[0], row['reps'] + 1, (row['lapses'] or 0) + 1, 0, 1
            return s, d, now + interval_days(s) * DAY, row['reps'] + 1, (row['lapses'] or 0) + 1, None, 0
        hard = W[15] if g == 2 else 1
        easy = W[16] if g == 4 else 1
        s = s * (1 + math.exp(W[8]) * (11 - d) * s ** -W[9] * (math.exp(W[10] * (1 - r)) - 1) * hard * easy)
        return s, d, now + interval_days(s) * DAY, row['reps'] + 1, row['lapses'] or 0, None, 0
    steps = RELEARN_STEPS if relearn else LEARN_STEPS
    if not steps: return s, d, now + interval_days(s) * DAY, reps, lapses, None, 0
    i = 0 if new else min(step, len(steps) - 1)
    if g == 1: return s, d, now + steps[0], reps, lapses, 0, relearn
    if g == 2: return s, d, now + hard_delay(steps, i), reps, lapses, i, relearn
    if g == 3 and i + 1 < len(steps): return s, d, now + steps[i + 1], reps, lapses, i + 1, relearn
    # graduate: Good on the last step, or Easy on any step. Easy is a day longer than Good would be from the same memory,
    # except on a new card, whose memory Easy already set (FSRS's own first Easy interval)
    days = interval_days(s) + (1 if g == 4 and not new else 0)
    return s, d, now + days * DAY, reps, lapses, None, 0

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
    if (attempt['hints'] or 0) >= 3: return lv, False       # a near example or the answer was shown: no step up this time
    feats = json.loads(attempt['features'] or '{}')
    prev = db.execute("SELECT coverage FROM attempts WHERE card_id=? AND id<? AND level=? AND rating IS NOT NULL AND COALESCE(undone, 0)=0 ORDER BY id DESC LIMIT 1",
                      (card['id'], attempt['id'], lv)).fetchone()
    if attempt['ms'] <= fast_ms(lv, feats.get('blanks', 1)) or (prev and prev['coverage'] >= 0.99):
        higher = [int(k) for k in fades if int(k) > lv]
        if higher: return min(higher), True
    return lv, False

def plan(db, card, srow, attempt, g, now):
    s, d, due, reps, lapses, step, relearn = schedule(srow, g, now)
    level, up = (next_level(db, card, srow, attempt, g) if card['kind'] == 'drill' else (1, False))
    if up: due = min(due, now + DAY)          # try the harder level soon instead of after a long gap
    return s, d, due, reps, lapses, step, relearn, level, up

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

def hint_rungs(c, level=None):
    """The four rungs for a card: authored nudge and near example, the expert's move, the answer."""
    data = json.loads(c['data'] or '{}')
    h = data.get('hints') or []
    if c['kind'] == 'drill': h = (h.get(str(level)) if isinstance(h, dict) else h) or []
    move = data.get('move') or MOVE.get(c['kind'], MOVE['define'])
    if c['kind'] == 'drill' and level == 3:
        ans = c['answer']
    elif c['kind'] == 'drill':
        ans = ', '.join(a if isinstance(a, str) else a[0] for a in data['fades'][str(level)]['answers'])
    else: ans = c['answer']
    return [h[0] if h else None, move, h[1] if len(h) > 1 else None, ans]

def card_payload(db, c, read_only=False, st=None, tm=None):
    """What the page needs to ask the question - never the answer (a Learn card is the lesson, so it carries it).
    4.37: its track, whether the track asks "How sure?" on every card, and teach_id: the Learn card "Teach me first" opens
    (the card's own, else its lesson's orientation; None when there is nothing to read first)."""
    c = filled(c)
    data = json.loads(c['data'] or '{}')
    mod = db.execute("SELECT name, project FROM modules WHERE id=?", (c['deck'],)).fetchone()
    st, tm = st or settings(db), tm or track_map(db)
    track = track_of(tm, c['deck'])
    teach = c['learn_of'] if c['kind'] not in LEARN else None
    if c['kind'] not in LEARN and not teach:
        o = db.execute("SELECT id FROM cards WHERE deck=? AND kind='orientation' AND COALESCE(is_check, 0)=0 ORDER BY ord LIMIT 1", (c['deck'],)).fetchone()
        teach = o['id'] if o else None
    out = {'id': c['id'], 'deck': c['deck'], 'kind': c['kind'], 'tier': TIER.get(c['kind'], 3), 'prompt': c['prompt'],
           'reps': c['reps'] or 0, 'module': fill(mod['name']) if mod else None, 'project': fill(mod['project']) if mod else None,
           'learn_of': c['learn_of'], 'refresh': bool(c['refresh']) if 'refresh' in c.keys() else False,
           'track': track, 'ask_confidence': track in st['ask_confidence'], 'teach_id': teach}
    if c['kind'] == 'drill':
        lv = card_level(c, c['level'])
        fade = data['fades'][str(lv)]
        rungs = hint_rungs(c, lv)
        out.update({'level': lv, 'levels': sorted(int(k) for k in data['fades']), 'level_name': LEVELS[lv], 'code': fade['code'],
                    'breadcrumb': data.get('breadcrumb', ''), 'context': data.get('context', ''),
                    'widths': [max(len(x if isinstance(x, str) else x[0]), 3) for x in fade['answers']],
                    'rungs': [bool(r) for r in rungs]})
    elif c['kind'] == 'explain':
        out.update({'type': data.get('type', ''), 'breadcrumb': data.get('breadcrumb', ''), 'rungs': [bool(r) for r in hint_rungs(c)]})
    elif c['kind'] == 'term':
        out.update({'category': data.get('category', ''), 'rungs': [bool(r) for r in hint_rungs(c)]})
    elif c['kind'] == 'define':
        out.update({'rungs': [bool(r) for r in hint_rungs(c)]})
    elif c['kind'] in CODE_KINDS:          # 4.32: never the model answer, the trace values or the lines' right order
        out.update({'breadcrumb': data.get('breadcrumb', ''), 'lang': data.get('lang', 'python'), 'rungs': [bool(r) for r in hint_rungs(c)]})
        if c['kind'] in ('predict', 'trace'): out['code'] = data.get('code', '')
        if c['kind'] == 'trace': out['steps'] = data.get('steps', [])
        if c['kind'] == 'parsons': out['lines'] = shuffled(data.get('lines', []), f"{c['id']}#{c['reps'] or 0}")
        if c['kind'] == 'write': out['starter'] = data.get('starter', '')
    if c['kind'] not in LEARN and 'is_check' in c.keys() and c['is_check']: out['check'] = True     # served as a module check
    elif c['kind'] == 'orientation':
        out.update({k: data.get(k) for k in ('files', 'terms', 'bridge')})
    elif c['kind'] == 'teach':
        spot = data.get('spot')
        out.update({k: data.get(k, '') for k in ('category', 'definition', 'anchor', 'contrast', 'move', 'try')})
        out['spot'] = {'snippet': spot['snippet'], 'lines': len(spot['snippet'].split('\n'))} if spot else None
        if read_only and spot: out['spot'].update({'line': spot['line'], 'why': spot['why']})
    elif c['kind'] == 'level0':
        out.update({'code': c['answer'], 'annotations': data.get('annotations', []), 'breadcrumb': data.get('breadcrumb', ''),
                    'context': data.get('context', ''), 'graded': bool(json.loads(c['points'] or '[]'))})
    elif c['kind'] == 'preread':
        out.update({'type': data.get('type', ''), 'breadcrumb': data.get('breadcrumb', ''), 'ideas': data.get('ideas', []),
                    'near': data.get('near'), 'try': data.get('try', '')})
        if read_only and data.get('near'): out['near'] = {**data['near'], 'answer': c['answer']}
    return out

CARD_Q = ("SELECT c.*, s.due, s.reps, s.level, s.refresh, s.step, m.at AS mat FROM cards c LEFT JOIN sched s ON s.card_id=c.id "
          "LEFT JOIN modules m ON m.id=c.deck")

def one_card(db, card_id):
    """A card to read again (Lessons view): a Learn card with its answers, never a practice card's answer."""
    c = db.execute(CARD_Q + " WHERE c.id=?", (card_id,)).fetchone()
    if not c or c['kind'] not in LEARN or c['is_check']: return None
    return card_payload(db, c, read_only=True)

def practice_card(db, card_id):
    """One practice card asked again (the end-of-session replay of today's mistakes): the question, never its answer."""
    c = db.execute(CARD_Q + " WHERE c.id=?", (card_id,)).fetchone()
    if not c or c['kind'] in LEARN or c['is_check']: return None
    return card_payload(db, c)

GROUP_SEP = ' › '   # " › ": a lesson whose project is "A › B" sits in submenu B of menu A (4.22.0)

def group_ids(db, deck):
    """The lesson ids a "group:<project>" choice stands for: lessons whose project is that name or lies under it
    ("group:GAME_RESEARCH" takes "GAME_RESEARCH › Topics" and "GAME_RESEARCH › Games"). None for a plain deck id."""
    if not deck or not deck.startswith('group:'): return None
    name = deck[6:]
    return [r[0] for r in db.execute("SELECT id FROM modules WHERE project=? OR project LIKE ?", (name, name + GROUP_SEP + '%'))]

def deck_where(db, deck):
    """SQL filter and arguments for the cards of one deck, one lesson, or a whole group of lessons."""
    ids = group_ids(db, deck)
    if ids is None: return ("c.deck=?", [deck]) if deck else ("", [])
    if not ids: return "0", []
    return "c.deck IN (" + ",".join("?" * len(ids)) + ")", ids

# ---------- tracks (4.37): what Today pins and the shelf holds ----------
# A track is what a person picks to study: a plain deck (its id), or every lesson of one project or course ("group:<name>",
# submenus included: "GAME_RESEARCH › Topics" and "GAME_RESEARCH › Games" are one track), or a lesson without a project
# (its own id). The ids are ones deck_where() already takes, so a track is studied like any choice in the picker.
def track_map(db):
    """{deck or lesson id: track id} for every card's deck in this database."""
    out = {}
    for r in db.execute("SELECT id, project FROM modules"):
        root = (r['project'] or '').split(GROUP_SEP)[0].strip()
        out[r['id']] = 'group:' + root if root else r['id']
    for (d,) in db.execute("SELECT DISTINCT deck FROM cards"):
        out.setdefault(d, d)
    return out

def tracks(db, names=None):
    """Every track: [{id, name, lessons}] in a stable order (name). names: plain decks' names {deck id: name}."""
    tm, mods = track_map(db), {r['id']: r for r in db.execute("SELECT id, name, project FROM modules")}
    by = {}
    for d, t in tm.items(): by.setdefault(t, []).append(d)
    out = []
    for t, ds in by.items():
        if t.startswith('group:'): name = fill(mods[ds[0]]['name']) if len(ds) == 1 else fill(t[6:])
        elif t in mods: name = fill(mods[t]['name'])
        else: name = fill((names or {}).get(t) or t)
        out.append({'id': t, 'name': name, 'lessons': sorted(ds)})
    return sorted(out, key=lambda x: (x['name'].lower(), x['id']))

def track_of(tm, deck):
    return tm.get(deck, deck)

def scope_of(db, deck):
    """The track a chosen deck, lesson or group belongs to (a group choice is its own track); None for no choice."""
    if not deck: return None
    if deck.startswith('group:'): return 'group:' + deck[6:].split(GROUP_SEP)[0].strip()
    return track_of(track_map(db), deck)

def new_today(db, tm, now):
    """{track: practice cards seen for the first time today}: a card counts on the local day of its first rating (not undone)."""
    out = {}
    for r in db.execute("SELECT c.deck, MIN(a.at) AS first FROM attempts a JOIN cards c ON c.id=a.card_id WHERE a.rating>0 "
                        "AND COALESCE(a.undone, 0)=0 AND c.kind NOT IN (?,?,?,?) AND COALESCE(c.is_check, 0)=0 GROUP BY a.card_id", LEARN):
        if r['first'] >= day_start(now):
            t = track_of(tm, r['deck']); out[t] = out.get(t, 0) + 1
    return out

def new_limit(st, track):
    lim = st['new_per_day']
    return lim[track] if track in lim else lim.get('*', NEW_PER_DAY)

# ---------- study settings (stored in each person's database, next to the history they shape) ----------
# bury: siblings wait until tomorrow (spec section 15.3). teach_first: the old order, every practice card after its Learn
# card (4.37: off; a practice card comes first and its teaching is the feedback). pinned: up to PIN_MAX tracks on Today;
# shelved: tracks hidden from study and from every count, history kept. new_per_day: {track: n} ("*" = every track),
# NEW_PER_DAY when not set. goal: {track: one line}, the owner's words. ask_confidence: tracks that ask "How sure?" on
# every card (others ask on every CONF_EVERY-th card).
SETTINGS = {'bury': True, 'teach_first': False, 'pinned': [], 'shelved': [], 'new_per_day': {}, 'goal': {}, 'ask_confidence': []}
PIN_MAX, NEW_PER_DAY, CONF_EVERY = 3, 10, 5

class Refusal(ValueError):
    """A setting Mentor will not save, with the sentence that says what to do instead."""

def _ids(v):
    if not isinstance(v, list) or not all(isinstance(x, str) and 0 < len(x) <= 200 for x in v) or len(v) > 200: raise TypeError
    out = []
    for x in v:
        if x not in out: out.append(x)
    return out

def _merge(old, v, check):
    """A map setting is merged: {track: value} sets one, {track: null} takes it out again."""
    if not isinstance(v, dict) or len(v) > 200: raise TypeError
    out = dict(old)
    for k, x in v.items():
        if not isinstance(k, str) or not 0 < len(k) <= 200: raise TypeError
        if x is None: out.pop(k, None)
        else: out[k] = check(x)
    return out

def _count(x):
    if isinstance(x, bool) or not isinstance(x, int) or not 0 <= x <= 999: raise TypeError
    return x

def _goal(x):
    if not isinstance(x, str): raise TypeError
    return ' '.join(x.split())[:140]

def settings(db):
    out = {k: (list(v) if isinstance(v, list) else dict(v) if isinstance(v, dict) else v) for k, v in SETTINGS.items()}
    for r in db.execute("SELECT key, value FROM settings"):
        if r['key'] in SETTINGS:
            try: v = json.loads(r['value'])
            except ValueError: continue
            if isinstance(v, type(SETTINGS[r['key']])): out[r['key']] = v
    return out

def set_settings(db, changes):
    """Save the known keys with the right type; anything else is ignored. Returns every setting. A fourth pin raises
    Refusal (nothing is saved); a value of the wrong type is ignored."""
    changes = {k: v for k, v in (changes or {}).items() if k in SETTINGS}
    with DB_LOCK:
        cur = settings(db); new = {}
        for k, v in changes.items():
            try:
                if k in ('pinned', 'shelved', 'ask_confidence'): new[k] = _ids(v)
                elif k == 'new_per_day': new[k] = _merge(cur[k], v, _count)
                elif k == 'goal': new[k] = _merge(cur[k], v, _goal)
                elif isinstance(v, type(SETTINGS[k])): new[k] = v
            except TypeError: pass              # a wrong type is ignored, as for every setting
        if 'pinned' in new and len(new['pinned']) > PIN_MAX:
            raise Refusal(f'You can pin {PIN_MAX} tracks. Unpin one first: open the shelf on Today and choose Unpin on the track you need least.')
        # a track is pinned or shelved, never both: the list sent in this request wins
        if 'shelved' in new: new['pinned'] = [x for x in new.get('pinned', cur['pinned']) if x not in new['shelved']]
        if 'pinned' in new: new['shelved'] = [x for x in new.get('shelved', cur['shelved']) if x not in new['pinned']]
        for k, v in new.items():
            db.execute("INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (k, json.dumps(v)))
        db.commit()
    return settings(db)

def day_start(now):
    """Local midnight before now: "until tomorrow" ends here plus a day."""
    t = time.localtime(now)
    return time.mktime((t.tm_year, t.tm_mon, t.tm_mday, 0, 0, 0, 0, 0, -1))

def buried(db, now):
    """Bury siblings (Anki): once a card is rated today, the other cards from its note wait until tomorrow. Returns a test
    for a card row (needs id, kind, note, step). A Learn card is never buried, nor a card in its learning steps (it is
    already on its way), nor anything when the setting is off. Notes come from courses; a Loose lesson card has none."""
    if not settings(db)['bury']: return lambda r: False
    rated = {}
    for r in db.execute("SELECT DISTINCT c.note, a.card_id FROM attempts a JOIN cards c ON c.id=a.card_id WHERE a.at>=? AND a.rating>0 "
                        "AND COALESCE(a.undone, 0)=0 AND c.note IS NOT NULL", (day_start(now),)):
        rated.setdefault(r['note'], set()).add(r['card_id'])
    return lambda r: bool(r['note'] and rated.get(r['note'], set()) - {r['id']} and r['kind'] not in LEARN and r['step'] is None)

# ---------- mastery, unlock and module checks (spec section 8; 4.32) ----------
def right_answer(rating, hints):
    """Answered right, for mastery and module checks: rated Good or Easy, with no hint above rung 2 (spec section 8)."""
    return (rating or 0) >= 3 and (hints or 0) <= 2

def mastery(db, now=None, hidden=None):
    """Where each course lesson and course module stands. Loose lessons are never locked and have no module check.
    A lesson's progress is the share of its practice cards answered right at least once (right_answer); it is mastered
    at PASS (80%). A module is mastered when all its lessons are; it is locked while a module it `requires` isn't mastered.
    A lesson is locked while its module is, or while a lesson it `requires` isn't mastered. A module's check items are
    served once the module is mastered (and not locked): each once; one answered wrong comes back the next day, until the
    check passes (PASS of its items right, each item's latest answer counting). An item whose note had a sibling rated today
    (bury siblings, `hidden`: buried() unless given) waits until tomorrow: the check's `now` counts only the items served
    today and `later` the ones held back, so the course map and the queue say the same.
    Returns {'lessons': {id: {...}}, 'modules': {cmodule id: {...}}, 'checks': {check item ids to serve now}}."""
    now = now or time.time()
    hidden = hidden or buried(db, now)
    lessons = {r['id']: dict(r) for r in db.execute("SELECT id, name, course, cmodule, requires FROM modules WHERE course IS NOT NULL AND course<>?", (LOOSE,))}
    out = {'lessons': {}, 'modules': {}, 'checks': set()}
    if not lessons: return out
    latest, right = {}, set()            # card -> its latest rating (not undone); cards ever answered right
    for r in db.execute("SELECT card_id, rating, hints, at FROM attempts WHERE rating>0 AND COALESCE(undone, 0)=0 ORDER BY id"):
        latest[r['card_id']] = r
        if right_answer(r['rating'], r['hints']): right.add(r['card_id'])
    practice, checks, learn, held = {}, {}, {}, set()      # held: check items buried today
    for c in db.execute("SELECT c.id, c.deck, c.kind, c.is_check, c.note, s.reps, s.step FROM cards c LEFT JOIN sched s ON s.card_id=c.id"):
        if c['deck'] not in lessons: continue
        if c['kind'] in LEARN:
            if not c['is_check']: learn.setdefault(c['deck'], []).append(bool(c['reps']))
        else:
            (checks if c['is_check'] else practice).setdefault(c['deck'], []).append(c['id'])
            if c['is_check'] and hidden(c): held.add(c['id'])
    for lid, les in lessons.items():
        cards = practice.get(lid, [])
        if cards: prog = sum(1 for x in cards if x in right) / len(cards)
        else: prog = sum(learn.get(lid, [])) / (len(learn.get(lid, [])) or 1)       # a lesson of Learn cards only: read it
        try: req = [r for r in json.loads(les['requires'] or '[]') if r in lessons and r != lid]
        except (ValueError, TypeError): req = []
        out['lessons'][lid] = {'progress': round(prog, 3), 'mastered': prog >= PASS - 1e-9, 'requires': req, 'cmodule': les['cmodule'],
                               'name': les['name'], 'right': sum(1 for x in cards if x in right), 'cards': len(cards)}
    mods = {r['id']: dict(r) for r in db.execute("SELECT id, name, course, requires FROM cmodules WHERE course<>?", (LOOSE,))}
    for mid, mod in mods.items():
        ls = [x for x in out['lessons'].values() if x['cmodule'] == mid]
        out['modules'][mid] = {'name': mod['name'], 'lessons': len(ls), 'done': sum(x['mastered'] for x in ls),
                               'progress': round(sum(x['progress'] for x in ls) / len(ls), 3) if ls else 0.0,
                               'mastered': bool(ls) and all(x['mastered'] for x in ls)}
    day0 = day_start(now)
    for mid, mod in mods.items():
        try: req = [r for r in json.loads(mod['requires'] or '[]') if r in mods and r != mid]
        except (ValueError, TypeError): req = []
        m = out['modules'][mid]
        m['requires'] = req; m['locked'] = any(not out['modules'][r]['mastered'] for r in req)
        m['waiting_on'] = [fill(out['modules'][r]['name']) for r in req if not out['modules'][r]['mastered']]
        items = [i for lid, x in out['lessons'].items() if x['cmodule'] == mid for i in checks.get(lid, [])]
        ok = [i for i in items if i in latest and right_answer(latest[i]['rating'], latest[i]['hints'])]
        answered = [i for i in items if i in latest]
        state = ('none' if not items else 'waiting' if m['locked'] or not m['mastered'] else
                 ('passed' if len(ok) / len(items) >= PASS - 1e-9 else 'failed') if len(answered) == len(items) else 'ready')
        m['check'] = {'state': state, 'items': len(items), 'answered': len(answered), 'right': len(ok), 'now': 0, 'later': 0}
        if state in ('ready', 'failed'):
            serve = [i for i in items if i not in latest or (i not in ok and latest[i]['at'] < day0)]
            today = [i for i in serve if i not in held]
            out['checks'].update(today); m['check']['now'] = len(today); m['check']['later'] = len(serve) - len(today)
    for lid, x in out['lessons'].items():
        mod = out['modules'].get(x['cmodule'], {})
        waiting = [out['lessons'][r]['name'] for r in x['requires'] if not out['lessons'][r]['mastered']]
        x['locked'] = bool(mod.get('locked')) or bool(waiting)
        x['waiting_on'] = [fill(n) for n in waiting] or (list(mod.get('waiting_on') or []) if mod.get('locked') else [])
    return out

def locked_reason(db, deck):
    """Why a chosen track or course lesson has no card to study: on the shelf, or the lessons (or modules) it waits for,
    in a sentence; else None."""
    if deck and scope_of(db, deck) in settings(db)['shelved']:
        return 'This track is on the shelf. Take it off the shelf (Today, at the bottom) to study it again; its history is kept.'
    x = mastery(db)['lessons'].get(deck) if deck else None
    if not x or not x['locked']: return None
    return f"This lesson unlocks when you have answered {round(PASS * 100)}% of the cards right in: {', '.join(x['waiting_on'])}."

def next_card(db, deck=None, extra=False, session=False, out=None):
    """The next card to study: a Learn card sent back first, then reviews due, a module's check, then new cards.
    4.37: a track on the shelf is never served. Question first (unless the teach_first setting is on): a lesson's new
    practice cards come without their Learn cards in front, and the teaching arrives as feedback (answer()); a Learn card
    is served on its own only in a lesson that has nothing else, or when stuck detection sends it back. New practice cards
    stop at each track's daily limit (new_per_day). session=True (Study 10 minutes): reviews of the pinned tracks first,
    then other reviews, then new cards from the pinned tracks only (every track off the shelf while nothing is pinned).
    out (a dict) gets 'held': how many new cards the daily limit holds back for this choice."""
    scan_inbox(db)
    now = time.time()
    st, tm = settings(db), track_map(db)
    shelf, pins, first = set(st['shelved']), set(st['pinned']), st['teach_first']
    q, args = CARD_Q, []
    w, wargs = deck_where(db, deck)
    if w: q += " WHERE " + w; args += wargs
    hidden = buried(db, now)
    info = mastery(db, now, hidden)
    locked = {k for k, v in info['lessons'].items() if v['locked']}     # a locked lesson's new cards wait; its reviews go on
    # check items are for module checks, never practice; a buried sibling waits for tomorrow (and holds back nothing)
    every = [r for r in db.execute(q, args).fetchall() if track_of(tm, r['deck']) not in shelf]
    rows = [r for r in every if not r['is_check'] and not hidden(r)]
    # a Learn card sent back by stuck detection comes first, before any review
    back = [r for r in rows if r['refresh'] and r['kind'] in LEARN]
    if back: return card_payload(db, back[0]), None
    practice = {r['deck'] for r in every if r['kind'] not in LEARN and not r['is_check']}     # lessons with something to answer
    learn_alone = lambda r: r['kind'] in LEARN and (first or r['deck'] not in practice)
    # funnel: a lesson's cards unlock in FUNNEL order (teach_first: each practice card after its own Learn card)
    stage, seen = {}, {r['id'] for r in rows if r['reps']}
    for r in rows:
        if r['kind'] in FUNNEL and not r['reps'] and (r['kind'] not in LEARN or learn_alone(r)):
            stage[r['deck']] = min(stage.get(r['deck'], 99), FUNNEL[r['kind']])
    def ready(r):
        if r['reps'] or r['due'] is not None or r['deck'] in locked: return False
        if r['kind'] in LEARN and not learn_alone(r): return False
        if FUNNEL.get(r['kind'], 0) > stage.get(r['deck'], 99): return False
        return r['kind'] in LEARN or not first or not r['learn_of'] or r['learn_of'] in seen
    due = sorted((r for r in rows if r['due'] is not None and r['due'] <= now), key=lambda r: r['due'])
    order = lambda r: (r['mat'] or 0, r['deck'], r['ord'] or 0, r['id'])
    new = sorted((r for r in rows if ready(r)), key=order)
    made = new_today(db, tm, now)
    room = lambda r: r['kind'] in LEARN or new_limit(st, track_of(tm, r['deck'])) - made.get(track_of(tm, r['deck']), 0) > 0
    if out is not None: out['held'] = sum(1 for r in new if not room(r))
    new = [r for r in new if room(r)]
    if session and pins:
        mine = lambda r: track_of(tm, r['deck']) in pins
        due = [r for r in due if mine(r)] or due
        new = [r for r in new if mine(r)]
    # a module's check, once all its lessons are mastered: after the reviews due, before new cards (mastery leaves out an
    # item buried today, so the course map counts the same)
    checks = sorted((r for r in every if r['id'] in info['checks'] and r['kind'] not in LEARN), key=order)
    pool = due or checks or new
    if pool: c = interleave(pool)
    elif extra and [r for r in rows if r['due']]: c = min((r for r in rows if r['due']), key=lambda r: r['due'])   # practise ahead
    else: return None, min((r['due'] for r in rows if r['due']), default=None)
    return card_payload(db, c, st=st, tm=tm), None

def hint(db, card_id, rung):
    """One rung of the hint ladder (1-4). Rung 4 is the answer; the page then submits a blank answer with hints=4."""
    c = filled(db.execute("SELECT c.*, s.level FROM cards c LEFT JOIN sched s ON s.card_id=c.id WHERE c.id=?", (card_id,)).fetchone())
    if not c or c['kind'] in LEARN or rung not in (1, 2, 3, 4): return None
    level = card_level(c, c['level']) if c['kind'] == 'drill' else None
    rungs = hint_rungs(c, level)
    while rung < 4 and not rungs[rung - 1]: rung += 1       # a card without an authored nudge or near example skips that rung
    return {'rung': rung, 'name': RUNGS[rung - 1], 'text': rungs[rung - 1], 'next': next((k + 1 for k in range(rung, 4) if rungs[k]), None)}

def cap(sug, rungs):
    """The hint ladder caps the suggested rating: rung 2 -> at most Good, rung 3 -> at most Hard, rung 4 -> Again."""
    return min(sug, {0: 4, 1: 4, 2: 3, 3: 2}.get(rungs, 1))

def refresh(db, learn_id):
    if not learn_id: return False
    db.execute("INSERT INTO sched(card_id,reps,refresh) VALUES(?,1,1) ON CONFLICT(card_id) DO UPDATE SET refresh=1", (learn_id,))
    return True

def learn_answer(db, c, text, ms, skipped):
    """A Learn card is read, not graded: the typed reflections are stored, the spot-it check and self-explanation are checked."""
    data, kind = json.loads(c['data'] or '{}'), c['kind']
    cov, hits, missed, extra, feats = None, [], [], {}, {'words': len(WORDS.findall(text))}
    if kind == 'teach' and data.get('spot'):
        ok = text.strip() == str(data['spot']['line'])
        cov = 1.0 if ok else 0.0
        extra = {'line': data['spot']['line'], 'why': data['spot']['why'], 'spot_ok': ok}
    elif kind == 'level0':
        try: parts = json.loads(text) if text.strip().startswith('{') else {}
        except (ValueError, RecursionError): parts = {}
        if not isinstance(parts, dict): parts = {}
        explain = str(parts.get('explain') or '')
        if json.loads(c['points'] or '[]') and explain.strip():
            cov, hits, missed, f = grade(c, explain); feats.update(f)
        extra = {'reflections': [str(x)[:300] for x in as_list(parts.get('reflections'))][:8]}
    elif kind == 'preread':
        extra = {'answer': c['answer']}
    if skipped: feats['skipped'] = True
    with DB_LOCK:
        cur = db.execute("INSERT INTO attempts(card_id,at,answer,confidence,ms,coverage,hits,missed,features,suggested,grader,kind,level,skipped,reflections) "
                         "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (c['id'], time.time(), text[:2000], None, ms, cov, json.dumps(hits),
                         json.dumps(missed), json.dumps(feats), 0, 'learn', kind, None, 1 if skipped else 0, json.dumps(extra.get('reflections', []))))
        db.commit()
    n = len(hits) + len(missed)
    if skipped: coach = 'Skipped. If the practice card goes wrong, this one comes back.'
    elif 'spot_ok' in extra: coach = f"That's it: {extra['why']}" if extra['spot_ok'] else f"It's on line {extra['line']}: {extra['why']}"
    elif n: coach = f"All {n} key ideas." if cov >= 0.99 else f"{round(cov * n)} of {n} key ideas. Read the model answer, then say the missing part in your own words."
    else: coach = 'Read it once more, then move on: the practice card will show what stuck.'
    return {'attempt': cur.lastrowid, 'kind': kind, 'coverage': cov, 'hits': hits, 'missed': missed, 'reference': c['answer'],
            'suggested': 0, 'previews': {}, 'level_after': None, 'coach': coach, 'learn': True, **extra}

THINK_KINDS = ('define', 'explain', 'predict', 'write')      # cards a phone shows as "think it, reveal it, rate it" (4.37)

def answer(db, card_id, text, confidence, ms, hints=0, reflections=None, skipped=False, think=False):
    """Grade one answer. think=True (4.37, "think it, reveal it, rate it"): nothing was typed, so nothing is graded; the
    attempt is stored without a coverage (grader "self"), Mentor suggests no rating, and the person rates it."""
    c = filled(db.execute("SELECT c.*, s.level FROM cards c LEFT JOIN sched s ON s.card_id=c.id WHERE c.id=?", (card_id,)).fetchone())
    if not c: return None
    if c['kind'] in LEARN: return learn_answer(db, c, text, ms, skipped)
    if think and c['kind'] in THINK_KINDS and not c['is_check']: return think_answer(db, c, confidence, ms, hints, reflections)
    data = json.loads(c['data'] or '{}')
    level, per, extra = None, None, {}
    hints = max(0, min(4, int(hints or 0)))
    if hints == 4: text = ''                       # the answer was shown: this attempt counts as a blank one
    if c['kind'] == 'drill':
        level = card_level(c, c['level'])
        cov, feats, per = grade_drill(c, level, text)
        hits = [f"Blank {p['n']}" for p in per if p['ok']]; missed = [f"Blank {p['n']}" for p in per if not p['ok']]
        grader = 'drill-A'
        extra = {'level': level, 'canonical': c['answer'], 'note': data.get('note', ''), 'blanks': per,
                 'problem': feats.get('problem'), 'same_structure': feats.get('same_structure'),
                 'look': (data.get('look') or {}).get(str(level)) or []}
        if level == 3: extra['yours'] = fill_body(data['fades']['3']['code'], text)
    elif c['kind'] == 'term':
        cov = grade_term(c, text)
        hits, missed = ([c['answer']], []) if cov >= 0.99 else ([], [c['answer']])
        feats, grader = {'coverage': cov, 'words': len(text.split())}, 'term-A'
        extra = {k: data.get(k, '') for k in ('definition', 'anchor', 'contrast', 'category')}
    elif c['kind'] in ('trace', 'parsons'):     # 4.32: one row per step or line, as a drill has one per blank
        cov, feats, per = (grade_trace if c['kind'] == 'trace' else grade_parsons)(c, text)
        what = (lambda p: f"After line {p['line']}") if c['kind'] == 'trace' else (lambda p: f"Line {p['n']}")
        hits, missed = [what(p) for p in per if p['ok']], [what(p) for p in per if not p['ok']]
        grader = c['kind'] + '-A'
        extra = {'breadcrumb': data.get('breadcrumb', ''), 'rows': per}
        if c['kind'] == 'trace': extra['code'] = data.get('code', '')
    else:
        cov, hits, missed, feats = grade(c, text, code_tokens_words if c['kind'] in CODE_KINDS else tokens)
        grader = 'rubric-A-auto' if feats.get('auto_points') else 'rubric-A'
        extra = {'breadcrumb': data.get('breadcrumb', ''), 'rough': bool(feats.get('auto_points'))}
        if c['kind'] == 'predict': extra['code'] = data.get('code', '')
        if c['kind'] == 'write' and data.get('lang', 'python') == 'python' and text.strip():
            # parsed, never run: Python's own syntax error is shown with the key ideas (it does not change the grade)
            extra['problem'] = syntax_problem(textwrap.dedent(text)); feats['syntax_ok'] = extra['problem'] is None
    extra['move'] = data.get('move') or MOVE.get(c['kind'], MOVE['define'])
    # slip or mistake (Norman): a blank that was right before, or the same card right at another time, is a slip
    prev = db.execute("SELECT * FROM attempts WHERE card_id=? AND kind=? ORDER BY id DESC LIMIT 1", (card_id, c['kind'])).fetchone()
    extra['slip'] = bool(prev and cov < 0.99 and (prev['coverage'] or 0) >= 0.99)
    # stuck: wrong twice in a row within a session -> the lesson's Learn card comes back before the next try
    stuck = None
    if cov < 0.5 and prev and prev['coverage'] is not None and prev['coverage'] < 0.5 and time.time() - prev['at'] < STUCK_WINDOW:
        stuck = 'repeat'
    elif cov < 0.5 and c['learn_of']:
        la = db.execute("SELECT skipped FROM attempts WHERE card_id=? ORDER BY id DESC LIMIT 1", (c['learn_of'],)).fetchone()
        if la and la['skipped']: stuck = 'skipped'     # "I know this, test me" was a miscalibration
    feats.update({'confidence': confidence, 'ms': ms, 'kind': c['kind'], 'level': level, 'hints': hints, 'slip': extra['slip']})
    sug = cap(suggest_rating(cov, confidence), hints)
    with DB_LOCK:
        cur = db.execute("INSERT INTO attempts(card_id,at,answer,confidence,ms,coverage,hits,missed,features,suggested,grader,kind,level,hints,reflections,stuck) "
                         "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (card_id, time.time(), text, confidence, ms, cov,
                         json.dumps(hits), json.dumps(missed), json.dumps(feats), sug, grader, c['kind'], level, hints,
                         json.dumps([str(x)[:300] for x in as_list(reflections)][:4]), stuck))
        if stuck: refresh(db, c['learn_of'])
        db.commit()
    att = db.execute("SELECT * FROM attempts WHERE id=?", (cur.lastrowid,)).fetchone()
    srow = db.execute("SELECT * FROM sched WHERE card_id=?", (card_id,)).fetchone()
    now = time.time()
    if c['is_check']:       # a module check item is answered once per check, never scheduled: nothing to preview
        previews, level_after = {}, None
    else:
        plans = {g: plan(db, c, srow, att, g, now) for g in (1, 2, 3, 4)}
        previews = {g: round((p[2] - now) / DAY, 6) for g, p in plans.items()}      # days until it returns (to the second: steps are minutes)
        level_after = {g: p[7] for g, p in plans.items()} if c['kind'] == 'drill' else None
    n = len(hits) + len(missed)
    # question first (4.37): the card's teaching comes with the result, and counts as read the first time it does
    teach, teach_new = teaching(db, c, now)
    extra.update({'teach': teach, 'teach_new': teach_new})
    return {'attempt': cur.lastrowid, 'kind': c['kind'], 'coverage': round(cov, 2), 'hits': hits, 'missed': missed,
            'previews': previews, 'level_after': level_after, 'reference': c['answer'], 'suggested': sug, 'hints': hints,
            'stuck': stuck, 'check': bool(c['is_check']), 'coach': coach_line(c['kind'], cov, confidence, n, extra), **extra}

def teaching(db, c, now):
    """The card's Learn card as feedback (question first, 4.37): its payload, and whether this is the first time (then it
    counts as read). (None, False) for a card without one."""
    if not c['learn_of'] or c['is_check']: return None, False
    lr = db.execute(CARD_Q + " WHERE c.id=?", (c['learn_of'],)).fetchone()
    if not lr or lr['kind'] not in LEARN or lr['is_check']: return None, False
    if not lr['reps']:
        with DB_LOCK:
            db.execute("INSERT INTO sched(card_id,reps,refresh,last) VALUES(?,1,0,?) ON CONFLICT(card_id) DO UPDATE SET reps=1, last=excluded.last",
                       (lr['id'], now)); db.commit()
    return card_payload(db, lr, read_only=True), not lr['reps']

def think_answer(db, c, confidence, ms, hints, reflections):
    data, now = json.loads(c['data'] or '{}'), time.time()
    hints = max(0, min(3, int(hints or 0)))
    feats = {'think': True, 'confidence': confidence, 'ms': ms, 'kind': c['kind'], 'hints': hints}
    with DB_LOCK:
        cur = db.execute("INSERT INTO attempts(card_id,at,answer,confidence,ms,coverage,hits,missed,features,suggested,grader,kind,level,hints,reflections) "
                         "VALUES(?,?,?,?,?,NULL,'[]','[]',?,0,'self',?,NULL,?,?)", (c['id'], now, '', confidence, ms, json.dumps(feats), c['kind'],
                         hints, json.dumps([str(x)[:300] for x in as_list(reflections)][:4])))
        db.commit()
    att = db.execute("SELECT * FROM attempts WHERE id=?", (cur.lastrowid,)).fetchone()
    srow = db.execute("SELECT * FROM sched WHERE card_id=?", (c['id'],)).fetchone()
    previews = {g: round((plan(db, c, srow, att, g, now)[2] - now) / DAY, 6) for g in (1, 2, 3, 4)}
    teach, teach_new = teaching(db, c, now)
    return {'attempt': cur.lastrowid, 'kind': c['kind'], 'coverage': None, 'hits': [], 'missed': [], 'previews': previews,
            'level_after': None, 'reference': c['answer'], 'suggested': 0, 'hints': hints, 'stuck': None, 'check': False, 'think': True,
            'coach': 'Compare it with what you thought, then say how well you knew it.', 'breadcrumb': data.get('breadcrumb', ''),
            'code': data.get('code', '') if c['kind'] == 'predict' else '', 'slip': False,
            'move': data.get('move') or MOVE.get(c['kind'], MOVE['define']), 'teach': teach, 'teach_new': teach_new}

def coach_line(kind, cov, conf, n, extra):
    """At most two sentences: what the result was, then the expert's first move and one place to look (Hattie &
    Timperley 2007: task and process feedback, never about the person). A right answer gets one sentence."""
    k, move = round(cov * n), extra.get('move', '')
    look = extra.get('look') or []
    if conf and conf >= 3 and cov < 0.5:
        return f"You felt sure but got {k} of {n}. {move}"
    if conf and conf <= 2 and cov >= 0.99:
        return "You knew more than you thought: it's all there. Trust that answer next time."
    if extra.get('slip') and cov < 0.99:
        return f"Right idea, wrong detail: you had this one before. {move}"
    if kind == 'drill':
        if extra.get('level') == 3:
            if extra.get('problem'): return f"Python can't read your version ({extra['problem']}). Fix that line in your head, then compare the two."
            if extra.get('same_structure'): return "Same structure as the model answer. You wrote it from memory."
            return f"It runs differently from the model answer. {move}"
        # the verdict above already says how many blanks were right: the coach line says what to do with that
        if cov >= 0.99: return "You filled every blank from memory. Read the full code once more as a whole."
        where = f" Look at {look[0]}." if look else ''
        return f"{move}{where}"
    if kind == 'term':
        if cov >= 0.99: return "Right term. Read where it lives in your code, so you'll spot it next time."
        if cov > 0: return f"Close, not the exact term. {move}"
        return f"{move} The term is below: find it in your code first, then in the look-alike."
    if kind == 'trace':
        if cov >= 0.99: return "Every value right. You can run this code in your head."
        return move                      # the verdict above already says how many: the coach says where to look
    if kind == 'parsons':
        if cov >= 0.99: return "Every line in its place. Read the whole function once more, top to bottom."
        return move
    if kind == 'write' and extra.get('problem'):
        return f"Python can't read your version yet ({extra['problem']}). The key ideas below are graded anyway."
    rough =' (this card checks content words only, so judge for yourself)' if extra.get('rough') else ''
    if cov >= 0.99: return f"All {n} key ideas."
    if cov == 0: return f"None of the key ideas yet{rough}. {move}"
    return f"{k} of {n} key ideas{rough}. {move}"

def review_kind(srow, ratings, now):
    """What this rating is, for the review log. ratings: the card's earlier ratings, newest first. A card on its learning
    steps is learning (or relearning, after a lapse); before steps (4.29), learning lasted until the card was first passed
    (Hard or better). Rating a review card before it is due is practising ahead (manual)."""
    if srow and srow['reps'] and srow['step'] is not None: return 'relearn' if srow['relearn'] else 'learn'
    if not srow or not any(r >= 2 for r in ratings): return 'learn'
    if srow['due'] is not None and srow['due'] > now: return 'manual'
    return 'relearn' if ratings[0] == 1 else 'review'

def rate(db, attempt_id, rating, grade_wrong):
    a = db.execute("SELECT * FROM attempts WHERE id=?", (attempt_id,)).fetchone()
    if not a: return None
    c = db.execute("SELECT * FROM cards WHERE id=?", (a['card_id'],)).fetchone()
    now = time.time()
    if c and c['kind'] in LEARN:                 # a Learn card is seen, never scheduled; rating 0 (or any) marks it read
        with DB_LOCK:
            db.execute("INSERT INTO sched(card_id,reps,refresh,last) VALUES(?,1,0,?) ON CONFLICT(card_id) DO UPDATE SET reps=1,refresh=0,last=excluded.last",
                       (c['id'], now))
            db.execute("UPDATE attempts SET rating=0 WHERE id=?", (attempt_id,))
            db.commit()
        return {'due': None, 'days': None, 'level': None, 'level_change': 0, 'learn': True}
    if rating not in (1, 2, 3, 4): return None
    if c and c['is_check']:          # a module check item: counted for the check, never scheduled as practice (spec section 8)
        with DB_LOCK:
            srow = db.execute("SELECT * FROM sched WHERE card_id=?", (a['card_id'],)).fetchone()
            prev = {'sched': {k: srow[k] for k in SCHED_COLS} if srow else None}
            db.execute("INSERT INTO sched(card_id,reps,lapses,last,due,step,relearn) VALUES(?,1,0,?,NULL,NULL,0) ON CONFLICT(card_id) DO UPDATE SET "
                       "reps=COALESCE(sched.reps, 0)+1, last=excluded.last, due=NULL, step=NULL", (a['card_id'], now))
            db.execute("UPDATE attempts SET rating=?, grade_wrong=?, review='check', ivl_before=NULL, ivl_after=NULL, took=?, prev_json=?, "
                       "undone=0 WHERE id=?", (rating, 1 if grade_wrong else 0, min(a['ms'] or 0, 60_000), json.dumps(prev), attempt_id))
            db.commit()
        return {'due': None, 'days': None, 'step': None, 'level': None, 'level_change': 0, 'held': False, 'back': False, 'check': True,
                'right': right_answer(rating, a['hints'])}
    held, back = False, False
    with DB_LOCK:
        srow = db.execute("SELECT * FROM sched WHERE card_id=?", (a['card_id'],)).fetchone()
        prev = {'sched': {k: srow[k] for k in SCHED_COLS} if srow else None}     # for undo: the schedule as it was
        if c is None: s, d, due, reps, lapses, step, relearn, level, up = (*schedule(srow, rating, now), 1, False)
        else: s, d, due, reps, lapses, step, relearn, level, up = plan(db, c, srow, a, rating, now)
        if c and c['learn_of']:
            older = db.execute("SELECT hints, rating, at FROM attempts WHERE card_id=? AND id<? AND rating IS NOT NULL AND COALESCE(undone, 0)=0 "
                               "ORDER BY id DESC LIMIT 3", (c['id'], attempt_id)).fetchall()
            # the answer was shown twice, or "Needs work" twice in a week: hold the card a day and send its Learn card back
            if (a['hints'] == 4 and any(o['hints'] == 4 for o in older)) or (rating == 1 and any(o['rating'] == 1 and now - o['at'] < LAPSE_WINDOW for o in older)):
                held, due = True, max(due, now + DAY)
                lrow = db.execute("SELECT * FROM sched WHERE card_id=?", (c['learn_of'],)).fetchone()
                prev['learn'] = {'id': c['learn_of'], 'refresh': lrow['refresh'] if lrow else 0}
                back = refresh(db, c['learn_of'])
        db.execute("INSERT INTO sched(card_id,stability,difficulty,due,last,reps,lapses,level,step,relearn) VALUES(?,?,?,?,?,?,?,?,?,?) "
                   "ON CONFLICT(card_id) DO UPDATE SET stability=excluded.stability,difficulty=excluded.difficulty,"
                   "due=excluded.due,last=excluded.last,reps=excluded.reps,lapses=excluded.lapses,level=excluded.level,"
                   "step=excluded.step,relearn=excluded.relearn",
                   (a['card_id'], s, d, due, now, reps, lapses, level, step, relearn))
        ratings = [r[0] for r in db.execute("SELECT rating FROM attempts WHERE card_id=? AND id<? AND rating>0 AND COALESCE(undone, 0)=0 ORDER BY id DESC",
                                            (a['card_id'], attempt_id))]
        before = (srow['due'] - srow['last']) / DAY if srow and srow['due'] is not None and srow['last'] else None
        db.execute("UPDATE attempts SET rating=?, grade_wrong=?, stuck=COALESCE(stuck, ?), review=?, ivl_before=?, ivl_after=?, took=?, "
                   "prev_json=?, undone=0 WHERE id=?",
                   (rating, 1 if grade_wrong else 0, 'held' if held else None, review_kind(srow, ratings, now), before,
                    (due - now) / DAY, min(a['ms'] or 0, 60_000), json.dumps(prev), attempt_id))
        db.commit()
    old = a['level']
    return {'due': due, 'days': round((due - now) / DAY, 6), 'step': step, 'level': level if c and c['kind'] == 'drill' else None,
            'level_change': (level - old) if old and c and c['kind'] == 'drill' else 0, 'held': held, 'back': back}

SCHED_COLS = ('stability', 'difficulty', 'due', 'last', 'reps', 'lapses', 'level', 'refresh', 'step', 'relearn')
# a schedule row that was not there before a rating comes back as "never studied" (the row stays; nothing is deleted)
NEVER = {'stability': None, 'difficulty': None, 'due': None, 'last': None, 'reps': 0, 'lapses': 0, 'level': None, 'refresh': 0,
         'step': None, 'relearn': 0}

def undo(db, attempt_id):
    """Ctrl+Z: take back the latest rating. Only that one (the page sends its own session's last rating; an older one, one
    already undone, or one from before 4.29 is refused), so a stale page can't rewind history. The card's schedule (and a
    Learn card the rating sent back stops being sent back) returns to exactly what it was; the log row stays, marked undone=1.
    Returns {'undone': False} when there is nothing to undo, else the card to answer again."""
    with DB_LOCK:
        a = db.execute("SELECT * FROM attempts WHERE id=?", (attempt_id,)).fetchone()
        last = db.execute("SELECT id FROM attempts WHERE rating>0 AND COALESCE(undone, 0)=0 ORDER BY id DESC LIMIT 1").fetchone()
        if not a or not a['prev_json'] or a['undone'] or not a['rating'] or not last or last['id'] != a['id']: return {'undone': False}
        if db.execute("SELECT 1 FROM attempts WHERE id>? AND undone=1", (attempt_id,)).fetchone(): return {'undone': False}   # one step back only
        prev = json.loads(a['prev_json'])
        vals = prev.get('sched') or NEVER
        db.execute(f"UPDATE sched SET {', '.join(k + '=?' for k in SCHED_COLS)} WHERE card_id=?", (*(vals.get(k) for k in SCHED_COLS), a['card_id']))
        if prev.get('learn'):          # only its "sent back" flag: reading it since then still counts
            db.execute("UPDATE sched SET refresh=? WHERE card_id=?", (prev['learn']['refresh'] or 0, prev['learn']['id']))
        db.execute("UPDATE attempts SET undone=1 WHERE id=?", (attempt_id,))
        db.commit()
    c = db.execute(CARD_Q + " WHERE c.id=?", (a['card_id'],)).fetchone()
    return {'undone': True, 'rating': a['rating'], 'card': card_payload(db, c) if c and c['kind'] not in LEARN else None}

def modules(db, info=None):
    """Lessons for the Lessons view: the CTA summary, what's in them, how far along you are, and the Learn cards to read again.
    A course lesson also has its mastery (4.32): progress (share answered right), mastered, locked and what it waits on."""
    info = info or mastery(db)
    out = []
    counts = db.execute("SELECT c.deck, c.kind, COUNT(*) n, SUM(CASE WHEN s.reps>0 THEN 1 ELSE 0 END) seen, "
                        "SUM(CASE WHEN c.kind='drill' AND s.level=3 THEN 1 ELSE 0 END) top "
                        "FROM cards c LEFT JOIN sched s ON s.card_id=c.id WHERE COALESCE(c.is_check, 0)=0 GROUP BY c.deck, c.kind").fetchall()
    by = {}
    for r in counts: by.setdefault(r['deck'], {})[r['kind']] = {'n': r['n'], 'seen': r['seen'] or 0, 'top': r['top'] or 0}
    learn = {}
    for r in db.execute("SELECT c.id, c.deck, c.kind, c.prompt, c.answer, c.data, s.reps FROM cards c LEFT JOIN sched s ON s.card_id=c.id "
                        "WHERE c.kind IN (?,?,?,?) AND COALESCE(c.is_check, 0)=0 ORDER BY c.ord, c.id", LEARN).fetchall():
        d = json.loads(r['data'] or '{}')
        title = {'orientation': 'Orientation', 'teach': f"Teach: {r['prompt']}", 'level0': f"Worked example: {(d.get('breadcrumb') or '').split('->')[-1].strip() or r['prompt'][:40]}",
                 'preread': f"Before {(d.get('type') or 'the explain card').lower().replace('pre-mortem', 'the bug hunt')}: {(d.get('breadcrumb') or '').split('->')[-1].strip()}"}[r['kind']]
        learn.setdefault(r['deck'], []).append({'id': r['id'], 'kind': r['kind'], 'title': fill(title.rstrip(': ')), 'seen': bool(r['reps'])})
    for m in db.execute("SELECT * FROM modules ORDER BY built_in, at DESC, ord").fetchall():   # a course's lessons share one `at`
        cards = by.get(m['id'], {})
        out.append({'id': m['id'], 'name': fill(m['name']), 'project': fill(m['project']), 'built_in': bool(m['built_in']), 'at': m['at'],
                    'course': m['course'], 'cmodule': m['cmodule'],
                    'summary': json.loads(fill(m['summary'], as_json=True) or '{}'), 'concepts': json.loads(fill(m['concepts'], as_json=True) or '[]'),
                    'files': json.loads(fill(m['files'], as_json=True) or '[]'), 'cards': cards, 'learn': learn.get(m['id'], []),
                    'to_learn': sum(c['n'] - c['seen'] for k, c in cards.items() if k in LEARN)})
        x = info['lessons'].get(m['id'])
        if x: out[-1].update({k: x[k] for k in ('progress', 'mastered', 'locked', 'waiting_on', 'requires')})
    return out

def courses(db, info=None):
    """Courses with their modules in order and each module's lesson ids, Loose lessons last; text filled in. A course module
    also has its mastery (4.32): lessons mastered, progress, locked and what it waits on, and its check's state."""
    info = info or mastery(db)
    lessons = {}
    for r in db.execute("SELECT id, cmodule FROM modules ORDER BY ord, at DESC, id"): lessons.setdefault(r['cmodule'], []).append(r['id'])
    los = {r[0]: r[1] for r in db.execute("SELECT course, COUNT(*) FROM los GROUP BY course")}
    out = []
    for c in db.execute("SELECT * FROM courses ORDER BY id=?, at DESC, id", (LOOSE,)).fetchall():
        mods = [{'id': x['id'], 'name': fill(x['name']), 'requires': json.loads(x['requires'] or '[]'), 'lessons': lessons.get(x['id'], []),
                 **{k: v for k, v in info['modules'].get(x['id'], {}).items() if k in ('done', 'progress', 'mastered', 'locked', 'waiting_on', 'check')}}
                for x in db.execute("SELECT * FROM cmodules WHERE course=? ORDER BY ord, id", (c['id'],))]
        out.append({'id': c['id'], 'name': fill(c['name']), 'summary': fill(c['summary']), 'loose': c['id'] == LOOSE,
                    'modules': mods, 'los': los.get(c['id'], 0)})
    return out

def stats(db, deck=None):
    scan_inbox(db)
    now = time.time(); day0 = now - (now % DAY)
    cw, args = deck_where(db, deck)
    w = "WHERE COALESCE(c.is_check, 0)=0" + (" AND " + cw if cw else "")     # check items never wait to be studied
    hidden = buried(db, now)       # a buried sibling is neither due nor new until tomorrow
    info = mastery(db, now, hidden)
    locked = {k for k, v in info['lessons'].items() if v['locked']}
    # a locked lesson's cards don't wait to be studied yet (only its reviews, if it was studied before it was locked)
    st, tm = settings(db), track_map(db)
    shelf = set(st['shelved'])          # a track on the shelf is in no count (4.37); its history stays
    cards = [c for c in db.execute(f"SELECT c.id, c.deck, c.kind, c.note, s.due, s.reps, s.step FROM cards c LEFT JOIN sched s ON s.card_id=c.id {w}", args)
             if not hidden(c) and not (c['deck'] in locked and c['due'] is None) and track_of(tm, c['deck']) not in shelf]
    # question first: a Learn card waits to be read only in a lesson that has nothing to answer (the rest come as feedback)
    answerable = {c['deck'] for c in db.execute("SELECT DISTINCT deck FROM cards WHERE kind NOT IN (?,?,?,?) AND COALESCE(is_check, 0)=0", LEARN)}
    to_read = lambda c: c['kind'] in LEARN and not c['reps'] and (st['teach_first'] or c['deck'] not in answerable)
    cw2 = "WHERE c.is_check=1" + (" AND " + cw if cw else "")
    checks = sum(1 for c in db.execute(f"SELECT c.id, c.deck, c.kind FROM cards c {cw2}", args)    # buried ones are left out by mastery
                 if c['id'] in info['checks'] and c['kind'] not in LEARN and track_of(tm, c['deck']) not in shelf)
    ids = group_ids(db, deck)
    pats = [i + ':%' for i in ids] if ids is not None else ([deck + ':%'] if deck else [])
    aw = ("WHERE " + " OR ".join("a.card_id LIKE ?" for _ in pats)) if pats else ("WHERE 0" if ids is not None else "")
    att = db.execute(f"SELECT a.* FROM attempts a {aw} ORDER BY a.id DESC LIMIT 500", pats).fetchall()
    rated = [a for a in att if a['rating'] and not a['undone']]
    graded = [a for a in rated if a['coverage'] is not None]      # a self-rated ("think it") attempt has no coverage
    conf = [a for a in graded if a['confidence']]
    # calibration: confidence (1-4 -> 0..1) minus coverage; positive = overconfident
    cal = round(sum((a['confidence'] - 1) / 3 - a['coverage'] for a in conf) / len(conf), 2) if conf else None
    imports = [dict(r) for r in db.execute("SELECT path, ok, msg, module, at FROM imports ORDER BY at DESC LIMIT 8")]
    practice = [c for c in cards if c['kind'] not in LEARN]
    week = [a for a in att if a['at'] >= now - 7 * DAY and a['kind'] not in LEARN]
    return {'cards': len(practice), 'new': sum(1 for c in practice if c['due'] is None),
            'learn': sum(1 for c in cards if to_read(c)),
            'due': sum(1 for c in practice if c['due'] is not None and c['due'] <= now),
            # cards on their learning steps that come back later today (once its minutes are up a card counts as due instead)
            'steps': sum(1 for c in practice if c['step'] is not None and c['due'] is not None and now < c['due'] < day_start(now) + DAY),
            'learned': sum(1 for c in practice if (c['reps'] or 0) > 0),
            'today': sum(1 for a in att if a['at'] >= day0 and a['kind'] not in LEARN),
            'avg_coverage': round(sum(a['coverage'] for a in graded) / len(graded), 2) if graded else None,
            'calibration': cal, 'labels': len(rated),
            'grade_disputes': sum(1 for a in rated if a['grade_wrong']),
            'hints_per_card': round(sum(a['hints'] or 0 for a in week) / len(week), 2) if week else None,
            'sent_back': sum(1 for a in att if a['stuck'] in ('held', 'repeat', 'skipped') and a['at'] >= day0),
            'checks': checks, 'pass': PASS,          # module check questions to answer now; the mastery threshold (4.32)
            'modules': modules(db, info), 'courses': courses(db, info), 'imports': imports, 'settings': settings(db),
            'inbox': INBOX.replace(os.path.expanduser('~'), '~', 1) if getattr(db, 'own_inbox', True) else ''}

# ---------- Today (4.37): the first view, and Elaia's Today card ----------
SESSION_MIN = 10            # "Study 10 minutes"
CARD_MS_CAP = 120_000       # a card counts at most 2 minutes toward the week's minutes (a page left open is not study)

def today(db, names=None):
    """Everything the Today view needs in one answer: every track with its counts and goal (pinned first), the totals
    the one button studies, the week's minutes (oldest day first, today last) and what tomorrow brings."""
    scan_inbox(db)
    now = time.time(); day0 = day_start(now); day1 = day_start(day0 + 1.5 * DAY); day2 = day_start(day1 + 1.5 * DAY)
    st, tm = settings(db), track_map(db)
    shelf, pins = set(st['shelved']), [p for p in st['pinned']]
    hidden = buried(db, now)
    info = mastery(db, now, hidden)
    locked = {k for k, v in info['lessons'].items() if v['locked']}
    z = lambda: {'cards': 0, 'learned': 0, 'due': 0, 'new': 0, 'later': 0, 'tomorrow': 0}
    per = {}
    for c in db.execute("SELECT c.id, c.deck, c.kind, c.note, s.due, s.reps, s.step FROM cards c LEFT JOIN sched s ON s.card_id=c.id "
                        "WHERE COALESCE(c.is_check, 0)=0 AND c.kind NOT IN (?,?,?,?)", LEARN):
        t = per.setdefault(track_of(tm, c['deck']), z())
        t['cards'] += 1; t['learned'] += 1 if (c['reps'] or 0) > 0 else 0
        if hidden(c): continue
        if c['due'] is not None and c['due'] <= now: t['due'] += 1
        if c['due'] is None and c['deck'] not in locked: t['new'] += 1
        if c['due'] is not None and now < c['due'] < day1: t['later'] += 1          # back later today (learning steps)
        if c['due'] is not None and day1 <= c['due'] < day2: t['tomorrow'] += 1
    last = {}
    for r in db.execute("SELECT c.deck, MAX(a.at) AS at FROM attempts a JOIN cards c ON c.id=a.card_id GROUP BY c.deck"):
        t = track_of(tm, r['deck']); last[t] = max(last.get(t, 0), r['at'] or 0)
    made = new_today(db, tm, now)
    rows = []
    for tr in tracks(db, names):
        t, tid = per.get(tr['id'], z()), tr['id']
        lim = new_limit(st, tid)
        rows.append({'id': tid, 'name': tr['name'], 'lessons': len(tr['lessons']), 'goal': st['goal'].get(tid, ''),
                     'cards': t['cards'], 'learned': t['learned'], 'progress': round(t['learned'] / t['cards'], 3) if t['cards'] else 0.0,
                     'due': t['due'], 'new': t['new'], 'new_per_day': lim, 'new_today': made.get(tid, 0),
                     'new_left': min(t['new'], max(0, lim - made.get(tid, 0))), 'later': t['later'], 'tomorrow': t['tomorrow'], 'last': last.get(tid),
                     'pinned': tid in pins, 'shelved': tid in shelf, 'ask_confidence': tid in st['ask_confidence']})
    rows.sort(key=lambda r: (not r['pinned'], pins.index(r['id']) if r['pinned'] else 0, r['shelved'], r['name'].lower()))
    live = [r for r in rows if not r['shelved']]
    scope = [r for r in live if r['pinned']] or live           # nothing pinned yet: every track off the shelf
    week = []
    for i in range(6, -1, -1):
        d0 = day_start(day0 - i * DAY + 3600); d1 = day_start(d0 + 1.5 * DAY)
        ms = db.execute("SELECT COALESCE(SUM(MIN(COALESCE(ms, 0), ?)), 0) FROM attempts WHERE at>=? AND at<?", (CARD_MS_CAP, d0, d1)).fetchone()[0]
        week.append({'day': time.strftime('%Y-%m-%d', time.localtime(d0)), 'minutes': round(ms / 60000)})
    nxt = db.execute("SELECT c.deck, s.due FROM sched s JOIN cards c ON c.id=s.card_id WHERE s.due>? ORDER BY s.due", (now,)).fetchall()
    nxt = next((r['due'] for r in nxt if track_of(tm, r['deck']) not in shelf), None)
    return {'tracks': rows, 'pinned': pins, 'pin_max': PIN_MAX, 'shelf': len([r for r in rows if r['shelved']]),
            'due': sum(r['due'] for r in live), 'new_left': sum(r['new_left'] for r in scope), 'scope': [r['id'] for r in scope],
            'later': sum(r['later'] for r in live), 'tomorrow': sum(r['tomorrow'] for r in live), 'next_due': nxt, 'week': week, 'minutes': SESSION_MIN,
            'confidence_every': CONF_EVERY, 'teach_first': st['teach_first']}

def track_preview(db, tid, names=None):
    """Preview on the shelf: a track's size, its history, and its first few questions (never an answer). Changes nothing."""
    tr = next((t for t in tracks(db, names) if t['id'] == tid), None)
    if not tr: return None
    st, tm = settings(db), track_map(db)
    ds = set(tr['lessons'])
    kinds, learned, qs = {}, 0, []
    for c in db.execute(CARD_Q + " WHERE COALESCE(c.is_check, 0)=0 ORDER BY m.at, c.deck, c.ord, c.id"):
        if c['deck'] not in ds: continue
        kinds[c['kind']] = kinds.get(c['kind'], 0) + 1
        if c['kind'] in LEARN: continue
        learned += 1 if c['reps'] else 0
        if len(qs) < 3: qs.append(' '.join(BLANK.sub('___', fill(c['prompt'] or '')).split())[:200])
    att = db.execute("SELECT COUNT(*), MAX(a.at) FROM attempts a JOIN cards c ON c.id=a.card_id WHERE c.deck IN (%s) AND a.rating>0 "
                     "AND COALESCE(a.undone, 0)=0" % ','.join('?' * len(ds)), list(ds)).fetchone()
    return {'id': tid, 'name': tr['name'], 'lessons': len(ds), 'goal': st['goal'].get(tid, ''),
            'cards': sum(n for k, n in kinds.items() if k not in LEARN), 'reading': sum(n for k, n in kinds.items() if k in LEARN),
            'learned': learned, 'answers': att[0], 'last': att[1], 'questions': qs,
            'pinned': tid in st['pinned'], 'shelved': tid in st['shelved']}

# ---------- the local AI's part (docs/mentor-ai.md): stored with the attempt, shown labelled, not used for the rating ----------
AI_KINDS = ('explain', 'define', 'write')     # written answers (4.32: and written code); drills, terms, traces and Parsons are graded exactly

def card_prompt(db, card_id):
    c = db.execute("SELECT prompt FROM cards WHERE id=?", (card_id,)).fetchone()
    return fill(c['prompt']) if c else ''

def set_ai(db, attempt_id, d):
    with DB_LOCK:
        db.execute("UPDATE attempts SET ai=? WHERE id=?", (json.dumps(d), attempt_id)); db.commit()

def get_ai(db, attempt_id):
    r = db.execute("SELECT ai FROM attempts WHERE id=?", (attempt_id,)).fetchone()
    return json.loads(r['ai']) if r and r['ai'] else None

def export(db, out):
    """Every rated attempt as one JSON line: the training data for a grader that learns from you (stage Bv2).
    Placeholders stay as {{...}}; answers are yours, so the file stays on your machine."""
    n = 0
    for a in db.execute("SELECT a.*, c.prompt, c.answer AS reference FROM attempts a LEFT JOIN cards c ON c.id=a.card_id WHERE a.rating IS NOT NULL ORDER BY a.id"):
        d = {k: a[k] for k in ('id', 'card_id', 'kind', 'at', 'prompt', 'reference', 'answer', 'confidence', 'ms', 'coverage', 'suggested', 'rating', 'grade_wrong', 'hints', 'grader', 'undone')}
        d['features'] = json.loads(a['features'] or '{}'); d['ai'] = json.loads(a['ai']) if a['ai'] else None
        out.write(json.dumps(d) + '\n'); n += 1
    return n

if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2 or sys.argv[1] != 'export':
        sys.exit('usage: python mentor.py export [path/to/mentor.db] > attempts.jsonl')
    path = sys.argv[2] if len(sys.argv) > 2 else os.path.expanduser(os.environ.get('ARGUS_MENTOR_DB', '~/.local/share/argus-ui/mentor.db'))
    n = export(connect(path), sys.stdout)
    print(f'{n} rated attempts exported', file=sys.stderr)
