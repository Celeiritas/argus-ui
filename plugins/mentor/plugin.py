# Mentor as a bundled server plugin (docs/leafy-plugin.md, docs/mentor.md): the Learn section and api/mentor/...
# The study logic is mentor.py next to this file; this is only the door between Elaia's server and it.
# The owner's database stays where Mentor has always kept it (~/.local/share/argus-ui/mentor.db, or ARGUS_MENTOR_DB),
# not in ctx.data_dir, so moving Mentor into a plugin moved no one's review history. Since 4.37 every other person in the
# people file (learners.py) has a database of their own next to it, mentor-<id>.db, holding only their own lessons
# (~/.local/share/argus-ui/decks-<id>/): never the theme's decks, never the inbox.
import importlib.util, os, threading

def _load(name, file):
    spec = importlib.util.spec_from_file_location(name, os.path.join(os.path.dirname(os.path.abspath(__file__)), file))
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)      # by path: an old installed copy can't shadow it
    return mod
mentor = _load('leafy_mentor', 'mentor.py')
assist = _load('leafy_mentor_assist', 'assist.py')            # the optional local AI (docs/mentor-ai.md)
learners = _load('leafy_mentor_learners', 'learners.py')      # who is studying (the people file)

SHARE = os.path.expanduser('~/.local/share/argus-ui')
DB, DECK_DIRS, THEME_DECKS = None, [], None
AI = threading.Semaphore(1)           # the local model answers one attempt at a time; the rest wait their turn in their threads
PENDING = set()                       # (database path, attempt) whose AI part is still being worked out

class Book:
    """One person's database and its lock. One request at a time on one SQLite connection: two at once (the page asks for
    decks and stats together) could read each other's rows. Every call is a few milliseconds, so nobody waits noticeably.
    Two people's requests never wait for each other."""
    def __init__(self, path, dirs, inbox):
        self.path, self.dirs, self.lock, self.sig = path, dirs, threading.Lock(), None
        self.db = mentor.connect(path, inbox=inbox)
    def load(self, always=False):
        """Load the deck folders; a learner's folder again whenever a file in it was added or changed (no restart)."""
        sig = []
        for d in self.dirs:
            try: sig += sorted((e.name, e.stat().st_mtime, e.stat().st_size) for e in os.scandir(d) if e.name.endswith('.json'))
            except OSError: pass
        if always or sig != self.sig:
            for d in self.dirs: mentor.load_decks(self.db, d)
            self.sig = sig

BOOKS = {}                            # database path -> Book
BOOKS_LOCK = threading.Lock()
ONE = None                            # the owner's lock (as before people); kept for code that still names it

def owner_path():
    return os.environ.get('ARGUS_MENTOR_DB', f'{SHARE}/mentor.db')

def init(ctx):
    global DB, DECK_DIRS, THEME_DECKS, ONE
    THEME_DECKS = os.path.join(ctx.theme_dir, 'decks')
    DECK_DIRS = [THEME_DECKS, os.environ.get('ARGUS_DECKS', f'{SHARE}/decks')]   # the theme's + your own
    BOOKS.clear()
    b = book_for(None)
    DB, ONE = b.db, b.lock

def book_for(person):
    """The Book of the person studying (learners.studying()); None = the owner, as before people existed."""
    if person is None or person['owner_db']: path, dirs, inbox = owner_path(), DECK_DIRS, True
    else:
        path = os.path.join(os.path.dirname(owner_path()) or '.', f"mentor-{person['id']}.db")
        dirs, inbox = [os.path.join(SHARE, f"decks-{person['id']}")], False      # their own lessons only
    with BOOKS_LOCK:
        b = BOOKS.get(path)
        if b is None:
            b = BOOKS[path] = Book(path, dirs, inbox)
            if person is not None and not person['owner_db']: b.load(True)
            else:
                for d in dirs: mentor.load_decks(b.db, d)        # the owner's decks: once at start, as before
    if person is not None and not person['owner_db']: b.load()
    return b

def plural(n, one, many=None):
    return f'{n} {one if n == 1 else (many or one + "s")}'

def line(s):
    # the old one line (before Today): what is waiting to be studied. Kept for anything that still reads it
    if s['due']: return plural(s['due'], 'card') + ' due' + (f" · {s['learn']} to learn" if s['learn'] else '')
    if s.get('checks'): return plural(s['checks'], 'module check question') + ' ready'
    if s['learn']: return f"{s['learn']} to learn"
    return plural(s['new'], 'new card') + ' waiting' if s['new'] else 'Nothing due'

def status(t):
    """Elaia's Today card (and Home's line): "6 due" with the action "Study 10 minutes", per person."""
    if t['due']: ln = f"{t['due']} due"
    elif t['new_left']: ln = f"{plural(t['new_left'], 'new card')} waiting"
    else: ln = 'Nothing due today'
    return {'line': ln, 'needs': bool(t['due']), 'action': 'Study 10 minutes' if t['due'] or t['new_left'] else ''}

def refused(e):
    return e.code, {'ok': False, 'msg': str(e)}

def deck_names(b):
    out = {}
    for d in b.dirs: out.update({x['id']: x['name'] for x in mentor.deck_list(d)})
    return out

def get(path, query, ctx, who=None):
    try:
        if path == 'learners': return 200, learners.listing(who)
        person = learners.studying(who, (query.get('learner') or [None])[0])
    except learners.Refused as e: return refused(e)
    if path == 'ai' and not query.get('attempt'):          # may ask the model server: outside the lock
        return 200, assist.status() if person['role'] == 'owner' else {'enabled': False, 'owner_only': True, 'problem': ''}
    b = book_for(person)
    with b.lock: return _get(b, person, path, query)

def post(path, body, ctx, who=None):
    if not isinstance(body, dict): return 400, {'ok': False, 'msg': 'bad request'}
    try: person = learners.studying(who, body.get('learner'), write=True)
    except learners.Refused as e: return refused(e)
    b = book_for(person)
    with b.lock: code, r = _post(b, person, path, body)
    # the rubric has answered; the local AI's part (if it is on) follows in a thread and the page asks for it (GET ai?attempt=).
    # Only when the person studying is an owner: a learner's answer never starts it (docs/mentor-ai.md, "Who it runs for")
    if (code == 200 and path == 'answer' and r.get('attempt') and r.get('kind') in mentor.AI_KINDS and person['role'] == 'owner'
            and str(body.get('text', '')).strip()):
        c = assist.config()
        if c['enabled'] and not c['problem']:
            r['ai_pending'] = True; PENDING.add((b.path, r['attempt']))
            threading.Thread(target=judge, args=(b, r['attempt'], str(body.get('card', '')), r.get('reference') or '', str(body.get('text', ''))[:2000]), daemon=True).start()
    return code, r

def judge(b, attempt, card, reference, text):
    try:
        with b.lock: prompt = mentor.card_prompt(b.db, card)
        with AI: res = assist.judge(prompt, reference, text)
        with b.lock: mentor.set_ai(b.db, attempt, res)
    finally: PENDING.discard((b.path, attempt))

def _get(b, person, path, query):
    db = b.db
    deck = (query.get('deck') or [None])[0] or None
    if path == 'decks':
        decks = []
        for d in b.dirs: decks += mentor.deck_list(d)
        return 200, {'decks': decks}
    if path == 'next':
        if query.get('replay'):                  # one practice card asked again (replaying the session's mistakes)
            return 200, {'card': mentor.practice_card(db, query['replay'][0])}
        if query.get('card'):                    # one Learn card to read again (Lessons view, Teach me first); never a practice card
            return 200, {'card': mentor.one_card(db, query['card'][0])}
        session = (query.get('session') or ['0'])[0] == '1'     # Study 10 minutes: due first, new cards from the pinned tracks
        card, next_due = mentor.next_card(db, deck, (query.get('extra') or ['0'])[0] == '1', session=session)
        # a course lesson that waits for others (4.32), or a track on the shelf, says why instead of "nothing due"
        return 200, {'card': card, 'next_due': next_due, 'locked': None if card else mentor.locked_reason(db, deck)}
    if path == 'stats': return 200, mentor.stats(db, deck)
    if path == 'today': return 200, {**mentor.today(db, deck_names(b)), 'learner': {k: person[k] for k in ('id', 'name', 'role')}}
    if path == 'track':                          # Preview: one track's size, history and a few questions; nothing is scheduled
        t = mentor.track_preview(db, (query.get('id') or [''])[0], deck_names(b))
        return (200, t) if t else (404, {'ok': False, 'msg': 'There is no track with that id here.'})
    if path == 'ai':                             # one attempt's AI part: pending, done (similarity, feedback), error, or none
        try: aid = int(query['attempt'][0])
        except (ValueError, TypeError, KeyError): return 400, {'ok': False, 'msg': 'bad attempt'}
        if (b.path, aid) in PENDING: return 200, {'state': 'pending'}
        d = mentor.get_ai(db, aid)
        return 200, {'state': 'none'} if not d else {'state': 'error', 'error': d['error']} if 'error' in d else {'state': 'done', **d}
    if path == 'status':                         # Elaia's Today card and Home: the line, "needs you", a verb-first action
        return 200, status(mentor.today(db, deck_names(b)))
    return 404, {'ok': False, 'msg': 'not found'}

def _post(b, person, path, body):
    db = b.db
    try:
        if path == 'answer' and body.get('hint'):     # one rung of the hint ladder; no attempt is written yet
            r = mentor.hint(db, str(body.get('card', '')), int(body['hint']))
        elif path == 'answer':
            text = str(body.get('text', ''))[:2000]
            conf = body.get('confidence'); conf = int(conf) if conf in (1, 2, 3, 4, '1', '2', '3', '4') else None
            ms = int(body.get('ms') or 0)
            r = mentor.answer(db, str(body.get('card', '')), text, conf, max(0, min(ms, 3_600_000)),
                              int(body.get('hints') or 0), body.get('reflections') or [], bool(body.get('skipped')), think=body.get('think') is True)
        elif path == 'rate':
            r = mentor.rate(db, int(body.get('attempt') or 0), int(body.get('rating') or 0), bool(body.get('grade_wrong')))
        elif path == 'undo':                          # Ctrl+Z: the page's last rating this session; {'undone': False} if not undoable
            r = mentor.undo(db, int(body.get('attempt') or 0))
        elif path == 'settings':                      # known keys with the right type only; a track's goal is the owner's to set
            keys = set(mentor.SETTINGS) - ({'goal'} if person['my_role'] != 'owner' else set())
            r = {'settings': mentor.set_settings(db, {k: v for k, v in body.items() if k in keys})}
        else: return 404, {'ok': False, 'msg': 'not found'}
    except mentor.Refusal as e: return 400, {'ok': False, 'msg': str(e)}
    except (ValueError, TypeError): return 400, {'ok': False, 'msg': 'bad request'}
    if r is None: return 400, {'ok': False, 'msg': 'unknown card or attempt'}
    return 200, {'ok': True, **r}
