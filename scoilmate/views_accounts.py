"""Login/logout, admin account management, parent child management, student settings."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import accounts, auth
from .auth import csrf_protect, require_role
from .config import settings
from .db import get_db
from .models import AuditLog, User
from .web import render

router = APIRouter()
admin_only = require_role("admin")
parent_only = require_role("parent")
student_only = require_role("student")
GENERIC_LOGIN_ERROR = "Login name or password not recognised."


def see_other(url: str):
    return RedirectResponse(url, status_code=303)


async def form_dict(request: Request) -> dict:
    return {k: v for k, v in (await request.form()).items() if isinstance(v, str)}


# ---------------- login / logout ----------------


@router.get("/login")
def login_page(request: Request, next: str = "", user: User | None = Depends(auth.current_user)):
    if user:
        return see_other(auth.home_for(user))
    return render(request, "login.html", next=auth.safe_next(next, ""))


@router.post("/login", dependencies=[Depends(csrf_protect)])
def login(
    request: Request,
    login: str = Form(""),
    password: str = Form(""),
    next: str = Form(""),
    db: Session = Depends(get_db),
):
    name = auth.normalise_login(login)[:64]
    ip = request.client.host if request.client else "unknown"
    wait = auth.login_blocked(name, ip)
    if wait:
        response = render(
            request,
            "login.html",
            status_code=429,
            next=auth.safe_next(next, ""),
            error=f"Too many attempts. Please wait {max(1, wait // 60)} minute(s) and try again.",
        )
        response.headers["Retry-After"] = str(wait)
        return response
    user = db.scalar(select(User).where(User.login == name))
    if not auth.verify_password(user, password) or not user.active:
        auth.login_limiter.hit(f"acct:{name}")
        auth.login_limiter.hit(f"ip:{ip}")
        return render(
            request,
            "login.html",
            status_code=400,
            next=auth.safe_next(next, ""),
            error=GENERIC_LOGIN_ERROR,
            login=name,
        )
    auth.login_limiter.clear(f"acct:{name}")
    auth.end_session(db, request.cookies.get(settings.session_cookie))  # rotate
    token = auth.start_session(db, user)
    response = see_other(auth.safe_next(next, auth.home_for(user)))
    auth.set_session_cookie(response, token)
    return response


@router.post("/logout", dependencies=[Depends(csrf_protect)])
def logout(request: Request, db: Session = Depends(get_db)):
    auth.end_session(db, request.cookies.get(settings.session_cookie))
    response = see_other("/login?bye=1")
    auth.clear_session_cookie(response)
    return response


# ---------------- admin ----------------


@router.get("/admin")
def admin_home(request: Request, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    people = db.scalars(select(User).order_by(User.role, User.display_name)).all()
    students = [u for u in people if u.role == "student"]
    return render(
        request,
        "admin_home.html",
        parents=[u for u in people if u.role == "parent"],
        admins=[u for u in people if u.role == "admin"],
        students=students,
        parents_of={s.id: accounts.parents_of(db, s) for s in students},
        orphans=accounts.students_without_parent(db),
        deletion_requests=[s for s in students if s.deletion_requested_at],
    )


@router.get("/admin/users/new")
def admin_new_user(
    request: Request,
    role: str = "student",
    user: User = Depends(admin_only),
    db: Session = Depends(get_db),
):
    if role not in ("student", "parent"):
        raise HTTPException(404, "Unknown account type")
    parents = db.scalars(
        select(User).where(User.role == "parent").order_by(User.display_name)
    ).all()
    return render(
        request, "user_new.html", role=role, parents=parents, form={}, action="/admin/users/new"
    )


@router.post("/admin/users/new", dependencies=[Depends(csrf_protect)])
async def admin_create_user(
    request: Request, user: User = Depends(admin_only), db: Session = Depends(get_db)
):
    form = await form_dict(request)
    role = form.get("role")
    if role not in ("student", "parent"):
        raise HTTPException(400, "Unknown account type")
    parent_ids = [
        v
        for k, v in (await request.form()).multi_items()
        if k == "parent_id" and isinstance(v, str)
    ]
    try:
        password = form.get("password") or auth.generate_password()
        new = accounts.create_user(
            db,
            user,
            role,
            form.get("login", ""),
            form.get("display_name", ""),
            password,
            email=form.get("email"),
            school_year=accounts.parse_year(form.get("school_year")),
            subjects=accounts.parse_subjects(form) if role == "student" else None,
        )
        for pid in parent_ids:
            accounts.link(db, user, accounts.get_user(db, pid, "parent"), new)
    except ValueError as exc:
        db.rollback()
        parents = db.scalars(select(User).where(User.role == "parent")).all()
        return render(
            request,
            "user_new.html",
            status_code=400,
            role=role,
            parents=parents,
            form=form,
            error=str(exc),
            action="/admin/users/new",
        )
    return render(
        request,
        "password_shown.html",
        target=new,
        password=password,
        back=f"/admin/users/{new.id}",
        created=True,
    )


@router.get("/admin/users/{user_id}")
def admin_user(
    request: Request, user_id: str, user: User = Depends(admin_only), db: Session = Depends(get_db)
):
    target = accounts.get_user(db, user_id)
    linked = (
        accounts.parents_of(db, target)
        if target.role == "student"
        else accounts.children_of(db, target)
    )
    candidates = db.scalars(
        select(User)
        .where(User.role == ("parent" if target.role == "student" else "student"))
        .order_by(User.display_name)
    ).all()
    log = db.scalars(
        select(AuditLog)
        .where(AuditLog.target_user_id == target.id)
        .order_by(AuditLog.id.desc())
        .limit(30)
    ).all()
    return render(
        request,
        "admin_user.html",
        target=target,
        linked=linked,
        candidates=[c for c in candidates if c not in linked],
        log=log,
        subjects={s.subject: s for s in target.subjects},
    )


def _admin_target(db, user_id):
    return accounts.get_user(db, user_id)


@router.post("/admin/users/{user_id}/settings", dependencies=[Depends(csrf_protect)])
async def admin_settings(
    request: Request, user_id: str, user: User = Depends(admin_only), db: Session = Depends(get_db)
):
    target = accounts.get_user(db, user_id, "student")
    form = await form_dict(request)
    try:
        accounts.update_settings(
            db,
            user,
            target,
            accounts.parse_year(form.get("school_year")),
            accounts.parse_subjects(form),
            form.get("display_name"),
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return see_other(f"/admin/users/{target.id}?saved=1")


@router.post("/admin/users/{user_id}/link", dependencies=[Depends(csrf_protect)])
def admin_link(
    user_id: str,
    other_id: str = Form(""),
    unlink: str = Form(""),
    user: User = Depends(admin_only),
    db: Session = Depends(get_db),
):
    target, other = accounts.get_user(db, user_id), accounts.get_user(db, other_id)
    parent, student = (other, target) if target.role == "student" else (target, other)
    if parent.role != "parent" or student.role != "student":
        raise HTTPException(400, "Links join a parent and a student.")
    (accounts.unlink if unlink else accounts.link)(db, user, parent, student)
    return see_other(f"/admin/users/{target.id}")


@router.post("/admin/users/{user_id}/reset", dependencies=[Depends(csrf_protect)])
def admin_reset(
    request: Request, user_id: str, user: User = Depends(admin_only), db: Session = Depends(get_db)
):
    target = accounts.get_user(db, user_id)
    if target.id == user.id:
        raise HTTPException(400, "Use the create-admin command to change your own password.")
    password = accounts.reset_access(db, user, target)
    return render(
        request,
        "password_shown.html",
        target=target,
        password=password,
        back=f"/admin/users/{target.id}",
    )


@router.post("/admin/users/{user_id}/status", dependencies=[Depends(csrf_protect)])
def admin_status(
    user_id: str,
    active: str = Form(...),
    user: User = Depends(admin_only),
    db: Session = Depends(get_db),
):
    target = accounts.get_user(db, user_id)
    try:
        accounts.set_active(db, user, target, active == "1")
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return see_other(f"/admin/users/{target.id}")


@router.post("/admin/users/{user_id}/delete", dependencies=[Depends(csrf_protect)])
def admin_delete(
    request: Request,
    user_id: str,
    confirm: str = Form(""),
    user: User = Depends(admin_only),
    db: Session = Depends(get_db),
):
    target = accounts.get_user(db, user_id)
    if auth.normalise_login(confirm) != target.login:
        raise HTTPException(400, "Type the login name exactly to confirm deletion.")
    try:
        orphans = accounts.delete_user(db, user, target)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return render(request, "deleted.html", role=target.role, orphans=orphans)


@router.get("/admin/audit")
def admin_audit(request: Request, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    log = db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(300)).all()
    return render(request, "admin_audit.html", log=log)


# ---------------- parent ----------------


@router.get("/parent")
def parent_home(request: Request, user: User = Depends(parent_only), db: Session = Depends(get_db)):
    return render(request, "parent_home.html", children=accounts.children_of(db, user))


@router.get("/parent/children/new")
def parent_new_child(request: Request, user: User = Depends(parent_only)):
    return render(
        request, "user_new.html", role="student", parents=[], form={}, action="/parent/children/new"
    )


@router.post("/parent/children/new", dependencies=[Depends(csrf_protect)])
async def parent_create_child(
    request: Request, user: User = Depends(parent_only), db: Session = Depends(get_db)
):
    form = await form_dict(request)
    try:
        password = form.get("password") or auth.generate_password()
        child = accounts.create_user(
            db,
            user,
            "student",
            form.get("login", ""),
            form.get("display_name", ""),
            password,
            school_year=accounts.parse_year(form.get("school_year")),
            subjects=accounts.parse_subjects(form),
        )
        accounts.link(db, user, user, child)
    except ValueError as exc:
        db.rollback()
        return render(
            request,
            "user_new.html",
            status_code=400,
            role="student",
            parents=[],
            form=form,
            error=str(exc),
            action="/parent/children/new",
        )
    return render(
        request,
        "password_shown.html",
        target=child,
        password=password,
        back=f"/parent/children/{child.id}",
        created=True,
    )


@router.get("/parent/children/{student_id}")
def parent_child(
    request: Request,
    student_id: str,
    user: User = Depends(parent_only),
    db: Session = Depends(get_db),
):
    child = accounts.student_for(db, user, student_id)
    return render(
        request, "parent_child.html", child=child, subjects={s.subject: s for s in child.subjects}
    )


@router.post("/parent/children/{student_id}/settings", dependencies=[Depends(csrf_protect)])
async def parent_settings(
    request: Request,
    student_id: str,
    user: User = Depends(parent_only),
    db: Session = Depends(get_db),
):
    child = accounts.student_for(db, user, student_id)
    form = await form_dict(request)
    try:
        accounts.update_settings(
            db,
            user,
            child,
            accounts.parse_year(form.get("school_year")),
            accounts.parse_subjects(form),
            form.get("display_name"),
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return see_other(f"/parent/children/{child.id}?saved=1")


@router.post("/parent/children/{student_id}/reset", dependencies=[Depends(csrf_protect)])
def parent_reset(
    request: Request,
    student_id: str,
    user: User = Depends(parent_only),
    db: Session = Depends(get_db),
):
    child = accounts.student_for(db, user, student_id)
    password = accounts.reset_access(db, user, child)
    return render(
        request,
        "password_shown.html",
        target=child,
        password=password,
        back=f"/parent/children/{child.id}",
    )


@router.post("/parent/children/{student_id}/status", dependencies=[Depends(csrf_protect)])
def parent_status(
    student_id: str,
    active: str = Form(...),
    user: User = Depends(parent_only),
    db: Session = Depends(get_db),
):
    child = accounts.student_for(db, user, student_id)
    accounts.set_active(db, user, child, active == "1")
    return see_other(f"/parent/children/{child.id}")


@router.post("/parent/children/{student_id}/deletion", dependencies=[Depends(csrf_protect)])
def parent_deletion(
    student_id: str,
    cancel: str = Form(""),
    user: User = Depends(parent_only),
    db: Session = Depends(get_db),
):
    child = accounts.student_for(db, user, student_id)
    if cancel:
        accounts.cancel_deletion_request(db, user, child)
    else:
        accounts.request_deletion(db, user, child)
    return see_other(f"/parent/children/{child.id}")


# ---------------- student ----------------


@router.get("/me/settings")
def my_settings(request: Request, saved: int = 0, user: User = Depends(student_only)):
    return render(
        request,
        "my_settings.html",
        subjects={s.subject: s for s in user.subjects},
        saved=saved,
        year=user.school_year,
    )


@router.post("/me/settings", dependencies=[Depends(csrf_protect)])
async def my_settings_save(
    request: Request, user: User = Depends(student_only), db: Session = Depends(get_db)
):
    form = await form_dict(request)
    try:  # own year/subjects only; name and access are managed by a parent/admin
        accounts.update_settings(
            db,
            user,
            user,
            accounts.parse_year(form.get("school_year")),
            accounts.parse_subjects(form),
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return see_other("/me/settings?saved=1")
