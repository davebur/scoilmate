"""Content storage: import the editorial JSON into versioned rows and serve learner-safe views.

Answer keys and explanations never leave this module except through `grade()`, which runs on
the server after the learner submits.
"""
from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import ROOT, settings
from .db import utcnow
from .models import ContentItem, ContentRating, ContentVersion, Topic

CONTENT_FILE = ROOT / 'content' / 'draft-samples.json'

SUBJECTS = {
    'english': {'name': 'English', 'lang': 'en'},
    'gaeilge': {'name': 'Gaeilge', 'lang': 'ga'},
    'history': {'name': 'History', 'lang': 'en'},
}
TRACK_NAMES = {'general': '', 'T1': 'T1 (Teanga 1)', 'T2': 'T2 (Teanga 2)'}
FEEDBACK_REASONS = {
    'unclear': 'Confusing or unclear',
    'wrong': 'I think something is wrong',
    'too_easy': 'Too easy',
    'too_hard': 'Too hard',
    'helpful': 'Really helpful',
}
# Fields copied from the editorial JSON into the immutable version body.
QUESTION_FIELDS = ('prompt', 'options', 'correct_option_id', 'explanation', 'hints', 'help_lesson_id',
                   'language', 'levels', 'year_guidance', 'strand', 'outcome_mapping_status', 'provenance')
LESSON_FIELDS = ('title', 'body')


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
        return f"{SUBJECTS[self.subject]['name']} {TRACK_NAMES[self.track]}".strip()

    @property
    def lang(self) -> str:
        return SUBJECTS[self.subject]['lang']

    @classmethod
    def from_slug(cls, slug: str) -> 'Strand | None':
        for subject in SUBJECTS:
            for track in (('T1', 'T2') if subject == 'gaeilge' else ('general',)):
                if cls(subject, track).slug == slug:
                    return cls(subject, track)
        return None


def all_strands() -> list[Strand]:
    return [Strand('english', 'general'), Strand('gaeilge', 'T1'), Strand('gaeilge', 'T2'),
            Strand('history', 'general')]


def canonical(body: dict) -> str:
    return json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


def validate_question_body(body: dict):
    """Structural checks for one question version (shared by import and the admin editor)."""
    def need(ok, message):
        if not ok:
            raise ValueError(message)
    opts = body.get('options') or []
    keys = [o.get('id') for o in opts]
    need(str(body.get('prompt', '')).strip(), 'Question prompt is required')
    need(3 <= len(opts) <= 5 and len(set(keys)) == len(keys), 'Give 3-5 options with distinct letters')
    need(all(str(o.get('text', '')).strip() for o in opts), 'Every option needs text')
    need(len({o['text'].strip() for o in opts}) == len(opts), 'Options must be different')
    need(body.get('correct_option_id') in keys, 'The correct answer must be one of the options')
    need(str(body.get('explanation', '')).strip(), 'An explanation is required')
    hints = body.get('hints') or []
    need(1 <= len(hints) <= 3 and all(isinstance(h, str) and h.strip() for h in hints), 'Give 1-3 hints')


# ---------- import ----------

def _topic_for(db: Session, subject: str, track: str, slug: str, title: str, ordinal: int) -> Topic:
    topic = db.scalar(select(Topic).where(Topic.slug == slug))
    if topic is None:
        topic = Topic(slug=slug, subject=subject, track=track, title=title, ordinal=ordinal)
        db.add(topic)
        db.flush()
    elif (topic.subject, topic.track) != (subject, track):
        raise ValueError(f'topic {slug} belongs to another subject/track')
    return topic


def _add_version(db: Session, kind: str, slug: str, topic: Topic, version: int, title: str,
                 body: dict, status: str = 'draft') -> bool:
    item = db.scalar(select(ContentItem).where(ContentItem.slug == slug))
    if item is None:
        item = ContentItem(slug=slug, kind=kind, topic_id=topic.id)
        db.add(item)
        db.flush()
    elif item.kind != kind or item.topic_id != topic.id:
        raise ValueError(f'{slug}: kind/topic differs from the stored item')
    existing = db.scalar(select(ContentVersion).where(ContentVersion.item_id == item.id,
                                                      ContentVersion.version == version))
    text = canonical(body)
    if existing is not None:
        if existing.body != text or existing.title != title:
            raise ValueError(f'{slug} v{version} already stored with different content; bump the version')
        return False
    db.add(ContentVersion(item_id=item.id, version=version, status=status, title=title, body=text))
    db.flush()
    return True


def import_json(db: Session, path: Path = CONTENT_FILE) -> tuple[int, int]:
    """Import the editorial file. Idempotent; new versions only. Everything lands as draft.

    Topic: an explicit `topic` {slug,title} if present, else one topic per help lesson.
    """
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    sys.path.insert(0, str(ROOT / 'tools'))
    try:
        from validate_content import validate
    finally:
        sys.path.pop(0)
    validate(data)
    created = skipped = 0
    lesson_topics = {}
    for n, lesson in enumerate(data['lessons']):
        t = lesson.get('topic') or {'slug': lesson['id'].removeprefix('lesson-'), 'title': lesson['title']}
        topic = _topic_for(db, lesson['subject'], lesson['track'], t['slug'], t['title'], n)
        lesson_topics[lesson['id']] = topic
        body = {k: lesson[k] for k in LESSON_FIELDS}
        ok = _add_version(db, 'lesson', lesson['id'], topic, lesson['version'], lesson['title'], body)
        created, skipped = created + ok, skipped + (not ok)
    for q in data['questions']:
        topic = lesson_topics[q['help_lesson_id']]
        body = {k: q[k] for k in QUESTION_FIELDS if k in q}
        validate_question_body(body)
        ok = _add_version(db, 'question', q['id'], topic, q['version'], q['prompt'], body)
        created, skipped = created + ok, skipped + (not ok)
    return created, skipped


def import_ratings_jsonl(db: Session, path: Path) -> tuple[int, int]:
    """Move step-1 anonymous ratings into the table. Idempotent via a line digest."""
    created = skipped = 0
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        key = hashlib.sha256(line.strip().encode()).hexdigest()
        row = json.loads(line)
        if db.scalar(select(ContentRating.id).where(ContentRating.source_key == key)):
            skipped += 1
            continue
        version = db.scalar(select(ContentVersion).join(ContentItem).where(
            ContentItem.slug == row['id'], ContentVersion.version == row['version']))
        if version is None or row['rating'] not in ('up', 'down') or (
                row.get('reason') and row['reason'] not in FEEDBACK_REASONS):
            skipped += 1
            continue
        from datetime import datetime
        at = datetime.fromisoformat(row['at']).replace(tzinfo=None)
        db.add(ContentRating(version_id=version.id, rating=row['rating'], reason=row.get('reason'),
                             at=at, source_key=key))
        created += 1
    db.flush()
    return created, skipped


# ---------- practice views ----------

def practice_statuses(include_drafts: bool | None = None) -> tuple[str, ...]:
    if include_drafts is None:
        include_drafts = settings.allow_draft_practice
    return ('draft', 'reviewed', 'published') if include_drafts else ('published',)


def current_version(item: ContentItem, include_drafts: bool | None = None) -> ContentVersion | None:
    """Version used for *new* practice: newest published one; in draft-preview mode the newest
    non-retired one. Retired versions are never offered (old attempts still render them)."""
    allowed = practice_statuses(include_drafts)
    for v in sorted(item.versions, key=lambda v: -v.version):
        if v.status in allowed:
            return v
    return None


def topic_versions(db: Session, topic: Topic, kind: str, include_drafts: bool | None = None) -> list[ContentVersion]:
    items = db.scalars(select(ContentItem).where(ContentItem.topic_id == topic.id, ContentItem.kind == kind)
                       .order_by(ContentItem.id)).all()
    return [v for v in (current_version(i, include_drafts) for i in items) if v is not None]


def strand_topics(db: Session, strand: Strand, include_drafts: bool | None = None) -> list[Topic]:
    """Topics in a strand with at least one practisable question."""
    topics = db.scalars(select(Topic).where(Topic.subject == strand.subject, Topic.track == strand.track)
                        .order_by(Topic.ordinal, Topic.id)).all()
    return [t for t in topics if topic_versions(db, t, 'question', include_drafts)]


def lesson_for(db: Session, slug: str, include_drafts: bool | None = None) -> ContentVersion | None:
    item = db.scalar(select(ContentItem).where(ContentItem.slug == slug, ContentItem.kind == 'lesson'))
    return current_version(item, include_drafts) if item else None


def public_question(v: ContentVersion, hints_shown: int = 0) -> dict:
    """Learner-safe pre-submit view: no key, no explanation, only revealed hints."""
    d = v.data
    hints_shown = max(0, min(hints_shown, len(d['hints'])))
    return {'id': v.item.slug, 'version': v.version, 'prompt': d['prompt'],
            'options': [{'id': o['id'], 'text': o['text']} for o in d['options']],
            'hints': d['hints'][:hints_shown], 'hints_total': len(d['hints']),
            'help_lesson_id': d.get('help_lesson_id'), 'draft': v.status != 'published'}


def grade(v: ContentVersion, chosen: str) -> dict:
    d = v.data
    texts = {o['id']: o['text'] for o in d['options']}
    if chosen not in texts:
        raise ValueError('invalid option')
    correct = d['correct_option_id']
    return {'correct': chosen == correct, 'chosen': chosen, 'chosen_text': texts[chosen],
            'correct_option_id': correct, 'correct_text': texts[correct], 'explanation': d['explanation']}


def record_rating(db: Session, version: ContentVersion, rating: str, reason: str | None) -> ContentRating:
    if rating not in ('up', 'down') or (reason and reason not in FEEDBACK_REASONS):
        raise ValueError('invalid rating')
    row = ContentRating(version_id=version.id, rating=rating, reason=reason or None, at=utcnow())
    db.add(row)
    db.flush()
    return row
