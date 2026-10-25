#!/usr/bin/env python3
"""Check Mentor lessons and decks against the deck rubric (docs/mentor-rubric.md).

    python3 scripts/check-deck.py PATH...      files, or folders of *.json

Prints one line per finding, `file: card: LEVEL Rn message`, and exits 1 if any is an ERROR.
Only what the learner reads is checked: code (snippets, canonical code, fades, answers) may name files."""
import ast, json, os, re, sys, textwrap

# keys whose text is code, ids or bookkeeping, never prose the learner reads
SKIP = {'full_canonical_code', 'level_1_fade', 'level_2_fade', 'level_3_fade', 'answers', 'snippet', 'code', 'any',
        'id', 'timestamp', 'source_files', 'project', 'lint', 'category', 'card_type', 'concepts_covered', 'teach_order',
        'line', 'weight', 'file_breadcrumb'}
SHORT = {'concise_definition', 'contrast_anchor', 'project_anchor', 'note', 'idea'}      # one sentence each
LONG_WORDS, SHORT_WORDS, MAX_IDEAS = 80, 30, 3
EXT = r'(?:py|js|mjs|css|json|sh|md|html|ts|yml|yaml|toml|txt|db|ini|cfg)'
# a file name ends in a known extension and is not followed by a call or attribute (`r.json()` is code, not a file);
# library names that end in .js are names, not files
NOT_FILE = r'(?!(?:node|vue|next|nuxt|three|d3|express|chart)\.js\b)'
FILE = re.compile(rf'(?<![\w.$]){NOT_FILE}[\w-]+(?:\.[\w-]+)*\.{EXT}\b(?!\(|\.\w|\w)|~/|\{{\{{HOME_\w+\}}\}}'
                  rf'|(?<![\w:/])(?:[\w.-]+/)+[\w.-]+\.{EXT}\b(?!\(|\.\w|\w)', re.I)
JARGON = re.compile(r"\b(?:(?i:repos?|pull requests?|handoffs?|worktrees?)|PRs?(?:\s*#\d+)?|TODO)\b|(?i:\bCLAUDE\.md\b)")
FENCE = re.compile(r'```.*?```', re.S)
URL = re.compile(r'https?://\S+')

def words(s): return len(re.findall(r"[A-Za-z0-9_']+", s))
def lst(x): return x if isinstance(x, list) else []

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
    for i, t in enumerate(lst(doc.get('tier_3_terminology_cards'))):
        if not isinstance(t, dict): continue
        cid, r = t.get('id') or f'term {i + 1}', []
        text_rules(t, r)
        term = str(t.get('term') or '').strip().lower()
        if term in seen: r.append(('ERROR', 'R5', f'"{t.get("term")}" is defined twice'))
        seen.add(term)
        if not str(t.get('concise_definition') or '').strip(): r.append(('ERROR', 'R5', f'"{t.get("term")}" has no concise_definition'))
        if not str(t.get('try_first') or '').strip(): r.append(('WARN', 'R3', 'teach card has no try_first question'))
        add(cid, r)
    for i, d in enumerate(lst(doc.get('tier_1_faded_code_drills') or doc.get('faded_code_drills'))):
        if not isinstance(d, dict): continue
        cid, r = d.get('id') or f'drill {i + 1}', []
        text_rules(d, r); crumb_rule(d, r)
        w = d.get('level_0_worked') if isinstance(d.get('level_0_worked'), dict) else {}
        if not w.get('annotations'): r.append(('ERROR', 'R4', 'no level_0_worked annotations: show the worked example first'))
        if not d.get('level_1_fade'): r.append(('ERROR', 'R4', 'no level_1_fade: fade one step at a time'))
        add(cid, r)
    for i, c in enumerate(lst(doc.get('tier_2_self_explanation_cards') or doc.get('self_explanation_flashcards'))):
        if not isinstance(c, dict): continue
        cid, r = c.get('id') or f'explain {i + 1}', []
        text_rules(c, r); crumb_rule(c, r)
        pre = c.get('preread') if isinstance(c.get('preread'), dict) else {}
        ideas = lst(pre.get('key_ideas'))
        if len(ideas) > MAX_IDEAS: r.append(('WARN', 'R2', f'pre-read has {len(ideas)} key ideas (at most {MAX_IDEAS})'))
        if not str(pre.get('try_first') or '').strip(): r.append(('WARN', 'R3', 'pre-read has no try_first question'))
        add(cid, r)
    return found

# ---------- courses (checker v2; docs/plans/2026-10-25-mentor-courses-spec.md sections 4, 5, 10) ----------
LO_FIELDS = ('id', 'text', 'verb', 'bloom', 'mode', 'knowledge', 'condition', 'standard', 'parent')
ENUMS = {'bloom': ('remember', 'understand', 'apply', 'analyse', 'evaluate', 'create'), 'mode': ('read', 'write'),
         'knowledge': ('factual', 'conceptual', 'procedural', 'metacognitive')}
VERBS = set('trace predict explain write fix choose build name define order find modify compare rebuild describe'.split())
VAGUE = re.compile(r'^(?:know|understand|learn(?:\s+about)?)\b', re.I)       # not observable (Mager)
LATER_ROLES = ('predict', 'trace', 'parsons', 'write', 'make')                  # card roles phase 4 adds
TIERS = (('tier_3_terminology_cards', ('term', 'recall')), ('tier_1_faded_code_drills', ('drill',)),
         ('tier_2_self_explanation_cards', ('explain', 'find-bug', 'choose-design')))
CITE = re.compile(r'^.+ \(\d{4}[a-z]?\)\. .+\. .+\.$')                          # Author(s) (year). Title. Venue.

def is_course(doc):
    return str(doc.get('format') or '').startswith('mentor-course/')

def check_course(doc):
    """Return [(where, level, rule, message)] for one course: C1 schema, C2 LO form, C3 alignment, C4 cards,
    C5 requires, C6 citations, C7 answers parse, and each lesson's R1-R5."""
    out, los, mods = [], {}, {}       # los: LO id -> (scope, owner id, lo)
    add = lambda where, level, rule, msg: out.append((where, level, rule, msg))
    for k in ('format', 'id', 'name', 'los', 'modules'):
        if k not in doc: add('course', 'ERROR', 'C1', f'no "{k}"')
    r = []; text_rules({'name': doc.get('name'), 'summary': doc.get('summary')}, r); out.extend(('course', *x) for x in r)

    def take_los(items, scope, owner):
        ids = []
        for lo in lst(items):
            if not isinstance(lo, dict) or not lo.get('id'): add(owner, 'ERROR', 'C1', 'an LO without an id'); continue
            w = f"{owner}: LO {lo['id']}"
            if lo['id'] in los: add(w, 'ERROR', 'C1', 'LO id used twice in the course')
            los[lo['id']] = (scope, owner, lo); ids.append(lo['id'])
            missing = [f for f in LO_FIELDS if f not in lo]
            if missing: add(w, 'ERROR', 'C2', f'missing {", ".join(missing)}')
            if scope != 'course' and not lo.get('parent'): add(w, 'ERROR', 'C2', 'no parent (only a course LO has none)')
            for f, ok in ENUMS.items():
                if f in lo and lo[f] not in ok: add(w, 'ERROR', 'C2', f'{f} "{lo[f]}" is not one of {", ".join(ok)}')
            verb, text = str(lo.get('verb') or '').strip(), str(lo.get('text') or '').strip()
            if len(verb.split()) != 1: add(w, 'ERROR', 'C2', f'verb "{verb}": one verb, one word')
            elif VAGUE.match(verb) or VAGUE.match(text): add(w, 'ERROR', 'C2', f'"{verb}" can\'t be seen: use trace, explain, write, choose...')
            elif not text.lower().startswith(verb.lower()): add(w, 'ERROR', 'C2', f'text should start with its verb "{verb}"')
            elif verb.lower() not in VERBS: add(w, 'WARN', 'C2', f'verb "{verb}" is not one of the usual ones ({", ".join(sorted(VERBS))})')
            r = []; text_rules({'text': text}, r); out.extend((w, *x) for x in r)
        return ids

    def cite(where, ref):
        if isinstance(ref, dict) and 'cite' in ref and not CITE.match(str(ref['cite']).strip()):
            add(where, 'ERROR', 'C6', f'citation "{ref["cite"]}" is not "Author(s) (year). Title. Venue."')

    take_los(doc.get('los'), 'course', 'course')
    for i, s in enumerate(lst(doc.get('sources'))): cite(f'source {i + 1}', s)
    for i, mod in enumerate(lst(doc.get('modules'))):
        if not isinstance(mod, dict) or not mod.get('id'): add(f'module {i + 1}', 'ERROR', 'C1', 'a module needs an id'); continue
        if mod['id'] in mods: add(mod['id'], 'ERROR', 'C1', 'module id used twice')
        mods[mod['id']] = mod
        for k in ('name', 'lessons'):
            if k not in mod: add(mod['id'], 'ERROR', 'C1', f'no "{k}"')
        r = []; text_rules({'name': mod.get('name')}, r); out.extend((mod['id'], *x) for x in r)
        for lid in take_los(mod.get('los'), 'module', mod['id']):
            p = los[lid][2].get('parent')
            if p and (p not in los or los[p][0] != 'course'): add(f"{mod['id']}: LO {lid}", 'ERROR', 'C3', f'parent "{p}" is not a course LO')
        seen_lessons = set()
        for j, les in enumerate(lst(mod.get('lessons'))):
            if not isinstance(les, dict) or not les.get('id'): add(f"{mod['id']} lesson {j + 1}", 'ERROR', 'C1', 'a lesson needs an id'); continue
            where = f"{mod['id']}/{les['id']}"
            if les['id'] in seen_lessons: add(where, 'ERROR', 'C1', 'lesson id used twice in the module')
            seen_lessons.add(les['id'])
            if 'los' not in les: add(where, 'ERROR', 'C1', 'no "los": a lesson teaches 1-3 LOs')
            llos = take_los(les.get('los'), 'lesson', where)
            for lid in llos:
                p = los[lid][2].get('parent')
                if p and (p not in los or los[p][0] != 'module' or los[p][1] != mod['id']):
                    add(f'{where}: LO {lid}', 'ERROR', 'C3', f'parent "{p}" is not an LO of module {mod["id"]}')
            notes = {}
            for nt in lst(les.get('notes')):
                if not isinstance(nt, dict) or not nt.get('id'): add(where, 'ERROR', 'C1', 'a note without an id'); continue
                if nt['id'] in notes: add(f"{where}: note {nt['id']}", 'ERROR', 'C1', 'note id used twice')
                notes[nt['id']] = nt; cite(f"{where}: note {nt['id']}", nt.get('source_ref'))
            counts, items = {lid: [0, 0] for lid in llos}, set()
            for key, roles in TIERS:
                for item in lst(les.get(key)):
                    if not isinstance(item, dict): continue
                    iid = item.get('id') or '?'; w = f'{where}: {iid}'
                    if iid in items: add(w, 'ERROR', 'C1', 'card id used twice in the lesson')
                    items.add(iid)
                    role = item.get('role')
                    if role in LATER_ROLES: add(w, 'ERROR', 'C4', f'role {role} arrives in phase 4'); continue
                    if role not in roles: add(w, 'ERROR', 'C4', f'role "{role}" is not one of {", ".join(roles)} for this list')
                    if item.get('lo') not in counts: add(w, 'ERROR', 'C4', f'lo "{item.get("lo")}" is not one of this lesson\'s LOs')
                    else: counts[item['lo']][1 if item.get('check') is True else 0] += 1
                    if not item.get('note'): add(w, 'WARN', 'C4', 'no note: where does this card come from?')
                    elif item['note'] not in notes: add(w, 'ERROR', 'C4', f'note "{item["note"]}" is not one of this lesson\'s')
                    if key == 'tier_1_faded_code_drills': parses(item, notes.get(item.get('note')), w, add)
            for lid, (practice, checks) in counts.items():
                if practice < 2: add(f'{where}: LO {lid}', 'ERROR', 'C4', f'{practice} practice card{"s" * (practice != 1)} (at least 2)')
                if checks < 1: add(f'{where}: LO {lid}', 'ERROR', 'C4', 'no check item ("check": true)')
            out.extend((f'{where}: {cid}', *x) for cid, *x in check(les))          # today's rubric, R1-R5
    for lid, (scope, owner, lo) in los.items():
        kids = [k for k, v in los.items() if v[2].get('parent') == lid]
        if scope in ('course', 'module') and not kids:
            add(f'{owner}: LO {lid}', 'WARN', 'C3', f'no {"module" if scope == "course" else "lesson"} LO serves it')
    for mid_, mod in mods.items():
        for r_ in lst(mod.get('requires')):
            if r_ not in mods: add(mid_, 'ERROR', 'C5', f'requires "{r_}", which is not a module of this course')
    loop = cycle({k: [r_ for r_ in lst(v.get('requires')) if r_ in mods] for k, v in mods.items()})
    if loop: add('modules', 'ERROR', 'C5', 'requires go in a circle: ' + ' → '.join(loop))
    return out

def cycle(graph):
    """One cycle in {node: [nodes it requires]} as a list of nodes (first repeated at the end), or None."""
    state, path = {}, []
    def visit(n):
        state[n] = 1; path.append(n)
        for nxt in graph.get(n, []):
            if state.get(nxt) == 1: return path[path.index(nxt):] + [nxt]
            if not state.get(nxt):
                found = visit(nxt)
                if found: return found
        state[n] = 2; path.pop()
    for n in graph:
        if not state.get(n):
            found = visit(n)
            if found: return found
    return None

def parses(item, note, where, add):
    """C7: a Python drill's canonical code and level-3 answer must parse (never run)."""
    path = str(((note or {}).get('source_ref') or {}).get('path') or '')
    if item.get('lang', 'python' if path.endswith('.py') else None) != 'python':
        add(where, 'INFO', 'C7', f'not parsed ({item.get("lang") or "language unknown"}): only Python is checked'); return
    blobs = [('full_canonical_code', item.get('full_canonical_code'))]
    blobs += [('level 3 answer', a) for a in lst((item.get('answers') or {}).get('level_3'))[:1] if isinstance(a, str)]
    for name, src in blobs:
        try: ast.parse(textwrap.dedent(str(src or '')))
        except SyntaxError as e: add(where, 'ERROR', 'C7', f'{name} is not valid Python (line {e.lineno}: {e.msg})')

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
        for cid, level, rule, msg in (check_course(doc) if is_course(doc) else check(doc)):
            print(f'{f}: {cid}: {level} {rule} {msg}')
            errors += level == 'ERROR'; warns += level == 'WARN'
    print(f'check-deck: {errors} error{"s" * (errors != 1)}, {warns} warning{"s" * (warns != 1)}')
    return 1 if errors else 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
