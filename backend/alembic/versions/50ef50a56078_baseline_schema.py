"""baseline schema

Revision ID: 50ef50a56078
Revises: 
Create Date: 2026-10-05 11:08:58.632495

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '50ef50a56078'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _batch_naming() -> dict:
    """SQLite batch recreate needs named constraints; reflected unnamed FKs
    are rendered via this convention (same pattern as 4f8e2a71c9b3)."""
    return {
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }


def upgrade() -> None:
    # Created in dependency order so this migration applies to PostgreSQL,
    # where CREATE TABLE refuses FOREIGN KEY references to not-yet-existing
    # tables (SQLite never enforced this, which is why the bug stayed hidden):
    # users/jobs/resumes first; the applications ↔ resume_versions FK cycle
    # is broken by deferring one constraint to a post-create ALTER.
    op.create_table('users',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('username', sa.String(length=128), nullable=False),
    sa.Column('password_hash', sa.String(length=256), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)
    op.create_table('jobs',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=True),
    sa.Column('title', sa.String(length=512), nullable=False),
    sa.Column('company_name', sa.String(length=512), nullable=True),
    sa.Column('source_url', sa.Text(), nullable=True),
    sa.Column('raw_text', sa.Text(), nullable=False),
    sa.Column('location', sa.String(length=512), nullable=True),
    sa.Column('structured', sa.JSON(), nullable=True),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_jobs_user_id'), 'jobs', ['user_id'], unique=False)
    op.create_table('resumes',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=True),
    sa.Column('filename', sa.String(length=512), nullable=False),
    sa.Column('content_type', sa.String(length=128), nullable=False),
    sa.Column('file_path', sa.String(length=1024), nullable=False),
    sa.Column('raw_text', sa.Text(), nullable=False),
    sa.Column('profile', sa.JSON(), nullable=True),
    sa.Column('parse_status', sa.String(length=32), nullable=False),
    sa.Column('parse_error', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_resumes_user_id'), 'resumes', ['user_id'], unique=False)
    op.create_table('applications',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('job_id', sa.String(length=36), nullable=True),
    sa.Column('company', sa.String(length=512), nullable=False),
    sa.Column('role', sa.String(length=512), nullable=False),
    sa.Column('location', sa.String(length=512), nullable=True),
    sa.Column('job_url', sa.Text(), nullable=True),
    sa.Column('date_saved', sa.String(length=32), nullable=True),
    sa.Column('date_applied', sa.String(length=32), nullable=True),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('salary', sa.String(length=256), nullable=True),
    sa.Column('ats_score', sa.Float(), nullable=True),
    sa.Column('resume_version_id', sa.String(length=36), nullable=True),
    sa.Column('interview_date', sa.String(length=64), nullable=True),
    sa.Column('next_step', sa.Text(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=False),
    sa.Column('raw_jd', sa.Text(), nullable=False),
    sa.Column('jd_analysis', sa.JSON(), nullable=True),
    sa.Column('status_history', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_applications_status'), 'applications', ['status'], unique=False)
    op.create_index(op.f('ix_applications_user_id'), 'applications', ['user_id'], unique=False)
    op.create_table('resume_versions',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('resume_id', sa.String(length=36), nullable=True),
    sa.Column('application_id', sa.String(length=36), nullable=True),
    sa.Column('label', sa.String(length=512), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('changes', sa.JSON(), nullable=False),
    sa.Column('missing_keywords', sa.JSON(), nullable=False),
    sa.Column('ats_score', sa.Float(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ),
    sa.ForeignKeyConstraint(['resume_id'], ['resumes.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_resume_versions_application_id'), 'resume_versions', ['application_id'], unique=False)
    op.create_index(op.f('ix_resume_versions_user_id'), 'resume_versions', ['user_id'], unique=False)
    # Deferred FK from the applications ↔ resume_versions cycle; batch mode
    # keeps the SQLite path working (plain ALTER ADD CONSTRAINT is unsupported there).
    with op.batch_alter_table('applications', naming_convention=_batch_naming()) as batch:
        batch.create_foreign_key('fk_applications_resume_version_id_resume_versions', 'resume_versions', ['resume_version_id'], ['id'])
    op.create_table('ats_analyses',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('application_id', sa.String(length=36), nullable=True),
    sa.Column('resume_version_id', sa.String(length=36), nullable=True),
    sa.Column('score', sa.Float(), nullable=False),
    sa.Column('breakdown', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ),
    sa.ForeignKeyConstraint(['resume_version_id'], ['resume_versions.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ats_analyses_application_id'), 'ats_analyses', ['application_id'], unique=False)
    op.create_index(op.f('ix_ats_analyses_user_id'), 'ats_analyses', ['user_id'], unique=False)
    op.create_table('companies',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=True),
    sa.Column('job_id', sa.String(length=36), nullable=True),
    sa.Column('application_id', sa.String(length=36), nullable=True),
    sa.Column('name', sa.String(length=512), nullable=False),
    sa.Column('website', sa.Text(), nullable=True),
    sa.Column('profile', sa.JSON(), nullable=True),
    sa.Column('sources', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_companies_application_id'), 'companies', ['application_id'], unique=False)
    op.create_index(op.f('ix_companies_user_id'), 'companies', ['user_id'], unique=False)
    op.create_table('interview_preps',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('application_id', sa.String(length=36), nullable=True),
    sa.Column('plan', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_interview_preps_application_id'), 'interview_preps', ['application_id'], unique=False)
    op.create_index(op.f('ix_interview_preps_user_id'), 'interview_preps', ['user_id'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # Reverse of upgrade() in PostgreSQL-safe order (dependents first).
    op.drop_index(op.f('ix_interview_preps_user_id'), table_name='interview_preps')
    op.drop_index(op.f('ix_interview_preps_application_id'), table_name='interview_preps')
    op.drop_table('interview_preps')
    op.drop_index(op.f('ix_companies_user_id'), table_name='companies')
    op.drop_index(op.f('ix_companies_application_id'), table_name='companies')
    op.drop_table('companies')
    op.drop_index(op.f('ix_ats_analyses_user_id'), table_name='ats_analyses')
    op.drop_index(op.f('ix_ats_analyses_application_id'), table_name='ats_analyses')
    op.drop_table('ats_analyses')
    with op.batch_alter_table('applications', naming_convention=_batch_naming()) as batch:
        batch.drop_constraint('fk_applications_resume_version_id_resume_versions', type_='foreignkey')
    op.drop_index(op.f('ix_resume_versions_user_id'), table_name='resume_versions')
    op.drop_index(op.f('ix_resume_versions_application_id'), table_name='resume_versions')
    op.drop_table('resume_versions')
    op.drop_index(op.f('ix_applications_user_id'), table_name='applications')
    op.drop_index(op.f('ix_applications_status'), table_name='applications')
    op.drop_table('applications')
    op.drop_index(op.f('ix_jobs_user_id'), table_name='jobs')
    op.drop_table('jobs')
    op.drop_index(op.f('ix_resumes_user_id'), table_name='resumes')
    op.drop_table('resumes')
    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_table('users')
    # ### end Alembic commands ###
