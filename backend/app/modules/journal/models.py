from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
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


class JournalDay(Base):
    __tablename__ = "journal_days"
    __table_args__ = (
        UniqueConstraint("user_id", "local_date", name="journal_user_date"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    local_date: Mapped[date] = mapped_column(Date)
    catalog_release_id: Mapped[UUID] = mapped_column(
        ForeignKey("catalog_releases.id", ondelete="RESTRICT")
    )
    group_plans: Mapped[dict | None] = mapped_column(JSONB)
    fasting_baseline: Mapped[dict | None] = mapped_column(JSONB)
    timezone_at_creation: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ActivityState(Base):
    __tablename__ = "journal_activity_states"
    __table_args__ = (
        UniqueConstraint("journal_day_id", "activity_id", name="journal_day_activity"),
        CheckConstraint(
            "state IN ('PENDING','COMPLETED','EXCLUDED')", name="journal_state"
        ),
        CheckConstraint("row_version >= 1", name="activity_version"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    journal_day_id: Mapped[UUID] = mapped_column(
        ForeignKey("journal_days.id", ondelete="RESTRICT")
    )
    activity_id: Mapped[UUID] = mapped_column(
        ForeignKey("activities.id", ondelete="RESTRICT")
    )
    state: Mapped[str] = mapped_column(String(12))
    row_version: Mapped[int] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AdhkarCount(Base):
    __tablename__ = "journal_adhkar_counts"
    __table_args__ = (
        UniqueConstraint("journal_day_id", "adhkar_item_id", name="journal_day_item"),
        CheckConstraint(
            "target_count_snapshot BETWEEN 1 AND 1000", name="snapshot_target"
        ),
        CheckConstraint(
            "completed_count BETWEEN 0 AND target_count_snapshot", name="snapshot_count"
        ),
        CheckConstraint("row_version >= 0", name="count_version"),
        CheckConstraint(
            "(source_type = 'OFFICIAL' AND adhkar_item_id IS NOT NULL "
            "AND custom_item_id IS NULL) OR (source_type = 'PERSONAL' "
            "AND adhkar_item_id IS NULL AND custom_item_id IS NOT NULL "
            "AND NOT is_score_eligible_snapshot)",
            name="snapshot_source",
        ),
        UniqueConstraint(
            "journal_day_id",
            "activity_id",
            "custom_item_id",
            name="journal_day_custom_item",
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    journal_day_id: Mapped[UUID] = mapped_column(
        ForeignKey("journal_days.id", ondelete="RESTRICT")
    )
    activity_id: Mapped[UUID] = mapped_column(
        ForeignKey("activities.id", ondelete="RESTRICT")
    )
    custom_item_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("user_custom_items.id", ondelete="RESTRICT")
    )
    adhkar_item_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("adhkar_items.id", ondelete="RESTRICT")
    )
    item_code_snapshot: Mapped[str] = mapped_column(String(90))
    text_ar_snapshot: Mapped[str] = mapped_column(Text)
    target_count_snapshot: Mapped[int] = mapped_column(Integer)
    source_type: Mapped[str] = mapped_column(String(12), default="OFFICIAL")
    is_score_eligible_snapshot: Mapped[bool] = mapped_column(Boolean)
    sort_order: Mapped[int] = mapped_column(Integer)
    completed_count: Mapped[int] = mapped_column(Integer, default=0)
    row_version: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MutationReceipt(Base):
    __tablename__ = "mutation_receipts"
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    payload_hash: Mapped[str] = mapped_column(String(64))
    result_json: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
