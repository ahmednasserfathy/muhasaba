from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.db import get_session
from app.modules.catalog.models import Activity, CatalogRelease
from app.modules.catalog.schemas import (
    ActivityResponse,
    CatalogResponse,
    CategoryResponse,
    ItemResponse,
)

router = APIRouter(prefix="/api/v1", tags=["catalog"])


@router.get(
    "/catalog",
    response_model=CatalogResponse,
    responses={
        404: {"description": "No published release for this date"},
        503: {"description": "Catalog database unavailable"},
    },
)
def get_catalog(
    date: Annotated[date, Query(description="Explicit local date (YYYY-MM-DD)")],
    session: Annotated[Session, Depends(get_session)],
) -> CatalogResponse:
    """Public official catalog only; no user-specific state or editorial drafts."""
    release = session.scalar(
        select(CatalogRelease)
        .where(
            CatalogRelease.status == "PUBLISHED", CatalogRelease.effective_from <= date
        )
        .order_by(CatalogRelease.effective_from.desc())
        .limit(1)
        .options(
            selectinload(CatalogRelease.activities).selectinload(Activity.category),
            selectinload(CatalogRelease.activities).selectinload(Activity.items),
        )
    )
    if release is None:
        raise HTTPException(404, "No published catalog for this date")
    categories = {}
    for activity in release.activities:
        if not activity.is_active:
            continue
        category = activity.category
        if category.code not in categories:
            categories[category.code] = CategoryResponse(
                code=category.code,
                title_ar=category.title_ar,
                sort_order=category.sort_order,
                activities=[],
            )
        categories[category.code].activities.append(
            ActivityResponse(
                code=activity.code,
                title_ar=activity.title_ar,
                sort_order=activity.sort_order,
                points=activity.points,
                kind=activity.kind,
                schedule_kind=activity.schedule_kind,
                show_details=activity.show_details,
                items=[
                    ItemResponse(
                        code=item.code,
                        sort_order=item.sort_order,
                        target_count=item.target_count,
                        text_ar=item.text_ar,
                        review_status=item.review_status,
                        is_score_eligible=item.is_score_eligible,
                        source_name=item.source_name,
                        source_url=item.source_url,
                        license_notes=item.license_notes,
                    )
                    for item in activity.items
                    if item.review_status == "VERIFIED"
                ],
            )
        )
    return CatalogResponse(
        release=release.code,
        categories=sorted(
            categories.values(), key=lambda category: category.sort_order
        ),
    )
