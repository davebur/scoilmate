"""ScoilMate preview: learn -> practise -> feedback, using draft sample content.

Content and anonymous ratings live in SQLite (versioned rows). No accounts yet: quiz
progress lives only in a signed, short-lived browser cookie.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import auth, content as content_mod
from .auth import LoginRequired, csrf_protect
from .config import settings
from .content import FEEDBACK_REASONS, Strand
from .db import get_db
from .views_accounts import router as accounts_router
from .web import PKG, render

ROOT = PKG.parent
COOKIE = 'scoilmate_practice'
COOKIE_MAX_AGE = 4 * 3600
# Per-process secret unless one is supplied: restarting the server simply resets practice runs.
_SECRET = os.environ.get('SCOILMATE_SECRET', '').encode() or secrets.token_bytes(32)
CSP = ("default-src 'self'; script-src 'none'; img-src 'self'; style-src 'self'; form-action 'self'; "
       "frame-ancestors 'none'; base-uri 'none'; object-src 'none'")

app = FastAPI(title='ScoilMate preview', docs_url=None, redoc_url=None, openapi_url=None,
              dependencies=[Depends(auth.current_session)])  # every page knows who is logged in
app.mount('/static/branding', StaticFiles(directory=ROOT / 'assets' / 'branding'), name='branding')
app.mount('/static/app', StaticFiles(directory=PKG / 'static'), name='appstatic')
app.include_router(accounts_router)


@app.middleware('http')
async def security_headers(request: Request, call_next):
    # Pre-login CSRF: random double-submit cookie; after login the token is bound to the session.
    token = request.cookies.get(settings.csrf_cookie)
    fresh = not token or len(token) > 100
    request.state.anon_csrf = secrets.token_urlsafe(32) if fresh else token
    response = await call_next(request)
    if fresh:
        response.set_cookie(settings.csrf_cookie, request.state.anon_csrf, httponly=True, samesite='lax',
                            secure=settings.secure_cookies, path='/')
    h = response.headers
    h.setdefault('X-Content-Type-Options', 'nosniff')
    h.setdefault('Referrer-Policy', 'same-origin')
    h.setdefault('X-Frame-Options', 'DENY')
    h.setdefault('Content-Security-Policy', CSP)
    if not request.url.path.startswith('/static/'):
        h.setdefault('Cache-Control', 'no-store')
    if settings.secure_cookies:
        h.setdefault('Strict-Transport-Security', 'max-age=31536000')
    return response


@app.exception_handler(LoginRequired)
async def login_required(request: Request, exc: LoginRequired):
    target = request.url.path if request.method == 'GET' else ''
    return RedirectResponse('/login' + (f'?next={target}' if target else ''), status_code=303)


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    if request.url.path.startswith('/static/'):
        return HTMLResponse('Not found', status_code=exc.status_code)
    message = exc.detail if exc.status_code < 500 else 'Something went wrong'
    return render(request, 'error.html', status_code=exc.status_code, status=exc.status_code, message=message)


# ---- signed practice-state cookie (no server storage) ----

def _sign(payload: bytes) -> str:
    mac = hmac.new(_SECRET, payload, hashlib.sha256).digest()[:16]
    return base64.urlsafe_b64encode(mac + payload).decode()


def _unsign(value: str | None) -> dict:
    if not value:
        return {}
    try:
        raw = base64.urlsafe_b64decode(value.encode())
        mac, payload = raw[:16], raw[16:]
        if not hmac.compare_digest(mac, hmac.new(_SECRET, payload, hashlib.sha256).digest()[:16]):
            return {}
        state = json.loads(payload)
        return state if isinstance(state, dict) else {}
    except (ValueError, json.JSONDecodeError):
        return {}


def _state(request: Request) -> dict:
    return _unsign(request.cookies.get(COOKIE))


def _save(response, state: dict):
    payload = json.dumps(state, separators=(',', ':')).encode()
    response.set_cookie(COOKIE, _sign(payload), max_age=COOKIE_MAX_AGE, httponly=True,
                        samesite='strict', path='/practice')
    return response


# ---- helpers: a strand's current practice content, from the database ----

class _StrandContent:
    def __init__(self, db: Session, strand: Strand):
        topics = content_mod.strand_topics(db, strand)
        self.question_versions = [v for t in topics for v in content_mod.topic_versions(db, t, 'question')]
        self.lesson_versions = [v for t in topics for v in content_mod.topic_versions(db, t, 'lesson')]
        self.questions = [dict(v.data, id=v.item.slug, version=v.version) for v in self.question_versions]
        self.lessons = {v.item.slug: dict(v.data, id=v.item.slug, version=v.version) for v in self.lesson_versions}


def _strands(db: Session) -> list[Strand]:
    return [s for s in content_mod.all_strands() if content_mod.strand_topics(db, s)]


def _strand(db: Session, slug: str):
    strand = Strand.from_slug(slug)
    if strand is None or strand not in _strands(db):
        raise HTTPException(404, 'Unknown practice area')
    return strand, _StrandContent(db, strand)


def _question_at(sc: _StrandContent, n: int):
    if not 1 <= n <= len(sc.questions):
        raise HTTPException(404, 'No such question')
    return sc.questions[n - 1], sc.question_versions[n - 1], len(sc.questions)


def _results(state: dict, strand) -> dict:
    run = state.get(strand.slug)
    return run if isinstance(run, dict) else {}


def _summary(results: dict, total: int) -> dict:
    answered = len(results)
    correct = sum(1 for r in results.values() if r.get('c'))
    independent = sum(1 for r in results.values() if r.get('c') and not r.get('h'))
    return {'answered': answered, 'total': total, 'correct': correct,
            'independent': independent, 'assisted': correct - independent}


# ---- routes ----

@app.get('/health')
def health():
    return {'status': 'ok', 'app': 'ScoilMate', 'mode': 'preview'}


@app.get('/', response_class=HTMLResponse)
def landing(request: Request, db: Session = Depends(get_db)):
    return render(request, 'landing.html', strands=_strands(db))


@app.get('/practice', response_class=HTMLResponse)
def practice_home(request: Request, db: Session = Depends(get_db)):
    state = _state(request)
    areas = []
    for s in _strands(db):
        sc = _StrandContent(db, s)
        areas.append({'strand': s, 'summary': _summary(_results(state, s), len(sc.questions)),
                      'lessons': len(sc.lessons)})
    return render(request, 'practice_home.html', areas=areas)


@app.get('/practice/{slug}', response_class=HTMLResponse)
def strand_home(request: Request, slug: str, db: Session = Depends(get_db)):
    strand, sc = _strand(db, slug)
    return render(request, 'strand.html', strand=strand, lessons=list(sc.lessons.values()),
                  summary=_summary(_results(_state(request), strand), len(sc.questions)))


@app.get('/practice/{slug}/lesson/{lesson_id}', response_class=HTMLResponse)
def lesson(request: Request, slug: str, lesson_id: str, back: int = 0, thanks: int = 0,
           db: Session = Depends(get_db)):
    strand, sc = _strand(db, slug)
    item = sc.lessons.get(lesson_id)
    if item is None:
        raise HTTPException(404, 'No such lesson')
    back = back if 1 <= back <= len(sc.questions) else 0
    rated = f"l:{lesson_id}:{item['version']}" in (_state(request).get('_rated') or [])
    return render(request, 'lesson.html', strand=strand, lesson=item, back=back,
                  thanks=bool(thanks), rated=rated)


@app.get('/practice/{slug}/q/{n}', response_class=HTMLResponse)
def question(request: Request, slug: str, n: int, hints: int = 0, thanks: int = 0,
             db: Session = Depends(get_db)):
    strand, sc = _strand(db, slug)
    q, v, total = _question_at(sc, n)
    public = content_mod.public_question(v, hints)
    return render(request, 'question.html', strand=strand, q=public, n=n, total=total,
                  hints_shown=len(public['hints']), thanks=bool(thanks))


@app.post('/practice/{slug}/q/{n}', response_class=HTMLResponse, dependencies=[Depends(csrf_protect)])
def answer(request: Request, slug: str, n: int, option: str = Form(''), hints_used: int = Form(0),
           db: Session = Depends(get_db)):
    strand, sc = _strand(db, slug)
    q, v, total = _question_at(sc, n)
    if not option:
        public = content_mod.public_question(v, hints_used)
        return render(request, 'question.html', strand=strand, q=public, n=n, total=total,
                      hints_shown=len(public['hints']), error='Choose an answer before checking.')
    try:
        result = content_mod.grade(v, option)
    except ValueError:
        raise HTTPException(400, 'Invalid answer option')
    hints_used = max(0, min(hints_used, len(q['hints'])))
    state = _state(request)
    run = _results(state, strand)
    first_attempt = q['id'] not in run
    if first_attempt:  # the first answer counts; retries are practice only
        run[q['id']] = {'c': result['correct'], 'h': hints_used, 'v': q['version']}
        state[strand.slug] = run
    lesson_item = sc.lessons.get(q['help_lesson_id'])
    rated = f"q:{q['id']}:{q['version']}" in (state.get('_rated') or [])
    response = render(request, 'feedback.html', strand=strand, q=q, n=n, total=total, result=result,
                      hints_used=hints_used, first_attempt=first_attempt, lesson=lesson_item,
                      rated=rated)
    return _save(response, state) if first_attempt else response


@app.get('/practice/{slug}/summary', response_class=HTMLResponse)
def summary(request: Request, slug: str, thanks: int = 0, db: Session = Depends(get_db)):
    strand, sc = _strand(db, slug)
    results = _results(_state(request), strand)
    rows = []
    for i, q in enumerate(sc.questions, 1):
        r = results.get(q['id'])
        status = 'not tried' if r is None else ('correct' if r['c'] and not r['h'] else
                                                'correct with hints' if r['c'] else 'review')
        rows.append({'n': i, 'prompt': q['prompt'], 'status': status,
                     'lesson': sc.lessons.get(q['help_lesson_id'])})
    return render(request, 'summary.html', strand=strand, rows=rows,
                  summary=_summary(results, len(sc.questions)), thanks=bool(thanks))


@app.post('/practice/{slug}/rate', dependencies=[Depends(csrf_protect)])
def rate(request: Request, slug: str, item_type: str = Form(...), item_id: str = Form(...),
         rating: str = Form(...), reason: str = Form(''), n: int = Form(0), db: Session = Depends(get_db)):
    """Thumbs up/down on a question or lesson. Anonymous; one rating per item per browser run."""
    strand, sc = _strand(db, slug)
    if rating not in ('up', 'down') or (reason and reason not in FEEDBACK_REASONS):
        raise HTTPException(400, 'Invalid rating')
    if item_type == 'question':
        version = next((v for v in sc.question_versions if v.item.slug == item_id), None)
    elif item_type == 'lesson':
        version = next((v for v in sc.lesson_versions if v.item.slug == item_id), None)
    else:
        version = None
    if version is None:
        raise HTTPException(404, 'No such item')
    state = _state(request)
    rated = state.get('_rated') if isinstance(state.get('_rated'), list) else []
    key = f"{item_type[0]}:{item_id}:{version.version}"
    if key not in rated:
        content_mod.record_rating(db, version, rating, reason or None)
        rated.append(key)
        state['_rated'] = rated[-200:]
    total = len(sc.questions)
    if item_type == 'lesson':
        target = f'/practice/{strand.slug}/lesson/{item_id}?thanks=1'
        if 1 <= n <= total:
            target += f'&back={n}'
    else:
        target = (f'/practice/{strand.slug}/q/{n + 1}?thanks=1' if 1 <= n < total
                  else f'/practice/{strand.slug}/summary?thanks=1')
    return _save(RedirectResponse(target, status_code=303), state)


@app.post('/practice/{slug}/reset', dependencies=[Depends(csrf_protect)])
def reset(request: Request, slug: str, db: Session = Depends(get_db)):
    strand, _ = _strand(db, slug)
    state = _state(request)
    state.pop(strand.slug, None)
    return _save(RedirectResponse(f'/practice/{strand.slug}', status_code=303), state)
