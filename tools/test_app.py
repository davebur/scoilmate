"""HTTP tests for the practice slice. Run with the project venv:
.venv/bin/python -m unittest discover -s tools -p 'test_*.py' -v
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
_tmp = tempfile.TemporaryDirectory()
os.environ['SCOILMATE_FEEDBACK_FILE'] = str(Path(_tmp.name) / 'feedback.jsonl')

try:
    from fastapi.testclient import TestClient
    from scoilmate import app as appmod
    from scoilmate.content import load
except ImportError as exc:  # system python without the venv
    raise unittest.SkipTest(f'preview dependencies unavailable: {exc}')


class PracticeTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(appmod.app)
        self.c = load()
        appmod.FEEDBACK_FILE.unlink(missing_ok=True)

    def first(self, slug='english'):
        return self.c.strand_questions(self.c.strands[slug])[0]

    def test_pages_render(self):
        for path in ['/', '/practice', '/health', '/practice/english', '/practice/gaeilge-t2',
                     '/practice/gaeilge-t1', '/practice/history', '/practice/english/q/1',
                     '/practice/english/lesson/lesson-simile', '/practice/english/summary']:
            with self.subTest(path=path):
                r = self.client.get(path)
                self.assertEqual(r.status_code, 200)
        self.assertIn('Content-Security-Policy', self.client.get('/').headers)

    def test_unknown_routes_404(self):
        for path in ['/practice/maths', '/practice/english/q/0', '/practice/english/q/99',
                     '/practice/english/lesson/lesson-primary']:  # lesson from another subject
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)

    def test_question_page_never_leaks_key_or_explanation(self):
        for slug, strand in self.c.strands.items():
            for n, q in enumerate(self.c.strand_questions(strand), 1):
                html = self.client.get(f'/practice/{slug}/q/{n}?hints=9').text
                self.assertNotIn(q['explanation'], html)
                self.assertNotIn('correct', html.lower().replace('check answer', ''))
                for hint in q['hints']:
                    self.assertIn(hint, html)  # all hints revealed when requested
        html = self.client.get('/practice/english/q/1').text
        self.assertNotIn(self.first()['hints'][0], html)  # none by default

    def test_grading_and_summary(self):
        q = self.first()
        wrong = next(o['id'] for o in q['options'] if o['id'] != q['correct_option_id'])
        r = self.client.post('/practice/english/q/1', data={'option': q['correct_option_id'], 'hints_used': '0'})
        self.assertIn('Correct', r.text)
        self.assertIn(q['explanation'], r.text)
        r = self.client.post('/practice/english/q/2', data={'option': 'A', 'hints_used': '2'})
        self.assertEqual(r.status_code, 200)
        # Retry of q1 with the wrong answer must not overwrite the first result
        r = self.client.post('/practice/english/q/1', data={'option': wrong, 'hints_used': '0'})
        self.assertIn('Not this time', r.text)
        self.assertIn('first answer is the one that counts', r.text)
        s = self.client.get('/practice/english/summary').text
        self.assertIn('<b>2</b> of 3 tried', s)
        self.assertIn('<b>1</b> correct on your own', s)

    def test_invalid_and_missing_answers(self):
        self.assertEqual(self.client.post('/practice/english/q/1', data={'option': 'Z'}).status_code, 400)
        r = self.client.post('/practice/english/q/1', data={})
        self.assertEqual(r.status_code, 200)
        self.assertIn('Choose an answer', r.text)

    def test_tampered_cookie_ignored(self):
        self.client.cookies.set(appmod.COOKIE, 'AAAA' + 'x' * 40, path='/practice')
        self.assertIn('<b>0</b> of 3 tried', self.client.get('/practice/english/summary').text)

    def test_reset(self):
        q = self.first()
        self.client.post('/practice/english/q/1', data={'option': q['correct_option_id']})
        r = self.client.post('/practice/english/reset', follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        self.assertIn('Start questions', r.text)

    def test_rating_question_and_lesson(self):
        q = self.first()
        r = self.client.post('/practice/english/rate', data={
            'item_type': 'question', 'item_id': q['id'], 'rating': 'down', 'reason': 'unclear', 'n': '1'},
            follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertTrue(r.headers['location'].startswith('/practice/english/q/2'))
        # duplicate rating from the same browser is not recorded twice
        self.client.post('/practice/english/rate', data={
            'item_type': 'question', 'item_id': q['id'], 'rating': 'up', 'n': '1'})
        self.client.post('/practice/english/rate', data={
            'item_type': 'lesson', 'item_id': 'lesson-simile', 'rating': 'up', 'n': '0'})
        rows = [json.loads(x) for x in appmod.FEEDBACK_FILE.read_text().splitlines()]
        self.assertEqual([(x['type'], x['id'], x['rating'], x['reason']) for x in rows],
                         [('question', q['id'], 'down', 'unclear'), ('lesson', 'lesson-simile', 'up', None)])
        self.assertEqual(set(rows[0]), {'at', 'type', 'id', 'version', 'rating', 'reason'})  # nothing identifying
        self.assertIn('you rated this note', self.client.get('/practice/english/lesson/lesson-simile').text)

    def test_rating_rejects_bad_input(self):
        q = self.first()
        bad = [{'item_type': 'question', 'item_id': q['id'], 'rating': 'meh'},
               {'item_type': 'question', 'item_id': q['id'], 'rating': 'up', 'reason': '<script>'},
               {'item_type': 'other', 'item_id': q['id'], 'rating': 'up'},
               {'item_type': 'question', 'item_id': 'q-primary', 'rating': 'up'}]  # wrong subject
        for data in bad:
            with self.subTest(data=data):
                self.assertIn(self.client.post('/practice/english/rate', data=data).status_code, (400, 404))
        self.assertFalse(appmod.FEEDBACK_FILE.exists())


if __name__ == '__main__':
    unittest.main()
