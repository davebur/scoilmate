"""Passwords (Argon2id), server-side sessions, CSRF tokens, login rate limiting, role guards."""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import threading
import time
from collections import deque
from datetime import timedelta
from types import SimpleNamespace
from urllib.parse import urlsplit

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import Depends, Form, HTTPException, Request
from sqlalchemy import delete
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db, utcnow
from .models import AuthSession, User

# argon2-cffi defaults are Argon2id, 64 MiB, t=3, p=4 (above the OWASP 19 MiB/t=2 baseline).
hasher = PasswordHasher()
_DUMMY_HASH = hasher.hash(secrets.token_urlsafe(16))
LOGIN_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,31}$")
PASSWORD_MIN, PASSWORD_MAX = 8, 128
# (idle, absolute) session lifetimes per role
LIFETIMES = {
    "admin": (timedelta(minutes=20), timedelta(hours=8)),
    "parent": (timedelta(minutes=60), timedelta(hours=12)),
    "student": (timedelta(minutes=60), timedelta(hours=12)),
}
TOUCH_EVERY = timedelta(seconds=60)  # throttle last-seen writes


class LoginRequired(Exception):
    pass


# ---------- passwords and login names ----------


def normalise_login(value: str) -> str:
    return (value or "").strip().lower()


def check_login_name(value: str) -> str:
    login = normalise_login(value)
    if not LOGIN_RE.match(login):
        raise ValueError(
            "Login names are 3-32 characters: letters, numbers, dot, dash or underscore."
        )
    return login


def check_password(value: str) -> str:
    if not PASSWORD_MIN <= len(value or "") <= PASSWORD_MAX:
        raise ValueError(f"Passwords must be {PASSWORD_MIN}-{PASSWORD_MAX} characters.")
    return value


def hash_password(password: str) -> str:
    return hasher.hash(check_password(password))


def verify_password(user: User | None, password: str) -> bool:
    """Constant-ish work whether or not the account exists; rehashes on policy change."""
    if len(password or "") > PASSWORD_MAX:
        return False
    stored = user.password_hash if user is not None and user.password_hash else _DUMMY_HASH
    try:
        hasher.verify(stored, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
    if user is None or not user.password_hash:
        return False
    if hasher.check_needs_rehash(stored):
        user.password_hash = hasher.hash(password)
    return True


def generate_password() -> str:
    """Readable temporary password for a parent/admin to pass on (about 60 bits)."""
    words = secrets.token_hex(2), secrets.token_hex(2), secrets.token_hex(2), secrets.token_hex(2)
    return "-".join(words)


# ---------- rate limiting (in-process; resets on restart) ----------


class RateLimiter:
    def __init__(self):
        self._hits: dict[str, deque] = {}
        self._lock = threading.Lock()

    def retry_after(self, key: str, limit: int, window: int) -> int:
        now = time.monotonic()
        with self._lock:
            q = self._hits.get(key)
            if not q:
                return 0
            while q and q[0] <= now - window:
                q.popleft()
            return int(q[0] + window - now) + 1 if len(q) >= limit else 0

    def hit(self, key: str):
        with self._lock:
            self._hits.setdefault(key, deque()).append(time.monotonic())
            if len(self._hits) > 50_000:  # bounded memory
                self._hits.pop(next(iter(self._hits)))

    def clear(self, key: str):
        with self._lock:
            self._hits.pop(key, None)

    def reset(self):
        with self._lock:
            self._hits.clear()


login_limiter = RateLimiter()


def login_blocked(login: str, ip: str) -> int:
    s = settings
    return max(
        login_limiter.retry_after(f"acct:{login}", s.login_max_per_account, s.login_window_s),
        login_limiter.retry_after(f"ip:{ip}", s.login_max_per_ip, s.login_window_s),
    )


# ---------- sessions ----------


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def start_session(db: Session, user: User) -> str:
    token = secrets.token_urlsafe(32)  # 256 bits; only the digest is stored
    idle, absolute = LIFETIMES[user.role]
    now = utcnow()
    db.add(
        AuthSession(
            token_digest=_digest(token),
            user_id=user.id,
            csrf_token=secrets.token_urlsafe(32),
            created_at=now,
            last_seen_at=now,
            idle_expires_at=now + idle,
            absolute_expires_at=now + absolute,
        )
    )
    db.execute(delete(AuthSession).where(AuthSession.absolute_expires_at < now))  # housekeeping
    return token


def end_session(db: Session, token: str | None):
    if token:
        db.execute(delete(AuthSession).where(AuthSession.token_digest == _digest(token)))


def revoke_all(db: Session, user_id: str):
    db.execute(delete(AuthSession).where(AuthSession.user_id == user_id))


def load_session(db: Session, token: str | None) -> AuthSession | None:
    if not token or len(token) > 100:
        return None
    sess = db.get(AuthSession, _digest(token))
    if sess is None:
        return None
    now = utcnow()
    if now >= sess.idle_expires_at or now >= sess.absolute_expires_at or not sess.user.active:
        db.delete(sess)
        return None
    if now - sess.last_seen_at >= TOUCH_EVERY:
        idle, _ = LIFETIMES[sess.user.role]
        sess.last_seen_at = now
        sess.idle_expires_at = min(now + idle, sess.absolute_expires_at)
    return sess


def set_session_cookie(response, token: str):
    response.set_cookie(
        settings.session_cookie,
        token,
        httponly=True,
        samesite="lax",
        secure=settings.secure_cookies,
        path="/",
    )


def clear_session_cookie(response):
    response.delete_cookie(
        settings.session_cookie,
        path="/",
        secure=settings.secure_cookies,
        httponly=True,
        samesite="lax",
    )


# ---------- request dependencies ----------


def current_session(request: Request, db: Session = Depends(get_db)) -> AuthSession | None:
    if not hasattr(request.state, "auth"):
        sess = load_session(db, request.cookies.get(settings.session_cookie))
        request.state.auth = sess
        # Plain snapshot for templates: still usable on error pages after the DB session closed.
        request.state.viewer = (
            SimpleNamespace(
                id=sess.user.id,
                role=sess.user.role,
                display_name=sess.user.display_name,
                login=sess.user.login,
                csrf=sess.csrf_token,
            )
            if sess
            else None
        )
    return request.state.auth


def current_user(sess: AuthSession | None = Depends(current_session)) -> User | None:
    return sess.user if sess else None


def require_user(user: User | None = Depends(current_user)) -> User:
    if user is None:
        raise LoginRequired()
    return user


def require_role(*roles: str):
    def dep(user: User = Depends(require_user)) -> User:
        if user.role not in roles:
            raise HTTPException(403, "You don't have access to that page.")
        return user

    return dep


def expected_csrf(request: Request) -> str | None:
    viewer = getattr(request.state, "viewer", None)
    return viewer.csrf if viewer else getattr(request.state, "anon_csrf", None)


def _same_origin(request: Request) -> bool:
    origin = request.headers.get("origin") or request.headers.get("referer")
    if not origin or origin == "null":
        return origin is None
    host = request.headers.get("host", "")
    return urlsplit(origin).netloc == host


def csrf_protect(
    request: Request,
    csrf_token: str = Form(""),
    _sess: AuthSession | None = Depends(current_session),
):
    """Synchronizer token (session-bound; double-submit cookie before login) + Origin check."""
    expected = expected_csrf(request)
    if not expected or not csrf_token or not hmac.compare_digest(expected, csrf_token):
        raise HTTPException(403, "This form expired. Go back, reload the page and try again.")
    if not _same_origin(request):
        raise HTTPException(403, "Cross-site form submissions are not allowed.")


def safe_next(target: str | None, default: str) -> str:
    """Only allow local absolute paths as post-login redirects."""
    if target and target.startswith("/") and not target.startswith("//") and "\\" not in target:
        return target
    return default


def home_for(user: User) -> str:
    return {"admin": "/admin", "parent": "/parent", "student": "/practice"}[user.role]
