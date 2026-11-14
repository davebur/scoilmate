"""ScoilMate preview: learn -> practise -> feedback, using draft sample content.

No accounts, no database, no student data. Quiz progress lives only in a
signed, short-lived browser cookie and is lost when the server restarts.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import content as content_mod

PKG = Path(__file__).resolve().parent
ROOT = PKG.parent
COOKIE = 'scoilmate_practice'
COOKIE_MAX_AGE = 4 * 3600
# Anonymous content ratings (no identity, no free text). instance/ is git-ignored.
FEEDBACK_FILE = Path(os.environ.get('SCOILMATE_FEEDBACK_FILE', ROOT / 'instance' / 'content-feedback.jsonl'))
FEEDBACK_REASONS = {
    'unclear': 'Confusing or unclear',
    'wrong': 'I think something is wrong',
    'too_easy': 'Too easy',
    'too_hard': 'Too hard',
    'helpful': 'Really helpful',
}
_feedback_lock = threading.Lock()
# Per-process secret unless one is supplied: restarting the server simply resets practice runs.
_SECRET = os.environ.get('SCOILMATE_SECRET', '').encode() or secrets.token_bytes(32)

app = FastAPI(title='ScoilMate preview', docs_url=None, redoc_url=None, openapi_url=None)
app.mount('/static/branding', StaticFiles(directory=ROOT / 'assets' / 'branding'), name='branding')
app.mount('/static/app', StaticFiles(directory=PKG / 'static'), name='appstatic')
templates = Jinja2Templates(directory=PKG / 'templates')


@app.middleware('http')
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault('X-Content-Type-Options', 'nosniff')
    response.headers.setdefault('Referrer-Policy', 'same-origin')
    response.headers.setdefault('X-Frame-Options', 'DENY')
    response.headers.setdefault(
        'Content-Security-Policy',
        "default-src 'self'; img-src 'self'; style-src 'self'; form-action 'self'; frame-ancestors 'none'")
    return response


from starlette.exceptions import HTTPException as StarletteHTTPException


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    if request.url.path.startswith('/static/'):
        return HTMLResponse('Not found', status_code=exc.status_code)
    message = exc.detail if exc.status_code < 500 else 'Something went wrong'
    response = templates.TemplateResponse(request, 'error.html',
                                          {'status': exc.status_code, 'message': message},
                                          status_code=exc.status_code)
    return response


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


# ---- helpers ----

def _content():
    return content_mod.load()


def _strand(slug: str):
    strand = _content().strands.get(slug)
    if strand is None:
        raise HTTPException(404, 'Unknown practice area')
    return strand


def _question_at(strand, n: int):
    qs = _content().strand_questions(strand)
    if not 1 <= n <= len(qs):
        raise HTTPException(404, 'No such question')
    return qs[n - 1], len(qs)


def _results(state: dict, strand) -> dict:
    run = state.get(strand.slug)
    return run if isinstance(run, dict) else {}


def _summary(results: dict, total: int) -> dict:
    answered = len(results)
    correct = sum(1 for r in results.values() if r.get('c'))
    independent = sum(1 for r in results.values() if r.get('c') and not r.get('h'))
    return {'answered': answered, 'total': total, 'correct': correct,
            'independent': independent, 'assisted': correct - independent}


def render(request: Request, name: str, **ctx):
    ctx.setdefault('reasons', FEEDBACK_REASONS)
    return templates.TemplateResponse(request, name, ctx)


def record_feedback(item_type: str, item: dict, rating: str, reason: str | None):
    entry = {'at': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'type': item_type,
             'id': item['id'], 'version': item['version'], 'rating': rating, 'reason': reason}
    with _feedback_lock:
        FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
        with FEEDBACK_FILE.open('a', encoding='utf-8') as fh:
            fh.write(json.dumps(entry) + '\n')


# ---- routes ----

@app.get('/health')
def health():
    return {'status': 'ok', 'app': 'ScoilMate', 'mode': 'preview'}


@app.get('/', response_class=HTMLResponse)
def landing(request: Request):
    return render(request, 'landing.html', strands=list(_content().strands.values()))


@app.get('/practice', response_class=HTMLResponse)
def practice_home(request: Request):
    c, state = _content(), _state(request)
    areas = [{'strand': s, 'summary': _summary(_results(state, s), len(c.strand_questions(s))),
              'lessons': len(c.strand_lessons(s))} for s in c.strands.values()]
    return render(request, 'practice_home.html', areas=areas)


@app.get('/practice/{slug}', response_class=HTMLResponse)
def strand_home(request: Request, slug: str):
    strand, c = _strand(slug), _content()
    qs = c.strand_questions(strand)
    return render(request, 'strand.html', strand=strand, lessons=c.strand_lessons(strand),
                  summary=_summary(_results(_state(request), strand), len(qs)))


@app.get('/practice/{slug}/lesson/{lesson_id}', response_class=HTMLResponse)
def lesson(request: Request, slug: str, lesson_id: str, back: int = 0, thanks: int = 0):
    strand, c = _strand(slug), _content()
    item = c.lessons.get(lesson_id)
    if item is None or (item['subject'], item['track']) != (strand.subject, strand.track):
        raise HTTPException(404, 'No such lesson')
    qs = c.strand_questions(strand)
    back = back if 1 <= back <= len(qs) else 0
    rated = f"l:{lesson_id}:{item['version']}" in (_state(request).get('_rated') or [])
    return render(request, 'lesson.html', strand=strand, lesson=item, back=back,
                  thanks=bool(thanks), rated=rated)


@app.get('/practice/{slug}/q/{n}', response_class=HTMLResponse)
def question(request: Request, slug: str, n: int, hints: int = 0, thanks: int = 0):
    strand = _strand(slug)
    q, total = _question_at(strand, n)
    public = _content().public_question(q, hints)
    return render(request, 'question.html', strand=strand, q=public, n=n, total=total,
                  hints_shown=len(public['hints']), thanks=bool(thanks))


@app.post('/practice/{slug}/q/{n}', response_class=HTMLResponse)
def answer(request: Request, slug: str, n: int, option: str = Form(''), hints_used: int = Form(0)):
    strand = _strand(slug)
    q, total = _question_at(strand, n)
    if not option:
        public = _content().public_question(q, hints_used)
        return render(request, 'question.html', strand=strand, q=public, n=n, total=total,
                      hints_shown=len(public['hints']), error='Choose an answer before checking.')
    try:
        result = _content().grade(q['id'], option)
    except ValueError:
        raise HTTPException(400, 'Invalid answer option')
    hints_used = max(0, min(hints_used, len(q['hints'])))
    state = _state(request)
    run = _results(state, strand)
    first_attempt = q['id'] not in run
    if first_attempt:  # the first answer counts; retries are practice only
        run[q['id']] = {'c': result['correct'], 'h': hints_used, 'v': q['version']}
        state[strand.slug] = run
    lesson_item = _content().lessons[q['help_lesson_id']]
    rated = f"q:{q['id']}:{q['version']}" in (state.get('_rated') or [])
    response = render(request, 'feedback.html', strand=strand, q=q, n=n, total=total, result=result,
                      hints_used=hints_used, first_attempt=first_attempt, lesson=lesson_item,
                      rated=rated)
    return _save(response, state) if first_attempt else response


@app.get('/practice/{slug}/summary', response_class=HTMLResponse)
def summary(request: Request, slug: str, thanks: int = 0):
    strand, c = _strand(slug), _content()
    qs = c.strand_questions(strand)
    results = _results(_state(request), strand)
    rows = []
    for i, q in enumerate(qs, 1):
        r = results.get(q['id'])
        status = 'not tried' if r is None else ('correct' if r['c'] and not r['h'] else
                                                'correct with hints' if r['c'] else 'review')
        rows.append({'n': i, 'prompt': q['prompt'], 'status': status,
                     'lesson': c.lessons[q['help_lesson_id']]})
    return render(request, 'summary.html', strand=strand, rows=rows,
                  summary=_summary(results, len(qs)), thanks=bool(thanks))


@app.post('/practice/{slug}/rate')
def rate(request: Request, slug: str, item_type: str = Form(...), item_id: str = Form(...),
         rating: str = Form(...), reason: str = Form(''), n: int = Form(0)):
    """Thumbs up/down on a question or lesson. Anonymous; one rating per item per browser run."""
    strand, c = _strand(slug), _content()
    if rating not in ('up', 'down') or (reason and reason not in FEEDBACK_REASONS):
        raise HTTPException(400, 'Invalid rating')
    pool = c.questions if item_type == 'question' else c.lessons if item_type == 'lesson' else None
    item = pool.get(item_id) if pool is not None else None
    if item is None or (item['subject'], item['track']) != (strand.subject, strand.track):
        raise HTTPException(404, 'No such item')
    state = _state(request)
    rated = state.get('_rated') if isinstance(state.get('_rated'), list) else []
    key = f"{item_type[0]}:{item_id}:{item['version']}"
    if key not in rated:
        record_feedback(item_type, item, rating, reason or None)
        rated.append(key)
        state['_rated'] = rated[-200:]
    if item_type == 'lesson':
        target = f'/practice/{strand.slug}/lesson/{item_id}?thanks=1'
        if 1 <= n <= len(c.strand_questions(strand)):
            target += f'&back={n}'
    else:
        total = len(c.strand_questions(strand))
        target = (f'/practice/{strand.slug}/q/{n + 1}?thanks=1' if 1 <= n < total
                  else f'/practice/{strand.slug}/summary?thanks=1')
    return _save(RedirectResponse(target, status_code=303), state)


@app.post('/practice/{slug}/reset')
def reset(request: Request, slug: str):
    strand = _strand(slug)
    state = _state(request)
    state.pop(strand.slug, None)
    return _save(RedirectResponse(f'/practice/{strand.slug}', status_code=303), state)
