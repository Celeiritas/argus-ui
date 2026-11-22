#!/usr/bin/env python3
"""Publish a completed explicit source manifest, or inspect full catalog/search JSON.

Never modifies the legacy embedding index or its corpus. No model calls.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
import sqlite3

spec = importlib.util.spec_from_file_location('library', Path(__file__).resolve().parents[1] / 'plugins/memory/library.py')
lib = importlib.util.module_from_spec(spec); spec.loader.exec_module(lib)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db', required=True, help='New library catalog, never the legacy embedding index')
    sub = p.add_subparsers(dest='command', required=True)
    pub = sub.add_parser('publish'); pub.add_argument('manifest'); pub.add_argument('--text-root', required=True)
    pub.add_argument('--apply', action='store_true', help='Publish after validation; default only validates')
    for name in ('search', 'catalog'):
        cmd = sub.add_parser(name); cmd.add_argument('--kind', choices=('',) + lib.KINDS, default='paper' if name == 'search' else '')
        cmd.add_argument('--collection', default='')
        if name == 'search': cmd.add_argument('query')
    args = p.parse_args()
    try:
        if args.command == 'publish':
            manifest = json.loads(Path(args.manifest).read_text(encoding='utf-8-sig'))
            scope, records = lib.prepare(manifest, args.text_root)
            answer = lib.publish(args.db, manifest, args.text_root) if args.apply else dict(valid=True, sources=len(records), collections=scope, published=False)
        elif args.command == 'search': answer = lib.search(args.db, args.query, args.kind, args.collection)
        else: answer = lib.catalog(args.db, args.kind, args.collection)
        print(json.dumps(answer, ensure_ascii=False, indent=2))
    except (ValueError, OSError, sqlite3.Error) as e:
        print('Not published: ' + str(e), file=sys.stderr); return 1
    return 0


if __name__ == '__main__': sys.exit(main())
