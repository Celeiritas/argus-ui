"""Events: one plain-words message per change of state (docs/checks.md, "Events").

    notify(event)      hand an event to every registered sink; returns the finished event
    register(sink)     add a sink: a function that takes the event (a dict). A sink that raises is skipped.

An event is {id, at, kind, subject, title, body, url, level}:
  kind     broke | needs-yes | fixed | recovered | summary
  subject  what it is about (a check id)
  title    one plain sentence a non-programmer understands ("Jellyfin runs, but cannot read its drive")
  body     two or three plain sentences: what it means and what happens next
  url      a section id or a path under the page, or '' (the page decides how to open it)
  level    alert | warn | info
A repair's events also carry `by` ('owner': his press on the page, with `pressed`, when; 'argus': self-repair), for the daily
summary's words and the phone's rule about his own press (watch.told_by, push.own_press).
The first sink writes a capped file, one JSON object per line: ARGUS_EVENTS, else ~/.local/state/argus-ui/events.jsonl.
Later sinks (a phone push) are added with register(); nothing else here needs to change."""
import json, os, sys, threading, time
from datetime import datetime

KINDS = ('broke', 'needs-yes', 'fixed', 'recovered', 'summary')
LEVELS = ('alert', 'warn', 'info')
MAX_LINES = 500          # the file keeps the newest 500 events
SLACK = 100              # and is only rewritten once it holds this many more, so most writes are one append
_lock = threading.Lock()
_count = [0]
SINKS = []


def events_path():
    return os.path.expanduser(os.environ.get('ARGUS_EVENTS') or '~/.local/state/argus-ui/events.jsonl')


def register(sink):
    if sink not in SINKS: SINKS.append(sink)


def file_sink(event):
    path = events_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with _lock:
        with open(path, 'a', encoding='utf-8') as f: f.write(json.dumps(event, ensure_ascii=False) + '\n')
        with open(path, encoding='utf-8') as f: lines = f.readlines()
        if len(lines) > MAX_LINES + SLACK:
            tmp = path + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f: f.writelines(lines[-MAX_LINES:])
            os.replace(tmp, path)          # atomic: a crash can't leave half a file


def read_events(limit=50):
    """The newest events, newest first (for a page or a summary). A damaged line is skipped."""
    try:
        with open(events_path(), encoding='utf-8') as f: lines = f.readlines()
    except OSError: return []
    out = []
    for l in reversed(lines):
        try: e = json.loads(l)
        except ValueError: continue
        if isinstance(e, dict): out.append(e)
        if len(out) >= limit: break
    return out


def make(kind, subject, title, body='', url='', level=None, at=None):
    if kind not in KINDS: raise ValueError(f'unknown kind {kind!r}')
    with _lock:
        _count[0] += 1; n = _count[0]
    now = at or datetime.now().astimezone()
    return dict(id=f'{int(now.timestamp() * 1000):x}-{n}', at=now.isoformat(timespec='seconds'), kind=kind, subject=str(subject),
                title=str(title)[:200], body=str(body)[:600], url=str(url or ''),
                level=level if level in LEVELS else {'broke': 'alert', 'needs-yes': 'alert', 'fixed': 'info', 'recovered': 'info', 'summary': 'info'}[kind])


def notify(event):
    """Give the event an id and a time if it has none, then hand it to every sink."""
    if not event.get('id') or not event.get('at'):
        event = dict(make(event['kind'], event.get('subject', ''), event.get('title', ''), event.get('body', ''), event.get('url', ''), event.get('level')), **{k: v for k, v in event.items() if v})
    for sink in list(SINKS):
        try: sink(event)
        except Exception as e: print(f'argus-ui: an event sink failed: {e}', file=sys.stderr, flush=True)
    return event


register(file_sink)
