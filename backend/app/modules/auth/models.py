from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "registration_source IN ('NATIVE','IMPORTED')", name="user_source"
        ),
        CheckConstraint("role IN ('USER','ADMIN')", name="user_role"),
        CheckConstraint(
            "registration_source <> 'NATIVE' OR "
            "(email_normalized IS NOT NULL AND password_hash IS NOT NULL)",
            name="native_credentials",
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    email_normalized: Mapped[str | None] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str | None] = mapped_column(Text)
    registration_source: Mapped[str] = mapped_column(
        String(12), server_default="NATIVE"
    )
    role: Mapped[str] = mapped_column(String(8), server_default="USER")
    timezone: Mapped[str] = mapped_column(String(64), server_default="Africa/Cairo")
    locale: Mapped[str] = mapped_column(String(16), server_default="ar-EG")
    region_key: Mapped[str] = mapped_column(String(32), server_default="EG")
    tracking_start_date: Mapped[date] = mapped_column(Date)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    access_token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    refresh_token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    access_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ExternalIdentity(Base):
    __tablename__ = "external_identities"
    __table_args__ = (
        UniqueConstraint(
            "source_system", "external_subject", name="external_source_subject"
        ),
        CheckConstraint(
            "link_status IN ('PENDING','VERIFIED','REVOKED')", name="identity_status"
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    source_system: Mapped[str] = mapped_column(String(60))
    external_subject: Mapped[str] = mapped_column(String(255))
    link_status: Mapped[str] = mapped_column(String(12), server_default="PENDING")
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class UserSettings(Base):
    __tablename__ = "user_settings"
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True
    )
    theme: Mapped[str] = mapped_column(String(12), server_default="DARK")
    reminder_settings: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    quiet_hours: Mapped[dict | None] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
