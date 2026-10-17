"""truthful resume evidence

Revision ID: b8d3f6a41c02
Revises: 4f8e2a71c9b3
Create Date: 2026-10-18 11:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8d3f6a41c02'
down_revision: Union[str, None] = '4f8e2a71c9b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'candidate_evidence',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('resume_id', sa.String(length=36), sa.ForeignKey('resumes.id'), nullable=True),
        sa.Column('ev_ref', sa.String(length=32), nullable=False),
        sa.Column('kind', sa.String(length=32), nullable=False),
        sa.Column('assert_type', sa.String(length=16), nullable=False, server_default='stated'),
        sa.Column('label', sa.String(length=512), nullable=True, server_default=''),
        sa.Column('fact', sa.JSON(), nullable=True),
        sa.Column('source_section', sa.String(length=64), nullable=True, server_default=''),
        sa.Column('line_start', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('line_end', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('source_text', sa.Text(), nullable=True, server_default=''),
        sa.Column('status', sa.String(length=16), nullable=False, server_default='extracted'),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_candidate_evidence_user_id', 'user_id'),
        sa.Index('ix_candidate_evidence_resume_id', 'resume_id'),
        sa.Index('ix_candidate_evidence_ev_ref', 'ev_ref'),
        sa.Index('ix_candidate_evidence_kind', 'kind'),
    )
    # resume_versions: which master snapshot a version derives from
    op.add_column('resume_versions', sa.Column('master_sha256', sa.String(length=64), nullable=True))
    # ats_analyses: stale once the analysed version is manually edited
    op.add_column('ats_analyses', sa.Column('stale', sa.Boolean(), server_default=sa.text('0'), nullable=False))
    # optimization_runs: provenance hashes, export reparse validation, invalidation
    op.add_column('optimization_runs', sa.Column('jd_sha256', sa.String(length=64), nullable=True))
    op.add_column('optimization_runs', sa.Column('resume_sha256', sa.String(length=64), nullable=True))
    op.add_column('optimization_runs', sa.Column('config_hash', sa.String(length=64), nullable=True))
    op.add_column('optimization_runs', sa.Column('export_validation', sa.JSON(), nullable=True))
    op.add_column('optimization_runs', sa.Column('final_pdf_sha256', sa.String(length=64), nullable=True))
    op.add_column('optimization_runs', sa.Column('invalidated', sa.Boolean(), server_default=sa.text('0'), nullable=False))


def downgrade() -> None:
    op.drop_column('optimization_runs', 'invalidated')
    op.drop_column('optimization_runs', 'final_pdf_sha256')
    op.drop_column('optimization_runs', 'export_validation')
    op.drop_column('optimization_runs', 'config_hash')
    op.drop_column('optimization_runs', 'resume_sha256')
    op.drop_column('optimization_runs', 'jd_sha256')
    op.drop_column('ats_analyses', 'stale')
    op.drop_column('resume_versions', 'master_sha256')
    op.drop_table('candidate_evidence')
