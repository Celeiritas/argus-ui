# Mealie: tonight's meal on Today and this week's meal plan, read from the owner's Mealie (docs/mealie.md).
# A bundled server plugin (docs/leafy-plugin.md): GET api/mealie/status (Today's line) and api/mealie/plan (the section).
# Read-only: one GET of Mealie's meal plan (and of the signed-in user, for recipe links), never a write to Mealie.
#
# The API token lives in one file on the server, ~/.config/argus-ui/mealie-token.txt (ARGUS_MEALIE_TOKEN points elsewhere).
# It is read on every request (a new token counts at once, no restart) and goes to Mealie only, in the Authorization
# header: never into an answer, a log line, an error text or the page. Redirects are not followed, so the header never
# reaches another address, and the system's proxy settings are not used.
#
# Mealie's API (v3.30.0, the version the owner runs; source pinned at that tag, docs/mealie.md cites it):
#   GET /api/households/mealplans?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD&perPage=N   Authorization: Bearer <token>
#     -> {"page", "perPage", "total", "totalPages", "items": [{"date", "entryType", "title", "text", "recipe": {"name", "slug"} | null, ...}]}
#   GET /api/users/self -> {"groupSlug", ...}; a recipe's page is <mealie>/g/<groupSlug>/r/<recipe slug>
import calendar, datetime, http.client, json, os, re, socket, threading, time, urllib.error, urllib.parse, urllib.request

DEFAULT_URL = 'http://127.0.0.1:9925'       # Mealie's documented default port, on the machine LeafyGrove runs on
TIMEOUT = 3                                 # seconds in all for one look at Mealie (the plan and, once per token, the group
                                            # together): Today never waits longer for a meal, however slowly Mealie answers
MAX_BYTES = 1 << 20                         # Mealie's answer is read up to 1 MB, no more
FRESH, STALE_ERR = 60, 30                   # a good answer is kept 60 s, a failure 30 s (the page asks every 15 s)
AGAIN = 5                                   # "Check again" asks Mealie again when the kept answer is older than 5 s
DAYS = 7                                    # today and the next six days
ORDER = ('breakfast', 'lunch', 'dinner', 'side', 'snack', 'drink', 'dessert')
TYPE_WORD = {t: t.capitalize() for t in ORDER}
ADDRESS = re.compile(r'https?://[^\s"\'<>\\`]+')
TOKEN_OK = re.compile(r'[A-Za-z0-9._~+/=-]{8,4096}')     # a JWT or similar: one word of safe characters

SETUP_LINE = 'Not set up yet: make an API token in Mealie'
LINES = {
    'setup': SETUP_LINE,
    'empty': 'Not set up yet: the token file is empty',
    'badtoken': 'The token file does not hold a token',
    'config': 'mealie.json could not be read',
    'refused': 'Mealie refused the token: make a new one',
    'down': 'Mealie is not answering',
    'slow': 'Mealie took too long to answer',
    'unexpected': 'Mealie answered something unexpected',
}

def where(env=None):
    """(token file, settings file), asked on every request. ARGUS_MEALIE_TOKEN and ARGUS_MEALIE point elsewhere; an
    empty setting counts as unset."""
    env = os.environ if env is None else env
    cfg = os.path.join(os.path.expanduser('~'), '.config', 'argus-ui')
    tok = os.path.expanduser(env.get('ARGUS_MEALIE_TOKEN') or '') or os.path.join(cfg, 'mealie-token.txt')
    conf = os.path.expanduser(env.get('ARGUS_MEALIE') or '') or os.path.join(cfg, 'mealie.json')
    return tok, conf

def media_file(env=None):
    env = os.environ if env is None else env
    return os.path.expanduser(env.get('ARGUS_MEDIA') or '') or os.path.join(os.path.expanduser('~'), '.config', 'argus-ui', 'media.json')

def _address(v):
    v = v.strip() if isinstance(v, str) else ''
    return v.rstrip('/') if len(v) <= 300 and ADDRESS.fullmatch(v) else ''

def settings(path):
    """The server-side address of Mealie: {"url": "http://127.0.0.1:<port>"} in mealie.json, else DEFAULT_URL.
    (url, problem): a broken file gives ('', problem) and nothing is asked."""
    if not os.path.exists(path): return DEFAULT_URL, ''
    try:
        with open(path, encoding='utf-8') as f: d = json.load(f)
        if not isinstance(d, dict): raise ValueError
    except (OSError, ValueError): return '', 'config'
    if 'url' not in d: return DEFAULT_URL, ''
    url = _address(d.get('url'))
    return (url, '') if url else ('', 'config')

def open_address(path):
    """The address the owner's browser opens Mealie at: the "mealie" key of media.json (Today's Open row), or ''."""
    try:
        with open(path, encoding='utf-8') as f: d = json.load(f)
    except (OSError, ValueError): return ''
    if not isinstance(d, dict): return ''
    return _address(next((v for k, v in d.items() if str(k).lower() == 'mealie'), ''))

def token(path):
    """(token, state, stamp): the first non-empty line of the token file. state is '' when there is a token, else 'setup'
    (no file), 'empty' or 'badtoken'. stamp changes when the file does, so a new token is used at once."""
    try:
        st = os.stat(path)
        with open(path, encoding='utf-8', errors='replace') as f: text = f.read(8192)
    except FileNotFoundError: return '', 'setup', None
    except OSError: return '', 'badtoken', None
    stamp = (st.st_mtime_ns, st.st_size)
    first = next((ln.strip() for ln in text.splitlines() if ln.strip()), '')
    if not first: return '', 'empty', stamp
    if not TOKEN_OK.fullmatch(first): return '', 'badtoken', stamp
    return first, '', stamp

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k): return None      # a 3xx becomes an HTTPError: the token never follows it

_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect)

class Failed(Exception):
    def __init__(self, state): super().__init__(state); self.state = state

def _get(base, path, tok, until):
    """GET base+path with the token, given up at `until` (time.monotonic()); the decoded JSON, or Failed(state). No text
    from the exception is kept: an error answer could echo a header."""
    req = urllib.request.Request(base + path, headers={'Authorization': 'Bearer ' + tok, 'Accept': 'application/json',
                                                       'User-Agent': 'LeafyGrove-mealie'})
    try:
        with _OPENER.open(req, timeout=max(.05, until - time.monotonic())) as r:
            body = b''
            while len(body) <= MAX_BYTES:              # piece by piece, so an answer that trickles in still ends on time
                if time.monotonic() > until: raise Failed('slow')
                part = r.read1(65536)
                if not part: break
                body += part
    except urllib.error.HTTPError as e:
        e.close()
        raise Failed('refused' if e.code in (401, 403) else 'unexpected') from None
    except (socket.timeout, TimeoutError): raise Failed('slow') from None
    except urllib.error.URLError as e:
        raise Failed('slow' if isinstance(e.reason, (socket.timeout, TimeoutError)) else 'down') from None
    except (OSError, ValueError): raise Failed('down') from None
    except http.client.HTTPException: raise Failed('unexpected') from None   # cut short (IncompleteRead), not HTTP (BadStatusLine)
    if len(body) > MAX_BYTES: raise Failed('unexpected')
    try: return json.loads(body.decode('utf-8'))
    except ValueError: raise Failed('unexpected') from None

def ask(base, path, tok, until):
    """_get on a helper thread, waited for until `until` at the latest: the deadline holds even when one network step
    (connecting, a header line) stalls. A helper left behind stops on its own at its socket timeout or deadline; its
    answer is dropped. Anything it raises becomes a Failed state, never an exception with text."""
    left = until - time.monotonic()
    if left <= 0: raise Failed('slow')
    box = {}
    def run():
        try: box['doc'] = _get(base, path, tok, until)
        except Failed as e: box['state'] = e.state
        except Exception: box['state'] = 'unexpected'
    t = threading.Thread(target=run, name='mealie-ask', daemon=True); t.start(); t.join(left)
    if t.is_alive(): raise Failed('slow')
    if 'doc' in box: return box['doc']
    raise Failed(box.get('state', 'unexpected'))

def _text(v, n=100):
    return ' '.join(str(v).split())[:n] if isinstance(v, (str, int, float)) and not isinstance(v, bool) else ''

def part(v):
    """True for one safe piece of a link's path: no / ? # %, and not "." or ".." (a browser reads those as "here" and
    "up one", so /g/../r/.. would open Mealie's home page instead of the recipe)."""
    return bool(re.fullmatch(r'[A-Za-z0-9._~-]+', v)) and v not in ('.', '..')

def entries(doc):
    """Mealie's page of plan entries -> [{date, type, name, slug}], checked; Failed('unexpected') when it is not that shape."""
    items = doc.get('items') if isinstance(doc, dict) else None
    if not isinstance(items, list): raise Failed('unexpected')
    out = []
    for it in items:
        if not isinstance(it, dict): continue
        day = it.get('date') if isinstance(it.get('date'), str) else ''
        try: datetime.date.fromisoformat(day[:10])
        except ValueError: continue
        rec = it.get('recipe') if isinstance(it.get('recipe'), dict) else {}
        name = _text(rec.get('name')) or _text(it.get('title')) or _text(it.get('text')) or 'A meal with no name'
        slug = _text(rec.get('slug'), 200)
        kind = str(it.get('entryType') or '').lower()
        out.append({'date': day[:10], 'type': kind if kind in ORDER else 'other', 'name': name, 'slug': slug if part(slug) else ''})
    out.sort(key=lambda e: (e['date'], ORDER.index(e['type']) if e['type'] in ORDER else len(ORDER), e['name'].lower()))
    return out

_lock = threading.Lock()
_cache = {}            # key -> (time, result)
_slug = {}             # (base, token stamp) -> (time, group slug or None when Mealie did not answer)

def fetch(today, env=None, now=None, max_age=None):
    """Everything the section shows, from the cache when it is fresh: {state, entries, group, more}. state '' = read.
    One fetch at a time; the GETs that arrive meanwhile wait and share its answer. Both asks together take at most
    TIMEOUT seconds. max_age: "Check again" asks Mealie again when the kept answer is older than that (never more than
    once every few seconds)."""
    now = time.time() if now is None else now
    tok_path, conf_path = where(env)
    tok, problem, stamp = token(tok_path)
    base, bad = settings(conf_path)
    if problem or bad: return {'state': problem or bad, 'entries': [], 'group': '', 'more': False}
    key = (base, stamp, today.isoformat())
    with _lock:
        hit = _cache.get(key)
        keep = FRESH if hit and not hit[1]['state'] else STALE_ERR
        if max_age is not None: keep = min(keep, max_age)
        if hit and now - hit[0] < keep: return hit[1]
        until = time.monotonic() + TIMEOUT
        end = today + datetime.timedelta(days=DAYS - 1)
        q = urllib.parse.urlencode({'start_date': today.isoformat(), 'end_date': end.isoformat(), 'perPage': 100, 'page': 1})
        try:
            doc = ask(base, '/api/households/mealplans?' + q, tok, until)
            res = {'state': '', 'entries': entries(doc), 'group': '', 'more': False}
            total = doc.get('total')
            res['more'] = isinstance(total, int) and total > len(doc['items'])
        except Failed as e:
            res = {'state': e.state, 'entries': [], 'group': '', 'more': False}
        if not res['state']:
            # the recipe links' group: once per token while Mealie gives it; a failed ask is not repeated for STALE_ERR
            # seconds, and never costs the plan already read (the section shows it without links meanwhile)
            known = _slug.get((base, stamp))
            if not known or (known[1] is None and not 0 <= now - known[0] < STALE_ERR):
                try:
                    me = ask(base, '/api/users/self', tok, until)
                    g = _text(me.get('groupSlug'), 100) if isinstance(me, dict) else ''
                    _slug[(base, stamp)] = (now, g if part(g) else '')
                except Failed:
                    _slug[(base, stamp)] = (now, None)
            res['group'] = _slug[(base, stamp)][1] or ''
        _cache.clear(); _cache[key] = (now, res)
        return res

def _names(es):
    return ' · '.join(e['name'] for e in es)

def line(res, today):
    """Today's one line: tonight's dinner, else what else is planned today, else that nothing is."""
    if res['state']: return LINES[res['state']]
    day = [e for e in res['entries'] if e['date'] == today.isoformat()]
    dinner = [e for e in day if e['type'] == 'dinner']
    if dinner: return 'Tonight: ' + _names(dinner)
    if not day: return 'No meal planned today'
    if len(day) == 1: return f"No dinner planned · {TYPE_WORD.get(day[0]['type'], 'Meal')}: {day[0]['name']}"
    return f'No dinner planned · {len(day)} other meals today'

def day_label(d, today):
    if d == today: return 'Today'
    if d == today + datetime.timedelta(days=1): return 'Tomorrow'
    return f'{calendar.day_name[d.weekday()]}, {calendar.month_abbr[d.month]} {d.day}'

def plan(res, today, open_href):
    """The section: today always (empty or not), then each later day that has a meal. A recipe links to its page in
    Mealie only when the owner's browser address is known (media.json) and Mealie said its group."""
    days = []
    for i in range(DAYS):
        d = today + datetime.timedelta(days=i)
        meals = [e for e in res['entries'] if e['date'] == d.isoformat()]
        if i and not meals: continue
        out = []
        for e in meals:
            m = {'type': TYPE_WORD.get(e['type'], 'Meal'), 'name': e['name']}
            if open_href and res['group'] and e['slug']: m['href'] = f"{open_href}/g/{res['group']}/r/{e['slug']}"
            out.append(m)
        days.append({'date': d.isoformat(), 'label': day_label(d, today), 'meals': out})
    return {'state': res['state'] or 'ok', 'line': line(res, today), 'days': days if not res['state'] else [],
            'more': res['more'], 'open': open_href}

def get(path, query, ctx):
    today = datetime.date.today()          # the server's own day (LeafyGrove and Mealie share the machine's clock)
    if path == 'status':
        try: return 200, {'line': line(fetch(today), today), 'needs': False}
        except Exception: return 200, {'line': LINES['unexpected'], 'needs': False}   # never a traceback: it could hold the token
    if path == 'plan':
        again = (query or {}).get('again') == ['1']          # Check again: a newer answer than the kept one, at most every 5 s
        try: res = fetch(today, max_age=AGAIN if again else None)
        except Exception: res = {'state': 'unexpected', 'entries': [], 'group': '', 'more': False}
        return 200, plan(res, today, open_address(media_file()))
    return 404, {'ok': False, 'msg': 'not found'}
