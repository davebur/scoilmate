"""accounts: sessions, parent links, audit log

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-14
"""
from alembic import op
import sqlalchemy as sa


revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('audit_log',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('at', sa.DateTime(), nullable=False),
    sa.Column('actor_id', sa.String(length=32), nullable=True),
    sa.Column('action', sa.String(length=40), nullable=False),
    sa.Column('target_user_id', sa.String(length=32), nullable=True),
    sa.Column('detail', sa.String(length=300), nullable=True),
    sa.ForeignKeyConstraint(['actor_id'], ['user.id'], name=op.f('fk_audit_log_actor_id_user'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['target_user_id'], ['user.id'], name=op.f('fk_audit_log_target_user_id_user'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_audit_log'))
    )
    with op.batch_alter_table('audit_log', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_audit_log_at'), ['at'], unique=False)
        batch_op.create_index(batch_op.f('ix_audit_log_target_user_id'), ['target_user_id'], unique=False)

    op.create_table('parent_student',
    sa.Column('parent_id', sa.String(length=32), nullable=False),
    sa.Column('student_id', sa.String(length=32), nullable=False),
    sa.Column('created_by', sa.String(length=32), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['user.id'], name=op.f('fk_parent_student_created_by_user'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['parent_id'], ['user.id'], name=op.f('fk_parent_student_parent_id_user'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['student_id'], ['user.id'], name=op.f('fk_parent_student_student_id_user'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('parent_id', 'student_id', name=op.f('pk_parent_student'))
    )
    with op.batch_alter_table('parent_student', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_parent_student_student_id'), ['student_id'], unique=False)

    op.create_table('session',
    sa.Column('token_digest', sa.String(length=64), nullable=False),
    sa.Column('user_id', sa.String(length=32), nullable=False),
    sa.Column('csrf_token', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('last_seen_at', sa.DateTime(), nullable=False),
    sa.Column('idle_expires_at', sa.DateTime(), nullable=False),
    sa.Column('absolute_expires_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('fk_session_user_id_user'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('token_digest', name=op.f('pk_session'))
    )
    with op.batch_alter_table('session', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_session_user_id'), ['user_id'], unique=False)



def downgrade():
    with op.batch_alter_table('session', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_session_user_id'))

    op.drop_table('session')
    with op.batch_alter_table('parent_student', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_parent_student_student_id'))

    op.drop_table('parent_student')
    with op.batch_alter_table('audit_log', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_audit_log_target_user_id'))
        batch_op.drop_index(batch_op.f('ix_audit_log_at'))

    op.drop_table('audit_log')
