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
