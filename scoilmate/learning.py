"""Learning rules: mastery levels, hint credit, revisit ladder, mixed reviews, mistake review.

Every rule here is meant to be explainable to a 13-year-old (learning-design guidance §3).
Progress is *derived*: `replay()` rebuilds it from completed practice sets, and the
`topic_progress` table is only a cache of that result.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from . import content
from .content import Strand
from .db import utcnow
from .models import (
    Activity,
    ContentItem,
    ContentVersion,
    HintEvent,
    PracticeItem,
    PracticeSet,
    Response,
    Topic,
    TopicProgress,
    User,
)

RULE_VERSION = 1
LEVELS = ("not_started", "attempted", "familiar", "proficient", "mastered")
LABELS = {
    "not_started": "Not started",
    "attempted": "Attempted",
    "familiar": "Familiar",
    "proficient": "Proficient",
    "mastered": "Mastered",
}
RULES = {
    "not_started": "You have not practised this topic yet.",
    "attempted": "Attempted: under 70% in your last practice of this topic.",
    "familiar": "Familiar: 70% or more in your last practice of this topic (or a slip in a mixed review).",
    "proficient": "Proficient: everything right first time in your last practice (one answer with one hint is OK).",
    "mastered": "Mastered: Proficient, then right again in a mixed review at least 3 days later.",
}
CREDIT_RULE = (
    "Scoring: right first time with no hint = 1, right after one hint = ½, otherwise 0 for levels. "
    "Hints help you learn; they just mean we will check this again soon."
)
INTERVALS = {"attempted": 1, "familiar": 3, "proficient": 7, "mastered": 21}
MASTERED_AGAIN_DAYS = 45
MASTERY_GAP = timedelta(days=3)
MIXED_MIN_TOPICS, MIXED_MAX_TOPICS, MIXED_MAX_QUESTIONS = 2, 5, 15
TOPIC_SET_MAX = 8
CONFIDENCE = {1: "not yet", 2: "a bit", 3: "mostly", 4: "very"}
NEXT_STEPS = {
    "revisit": "Revisit this topic",
    "mixed": "Try a mixed review",
    "new_topic": "Move to a new topic",
}


def credit(is_correct: bool, hints: int) -> float:
    return 1.0 if is_correct and hints == 0 else 0.5 if is_correct and hints == 1 else 0.0


def rank(level: str) -> int:
    return LEVELS.index(level)


def set_level(results: list[tuple[bool, int]]) -> tuple[str, float]:
    """Level earned by one topic practice set: list of (correct first time?, hints used)."""
    score = sum(credit(c, h) for c, h in results) / len(results)
    hinted = [h for c, h in results if h]
    if all(c for c, _ in results) and len(hinted) <= 1 and max(hinted, default=0) <= 1:
        return "proficient", score
    return ("familiar" if score >= 0.7 else "attempted"), score


@dataclass
class TopicState:
    level: str = "not_started"
    reason: str = RULES["not_started"]
    last_at: datetime | None = None
    proficient_since: datetime | None = None
    due_at: datetime | None = None
    mastered_reviews: int = 0

    def schedule(self, at: datetime):
        days = INTERVALS.get(self.level)
        if self.level == "mastered" and self.mastered_reviews > 1:
            days = MASTERED_AGAIN_DAYS
        self.due_at = at + timedelta(days=days) if days else None
        self.last_at = at


def _describe(results, score) -> str:
    n = len(results)
    own = sum(1 for c, h in results if c and not h)
    hinted = sum(1 for c, h in results if c and h)
    return f"{own} of {n} right first time on your own, {hinted} with hints (score {round(score * 100)}%)."


def apply_topic_set(st: TopicState, at: datetime, results: list[tuple[bool, int]]):
    earned, score = set_level(results)
    prev = st.level
    if prev == "mastered" and earned == "proficient":
        new = "mastered"
        why = "Still Mastered: everything right again in topic practice."
    elif prev != "not_started" and rank(earned) < rank(prev):
        new = LEVELS[max(rank(earned), rank(prev) - 1)]  # never drop more than one step at a time
        st.mastered_reviews = 0
        why = f"Moved one step from {LABELS[prev]} to {LABELS[new]} (levels only move one step at a time)."
    else:
        new = earned
        why = RULES[new]
    if new == "proficient" and prev not in ("proficient", "mastered"):
        st.proficient_since = at
    elif rank(new) < rank("proficient"):
        st.proficient_since = None
    st.level, st.reason = new, f"{why} Last practice: {_describe(results, score)}"
    st.schedule(at)


def apply_mixed(st: TopicState, at: datetime, results: list[tuple[bool, int]]):
    clean = all(c and not h for c, h in results)
    prev = st.level
    if prev == "not_started":
        return  # mixed reviews only include practised topics; nothing to update
    if clean:
        if (
            prev in ("proficient", "mastered")
            and st.proficient_since
            and at - st.proficient_since >= MASTERY_GAP
        ):
            st.level = "mastered"
            st.mastered_reviews += 1
            st.reason = (
                "Mastered: Proficient, then right again in a mixed review at least 3 days later."
            )
        elif prev == "proficient":
            st.reason = (
                "Mixed review right, but Mastered needs a mixed review at least 3 days after you "
                "became Proficient. Keep going!"
            )
        else:
            st.reason = (
                f"{RULES[prev]} Right in a mixed review too; a topic practice set can move you up."
            )
    else:
        if prev in ("proficient", "mastered"):
            st.level = LEVELS[rank(prev) - 1]
            st.proficient_since = at if st.level == "proficient" else None
            st.mastered_reviews = 0
            st.reason = (
                f"Moved one step to {LABELS[st.level]}: a question on this topic in a mixed review "
                "needs another look."
            )
        else:
            st.reason = f"{RULES[prev]} A mixed review question needs another look."
    st.schedule(at)


# ---------- replay (the source of truth for progress) ----------


def _first_results(items: list[PracticeItem]) -> dict[int, list[tuple[bool, int]]]:
    by_topic: dict[int, list] = {}
    for it in items:
        if it.response is not None:
            by_topic.setdefault(it.question.item.topic_id, []).append(
                (it.response.is_correct, it.response.hints_used)
            )
    return by_topic


def completed_sets(db: Session, student_id: str) -> list[PracticeSet]:
    return list(
        db.scalars(
            select(PracticeSet)
            .where(PracticeSet.student_id == student_id, PracticeSet.completed_at.is_not(None))
            .order_by(PracticeSet.completed_at, PracticeSet.id)
            .options(
                selectinload(PracticeSet.items).selectinload(PracticeItem.response),
                selectinload(PracticeSet.items)
                .selectinload(PracticeItem.question)
                .selectinload(ContentVersion.item),
            )
        )
    )


def replay(db: Session, student_id: str) -> dict[int, TopicState]:
    states: dict[int, TopicState] = {}
    for ps in completed_sets(db, student_id):
        for topic_id, results in _first_results(ps.items).items():
            st = states.setdefault(topic_id, TopicState())
            if ps.kind == "topic":
                apply_topic_set(st, ps.completed_at, results)
            elif ps.kind == "mixed":
                apply_mixed(st, ps.completed_at, results)
            # 'mistakes' sets are extra practice: they clear mistakes but don't change levels
    return states


def refresh_cache(db: Session, student_id: str) -> dict[int, TopicState]:
    states = replay(db, student_id)
    db.execute(delete(TopicProgress).where(TopicProgress.student_id == student_id))
    for topic_id, st in states.items():
        db.add(
            TopicProgress(
                student_id=student_id,
                topic_id=topic_id,
                level=st.level,
                reason=st.reason[:300],
                last_practised_at=st.last_at,
                proficient_since=st.proficient_since,
                due_at=st.due_at,
                mastered_reviews=st.mastered_reviews,
                rule_version=RULE_VERSION,
            )
        )
    db.flush()
    return states


def cached_progress(db: Session, student_id: str) -> dict[int, TopicProgress]:
    return {
        p.topic_id: p
        for p in db.scalars(select(TopicProgress).where(TopicProgress.student_id == student_id))
    }


# ---------- what the student can practise ----------


def student_strands(student: User) -> list[Strand]:
    order = {s.slug: i for i, s in enumerate(content.all_strands())}
    strands = [Strand(s.subject, s.track) for s in student.subjects]
    return sorted(strands, key=lambda s: order.get(s.slug, 99))


def topic_for(db: Session, student: User, slug: str) -> Topic:
    topic = db.scalar(select(Topic).where(Topic.slug == slug))
    if (
        topic is None
        or Strand(topic.subject, topic.track) not in student_strands(student)
        or not content.topic_versions(db, topic, "question")
    ):
        raise HTTPException(404, "No such topic")
    return topic


def mixed_topics(
    db: Session, student: User, strand: Strand, now: datetime | None = None
) -> list[Topic]:
    """Practised topics in one subject, the most overdue first; empty if fewer than the minimum."""
    now = now or utcnow()
    progress = cached_progress(db, student.id)
    topics = [
        t
        for t in content.strand_topics(db, strand)
        if t.id in progress and progress[t.id].level != "not_started"
    ]
    topics.sort(key=lambda t: progress[t.id].due_at or now)
    return topics[:MIXED_MAX_TOPICS] if len(topics) >= MIXED_MIN_TOPICS else []


def mistakes(db: Session, student_id: str) -> list[ContentVersion]:
    """Questions whose most recent answer was wrong and are still offered for practice."""
    rows = db.execute(
        select(PracticeItem.question_version_id, Response.is_correct)
        .join(PracticeSet)
        .join(Response)
        .where(PracticeSet.student_id == student_id)
        .order_by(Response.answered_at, Response.id)
    ).all()
    latest: dict[int, bool] = {}
    for version_id, ok in rows:
        v = db.get(ContentVersion, version_id)
        latest[v.item_id] = ok
    out = []
    for item_id, ok in latest.items():
        if not ok:
            v = content.current_version(db.get(ContentItem, item_id))
            if v is not None:
                out.append(v)
    return out


def _lesson_version(db: Session, q: ContentVersion) -> ContentVersion | None:
    slug = q.data.get("help_lesson_id")
    return content.lesson_for(db, slug) if slug else None


def start_set(
    db: Session,
    student: User,
    kind: str,
    strand: Strand,
    questions: list[ContentVersion],
    topic: Topic | None = None,
    confidence: int | None = None,
) -> PracticeSet:
    if not questions:
        raise HTTPException(400, "There are no questions to practise here yet.")
    if confidence not in (None, 1, 2, 3, 4):
        raise HTTPException(400, "Confidence must be 1-4")
    ps = PracticeSet(
        student_id=student.id,
        kind=kind,
        subject=strand.subject,
        track=strand.track,
        topic_id=topic.id if topic else None,
        confidence=confidence,
        started_at=utcnow(),
    )
    for n, q in enumerate(questions, 1):
        lesson = _lesson_version(db, q)
        ps.items.append(
            PracticeItem(
                ordinal=n, question_version_id=q.id, lesson_version_id=lesson.id if lesson else None
            )
        )
    db.add(ps)
    db.flush()
    return ps


def topic_questions(db: Session, topic: Topic) -> list[ContentVersion]:
    return content.topic_versions(db, topic, "question")[:TOPIC_SET_MAX]


def mixed_questions(db: Session, topics: list[Topic], seed=None) -> list[ContentVersion]:
    qs = [q for t in topics for q in content.topic_versions(db, t, "question")]
    random.Random(seed).shuffle(qs)
    return qs[:MIXED_MAX_QUESTIONS]


def get_set(db: Session, student: User, set_id: int) -> PracticeSet:
    ps = db.get(PracticeSet, set_id)
    if ps is None or ps.student_id != student.id:
        raise HTTPException(404, "No such practice set")
    return ps


def get_item(ps: PracticeSet, n: int) -> PracticeItem:
    if not 1 <= n <= len(ps.items):
        raise HTTPException(404, "No such question")
    return ps.items[n - 1]


def reveal_hint(db: Session, item: PracticeItem) -> int:
    total = len(item.question.data["hints"])
    if item.response is None and len(item.hints) < total:
        item.hints.append(HintEvent(ordinal=len(item.hints) + 1, at=utcnow()))
        db.flush()
    return len(item.hints)


def answer(db: Session, item: PracticeItem, option: str) -> tuple[dict, bool]:
    """Grade on the server. Only the first answer is stored; retries are practice only."""
    try:
        result = content.grade(item.question, option)
    except ValueError:
        raise HTTPException(400, "Invalid answer option")
    first = item.response is None and item.set.completed_at is None
    if first:
        hints = len(item.hints)
        item.response = Response(
            selected=option,
            is_correct=result["correct"],
            hints_used=hints,
            credit=credit(result["correct"], hints),
            answered_at=utcnow(),
        )
        db.flush()
    return result, first


def finish(db: Session, ps: PracticeSet) -> dict[int, tuple[TopicState | None, TopicState]]:
    """Complete a set; returns {topic_id: (before, after)} for the topics it touched."""
    before = {
        tid: TopicState(level=p.level) for tid, p in cached_progress(db, ps.student_id).items()
    }
    if ps.completed_at is None:
        ps.completed_at = utcnow()
        db.add(
            Activity(
                student_id=ps.student_id, kind="set_completed", set_id=ps.id, at=ps.completed_at
            )
        )
        db.flush()
    after = refresh_cache(db, ps.student_id)
    touched = {it.question.item.topic_id for it in ps.items if it.response is not None}
    return {tid: (before.get(tid), after[tid]) for tid in touched if tid in after}


def set_summary(ps: PracticeSet) -> dict:
    answered = [it for it in ps.items if it.response is not None]
    own = sum(1 for it in answered if it.response.is_correct and not it.response.hints_used)
    hinted = sum(1 for it in answered if it.response.is_correct and it.response.hints_used)
    return {
        "total": len(ps.items),
        "answered": len(answered),
        "own": own,
        "hinted": hinted,
        "review": len(answered) - own - hinted,
    }


def record_lesson_read(db: Session, student: User, lesson: ContentVersion):
    db.add(Activity(student_id=student.id, kind="lesson_read", version_id=lesson.id, at=utcnow()))
