"""content workflow: reviewer name on versions, resolving version on ratings

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-15
"""
from alembic import op
import sqlalchemy as sa


revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade():
    # Plain ADD COLUMN (no table rebuild) keeps the content_version immutability trigger intact.
    op.add_column('content_version', sa.Column('reviewer_name', sa.String(length=80), nullable=True))
    op.add_column('content_rating', sa.Column('resolved_version', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('content_rating', 'resolved_version')
    op.drop_column('content_version', 'reviewer_name')
