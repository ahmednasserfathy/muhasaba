from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Category(Base):
    __tablename__ = "categories"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(30), unique=True)
    title_ar: Mapped[str] = mapped_column(String(100))
    sort_order: Mapped[int] = mapped_column(SmallInteger, unique=True)


class CatalogRelease(Base):
    __tablename__ = "catalog_releases"
    __table_args__ = (
        CheckConstraint("status IN ('DRAFT','PUBLISHED')", name="release_status"),
        CheckConstraint(
            "(status = 'PUBLISHED') = (published_at IS NOT NULL)",
            name="release_publication_time",
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(50), unique=True)
    effective_from: Mapped[date] = mapped_column(Date, unique=True)
    status: Mapped[str] = mapped_column(String(12), server_default="DRAFT")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    activities: Mapped[list["Activity"]] = relationship(order_by="Activity.sort_order")


class Activity(Base):
    __tablename__ = "activities"
    __table_args__ = (
        UniqueConstraint("catalog_release_id", "code", name="activity_release_code"),
        UniqueConstraint(
            "catalog_release_id", "category_id", "sort_order", name="activity_order"
        ),
        CheckConstraint("points >= 0", name="activity_points"),
        CheckConstraint(
            "kind IN ('TOGGLE','ADHKAR_SET','FASTING')", name="activity_kind"
        ),
        CheckConstraint(
            "schedule_kind IN ('DAILY','FASTING_DYNAMIC')", name="activity_schedule"
        ),
        CheckConstraint(
            "(kind = 'FASTING') = (schedule_kind = 'FASTING_DYNAMIC')",
            name="fasting_schedule",
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    catalog_release_id: Mapped[UUID] = mapped_column(
        ForeignKey("catalog_releases.id", ondelete="RESTRICT")
    )
    category_id: Mapped[UUID] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT")
    )
    code: Mapped[str] = mapped_column(String(80))
    title_ar: Mapped[str] = mapped_column(String(200))
    sort_order: Mapped[int] = mapped_column(SmallInteger)
    points: Mapped[int] = mapped_column(SmallInteger)
    kind: Mapped[str] = mapped_column(String(20))
    schedule_kind: Mapped[str] = mapped_column(String(24), server_default="DAILY")
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    description_ar: Mapped[str | None] = mapped_column(Text)
    show_details: Mapped[bool] = mapped_column(Boolean, server_default="false")
    category: Mapped[Category] = relationship()
    items: Mapped[list["AdhkarItem"]] = relationship(order_by="AdhkarItem.sort_order")


class LibraryEntry(Base):
    __tablename__ = "library_entries"
    __table_args__ = (
        CheckConstraint("type IN ('DHIKR','DUA')", name="library_type"),
        CheckConstraint(
            "default_target_count BETWEEN 1 AND 1000", name="library_target"
        ),
        CheckConstraint("review_status IN ('DRAFT','VERIFIED')", name="library_review"),
        CheckConstraint(
            "status IN ('DRAFT','ACTIVE','ARCHIVED')", name="library_status"
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(100), unique=True)
    type: Mapped[str] = mapped_column(String(8))
    title_ar: Mapped[str | None] = mapped_column(Text)
    text_ar: Mapped[str] = mapped_column(Text)
    default_target_count: Mapped[int] = mapped_column(SmallInteger)
    source_name: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    license_notes: Mapped[str | None] = mapped_column(Text)
    review_status: Mapped[str] = mapped_column(String(12), server_default="DRAFT")
    status: Mapped[str] = mapped_column(String(12), server_default="DRAFT")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AdhkarItem(Base):
    __tablename__ = "adhkar_items"
    __table_args__ = (
        UniqueConstraint("activity_id", "code", name="item_activity_code"),
        UniqueConstraint("activity_id", "sort_order", name="item_order"),
        CheckConstraint("target_count BETWEEN 1 AND 1000", name="item_target"),
        CheckConstraint("review_status IN ('DRAFT','VERIFIED')", name="item_review"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    activity_id: Mapped[UUID] = mapped_column(
        ForeignKey("activities.id", ondelete="RESTRICT")
    )
    library_entry_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("library_entries.id", ondelete="RESTRICT")
    )
    code: Mapped[str] = mapped_column(String(90))
    text_ar: Mapped[str] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(SmallInteger)
    target_count: Mapped[int] = mapped_column(SmallInteger)
    source_name: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    license_notes: Mapped[str | None] = mapped_column(Text)
    review_status: Mapped[str] = mapped_column(String(12), server_default="DRAFT")
    is_score_eligible: Mapped[bool] = mapped_column(Boolean, server_default="true")
