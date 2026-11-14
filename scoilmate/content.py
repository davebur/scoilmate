"""Load the draft content file and expose learner-safe views.

Answer keys and explanations never leave this module except through
`grade()`, which runs on the server after the learner submits.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT_FILE = ROOT / 'content' / 'draft-samples.json'

SUBJECTS = {
    'english': {'name': 'English', 'lang': 'en'},
    'gaeilge': {'name': 'Gaeilge', 'lang': 'ga'},
    'history': {'name': 'History', 'lang': 'en'},
}
TRACK_NAMES = {'general': '', 'T1': 'T1 (Teanga 1)', 'T2': 'T2 (Teanga 2)'}


@dataclass(frozen=True)
class Strand:
    """One practice area: a subject plus (for Gaeilge) a track."""
    subject: str
    track: str

    @property
    def slug(self) -> str:
        return self.subject if self.track == 'general' else f'{self.subject}-{self.track.lower()}'

    @property
    def title(self) -> str:
        name = SUBJECTS[self.subject]['name']
        return f'{name} {TRACK_NAMES[self.track]}'.strip()

    @property
    def lang(self) -> str:
        return SUBJECTS[self.subject]['lang']


class Content:
    def __init__(self, data: dict):
        sys.path.insert(0, str(ROOT / 'tools'))
        try:
            from validate_content import validate
        finally:
            sys.path.pop(0)
        validate(data)
        self.lessons = {x['id']: x for x in data['lessons']}
        self.questions = {x['id']: x for x in data['questions']}
        order = []
        for q in data['questions']:
            s = Strand(q['subject'], q['track'])
            if s not in order:
                order.append(s)
        order.sort(key=lambda s: (list(SUBJECTS).index(s.subject), s.track))
        self.strands = {s.slug: s for s in order}

    def strand_questions(self, strand: Strand) -> list[dict]:
        return [q for q in self.questions.values()
                if (q['subject'], q['track']) == (strand.subject, strand.track)]

    def strand_lessons(self, strand: Strand) -> list[dict]:
        return [x for x in self.lessons.values()
                if (x['subject'], x['track']) == (strand.subject, strand.track)]

    @staticmethod
    def public_question(q: dict, hints_shown: int = 0) -> dict:
        """Learner-safe pre-submit view: no key, no explanation, only revealed hints."""
        hints_shown = max(0, min(hints_shown, len(q['hints'])))
        return {
            'id': q['id'], 'version': q['version'], 'prompt': q['prompt'],
            'options': [{'id': o['id'], 'text': o['text']} for o in q['options']],
            'hints': q['hints'][:hints_shown], 'hints_total': len(q['hints']),
            'help_lesson_id': q['help_lesson_id'],
        }

    def grade(self, question_id: str, chosen: str) -> dict:
        q = self.questions[question_id]
        valid = {o['id'] for o in q['options']}
        if chosen not in valid:
            raise ValueError('invalid option')
        correct = q['correct_option_id']
        texts = {o['id']: o['text'] for o in q['options']}
        return {
            'correct': chosen == correct, 'chosen': chosen, 'chosen_text': texts[chosen],
            'correct_option_id': correct, 'correct_text': texts[correct],
            'explanation': q['explanation'],
        }


@lru_cache(maxsize=1)
def load(path: Path = CONTENT_FILE) -> Content:
    return Content(json.loads(path.read_text(encoding='utf-8')))
