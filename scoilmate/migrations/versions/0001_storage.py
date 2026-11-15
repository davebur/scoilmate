"""storage: content versions, ratings, attempts

Revision ID: 0001
Revises:
Create Date: 2026-11-14

Content versions are immutable: a trigger rejects changes to a version's identity, title
or body. Status/review columns may change (publish, retire).
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "topic",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("subject", sa.String(length=10), nullable=False),
        sa.Column("track", sa.String(length=10), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_topic")),
        sa.UniqueConstraint("slug", name=op.f("uq_topic_slug")),
    )
    op.create_table(
        "user",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("login", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=80), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("role", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("school_year", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("disabled_at", sa.DateTime(), nullable=True),
        sa.Column("deletion_requested_at", sa.DateTime(), nullable=True),
        sa.Column("deletion_requested_by", sa.String(length=32), nullable=True),
        sa.CheckConstraint("role IN ('admin','parent','student')", name=op.f("ck_user_role")),
        sa.CheckConstraint("status IN ('active','disabled')", name=op.f("ck_user_status")),
        sa.CheckConstraint(
            "school_year IS NULL OR school_year BETWEEN 1 AND 3", name=op.f("ck_user_year")
        ),
        sa.ForeignKeyConstraint(
            ["deletion_requested_by"],
            ["user.id"],
            name=op.f("fk_user_deletion_requested_by_user"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user")),
        sa.UniqueConstraint("login", name=op.f("uq_user_login")),
    )
    op.create_table(
        "content_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("topic_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("kind IN ('lesson','question')", name=op.f("ck_content_item_kind")),
        sa.ForeignKeyConstraint(
            ["topic_id"],
            ["topic.id"],
            name=op.f("fk_content_item_topic_id_topic"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_content_item")),
        sa.UniqueConstraint("slug", name=op.f("uq_content_item_slug")),
    )
    with op.batch_alter_table("content_item", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_content_item_topic_id"), ["topic_id"], unique=False)

    op.create_table(
        "practice_set",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.String(length=32), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("subject", sa.String(length=10), nullable=False),
        sa.Column("track", sa.String(length=10), nullable=False),
        sa.Column("topic_id", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Integer(), nullable=True),
        sa.Column("next_step", sa.String(length=10), nullable=True),
        sa.Column("reflection", sa.String(length=500), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "kind IN ('topic','mixed','mistakes')", name=op.f("ck_practice_set_kind")
        ),
        sa.CheckConstraint(
            "next_step IS NULL OR next_step IN ('revisit','mixed','new_topic')",
            name=op.f("ck_practice_set_next_step"),
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR confidence BETWEEN 1 AND 4",
            name=op.f("ck_practice_set_confidence"),
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["user.id"],
            name=op.f("fk_practice_set_student_id_user"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["topic_id"],
            ["topic.id"],
            name=op.f("fk_practice_set_topic_id_topic"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_practice_set")),
    )
    with op.batch_alter_table("practice_set", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_practice_set_student_id"), ["student_id"], unique=False
        )

    op.create_table(
        "student_subject",
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("subject", sa.String(length=10), nullable=False),
        sa.Column("track", sa.String(length=10), nullable=False),
        sa.Column("level", sa.String(length=10), nullable=False),
        sa.CheckConstraint(
            "level IN ('higher','ordinary','common','undecided')",
            name=op.f("ck_student_subject_level"),
        ),
        sa.CheckConstraint(
            "subject IN ('english','gaeilge','history')", name=op.f("ck_student_subject_subject")
        ),
        sa.CheckConstraint("track IN ('general','T1','T2')", name=op.f("ck_student_subject_track")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            name=op.f("fk_student_subject_user_id_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "subject", name=op.f("pk_student_subject")),
    )
    op.create_table(
        "content_version",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.String(length=32), nullable=True),
        sa.Column("reviewed_by", sa.String(length=32), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("review_note", sa.String(length=500), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("retired_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "status IN ('draft','reviewed','published','retired')",
            name=op.f("ck_content_version_status"),
        ),
        sa.CheckConstraint("version > 0", name=op.f("ck_content_version_version_positive")),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["user.id"],
            name=op.f("fk_content_version_created_by_user"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["content_item.id"],
            name=op.f("fk_content_version_item_id_content_item"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by"],
            ["user.id"],
            name=op.f("fk_content_version_reviewed_by_user"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_content_version")),
        sa.UniqueConstraint("item_id", "version", name="uq_content_version_item_version"),
    )
    with op.batch_alter_table("content_version", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_content_version_item_id"), ["item_id"], unique=False)

    op.create_table(
        "content_rating",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("version_id", sa.Integer(), nullable=False),
        sa.Column("rating", sa.String(length=4), nullable=False),
        sa.Column("reason", sa.String(length=10), nullable=True),
        sa.Column("at", sa.DateTime(), nullable=False),
        sa.Column("source_key", sa.String(length=64), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("rating IN ('up','down')", name=op.f("ck_content_rating_rating")),
        sa.CheckConstraint(
            "reason IS NULL OR reason IN ('unclear','wrong','too_easy','too_hard','helpful')",
            name=op.f("ck_content_rating_reason"),
        ),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["content_version.id"],
            name=op.f("fk_content_rating_version_id_content_version"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_content_rating")),
        sa.UniqueConstraint("source_key", name=op.f("uq_content_rating_source_key")),
    )
    with op.batch_alter_table("content_rating", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_content_rating_version_id"), ["version_id"], unique=False
        )

    op.create_table(
        "practice_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("set_id", sa.Integer(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("question_version_id", sa.Integer(), nullable=False),
        sa.Column("lesson_version_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["lesson_version_id"],
            ["content_version.id"],
            name=op.f("fk_practice_item_lesson_version_id_content_version"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["question_version_id"],
            ["content_version.id"],
            name=op.f("fk_practice_item_question_version_id_content_version"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["set_id"],
            ["practice_set.id"],
            name=op.f("fk_practice_item_set_id_practice_set"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_practice_item")),
        sa.UniqueConstraint("set_id", "ordinal", name="uq_practice_item_set_ordinal"),
    )
    with op.batch_alter_table("practice_item", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_practice_item_question_version_id"),
            ["question_version_id"],
            unique=False,
        )
        batch_op.create_index(batch_op.f("ix_practice_item_set_id"), ["set_id"], unique=False)

    op.create_table(
        "hint_event",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["practice_item.id"],
            name=op.f("fk_hint_event_item_id_practice_item"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_hint_event")),
        sa.UniqueConstraint("item_id", "ordinal", name="uq_hint_event_item_ordinal"),
    )
    op.create_table(
        "response",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("selected", sa.String(length=8), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("hints_used", sa.Integer(), nullable=False),
        sa.Column("credit", sa.Float(), nullable=False),
        sa.Column("answered_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["practice_item.id"],
            name=op.f("fk_response_item_id_practice_item"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_response")),
        sa.UniqueConstraint("item_id", name=op.f("uq_response_item_id")),
    )
    op.execute(IMMUTABLE_TRIGGER)


IMMUTABLE_TRIGGER = """
CREATE TRIGGER content_version_immutable
BEFORE UPDATE OF item_id, version, title, body ON content_version
WHEN OLD.item_id IS NOT NEW.item_id OR OLD.version IS NOT NEW.version
  OR OLD.title IS NOT NEW.title OR OLD.body IS NOT NEW.body
BEGIN SELECT RAISE(ABORT, 'content versions are immutable; create a new version'); END
"""


def downgrade():
    op.execute("DROP TRIGGER IF EXISTS content_version_immutable")
    op.drop_table("response")
    op.drop_table("hint_event")
    with op.batch_alter_table("practice_item", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_practice_item_set_id"))
        batch_op.drop_index(batch_op.f("ix_practice_item_question_version_id"))

    op.drop_table("practice_item")
    with op.batch_alter_table("content_rating", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_content_rating_version_id"))

    op.drop_table("content_rating")
    with op.batch_alter_table("content_version", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_content_version_item_id"))

    op.drop_table("content_version")
    op.drop_table("student_subject")
    with op.batch_alter_table("practice_set", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_practice_set_student_id"))

    op.drop_table("practice_set")
    with op.batch_alter_table("content_item", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_content_item_topic_id"))

    op.drop_table("content_item")
    op.drop_table("user")
    op.drop_table("topic")
