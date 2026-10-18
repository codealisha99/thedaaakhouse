"""Gmail OAuth account storage and outreach delivery ledger.

Revision ID: 6b41ce2a0901
Revises: f23d8a1b72c4
"""
from alembic import op
import sqlalchemy as sa

revision = "6b41ce2a0901"
down_revision = "f23d8a1b72c4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("email_accounts",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False), sa.Column("email", sa.String(320), nullable=False),
        sa.Column("refresh_token_ciphertext", sa.Text(), nullable=False), sa.Column("status", sa.String(16), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"), sa.UniqueConstraint("user_id"))
    op.create_index("ix_email_accounts_user_id", "email_accounts", ["user_id"])
    op.create_index("ix_email_accounts_status", "email_accounts", ["status"])
    op.create_table("gmail_oauth_states", sa.Column("state_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"))
    op.create_index("ix_gmail_oauth_states_user_id", "gmail_oauth_states", ["user_id"])
    op.create_table("outreach_sends",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("draft_id", sa.String(36), nullable=False), sa.Column("task_id", sa.String(36), nullable=False),
        sa.Column("payload_sha256", sa.String(64), nullable=False), sa.Column("payload_snapshot", sa.JSON(), nullable=False),
        sa.Column("message_id_header", sa.String(255), nullable=False), sa.Column("provider_message_id", sa.String(255)),
        sa.Column("thread_id", sa.String(255)), sa.Column("status", sa.String(24), nullable=False), sa.Column("last_history_id", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["draft_id"], ["outreach_drafts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["task_runs.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "draft_id", "payload_sha256", name="uq_outreach_send_payload"),
        sa.UniqueConstraint("task_id"), sa.UniqueConstraint("message_id_header"))
    for col in ("user_id", "draft_id", "payload_sha256", "provider_message_id", "status"):
        op.create_index(f"ix_outreach_sends_{col}", "outreach_sends", [col])
    op.create_index("ix_outreach_sends_user_status", "outreach_sends", ["user_id", "status"])
    op.create_table("outreach_delivery_events",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("send_id", sa.String(36), nullable=False), sa.Column("event_key", sa.String(255), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False), sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["send_id"], ["outreach_sends.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "event_key", name="uq_outreach_event_key"))
    op.create_index("ix_outreach_delivery_events_user_id", "outreach_delivery_events", ["user_id"])
    op.create_index("ix_outreach_delivery_events_send_id", "outreach_delivery_events", ["send_id"])
    op.create_table("outreach_suppressions",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("email", sa.String(320), nullable=False), sa.Column("reason", sa.String(24), nullable=False),
        sa.Column("source_send_id", sa.String(36)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_send_id"], ["outreach_sends.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("user_id", "email", name="uq_outreach_suppression"))
    op.create_index("ix_outreach_suppressions_user_id", "outreach_suppressions", ["user_id"])


def downgrade():
    op.drop_index("ix_outreach_suppressions_user_id", table_name="outreach_suppressions")
    op.drop_table("outreach_suppressions")
    op.drop_index("ix_outreach_delivery_events_send_id", table_name="outreach_delivery_events")
    op.drop_index("ix_outreach_delivery_events_user_id", table_name="outreach_delivery_events")
    op.drop_table("outreach_delivery_events")
    op.drop_index("ix_outreach_sends_user_status", table_name="outreach_sends")
    for col in ("user_id", "draft_id", "payload_sha256", "provider_message_id", "status"):
        op.drop_index(f"ix_outreach_sends_{col}", table_name="outreach_sends")
    op.drop_table("outreach_sends")
    op.drop_index("ix_gmail_oauth_states_user_id", table_name="gmail_oauth_states")
    op.drop_table("gmail_oauth_states")
    op.drop_index("ix_email_accounts_status", table_name="email_accounts")
    op.drop_index("ix_email_accounts_user_id", table_name="email_accounts")
    op.drop_table("email_accounts")
