"""learning: topic progress cache, activity log, rating receipts

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-14
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "topic_progress",
        sa.Column("student_id", sa.String(length=32), nullable=False),
        sa.Column("topic_id", sa.Integer(), nullable=False),
        sa.Column("level", sa.String(length=12), nullable=False),
        sa.Column("reason", sa.String(length=300), nullable=False),
        sa.Column("last_practised_at", sa.DateTime(), nullable=True),
        sa.Column("proficient_since", sa.DateTime(), nullable=True),
        sa.Column("due_at", sa.DateTime(), nullable=True),
        sa.Column("mastered_reviews", sa.Integer(), nullable=False),
        sa.Column("rule_version", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "level IN ('not_started','attempted','familiar','proficient','mastered')",
            name=op.f("ck_topic_progress_level"),
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["user.id"],
            name=op.f("fk_topic_progress_student_id_user"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["topic_id"],
            ["topic.id"],
            name=op.f("fk_topic_progress_topic_id_topic"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("student_id", "topic_id", name=op.f("pk_topic_progress")),
    )
    op.create_table(
        "activity",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.String(length=32), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("version_id", sa.Integer(), nullable=True),
        sa.Column("set_id", sa.Integer(), nullable=True),
        sa.Column("at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "kind IN ('lesson_read','set_completed')", name=op.f("ck_activity_kind")
        ),
        sa.ForeignKeyConstraint(
            ["set_id"],
            ["practice_set.id"],
            name=op.f("fk_activity_set_id_practice_set"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["user.id"],
            name=op.f("fk_activity_student_id_user"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["content_version.id"],
            name=op.f("fk_activity_version_id_content_version"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_activity")),
    )
    with op.batch_alter_table("activity", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_activity_student_id"), ["student_id"], unique=False)

    op.create_table(
        "rating_receipt",
        sa.Column("student_id", sa.String(length=32), nullable=False),
        sa.Column("version_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["user.id"],
            name=op.f("fk_rating_receipt_student_id_user"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["content_version.id"],
            name=op.f("fk_rating_receipt_version_id_content_version"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("student_id", "version_id", name=op.f("pk_rating_receipt")),
    )


def downgrade():
    op.drop_table("rating_receipt")
    with op.batch_alter_table("activity", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_activity_student_id"))

    op.drop_table("activity")
    op.drop_table("topic_progress")
