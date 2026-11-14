"""ScoilMate management commands.

    python -m scoilmate.cli migrate                 # apply Alembic migrations (run before the server)
    python -m scoilmate.cli import-content [file]   # import editorial JSON as draft versions
    python -m scoilmate.cli import-ratings [file]   # move step-1 JSONL ratings into the database
    python -m scoilmate.cli backup [--out FILE]     # online backup (SQLite backup API)
    python -m scoilmate.cli restore FILE            # replace the database with a backup (server stopped!)
    python -m scoilmate.cli create-admin LOGIN [--name NAME]
        # prompts for the password; or reads SCOILMATE_ADMIN_PASSWORD (tests/automation)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import content, db
from .config import ROOT, settings


def cmd_migrate(args):
    db.migrate(args.revision)
    print(f'Database at {settings.db_path} migrated to {args.revision}.')


def cmd_import_content(args):
    with db.session_scope() as s:
        created, skipped = content.import_json(s, Path(args.file))
    print(f'Imported {created} new content versions as draft ({skipped} already present).')


def cmd_import_ratings(args):
    path = Path(args.file)
    if not path.exists():
        print(f'No ratings file at {path}; nothing to import.')
        return
    with db.session_scope() as s:
        created, skipped = content.import_ratings_jsonl(s, path)
    print(f'Imported {created} ratings ({skipped} skipped: already imported or unknown item).')


def cmd_backup(args):
    from datetime import datetime
    out = Path(args.out) if args.out else (
        ROOT / 'instance' / 'backups' / f"scoilmate-{datetime.now():%Y%m%d-%H%M%S}.db")
    print(f'Backup written: {db.backup(out)}')


def cmd_restore(args):
    if not args.yes:
        answer = input(f'Replace {settings.db_path} with {args.file}? Stop the server first. Type yes: ')
        if answer.strip() != 'yes':
            sys.exit('Not restored.')
    db.restore(Path(args.file))
    db.migrate()
    print(f'Restored {args.file} into {settings.db_path}.')


def cmd_create_admin(args):
    import getpass
    import os
    from . import accounts, auth
    from .models import User
    password = os.environ.get('SCOILMATE_ADMIN_PASSWORD')
    if not password:
        password = getpass.getpass('New admin password (8-128 characters): ')
        if getpass.getpass('Repeat password: ') != password:
            sys.exit('Passwords did not match.')
    try:
        auth.check_password(password)
        db.migrate()
        with db.session_scope() as s:
            existing = s.query(User).filter_by(login=auth.normalise_login(args.login)).one_or_none()
            if existing is not None:
                if existing.role != 'admin' or not args.reset:
                    sys.exit('That login exists. Use --reset to set a new password for an existing admin.')
                accounts.reset_access(s, None, existing, password)
                print(f'Password reset for admin {existing.login}.')
                return
            user = accounts.create_user(s, None, 'admin', args.login, args.name or args.login, password)
            print(f'Admin {user.login} created.')
    except ValueError as exc:
        sys.exit(str(exc))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog='python -m scoilmate.cli', description='ScoilMate management')
    sub = p.add_subparsers(dest='cmd', required=True)
    m = sub.add_parser('migrate'); m.add_argument('revision', nargs='?', default='head'); m.set_defaults(fn=cmd_migrate)
    c = sub.add_parser('import-content'); c.add_argument('file', nargs='?', default=str(content.CONTENT_FILE))
    c.set_defaults(fn=cmd_import_content)
    r = sub.add_parser('import-ratings')
    r.add_argument('file', nargs='?', default=str(ROOT / 'instance' / 'content-feedback.jsonl'))
    r.set_defaults(fn=cmd_import_ratings)
    b = sub.add_parser('backup'); b.add_argument('--out'); b.set_defaults(fn=cmd_backup)
    rs = sub.add_parser('restore'); rs.add_argument('file'); rs.add_argument('--yes', action='store_true')
    rs.set_defaults(fn=cmd_restore)
    a = sub.add_parser('create-admin'); a.add_argument('login'); a.add_argument('--name')
    a.add_argument('--reset', action='store_true', help='set a new password for an existing admin')
    a.set_defaults(fn=cmd_create_admin)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.fn(args)


if __name__ == '__main__':
    main()
