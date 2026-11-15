"""Template rendering shared by all views."""

from __future__ import annotations

from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates

from . import auth
from .accounts import LEVELS, TRACKS
from .config import settings
from .content import FEEDBACK_REASONS, SUBJECTS, TRACK_NAMES

PKG = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=PKG / "templates")  # autoescape on for .html
templates.env.globals.update(
    SUBJECTS=SUBJECTS,
    TRACKS=TRACKS,
    LEVELS=LEVELS,
    TRACK_NAMES=TRACK_NAMES,
    REASONS=FEEDBACK_REASONS,
)


def fmt_date(value, with_time=False):
    if value is None:
        return "—"
    return value.strftime("%a %d %b %Y" + (" %H:%M UTC" if with_time else ""))


templates.env.filters["date"] = fmt_date


def render(request: Request, name: str, status_code: int = 200, **ctx):
    ctx.setdefault("reasons", FEEDBACK_REASONS)
    ctx.update(
        user=getattr(request.state, "viewer", None),
        csrf_token=auth.expected_csrf(request) or "",
        draft_practice=settings.allow_draft_practice,
    )
    return templates.TemplateResponse(request, name, ctx, status_code=status_code)
