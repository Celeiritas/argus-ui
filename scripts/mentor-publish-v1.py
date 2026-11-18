#!/usr/bin/env python3
"""Publish one checked Mentor lesson (4.59, docs/mentor.md "Clean slate and publication"). Standard library only.

    python scripts/mentor-publish-v1.py --sha LESSON.json                 print the payload_sha256 the evidence must carry
    python scripts/mentor-publish-v1.py --check LESSON.json               run the server's gate here (EVIDENCE defaults to
                                                                          LESSON.evidence.json next to it); nothing is sent
    python scripts/mentor-publish-v1.py --check LESSON.json --ssh <host>  the same, then copy the evidence and the lesson into
                                                                          ~/.local/share/argus-ui/lessons/ on <host>

The gate here is the same code the server runs (plugins/mentor/publish.py, importing the lesson into a throwaway database
with plugins/mentor/mentor.py), so a lesson held here is held there too. The server checks again on arrival, and also
checks what this machine cannot see: duplicates of lessons already published there, a correction reason when it replaces
a published revision, and the clean-slate reset's retired list. Each file is written under a temporary name and renamed,
evidence first, so the server never reads half a file. Nothing is published when the gate holds the lesson."""
import argparse, importlib.util, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
CODE = os.path.join(os.path.dirname(HERE), 'plugins', 'mentor')
REMOTE = '.local/share/argus-ui/lessons'

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod

def send(host, local, name):
    """Copy one file to <host>:~/<REMOTE>/<name> through ssh (cat into a temporary name, then mv)."""
    with open(local, 'rb') as fh:
        r = subprocess.run(['ssh', '-o', 'BatchMode=yes', host, f'mkdir -p {REMOTE} && cat > {REMOTE}/.{name}.tmp && mv {REMOTE}/.{name}.tmp {REMOTE}/{name}'],
                           stdin=fh, capture_output=True, text=True, timeout=120)
    if r.returncode: raise SystemExit(f'copy of {name} to {host} failed: {r.stderr.strip()[:300]}')

def main(argv=None):
    ap = argparse.ArgumentParser(description='Check (and optionally publish) one Mentor lesson.')
    ap.add_argument('--sha', metavar='LESSON')
    ap.add_argument('--check', metavar='LESSON')
    ap.add_argument('evidence', nargs='?', help='the evidence file (default: LESSON.evidence.json)')
    ap.add_argument('--ssh', metavar='HOST', help='publish to this host after the gate passes')
    a = ap.parse_args(argv)
    publish = load('leafy_mentor_publish', os.path.join(CODE, 'publish.py'))
    if a.sha:
        with open(a.sha, 'rb') as fh: print(publish.sha256(fh.read())); return 0
    if not a.check: ap.error('give --sha LESSON or --check LESSON')
    lesson = a.check
    if os.path.basename(lesson).endswith('.evidence.json'): ap.error('give the lesson file, not its evidence')
    ev_path = a.evidence or lesson[:-5] + '.evidence.json'
    mentor = load('leafy_mentor', os.path.join(CODE, 'mentor.py'))
    mid = mentor.slug(os.path.basename(lesson)[:-5])
    with open(lesson, 'rb') as fh: raw = fh.read()
    try:
        with open(ev_path, encoding='utf-8') as fh: ev = json.load(fh)
    except (OSError, ValueError) as x:
        print(f'HELD {lesson}\n  - no readable evidence file {ev_path} ({str(x)[:120]})'); return 1
    try: gate = publish.check(raw, ev, mid, contract=mentor.dry_import)
    except publish.Held as x:
        print(f'HELD {lesson}'); [print('  - ' + r) for r in x.reasons]; return 1
    print(f'PASS {lesson}: revision {gate["revision"]} ({gate["reason"]}), policy {ev.get("policy")}')
    if a.ssh:
        name = mid + '.json'
        send(a.ssh, ev_path, mid + '.evidence.json'); send(a.ssh, lesson, name)
        print(f'sent to {a.ssh}:~/{REMOTE}/{name}; the server checks it again and records "published" or "held" (Learn > lesson list)')
    return 0

if __name__ == '__main__':
    sys.exit(main())
