from datetime import UTC, date, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field, HttpUrl, field_validator
from sqlalchemy import delete, select

from app.modules.auth.models import User
from app.modules.auth.router import Database, current_user
from app.modules.catalog.models import (
    Activity,
    AdhkarItem,
    CatalogRelease,
    LibraryEntry,
)
from app.modules.journal.schemas import JournalModel, Version
from app.modules.journal.service import today
from app.modules.personal.transactions import mutate

router = APIRouter(prefix="/api/v1/admin", tags=["editorial"])


def admin(user: Annotated[User, Depends(current_user)]):
    if user.role != "ADMIN":
        raise HTTPException(403, "Administrator role required")
    return user


Admin = Annotated[User, Depends(admin)]


class Edit(JournalModel):
    client_mutation_id: UUID
    expected_version: Version


class LibraryWrite(Edit):
    code: str = Field(min_length=1, max_length=90, pattern=r"^[a-zA-Z0-9_-]+$")
    type: Literal["DHIKR", "DUA"]
    title_ar: str = Field(max_length=500, default="")
    text_ar: str = Field(min_length=1, max_length=20000)
    default_target_count: int = Field(strict=True, ge=1, le=1000)
    source_name: str = Field(min_length=1, max_length=500)
    source_url: HttpUrl
    license_notes: str = Field(min_length=1, max_length=2000)
    verified: bool = False

    @field_validator("text_ar", "source_name", "license_notes")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Provenance and text must not be blank")
        return value


class ReleaseWrite(Edit):
    base_release_id: UUID
    code: str = Field(min_length=1, max_length=50)
    effective_from: date


class Binding(JournalModel):
    library_entry_id: UUID
    code: str = Field(min_length=1, max_length=90, pattern=r"^[a-zA-Z0-9_-]+$")
    target_count: int = Field(strict=True, ge=1, le=1000)
    is_score_eligible: bool = True


class BindingsWrite(Edit):
    items: list[Binding] = Field(max_length=1000)


def library_view(row):
    return dict(
        id=str(row.id),
        code=row.code,
        type=row.type,
        titleAr=row.title_ar,
        textAr=row.text_ar,
        defaultTargetCount=row.default_target_count,
        sourceName=row.source_name,
        sourceUrl=row.source_url,
        licenseNotes=row.license_notes,
        reviewStatus=row.review_status,
        status=row.status,
        rowVersion=row.row_version,
        reviewedAt=row.reviewed_at.isoformat() if row.reviewed_at else None,
        reviewedBy=str(row.reviewed_by) if row.reviewed_by else None,
    )


def release_view(row):
    return dict(
        id=str(row.id),
        code=row.code,
        effectiveFrom=str(row.effective_from),
        status=row.status,
        rowVersion=row.row_version,
    )


def locked(db, model, key, version):
    row = db.scalar(select(model).where(model.id == key).with_for_update())
    if row is None:
        raise HTTPException(404, "Unknown editorial resource")
    if row.row_version != version:
        raise HTTPException(409, "Editorial version changed")
    return row


@router.get("/library-items")
def list_library(user: Admin, db: Database):
    return [
        library_view(row)
        for row in db.scalars(
            select(LibraryEntry).order_by(LibraryEntry.code).limit(1000)
        )
    ]


def save_library(db, user, data, key=None):
    if key:
        row = locked(db, LibraryEntry, key, data.expected_version)
        if row.status == "ARCHIVED":
            raise HTTPException(409, "Create a new draft for archived content")
        row.row_version += 1
    else:
        if data.expected_version != 0:
            raise HTTPException(409, "New content starts at version zero")
        row = LibraryEntry(created_by_admin=user.id)
        db.add(row)
    for field in (
        "code",
        "type",
        "title_ar",
        "text_ar",
        "default_target_count",
        "source_name",
        "license_notes",
    ):
        setattr(row, field, getattr(data, field))
    row.source_url = str(data.source_url)
    row.review_status = "VERIFIED" if data.verified else "DRAFT"
    row.status = "ACTIVE" if data.verified else "DRAFT"
    row.reviewed_at = datetime.now(UTC) if data.verified else None
    row.reviewed_by = user.id if data.verified else None
    db.flush()
    return library_view(row)


@router.post("/library-items", status_code=201)
def create_library(data: LibraryWrite, user: Admin, db: Database):
    return mutate(
        db, user, "library-create", data, lambda: save_library(db, user, data)
    )


@router.patch("/library-items/{key}")
def edit_library(key: UUID, data: LibraryWrite, user: Admin, db: Database):
    return mutate(
        db, user, f"library-edit:{key}", data, lambda: save_library(db, user, data, key)
    )


@router.post("/library-items/{key}/archive")
def archive_library(key: UUID, data: Edit, user: Admin, db: Database):
    def operation():
        row = locked(db, LibraryEntry, key, data.expected_version)
        row.status, row.archived_at = "ARCHIVED", datetime.now(UTC)
        row.row_version += 1
        db.flush()
        return library_view(row)

    return mutate(db, user, f"library-archive:{key}", data, operation)


@router.get("/catalog-releases")
def releases(user: Admin, db: Database):
    return [
        release_view(row)
        for row in db.scalars(
            select(CatalogRelease)
            .order_by(CatalogRelease.effective_from.desc())
            .limit(100)
        )
    ]


@router.post("/catalog-releases", status_code=201)
def create_release(data: ReleaseWrite, user: Admin, db: Database):
    def operation():
        base = db.get(CatalogRelease, data.base_release_id)
        if base is None:
            raise HTTPException(404, "Unknown base release")
        if data.expected_version != 0 or data.effective_from <= today(user):
            raise HTTPException(422, "Create a future draft at version zero")
        # Publication and definition changes lock this row too.
        db.refresh(base, with_for_update=True)
        row = CatalogRelease(code=data.code, effective_from=data.effective_from)
        db.add(row)
        db.flush()
        for old in base.activities:
            activity = Activity(
                catalog_release_id=row.id,
                **{
                    field: getattr(old, field)
                    for field in (
                        "category_id",
                        "code",
                        "title_ar",
                        "sort_order",
                        "points",
                        "kind",
                        "schedule_kind",
                        "is_active",
                        "description_ar",
                        "show_details",
                    )
                },
            )
            db.add(activity)
            db.flush()
            for item in old.items:
                db.add(
                    AdhkarItem(
                        activity_id=activity.id,
                        **{
                            field: getattr(item, field)
                            for field in (
                                "library_entry_id",
                                "code",
                                "text_ar",
                                "sort_order",
                                "target_count",
                                "source_name",
                                "source_url",
                                "license_notes",
                                "review_status",
                                "is_score_eligible",
                            )
                        },
                    )
                )
        db.flush()
        return release_view(row)

    return mutate(db, user, "release-create", data, operation)


@router.put("/catalog-releases/{key}/groups/{code}/items")
def bind_items(key: UUID, code: str, data: BindingsWrite, user: Admin, db: Database):
    def operation():
        row = locked(db, CatalogRelease, key, data.expected_version)
        if row.status != "DRAFT":
            raise HTTPException(409, "Published release is immutable")
        activity = next(
            (a for a in row.activities if a.code == code and a.kind == "ADHKAR_SET"),
            None,
        )
        if activity is None:
            raise HTTPException(404, "Unknown adhkar group")
        if len({i.code for i in data.items}) != len(data.items):
            raise HTTPException(422, "Duplicate binding code")
        db.execute(delete(AdhkarItem).where(AdhkarItem.activity_id == activity.id))
        for index, item in enumerate(data.items):
            source = db.scalar(
                select(LibraryEntry)
                .where(LibraryEntry.id == item.library_entry_id)
                .with_for_update(read=True)
            )
            if (
                source is None
                or source.status != "ACTIVE"
                or source.review_status != "VERIFIED"
                or source.reviewed_at is None
            ):
                raise HTTPException(
                    422, "Only reviewed active library sources can be bound"
                )
            db.add(
                AdhkarItem(
                    activity_id=activity.id,
                    library_entry_id=source.id,
                    code=item.code,
                    text_ar=source.text_ar,
                    target_count=item.target_count,
                    sort_order=index,
                    source_name=source.source_name,
                    source_url=source.source_url,
                    license_notes=source.license_notes,
                    review_status="VERIFIED",
                    is_score_eligible=item.is_score_eligible,
                )
            )
        row.row_version += 1
        db.flush()
        return release_view(row)

    return mutate(db, user, f"bindings:{key}:{code}", data, operation)


@router.post("/catalog-releases/{key}/publish")
def publish_release(key: UUID, data: Edit, user: Admin, db: Database):
    def operation():
        row = locked(db, CatalogRelease, key, data.expected_version)
        if row.status != "DRAFT" or row.effective_from <= today(user):
            raise HTTPException(409, "Publish a future draft only")
        row.status, row.published_at = "PUBLISHED", datetime.now(UTC)
        row.row_version += 1
        db.flush()  # Database publication guards validate every immutable binding.
        return release_view(row)

    return mutate(db, user, f"publish:{key}", data, operation)
