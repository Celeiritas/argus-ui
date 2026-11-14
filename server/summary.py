"""The daily summary (docs/phone-alerts.md): once a day ONE `summary` event through notify.notify, in plain words.

    ARGUS_SUMMARY_AT     local time, default 08:00
    ARGUS_SUMMARY=0      off
    ARGUS_SUMMARY_STATE  the date of the last summary, default ~/.local/state/argus-ui/summary.json

It is built from the events of the last 24 hours (notify.read_events) and the watch rows as they are now. The date is saved
BEFORE the event is made, so a restart never sends a second one. If the server was off at the set time, the summary is sent
when it is back only within 4 hours after that time; later than that, that day has none."""
import json, os, re, sys, threading
from datetime import datetime, timedelta

import notify

LATE = timedelta(hours=4)          # how long after the set time a summary may still go out
EVERY = 30                         # seconds between looks at the clock
STOP = threading.Event()
TROUBLE = ('broke', 'needs-yes', 'fixed', 'recovered')


def log(msg): print(f'argus-ui: summary: {msg}', file=sys.stderr, flush=True)


def state_path(): return os.path.expanduser(os.environ.get('ARGUS_SUMMARY_STATE') or '~/.local/state/argus-ui/summary.json')


def at():
    """(hour, minute) from ARGUS_SUMMARY_AT; a value that is not HH:MM is logged and 08:00 is used."""
    v = str(os.environ.get('ARGUS_SUMMARY_AT') or '08:00').strip()
    m = re.fullmatch(r'([01]?\d|2[0-3]):([0-5]\d)', v)
    if not m:
        log(f'ARGUS_SUMMARY_AT={v!r} is not a time like 08:00; 08:00 is used'); return 8, 0
    return int(m.group(1)), int(m.group(2))


def last_date():
    try:
        with open(state_path(), encoding='utf-8') as f: return str(json.load(f).get('last') or '')
    except (OSError, ValueError, AttributeError): return ''


def save_date(day):
    path = state_path(); os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f: json.dump({'last': day}, f)
    os.replace(tmp, path)


def due(now, last, hm):
    """The date (YYYY-MM-DD) whose summary should go out now, or None. Today's time, or yesterday's when that window
    reaches past midnight; only within LATE after the set time; never twice for one date."""
    for back in (0, 1):
        t = (now - timedelta(days=back)).replace(hour=hm[0], minute=hm[1], second=0, microsecond=0)
        if t <= now < t + LATE and last != t.date().isoformat(): return t.date().isoformat()
    return None


def _when(e):
    try:
        d = datetime.fromisoformat(str(e.get('at')))
        return d if d.tzinfo else d.astimezone()
    except (TypeError, ValueError): return None


def names(subjects, title):
    """'Media player', 'Media player and Backups', 'Media player, Backups and 1 more'."""
    n = [title(s) for s in subjects]
    if len(n) <= 2: return ' and '.join(n)
    return f'{n[0]}, {n[1]} and {len(n) - 2} more'


def compose(events, rows, now, backups='', hushed=None):
    """The summary event's {title, body, url} for the last 24 hours (events newest first, as read_events gives them).
    `backups`: the Memory plugin's one line when backups need a look (summary_line there), added as the body's last line.
    `hushed(event)`: True for what keeps still (a quiet section, or a check of a task marked known; server/quiet.py): its
    events and its row are left out, so it is neither a need nor counted."""
    since = now - timedelta(hours=24)
    still = hushed or (lambda e: False)
    rows = [r for r in rows or [] if isinstance(r, dict) and r.get('id') and not still({'subject': r['id']})]
    title_of = {r['id']: str(r.get('title') or r['id']) for r in rows}
    title = lambda s: title_of.get(s, s)
    recent = [e for e in events if e.get('kind') in TROUBLE and (_when(e) or since - timedelta(1)) >= since and not still(e)]
    latest, last, stopped = {}, {}, []
    for e in recent:                                   # newest first: the first event of a subject is its latest
        s = str(e.get('subject') or '')
        latest.setdefault(s, e['kind']); last.setdefault(s, e)
        if e['kind'] in ('broke', 'needs-yes') and s not in stopped: stopped.append(s)
    stopped.reverse()                                  # oldest first reads more naturally
    bad_now = [r['id'] for r in rows if r.get('works') is False]
    waiting = [s for s in stopped if latest.get(s) == 'needs-yes' and (s in bad_now or s not in title_of)]
    broken = [s for s in bad_now if s not in waiting]
    fixed = [s for s in stopped if latest.get(s) == 'fixed']
    mine = [s for s in fixed if last[s].get('by') == 'owner']       # he restarted it from the page (an event before 4.40 has no `by`:
    his = [s for s in fixed if s not in mine]                        # only Argus's own repairs wrote `fixed` then)
    back = [s for s in stopped if latest.get(s) == 'recovered']
    plural = lambda n, one, many: one if n == 1 else many
    if waiting:
        head = f'{len(waiting)} {plural(len(waiting), "thing is", "things are")} waiting for your yes'
    elif broken:
        head = f'{len(broken)} {plural(len(broken), "thing is", "things are")} not working right now'
    elif stopped and len(fixed) == len(stopped) and not (mine and his):
        head = f'Yesterday: {len(stopped)} {plural(len(stopped), "thing", "things")} stopped working, {"you" if mine else "Argus"} fixed {plural(len(stopped), "it", "them")}'
    elif stopped:
        head = f'Yesterday: {len(stopped)} {plural(len(stopped), "thing", "things")} stopped working, and {plural(len(stopped), "it works", "all work")} again'
    else:
        head = 'Yesterday: everything worked'
    said = []
    if waiting: said.append(f'{names(waiting, title)} {plural(len(waiting), "needs", "need")} a restart, and Argus waits for your yes.')
    if broken: said.append(f'{names(broken, title)} {plural(len(broken), "does", "do")} not work right now.')
    if mine: said.append(f'You restarted {names(mine, title)} from the page, and {plural(len(mine), "it works", "they work")} now.')
    if his: said.append(f'Argus restarted {names(his, title)} as you allowed, and {plural(len(his), "it works", "they work")} now.')
    if back: said.append(f'{names(back, title)} came back by {plural(len(back), "itself", "themselves")}.')
    if not stopped and not broken:
        said.append(f'Argus checked {len(rows)} {plural(len(rows), "thing", "things")} all day, and nothing stopped working.' if rows
                    else 'Nothing stopped working in the last 24 hours.')
    if not waiting: said.append('Nothing waits for you.')
    body = ' '.join(said[:3])
    if backups: body += '\n' + backups
    return {'title': head, 'body': body, 'url': 'argus' if waiting or broken or stopped else ''}


_backups_told = False                                  # a backups line that could not be made is logged once, not every day


def backups_line(backups):
    """The one backups line, or '' when backups are fine, there is no reader, or the reader failed (logged once)."""
    global _backups_told
    if backups is None: return ''
    try: return str(backups() or '').strip()[:200]
    except Exception as e:
        if not _backups_told:
            _backups_told = True; log(f'sent without the backups line: {e if isinstance(e, LookupError) else type(e).__name__}')
        return ''


def tick(rows=lambda: [], now=None, backups=None, quiet=None):
    """Send today's summary if it is due. -> the event sent, or None. `backups`: a callable that answers the Memory
    plugin's one line (argus_ui.backups_line); it is asked once, only when the summary goes out. `quiet`: a callable that
    answers hushed(event) as it is now (argus_ui.hushed_now), asked once, only when the summary goes out."""
    if os.environ.get('ARGUS_SUMMARY') == '0': return None
    now = now or datetime.now().astimezone()
    day = due(now, last_date(), at())
    if not day: return None
    save_date(day)                                     # first: a crash below never leads to a second summary
    try: rs = rows()
    except Exception as e:
        log(f'the watch rows could not be read ({type(e).__name__})'); rs = []
    hushed = None
    if quiet is not None:
        try: hushed = quiet()
        except Exception as e: log(f'what keeps quiet could not be read ({type(e).__name__})')
    s = compose(notify.read_events(500), rs, now, backups_line(backups), hushed)
    return notify.notify(notify.make('summary', 'daily-summary', s['title'], s['body'], s['url'], 'info'))


def start(rows, backups=None, quiet=None):
    """Its own small thread (one line in the server's start). ARGUS_SUMMARY=0: nothing starts."""
    if os.environ.get('ARGUS_SUMMARY') == '0': return None
    at()                                               # a bad setting is logged once, at start
    def loop():
        while not STOP.is_set():
            try: tick(rows, backups=backups, quiet=quiet)
            except Exception as e: log(f'failed ({type(e).__name__}: {e})')
            STOP.wait(EVERY)
    t = threading.Thread(target=loop, name='argus-summary', daemon=True); t.start()
    return t
