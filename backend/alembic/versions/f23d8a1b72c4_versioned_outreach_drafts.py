"""versioned offline outreach drafts

Revision ID: f23d8a1b72c4
Revises: e1a7c4b902d6
Create Date: 2026-10-18 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f23d8a1b72c4"
down_revision: Union[str, None] = "e1a7c4b902d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "outreach_drafts",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("opportunity_id", sa.String(36), nullable=False),
        sa.Column("mode", sa.String(16), nullable=False),
        sa.Column("recipient_email", sa.String(320), nullable=False),
        sa.Column("recipient_name", sa.String(256), nullable=True),
        sa.Column("recipient_role", sa.String(256), nullable=True),
        sa.Column("recipient_identity", sa.String(24), nullable=False),
        sa.Column("contact_source_url", sa.Text(), nullable=True),
        sa.Column("contact_source_kind", sa.String(24), nullable=False),
        sa.Column("subject", sa.String(998), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("personalization", sa.JSON(), nullable=False),
        sa.Column("factuality_findings", sa.JSON(), nullable=False),
        sa.Column("resume_version_id", sa.String(36), nullable=True),
        sa.Column("attachment_name", sa.String(512), nullable=True),
        # Frozen text is returned only to this authenticated draft owner for review.
        sa.Column("attachment_text", sa.Text(), nullable=True),
        sa.Column("attachment_sha256", sa.String(64), nullable=True),
        sa.Column("payload_sha256", sa.String(64), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("approval_payload_sha256", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("mode IN ('vacancy','startup_introduction')", name="ck_outreach_draft_mode"),
        sa.CheckConstraint("recipient_identity IN ('known','unknown')", name="ck_outreach_draft_identity"),
        sa.CheckConstraint("revision >= 1", name="ck_outreach_draft_revision"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resume_version_id"], ["resume_versions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for col in ("user_id", "opportunity_id", "payload_sha256"):
        op.create_index(f"ix_outreach_drafts_{col}", "outreach_drafts", [col])
    op.create_index("ix_outreach_drafts_user_opportunity", "outreach_drafts", ["user_id", "opportunity_id"])

    op.create_table(
        "outreach_draft_versions",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("draft_id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("payload_sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["draft_id"], ["outreach_drafts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("draft_id", "revision", name="uq_outreach_draft_revision"),
    )
    op.create_index("ix_outreach_draft_versions_draft_id", "outreach_draft_versions", ["draft_id"])
    op.create_index("ix_outreach_draft_versions_user_id", "outreach_draft_versions", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_outreach_draft_versions_user_id", table_name="outreach_draft_versions")
    op.drop_index("ix_outreach_draft_versions_draft_id", table_name="outreach_draft_versions")
    op.drop_table("outreach_draft_versions")
    op.drop_index("ix_outreach_drafts_user_opportunity", table_name="outreach_drafts")
    for col in ("user_id", "opportunity_id", "payload_sha256"):
        op.drop_index(f"ix_outreach_drafts_{col}", table_name="outreach_drafts")
    op.drop_table("outreach_drafts")
