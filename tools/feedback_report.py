"""Summarise anonymous thumbs up/down ratings from the database (admins also have /admin/ratings).

Usage: .venv/bin/python tools/feedback_report.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import case, func, select  # noqa: E402

from scoilmate import db  # noqa: E402
from scoilmate.models import ContentItem, ContentRating, ContentVersion  # noqa: E402

with db.session_scope() as s:
    rows = s.execute(
        select(ContentItem.kind, ContentItem.slug, ContentVersion.version,
               func.sum(case((ContentRating.rating == 'up', 1), else_=0)),
               func.sum(case((ContentRating.rating == 'down', 1), else_=0)),
               func.group_concat(ContentRating.reason))
        .join(ContentVersion, ContentRating.version_id == ContentVersion.id).join(ContentItem)
        .group_by(ContentVersion.id).order_by(func.sum(case((ContentRating.rating == 'down', 1), else_=0)).desc())
    ).all()
if not rows:
    sys.exit('No ratings yet.')
print(f"{'type':8} {'id':22} {'v':>2} {'up':>3} {'down':>4}  reasons")
for kind, slug, version, up, down, reasons in rows:
    print(f"{kind:8} {slug:22} {version:>2} {up:>3} {down:>4}  {reasons or ''}")
