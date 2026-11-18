"""Mentor's exact comparator (4.55, plugins/mentor/compare.py): layout is forgiven, meaning never is.

    python3 tests/mentor_compare_test.py -v        (tests/run.sh runs it under "== mentor model")"""
import importlib.util, os, unittest

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location('leafy_mentor_compare', os.path.join(R, 'plugins', 'mentor', 'compare.py'))
c = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(c)

class Compare(unittest.TestCase):
    def test_sign_kept(self):
        self.assertFalse(c.same_value('-12', ['12'])); self.assertFalse(c.same_value('12', ['-12']))
    def test_operator_kept(self):
        self.assertFalse(c.same_value('a - b', ['a + b']))
    def test_order_kept(self):
        self.assertFalse(c.same_value('2 1', ['1 2'])); self.assertFalse(c.same_value('[2, 1]', ['[1, 2]']))
    def test_space_tolerant(self):
        self.assertTrue(c.same_value('[1,2]', ['[1, 2]'])); self.assertTrue(c.same_value(' total=6 ', ['total = 6']))
        self.assertTrue(c.same_value('1\n2\n3', ['1 2 3']))
    def test_unicode(self):
        self.assertTrue(c.same_value('猫', ['猫'])); self.assertFalse(c.same_value('', ['猫'])); self.assertFalse(c.same_value('犬', ['猫']))
    def test_unicode_form(self):
        # 'e' + a combining accent (some keyboards) equals the composed é; a plain e does not
        self.assertTrue(c.same_value('café', ['café'])); self.assertFalse(c.same_value('cafe', ['café']))
    def test_variants(self):
        self.assertTrue(c.same_value('None', ['None', 'none'])); self.assertFalse(c.same_value('NONE', ['None', 'none']))
    def test_empty_accepted_never_matches(self):
        self.assertFalse(c.same_value('x', ['', '  ']))

if __name__ == '__main__':
    unittest.main()
