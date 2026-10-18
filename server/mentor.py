"""Mentor - the study coach behind the Practice tab. Python standard library only.

Grading roadmap (each stage keeps the data the next one learns from):
  A    rubric grader (this file): each card lists key ideas + accepted wordings; answers are checked for them.
  B    local similarity model: adds a semantic score as one more feature.
  Bv2  learned grader: once enough of your own ratings exist, a small model trained on YOUR attempts
       (features below + your final rating + "grade was wrong" flags) predicts the grade and coaching hints.
Every attempt is stored with its features and your labels in the `attempts` table, from day one.

Scheduling: FSRS-4.5 (Free Spaced Repetition Scheduler) with its published default weights.
"""
import json, math, os, re, sqlite3, threading, time, glob
from difflib import SequenceMatcher

DB_LOCK = threading.Lock()

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
"""

def connect(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    db = sqlite3.connect(path, check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    return db

def load_decks(db, folder):
    """Upsert every deck JSON file in folder. Editing a deck file and restarting updates the cards; history stays."""
    n = 0
    for f in sorted(glob.glob(os.path.join(folder, '*.json'))):
        try:
            with open(f, encoding='utf-8') as fh: deck = json.load(fh)
        except Exception:
            continue
        for c in deck.get('cards', []):
            cid = f"{deck['id']}:{c['id']}"
            db.execute("INSERT INTO cards(id,deck,kind,prompt,answer,points,tags,updated) VALUES(?,?,?,?,?,?,?,?) "
                       "ON CONFLICT(id) DO UPDATE SET deck=excluded.deck,kind=excluded.kind,prompt=excluded.prompt,"
                       "answer=excluded.answer,points=excluded.points,tags=excluded.tags,updated=excluded.updated",
                       (cid, deck['id'], c.get('kind', 'define'), c['prompt'], c['answer'],
                        json.dumps(c.get('points', [])), json.dumps(c.get('tags', [])), time.time()))
            n += 1
    db.commit()
    return n

def deck_list(folder):
    out = []
    for f in sorted(glob.glob(os.path.join(folder, '*.json'))):
        try:
            with open(f, encoding='utf-8') as fh: d = json.load(fh)
            out.append({'id': d['id'], 'name': d.get('name', d['id']), 'blurb': d.get('blurb', ''), 'count': len(d.get('cards', []))})
        except Exception:
            pass
    return out

# ---------- A: rubric grader ----------
STOP = set('a an the of to in on for and or is are be it its that this with as by from at your you their they them can'.split())

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

def grade(card, answer):
    """Returns coverage 0..1, which key ideas were hit/missed, and the features a later learned grader uses."""
    points = json.loads(card['points']) if isinstance(card['points'], str) else card['points']
    at = set(tokens(answer))
    hits, missed, per = [], [], []
    for p in points:
        ok = any(phrase_hit(k, at) for k in p.get('any', []))
        per.append(1 if ok else 0)
        (hits if ok else missed).append(p['idea'])
    total = sum(p.get('weight', 1) for p in points) or 1
    coverage = sum(p.get('weight', 1) for p, h in zip(points, per) if h) / total
    ref = set(tokens(card['answer']))
    overlap = len(at & ref) / (len(ref) or 1)
    features = {'coverage': round(coverage, 3), 'points': per, 'n_points': len(points),
                'words': len(answer.split()), 'ref_overlap': round(overlap, 3)}
    return coverage, hits, missed, features

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

# ---------- API helpers ----------
def card_dict(c, srow=None):
    return {'id': c['id'], 'deck': c['deck'], 'kind': c['kind'], 'prompt': c['prompt'],
            'reps': srow['reps'] if srow else 0}

def next_card(db, deck=None, extra=False):
    now = time.time()
    q = "SELECT c.*, s.due, s.reps FROM cards c LEFT JOIN sched s ON s.card_id=c.id"
    args = []
    if deck: q += " WHERE c.deck=?"; args.append(deck)
    rows = db.execute(q, args).fetchall()
    due = [r for r in rows if r['due'] is not None and r['due'] <= now]
    new = [r for r in rows if r['due'] is None]
    if due: c = min(due, key=lambda r: r['due'])
    elif new: c = sorted(new, key=lambda r: r['id'])[0]
    elif extra and rows: c = min(rows, key=lambda r: r['due'])          # practise ahead: the soonest-due card
    else: return None, min((r['due'] for r in rows if r['due']), default=None)
    return {'id': c['id'], 'deck': c['deck'], 'kind': c['kind'], 'prompt': c['prompt'], 'reps': c['reps'] or 0}, None

def answer(db, card_id, text, confidence, ms):
    c = db.execute("SELECT * FROM cards WHERE id=?", (card_id,)).fetchone()
    if not c: return None
    cov, hits, missed, feats = grade(c, text)
    feats.update({'confidence': confidence, 'ms': ms})
    sug = suggest_rating(cov, confidence)
    with DB_LOCK:
        cur = db.execute("INSERT INTO attempts(card_id,at,answer,confidence,ms,coverage,hits,missed,features,suggested,grader) "
                         "VALUES(?,?,?,?,?,?,?,?,?,?,?)", (card_id, time.time(), text, confidence, ms, cov,
                         json.dumps(hits), json.dumps(missed), json.dumps(feats), sug, 'rubric-A'))
        db.commit()
    srow = db.execute("SELECT * FROM sched WHERE card_id=?", (card_id,)).fetchone()
    now = time.time()
    previews = {g: round((schedule(srow, g, now)[2] - now) / DAY, 3) for g in (1, 2, 3, 4)}   # days until it returns
    return {'attempt': cur.lastrowid, 'coverage': round(cov, 2), 'hits': hits, 'missed': missed, 'previews': previews,
            'reference': c['answer'], 'suggested': sug, 'coach': coach_line(cov, confidence, len(json.loads(c['points'])), hits)}

def coach_line(cov, conf, n, hits):
    k = round(cov * n)
    if conf and conf >= 3 and cov < 0.5:
        return f"You felt sure but covered {k} of {n} key ideas. Cards like this are where overconfidence hides: slow down on it next time."
    if conf and conf <= 2 and cov >= 0.99:
        return "You knew more than you thought: every key idea is there. Trust that answer next time."
    if cov >= 0.99: return f"All {n} key ideas. Solid."
    if cov == 0: return "None of the key ideas yet. Read the model answer, then say it back in your own words before rating."
    return f"{k} of {n} key ideas. Look at what's missing and add it to your own version."

def rate(db, attempt_id, rating, grade_wrong):
    a = db.execute("SELECT * FROM attempts WHERE id=?", (attempt_id,)).fetchone()
    if not a or rating not in (1, 2, 3, 4): return None
    now = time.time()
    with DB_LOCK:
        srow = db.execute("SELECT * FROM sched WHERE card_id=?", (a['card_id'],)).fetchone()
        s, d, due, reps, lapses = schedule(srow, rating, now)
        db.execute("INSERT INTO sched(card_id,stability,difficulty,due,last,reps,lapses) VALUES(?,?,?,?,?,?,?) "
                   "ON CONFLICT(card_id) DO UPDATE SET stability=excluded.stability,difficulty=excluded.difficulty,"
                   "due=excluded.due,last=excluded.last,reps=excluded.reps,lapses=excluded.lapses",
                   (a['card_id'], s, d, due, now, reps, lapses))
        db.execute("UPDATE attempts SET rating=?, grade_wrong=? WHERE id=?", (rating, 1 if grade_wrong else 0, attempt_id))
        db.commit()
    return {'due': due, 'days': round((due - now) / DAY, 1)}

def stats(db, deck=None):
    now = time.time(); day0 = now - (now % DAY)
    w, args = ("WHERE c.deck=?", [deck]) if deck else ("", [])
    cards = db.execute(f"SELECT c.id, s.due, s.reps FROM cards c LEFT JOIN sched s ON s.card_id=c.id {w}", args).fetchall()
    aw = "WHERE a.card_id LIKE ?" if deck else ""
    att = db.execute(f"SELECT a.* FROM attempts a {aw} ORDER BY a.id DESC LIMIT 500", [deck + ':%'] if deck else []).fetchall()
    rated = [a for a in att if a['rating']]
    conf = [a for a in rated if a['confidence']]
    # calibration: confidence (1-4 -> 0..1) minus coverage; positive = overconfident
    cal = round(sum((a['confidence'] - 1) / 3 - a['coverage'] for a in conf) / len(conf), 2) if conf else None
    return {'cards': len(cards), 'new': sum(1 for c in cards if c['due'] is None),
            'due': sum(1 for c in cards if c['due'] is not None and c['due'] <= now),
            'learned': sum(1 for c in cards if (c['reps'] or 0) > 0),
            'today': sum(1 for a in att if a['at'] >= day0),
            'avg_coverage': round(sum(a['coverage'] for a in rated) / len(rated), 2) if rated else None,
            'calibration': cal, 'labels': len(rated),
            'grade_disputes': sum(1 for a in rated if a['grade_wrong'])}
