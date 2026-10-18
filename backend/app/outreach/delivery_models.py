"""Provider account, immutable send ledger, events and suppression state."""
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.database import Base, TimestampMixin, uuid_key


class EmailAccount(Base, TimestampMixin):
    __tablename__ = "email_accounts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_key)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    provider: Mapped[str] = mapped_column(String(32), default="gmail")
    email: Mapped[str] = mapped_column(String(320))
    refresh_token_ciphertext: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="connected", index=True)
    scopes: Mapped[list] = mapped_column(JSON, default=list)


class GmailOAuthState(Base):
    __tablename__ = "gmail_oauth_states"
    state_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class OutreachSend(Base, TimestampMixin):
    __tablename__ = "outreach_sends"
    __table_args__ = (UniqueConstraint("user_id", "draft_id", "payload_sha256", name="uq_outreach_send_payload"),
                      Index("ix_outreach_sends_user_status", "user_id", "status"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_key)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    draft_id: Mapped[str] = mapped_column(String(36), ForeignKey("outreach_drafts.id", ondelete="CASCADE"), index=True)
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("task_runs.id", ondelete="CASCADE"), unique=True)
    payload_sha256: Mapped[str] = mapped_column(String(64), index=True)
    payload_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    message_id_header: Mapped[str] = mapped_column(String(255), unique=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    thread_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    last_history_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class OutreachDeliveryEvent(Base):
    __tablename__ = "outreach_delivery_events"
    __table_args__ = (UniqueConstraint("user_id", "event_key", name="uq_outreach_event_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_key)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    send_id: Mapped[str] = mapped_column(String(36), ForeignKey("outreach_sends.id", ondelete="CASCADE"), index=True)
    event_key: Mapped[str] = mapped_column(String(255))
    kind: Mapped[str] = mapped_column(String(24))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)


class OutreachSuppression(Base, TimestampMixin):
    __tablename__ = "outreach_suppressions"
    __table_args__ = (UniqueConstraint("user_id", "email", name="uq_outreach_suppression"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_key)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(320))
    reason: Mapped[str] = mapped_column(String(24))
    source_send_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("outreach_sends.id", ondelete="SET NULL"), nullable=True)
