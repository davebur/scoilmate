"""Account management services. Every change is written to the audit log.

Permission checks live here too (not only in routes): parents can only act on students
linked to them; nothing trusts a user id from the client without scoping it.
"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import exists, select, update
from sqlalchemy.orm import Session

from . import auth
from .content import SUBJECTS
from .db import utcnow
from .models import AuditLog, ParentStudent, StudentSubject, User

LEVELS = {
    "english": ("higher", "ordinary", "undecided"),
    "gaeilge": ("higher", "ordinary", "undecided"),
    "history": ("common",),
}
TRACKS = {"english": ("general",), "gaeilge": ("T1", "T2"), "history": ("general",)}


def audit(
    db: Session,
    actor: User | None,
    action: str,
    target: User | None = None,
    detail: str | None = None,
):
    db.add(
        AuditLog(
            actor_id=actor.id if actor else None,
            action=action,
            target_user_id=target.id if target else None,
            detail=(detail or "")[:300] or None,
        )
    )


def is_linked(db: Session, parent_id: str, student_id: str) -> bool:
    return bool(
        db.scalar(
            select(
                exists().where(
                    ParentStudent.parent_id == parent_id, ParentStudent.student_id == student_id
                )
            )
        )
    )


def children_of(db: Session, parent: User) -> list[User]:
    return list(
        db.scalars(
            select(User)
            .join(ParentStudent, ParentStudent.student_id == User.id)
            .where(ParentStudent.parent_id == parent.id)
            .order_by(User.display_name)
        )
    )


def parents_of(db: Session, student: User) -> list[User]:
    return list(
        db.scalars(
            select(User)
            .join(ParentStudent, ParentStudent.parent_id == User.id)
            .where(ParentStudent.student_id == student.id)
            .order_by(User.display_name)
        )
    )


def get_user(db: Session, user_id: str, role: str | None = None) -> User:
    user = db.get(User, user_id) if user_id and len(user_id) <= 32 else None
    if user is None or (role and user.role != role):
        raise HTTPException(404, "No such account")
    return user


def student_for(db: Session, actor: User, student_id: str) -> User:
    """The single gate for 'may this person act on/see this student?'. 404 hides existence."""
    student = db.get(User, student_id) if student_id and len(student_id) <= 32 else None
    allowed = (
        student is not None
        and student.role == "student"
        and (
            actor.role == "admin"
            or (actor.role == "parent" and is_linked(db, actor.id, student.id))
            or (actor.role == "student" and actor.id == student.id)
        )
    )
    if not allowed:
        raise HTTPException(404, "No such student")
    return student


def parse_subjects(form: dict) -> list[tuple[str, str, str]]:
    """Read subject checkboxes / track / level fields from a submitted form."""
    chosen = []
    for subject in SUBJECTS:
        if form.get(f"subj_{subject}") != "on":
            continue
        track = form.get(f"track_{subject}") or TRACKS[subject][0]
        level = form.get(f"level_{subject}") or LEVELS[subject][-1]
        if track not in TRACKS[subject] or level not in LEVELS[subject]:
            raise ValueError("Choose a valid track and level for each subject.")
        chosen.append((subject, track, level))
    return chosen


def parse_year(value) -> int | None:
    if value in (None, ""):
        return None
    if str(value) not in ("1", "2", "3"):
        raise ValueError("School year must be 1, 2 or 3.")
    return int(value)


def create_user(
    db: Session,
    actor: User | None,
    role: str,
    login: str,
    display_name: str,
    password: str,
    email: str | None = None,
    school_year: int | None = None,
    subjects: list[tuple[str, str, str]] | None = None,
) -> User:
    login = auth.check_login_name(login)
    display_name = (display_name or "").strip()
    if not 1 <= len(display_name) <= 80:
        raise ValueError(
            "Give a name (students: a first name or nickname is enough), up to 80 characters."
        )
    if role == "student":
        email = None  # never needed for students
    elif email:
        email = email.strip()
        if len(email) > 254 or "@" not in email:
            raise ValueError("That email address does not look right.")
    if db.scalar(select(User.id).where(User.login == login)):
        raise ValueError("That login name is taken; choose another.")
    user = User(
        login=login,
        display_name=display_name,
        role=role,
        email=email or None,
        password_hash=auth.hash_password(password),
        school_year=school_year if role == "student" else None,
    )
    db.add(user)
    db.flush()
    if role == "student":
        set_subjects(
            db,
            user,
            (
                subjects
                if subjects is not None
                else [
                    ("english", "general", "undecided"),
                    ("gaeilge", "T2", "undecided"),
                    ("history", "general", "common"),
                ]
            ),
        )
    audit(db, actor, f"{role}_created", user, f"login={login}")
    return user


def set_subjects(db: Session, student: User, subjects: list[tuple[str, str, str]]):
    student.subjects.clear()
    db.flush()
    for subject, track, level in subjects:
        student.subjects.append(StudentSubject(subject=subject, track=track, level=level))
    db.flush()


def update_settings(
    db: Session,
    actor: User,
    student: User,
    school_year: int | None,
    subjects: list[tuple[str, str, str]],
    display_name: str | None = None,
):
    if display_name is not None and actor.role != "student":
        display_name = display_name.strip()
        if not 1 <= len(display_name) <= 80:
            raise ValueError("Name must be 1-80 characters.")
        student.display_name = display_name
    student.school_year = school_year
    set_subjects(db, student, subjects)
    audit(
        db,
        actor,
        "settings_changed",
        student,
        f"year={school_year}; " + ", ".join(f"{s}:{t}:{lv}" for s, t, lv in subjects),
    )


def link(db: Session, actor: User, parent: User, student: User):
    if parent.role != "parent" or student.role != "student":
        raise ValueError("Links join a parent and a student.")
    if not is_linked(db, parent.id, student.id):
        db.add(ParentStudent(parent_id=parent.id, student_id=student.id, created_by=actor.id))
        audit(db, actor, "link_added", student, f"parent={parent.login}")


def unlink(db: Session, actor: User, parent: User, student: User):
    row = db.get(ParentStudent, (parent.id, student.id))
    if row is not None:
        db.delete(row)
        audit(db, actor, "link_removed", student, f"parent={parent.login}")


def reset_access(db: Session, actor: User, user: User, new_password: str | None = None) -> str:
    password = new_password or auth.generate_password()
    user.password_hash = auth.hash_password(password)
    auth.revoke_all(db, user.id)
    audit(db, actor, "access_reset", user)
    return password


def set_active(db: Session, actor: User, user: User, active: bool):
    if user.id == actor.id:
        raise ValueError("You can't deactivate your own account.")
    user.status = "active" if active else "disabled"
    user.disabled_at = None if active else utcnow()
    if not active:
        auth.revoke_all(db, user.id)
    audit(db, actor, "reactivated" if active else "deactivated", user)


def request_deletion(db: Session, parent: User, student: User):
    student.deletion_requested_at = utcnow()
    student.deletion_requested_by = parent.id
    audit(db, parent, "deletion_requested", student)


def cancel_deletion_request(db: Session, actor: User, student: User):
    student.deletion_requested_at = student.deletion_requested_by = None
    audit(db, actor, "deletion_request_cancelled", student)


def delete_user(db: Session, actor: User, user: User) -> list[User]:
    """Admin only. Students: all learning data goes too (FK cascades). Parents: their children
    stay; returns children left with no parent so the admin can follow up."""
    if user.id == actor.id:
        raise ValueError("You can't delete your own account.")
    orphans = []
    if user.role == "parent":
        orphans = [c for c in children_of(db, user) if len(parents_of(db, c)) == 1]
    role = user.role
    # Scrub identifying audit detail about the erased person, then record the erasure itself.
    db.execute(update(AuditLog).where(AuditLog.target_user_id == user.id).values(detail=None))
    db.delete(user)
    db.flush()
    audit(db, actor, f"{role}_deleted", None, "account and its data erased")
    return orphans


def students_without_parent(db: Session) -> list[User]:
    return list(
        db.scalars(
            select(User)
            .where(User.role == "student", ~exists().where(ParentStudent.student_id == User.id))
            .order_by(User.display_name)
        )
    )
