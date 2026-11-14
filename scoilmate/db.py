"""SQLite engine/session setup.

Every connection: foreign keys ON (verified), WAL, bounded busy timeout. Transactions use
BEGIN IMMEDIATE so concurrent writers queue on the busy timeout instead of failing on a
read->write lock upgrade. That serialises requests, which is fine for a small pilot.
"""
from __future__ import annotations

import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .config import ROOT, settings

MIGRATIONS = ROOT / 'scoilmate' / 'migrations'
_lock = threading.Lock()
_engine: Engine | None = None
_engine_path: Path | None = None
_Session: sessionmaker | None = None


def utcnow() -> datetime:
    """Naive UTC timestamp (SQLite has no time zones; everything stored is UTC)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def make_engine(path: Path) -> Engine:
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f'sqlite:///{path}', connect_args={'timeout': 15, 'check_same_thread': False})

    @event.listens_for(engine, 'connect')
    def _on_connect(dbapi_conn, _record):
        dbapi_conn.isolation_level = None  # we issue BEGIN ourselves
        cur = dbapi_conn.cursor()
        cur.execute('PRAGMA foreign_keys=ON')
        cur.execute('PRAGMA busy_timeout=15000')
        cur.execute('PRAGMA journal_mode=WAL')
        cur.execute('PRAGMA synchronous=NORMAL')
        if cur.execute('PRAGMA foreign_keys').fetchone()[0] != 1:
            raise RuntimeError('SQLite foreign key enforcement unavailable')
        cur.close()

    @event.listens_for(engine, 'begin')
    def _on_begin(conn):
        conn.exec_driver_sql('BEGIN IMMEDIATE')

    return engine


def engine() -> Engine:
    global _engine, _engine_path, _Session
    with _lock:
        if _engine is None or _engine_path != settings.db_path:
            if _engine is not None:
                _engine.dispose()
            _engine_path = Path(settings.db_path)
            _engine = make_engine(_engine_path)
            _Session = sessionmaker(_engine, expire_on_commit=False)
        return _engine


def dispose():
    global _engine, _Session
    with _lock:
        if _engine is not None:
            _engine.dispose()
        _engine = _Session = None


def new_session() -> Session:
    engine()
    return _Session()


@contextmanager
def session_scope():
    db = new_session()
    try:
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def get_db():
    """FastAPI dependency: one session per request, committed on success."""
    with session_scope() as db:
        yield db


def alembic_config():
    from alembic.config import Config
    cfg = Config()
    cfg.set_main_option('script_location', str(MIGRATIONS))
    return cfg


def migrate(revision: str = 'head'):
    from alembic import command
    cfg = alembic_config()
    with engine().connect() as conn:
        cfg.attributes['connection'] = conn
        command.upgrade(cfg, revision)
        conn.commit()


def downgrade(revision: str):
    from alembic import command
    cfg = alembic_config()
    with engine().connect() as conn:
        cfg.attributes['connection'] = conn
        command.downgrade(cfg, revision)
        conn.commit()


def backup(dest: Path) -> Path:
    """Consistent online copy using the SQLite backup API (safe with WAL)."""
    import sqlite3
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        raise FileExistsError(dest)
    src = sqlite3.connect(settings.db_path)
    dst = sqlite3.connect(dest)
    try:
        src.backup(dst)
        if dst.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise RuntimeError('backup failed integrity check')
    finally:
        dst.close()
        src.close()
    dest.chmod(0o600)
    return dest


def restore(source: Path):
    """Replace the live database with a backup. Stop the server first."""
    import sqlite3
    src = sqlite3.connect(f'file:{source}?mode=ro', uri=True)
    try:
        if src.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise RuntimeError('backup failed integrity check; not restored')
        dispose()
        dst = sqlite3.connect(settings.db_path)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
