"""Progress reports for students, parents and admins.

Do not show (learning-design guidance §3.10): grade predictions or descriptors, rankings or
comparisons between named students, class averages to students, private reflections to
anyone but the student, or time-of-day detail (reports show dates only).
"""

from __future__ import annotations

import csv
import io
from collections import Counter
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import content, learning
from .content import Strand
from .db import utcnow
from .models import (
    Activity,
    ContentItem,
    ContentVersion,
    PracticeItem,
    PracticeSet,
    Response,
    StudentSubject,
    Topic,
    User,
)

LOCAL = ZoneInfo("Europe/Dublin")
KIND_LABELS = {"topic": "Topic practice", "mixed": "Mixed review", "mistakes": "Mistake review"}


def local(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC).astimezone(LOCAL)


def due_text(due: datetime | None, now: datetime) -> str:
    if due is None:
        return ""
    if due <= now:
        return "Ready to revisit"
    d = local(due)
    if (due - now) < timedelta(days=6):
        return f"Due for review: {d:%A}"
    return f"Due for review: {d.day} {d:%b}"


def week_start(now: datetime) -> datetime:
    d = local(now)
    monday = (d - timedelta(days=d.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    return monday.astimezone(UTC).replace(tzinfo=None)


def strand_rows(db: Session, student: User, now: datetime) -> list[dict]:
    progress = learning.cached_progress(db, student.id)
    out = []
    for strand in learning.student_strands(student):
        topics = []
        for t in content.strand_topics(db, strand):
            p = progress.get(t.id)
            level = p.level if p else "not_started"
            topics.append(
                {
                    "topic": t,
                    "level": level,
                    "label": learning.LABELS[level],
                    "reason": p.reason if p else learning.RULES["not_started"],
                    "rule": learning.RULES[level],
                    "due_at": p.due_at if p else None,
                    "due_text": due_text(p.due_at if p else None, now),
                    "ready": bool(p and p.due_at and p.due_at <= now),
                    "last_at": p.last_practised_at if p else None,
                }
            )
        secure = sum(1 for x in topics if x["level"] in ("proficient", "mastered"))
        out.append(
            {
                "strand": strand,
                "topics": topics,
                "secure_pct": round(100 * secure / len(topics)) if topics else 0,
                "mixed_ready": len(learning.mixed_topics(db, student, strand, now))
                >= learning.MIXED_MIN_TOPICS,
            }
        )
    return out


def sessions(db: Session, student: User, limit: int | None = 10) -> list[dict]:
    q = (
        select(PracticeSet)
        .where(PracticeSet.student_id == student.id, PracticeSet.completed_at.is_not(None))
        .order_by(PracticeSet.completed_at.desc(), PracticeSet.id.desc())
    )
    if limit:
        q = q.limit(limit)
    rows = []
    for ps in db.scalars(q):
        summ = learning.set_summary(ps)
        title = ps.topic.title if ps.topic else Strand(ps.subject, ps.track).title
        rows.append(
            {
                "set": ps,
                "date": ps.completed_at,
                "kind": KIND_LABELS[ps.kind],
                "title": title,
                "summary": summ,
                "confidence": learning.CONFIDENCE.get(ps.confidence),
                "reflection": ps.reflection,
                "next_step": learning.NEXT_STEPS.get(ps.next_step),
            }
        )
    return rows


def weekly_counts(db: Session, student: User, weeks: int, now: datetime) -> list[dict]:
    start = week_start(now) - timedelta(weeks=weeks - 1)
    acts = db.execute(
        select(Activity.kind, Activity.at).where(
            Activity.student_id == student.id, Activity.at >= start
        )
    ).all()
    buckets = []
    for i in range(weeks):
        lo = start + timedelta(weeks=i)
        hi = lo + timedelta(weeks=1)
        inside = [k for k, at in acts if lo <= at < hi]
        buckets.append(
            {
                "week_of": lo,
                "sessions": inside.count("set_completed"),
                "notes": inside.count("lesson_read"),
            }
        )
    return buckets


def suggestion(rows: list[dict]) -> str:
    for r in rows:
        ready = [t for t in r["topics"] if t["ready"]]
        if ready:
            return f"Revisit “{ready[0]['topic'].title}” ({r['strand'].title}): it is ready for review."
    for r in rows:
        if r["mixed_ready"] and any(t["level"] == "proficient" for t in r["topics"]):
            return f"Try a mixed review in {r['strand'].title}: it is the way to reach Mastered."
    for r in rows:
        new = [t for t in r["topics"] if t["level"] == "not_started"]
        if new:
            return f"Start a new topic: “{new[0]['topic'].title}” ({r['strand'].title})."
    return "Nothing is due. Have a rest, or try a mixed review for fun."


def student_report(db: Session, student: User, audience: str, now: datetime | None = None) -> dict:
    """audience: 'student' (own view), 'parent' or 'admin'. Reflection text only for the student."""
    now = now or utcnow()
    rows = strand_rows(db, student, now)
    recent = sessions(db, student, 10)
    all_sets = sessions(db, student, None)
    totals = Counter()
    for s in all_sets:
        for k in ("answered", "own", "hinted", "review"):
            totals[k] += s["summary"][k]
    if audience != "student":
        for s in recent:
            s["reflection"] = None  # private to the student
    report = {
        "student": student,
        "audience": audience,
        "strands": rows,
        "recent": recent,
        "totals": totals,
        "calibration": [s for s in recent if s["confidence"]],
        "week_count": sum(1 for s in all_sets if s["date"] >= week_start(now)),
        "suggestion": suggestion(rows),
        "now": now,
        "mistakes": len(learning.mistakes(db, student.id)),
    }
    if audience in ("parent", "admin"):
        report["last_active"] = db.scalar(
            select(func.max(Activity.at)).where(Activity.student_id == student.id)
        )
        report["weekly"] = weekly_counts(db, student, 8 if audience == "admin" else 4, now)
    if audience == "admin":
        report["overdue"] = sum(1 for r in rows for t in r["topics"] if t["ready"])
        missed = Counter()
        for s in all_sets:
            for it in s["set"].items:
                if it.response is not None and not it.response.is_correct:
                    missed[it.question.item.topic_id] += 1
        report["most_missed"] = [(db.get(Topic, tid), n) for tid, n in missed.most_common(5)]
    return report


# ---------- admin: class overview and question stats ----------


def class_overview(db: Session, strand: Strand, year: int | None = None) -> dict:
    q = (
        select(User)
        .join(StudentSubject, StudentSubject.user_id == User.id)
        .where(
            User.role == "student",
            User.status == "active",
            StudentSubject.subject == strand.subject,
            StudentSubject.track == strand.track,
        )
        .order_by(User.display_name)
    )
    if year:
        q = q.where(User.school_year == year)
    students = db.scalars(q).all()
    topics = content.strand_topics(db, strand)
    grid = []
    for s in students:
        progress = learning.cached_progress(db, s.id)
        grid.append(
            {
                "student": s,
                "levels": [
                    progress[t.id].level if t.id in progress else "not_started" for t in topics
                ],
            }
        )
    distribution = [Counter(row["levels"][i] for row in grid) for i in range(len(topics))]
    return {
        "strand": strand,
        "year": year,
        "topics": topics,
        "grid": grid,
        "distribution": distribution,
    }


def question_stats(db: Session, subject: str | None = None) -> list[dict]:
    q = (
        select(ContentVersion, Response)
        .join(PracticeItem, PracticeItem.question_version_id == ContentVersion.id)
        .join(Response, Response.item_id == PracticeItem.id)
        .join(ContentItem, ContentVersion.item_id == ContentItem.id)
        .join(Topic, ContentItem.topic_id == Topic.id)
    )
    if subject:
        q = q.where(Topic.subject == subject)
    by_version: dict[int, dict] = {}
    for v, r in db.execute(q).all():
        row = by_version.setdefault(
            v.id, {"version": v, "n": 0, "correct": 0, "hinted": 0, "hints": 0, "wrong": Counter()}
        )
        row["n"] += 1
        row["correct"] += r.is_correct
        row["hinted"] += r.hints_used > 0
        row["hints"] += r.hints_used
        if not r.is_correct:
            row["wrong"][r.selected] += 1
    out = []
    for row in by_version.values():
        v, n = row["version"], row["n"]
        texts = {o["id"]: o["text"] for o in v.data["options"]}
        top_wrong = row["wrong"].most_common(1)
        out.append(
            {
                "version": v,
                "slug": v.item.slug,
                "topic": v.item.topic.title,
                "n": n,
                "pct_correct": round(100 * row["correct"] / n),
                "pct_hinted": round(100 * row["hinted"] / n),
                "avg_hints": round(row["hints"] / n, 2),
                "top_wrong": (
                    f"{top_wrong[0][0]}: {texts.get(top_wrong[0][0], '?')} ({top_wrong[0][1]})"
                    if top_wrong
                    else "—"
                ),
            }
        )
    out.sort(key=lambda r: (r["pct_correct"], r["slug"]))
    return out


def to_csv(header: list[str], rows: list[list]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    for row in rows:  # neutralise spreadsheet formula injection
        w.writerow(
            ["'" + c if isinstance(c, str) and c[:1] in ("=", "+", "-", "@") else c for c in row]
        )
    return buf.getvalue()


# ---------- data export (access request) ----------


def export_student(db: Session, student: User, include_reflections: bool) -> dict:
    def iso(dt):
        return dt.isoformat() + "Z" if dt else None

    sets = []
    for ps in db.scalars(
        select(PracticeSet).where(PracticeSet.student_id == student.id).order_by(PracticeSet.id)
    ):
        sets.append(
            {
                "kind": ps.kind,
                "subject": ps.subject,
                "track": ps.track,
                "topic": ps.topic.slug if ps.topic else None,
                "started_at": iso(ps.started_at),
                "completed_at": iso(ps.completed_at),
                "confidence_before": ps.confidence,
                "next_step": ps.next_step,
                "reflection": (
                    ps.reflection
                    if include_reflections
                    else ("(private to the student)" if ps.reflection else None)
                ),
                "items": [
                    {
                        "question": it.question.item.slug,
                        "question_version": it.question.version,
                        "hints_revealed": len(it.hints),
                        "answer": it.response.selected if it.response else None,
                        "correct": it.response.is_correct if it.response else None,
                        "answered_at": iso(it.response.answered_at) if it.response else None,
                    }
                    for it in ps.items
                ],
            }
        )
    acts = [
        {"kind": a.kind, "at": iso(a.at)}
        for a in db.scalars(
            select(Activity).where(Activity.student_id == student.id).order_by(Activity.id)
        )
    ]
    return {
        "exported_at": iso(utcnow()),
        "format": "scoilmate-student-export-1",
        "account": {
            "login": student.login,
            "name": student.display_name,
            "school_year": student.school_year,
            "status": student.status,
            "created_at": iso(student.created_at),
            "subjects": [
                {"subject": s.subject, "track": s.track, "level": s.level} for s in student.subjects
            ],
        },
        "progress": [
            {
                "topic": db.get(Topic, tid).slug,
                "level": p.level,
                "reason": p.reason,
                "due_at": iso(p.due_at),
            }
            for tid, p in learning.cached_progress(db, student.id).items()
        ],
        "practice_sets": sets,
        "activity": acts,
        "note": "Ratings are anonymous and cannot be linked to you, so they are not included.",
    }
