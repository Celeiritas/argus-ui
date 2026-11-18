#!/usr/bin/env python3
"""Mentor clean-slate reset, v1 (4.59, docs/mentor.md "Clean slate and publication"). Standard library only.

Gives the OWNER's Mentor collection a clean start: no old decks, no inherited mastery or review debt. Nothing is deleted:
  1. snapshot  the owner's database (cards, attempts, schedules, settings) and every file that fed it is MOVED into one
               folder, <share>/.set-aside-<YYYYMMDD-HHMM>-mentor-clean-slate/, outside every folder Mentor imports from,
               with manifest.json (sha256 of each file, the counts, how to put it back);
  2. disable   ~/.config/argus-ui/mentor.json turns the theme's decks and the old inbox off and lists every retired file
               (sha256) and lesson id, so a copy put back later is refused instead of bringing the old decks back;
  3. fresh     the owner's database is created empty on the next start; new lessons arrive only through the gated
               lessons folder (plugins/mentor/publish.py).
Left exactly as they are: other learners (mentor-<id>.db, decks-<id>/), the people file, mentor-ai.json and every other
config file, the installed code, and anything of Mnemosyne's (this script never opens those paths).

    python3 mentor-clean-slate-v1.py                 dry run (the default): print what it would snapshot, disable and reset
    python3 mentor-clean-slate-v1.py --apply         do it: stops the argus-ui user service first and starts it again after
    --keep 'name-*.json'                             leave matching inbox files active (repeatable)
    --service ''                                     do not touch any service (then the server must not be running)

Run it on the host where Mentor runs. It can be piped over ssh: `python3 - --dry-run < mentor-clean-slate-v1.py`."""
import argparse, datetime, fnmatch, hashlib, json, os, shutil, sqlite3, subprocess, sys

def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''): h.update(chunk)
    return h.hexdigest()

def json_files(folder):
    try: return sorted(os.path.join(folder, n) for n in os.listdir(folder) if n.endswith('.json') and os.path.isfile(os.path.join(folder, n)))
    except OSError: return []

def slug(s):
    import re
    return re.sub(r'[^a-z0-9_-]+', '-', str(s).lower()).strip('-') or 'lesson'

def file_ids(path):
    """The lesson / deck / course id a file imports as (what mentor.py would call it)."""
    try:
        with open(path, encoding='utf-8') as fh: doc = json.load(fh)
    except (OSError, ValueError): return []
    if not isinstance(doc, dict): return []
    if doc.get('format') == 'mentor-course/1': return [slug(doc.get('id') or os.path.basename(path)[:-5])]
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

def main(argv=None):
    home = os.path.expanduser('~')
    share0 = os.path.join(home, '.local', 'share', 'argus-ui')
    ap = argparse.ArgumentParser(description='Mentor clean-slate reset (dry run unless --apply).')
    ap.add_argument('--apply', action='store_true', help='do it (default: dry run)')
    ap.add_argument('--dry-run', action='store_true', help='print the plan only (the default)')
    ap.add_argument('--share', default=share0)
    ap.add_argument('--db', default=os.environ.get('ARGUS_MENTOR_DB'))
    ap.add_argument('--inbox', default=os.environ.get('ARGUS_MENTOR_INBOX'))
    ap.add_argument('--decks', default=os.environ.get('ARGUS_DECKS'), help='your own deck folder (ARGUS_DECKS)')
    ap.add_argument('--theme-decks', default=None, help='the installed theme decks (default <share>/static/decks)')
    ap.add_argument('--lessons', default=os.environ.get('ARGUS_MENTOR_LESSONS'))
    ap.add_argument('--config', default=os.environ.get('ARGUS_MENTOR_CONFIG', os.path.join(home, '.config', 'argus-ui', 'mentor.json')))
    ap.add_argument('--keep', action='append', default=[], help='inbox file names (glob) to leave active')
    ap.add_argument('--service', default='argus-ui', help="systemd --user unit to stop and start ('' = none)")
    ap.add_argument('--code', default=None, help='the installed Mentor plugin (default <share>/bundled/mentor)')
    ap.add_argument('--stamp', default=datetime.datetime.now().strftime('%Y%m%d-%H%M'))
    a = ap.parse_args(argv)
    if a.apply and a.dry_run: ap.error('choose --apply or --dry-run, not both')
    share = a.share
    db = a.db or os.path.join(share, 'mentor.db')
    inbox = a.inbox or os.path.join(share, 'inbox')
    decks = a.decks or os.path.join(share, 'decks')
    theme = a.theme_decks or os.path.join(share, 'static', 'decks')
    lessons = a.lessons or os.path.join(share, 'lessons')
    snap = os.path.join(share, f'.set-aside-{a.stamp}-mentor-clean-slate')
    out = print
    mode = 'APPLY' if a.apply else 'DRY RUN (nothing is changed)'
    out(f'Mentor clean-slate reset v1 - {mode}')
    if os.path.exists(snap): out(f'STOP: {snap} already exists; run again in a minute or pass --stamp'); return 2

    info = survey_db(db)
    inbox_files = json_files(inbox)
    keep = [p for p in inbox_files if any(fnmatch.fnmatch(os.path.basename(p), g) for g in a.keep)]
    move_inbox = [p for p in inbox_files if p not in keep]
    own_decks = json_files(decks)
    theme_files = json_files(theme)
    learners = sorted(n for n in (os.listdir(share) if os.path.isdir(share) else [])
                      if (n.startswith('mentor-') and n.endswith('.db')) or n.startswith('decks-'))
    svc = service_state(a.service)
    code = a.code or os.path.join(share, 'bundled', 'mentor')
    ready = os.path.exists(os.path.join(code, 'publish.py'))     # 4.59 or later reads mentor.json; older code would reload the theme decks

    out('\n1. SNAPSHOT (moved, never deleted) into')
    out(f'   {snap}')
    if info:
        c = info['counts']
        out(f"   owner database {db} ({info['bytes'] / 1e6:.1f} MB): {c.get('cards', 0)} cards in {len(info['decks'])} decks, "
            f"{c.get('attempts', 0)} attempts, {c.get('sched', 0)} schedule rows ({info['scheduled']} with a due date), "
            f"{c.get('modules', 0)} lessons, {c.get('imports', 0)} import records, settings: {', '.join(info['settings']) or 'none'}")
        for d, k in info['decks']: out(f'     {k:5d}  {d}')
    else: out(f'   owner database {db}: not there (nothing to snapshot)')
    out(f'   inbox {inbox}: {len(move_inbox)} file(s) moved' + (f', {len(keep)} kept active (--keep)' if keep else ''))
    for p in move_inbox: out(f'     {os.path.basename(p)}')
    for p in keep: out(f'     KEPT {os.path.basename(p)}')
    out(f'   your deck folder {decks}: {len(own_decks)} file(s) moved')
    for p in own_decks: out(f'     {os.path.basename(p)}')
    if os.path.exists(a.config): out(f'   the current {a.config} (moved as mentor.json.before)')

    out('\n2. DISABLE the old sources in ' + a.config)
    out(f'   theme decks off ({theme}: {len(theme_files)} file(s) stay installed, no longer loaded: '
        + ', '.join(os.path.basename(p)[:-5] for p in theme_files) + ')')
    out('   old inbox off (the folder stays; Mentor stops reading it)')
    ids = sorted(set((info['modules'] + info['courses']) if info else []) |
                 {i for p in move_inbox + own_decks + theme_files for i in file_ids(p)})
    out(f'   retired: {len(move_inbox) + len(own_decks) + len(theme_files)} file fingerprints and {len(ids)} lesson ids '
        '(a copy put back anywhere Mentor reads is refused)')
    out('   jobs: Mentor has no setup, sync or generation job of its own; lesson files reach the inbox by hand copy, '
        'which now lands in a folder Mentor no longer reads')

    out('\n3. RESET')
    out(f'   the owner database starts empty on the next start ({db}); collection id "owner-{a.stamp}"')
    out(f'   new lessons arrive only through the gated folder {lessons} (lesson + evidence, docs/mentor.md)')
    out('   no old-to-new mapping; no mastery, attempts or due reviews carried over')

    out('\nLEFT AS THEY ARE')
    out('   other learners: ' + (', '.join(learners) if learners else 'none on this host'))
    out('   the people file, mentor-ai.json, every other config file, the installed code, Mnemosyne (never opened)')
    out(f'   service {a.service or "(none)"}: {svc}' + (' - it is stopped before and started after --apply' if a.apply and svc == 'active' else ''))

    out(f'   installed Mentor code {code}: ' + ('reads mentor.json (4.59 or later)' if ready else
        'OLDER than 4.59 - it would load the theme decks into the fresh database; deploy 4.59 before --apply'))

    if not a.apply:
        out('\nDry run only. Nothing was changed. Run again with --apply to do it.')
        return 0

    if not ready:
        out(f'STOP: the installed Mentor ({code}) is older than 4.59. Deploy it first; nothing was changed.'); return 3
    stopped = False
    if svc == 'active':
        subprocess.run(['systemctl', '--user', 'stop', a.service], check=True, timeout=60); stopped = True
        out(f'stopped {a.service}')
    elif a.service == '' and info:
        out('(no service stopped: make sure nothing has the database open)')
    try:
        os.makedirs(snap)
        manifest = {'format': 'mentor-clean-slate/1', 'stamp': a.stamp, 'db': db, 'files': [], 'counts': info['counts'] if info else {},
                    'restore': ['stop the argus-ui service', 'move mentor.db (and -wal/-shm if here) back to ' + db,
                                'move inbox/* back to ' + inbox + ' and decks/* back to ' + decks,
                                'move mentor.json.before back to ' + a.config + ' (or move mentor.json aside if there was none)',
                                'start the service']}
        def move(src, sub):
            dst_dir = os.path.join(snap, sub) if sub else snap
            os.makedirs(dst_dir, exist_ok=True)
            entry = {'from': src, 'to': os.path.join(dst_dir, os.path.basename(src)), 'sha256': sha(src), 'bytes': os.path.getsize(src)}
            shutil.move(src, entry['to']); manifest['files'].append(entry)
            return entry
        retired_files = [{'name': os.path.basename(p), 'sha256': sha(p)} for p in move_inbox + own_decks + theme_files]
        for ext in ('', '-wal', '-shm'):
            if os.path.exists(db + ext): move(db + ext, '')
        for p in move_inbox: move(p, 'inbox')
        for p in own_decks: move(p, 'decks')
        if os.path.exists(a.config):
            e = move(a.config, ''); os.replace(e['to'], os.path.join(snap, 'mentor.json.before')); e['to'] = os.path.join(snap, 'mentor.json.before')
        if info:      # the moved copy still opens and answers (a broken snapshot is worse than none)
            chk = sqlite3.connect(f"file:{os.path.join(snap, os.path.basename(db))}?mode=ro", uri=True)
            try: ok = chk.execute('PRAGMA quick_check').fetchone()[0]
            finally: chk.close()
            manifest['quick_check'] = ok; out(f'snapshot database check: {ok}')
        with open(os.path.join(snap, 'manifest.json'), 'w', encoding='utf-8') as fh: json.dump(manifest, fh, indent=1)
        conf = {'format': 'mentor-collection/1', 'collection': f'owner-{a.stamp}', 'reset_at': a.stamp,
                'snapshot': os.path.basename(snap), 'theme_decks': False, 'legacy_inbox': False,
                'retired': {'files': retired_files, 'decks': ids}}
        os.makedirs(os.path.dirname(a.config) or '.', exist_ok=True)
        tmp = a.config + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as fh: json.dump(conf, fh, indent=1)
        os.replace(tmp, a.config)
        os.makedirs(lessons, exist_ok=True)
        out(f'moved {len(manifest["files"])} file(s) into {snap}; wrote {a.config}')
    finally:
        if stopped:
            subprocess.run(['systemctl', '--user', 'start', a.service], timeout=60)
            out(f'started {a.service}: {service_state(a.service)}')
    out('Done. The old collection is in the snapshot folder; manifest.json says how to put it back.')
    return 0

if __name__ == '__main__':
    sys.exit(main())
