# Mentor as a bundled server plugin (docs/leafy-plugin.md, docs/mentor.md): the Learn section and api/mentor/...
# The study logic is mentor.py next to this file; this is only the door between Elaia's server and it.
# The database stays where Mentor has always kept it (~/.local/share/argus-ui/mentor.db, or ARGUS_MENTOR_DB),
# not in ctx.data_dir, so moving Mentor into a plugin moved no one's review history.
import importlib.util, os, threading

_spec = importlib.util.spec_from_file_location('leafy_mentor', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mentor.py'))
mentor = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(mentor)    # by path: an old installed mentor.py can't shadow it

SHARE = os.path.expanduser('~/.local/share/argus-ui')
DB, DECK_DIRS = None, []
# One request at a time on Mentor's single SQLite connection: two at once (the page asks for decks and stats together)
# could read each other's rows. Every call is a few milliseconds, so nobody waits noticeably.
ONE = threading.Lock()

def init(ctx):
    global DB, DECK_DIRS
    DECK_DIRS = [os.path.join(ctx.theme_dir, 'decks'), os.environ.get('ARGUS_DECKS', f'{SHARE}/decks')]   # the theme's + your own
    DB = mentor.connect(os.environ.get('ARGUS_MENTOR_DB', f'{SHARE}/mentor.db'))
    for d in DECK_DIRS: mentor.load_decks(DB, d)

def plural(n, one, many=None):
    return f'{n} {one if n == 1 else (many or one + "s")}'

def line(s):
    # Home's one line: what is waiting to be studied
    if s['due']: return plural(s['due'], 'card') + ' due' + (f" · {s['learn']} to learn" if s['learn'] else '')
    if s['learn']: return f"{s['learn']} to learn"
    return plural(s['new'], 'new card') + ' waiting' if s['new'] else 'Nothing due'

def get(path, query, ctx):
    with ONE: return _get(path, query)

def post(path, body, ctx):
    with ONE: return _post(path, body)

def _get(path, query):
    deck = (query.get('deck') or [None])[0] or None
    if path == 'decks':
        decks = []
        for d in DECK_DIRS: decks += mentor.deck_list(d)
        return 200, {'decks': decks}
    if path == 'next':
        if query.get('card'):                    # one Learn card to read again (Lessons view); never a practice card
            return 200, {'card': mentor.one_card(DB, query['card'][0])}
        card, next_due = mentor.next_card(DB, deck, (query.get('extra') or ['0'])[0] == '1')
        return 200, {'card': card, 'next_due': next_due}
    if path == 'stats': return 200, mentor.stats(DB, deck)
    if path == 'status': return 200, {'line': line(mentor.stats(DB))}
    return 404, {'ok': False, 'msg': 'not found'}

def _post(path, body):
    try:
        if path == 'answer' and body.get('hint'):     # one rung of the hint ladder; no attempt is written yet
            r = mentor.hint(DB, str(body.get('card', '')), int(body['hint']))
        elif path == 'answer':
            text = str(body.get('text', ''))[:2000]
            conf = body.get('confidence'); conf = int(conf) if conf in (1, 2, 3, 4, '1', '2', '3', '4') else None
            ms = int(body.get('ms') or 0)
            r = mentor.answer(DB, str(body.get('card', '')), text, conf, max(0, min(ms, 3_600_000)),
                              int(body.get('hints') or 0), body.get('reflections') or [], bool(body.get('skipped')))
        elif path == 'rate':
            r = mentor.rate(DB, int(body.get('attempt') or 0), int(body.get('rating') or 0), bool(body.get('grade_wrong')))
        else: return 404, {'ok': False, 'msg': 'not found'}
    except (ValueError, TypeError): return 400, {'ok': False, 'msg': 'bad request'}
    if r is None: return 400, {'ok': False, 'msg': 'unknown card or attempt'}
    return 200, {'ok': True, **r}
