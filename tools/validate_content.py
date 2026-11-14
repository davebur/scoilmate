"""Validate the draft editorial contract; not an educational accuracy check."""
import json
from pathlib import Path


def validate(data):
    def need(ok, message):
        if not ok:
            raise ValueError(message)
    need(data['format_version'] == 1 and data['app'] == 'ScoilMate', 'format/app')
    need(data['status'] == 'draft' and data['review_status'] == 'unreviewed', 'draft warning')
    lessons = data['lessons']; questions = data['questions']
    for rows in (lessons, questions):
        need(len({x['id'] for x in rows}) == len(rows), 'duplicate id')
        for x in rows:
            need(type(x['version']) is int and x['version'] > 0, 'version')
            need(x['status'] == 'draft' and x['review_status'] == 'unreviewed', 'review status')
            need(x['subject'] in ('english','gaeilge','history'), 'subject')
            need(x['track'] in (('T1','T2') if x['subject']=='gaeilge' else ('general',)), 'track')
    by_id = {x['id']: x for x in lessons}
    for lesson in lessons:
        need(bool(lesson['title'].strip()) and bool(lesson['body'].strip()), 'lesson content')
    for q in questions:
        opts = q['options']; keys = [o['id'] for o in opts]
        need(len(opts) == 4 and len(set(keys)) == 4, 'option keys')
        need(len({o['text'].strip() for o in opts}) == 4, 'option text')
        need(q['correct_option_id'] in keys, 'answer reference')
        need(bool(q['prompt'].strip()) and bool(q['explanation'].strip()), 'question content')
        need(len(q['hints']) >= 2 and all(isinstance(h,str) and h.strip() for h in q['hints']), 'hints')
        need(q['levels'] == (['common'] if q['subject']=='history' else ['ordinary','higher']), 'levels')
        need(q['language'] == ('ga' if q['subject']=='gaeilge' else 'en'), 'language')
        need(all(type(y) is int and y in (1,2,3) for y in q['year_guidance']), 'year')
        need(q['outcome_mapping_status'] == 'candidate_unreviewed', 'mapping')
        lesson = by_id.get(q['help_lesson_id'])
        need(lesson is not None and (lesson['subject'],lesson['track']) == (q['subject'],q['track']), 'help reference')
    need(len(questions) == 9 and all(sum(q['subject']==s for q in questions)==3 for s in ('english','gaeilge','history')), 'sample coverage')
    return len(lessons), len(questions)


if __name__ == '__main__':
    path = Path(__file__).resolve().parents[1] / 'content/draft-samples.json'
    counts = validate(json.loads(path.read_text()))
    print(f'PASS: {counts[0]} lessons, {counts[1]} MCQs; keys, links, draft status and eligibility valid.')
