"""SQLAlchemy models. The Alembic migrations in scoilmate/migrations are the source of
truth for the schema; tools/test_storage.py checks the two agree.

Content rows are versioned: a `content_version`'s title/body never change after insert
(enforced by a database trigger). Editing creates a new version. Attempts pin versions.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime

from sqlalchemy import (Boolean, CheckConstraint, DateTime, Float, ForeignKey, Integer, MetaData,
                        String, Text, UniqueConstraint)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from .db import utcnow

NAMING = {'ix': 'ix_%(column_0_label)s', 'uq': 'uq_%(table_name)s_%(column_0_name)s',
          'ck': 'ck_%(table_name)s_%(constraint_name)s',
          'fk': 'fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s', 'pk': 'pk_%(table_name)s'}

ROLES = ('admin', 'parent', 'student')
STATUSES = ('draft', 'reviewed', 'published', 'retired')
SUBJECTS = ('english', 'gaeilge', 'history')
RATING_REASONS = ('unclear', 'wrong', 'too_easy', 'too_hard', 'helpful')
SET_KINDS = ('topic', 'mixed', 'mistakes')
NEXT_STEPS = ('revisit', 'mixed', 'new_topic')


def new_id() -> str:
    return uuid.uuid4().hex


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)


# ---------- identity ----------

class User(Base):
    __tablename__ = 'user'
    __table_args__ = (CheckConstraint("role IN ('admin','parent','student')", name='role'),
                      CheckConstraint("status IN ('active','disabled')", name='status'),
                      CheckConstraint('school_year IS NULL OR school_year BETWEEN 1 AND 3', name='year'))
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    login: Mapped[str] = mapped_column(String(64), unique=True)  # normalised lower-case
    display_name: Mapped[str] = mapped_column(String(80))  # alias for students; name for parents
    email: Mapped[str | None] = mapped_column(String(254))  # adults only
    password_hash: Mapped[str | None] = mapped_column(String(255))  # None = no access until reset
    role: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(10), default='active')
    school_year: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime)
    deletion_requested_at: Mapped[datetime | None] = mapped_column(DateTime)
    deletion_requested_by: Mapped[str | None] = mapped_column(ForeignKey('user.id', ondelete='SET NULL'))

    subjects: Mapped[list['StudentSubject']] = relationship(
        cascade='all, delete-orphan', passive_deletes=True, order_by='StudentSubject.subject')

    @property
    def active(self) -> bool:
        return self.status == 'active'


class StudentSubject(Base):
    __tablename__ = 'student_subject'
    __table_args__ = (CheckConstraint("subject IN ('english','gaeilge','history')", name='subject'),
                      CheckConstraint("track IN ('general','T1','T2')", name='track'),
                      CheckConstraint("level IN ('higher','ordinary','common','undecided')", name='level'))
    user_id: Mapped[str] = mapped_column(ForeignKey('user.id', ondelete='CASCADE'), primary_key=True)
    subject: Mapped[str] = mapped_column(String(10), primary_key=True)
    track: Mapped[str] = mapped_column(String(10), default='general')
    level: Mapped[str] = mapped_column(String(10), default='undecided')


# ---------- content ----------

class Topic(Base):
    __tablename__ = 'topic'
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    subject: Mapped[str] = mapped_column(String(10))
    track: Mapped[str] = mapped_column(String(10))
    title: Mapped[str] = mapped_column(String(160))
    ordinal: Mapped[int] = mapped_column(Integer, default=0)


class ContentItem(Base):
    __tablename__ = 'content_item'
    __table_args__ = (CheckConstraint("kind IN ('lesson','question')", name='kind'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    kind: Mapped[str] = mapped_column(String(10))
    topic_id: Mapped[int] = mapped_column(ForeignKey('topic.id', ondelete='RESTRICT'), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    topic: Mapped[Topic] = relationship()
    versions: Mapped[list['ContentVersion']] = relationship(
        back_populates='item', order_by='ContentVersion.version')


class ContentVersion(Base):
    __tablename__ = 'content_version'
    __table_args__ = (UniqueConstraint('item_id', 'version', name='uq_content_version_item_version'),
                      CheckConstraint("status IN ('draft','reviewed','published','retired')", name='status'),
                      CheckConstraint('version > 0', name='version_positive'))
    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey('content_item.id', ondelete='RESTRICT'), index=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(10), default='draft')
    title: Mapped[str] = mapped_column(String(300))  # lesson title / question prompt
    body: Mapped[str] = mapped_column(Text)  # JSON; immutable (trigger)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    created_by: Mapped[str | None] = mapped_column(ForeignKey('user.id', ondelete='SET NULL'))
    reviewed_by: Mapped[str | None] = mapped_column(ForeignKey('user.id', ondelete='SET NULL'))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    review_note: Mapped[str | None] = mapped_column(String(500))
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime)
    item: Mapped[ContentItem] = relationship(back_populates='versions')

    @property
    def data(self) -> dict:
        return json.loads(self.body)


class ContentRating(Base):
    """Anonymous 👍/👎: no user id, no free text."""
    __tablename__ = 'content_rating'
    __table_args__ = (CheckConstraint("rating IN ('up','down')", name='rating'),
                      CheckConstraint("reason IS NULL OR reason IN ('unclear','wrong','too_easy','too_hard','helpful')",
                                      name='reason'))
    id: Mapped[int] = mapped_column(primary_key=True)
    version_id: Mapped[int] = mapped_column(ForeignKey('content_version.id', ondelete='RESTRICT'), index=True)
    rating: Mapped[str] = mapped_column(String(4))
    reason: Mapped[str | None] = mapped_column(String(10))
    at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    source_key: Mapped[str | None] = mapped_column(String(64), unique=True)  # dedupes JSONL imports
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)


# ---------- attempts (pin exact versions) ----------

class PracticeSet(Base):
    __tablename__ = 'practice_set'
    __table_args__ = (CheckConstraint("kind IN ('topic','mixed','mistakes')", name='kind'),
                      CheckConstraint('confidence IS NULL OR confidence BETWEEN 1 AND 4', name='confidence'),
                      CheckConstraint("next_step IS NULL OR next_step IN ('revisit','mixed','new_topic')",
                                      name='next_step'))
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[str] = mapped_column(ForeignKey('user.id', ondelete='CASCADE'), index=True)
    kind: Mapped[str] = mapped_column(String(10))
    subject: Mapped[str] = mapped_column(String(10))
    track: Mapped[str] = mapped_column(String(10))
    topic_id: Mapped[int | None] = mapped_column(ForeignKey('topic.id', ondelete='RESTRICT'))
    confidence: Mapped[int | None] = mapped_column(Integer)  # 1-4, asked before the set
    next_step: Mapped[str | None] = mapped_column(String(10))
    reflection: Mapped[str | None] = mapped_column(String(500))  # private to the student
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    items: Mapped[list['PracticeItem']] = relationship(
        back_populates='set', order_by='PracticeItem.ordinal', cascade='all, delete-orphan', passive_deletes=True)
    topic: Mapped[Topic | None] = relationship()


class PracticeItem(Base):
    __tablename__ = 'practice_item'
    __table_args__ = (UniqueConstraint('set_id', 'ordinal', name='uq_practice_item_set_ordinal'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    set_id: Mapped[int] = mapped_column(ForeignKey('practice_set.id', ondelete='CASCADE'), index=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    question_version_id: Mapped[int] = mapped_column(ForeignKey('content_version.id', ondelete='RESTRICT'), index=True)
    lesson_version_id: Mapped[int | None] = mapped_column(ForeignKey('content_version.id', ondelete='RESTRICT'))
    set: Mapped[PracticeSet] = relationship(back_populates='items')
    question: Mapped[ContentVersion] = relationship(foreign_keys=[question_version_id])
    lesson: Mapped[ContentVersion | None] = relationship(foreign_keys=[lesson_version_id])
    hints: Mapped[list['HintEvent']] = relationship(order_by='HintEvent.ordinal', cascade='all, delete-orphan',
                                                    passive_deletes=True)
    response: Mapped['Response | None'] = relationship(cascade='all, delete-orphan', passive_deletes=True,
                                                       uselist=False)


class HintEvent(Base):
    """Server-recorded hint reveal; the client never reports its own hint count."""
    __tablename__ = 'hint_event'
    __table_args__ = (UniqueConstraint('item_id', 'ordinal', name='uq_hint_event_item_ordinal'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey('practice_item.id', ondelete='CASCADE'))
    ordinal: Mapped[int] = mapped_column(Integer)
    at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Response(Base):
    """First answer only; retries are practice and are not stored."""
    __tablename__ = 'response'
    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey('practice_item.id', ondelete='CASCADE'), unique=True)
    selected: Mapped[str] = mapped_column(String(8))
    is_correct: Mapped[bool] = mapped_column(Boolean)
    hints_used: Mapped[int] = mapped_column(Integer)
    credit: Mapped[float] = mapped_column(Float)
    answered_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


# ---------- accounts (migration 0002) ----------

class AuthSession(Base):
    """Server-side session. Only a SHA-256 digest of the cookie token is stored."""
    __tablename__ = 'session'
    token_digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('user.id', ondelete='CASCADE'), index=True)
    csrf_token: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    idle_expires_at: Mapped[datetime] = mapped_column(DateTime)
    absolute_expires_at: Mapped[datetime] = mapped_column(DateTime)
    user: Mapped[User] = relationship()


class ParentStudent(Base):
    __tablename__ = 'parent_student'
    parent_id: Mapped[str] = mapped_column(ForeignKey('user.id', ondelete='CASCADE'), primary_key=True)
    student_id: Mapped[str] = mapped_column(ForeignKey('user.id', ondelete='CASCADE'), primary_key=True, index=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey('user.id', ondelete='SET NULL'))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AuditLog(Base):
    """Who did what to which account. Never holds passwords, tokens or reflection text."""
    __tablename__ = 'audit_log'
    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey('user.id', ondelete='SET NULL'))
    action: Mapped[str] = mapped_column(String(40))
    target_user_id: Mapped[str | None] = mapped_column(ForeignKey('user.id', ondelete='SET NULL'), index=True)
    detail: Mapped[str | None] = mapped_column(String(300))
    actor: Mapped[User | None] = relationship(foreign_keys=[actor_id])
    target: Mapped[User | None] = relationship(foreign_keys=[target_user_id])


# ---------- learning (migration 0003) ----------

class TopicProgress(Base):
    """Derived cache, rebuilt by replaying completed practice sets (learning.replay)."""
    __tablename__ = 'topic_progress'
    __table_args__ = (CheckConstraint("level IN ('not_started','attempted','familiar','proficient','mastered')",
                                      name='level'),)
    student_id: Mapped[str] = mapped_column(ForeignKey('user.id', ondelete='CASCADE'), primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey('topic.id', ondelete='RESTRICT'), primary_key=True)
    level: Mapped[str] = mapped_column(String(12))
    reason: Mapped[str] = mapped_column(String(300))
    last_practised_at: Mapped[datetime | None] = mapped_column(DateTime)
    proficient_since: Mapped[datetime | None] = mapped_column(DateTime)
    due_at: Mapped[datetime | None] = mapped_column(DateTime)
    mastered_reviews: Mapped[int] = mapped_column(Integer, default=0)
    rule_version: Mapped[int] = mapped_column(Integer)


class Activity(Base):
    """Common activity log so reports cover every activity type (lessons read, sets done, ...)."""
    __tablename__ = 'activity'
    __table_args__ = (CheckConstraint("kind IN ('lesson_read','set_completed')", name='kind'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[str] = mapped_column(ForeignKey('user.id', ondelete='CASCADE'), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    version_id: Mapped[int | None] = mapped_column(ForeignKey('content_version.id', ondelete='RESTRICT'))
    set_id: Mapped[int | None] = mapped_column(ForeignKey('practice_set.id', ondelete='CASCADE'))
    at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class RatingReceipt(Base):
    """Records *that* a student rated a version (one rating each), never what they said."""
    __tablename__ = 'rating_receipt'
    student_id: Mapped[str] = mapped_column(ForeignKey('user.id', ondelete='CASCADE'), primary_key=True)
    version_id: Mapped[int] = mapped_column(ForeignKey('content_version.id', ondelete='RESTRICT'), primary_key=True)
