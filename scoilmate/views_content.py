"""Admin content workflow (draft -> reviewed -> published -> retired), ratings queue, wellbeing page.

Every edit inserts a new immutable version; publishing retires the previously published one.
"""
from __future__ import annotations

import re
from datetime import datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import case, func, select, update
from sqlalchemy.orm import Session

from . import accounts, content
from .auth import csrf_protect, require_role
from .content import Strand
from .db import get_db, utcnow
from .models import ContentItem, ContentRating, ContentVersion, Topic, User
from .web import render

router = APIRouter()
admin_only = require_role('admin')
SLUG_RE = re.compile(r'^[a-z0-9][a-z0-9-]{1,62}$')
LETTERS = 'ABCDE'
MAX_TEXT = 5000


def see_other(url: str):
    return RedirectResponse(url, status_code=303)


def item_or_404(db: Session, slug: str) -> ContentItem:
    item = db.scalar(select(ContentItem).where(ContentItem.slug == slug))
    if item is None:
        raise HTTPException(404, 'No such content item')
    return item


def version_or_404(item: ContentItem, version: int) -> ContentVersion:
    v = next((v for v in item.versions if v.version == version), None)
    if v is None:
        raise HTTPException(404, 'No such version')
    return v


def _text(form: dict, key: str, required=True, limit=MAX_TEXT) -> str:
    value = (form.get(key) or '').replace('\r\n', '\n').strip()
    if required and not value:
        raise ValueError(f'{key.replace("_", " ").capitalize()} is required.')
    if len(value) > limit:
        raise ValueError(f'{key} is too long (max {limit} characters).')
    return value


def body_from_form(kind: str, form: dict, topic: Topic, previous: dict | None) -> tuple[str, dict]:
    """Build and validate a version body from the editor form. Returns (title, body)."""
    if kind == 'lesson':
        title = _text(form, 'title', limit=160)
        return title, {'title': title, 'body': _text(form, 'body')}
    options = [{'id': L, 'text': _text(form, f'option_{L}', required=False, limit=300)} for L in LETTERS]
    options = [o for o in options if o['text']]
    body = dict(previous or {})  # keep editorial metadata (levels, year guidance, provenance...)
    body.update({
        'prompt': _text(form, 'prompt', limit=300), 'options': options,
        'correct_option_id': form.get('correct_option_id', ''), 'explanation': _text(form, 'explanation'),
        'hints': [h for h in (_text(form, f'hint_{i}', required=False, limit=500) for i in (1, 2, 3)) if h],
        'help_lesson_id': form.get('help_lesson_id') or None,
        'language': content.SUBJECTS[topic.subject]['lang'],
    })
    body.setdefault('levels', ['common'] if topic.subject == 'history' else ['ordinary', 'higher'])
    body.setdefault('provenance', 'Original ScoilMate content written in the admin editor.')
    content.validate_question_body(body)
    return body['prompt'], body


def _lessons_for(db: Session, topic: Topic) -> list[ContentItem]:
    return list(db.scalars(select(ContentItem).join(Topic).where(
        ContentItem.kind == 'lesson', Topic.subject == topic.subject, Topic.track == topic.track)
        .order_by(ContentItem.slug)))


def _audit(db, user, action, item, v=None):
    accounts.audit(db, user, action, None, f'{item.slug}' + (f' v{v.version}' if v else ''))


# ---------------- content list / create ----------------

@router.get('/admin/content')
def content_home(request: Request, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    topics = db.scalars(select(Topic).order_by(Topic.subject, Topic.track, Topic.ordinal, Topic.id)).all()
    items = db.scalars(select(ContentItem).order_by(ContentItem.kind, ContentItem.slug)).all()
    by_topic = {t.id: [] for t in topics}
    for i in items:
        latest = i.versions[-1]
        live = content.current_version(i, include_drafts=False)
        by_topic[i.topic_id].append({'item': i, 'latest': latest, 'live': live})
    return render(request, 'admin_content.html', topics=topics, by_topic=by_topic, strands=content.all_strands())


@router.post('/admin/topics/new', dependencies=[Depends(csrf_protect)])
def new_topic(strand: str = Form(''), slug: str = Form(''), title: str = Form(''), user: User = Depends(admin_only),
              db: Session = Depends(get_db)):
    st = Strand.from_slug(strand)
    slug, title = slug.strip().lower(), title.strip()
    if st is None or not SLUG_RE.match(slug) or not 1 <= len(title) <= 160:
        raise HTTPException(400, 'Choose a subject, a short slug (letters, numbers, dashes) and a title.')
    if db.scalar(select(Topic).where(Topic.slug == slug)):
        raise HTTPException(400, 'That topic slug already exists.')
    db.add(Topic(slug=slug, subject=st.subject, track=st.track, title=title, ordinal=100))
    accounts.audit(db, user, 'topic_created', None, slug)
    return see_other('/admin/content')


@router.get('/admin/content/new')
def new_item_form(request: Request, kind: str = 'question', topic: str = '', user: User = Depends(admin_only),
                  db: Session = Depends(get_db)):
    if kind not in ('question', 'lesson'):
        raise HTTPException(404, 'Unknown content type')
    t = db.scalar(select(Topic).where(Topic.slug == topic))
    if t is None:
        raise HTTPException(404, 'Choose a topic first')
    return render(request, 'content_edit.html', kind=kind, topic=t, item=None, data={}, form={},
                  lessons=_lessons_for(db, t), letters=LETTERS)


@router.post('/admin/content/new', dependencies=[Depends(csrf_protect)])
async def new_item(request: Request, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    form = {k: v for k, v in (await request.form()).items() if isinstance(v, str)}
    kind = form.get('kind')
    topic = db.scalar(select(Topic).where(Topic.slug == form.get('topic', '')))
    if kind not in ('question', 'lesson') or topic is None:
        raise HTTPException(400, 'Unknown content type or topic')
    try:
        slug = form.get('slug', '').strip().lower()
        if not SLUG_RE.match(slug):
            raise ValueError('Slug: 2-63 lower-case letters, numbers and dashes.')
        if db.scalar(select(ContentItem).where(ContentItem.slug == slug)):
            raise ValueError('That slug is already used.')
        title, body = body_from_form(kind, form, topic, None)
    except ValueError as exc:
        return render(request, 'content_edit.html', status_code=400, kind=kind, topic=topic, item=None, data={},
                      form=form, error=str(exc), lessons=_lessons_for(db, topic), letters=LETTERS)
    item = ContentItem(slug=slug, kind=kind, topic_id=topic.id)
    db.add(item)
    db.flush()
    v = ContentVersion(item_id=item.id, version=1, status='draft', title=title, body=content.canonical(body),
                       created_by=user.id, created_at=utcnow())
    db.add(v)
    _audit(db, user, 'content_created', item, v)
    return see_other(f'/admin/content/{slug}')


# ---------------- item detail / edit / review / publish / retire ----------------

def _item_page(request, db, item, shown, status_code=200, error=None, form=None):
    ratings = dict(db.execute(select(ContentRating.version_id, func.count()).where(
        ContentRating.version_id.in_([x.id for x in item.versions]), ContentRating.rating == 'down')
        .group_by(ContentRating.version_id)).all())
    return render(request, 'content_item.html', status_code=status_code, item=item, shown=shown, data=shown.data,
                  form=form or _form_from(item.kind, shown.data), error=error,
                  live=content.current_version(item, include_drafts=False), downs=ratings,
                  lessons=_lessons_for(db, item.topic), letters=LETTERS,
                  lang=content.SUBJECTS[item.topic.subject]['lang'], today=utcnow().strftime('%Y-%m-%d'))


def _form_from(kind: str, data: dict) -> dict:
    """Prefill the editor from a stored version."""
    if kind == 'lesson':
        return {'title': data.get('title', ''), 'body': data.get('body', '')}
    form = {'prompt': data.get('prompt', ''), 'explanation': data.get('explanation', ''),
            'correct_option_id': data.get('correct_option_id', ''), 'help_lesson_id': data.get('help_lesson_id') or ''}
    for o in data.get('options', []):
        form[f"option_{o['id']}"] = o['text']
    for n, h in enumerate(data.get('hints', []), 1):
        form[f'hint_{n}'] = h
    return form


@router.get('/admin/content/{slug}')
def item_page(request: Request, slug: str, v: int = 0, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    item = item_or_404(db, slug)
    shown = version_or_404(item, v) if v else item.versions[-1]
    return _item_page(request, db, item, shown)


@router.get('/admin/content/{slug}/v/{version}/preview')
def preview(request: Request, slug: str, version: int, user: User = Depends(admin_only),
            db: Session = Depends(get_db)):
    """Show one version exactly as a student would see it (nothing is recorded)."""
    item = item_or_404(db, slug)
    v = version_or_404(item, version)
    q = content.public_question(v, hints_shown=3) if item.kind == 'question' else None
    return render(request, 'content_preview.html', item=item, v=v, q=q, result=None,
                  lang=content.SUBJECTS[item.topic.subject]['lang'])


@router.post('/admin/content/{slug}/v/{version}/preview', dependencies=[Depends(csrf_protect)])
def preview_check(request: Request, slug: str, version: int, option: str = Form(''),
                  user: User = Depends(admin_only), db: Session = Depends(get_db)):
    """Grade a preview answer to check the feedback a student gets. Not stored anywhere."""
    item = item_or_404(db, slug)
    v = version_or_404(item, version)
    if item.kind != 'question':
        raise HTTPException(404, 'Only questions can be answered')
    q = content.public_question(v, hints_shown=3)
    if not option:
        result, error = None, 'Choose an answer first.'
    else:
        try:
            result, error = content.grade(v, option), None
        except ValueError:
            raise HTTPException(400, 'That is not one of the options')
    return render(request, 'content_preview.html', item=item, v=v, q=q, result=result, error=error,
                  lang=content.SUBJECTS[item.topic.subject]['lang'])


@router.post('/admin/content/{slug}/edit', dependencies=[Depends(csrf_protect)])
async def edit_item(request: Request, slug: str, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    item = item_or_404(db, slug)
    form = {k: v for k, v in (await request.form()).items() if isinstance(v, str)}
    latest = item.versions[-1]
    try:
        title, body = body_from_form(item.kind, form, item.topic, latest.data)
    except ValueError as exc:
        return _item_page(request, db, item, latest, status_code=400, error=str(exc), form=form)
    if content.canonical(body) == latest.body and title == latest.title:
        return see_other(f'/admin/content/{slug}?unchanged=1')
    v = ContentVersion(item_id=item.id, version=latest.version + 1, status='draft', title=title,
                       body=content.canonical(body), created_by=user.id, created_at=utcnow())
    db.add(v)
    _audit(db, user, 'content_edited', item, v)
    return see_other(f'/admin/content/{slug}')


@router.post('/admin/content/{slug}/v/{version}/review', dependencies=[Depends(csrf_protect)])
def review(slug: str, version: int, reviewer_name: str = Form(''), review_date: str = Form(''),
           note: str = Form(''), user: User = Depends(admin_only), db: Session = Depends(get_db)):
    """Record who checked a draft (e.g. a subject teacher), when, and what they checked."""
    item = item_or_404(db, slug)
    v = version_or_404(item, version)
    reviewer_name, note = reviewer_name.strip(), note.replace('\r\n', '\n').strip()
    if v.status != 'draft':
        raise HTTPException(400, 'Only draft versions can be reviewed.')
    if not 2 <= len(reviewer_name) <= 80:
        raise HTTPException(400, "Give the reviewer's name (2-80 characters).")
    if not 5 <= len(note) <= 500:
        raise HTTPException(400, 'Write a short review note: what was checked (5-500 characters).')
    now = utcnow()
    try:
        when = datetime.strptime(review_date, '%Y-%m-%d') if review_date else now
    except ValueError:
        raise HTTPException(400, 'Review date must look like 2026-11-15.')
    if when.date() > now.date() or when.date() < v.created_at.date():
        raise HTTPException(400, 'The review date must be between the day this version was written and today.')
    v.status, v.reviewed_by, v.reviewed_at = 'reviewed', user.id, when
    v.reviewer_name, v.review_note = reviewer_name, note
    _audit(db, user, 'content_reviewed', item, v)
    return see_other(f'/admin/content/{slug}?v={version}')


@router.post('/admin/content/{slug}/v/{version}/publish', dependencies=[Depends(csrf_protect)])
def publish(slug: str, version: int, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    item = item_or_404(db, slug)
    v = version_or_404(item, version)
    if v.status != 'reviewed':
        raise HTTPException(400, 'Record a review before publishing.')
    if item.kind == 'question':
        content.validate_question_body(v.data)
    now = utcnow()
    for old in item.versions:  # a newer publication supersedes older ones
        if old.status in ('published', 'draft', 'reviewed') and old.version < v.version:
            old.status, old.retired_at = 'retired', now
    v.status, v.published_at = 'published', now
    _audit(db, user, 'content_published', item, v)
    return see_other(f'/admin/content/{slug}?v={version}')


@router.post('/admin/content/{slug}/retire', dependencies=[Depends(csrf_protect)])
def retire(slug: str, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    item = item_or_404(db, slug)
    now = utcnow()
    for v in item.versions:
        if v.status != 'retired':
            v.status, v.retired_at = 'retired', now
    _audit(db, user, 'content_retired', item)
    return see_other(f'/admin/content/{slug}')


# ---------------- ratings queue ----------------

# Most serious first: a 'wrong' report outranks 'unclear', etc. Used after the 👎 count.
REASON_ORDER = ('wrong', 'unclear', 'too_hard', 'too_easy', 'helpful')


def ratings_rows(db: Session, show: str = 'open') -> list[dict]:
    """One row per rated version: 👎/👍 counts and down-vote reasons, sorted by 👎 then reason."""
    down = func.sum(case((ContentRating.rating == 'down', 1), else_=0))
    up = func.sum(case((ContentRating.rating == 'up', 1), else_=0))
    open_ = func.sum(case((ContentRating.resolved_at.is_(None), 1), else_=0))
    q = (select(ContentRating.version_id, down, up, open_, func.max(ContentRating.at),
                func.max(ContentRating.resolved_version), func.max(ContentRating.resolved_at))
         .group_by(ContentRating.version_id))
    rows = []
    for version_id, downs, ups, n_open, last, resolved_version, resolved_at in db.execute(q).all():
        if show != 'all' and not n_open:
            continue
        v = db.get(ContentVersion, version_id)
        reasons = dict(db.execute(select(ContentRating.reason, func.count()).where(
            ContentRating.version_id == version_id, ContentRating.reason.is_not(None),
            ContentRating.rating == 'down').group_by(ContentRating.reason)).all())
        top = min((REASON_ORDER.index(r) for r in reasons), default=len(REASON_ORDER))
        rows.append({'v': v, 'down': downs, 'up': ups, 'open': n_open, 'last': last, 'top_reason': top,
                     'reasons': sorted(reasons.items(), key=lambda kv: REASON_ORDER.index(kv[0])),
                     'resolved_version': resolved_version, 'resolved_at': resolved_at,
                     'later': [x for x in v.item.versions if x.version > v.version]})
    rows.sort(key=lambda r: (-r['down'], r['top_reason'], r['v'].item.slug, r['v'].version))
    return rows


@router.get('/admin/ratings')
def ratings_queue(request: Request, show: str = 'open', user: User = Depends(admin_only),
                  db: Session = Depends(get_db)):
    show = 'all' if show == 'all' else 'open'
    return render(request, 'admin_ratings.html', rows=ratings_rows(db, show), show=show)


@router.post('/admin/ratings/{version_id}/resolve', dependencies=[Depends(csrf_protect)])
def resolve(version_id: int, resolved_version: str = Form(''), user: User = Depends(admin_only),
            db: Session = Depends(get_db)):
    """Close the open ratings on a version, optionally naming the version that fixed it."""
    v = db.get(ContentVersion, version_id)
    if v is None:
        raise HTTPException(404, 'No such version')
    fixed_by = None
    if resolved_version:
        if not resolved_version.isdecimal() or not any(
                x.version == int(resolved_version) and x.version > v.version for x in v.item.versions):
            raise HTTPException(400, 'Choose a later version of this item, or "no change needed".')
        fixed_by = int(resolved_version)
    db.execute(update(ContentRating).where(ContentRating.version_id == v.id, ContentRating.resolved_at.is_(None))
               .values(resolved_at=utcnow(), resolved_version=fixed_by))
    accounts.audit(db, user, 'ratings_resolved', None,
                   f'{v.item.slug} v{v.version} ' + (f'resolved by v{fixed_by}' if fixed_by else 'no change needed'))
    return see_other('/admin/ratings')


# ---------------- public wellbeing page ----------------

@router.get('/wellbeing')
def wellbeing(request: Request):
    return render(request, 'wellbeing.html')
