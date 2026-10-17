"""discovery sources, listings, listing sources, runs

Revision ID: d3a9c8e5f1b6
Revises: 705732ddfa74
Create Date: 2026-10-18 12:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd3a9c8e5f1b6'
down_revision: Union[str, None] = 'b71f0d1a9c22'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'discovery_sources',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('owner_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('adapter', sa.String(length=32), nullable=False),
        sa.Column('config', sa.JSON(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('interval_minutes', sa.Integer(), nullable=False),
        sa.Column('max_listings', sa.Integer(), nullable=False),
        sa.Column('next_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cursor', sa.JSON(), nullable=True),
        sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_success_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('consecutive_failures', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.CheckConstraint('interval_minutes >= 5', name='ck_discovery_sources_interval'),
        sa.CheckConstraint('max_listings >= 1 AND max_listings <= 1000', name='ck_discovery_sources_budget'),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_discovery_sources_owner_id'), 'discovery_sources', ['owner_id'], unique=False)
    op.create_index('ix_discovery_sources_owner_enabled_next', 'discovery_sources', ['owner_id', 'enabled', 'next_run_at'], unique=False)

    op.create_table(
        'job_listings',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('owner_id', sa.String(length=36), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('company_name', sa.String(length=300), nullable=False),
        sa.Column('location', sa.String(length=300), nullable=True),
        sa.Column('remote_mode', sa.String(length=16), nullable=True),
        sa.Column('employment_type', sa.String(length=64), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('posted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('first_seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('closed_reason', sa.String(length=64), nullable=True),
        sa.Column('absent_scans', sa.Integer(), nullable=False),
        sa.Column('canonical_url', sa.String(length=1000), nullable=True),
        sa.Column('apply_url', sa.String(length=1000), nullable=True),
        sa.Column('content_hash', sa.String(length=64), nullable=True),
        sa.Column('needs_review', sa.Boolean(), nullable=False),
        sa.Column('review_candidate_id', sa.String(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.CheckConstraint("status IN ('active', 'closed')", name='ck_job_listings_status'),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['review_candidate_id'], ['job_listings.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_job_listings_owner_id'), 'job_listings', ['owner_id'], unique=False)
    op.create_index('ix_job_listings_owner_status', 'job_listings', ['owner_id', 'status'], unique=False)
    op.create_index('ix_job_listings_owner_canonical', 'job_listings', ['owner_id', 'canonical_url'], unique=False)

    op.create_table(
        'listing_sources',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('listing_id', sa.String(length=36), nullable=False),
        sa.Column('source_id', sa.String(length=36), nullable=False),
        sa.Column('external_id', sa.String(length=128), nullable=True),
        sa.Column('source_url', sa.String(length=1000), nullable=False),
        sa.Column('apply_url', sa.String(length=1000), nullable=True),
        sa.Column('posted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('first_seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('content_hash', sa.String(length=64), nullable=True),
        sa.Column('match_method', sa.String(length=32), nullable=False),
        sa.Column('match_score', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['listing_id'], ['job_listings.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_id'], ['discovery_sources.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source_id', 'external_id', name='uq_listing_sources_source_external'),
    )
    op.create_index(op.f('ix_listing_sources_listing_id'), 'listing_sources', ['listing_id'], unique=False)
    op.create_index(op.f('ix_listing_sources_source_id'), 'listing_sources', ['source_id'], unique=False)

    op.create_table(
        'discovery_runs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('source_id', sa.String(length=36), nullable=False),
        sa.Column('owner_id', sa.String(length=36), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('trigger', sa.String(length=16), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('pages_fetched', sa.Integer(), nullable=False),
        sa.Column('seen_count', sa.Integer(), nullable=False),
        sa.Column('created_count', sa.Integer(), nullable=False),
        sa.Column('updated_count', sa.Integer(), nullable=False),
        sa.Column('closed_count', sa.Integer(), nullable=False),
        sa.Column('review_count', sa.Integer(), nullable=False),
        sa.Column('error_code', sa.String(length=64), nullable=True),
        sa.Column('error_detail', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.CheckConstraint("status IN ('running', 'succeeded', 'failed')", name='ck_discovery_runs_status'),
        sa.CheckConstraint("trigger IN ('manual', 'scheduled')", name='ck_discovery_runs_trigger'),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_id'], ['discovery_sources.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_discovery_runs_owner_id'), 'discovery_runs', ['owner_id'], unique=False)
    op.create_index(op.f('ix_discovery_runs_source_id'), 'discovery_runs', ['source_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_discovery_runs_source_id'), table_name='discovery_runs')
    op.drop_index(op.f('ix_discovery_runs_owner_id'), table_name='discovery_runs')
    op.drop_table('discovery_runs')
    op.drop_index(op.f('ix_listing_sources_source_id'), table_name='listing_sources')
    op.drop_index(op.f('ix_listing_sources_listing_id'), table_name='listing_sources')
    op.drop_table('listing_sources')
    op.drop_index('ix_job_listings_owner_canonical', table_name='job_listings')
    op.drop_index('ix_job_listings_owner_status', table_name='job_listings')
    op.drop_index(op.f('ix_job_listings_owner_id'), table_name='job_listings')
    op.drop_table('job_listings')
    op.drop_index('ix_discovery_sources_owner_enabled_next', table_name='discovery_sources')
    op.drop_index(op.f('ix_discovery_sources_owner_id'), table_name='discovery_sources')
    op.drop_table('discovery_sources')
