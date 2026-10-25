#!/usr/bin/env python3
"""Check Mentor lessons and decks against the deck rubric (docs/mentor-rubric.md).

    python3 scripts/check-deck.py PATH...      files, or folders of *.json

Prints one line per finding, `file: card: LEVEL Rn message`, and exits 1 if any is an ERROR.
Only what the learner reads is checked: code (snippets, canonical code, fades, answers) may name files."""
import json, os, re, sys

# keys whose text is code, ids or bookkeeping, never prose the learner reads
SKIP = {'full_canonical_code', 'level_1_fade', 'level_2_fade', 'level_3_fade', 'answers', 'snippet', 'code', 'any',
        'id', 'timestamp', 'source_files', 'project', 'lint', 'category', 'card_type', 'concepts_covered', 'teach_order',
        'line', 'weight', 'file_breadcrumb'}
SHORT = {'concise_definition', 'contrast_anchor', 'project_anchor', 'note', 'idea'}      # one sentence each
LONG_WORDS, SHORT_WORDS, MAX_IDEAS = 80, 30, 3
EXT = r'(?:py|js|mjs|css|json|sh|md|html|ts|yml|yaml|toml|txt|db|ini|cfg)'
FILE = re.compile(rf'(?<![\w.])(?!node\.js\b)[\w-]+(?:\.[\w-]+)*\.{EXT}\b|~/|\{{\{{HOME_\w+\}}\}}|(?<![\w:/])(?:[\w.-]+/)+[\w.-]+\.\w{{1,5}}\b', re.I)
JARGON = re.compile(r"\b(?:repo|PR\s*#?\d*|pull request|handoff|CLAUDE\.md|worktree|TODO)\b")
FENCE = re.compile(r'```.*?```', re.S)
URL = re.compile(r'https?://\S+')

def words(s): return len(re.findall(r"[A-Za-z0-9_']+", s))

def prose(obj, key=''):
    """Yield (key, text) for every learner-facing string under obj."""
    if key in SKIP: return
    if isinstance(obj, str):
        yield key, URL.sub('', FENCE.sub('', obj))
    elif isinstance(obj, list):
        for x in obj: yield from prose(x, key)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if k == 'near_example' and isinstance(v, dict):
                yield from prose({kk: vv for kk, vv in v.items() if kk != 'code'}, k)
            else:
                yield from prose(v, k)

def text_rules(item, out):
    for key, s in prose(item):
        m = FILE.search(s)
        if m: out.append(('ERROR', 'R1', f'file path or name in {key}: "{m.group(0)}"'))
        m = JARGON.search(s)
        if m: out.append(('WARN', 'R1', f'repo word in {key}: "{m.group(0)}"'))
        n = words(s)
        if key in SHORT and n > SHORT_WORDS: out.append(('WARN', 'R2', f'{key} has {n} words (one idea: at most {SHORT_WORDS})'))
        elif n > LONG_WORDS: out.append(('WARN', 'R2', f'{key} has {n} words (one idea: at most {LONG_WORDS})'))

def crumb_rule(item, out):
    last = re.split(r'\s*(?:->|→|›)\s*', str(item.get('file_breadcrumb') or ''))[-1]
    if FILE.search(last): out.append(('ERROR', 'R1', f'breadcrumb ends in a file: "{last}" (cards show only the last part)'))

def check(doc):
    """Return [(card id, level, rule, message)] for one lesson or plain deck."""
    found = []
    def add(cid, rules):
        found.extend((cid, *r) for r in rules)
    if isinstance(doc.get('cards'), list):                                    # plain deck
        r = []; text_rules({k: doc.get(k) for k in ('name', 'blurb')}, r); add('deck', r)
        for i, c in enumerate(doc['cards']):
            if isinstance(c, dict):
                r = []; text_rules(c, r); add(c.get('id') or f'card {i + 1}', r)
        return found
    meta = doc.get('metadata') if isinstance(doc.get('metadata'), dict) else {}
    r = []; text_rules({'module_name': meta.get('module_name'), 'cta_summary': doc.get('cta_summary')}, r); add('lesson', r)
    seen = set()
    for i, t in enumerate(doc.get('tier_3_terminology_cards') or []):
        if not isinstance(t, dict): continue
        cid, r = t.get('id') or f'term {i + 1}', []
        text_rules(t, r)
        term = str(t.get('term') or '').strip().lower()
        if term in seen: r.append(('ERROR', 'R5', f'"{t.get("term")}" is defined twice'))
        seen.add(term)
        if not str(t.get('concise_definition') or '').strip(): r.append(('ERROR', 'R5', f'"{t.get("term")}" has no concise_definition'))
        if not str(t.get('try_first') or '').strip(): r.append(('WARN', 'R3', 'teach card has no try_first question'))
        add(cid, r)
    for i, d in enumerate(doc.get('tier_1_faded_code_drills') or doc.get('faded_code_drills') or []):
        if not isinstance(d, dict): continue
        cid, r = d.get('id') or f'drill {i + 1}', []
        text_rules(d, r); crumb_rule(d, r)
        w = d.get('level_0_worked') if isinstance(d.get('level_0_worked'), dict) else {}
        if not w.get('annotations'): r.append(('ERROR', 'R4', 'no level_0_worked annotations: show the worked example first'))
        if not d.get('level_1_fade'): r.append(('ERROR', 'R4', 'no level_1_fade: fade one step at a time'))
        add(cid, r)
    for i, c in enumerate(doc.get('tier_2_self_explanation_cards') or doc.get('self_explanation_flashcards') or []):
        if not isinstance(c, dict): continue
        cid, r = c.get('id') or f'explain {i + 1}', []
        text_rules(c, r); crumb_rule(c, r)
        pre = c.get('preread') if isinstance(c.get('preread'), dict) else {}
        if len(pre.get('key_ideas') or []) > MAX_IDEAS: r.append(('WARN', 'R2', f'pre-read has {len(pre["key_ideas"])} key ideas (at most {MAX_IDEAS})'))
        if not str(pre.get('try_first') or '').strip(): r.append(('WARN', 'R3', 'pre-read has no try_first question'))
        add(cid, r)
    return found

def files(paths):
    for p in paths:
        if os.path.isdir(p):
            yield from sorted(os.path.join(p, f) for f in os.listdir(p) if f.endswith('.json'))
        else:
            yield p

def main(argv):
    if not argv:
        print(__doc__.strip()); return 2
    try: sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError: pass
    errors = warns = 0
    for f in files(argv):
        try:
            with open(f, encoding='utf-8') as fh: doc = json.load(fh)
        except (OSError, ValueError) as e:
            print(f'{f}: -: ERROR R0 cannot read: {e}'); errors += 1; continue
        if not isinstance(doc, dict):
            print(f'{f}: -: ERROR R0 not a lesson or deck'); errors += 1; continue
        for cid, level, rule, msg in check(doc):
            print(f'{f}: {cid}: {level} {rule} {msg}')
            errors += level == 'ERROR'; warns += level == 'WARN'
    print(f'check-deck: {errors} error{"s" * (errors != 1)}, {warns} warning{"s" * (warns != 1)}')
    return 1 if errors else 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
