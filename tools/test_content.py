import copy
import json
from pathlib import Path
import unittest
from validate_content import validate

class ContentTests(unittest.TestCase):
    def setUp(self):
        self.data=json.loads((Path(__file__).resolve().parents[1]/'content/draft-samples.json').read_text())
    def test_valid(self):
        self.assertEqual(validate(self.data),(9,9))
    def test_reject_mutations(self):
        mutations=[lambda d:d['questions'][0].update(correct_option_id='Z'),
                   lambda d:d['questions'][0].update(help_lesson_id='missing'),
                   lambda d:d['questions'][0].update(track='T1'),
                   lambda d:d['questions'][6].update(levels=['higher']),
                   lambda d:d['questions'][0].update(status='published'),
                   lambda d:d['questions'][1].update(id=d['questions'][0]['id'])]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                d=copy.deepcopy(self.data); mutate(d)
                with self.assertRaises(ValueError): validate(d)
