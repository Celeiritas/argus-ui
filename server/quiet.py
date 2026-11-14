"""What Today, the phone and the daily summary keep quiet about, in one place (docs/home.md "Quiet").

1. Quiet sections. A section in quiet_sections() never counts as something that needs the owner: its tile keeps its own line
   ("6 due"), but its status answers needs false with no action and no count (no row under "N things need you", no number in
   it, no button on Today, no dot or count on the bar or the strip), and an event about it never buzzes and never goes into
   the daily summary. DEFAULT_QUIET is {'mentor'} (the owner, 2026-11-13: no Mentor notifications, ever); the next build
   turns it into the owner's own setting per section, read here. A learner's page is not quiet: Mentor is what she studies.

2. Known marks ("Known, low priority"). A failed task the owner already knows about, marked from its card or its row on
   Today (POST api/known). It stays on Watch in grey, but leaves "N things need you", never buzzes and is not in the summary.
   Saved in ARGUS_KNOWN (default ~/.local/state/argus-ui/known.json) as {task: {"fp": fingerprint, "at": ISO time}}, so it
   survives restarts and deploys.
   The fingerprint of a failure: systemd's Result and ExecMainStatus, and the codes of that task's checks that fail, as
   "exit-code/1/" or "success/0/no-answer" (fingerprint()). The mark goes away by itself (reconcile()) when
     - the task works again: a run ended well (state ok), or an always-on task runs while its checks pass, or
     - it fails in another way: the fingerprint is not the one it was marked with.
   It stays while the task is frozen, while a timer task is in the middle of a run, and while the task is missing from
   systemd's list (a hiccup must not wake every known failure at once)."""
import json, os, threading
from datetime import datetime

DEFAULT_QUIET = frozenset({'mentor'})
_lock = threading.Lock()


def quiet_sections():
    """The sections that never count as needing the owner. One place: the next build reads the owner's setting here."""
    return DEFAULT_QUIET


def is_quiet(section): return isinstance(section, str) and section in quiet_sections()


def known_path(): return os.path.expanduser(os.environ.get('ARGUS_KNOWN') or '~/.local/state/argus-ui/known.json')


def load():
    """{task: {"fp", "at"}}; a missing or broken file is no marks."""
    try:
        with open(known_path(), encoding='utf-8') as f: d = json.load(f)
    except (OSError, ValueError): return {}
    if not isinstance(d, dict): return {}
    return {k: v for k, v in d.items() if isinstance(k, str) and isinstance(v, dict) and isinstance(v.get('fp'), str)}


def _save(d):
    path = known_path(); os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f: json.dump(d, f, indent=1)
    os.replace(tmp, path)                  # atomic: a crash mid-write never leaves half a file


def key(j):
    """The name a mark is kept under: the task's unit, or for a transient task folded into one card (zeus-deploy-<id>) its
    base name, so a later run that fails the same way stays known and one that fails another way comes back."""
    return j.get('base') or j.get('job') or ''


def failing(j): return j.get('state') == 'failed' or j.get('works') is False


def works(j):
    """The task did its job: a run ended well, or an always-on task runs while its checks pass."""
    if j.get('works') is False: return False
    return j.get('state') == 'ok' or (j.get('state') == 'running' and j.get('next') == 'always on')


def fingerprint(j, rows=()):
    """How a failing task fails, as one string; None when it does not fail."""
    if not failing(j): return None
    codes = sorted({str(r.get('code') or '') for r in rows or () if r.get('job') == j.get('job') and r.get('works') is False})
    return f"{j.get('result') or ''}/{j.get('status') or ''}/{','.join(codes)}"


def reconcile(jobs, rows=()):
    """Clear the marks whose task works again or fails another way (see above). -> the marks left, {task: {fp, at}}."""
    by = {key(j): j for j in jobs or () if isinstance(j, dict)}
    with _lock:
        marks = load(); keep = {}
        for job, m in marks.items():
            j = by.get(job)
            if j is not None and (works(j) or (failing(j) and fingerprint(j, rows) != m['fp'])): continue
            keep[job] = m
        if keep != marks:
            try: _save(keep)
            except OSError: pass
    return keep


def mark(j, rows=(), now=None):
    """Mark a failing task as known. -> (ok, the time it was marked or the reason it was not)."""
    fp = fingerprint(j, rows)
    if fp is None: return False, 'It works again, so there is nothing to mark.'
    at = (now or datetime.now().astimezone()).isoformat(timespec='seconds')
    with _lock:
        d = load(); d[key(j)] = {'fp': fp, 'at': at}; _save(d)
    return True, at


def unmark(job):
    with _lock:
        d = load()
        if d.pop(job, None) is not None: _save(d)
    return True


def hushed(event, rows=(), marks=None):
    """True when an event keeps still: it is about a quiet section (its `section` or its subject), or about a check of a task
    marked known. `rows`: the watch rows (a check's id -> its task), `marks`: the marks after reconcile()."""
    if not isinstance(event, dict): return False
    subject = str(event.get('subject') or '')
    if is_quiet(event.get('section')) or is_quiet(subject): return True
    marks = load() if marks is None else marks
    job = next((r.get('job') for r in rows or () if r.get('id') == subject), '') or ''
    return bool(job) and job in marks
