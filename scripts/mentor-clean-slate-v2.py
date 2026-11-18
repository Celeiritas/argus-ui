#!/usr/bin/env python3
"""Mentor clean-slate reset, v2 (4.59, docs/mentor.md "Clean slate and publication"). Standard library only.

Gives the OWNER's Mentor collection a clean start: no old decks, no inherited mastery or review debt. Nothing is deleted:
  1. disable   ~/.config/argus-ui/mentor.json is written FIRST: the theme's decks, your own deck folder and the old inbox
               off, and every retired file (sha256) and lesson id listed, so a copy put back later is refused;
  2. snapshot  the owner's database (cards, attempts, schedules, settings) and every file that fed it is MOVED into one
               folder, <share>/.set-aside-<YYYYMMDD-HHMM>-mentor-clean-slate/, outside every folder Mentor imports from;
               manifest.json there is rewritten after every move (sha256 of each file, how to put it back);
  3. fresh     the owner's database is created empty on the next start; new lessons arrive only through the gated
               lessons folder (plugins/mentor/publish.py).
Left exactly as they are: other learners (mentor-<id>.db, decks-<id>/), the people file, mentor-ai.json and every other
config file, the installed code, and anything of Mnemosyne's (this script never opens those paths).

    python3 mentor-clean-slate-v2.py                 dry run (the default): print what it would disable, snapshot and reset
    python3 mentor-clean-slate-v2.py --apply         do it: stops the argus-ui user service first, starts it again after
    --service ''                                     do not touch any service (then the server must not be running)

Paths follow the service: ARGUS_MENTOR_DB, ARGUS_MENTOR_INBOX, ARGUS_DECKS, ARGUS_STATIC, ARGUS_MENTOR_LESSONS and
ARGUS_MENTOR_CONFIG are read from the unit's Environment= first, then from this shell.
It refuses when mentor.json already names a collection (a second reset would retire lessons published since), when the
service does not stop, and when the installed Mentor is older than 4.59. If anything fails part-way, the service is LEFT
STOPPED (the old sources are already off in mentor.json) and the manifest says what moved.

Run it on the host where Mentor runs. It can be piped over ssh: `python3 - --dry-run < mentor-clean-slate-v2.py`."""
import argparse, datetime, hashlib, json, os, re, shlex, shutil, sqlite3, subprocess, sys

PATH_VARS = ('ARGUS_MENTOR_DB', 'ARGUS_MENTOR_INBOX', 'ARGUS_DECKS', 'ARGUS_STATIC', 'ARGUS_MENTOR_LESSONS', 'ARGUS_MENTOR_CONFIG')
NOT_RUNNING = ('inactive', 'failed')

def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''): h.update(chunk)
    return h.hexdigest()

def json_files(folder):
    try: return sorted(os.path.join(folder, n) for n in os.listdir(folder) if n.endswith('.json') and os.path.isfile(os.path.join(folder, n)))
    except OSError: return []

def slug(s):
    return re.sub(r'[^a-z0-9_-]+', '-', str(s).lower()).strip('-')[:80] or 'module'      # = mentor.slug

def file_ids(path):
    """The lesson / deck / course id a file imports as (what mentor.load_decks and the inbox call it)."""
    try:
        with open(path, encoding='utf-8') as fh: doc = json.load(fh)
    except (OSError, ValueError): return []
    if not isinstance(doc, dict): return []
    if str(doc.get('format') or '').startswith('mentor-course/'): return [slug(doc.get('id') or os.path.basename(path)[:-5])]
    if 'cards' in doc and 'id' in doc and not any(k.startswith('tier_') for k in doc): return [str(doc['id'])]
    return [slug(os.path.basename(path)[:-5])]

def survey_db(path):
    """Counts from the owner's database, opened read-only (a dry run never writes, not even a journal)."""
    if not os.path.exists(path): return None
    db = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
    try:
        q = lambda sql: db.execute(sql).fetchall()
        n = {t: q(f'SELECT COUNT(*) FROM {t}')[0][0] for t in ('cards', 'attempts', 'sched', 'modules', 'imports', 'courses')
             if q(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{t}'")}
        decks = q("SELECT deck, COUNT(*) FROM cards GROUP BY deck ORDER BY COUNT(*) DESC, deck")
        mods = [r[0] for r in q("SELECT id FROM modules")] if 'modules' in n else []
        courses = [r[0] for r in q("SELECT id FROM courses WHERE id<>'loose'")] if 'courses' in n else []
        due = q("SELECT COUNT(*) FROM sched WHERE due IS NOT NULL")[0][0] if 'sched' in n else 0
        keys = [r[0] for r in q("SELECT key FROM settings")] if q("SELECT name FROM sqlite_master WHERE type='table' AND name='settings'") else []
        return {'counts': n, 'decks': decks, 'modules': mods, 'courses': courses, 'scheduled': due, 'settings': keys,
                'bytes': sum(os.path.getsize(p) for p in (path, path + '-wal', path + '-shm') if os.path.exists(p))}
    finally: db.close()

def service_state(name):
    if not name: return 'not checked'
    try: r = subprocess.run(['systemctl', '--user', 'is-active', name], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired): return 'unknown (no systemctl)'
    return r.stdout.strip() or 'unknown'

def unit_env(name):
    """The service's own Environment= (so the paths are the server's, not this shell's). {} when there is none."""
    if not name: return {}
    try: r = subprocess.run(['systemctl', '--user', 'show', name, '-p', 'Environment', '--value'], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired): return {}
    try: words = shlex.split(r.stdout.strip())
    except ValueError: words = r.stdout.split()
    return dict(w.split('=', 1) for w in words if '=' in w)

def current_config(path):
    """What mentor.json says now: None (no file), a dict, or {'broken': reason}."""
    if not os.path.exists(path): return None
    try:
        with open(path, encoding='utf-8') as fh: doc = json.load(fh)
        return doc if isinstance(doc, dict) else {'broken': 'not a JSON object'}
    except (OSError, ValueError) as x: return {'broken': str(x)[:120]}

def write_json(path, doc):
    """Write path atomically (temporary name, flush to disk, rename)."""
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fh:
        json.dump(doc, fh, indent=1); fh.flush(); os.fsync(fh.fileno())
    os.replace(tmp, path)

def main(argv=None):
    home = os.path.expanduser('~')
    share = os.path.join(home, '.local', 'share', 'argus-ui')
    ap = argparse.ArgumentParser(description='Mentor clean-slate reset (dry run unless --apply).')
    ap.add_argument('--apply', action='store_true', help='do it (default: dry run)')
    ap.add_argument('--dry-run', action='store_true', help='print the plan only (the default)')
    ap.add_argument('--share', default=share)
    ap.add_argument('--db'); ap.add_argument('--inbox'); ap.add_argument('--decks', help='your own deck folder (ARGUS_DECKS)')
    ap.add_argument('--theme-decks', help='the installed theme decks (default $ARGUS_STATIC/decks or <share>/static/decks)')
    ap.add_argument('--lessons'); ap.add_argument('--config')
    ap.add_argument('--service', default='argus-ui', help="systemd --user unit to stop and start ('' = none)")
    ap.add_argument('--code', help='the installed Mentor plugin (default <share>/bundled/mentor)')
    ap.add_argument('--stamp', default=datetime.datetime.now().strftime('%Y%m%d-%H%M'))
    a = ap.parse_args(argv)
    if a.apply and a.dry_run: ap.error('choose --apply or --dry-run, not both')
    uenv = unit_env(a.service)
    env = lambda k: uenv.get(k) or os.environ.get(k)
    share = a.share
    db = a.db or env('ARGUS_MENTOR_DB') or os.path.join(share, 'mentor.db')
    inbox = os.path.expanduser(a.inbox or env('ARGUS_MENTOR_INBOX') or os.path.join(share, 'inbox'))
    decks = a.decks or env('ARGUS_DECKS') or os.path.join(share, 'decks')
    theme = a.theme_decks or os.path.join(env('ARGUS_STATIC') or os.path.join(share, 'static'), 'decks')
    lessons = os.path.expanduser(a.lessons or env('ARGUS_MENTOR_LESSONS') or os.path.join(share, 'lessons'))
    config = os.path.expanduser(a.config or env('ARGUS_MENTOR_CONFIG') or os.path.join(home, '.config', 'argus-ui', 'mentor.json'))
    snap = os.path.join(share, f'.set-aside-{a.stamp}-mentor-clean-slate')
    out = lambda s='': print(s, flush=True)
    out(f'Mentor clean-slate reset v2 - {"APPLY" if a.apply else "DRY RUN (nothing is changed)"}')
    if os.path.exists(snap): out(f'STOP: {snap} already exists; run again in a minute or pass --stamp'); return 2

    info = survey_db(db)
    move_inbox, own_decks, theme_files = json_files(inbox), json_files(decks), json_files(theme)
    learners = sorted(n for n in (os.listdir(share) if os.path.isdir(share) else [])
                      if (n.startswith('mentor-') and n.endswith('.db')) or n.startswith('decks-'))
    svc = service_state(a.service)
    code = a.code or os.path.join(share, 'bundled', 'mentor')
    ready = os.path.exists(os.path.join(code, 'publish.py'))     # 4.59 or later reads mentor.json; older code would reload the theme decks
    conf_now = current_config(config)
    done_before = bool(conf_now and conf_now.get('collection'))
    overrides = {k: uenv[k] for k in PATH_VARS if uenv.get(k)}

    out('\n1. DISABLE the old sources, first, in ' + config)
    out(f'   theme decks off ({theme}: {len(theme_files)} file(s) stay installed, no longer loaded: '
        + ', '.join(os.path.basename(p)[:-5] for p in theme_files) + ')')
    out(f'   your own deck folder off ({decks}) and the old inbox off ({inbox}); the folders stay, Mentor stops reading them')
    ids = sorted(set((info['modules'] + info['courses']) if info else []) |
                 {i for p in move_inbox + own_decks + theme_files for i in file_ids(p)})
    out(f'   retired: {len(move_inbox) + len(own_decks) + len(theme_files)} file fingerprints and {len(ids)} lesson ids '
        '(a copy put back anywhere Mentor reads is refused)')
    if conf_now: out(f'   the current {config} is copied into the snapshot as mentor.json.before')
    out('   jobs: Mentor has no setup, sync or generation job of its own; lesson files reach the inbox by hand copy, '
        'which now lands in a folder Mentor no longer reads')

    out('\n2. SNAPSHOT (moved, never deleted) into')
    out(f'   {snap}')
    if info:
        c = info['counts']
        out(f"   owner database {db} ({info['bytes'] / 1e6:.1f} MB): {c.get('cards', 0)} cards in {len(info['decks'])} decks, "
            f"{c.get('attempts', 0)} attempts, {c.get('sched', 0)} schedule rows ({info['scheduled']} with a due date), "
            f"{c.get('modules', 0)} lessons, {c.get('imports', 0)} import records, settings: {', '.join(info['settings']) or 'none'}")
        for d, k in info['decks']: out(f'     {k:5d}  {d}')
    else: out(f'   owner database {db}: not there (nothing to snapshot)')
    out(f'   inbox {inbox}: {len(move_inbox)} file(s) moved')
    for p in move_inbox: out(f'     {os.path.basename(p)}')
    out(f'   your deck folder {decks}: {len(own_decks)} file(s) moved')
    for p in own_decks: out(f'     {os.path.basename(p)}')

    out('\n3. RESET')
    out(f'   the owner database starts empty on the next start ({db}); collection id "owner-{a.stamp}"')
    out(f'   new lessons arrive only through the gated folder {lessons} (lesson + evidence, docs/mentor.md)')
    out('   no old-to-new mapping; no mastery, attempts or due reviews carried over')

    out('\nLEFT AS THEY ARE')
    out('   other learners: ' + (', '.join(learners) if learners else 'none on this host'))
    out('   the people file, mentor-ai.json, every other config file, the installed code, Mnemosyne (never opened)')
    out(f'   service {a.service or "(none)"}: {svc}; path overrides in its unit: '
        + (', '.join(f'{k}={v}' for k, v in overrides.items()) if overrides else 'none'))
    out(f'   installed Mentor code {code}: ' + ('reads mentor.json (4.59 or later)' if ready else
        'OLDER than 4.59 - it would load the theme decks into the fresh database; deploy 4.59 before --apply'))

    stop = ''
    if done_before:
        stop = (f'STOP: {config} already names collection "{conf_now.get("collection")}" (reset {conf_now.get("reset_at") or "before"}). '
                'A second reset would retire the lessons published since. To start over anyway, move that file aside first.')
    elif conf_now and conf_now.get('broken'):
        stop = f'STOP: {config} cannot be read ({conf_now["broken"]}); fix or move it aside first.'
    elif not ready:
        stop = f'STOP: the installed Mentor ({code}) is older than 4.59. Deploy it first.'
    elif a.service and svc.startswith('unknown'):
        stop = f'STOP: cannot tell whether {a.service} runs ({svc}); stop it yourself and pass --service \'\'.'
    if not a.apply:
        if stop: out('\n' + stop.replace('STOP:', '--apply would stop here:', 1))
        out('\nDry run only. Nothing was changed. Run again with --apply to do it.')
        return 0
    if stop: out(stop + ' Nothing was changed.'); return 3

    # stop the service; refuse unless it is really not running
    was_running = bool(a.service) and svc not in NOT_RUNNING
    if was_running:
        r = subprocess.run(['systemctl', '--user', 'stop', a.service], capture_output=True, text=True, timeout=90)
        now = service_state(a.service)
        if r.returncode or now not in NOT_RUNNING:
            err = r.stderr.strip()[:200]
            out(f'STOP: {a.service} did not stop (it is "{now}")' + (f': {err}' if err else '') + '. Nothing was changed.'); return 4
        out(f'stopped {a.service}')
    elif not a.service and info:
        out('(no service stopped: make sure nothing has the database open)')

    manifest = {'format': 'mentor-clean-slate/1', 'stamp': a.stamp, 'complete': False, 'db': db, 'config': config, 'files': [],
                'counts': info['counts'] if info else {},
                'restore': ['stop the argus-ui service', 'move each file below from "to" back to "from"',
                            'move mentor.json.before back to ' + config + ' (or move mentor.json aside if there was none)',
                            'start the service']}
    try:
        os.makedirs(snap)
        mpath = os.path.join(snap, 'manifest.json')
        write_json(mpath, manifest)
        # 1. the old sources off before anything moves: whatever happens next, they cannot come back
        retired_files = [{'name': os.path.basename(p), 'sha256': sha(p)} for p in move_inbox + own_decks + theme_files]
        if conf_now is not None:
            shutil.copy2(config, os.path.join(snap, 'mentor.json.before')); manifest['config_before'] = 'mentor.json.before'
        os.makedirs(os.path.dirname(config) or '.', exist_ok=True)
        write_json(config, {'format': 'mentor-collection/1', 'collection': f'owner-{a.stamp}', 'reset_at': a.stamp,
                            'snapshot': os.path.basename(snap), 'theme_decks': False, 'own_decks': False, 'legacy_inbox': False,
                            'retired': {'files': retired_files, 'decks': ids}})
        manifest['config_written'] = True; write_json(mpath, manifest)
        out(f'wrote {config}: old sources off, {len(retired_files)} files and {len(ids)} lesson ids retired')
        # 2. move, recording each file in the manifest as it goes
        def move(src, sub):
            dst_dir = os.path.join(snap, sub) if sub else snap
            os.makedirs(dst_dir, exist_ok=True)
            entry = {'from': src, 'to': os.path.join(dst_dir, os.path.basename(src)), 'sha256': sha(src), 'bytes': os.path.getsize(src)}
            shutil.move(src, entry['to']); manifest['files'].append(entry); write_json(mpath, manifest)
        for ext in ('', '-wal', '-shm'):
            if os.path.exists(db + ext): move(db + ext, '')
        for p in move_inbox: move(p, 'inbox')
        for p in own_decks: move(p, 'decks')
        if info:      # the moved copy still opens and answers (a broken snapshot is worse than none)
            chk = sqlite3.connect(f"file:{os.path.join(snap, os.path.basename(db))}?mode=ro", uri=True)
            try: ok = chk.execute('PRAGMA quick_check').fetchone()[0]
            finally: chk.close()
            manifest['quick_check'] = ok; out(f'snapshot database check: {ok}')
        os.makedirs(lessons, exist_ok=True)
        manifest['complete'] = True; write_json(mpath, manifest)
        out(f'moved {len(manifest["files"])} file(s) into {snap}')
    except Exception as x:
        out(f'\nFAILED part-way: {type(x).__name__}: {str(x)[:300]}')
        out(f'The service {a.service or "(none)"} is LEFT STOPPED on purpose. The old sources are '
            + ('already off in ' + config if manifest.get('config_written') else 'still as they were (mentor.json was not written)') + '.')
        out(f'{os.path.join(snap, "manifest.json")} lists every file moved so far. Fix the cause, then either finish by hand '
            'or put the files back as the manifest says, and start the service.')
        return 5
    if was_running:
        subprocess.run(['systemctl', '--user', 'start', a.service], timeout=90)
        out(f'started {a.service}: {service_state(a.service)}')
    out('Done. The old collection is in the snapshot folder; manifest.json says how to put it back.')
    return 0

if __name__ == '__main__':
    sys.exit(main())
