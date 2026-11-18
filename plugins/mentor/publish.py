"""Mentor's publication gate (4.59, docs/mentor.md "Clean slate and publication"). Standard library only, no network.

A lesson is published by putting two files in the lessons folder (~/.local/share/argus-ui/lessons): the lesson itself,
<id>.json, in the lesson format Mentor already imports (docs/mentor-command.md, checked by importing it into a throwaway
database), and <id>.evidence.json, "format": "mentor-evidence/1", saying what was checked:

    {"format": "mentor-evidence/1", "policy": "mentor-policy/1",       the authoring policy it was checked against
     "payload_sha256": "<sha256 of the exact lesson bytes>",           binds the check to this file, not a "verified" flag
     "revision": "2026-11-18a",                                        the lesson's revision name
     "risk": "routine" | "clinical" | "regulated",
     "review": {"by": "...", "qualification": "...", "at": "..."},     a qualified person's review: clinical / regulated only
     "sources": [{"locator": "...", "revision": "..."}],               where each claim was checked, at which version
     "correction": {"reason": "..."},                                  required when it replaces a published revision
     "items": {"<item id>": {"status": "ready", "checks": {"answerability": "pass", ...}}}}

Every item in the lesson must be listed as ready with every check in CHECKS passed; an item still on hold stays in the
draft and out of the published file. check() raises Held with every reason, or returns what the importer records.
Publication is separate from daily scheduling: a published lesson's cards are new cards like any other."""
import hashlib, json, os, re

FORMAT = 'mentor-evidence/1'
POLICY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'policy.json')
CHECKS = ('answerability', 'alignment', 'leakage', 'prerequisites', 'support', 'solution', 'novelty', 'contract')
RISKS = ('routine', 'clinical', 'regulated')
ITEM_LISTS = ('tier_1_faded_code_drills', 'tier_2_self_explanation_cards', 'tier_3_terminology_cards', 'faded_code_drills', 'code_cards')
# words that make a lesson clinical or regulatory whatever its evidence says: it then needs a qualified person's review
CLINICAL = re.compile(r'\b(nclex|clinical|dosage|medication|patients?|nursing|contraindicat\w*)\b', re.I)
STAMPED = re.compile(r'(19|20)\d{6}[_-]?\d{4,6}')      # a capture named by its time: a new deck each run, never a refinement

class Held(Exception):
    """The gate refused: .reasons lists every reason in plain words. Nothing is imported; a published revision stays."""
    def __init__(self, reasons):
        super().__init__('; '.join(reasons)); self.reasons = list(reasons)

def sha256(raw):
    return hashlib.sha256(raw).hexdigest()

def policy():
    with open(POLICY_FILE, encoding='utf-8') as fh: return json.load(fh)

def item_ids(doc):
    return [str(i.get('id')) for k in ITEM_LISTS for i in (doc.get(k) or []) if isinstance(i, dict) and i.get('id')]

def check(raw, evidence, mid, previous=None, published=None, why_retired=None, contract=None):
    """The gate. raw: the lesson file's bytes; evidence: its evidence document; mid: the lesson id (its file name);
    previous: the sha256 of the revision published before, if any; published: {other lesson id: name} already published;
    why_retired(raw, mid) -> '' or why the reset retired it; contract(doc, mid) -> (cards, notes), the importer itself.
    Returns {'revision', 'reason'}; raises Held."""
    why = []
    try: doc = json.loads(raw.decode('utf-8'))
    except (UnicodeDecodeError, ValueError) as x: raise Held([f'the lesson is not valid UTF-8 JSON ({str(x)[:80]})'])
    if not isinstance(doc, dict): raise Held(['the lesson is not a JSON object'])
    ev = evidence if isinstance(evidence, dict) else {}
    if ev.get('format') != FORMAT: why.append(f'the evidence is not "format": "{FORMAT}"')
    pol = policy()
    if ev.get('policy') != pol.get('id'): why.append(f'the evidence names policy {ev.get("policy")!r}, not the installed {pol.get("id")!r}')
    if ev.get('payload_sha256') != sha256(raw): why.append('the evidence was written for other bytes than this lesson file (payload_sha256 differs)')
    rev = str(ev.get('revision') or '').strip()
    if not rev: why.append('the evidence names no revision')
    srcs = ev.get('sources') if isinstance(ev.get('sources'), list) else []
    if not srcs or not all(isinstance(s, dict) and str(s.get('locator') or '').strip() and str(s.get('revision') or '').strip() for s in srcs):
        why.append('every source needs a locator and the revision that was checked; none may be missing')
    risk = ev.get('risk')
    if risk not in RISKS: why.append(f'risk must be one of {", ".join(RISKS)}')
    text = raw.decode('utf-8', 'replace')
    if risk == 'routine' and CLINICAL.search(text):
        why.append(f'the lesson mentions "{CLINICAL.search(text).group(0)}": clinical or regulated material is never routine')
    if risk in ('clinical', 'regulated'):
        rv = ev.get('review') if isinstance(ev.get('review'), dict) else {}
        by = str(rv.get('by') or '')
        if not by or not str(rv.get('qualification') or '').strip() or 'claude' in by.lower() or 'mentor' in by.lower():
            why.append(f'{risk} material needs an independent qualified person\'s review (review.by, review.qualification); Claude cannot sign it')
    items, ids = ev.get('items') if isinstance(ev.get('items'), dict) else {}, item_ids(doc)
    if not ids: why.append('the lesson has no items with ids to check')
    for iid in ids:
        it = items.get(iid)
        if not isinstance(it, dict): why.append(f'{iid}: not in the evidence (unchecked)'); continue
        if it.get('status') != 'ready':
            why.append(f'{iid}: on hold ({str(it.get("reason") or "no reason given")[:80]}); a held item stays in the draft'); continue
        checks = it.get('checks') if isinstance(it.get('checks'), dict) else {}
        missing = [c for c in CHECKS if checks.get(c) != 'pass']
        if missing: why.append(f'{iid}: checks not passed: {", ".join(missing)}')
    if STAMPED.search(mid): why.append(f'"{mid}" is named by a time: refine the lesson it repeats instead of adding a dated deck')
    name = str((doc.get('metadata') or {}).get('module_name') or '').strip().lower() if isinstance(doc.get('metadata'), dict) else ''
    for other, oname in (published or {}).items():
        if name and str(oname or '').strip().lower().replace('_', ' ') == name.replace('_', ' '):
            why.append(f'"{other}" already teaches "{oname}": publish a new revision of {other}.json instead of a second lesson')
    if previous and previous != sha256(raw) and not str((ev.get('correction') or {}).get('reason') or '').strip():
        why.append('this replaces a published revision: correction.reason must say why it changed')
    if why_retired:
        r = why_retired(raw, mid)
        if r: why.append(r)
    if contract and not why:
        try:
            n, notes = contract(doc, mid)
            if not n: why.append('the importer made no practice cards from it')
            if notes: why.append('the importer skipped parts of it: ' + '; '.join(notes[:4]))
        except (ValueError, KeyError, TypeError, AttributeError) as x: why.append(f'the importer refused it: {str(x)[:160]}')
    if why: raise Held(why)
    reason = str((ev.get('correction') or {}).get('reason') or '').strip() or ('first publication' if not previous else 'republished unchanged')
    return {'revision': rev, 'reason': reason}
