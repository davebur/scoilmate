"""Clearly fake demo accounts with some practice history, for clicking through the preview."""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import accounts, content, learning
from .config import settings
from .content import Strand
from .db import utcnow
from .models import Activity, HintEvent, Response, Topic, User

PASSWORDS = {  # demo only: never use on a real deployment
    'demo-admin': 'demo-admin-pass', 'demo-parent1': 'demo-parent-pass', 'demo-parent2': 'demo-parent-pass',
    'demo-student1': 'demo-student-pass', 'demo-student2': 'demo-student-pass', 'demo-student3': 'demo-student-pass',
}


def _topic(db: Session, slug: str) -> Topic:
    return db.scalar(select(Topic).where(Topic.slug == slug))


def _set(db, student, kind, slugs, plan, days_ago, confidence=None, reflection=None, next_step=None):
    topics = [_topic(db, s) for s in slugs]
    qs = [q for t in topics for q in content.topic_versions(db, t, 'question', include_drafts=True)]
    strand = Strand(topics[0].subject, topics[0].track)
    ps = learning.start_set(db, student, kind, strand, qs, topic=topics[0] if kind == 'topic' else None,
                            confidence=confidence)
    when = utcnow() - timedelta(days=days_ago, hours=2)
    ps.started_at = when
    for item, (ok, hints) in zip(ps.items, plan):
        d = item.question.data
        for h in range(hints):
            item.hints.append(HintEvent(ordinal=h + 1, at=when))
        choice = d['correct_option_id'] if ok else next(o['id'] for o in d['options'] if o['id'] != d['correct_option_id'])
        item.response = Response(selected=choice, is_correct=ok, hints_used=hints, credit=learning.credit(ok, hints),
                                 answered_at=when + timedelta(minutes=2))
    ps.completed_at = when + timedelta(minutes=10)
    ps.reflection, ps.next_step = reflection, next_step
    db.add(Activity(student_id=student.id, kind='set_completed', set_id=ps.id, at=ps.completed_at))
    lesson = content.lesson_for(db, qs[0].data['help_lesson_id'], include_drafts=True)
    db.add(Activity(student_id=student.id, kind='lesson_read', version_id=lesson.id, at=when))
    db.flush()


def seed(db: Session, reset: bool = False) -> dict[str, str]:
    existing = db.scalars(select(User).where(User.login.in_(PASSWORDS))).all()
    if existing and not reset:
        raise ValueError('Demo accounts already exist. Use --reset to delete and recreate them.')
    for u in existing:  # cascades remove their practice history too
        db.delete(u)
    db.flush()
    if not _topic(db, 'simile'):
        content.import_json(db)
    old = settings.allow_draft_practice
    settings.allow_draft_practice = True
    try:
        mk = lambda role, login, name, **kw: accounts.create_user(db, None, role, login, name, PASSWORDS[login], **kw)
        mk('admin', 'demo-admin', 'Demo Admin')
        p1 = mk('parent', 'demo-parent1', 'Demo Parent One', email='parent1@example.invalid')
        p2 = mk('parent', 'demo-parent2', 'Demo Parent Two', email='parent2@example.invalid')
        all3 = [('english', 'general', 'higher'), ('gaeilge', 'T2', 'ordinary'), ('history', 'general', 'common')]
        s1 = mk('student', 'demo-student1', 'Demo Student A', school_year=3, subjects=all3)
        s2 = mk('student', 'demo-student2', 'Demo Student B', school_year=2, subjects=all3)
        s3 = mk('student', 'demo-student3', 'Demo Student C', school_year=1,
                subjects=[('english', 'general', 'undecided'), ('gaeilge', 'T1', 'undecided'),
                          ('history', 'general', 'common')])
        for parent, child in ((p1, s1), (p1, s2), (p2, s3)):
            accounts.link(db, parent, parent, child)
        _set(db, s1, 'topic', ['simile'], [(True, 0)], 12, confidence=2)
        _set(db, s1, 'topic', ['purpose'], [(True, 1)], 12, confidence=3)
        _set(db, s1, 'topic', ['inference'], [(False, 0)], 11, confidence=3,
             reflection='Demo note: reread the inference note.', next_step='revisit')
        _set(db, s1, 'mixed', ['simile', 'purpose', 'inference'], [(True, 0), (True, 0), (False, 1)], 7, confidence=3)
        _set(db, s1, 'topic', ['primary'], [(True, 0)], 4, confidence=4)
        _set(db, s1, 'topic', ['corroboration'], [(False, 0)], 1, confidence=2)
        _set(db, s2, 'topic', ['simile'], [(False, 0)], 3, confidence=4)
        _set(db, s2, 'topic', ['ga-message'], [(True, 2)], 2)
        _set(db, s2, 'topic', ['ga-time'], [(True, 0)], 2, confidence=1)
        for s in (s1, s2, s3):
            learning.refresh_cache(db, s.id)
    finally:
        settings.allow_draft_practice = old
    return PASSWORDS
