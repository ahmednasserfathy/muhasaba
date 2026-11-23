from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class FastingOverride(Base):
    __tablename__ = "fasting_overrides"
    __table_args__ = (
        UniqueConstraint("user_id", "local_date", name="fasting_user_date"),
        CheckConstraint("mode IN ('DEFAULT','ADD','SKIP')", name="fasting_mode"),
        CheckConstraint(
            "fast_type IN ('VOLUNTARY','MAKEUP','OTHER')", name="fasting_type"
        ),
        CheckConstraint(
            "mode = 'ADD' OR fast_type IS NULL", name="fasting_type_only_add"
        ),
        CheckConstraint("row_version >= 1", name="fasting_version"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    local_date: Mapped[date] = mapped_column(Date)
    mode: Mapped[str] = mapped_column(String(8))
    fast_type: Mapped[str | None] = mapped_column(String(16))
    row_version: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CalendarPeriod(Base):
    __tablename__ = "calendar_periods"
    __table_args__ = (
        UniqueConstraint(
            "region_key", "period_kind", "start_date", name="calendar_region_start"
        ),
        CheckConstraint("period_kind = 'RAMADAN'", name="calendar_kind"),
        CheckConstraint(
            "confirmation_status IN ('PROVISIONAL','CONFIRMED')",
            name="calendar_confirmation",
        ),
        CheckConstraint("end_date >= start_date", name="calendar_dates"),
        CheckConstraint(
            "confirmation_status <> 'CONFIRMED' OR "
            "(source_url IS NOT NULL AND length(trim(source_url)) > 0)",
            name="calendar_confirmed_source",
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    region_key: Mapped[str] = mapped_column(String(32))
    period_kind: Mapped[str] = mapped_column(String(20), default="RAMADAN")
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    confirmation_status: Mapped[str] = mapped_column(String(12))
    source_url: Mapped[str | None] = mapped_column(String(2048))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
