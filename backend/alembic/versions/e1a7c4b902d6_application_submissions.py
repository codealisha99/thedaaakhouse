"""application submission packages and receipts

Revision ID: e1a7c4b902d6
Revises: d3a9c8e5f1b6
Create Date: 2026-10-18 13:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e1a7c4b902d6"
down_revision: Union[str, None] = "d3a9c8e5f1b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_ACTIVE = "state IN ('ready','queued','submitting','unknown')"


def upgrade() -> None:
    op.create_table(
        "application_submissions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("application_id", sa.String(length=36), nullable=False),
        sa.Column("adapter", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("state_reason", sa.Text(), nullable=False),
        sa.Column("package", sa.JSON(), nullable=False),
        sa.Column("package_sha256", sa.String(length=64), nullable=False),
        sa.Column("artifact_snapshot", sa.Text(), nullable=False),
        sa.Column("artifact_sha256", sa.String(length=64), nullable=False),
        sa.Column("resume_version_id", sa.String(length=36), nullable=True),
        sa.Column("resume_source", sa.String(length=32), nullable=False),
        sa.Column("destination_url", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("task_id", sa.String(length=36), nullable=True),
        sa.Column("receipt", sa.JSON(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint(
            "state IN ('ready','queued','submitting','submitted','failed','unknown','cancelled')",
            name="ck_application_submissions_state",
        ),
        sa.CheckConstraint("attempts >= 0", name="ck_application_submissions_attempts"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resume_version_id"], ["resume_versions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_submissions_idem"),
    )
    for col in ("user_id", "application_id", "state", "package_sha256", "artifact_sha256", "task_id"):
        op.create_index(f"ix_application_submissions_{col}", "application_submissions", [col])
    op.create_index(
        "uq_submissions_active_package",
        "application_submissions",
        ["user_id", "application_id", "package_sha256"],
        unique=True,
        sqlite_where=sa.text(_ACTIVE),
        postgresql_where=sa.text(_ACTIVE),
    )


def downgrade() -> None:
    op.drop_index("uq_submissions_active_package", table_name="application_submissions")
    for col in ("user_id", "application_id", "state", "package_sha256", "artifact_sha256", "task_id"):
        op.drop_index(f"ix_application_submissions_{col}", table_name="application_submissions")
    op.drop_table("application_submissions")
