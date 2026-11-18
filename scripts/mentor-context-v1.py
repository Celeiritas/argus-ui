#!/usr/bin/env python3
"""The /mentor command's context packet (4.59, docs/mentor.md "Clean slate and publication"), read-only.

Prints mentor.context_packet() as JSON: the collection, the study goal, the policy version, the published lessons with
their revisions and what the gate held, and the latest "grade was wrong" / "question unclear" flags with the card
revision each one saw. It opens the owner's database read-only (never a write, never a model) using the installed
Mentor code, so there is one definition of the packet. Run it where Mentor runs, for example over ssh:

    ssh <host> 'python3 - --db ~/.local/share/argus-ui/mentor.db' < scripts/mentor-context-v1.py

--code points at another copy of plugins/mentor (a checkout); the default is the installed one."""
import argparse, importlib.util, json, os, sqlite3, sys

def main(argv=None):
    share = os.path.expanduser('~/.local/share/argus-ui')
    ap = argparse.ArgumentParser(description="Print Mentor's authoring context packet (read-only).")
    ap.add_argument('--db', default=os.environ.get('ARGUS_MENTOR_DB', os.path.join(share, 'mentor.db')))
    ap.add_argument('--code', default=os.path.join(share, 'bundled', 'mentor'))
    ap.add_argument('--limit', type=int, default=30, help='how many recent flags')
    a = ap.parse_args(argv)
    src = os.path.join(os.path.expanduser(a.code), 'mentor.py')
    if not os.path.exists(os.path.join(os.path.dirname(src), 'publish.py')):
        print(json.dumps({'error': f'{src} is older than 4.59 (no publish.py); deploy 4.59 first'})); return 3
    spec = importlib.util.spec_from_file_location('leafy_mentor', src)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    if not os.path.exists(os.path.expanduser(a.db)):
        print(json.dumps({'format': 'mentor-context/1', 'empty': True, 'note': 'no owner database yet (a fresh collection)'})); return 0
    db = sqlite3.connect(f'file:{os.path.expanduser(a.db)}?mode=ro', uri=True, factory=m.Conn)
    db.row_factory = sqlite3.Row
    try: print(json.dumps(m.context_packet(db, a.limit), indent=1, ensure_ascii=False))
    finally: db.close()
    return 0

if __name__ == '__main__':
    sys.exit(main())
