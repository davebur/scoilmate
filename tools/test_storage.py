"""Storage tests: FK enforcement, migrations, immutable versions, pinned attempts, imports,
backup/restore. Run: .venv/bin/python -m unittest discover -s tools -p 'test_*.py'
"""
import json
import unittest

try:
    import testutil
    from sqlalchemy import func, select, text, update
    from sqlalchemy.exc import IntegrityError, OperationalError
    from scoilmate import content, db
    from scoilmate.config import settings
    from scoilmate.models import (Base, ContentItem, ContentRating, ContentVersion, PracticeItem, PracticeSet,
                                  Topic, User)
except ImportError as exc:
    raise unittest.SkipTest(f'dependencies unavailable: {exc}')


def make_student(s, login='demo-student'):
    u = User(login=login, display_name='Test', role='student')
    s.add(u)
    s.flush()
    return u


def q_version(s, slug='q-simile', version=1):
    return s.scalar(select(ContentVersion).join(ContentItem).where(
        ContentItem.slug == slug, ContentVersion.version == version))


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.path = testutil.fresh_db()

    def test_pragmas_on_every_connection(self):
        with db.engine().connect() as conn:
            self.assertEqual(conn.exec_driver_sql('PRAGMA foreign_keys').scalar(), 1)
            self.assertEqual(conn.exec_driver_sql('PRAGMA journal_mode').scalar(), 'wal')
            self.assertGreaterEqual(conn.exec_driver_sql('PRAGMA busy_timeout').scalar(), 5000)

    def test_foreign_keys_enforced(self):
        with self.assertRaises(IntegrityError):
            with db.session_scope() as s:
                s.add(ContentItem(slug='orphan', kind='lesson', topic_id=99999))
        with self.assertRaises(IntegrityError):  # referenced topic cannot be deleted
            with db.session_scope() as s:
                s.execute(text('DELETE FROM topic'))

    def test_models_match_migrations(self):
        from alembic.autogenerate import compare_metadata
        from alembic.migration import MigrationContext
        with db.engine().connect() as conn:
            diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
        self.assertEqual(diff, [])

    def test_migration_down_and_up_on_populated_db(self):
        with db.session_scope() as s:
            u = make_student(s)
            v = q_version(s)
            ps = PracticeSet(student_id=u.id, kind='topic', subject='english', track='general')
            ps.items.append(PracticeItem(ordinal=1, question_version_id=v.id))
            s.add(ps)
            content.record_rating(s, v, 'down', 'unclear')
        db.downgrade('base')
        with db.engine().connect() as conn:
            tables = {r[0] for r in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertEqual(tables - {'alembic_version'}, set())
        db.migrate()
        with db.session_scope() as s:
            self.assertEqual(content.import_json(s), (18, 0))
            self.assertEqual(s.scalar(select(func.count()).select_from(ContentVersion)), 18)

    def test_versions_immutable_and_new_versions_allowed(self):
        with db.session_scope() as s:
            v = q_version(s)
            item_id = v.item_id
        for column, value in (('body', '{}'), ('title', 'changed'), ('version', 7)):
            with self.subTest(column=column), self.assertRaises(IntegrityError):
                with db.session_scope() as s:
                    s.execute(update(ContentVersion).where(ContentVersion.item_id == item_id)
                              .values({column: value}))
        with db.session_scope() as s:  # status changes (publish/retire) are allowed
            s.execute(update(ContentVersion).where(ContentVersion.item_id == item_id).values(status='published'))
            s.add(ContentVersion(item_id=item_id, version=2, title='new', body='{}'))
        with self.assertRaises(IntegrityError):  # duplicate version number
            with db.session_scope() as s:
                s.add(ContentVersion(item_id=item_id, version=2, title='dup', body='{}'))

    def test_import_idempotent_and_rejects_silent_edits(self):
        with db.session_scope() as s:
            self.assertEqual(content.import_json(s), (0, 18))
            topics = s.scalars(select(Topic)).all()
            self.assertEqual(len(topics), 9)
            self.assertTrue(all(i.topic_id for i in s.scalars(select(ContentItem))))
            self.assertEqual({v.status for v in s.scalars(select(ContentVersion))}, {'draft'})
        data = json.loads(content.CONTENT_FILE.read_text())
        data['questions'][0]['prompt'] += ' (edited)'
        changed = testutil.TMP / 'changed.json'
        changed.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            with db.session_scope() as s:
                content.import_json(s, changed)
        data['questions'][0]['version'] = 2
        changed.write_text(json.dumps(data))
        with db.session_scope() as s:
            self.assertEqual(content.import_json(s, changed), (1, 17))

    def test_attempts_pin_versions(self):
        with db.session_scope() as s:
            u = make_student(s)
            v1 = q_version(s)
            ps = PracticeSet(student_id=u.id, kind='topic', subject='english', track='general')
            ps.items.append(PracticeItem(ordinal=1, question_version_id=v1.id))
            s.add(ps)
            s.flush()
            s.add(ContentVersion(item_id=v1.item_id, version=2, title='Edited prompt', body=v1.body))
            set_id, v1_id = ps.id, v1.id
        with db.session_scope() as s:
            item = s.get(PracticeSet, set_id).items[0]
            self.assertEqual((item.question_version_id, item.question.version), (v1_id, 1))
            self.assertEqual(content.current_version(item.question.item, True).version, 2)
        with self.assertRaises(IntegrityError):  # pinned versions can't be deleted
            with db.session_scope() as s:
                s.execute(text('DELETE FROM content_version WHERE id=:i'), {'i': v1_id})

    def test_ratings_jsonl_import(self):
        jsonl = testutil.TMP / 'ratings.jsonl'
        rows = [{'at': '2026-11-14T22:42:11+00:00', 'type': 'lesson', 'id': 'lesson-simile', 'version': 1,
                 'rating': 'up', 'reason': 'wrong'},
                {'at': '2026-11-14T22:43:00+00:00', 'type': 'question', 'id': 'q-simile', 'version': 1,
                 'rating': 'down', 'reason': None},
                {'at': '2026-11-14T22:44:00+00:00', 'type': 'question', 'id': 'q-gone', 'version': 1,
                 'rating': 'down', 'reason': None}]
        jsonl.write_text('\n'.join(json.dumps(r) for r in rows) + '\n')
        with db.session_scope() as s:
            self.assertEqual(content.import_ratings_jsonl(s, jsonl), (2, 1))
            self.assertEqual(content.import_ratings_jsonl(s, jsonl), (0, 3))
            self.assertEqual(s.scalar(select(func.count()).select_from(ContentRating)), 2)

    def test_backup_and_restore_drill(self):
        with db.session_scope() as s:
            make_student(s, 'before-backup')
        out = db.backup(testutil.TMP / f'backup-{self.path.stem}.db')
        self.assertEqual(oct(out.stat().st_mode & 0o777), '0o600')
        with self.assertRaises(FileExistsError):
            db.backup(out)
        with db.session_scope() as s:
            make_student(s, 'after-backup')
            s.execute(text('DELETE FROM content_rating'))
        db.restore(out)
        with db.session_scope() as s:
            logins = set(s.scalars(select(User.login)))
            self.assertEqual(logins, {'before-backup'})
            self.assertEqual(s.scalar(select(func.count()).select_from(ContentVersion)), 18)
            self.assertEqual(s.execute(text('PRAGMA integrity_check')).scalar(), 'ok')

    def test_restore_rejects_corrupt_file(self):
        bad = testutil.TMP / 'corrupt.db'
        bad.write_bytes(b'not a database' * 100)
        with self.assertRaises(Exception):
            db.restore(bad)
        with db.session_scope() as s:  # live DB untouched
            self.assertEqual(s.scalar(select(func.count()).select_from(ContentVersion)), 18)


if __name__ == '__main__':
    unittest.main()
