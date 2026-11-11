"""Exam-style items without a screen: scoring, ratings and the rules N1-N8 (plugins/mentor/items.py, docs/mentor-items.md).

    python3 tests/items_test.py -v        (tests/run.sh runs it under "== mentor items")

Pure functions and the checker over made-up tea fixtures; nothing outside a temporary folder is touched."""
import copy, importlib.util, json, os, subprocess, sys, unittest

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location('leafy_mentor_items', os.path.join(R, 'plugins', 'mentor', 'items.py'))
it = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(it)
FIX = os.path.join(R, 'tests', 'deck-fixtures')
def load(name):
    with open(os.path.join(FIX, name), encoding='utf-8') as f: return json.load(f)
GOOD = load('good-items.json')
ITEMS = {i['id']: i for i in GOOD['items']}

def pts(item_id, picks):
    r = it.score(ITEMS[item_id], {'picks': picks})
    return r['points'], r['max']

class Scoring(unittest.TestCase):
    def test_mcq(self):
        for picks, want in [('b', 1), (['b'], 1), ('a', 0), ('zz', 0), ([], 0), (['b', 'a'], 0), (['b', 'b'], 1), (None, 0), (7, 0), ({'x': 1}, 0)]:
            with self.subTest(picks=picks): self.assertEqual(pts('tea-mcq', picks), (want, 1))

    def test_sata_plus_minus(self):
        for name, picks, want in [
            ('all right', ['a', 'b', 'c'], 3), ('all wrong', ['d', 'e'], 0), ('nothing', [], 0),
            ('right picks plus one wrong', ['a', 'b', 'c', 'd'], 2), ('one right one wrong', ['a', 'd'], 0),
            ('never below zero', ['d', 'e', 'a'], 0), ('everything', ['a', 'b', 'c', 'd', 'e'], 1),
            ('unknown id ignored', ['a', 'nope'], 1), ('repeat counts once', ['a', 'a'], 1), ('non-text pick ignored', ['a', 5, None], 1),
            ('bare text', 'a', 1)]:
            with self.subTest(name): self.assertEqual(pts('tea-sata', picks), (want, 3))

    def test_sata_zero_one_with_a_pick_count(self):
        for picks, want in [(['a', 'b', 'c'], 3), (['a', 'd', 'e'], 1), (['a', 'b', 'c', 'd'], 0), (['a'], 1), ([], 0)]:
            with self.subTest(picks=picks): self.assertEqual(pts('tea-sata-pick', picks), (want, 3))

    def test_dropdown_zero_one(self):
        for picks, want in [({'d1': 'a', 'd2': 'a', 'd3': 'a'}, 3), ({'d1': 'a', 'd2': 'b', 'd3': 'a'}, 2), ({}, 0),
                            ({'d1': ['a', 'b'], 'd2': 'a', 'd3': 'a'}, 2), ({'d1': 'zz', 'd2': 'a', 'd3': 'a'}, 2), ({'zz': 'a'}, 0)]:
            with self.subTest(picks=picks): self.assertEqual(pts('tea-drop-01', picks), (want, 3))

    def test_dropdown_pair_needs_both_halves(self):
        for name, picks, want in [('both', {'d1': 'a', 'd2': 'a'}, 1), ('first only', {'d1': 'a', 'd2': 'b'}, 0),
                                  ('second only', {'d1': 'b', 'd2': 'a'}, 0), ('neither', {'d1': 'b', 'd2': 'b'}, 0),
                                  ('the unpaired list alone', {'d3': 'a'}, 1), ('everything', {'d1': 'a', 'd2': 'a', 'd3': 'a'}, 2)]:
            with self.subTest(name): self.assertEqual(pts('tea-drop-rationale', picks), (want, 2))
        rows = it.score(ITEMS['tea-drop-rationale'], {'picks': {'d1': 'a', 'd2': 'a'}})['per_part']
        self.assertEqual([r['credit'] for r in rows if r['part'] == 'p1'], [1])
        self.assertEqual([r['credit'] for r in rows if r['part'] in ('d1', 'd2')], [0, 0])     # the pair carries the point

    def test_matrix_one_tick_per_row(self):
        for name, picks, want in [('all right', {'r1': 'hot', 'r2': 'cool', 'r3': 'hot'}, 3), ('lists work', {'r1': ['hot']}, 1),
                                  ('two ticks in a row', {'r1': ['hot', 'cool'], 'r2': 'cool'}, 1), ('wrong column', {'r1': 'milk'}, 0),
                                  ('unknown column', {'r1': 'nope'}, 0), ('unknown row', {'zz': 'hot'}, 0), ('empty', {}, 0)]:
            with self.subTest(name): self.assertEqual(pts('tea-matrix', picks), (want, 3))
        row = [r for r in it.score(ITEMS['tea-matrix'], {'picks': {'r1': ['hot', 'cool']}})['per_part'] if r['part'] == 'r1'][0]
        self.assertEqual((row['credit'], row['note']), (0, 'too many picks'))

    def test_matrix_plus_minus_per_row(self):
        for name, picks, want in [('all right', {'r1': 'hot', 'r2': 'cool', 'r3': ['hot', 'milk']}, 4), ('half of the multi row', {'r3': 'milk'}, 1),
                                  ('right plus wrong in a row', {'r3': ['hot', 'milk', 'cool']}, 1), ('wrong never goes below 0 and not into other rows', {'r1': ['cool', 'milk'], 'r2': 'cool'}, 1)]:
            with self.subTest(name): self.assertEqual(pts('tea-matrix-multi', picks), (want, 4))

    def test_bowtie(self):
        full = {'condition': 'a', 'actions': ['a', 'b'], 'parameters': ['a', 'b']}
        self.assertEqual(pts('tea-bowtie', full), (5, 5))
        self.assertEqual(pts('tea-bowtie', {**full, 'actions': ['b', 'a']}), (5, 5))             # order inside a pair does not matter
        self.assertEqual(pts('tea-bowtie', {**full, 'actions': ['a', 'c']}), (4, 5))
        self.assertEqual(pts('tea-bowtie', {**full, 'condition': 'b'}), (4, 5))
        self.assertEqual(pts('tea-bowtie', {**full, 'parameters': ['a']}), (4, 5))
        self.assertEqual(pts('tea-bowtie', {**full, 'actions': ['a', 'b', 'c']}), (3, 5))        # too many: that group earns nothing
        self.assertEqual(pts('tea-bowtie', {**full, 'actions': ['a', 'a']}), (4, 5))             # a repeat is one pick
        self.assertEqual(pts('tea-bowtie', {'condition': ['a', 'b']}), (0, 5))
        self.assertEqual(pts('tea-bowtie', {}), (0, 5))

    def test_trend_scores_as_its_response_format(self):
        self.assertEqual(pts('tea-trend', 'a'), (1, 1))
        self.assertEqual(pts('tea-trend', 'b'), (0, 1))

    def test_case_scores_item_by_item_and_per_step(self):
        case = ITEMS['tea-case']
        self.assertEqual(it.score(case, {'items': {}})['points'], 0)
        resp = {'items': {'tea-case-1': {'picks': ['a', 'b', 'c']}, 'tea-case-3': {'picks': 'b'}, 'tea-case-5': {'picks': 'b'},
                          'tea-case-2': {'picks': {'d1': 'a', 'd2': 'a', 'd3': 'a'}}}}
        r = it.score(case, resp)
        self.assertEqual((r['points'], r['max']), (3 + 2 + 1 + 1, case['max_points']))
        self.assertEqual(list(r['per_step']), list(it.STEPS))
        self.assertEqual(r['per_step']['recognize-cues'], {'points': 3, 'max': 3})
        self.assertEqual([p['part'] for p in r['per_part']], [f'tea-case-{n}' for n in range(1, 7)])
        self.assertEqual(it.score(case, None)['points'], 0)
        self.assertEqual(it.score(case, {'items': 'nonsense'})['points'], 0)

    def test_bad_responses_never_raise(self):
        for item in GOOD['items']:
            for resp in (None, 5, 'x', [], {}, {'picks': None}, {'picks': 5}, {'picks': [[]]}, {'picks': {'a': {'b': 1}}}, {'picks': {'condition': [{}]}},
                         {'picks': [None, {}]}, {'items': 5}, {'items': {'x': 1}}, {'picks': float('nan')}):
                with self.subTest(item=item['id'], resp=str(resp)):
                    r = it.score(item, resp)
                    self.assertEqual(r['points'], 0)
                    self.assertIsInstance(r['points'], int)

    def test_empty_response_says_so(self):
        notes = [p.get('note') for p in it.score(ITEMS['tea-mcq'], None)['per_part']]
        self.assertIn('no response', notes)

    def test_points_are_whole_numbers(self):
        r = it.score(ITEMS['tea-sata'], {'picks': ['a', 'b', 'c', 'd']})
        self.assertIsInstance(r['points'], int); self.assertIsInstance(r['max'], int)

    def test_per_part_names_the_reason_to_show(self):
        rows = it.score(ITEMS['tea-sata'], {'picks': ['a', 'd']})['per_part']
        self.assertEqual([(r['pick'], r['credit'], r['correct'], r['reason']) for r in rows if r['pick']], [('a', 1, True, 'a'), ('d', -1, False, 'd')])
        self.assertEqual([r['reason'] for r in rows if r['pick'] is None and r.get('note') == 'missed'], ['b', 'c'])

    def test_a_broken_item_is_an_error(self):
        bad = copy.deepcopy(ITEMS['tea-sata']); bad['scoring'] = 'rationale'
        with self.assertRaises(it.ItemError): it.score(bad, {'picks': ['a']})
        with self.assertRaises(it.ItemError): it.score('nope', {})

    def test_max_points_matches_the_most_score_can_award(self):
        for item in GOOD['items']:
            self.assertEqual(it.max_points(item), item['max_points'], item['id'])
        perfect = {'tea-mcq': 'b', 'tea-sata': ['a', 'b', 'c']}
        for k, v in perfect.items(): self.assertEqual(pts(k, v), (ITEMS[k]['max_points'],) * 2)

class Rating(unittest.TestCase):
    def test_table(self):
        for name, args, want in [
            ('0 %', (0, 10, 5000, 0), 'again'), ('49.9 %', (499, 1000, 5000, 0), 'again'), ('just under half', (4, 9, 1, 0), 'again'),
            ('50 %', (5, 10, 5000, 0), 'hard'), ('99 %', (99, 100, 5000, 0), 'hard'), ('100 % no hint fast', (3, 3, 119_999, 0), 'easy'),
            ('100 % at 120 000 ms', (3, 3, 120_000, 0), 'good'), ('100 % slow', (3, 3, 300_000, 0), 'good'),
            ('100 % with a hint', (3, 3, 1000, 1), 'good'), ('100 % unknown time', (3, 3, None, 0), 'good'), ('100 % unknown hints', (3, 3, 1000, None), 'good'),
            ('nothing to score', (0, 0, 1, 0), 'again'), ('negative max', (1, -1, 1, 0), 'again'), ('not numbers', ('a', 'b', 1, 0), 'again'),
            ('more than max counts as full', (5, 3, 1000, 0), 'easy'), ('negative points', (-2, 3, 1000, 0), 'again'),
            ('bool is not a number', (True, True, 1, 0), 'again'), ('nan', (float('nan'), 3, 1, 0), 'again')]:
            with self.subTest(name): self.assertEqual(it.to_rating(*args), want)
        self.assertEqual(it.RATINGS, ('again', 'hard', 'good', 'easy'))

class Rules(unittest.TestCase):
    def rules(self, doc): return sorted({r for _, r, _ in it.validate_doc(doc)})

    def test_the_good_fixture_is_clean_and_covers_every_type(self):
        self.assertEqual(it.validate_doc(GOOD), [])
        self.assertEqual({i['type'] for i in GOOD['items']}, set(it.TYPES))
        self.assertEqual({i['scoring'] for i in GOOD['items'] if 'scoring' in i}, {'zero_one', 'plus_minus', 'rationale'})
        for i in GOOD['items']: self.assertEqual(it.validate(i, GOOD['sources']), [], i['id'])

    def test_each_bad_fixture_fires_its_rule(self):
        for n in range(1, 9):
            doc = load(f'bad-items-n{n}.json')
            with self.subTest(rule=f'N{n}'): self.assertIn(f'N{n}', self.rules(doc))

    def mut(self, fn):
        d = copy.deepcopy(GOOD); fn(d); return d

    def test_single_breaks(self):
        cases = [
            ('N1', lambda d: d.__setitem__('format', 'mentor-items/0')), ('N1', lambda d: d.pop('disclaimer')), ('N1', lambda d: d.__setitem__('items', [])),
            ('N2', lambda d: d['items'][0].pop('client_needs')), ('N2', lambda d: d['items'][0].__setitem__('ncjmm_step', 'guess')),
            ('N2', lambda d: d['items'][0].__setitem__('type', 'essay')), ('N2', lambda d: d['items'][0].pop('stem')),
            ('N2', lambda d: d['items'][0].pop('max_points')), ('N2', lambda d: d['items'][7].pop('exhibit')),
            ('N2', lambda d: d['items'][2].__setitem__('template', 'no marks')), ('N2', lambda d: d['items'][8].__setitem__('scoring', 'zero_one')),
            ('N2', lambda d: d['items'][3].__setitem__('pairs', [])), ('N2', lambda d: d['items'][2].pop('pairs')),
            ('N3', lambda d: d['items'][1]['options'][0].pop('id')), ('N3', lambda d: d['items'][4]['rows'][1].__setitem__('id', 'r1')),
            ('N3', lambda d: d['items'][8]['items'][0].__setitem__('id', 'tea-mcq')),
            ('N4', lambda d: d['items'][4]['rows'][0].pop('reason')), ('N4', lambda d: d['items'][6]['actions']['options'][3].__setitem__('reason', ' ')),
            ('N5', lambda d: d['items'][0]['options'][0].pop('src')), ('N5', lambda d: d['sources']['S1'].pop('url')),
            ('N5', lambda d: d['sources'].clear()),
            ('N6', lambda d: d['items'][0]['options'][0].__setitem__('key', True)), ('N6', lambda d: d['items'][6]['actions']['options'][2].__setitem__('key', True)),
            ('N6', lambda d: d['items'][4]['rows'][0].__setitem__('keys', ['hot', 'cool'])), ('N6', lambda d: d['items'][9].__setitem__('pick', 2)),
            ('N6', lambda d: [o.__setitem__('key', False) for o in d['items'][1]['options']]),
            ('N7', lambda d: d['items'][1].__setitem__('max_points', 4)), ('N7', lambda d: d['items'][2].__setitem__('max_points', 3)),
            ('N7', lambda d: d['items'][8].__setitem__('max_points', 1)),
            ('N8', lambda d: d['items'][8]['items'].pop()), ('N8', lambda d: d['items'][8]['items'].append(copy.deepcopy(d['items'][8]['items'][0]))),
        ]
        for rule, fn in cases:
            with self.subTest(rule=rule, n=cases.index((rule, fn))): self.assertIn(rule, self.rules(self.mut(fn)))

    def test_a_case_may_say_its_order_is_free(self):
        d = copy.deepcopy(GOOD); c = [i for i in d['items'] if i['type'] == 'case'][0]
        c['items'].reverse(); c['order'] = 'free'
        self.assertEqual(it.validate_doc(d), [])
        it.score(c, {})

    def test_duplicate_ids_across_the_file(self):
        d = copy.deepcopy(GOOD); d['items'][1]['id'] = d['items'][0]['id']
        self.assertIn('N3', self.rules(d))

    def test_validate_gives_sentences_and_never_raises_on_junk(self):
        for junk in (None, 5, 'x', [], {}, {'type': 'mcq'}, {'type': 'bowtie', 'condition': 5}, {'type': 'matrix', 'rows': [1], 'columns': 3},
                     {'type': 'dropdown', 'dropdowns': [5], 'template': 5}, {'type': 'case', 'items': [None]}, {'type': 'trend', 'answer_type': 'sata'}):
            with self.subTest(junk=str(junk)):
                out = it.validate(junk)
                self.assertTrue(out); self.assertTrue(all(isinstance(s, str) and s.endswith('.') for s in out))
        for junk in (None, 5, [], {}, {'items': [5]}, {'sources': 5, 'items': [{}]}):
            it.validate_doc(junk)

    def test_retired_items_are_still_checked(self):
        d = copy.deepcopy(GOOD); d['items'][0]['status'] = 'retired'; d['items'][0]['options'][0].pop('reason')
        self.assertIn('N4', self.rules(d))

class Checker(unittest.TestCase):
    def run_checker(self, name):
        p = subprocess.run([sys.executable, '-B', os.path.join(R, 'scripts', 'check-deck.py'), os.path.join(FIX, name)], capture_output=True, text=True, encoding='utf-8')
        return p.returncode, p.stdout

    def test_good_file_passes_and_each_bad_file_is_refused(self):
        self.assertEqual(self.run_checker('good-items.json')[0], 0)
        for n in range(1, 9):
            code, out = self.run_checker(f'bad-items-n{n}.json')
            with self.subTest(rule=f'N{n}'): self.assertEqual(code, 1); self.assertIn(f'ERROR N{n} ', out)

if __name__ == '__main__':
    unittest.main()
