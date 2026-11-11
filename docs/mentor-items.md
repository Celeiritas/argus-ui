# Mentor items: exam-style questions (`mentor-items/1`)

An **item** is one exam-style question: multiple choice, select all that apply, drop-down, matrix, bow-tie, trend, or a case study of six linked items. This page is the contract for the file format, the scoring rules, the checker rules N1 to N8, and the functions a screen calls. The engine is `plugins/mentor/items.py` (pure functions, standard library only); `scripts/check-deck.py` calls the same functions, so there is one set of rules. There is no screen yet; the screens are built on this page.

Mentor is a study aid. Every file carries a `disclaimer` that every screen must show.

## The file

```json
{"format": "mentor-items/1",
 "title": "Tea practice items",
 "disclaimer": "Made-up practice items for tests, not advice.",
 "sources": {"S1": {"title": "A made-up tea guide", "url": "https://example.org/tea", "read": "2026-11-11"}},
 "items": [ ... ]}
```

`sources` is an object of `{id: {title, url, read}}`; `url` and `read` are required, `title` is optional. `read` is the date a person read the page (`YYYY-MM-DD`). Fields such as `org` or `page_date` may be added and are ignored.

### Fields on every item
| Field | Meaning |
|---|---|
| `id` | unique in the file; stored with answers |
| `type` | `mcq`, `sata`, `dropdown`, `matrix`, `bowtie`, `trend`, `case` |
| `status` | `unverified` (default for anything new; screens show a "not yet checked" mark), `source-checked` (a second person re-read every cited page), `retired` (hidden, never deleted) |
| `client_needs` | the test-plan area, as text (for example `Tea making` in the fixtures) |
| `ncjmm_step` | one of `recognize-cues`, `analyze-cues`, `prioritize-hypotheses`, `generate-solutions`, `take-action`, `evaluate-outcomes`; a bow-tie or a case may say `all` |
| `stem` | the question (a case has `scenario` instead) |
| `scoring` | the rule that applies: `zero_one`, `plus_minus` or `rationale` (see the table; a case has none) |
| `max_points` | a whole number, equal to what `score` can award (a case too: the sum of its items) |

Every **option, row, list, column and slot has its own `id`**. Answers are stored by id, never by position, so a screen may shuffle freely. Every option and row has a `reason` (right ones and wrong ones) and `src` (a list of ids in `sources`). Optional on any item: `subcategory`, `review_notes`.

### Which scoring each type accepts
The item says which rule applies, because the exam's rule for each type is not confirmed. A mismatch is an error (N2), never a guess.

| Type | `scoring` | Points |
|---|---|---|
| `mcq` | `zero_one` | 1 for the right option |
| `sata` | `plus_minus` | +1 per right pick, -1 per wrong pick, never below 0; max = number of right options |
| `sata` | `zero_one` | +1 per right pick, and `pick` (a number equal to the right options) is the most you may pick; more earns 0 |
| `dropdown` | `zero_one` | 1 per list |
| `dropdown` | `rationale` | as above, but each pair in `pairs` earns one point only when both lists are right; max = lists minus pairs |
| `matrix` | `zero_one` | 1 per row, one tick per row (a row with two ticks earns 0) |
| `matrix` | `plus_minus` | per row: right ticks minus wrong ticks, never below 0; max = all right ticks |
| `bowtie` | `zero_one` | 1 for each of 5 slots: 1 condition, 2 actions, 2 parameters; order inside a pair does not matter |
| `trend` | the carried format's | scores as its `answer_type` |
| `case` | none | each item on its own; total plus a score per step |

## Examples (one per type)

**mcq**
```json
{"id": "q1", "type": "mcq", "status": "unverified", "client_needs": "Tea making", "ncjmm_step": "take-action",
 "scoring": "zero_one", "max_points": 1, "stem": "Which water is best for green tea?",
 "options": [{"id": "a", "text": "Boiling water", "key": false, "reason": "...", "src": ["S1"]},
             {"id": "b", "text": "Water that has cooled a little", "key": true, "reason": "...", "src": ["S1"]}]}
```
**sata** (same shape as mcq, `"type": "sata"`, `"scoring": "plus_minus"`, several `key: true`, not all, not none). With `"scoring": "zero_one"` add `"pick": <number of right options>`.

**dropdown** (the `template` marks each list exactly once as `{list-id}`)
```json
{"type": "dropdown", "scoring": "rationale", "max_points": 2, "stem": "Complete the sentence.",
 "template": "Black tea steeps for {d1} minutes because {d2}. Serve it {d3}.",
 "dropdowns": [{"id": "d1", "options": [{"id": "a", "text": "3 to 5", "key": true, "reason": "...", "src": ["S1"]}, ...]}, ...],
 "pairs": [{"id": "p1", "of": ["d1", "d2"]}]}
```
Each list has exactly one right option. `pairs` exists only with `rationale` scoring: two different lists each, a list in one pair at most.

**matrix** (`keys` are column ids; `reason` and `src` belong to the row)
```json
{"type": "matrix", "scoring": "zero_one", "max_points": 2, "stem": "Mark what each tea needs.",
 "columns": [{"id": "hot", "text": "Hot water"}, {"id": "cool", "text": "Cooled water"}],
 "rows": [{"id": "r1", "text": "Black tea", "keys": ["hot"], "reason": "...", "src": ["S1"]}, ...]}
```
`zero_one`: exactly one key per row. `plus_minus`: one or more.

**bowtie**
```json
{"type": "bowtie", "ncjmm_step": "all", "scoring": "zero_one", "max_points": 5, "stem": "...",
 "condition": {"pick": 1, "options": [ ... ]}, "actions": {"pick": 2, "options": [ ... ]}, "parameters": {"pick": 2, "options": [ ... ]}}
```
The `pick` numbers are 1, 2, 2, and each group marks exactly that many options right.

**trend** (an exhibit, then any response format named by `answer_type`, with that format's own fields beside it)
```json
{"type": "trend", "answer_type": "mcq", "scoring": "zero_one", "max_points": 1,
 "exhibit": {"title": "Temperature log", "columns": ["Minute", "Temp"], "rows": [["0", "95"], ["5", "80"]]},
 "stem": "What does the log show?", "options": [ ... ]}
```
**case**
```json
{"id": "c1", "type": "case", "status": "unverified", "client_needs": "...", "ncjmm_step": "all", "max_points": 12,
 "scenario": "...", "chart": {"tabs": {"Notes": [{"time": "09:00", "text": "..."}]}},
 "items": [ {"id": "c1-1", "type": "sata", "ncjmm_step": "recognize-cues", ...}, ... six, one per step, in order ]}
```
Items inside a case need `id`, `type`, `ncjmm_step`, `stem`, `scoring`, `max_points` and their options; they take `status` and `client_needs` from the case. The six steps in order is the default; `"order": "free"` allows another list (each item still names a step). A case cannot contain a case. The `chart` is for the screen; the engine does not read it.

## Calling the engine
```python
import importlib.util
spec = importlib.util.spec_from_file_location('leafy_mentor_items', '<path>/plugins/mentor/items.py')
items = importlib.util.module_from_spec(spec); spec.loader.exec_module(items)
```

### `score(item, response) -> dict`
`response` is `{"picks": X}`; X depends on the type:
| Type | `picks` |
|---|---|
| `mcq`, `sata` | an option id, or a list of ids |
| `dropdown` | `{"<list id>": "<option id>"}` |
| `matrix` | `{"<row id>": "<column id>" or ["<column id>", ...]}` |
| `bowtie` | `{"condition": id or [id], "actions": [id, id], "parameters": [id, id]}` |
| `trend` | as its `answer_type` |
| `case` | `{"items": {"<item id>": <that item's response>}}` |

Returns `{"points": int, "max": int, "per_part": [...]}`; a case adds `"per_step": {step: {"points", "max"}}` (only steps that appear). Each `per_part` row:
`{"part": ..., "pick": ..., "credit": int, "correct": bool|None, "reason": ..., "note": ... (optional)}`
- A note `no picks` means the response was an object without `picks` (a note `no response` means it was not an object at all).
- `part` names where it belongs: `options`; a drop-down list id or pair id; a matrix row id; `condition`, `actions` or `parameters`; or `response` for a problem with the whole response.
- There is a row for every pick and for every right option that was missed (`pick` is `None`, `note` is `missed`, `reason` is that right option's id). `reason` is the id of the option (or, for a matrix, the row) whose `reason` the screen should show next to the pick.
- `credit` is what the row earned: +1, 0 or -1 (plus/minus). `points` = the sum of the credits, but never below 0 (and not above `max`). A rationale pair is a row of its own (`of` lists its lists) and carries the point; the two list rows then show `credit` 0 with their own `correct`. The pair row has `reason: None` and no reason of its own: the reasons to show come from the two list rows.
- A matrix row's `pick` is the list of ticked column ids.
- A case's `per_part` has one row per item: `{"part": item id, "step", "credit", "max", "per_part": [that item's rows]}`.

**Bad responses never raise.** Decided and tested: a missing or wrong-type response or `picks` scores 0 (note `no response`); an id that is not an option (or a list/row/column that does not exist) is ignored, with no credit and no penalty (note `unknown option`); a pick that is not text is ignored; a repeated pick counts once (note `repeated pick`); more picks than allowed (a bow-tie group, a one-answer question, a matrix row under `zero_one`, a `zero_one` select-all) earns nothing for that group, row or item (note `too many picks`). A broken **item** raises `items.ItemError` (a `ValueError`), because guessing would hand out wrong marks. All numbers are whole numbers.

### `to_rating(points, max, ms, hints) -> "again" | "hard" | "good" | "easy"`
Under 50 % again; 50 % up to under 100 % hard; 100 % good; 100 % with no hint (`hints == 0`) in under 120 000 ms easy (exactly 120 000 ms is good). Unknown time or hints cannot earn easy. A time of 0 or less counts as unknown too (a timer that did not run must not give a free easy), so 0 ms is good, 1 ms is easy. Not numbers, or `max <= 0`: again. The words are Mentor's own four ratings (`mentor.py` stores them as 1 to 4; the page shows Again, Hard, Good, Easy). Compared in exact fractions, so 49.9 % (499 of 1000) is again.

### `validate(item, sources=None) -> list[str]`
Every problem as one plain sentence; empty means fine. Pass the file's `sources` to check `src` ids too: **an importer must pass them**, or a dangling `src` is accepted. `validate_doc(doc)` checks a whole file and returns `(item id or None, rule, sentence)`. `max_points(item)` gives what `score` can award.

## Checker rules N1 to N8
`python scripts/check-deck.py file.json` runs these on any file whose `format` is `mentor-items/1` (lesson and course rules are untouched). Messages read `file: item id: ERROR Nx sentence`.

| Rule | What it refuses |
|---|---|
| N1 | the file: wrong `format`, no `disclaimer`, no items |
| N2 | an item's own fields and shape: id, type, status, `client_needs`, `ncjmm_step`, stem, `scoring` that does not fit the type, no `max_points`, a template that does not mark each list once, a trend without exhibit or `answer_type` |
| N3 | ids: two items with one id in the file, or two items of one case with the same id (answers are stored by item id); an option, list, row, column or pair with no id or a repeated one |
| N4 | an option or row with no `reason` |
| N5 | an option or row with no `src`; a `src` id that is not in `sources`; a source with no `url` or no `read` date |
| N6 | the answer key: no right answer; a select-all with all options right; a multiple-choice item without exactly one; a bow-tie group whose right options differ from its `pick`; a matrix key outside the columns, or two keys under `zero_one`; a `zero_one` select-all whose `pick` is not the number of right options |
| N7 | `max_points` that is not what `score` can award |
| N8 | a case that does not have 6 items in the order of the six steps (unless `"order": "free"`), a case in a case |

## What changed from the first sample shape
The six draft samples (`mentor-items/0-draft`) are converted, not kept. Changes and why:
- `rationale` on an option is now `reason`: `rationale` is also the name of a scoring rule.
- Drop-down lists are a **list** `dropdowns: [{id, options}]` (the draft used an object) so order is stable, and options have ids (the draft's had none). `pairs` for the rationale rule are explicit.
- Matrix `key` (a column's text) is now `keys`, a list of column ids; columns are `{id, text}`. This gives plus/minus rows, and ids that do not change when text is reworded.
- Bow-tie and drop-down options have ids; the bow-tie's `ncjmm_step` is `all`, not free text.
- A case's items use `ncjmm_step` (the draft: `step`) and carry `max_points`.
- A trend states its response format as `answer_type`; the draft implied it.
- `sources` stay an object keyed by id; `read` is a real `YYYY-MM-DD` date.
