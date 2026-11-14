"""Shared test helpers: a migrated + imported template database, copied fresh per test."""
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TMP = Path(tempfile.mkdtemp(prefix='scoilmate-tests-'))
os.environ.setdefault('SCOILMATE_DB', str(TMP / 'unused.db'))

from scoilmate import content, db  # noqa: E402
from scoilmate.config import settings  # noqa: E402

_template: Path | None = None
_counter = 0


def template_db() -> Path:
    global _template
    if _template is None:
        settings.db_path = TMP / 'template.db'
        db.migrate()
        with db.session_scope() as s:
            content.import_json(s)
        db.dispose()
        # fold WAL into the main file so a plain copy is complete
        con = sqlite3.connect(settings.db_path)
        con.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        con.execute('PRAGMA journal_mode=DELETE')
        con.close()
        _template = settings.db_path
    return _template


def fresh_db(**overrides) -> Path:
    """Point the app at a new copy of the template DB; preview settings on by default."""
    global _counter
    src = template_db()
    _counter += 1
    path = TMP / f'test-{_counter}.db'
    shutil.copy(src, path)
    db.dispose()
    settings.db_path = path
    settings.allow_draft_practice = overrides.get('allow_draft_practice', True)
    settings.secure_cookies = overrides.get('secure_cookies', False)
    return path


# ---------- HTTP helpers ----------
import re  # noqa: E402

from argon2 import PasswordHasher  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from scoilmate import accounts, auth  # noqa: E402
from scoilmate.app import app  # noqa: E402

auth.hasher = PasswordHasher(time_cost=1, memory_cost=8192, parallelism=1)  # fast hashes for tests only
PASSWORD = 'correct-horse-battery'
TOKEN_RE = re.compile(r'name="csrf-token" content="([^"]*)"')


class Client(TestClient):
    def __init__(self, **kw):
        super().__init__(app, **kw)

    def token(self) -> str:
        return TOKEN_RE.search(self.get('/').text).group(1)

    def submit(self, path, data=None, **kw):
        data = dict(data or {})
        data.setdefault('csrf_token', self.token())
        kw.setdefault('follow_redirects', False)
        return self.post(path, data=data, **kw)

    def login(self, login, password=PASSWORD):
        r = self.submit('/login', {'login': login, 'password': password})
        assert r.status_code == 303, (r.status_code, r.text[:300])
        return self


def make_user(role, login, parent=None, **kw):
    """Create an account directly through the service layer (audited as 'system')."""
    with db.session_scope() as s:
        p = s.get(accounts.User, parent) if parent else None
        u = accounts.create_user(s, None, role, login, kw.pop('name', login.title()), PASSWORD, **kw)
        if p is not None:
            accounts.link(s, p, p, u)
        return u.id


def reset_limits():
    auth.login_limiter.reset()


def all_routes(routes=None):
    """(path, methods) for every route, including routers included into the app."""
    for r in (app.routes if routes is None else routes):
        if hasattr(r, 'original_router'):
            yield from all_routes(r.original_router.routes)
        elif getattr(r, 'methods', None):
            yield r.path, r.methods
