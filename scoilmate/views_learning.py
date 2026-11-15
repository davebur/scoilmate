"""Student practice (logged in, recorded), progress reports for students/parents/admins, exports."""

from __future__ import annotations

import json
from datetime import timedelta

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import exists, or_, select
from sqlalchemy.orm import Session

from . import accounts, auth, content, learning, reports
from .auth import csrf_protect, require_role
from .content import FEEDBACK_REASONS, Strand
from .db import get_db, utcnow
from .models import ContentVersion, PracticeItem, PracticeSet, RatingReceipt, User
from .web import render

router = APIRouter()
student_only = require_role("student")
parent_only = require_role("parent")
admin_only = require_role("admin")
BREAK_AFTER = timedelta(minutes=45)


def see_other(url: str):
    return RedirectResponse(url, status_code=303)


def late_now() -> bool:
    hour = reports.local(utcnow()).hour
    return hour >= 22 or hour < 6


def parse_confidence(value: str) -> int | None:
    if value in ("", None):
        return None
    if value not in ("1", "2", "3", "4"):
        raise HTTPException(400, "Confidence must be 1-4")
    return int(value)


def strand_or_404(student: User, slug: str) -> Strand:
    strand = Strand.from_slug(slug)
    if strand is None or strand not in learning.student_strands(student):
        raise HTTPException(404, "Unknown subject")
    return strand


# ---------------- student practice ----------------


@router.get("/practice")
def practice_home(
    request: Request, user: User = Depends(student_only), db: Session = Depends(get_db)
):
    report = reports.student_report(db, user, "student")
    return render(request, "practice_home.html", r=report, late=late_now())


@router.get("/practice/topic/{slug}")
def topic_page(
    request: Request, slug: str, user: User = Depends(student_only), db: Session = Depends(get_db)
):
    topic = learning.topic_for(db, user, slug)
    lessons = content.topic_versions(db, topic, "lesson")
    for lesson in lessons:
        learning.record_lesson_read(db, user, lesson)  # activity log only
    p = learning.cached_progress(db, user.id).get(topic.id)
    level = p.level if p else "not_started"
    rated = _rated(db, user, [v.id for v in lessons])
    return render(
        request,
        "topic.html",
        topic=topic,
        strand=Strand(topic.subject, topic.track),
        lessons=lessons,
        level=level,
        label=learning.LABELS[level],
        reason=p.reason if p else learning.RULES[level],
        due=reports.due_text(p.due_at if p else None, utcnow()),
        n_questions=len(learning.topic_questions(db, topic)),
        rated=rated,
        draft=any(v.status != "published" for v in lessons),
    )


@router.post("/practice/topic/{slug}/start", dependencies=[Depends(csrf_protect)])
def start_topic(
    slug: str,
    confidence: str = Form(""),
    user: User = Depends(student_only),
    db: Session = Depends(get_db),
):
    topic = learning.topic_for(db, user, slug)
    ps = learning.start_set(
        db,
        user,
        "topic",
        Strand(topic.subject, topic.track),
        learning.topic_questions(db, topic),
        topic=topic,
        confidence=parse_confidence(confidence),
    )
    return see_other(f"/practice/set/{ps.id}/q/1")


@router.get("/practice/mixed/{strand_slug}")
def mixed_page(
    request: Request,
    strand_slug: str,
    user: User = Depends(student_only),
    db: Session = Depends(get_db),
):
    strand = strand_or_404(user, strand_slug)
    topics = learning.mixed_topics(db, user, strand)
    return render(
        request, "mixed.html", strand=strand, topics=topics, min_topics=learning.MIXED_MIN_TOPICS
    )


@router.post("/practice/mixed/{strand_slug}/start", dependencies=[Depends(csrf_protect)])
def start_mixed(
    strand_slug: str,
    confidence: str = Form(""),
    user: User = Depends(student_only),
    db: Session = Depends(get_db),
):
    strand = strand_or_404(user, strand_slug)
    topics = learning.mixed_topics(db, user, strand)
    if not topics:
        raise HTTPException(
            400, f"Practise at least {learning.MIXED_MIN_TOPICS} topics in this subject first."
        )
    ps = learning.start_set(
        db,
        user,
        "mixed",
        strand,
        learning.mixed_questions(db, topics),
        confidence=parse_confidence(confidence),
    )
    return see_other(f"/practice/set/{ps.id}/q/1")


@router.post("/practice/mistakes/start", dependencies=[Depends(csrf_protect)])
def start_mistakes(user: User = Depends(student_only), db: Session = Depends(get_db)):
    qs = [
        q
        for q in learning.mistakes(db, user.id)
        if Strand(q.item.topic.subject, q.item.topic.track) in learning.student_strands(user)
    ]
    if not qs:
        raise HTTPException(400, "No mistakes to redo right now.")
    first = Strand(qs[0].item.topic.subject, qs[0].item.topic.track)
    ps = learning.start_set(db, user, "mistakes", first, qs[: learning.MIXED_MAX_QUESTIONS])
    return see_other(f"/practice/set/{ps.id}/q/1")


def _set_ctx(ps: PracticeSet) -> dict:
    title = (
        ps.topic.title
        if ps.topic
        else f"{reports.KIND_LABELS[ps.kind]}: {Strand(ps.subject, ps.track).title}"
    )
    return {
        "ps": ps,
        "title": title,
        "total": len(ps.items),
        "kind_label": reports.KIND_LABELS[ps.kind],
    }


def _lang(item: PracticeItem) -> str:
    return content.SUBJECTS[item.question.item.topic.subject]["lang"]


@router.get("/practice/set/{set_id}/q/{n}")
def question(
    request: Request,
    set_id: int,
    n: int,
    user: User = Depends(student_only),
    db: Session = Depends(get_db),
):
    ps = learning.get_set(db, user, set_id)
    item = learning.get_item(ps, n)
    if item.response is not None and ps.completed_at is None:
        pass  # already answered: allowed to look again / retry as practice
    public = content.public_question(item.question, len(item.hints))
    return render(
        request,
        "question.html",
        n=n,
        item=item,
        q=public,
        lang=_lang(item),
        take_break=utcnow() - ps.started_at > BREAK_AFTER,
        **_set_ctx(ps),
    )


@router.post("/practice/set/{set_id}/q/{n}/hint", dependencies=[Depends(csrf_protect)])
def hint(set_id: int, n: int, user: User = Depends(student_only), db: Session = Depends(get_db)):
    ps = learning.get_set(db, user, set_id)
    learning.reveal_hint(db, learning.get_item(ps, n))
    return see_other(f"/practice/set/{ps.id}/q/{n}#hints")


@router.post("/practice/set/{set_id}/q/{n}", dependencies=[Depends(csrf_protect)])
def answer(
    request: Request,
    set_id: int,
    n: int,
    option: str = Form(""),
    user: User = Depends(student_only),
    db: Session = Depends(get_db),
):
    ps = learning.get_set(db, user, set_id)
    item = learning.get_item(ps, n)
    if not option:
        public = content.public_question(item.question, len(item.hints))
        return render(
            request,
            "question.html",
            n=n,
            item=item,
            q=public,
            lang=_lang(item),
            error="Choose an answer before checking.",
            **_set_ctx(ps),
        )
    result, first = learning.answer(db, item, option)
    return render(
        request,
        "feedback.html",
        n=n,
        item=item,
        q=item.question.data,
        result=result,
        first=first,
        hints_used=len(item.hints),
        lang=_lang(item),
        lesson=item.lesson,
        rated=_rated(db, user, [item.question_version_id]),
        **_set_ctx(ps),
    )


@router.get("/practice/set/{set_id}/q/{n}/note")
def pinned_note(
    request: Request,
    set_id: int,
    n: int,
    user: User = Depends(student_only),
    db: Session = Depends(get_db),
):
    ps = learning.get_set(db, user, set_id)
    item = learning.get_item(ps, n)
    if item.lesson is None:
        raise HTTPException(404, "No topic note for this question")
    learning.record_lesson_read(db, user, item.lesson)
    return render(
        request,
        "note.html",
        n=n,
        lesson=item.lesson,
        lang=_lang(item),
        rated=_rated(db, user, [item.lesson.id]),
        **_set_ctx(ps),
    )


@router.post("/practice/set/{set_id}/finish", dependencies=[Depends(csrf_protect)])
def finish(set_id: int, user: User = Depends(student_only), db: Session = Depends(get_db)):
    ps = learning.get_set(db, user, set_id)
    learning.finish(db, ps)
    return see_other(f"/practice/set/{ps.id}/summary")


@router.get("/practice/set/{set_id}/summary")
def summary(
    request: Request, set_id: int, user: User = Depends(student_only), db: Session = Depends(get_db)
):
    ps = learning.get_set(db, user, set_id)
    if ps.completed_at is None:
        return see_other(f"/practice/set/{ps.id}/q/1")
    progress = learning.cached_progress(db, user.id)
    touched = sorted(
        {it.question.item.topic for it in ps.items if it.response is not None}, key=lambda t: t.id
    )
    changes = [
        {
            "topic": t,
            "label": learning.LABELS[progress[t.id].level],
            "reason": progress[t.id].reason,
            "due": reports.due_text(progress[t.id].due_at, utcnow()),
        }
        for t in touched
        if t.id in progress
    ]
    return render(
        request,
        "set_summary.html",
        summ=learning.set_summary(ps),
        changes=changes,
        confidence=learning.CONFIDENCE.get(ps.confidence),
        next_steps=learning.NEXT_STEPS,
        credit_rule=learning.CREDIT_RULE,
        **_set_ctx(ps),
    )


@router.post("/practice/set/{set_id}/next", dependencies=[Depends(csrf_protect)])
def next_step(
    set_id: int,
    choice: str = Form(""),
    reflection: str = Form(""),
    user: User = Depends(student_only),
    db: Session = Depends(get_db),
):
    ps = learning.get_set(db, user, set_id)
    if ps.completed_at is None or (choice and choice not in learning.NEXT_STEPS):
        raise HTTPException(400, "Finish the set first")
    ps.next_step = choice or None
    ps.reflection = reflection.strip()[:500] or None
    strand = Strand(ps.subject, ps.track)
    if choice == "revisit" and ps.topic:
        return see_other(f"/practice/topic/{ps.topic.slug}")
    if choice == "mixed":
        return see_other(f"/practice/mixed/{strand.slug}")
    return see_other("/practice")


def _rated(db: Session, user: User, version_ids: list[int]) -> set[int]:
    if not version_ids:
        return set()
    return set(
        db.scalars(
            select(RatingReceipt.version_id).where(
                RatingReceipt.student_id == user.id, RatingReceipt.version_id.in_(version_ids)
            )
        )
    )


@router.post("/practice/rate", dependencies=[Depends(csrf_protect)])
def rate(
    version_id: int = Form(...),
    rating: str = Form(...),
    reason: str = Form(""),
    back: str = Form(""),
    user: User = Depends(student_only),
    db: Session = Depends(get_db),
):
    """Anonymous 👍/👎: the rating row has no user id; a receipt only stops double-voting."""
    if rating not in ("up", "down") or (reason and reason not in FEEDBACK_REASONS):
        raise HTTPException(400, "Invalid rating")
    version = db.get(ContentVersion, version_id)
    seen = version is not None and db.scalar(
        select(
            exists().where(
                PracticeItem.set_id == PracticeSet.id,
                PracticeSet.student_id == user.id,
                or_(
                    PracticeItem.question_version_id == version_id,
                    PracticeItem.lesson_version_id == version_id,
                ),
            )
        )
    )
    if version is not None and not seen and version.item.kind == "lesson":
        topic = version.item.topic
        seen = (
            Strand(topic.subject, topic.track) in learning.student_strands(user)
            and content.current_version(version.item) is version
        )
    if not seen:
        raise HTTPException(404, "No such item")
    if db.get(RatingReceipt, (user.id, version.id)) is None:
        db.add(RatingReceipt(student_id=user.id, version_id=version.id))
        content.record_rating(db, version, rating, reason or None)
    target = auth.safe_next(back, "/practice").split("#")[0]
    return see_other(target + ("&" if "?" in target else "?") + "thanks=1")


# ---------------- reports ----------------


@router.get("/progress")
def my_progress(
    request: Request, user: User = Depends(student_only), db: Session = Depends(get_db)
):
    return render(request, "my_progress.html", r=reports.student_report(db, user, "student"))


def _json_download(data: dict, name: str):
    return Response(
        json.dumps(data, indent=2, ensure_ascii=False),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.get("/progress/export.json")
def my_export(user: User = Depends(student_only), db: Session = Depends(get_db)):
    return _json_download(
        reports.export_student(db, user, include_reflections=True), "my-scoilmate-data.json"
    )


@router.get("/parent/children/{student_id}/report")
def parent_report(
    request: Request,
    student_id: str,
    user: User = Depends(parent_only),
    db: Session = Depends(get_db),
):
    child = accounts.student_for(db, user, student_id)
    return render(
        request,
        "report_child.html",
        r=reports.student_report(db, child, "parent"),
        back="/parent",
        back_label="My children",
    )


@router.get("/parent/children/{student_id}/export.json")
def parent_export(
    student_id: str, user: User = Depends(parent_only), db: Session = Depends(get_db)
):
    child = accounts.student_for(db, user, student_id)
    accounts.audit(db, user, "data_exported", child)
    return _json_download(
        reports.export_student(db, child, include_reflections=False),
        f"{child.login}-scoilmate.json",
    )


@router.get("/admin/users/{student_id}/export.json")
def admin_export(student_id: str, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    child = accounts.get_user(db, student_id, "student")
    accounts.audit(db, user, "data_exported", child)
    return _json_download(
        reports.export_student(db, child, include_reflections=False),
        f"{child.login}-scoilmate.json",
    )


@router.get("/admin/reports/students/{student_id}")
def admin_student_report(
    request: Request,
    student_id: str,
    user: User = Depends(admin_only),
    db: Session = Depends(get_db),
):
    child = accounts.get_user(db, student_id, "student")
    return render(
        request,
        "report_child.html",
        r=reports.student_report(db, child, "admin"),
        back="/admin/reports",
        back_label="Reports",
    )


def _overview(db: Session, strand: str, year: str):
    st = Strand.from_slug(strand or "english")
    if st is None:
        raise HTTPException(404, "Unknown subject")
    return reports.class_overview(
        db, st, accounts.parse_year(year) if year in ("1", "2", "3") else None
    )


@router.get("/admin/reports")
def admin_reports(
    request: Request,
    strand: str = "english",
    year: str = "",
    user: User = Depends(admin_only),
    db: Session = Depends(get_db),
):
    return render(
        request,
        "admin_reports.html",
        o=_overview(db, strand, year),
        strands=content.all_strands(),
        labels=learning.LABELS,
    )


@router.get("/admin/reports/class.csv")
def admin_class_csv(
    strand: str = "english",
    year: str = "",
    user: User = Depends(admin_only),
    db: Session = Depends(get_db),
):
    o = _overview(db, strand, year)
    body = reports.to_csv(
        ["student", "login", "year"] + [t.title for t in o["topics"]],
        [
            [r["student"].display_name, r["student"].login, r["student"].school_year or ""]
            + [learning.LABELS[lv] for lv in r["levels"]]
            for r in o["grid"]
        ],
    )
    return Response(
        body,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="class-{o["strand"].slug}.csv"'},
    )


@router.get("/admin/reports/questions")
def admin_questions(
    request: Request,
    subject: str = "",
    user: User = Depends(admin_only),
    db: Session = Depends(get_db),
):
    subject = subject if subject in content.SUBJECTS else ""
    return render(
        request,
        "admin_questions.html",
        rows=reports.question_stats(db, subject or None),
        subject=subject,
    )


@router.get("/admin/reports/questions.csv")
def admin_questions_csv(
    subject: str = "", user: User = Depends(admin_only), db: Session = Depends(get_db)
):
    rows = reports.question_stats(db, subject if subject in content.SUBJECTS else None)
    body = reports.to_csv(
        [
            "question",
            "version",
            "topic",
            "prompt",
            "first_answers",
            "pct_correct",
            "most_chosen_wrong",
            "pct_used_hints",
            "avg_hints",
        ],
        [
            [
                r["slug"],
                r["version"].version,
                r["topic"],
                r["version"].title,
                r["n"],
                r["pct_correct"],
                r["top_wrong"],
                r["pct_hinted"],
                r["avg_hints"],
            ]
            for r in rows
        ],
    )
    return Response(
        body,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="questions.csv"'},
    )
