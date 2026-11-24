from datetime import date, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.modules.auth.models import User
from app.modules.auth.router import Database
from app.modules.journal import service as journal
from app.modules.journal.router import Account
from app.modules.personal import service
from app.modules.personal.models import CustomItem
from app.modules.personal.schemas import ItemContext, ItemWrite, PlanView, PlanWrite
from app.modules.personal.transactions import mutate

router = APIRouter(prefix="/api/v1/me", tags=["personal"])


@router.get("/custom-items")
def items(user: Account, db: Database):
    return [
        dict(
            id=str(r.id),
            activityCode=r.activity_code,
            type=r.type,
            textAr=r.text_ar,
            targetCount=r.target_count,
            archived=r.archived_at is not None,
        )
        for r in db.scalars(
            select(CustomItem)
            .where(CustomItem.user_id == user.id)
            .order_by(CustomItem.id)
            .limit(1000)
        )
    ]


@router.get("/groups/{code}/plan", response_model=PlanView)
def plan(
    code: str, user: Account, db: Database, date: Annotated[date | None, Query()] = None
):
    db.scalar(select(User).where(User.id == user.id).with_for_update(read=True))
    return service.view(db, user, code, date or journal.today(user) + timedelta(days=1))


@router.put("/groups/{code}/plan", response_model=PlanView)
def save(code: str, data: PlanWrite, user: Account, db: Database):
    return mutate(
        db, user, f"plan:{code}", data, lambda: service.apply(db, user, code, data)
    )


@router.post("/groups/{code}/restore-defaults", response_model=PlanView)
def restore(code: str, data: PlanWrite, user: Account, db: Database):
    cleared = data.model_copy(
        update={"hidden_default_codes": [], "official_order": [], "custom_items": []}
    )
    return mutate(
        db,
        user,
        f"restore-plan:{code}",
        data,
        lambda: service.apply(db, user, code, cleared),
    )


@router.post("/custom-items", response_model=PlanView, status_code=201)
def create_item(data: ItemWrite, user: Account, db: Database):
    return mutate(
        db,
        user,
        "custom-create",
        data,
        lambda: service.edit_item(db, user, data, data.item.id, "create"),
    )


@router.patch("/custom-items/{key}", response_model=PlanView)
def patch_item(key: UUID, data: ItemWrite, user: Account, db: Database):
    return mutate(
        db,
        user,
        f"custom-edit:{key}",
        data,
        lambda: service.edit_item(db, user, data, key, "edit"),
    )


@router.delete("/custom-items/{key}", response_model=PlanView)
def archive_item(key: UUID, data: ItemContext, user: Account, db: Database):
    return mutate(
        db,
        user,
        f"custom-archive:{key}",
        data,
        lambda: service.edit_item(db, user, data, key, "delete"),
    )
