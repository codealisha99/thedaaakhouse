"""opportunities, organizations, evaluations and applicant-count observations

Revision ID: 4f8e2a71c9b3
Revises: 705732ddfa74
Create Date: 2026-10-18 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4f8e2a71c9b3'
down_revision: Union[str, None] = '705732ddfa74'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _batch_naming() -> dict:
    """SQLite batch recreate needs named constraints; baseline tables have
    unnamed FKs, so reflection renders them via this convention."""
    return {
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }


def upgrade() -> None:
    op.create_table(
        'organizations',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('name', sa.String(length=512), nullable=True),
        sa.Column('domain', sa.String(length=512), nullable=True),
        sa.Column('website', sa.Text(), nullable=True),
        sa.Column('location', sa.String(length=512), nullable=True),
        sa.Column('sources', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_organizations_user_id', 'organizations', ['user_id'])
    op.create_index('ix_organizations_name', 'organizations', ['name'])
    op.create_index('ix_organizations_domain', 'organizations', ['domain'])

    op.create_table(
        'opportunities',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('organization_id', sa.String(length=36), sa.ForeignKey('organizations.id'), nullable=False),
        sa.Column('kind', sa.String(length=16), nullable=False, server_default='vacancy'),
        sa.Column('job_id', sa.String(length=36), sa.ForeignKey('jobs.id'), nullable=True),
        sa.Column('title', sa.String(length=512), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('priority_score', sa.Float(), nullable=True),
        sa.Column('latest_evaluation_id', sa.String(length=36), sa.ForeignKey('opportunity_evaluations.id'), nullable=True),
        sa.Column('eligibility_status', sa.String(length=16), nullable=False, server_default='unknown'),
        sa.Column('fit_classification', sa.String(length=32), nullable=False, server_default='needs_review'),
        sa.Column('fit_score', sa.Float(), nullable=True),
        sa.Column('competition_status', sa.String(length=16), nullable=False, server_default='unknown'),
        sa.Column('competition_count', sa.Integer(), nullable=True),
        sa.Column('competition_comparable', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('competition_observed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('competition_platform', sa.String(length=128), nullable=True),
        sa.Column('competition_meaning', sa.String(length=128), nullable=True),
        sa.Column('potentially_overlooked', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('excluded', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('exclusion_reason', sa.Text(), nullable=True),
        sa.Column('source_evidence', sa.JSON(), nullable=True),
        sa.Column('first_seen_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "(kind = 'startup_prospect') OR (job_id IS NOT NULL AND title IS NOT NULL)",
            name='ck_opportunity_vacancy_requires_listing',
        ),
    )
    op.create_index('ix_opportunities_user_id', 'opportunities', ['user_id'])
    op.create_index('ix_opportunities_organization_id', 'opportunities', ['organization_id'])
    op.create_index('ix_opportunities_kind', 'opportunities', ['kind'])
    op.create_index('ix_opportunities_excluded', 'opportunities', ['excluded'])

    op.create_table(
        'opportunity_evaluations',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('opportunity_id', sa.String(length=36), sa.ForeignKey('opportunities.id'), nullable=False),
        sa.Column('evaluation_no', sa.Integer(), nullable=False),
        sa.Column('eligibility_status', sa.String(length=16), nullable=False, server_default='unknown'),
        sa.Column('eligibility_reasons', sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column('eligibility_checks', sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column('fit_classification', sa.String(length=32), nullable=False, server_default='needs_review'),
        sa.Column('fit_score', sa.Float(), nullable=True),
        sa.Column('fit_factors', sa.JSON(), nullable=True),
        sa.Column('fit_conflicts', sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column('fit_unknowns', sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column('competition', sa.JSON(), nullable=True),
        sa.Column('signals', sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column('priority_score', sa.Float(), nullable=True),
        sa.Column('contributions', sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column('coverage', sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column('config', sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_opportunity_evaluations_user_id', 'opportunity_evaluations', ['user_id'])
    op.create_index('ix_opportunity_evaluations_opportunity_id', 'opportunity_evaluations', ['opportunity_id'])
    # Batch mode: plain ALTER of constraints does not work on SQLite.
    with op.batch_alter_table('opportunity_evaluations', naming_convention=_batch_naming()) as batch:
        batch.create_unique_constraint(
            'uq_evaluation_no_per_opportunity', ['opportunity_id', 'evaluation_no']
        )

    op.create_table(
        'applicant_count_observations',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('opportunity_id', sa.String(length=36), sa.ForeignKey('opportunities.id'), nullable=False),
        sa.Column('observed_count', sa.Integer(), nullable=False),
        sa.Column('platform', sa.String(length=128), nullable=True),
        sa.Column('source', sa.Text(), nullable=True),
        sa.Column('observed_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('meaning', sa.String(length=128), nullable=False, server_default='unknown'),
        sa.Column('comparable', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_applicant_count_observations_user_id', 'applicant_count_observations', ['user_id'])
    op.create_index('ix_applicant_count_observations_opportunity_id', 'applicant_count_observations', ['opportunity_id'])

    with op.batch_alter_table('applications', naming_convention=_batch_naming()) as batch:
        batch.add_column(sa.Column('opportunity_id', sa.String(length=36), nullable=True))
        batch.create_foreign_key(
            'fk_applications_opportunity_id_opportunities',
            'opportunities',
            ['opportunity_id'],
            ['id'],
        )
        batch.create_index('ix_applications_opportunity_id', ['opportunity_id'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_applications_opportunity_id', table_name='applications')
    with op.batch_alter_table('applications', naming_convention=_batch_naming()) as batch:
        batch.drop_column('opportunity_id')
    op.drop_table('applicant_count_observations')
    op.drop_index('ix_opportunity_evaluations_opportunity_id', table_name='opportunity_evaluations')
    with op.batch_alter_table('opportunity_evaluations', naming_convention=_batch_naming()) as batch:
        batch.drop_constraint('uq_evaluation_no_per_opportunity', type_='unique')
    op.drop_index('ix_opportunity_evaluations_user_id', table_name='opportunity_evaluations')
    op.drop_table('opportunity_evaluations')
    op.drop_index('ix_opportunities_excluded', table_name='opportunities')
    op.drop_index('ix_opportunities_kind', table_name='opportunities')
    op.drop_index('ix_opportunities_organization_id', table_name='opportunities')
    op.drop_index('ix_opportunities_user_id', table_name='opportunities')
    op.drop_table('opportunities')
    op.drop_index('ix_organizations_domain', table_name='organizations')
    op.drop_index('ix_organizations_name', table_name='organizations')
    op.drop_index('ix_organizations_user_id', table_name='organizations')
    op.drop_table('organizations')
