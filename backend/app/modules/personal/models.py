from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class CustomItem(Base):
    __tablename__ = "user_custom_items"
    __table_args__ = (
        CheckConstraint("type IN ('DHIKR','DUA')", name="custom_type"),
        CheckConstraint("target_count BETWEEN 1 AND 1000", name="custom_target"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    activity_code: Mapped[str] = mapped_column(String(80))
    type: Mapped[str] = mapped_column(String(8))
    text_ar: Mapped[str] = mapped_column(Text)
    target_count: Mapped[int] = mapped_column(Integer)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GroupPlan(Base):
    __tablename__ = "user_group_plans"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "activity_code", "effective_from", name="plan_user_group_date"
        ),
        CheckConstraint("row_version >= 1", name="plan_version"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    activity_code: Mapped[str] = mapped_column(String(80))
    effective_from: Mapped[date] = mapped_column(Date)
    row_version: Mapped[int] = mapped_column(Integer)
    definition: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
