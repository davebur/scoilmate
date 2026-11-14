"""ScoilMate web app: accounts, practice with recorded progress, reports, content workflow.

Routes live in views_*.py; this module wires middleware, error pages and routers.
"""
from __future__ import annotations

import secrets

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import auth, content as content_mod
from .auth import LoginRequired
from .config import settings
from .db import get_db
from .views_accounts import router as accounts_router
from .views_learning import router as learning_router
from .web import PKG, render

ROOT = PKG.parent
CSP = ("default-src 'self'; script-src 'none'; img-src 'self'; style-src 'self'; form-action 'self'; "
       "frame-ancestors 'none'; base-uri 'none'; object-src 'none'")

app = FastAPI(title='ScoilMate', docs_url=None, redoc_url=None, openapi_url=None,
              dependencies=[Depends(auth.current_session)])  # every page knows who is logged in
app.mount('/static/branding', StaticFiles(directory=ROOT / 'assets' / 'branding'), name='branding')
app.mount('/static/app', StaticFiles(directory=PKG / 'static'), name='appstatic')
app.include_router(accounts_router)
app.include_router(learning_router)


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


# ---- public pages ----

@app.get('/health')
def health():
    return {'status': 'ok', 'app': 'ScoilMate', 'mode': 'preview'}


@app.get('/')
def landing(request: Request, db: Session = Depends(get_db)):
    strands = [s for s in content_mod.all_strands() if content_mod.strand_topics(db, s)]
    return render(request, 'landing.html', strands=strands)
