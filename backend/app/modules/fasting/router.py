from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.modules.auth.models import User
from app.modules.auth.router import Database
from app.modules.fasting import service
from app.modules.fasting.schemas import CalendarView, FastingView, PlanWrite
from app.modules.journal.router import Account
from app.modules.journal.service import today

router = APIRouter(prefix="/api/v1", tags=["fasting"])


@router.get("/fasting/calendar", response_model=CalendarView)
def calendar(
    user: Account,
    db: Database,
    start: Annotated[date, Query(alias="from")],
    end: Annotated[date, Query(alias="to")],
):
    if start < user.tracking_start_date or not 0 <= (end - start).days < 366:
        raise HTTPException(
            422, "Calendar range must be 1..366 days within tracking history"
        )
    db.scalar(select(User).where(User.id == user.id).with_for_update(read=True))
    return CalendarView(
        today=today(user),
        tracking_start_date=user.tracking_start_date,
        days=[
            service.view(db, user, start + timedelta(days=i))
            for i in range((end - start).days + 1)
        ],
    )


@router.put("/days/{day_date}/fasting-plan", response_model=FastingView)
def set_plan(day_date: date, data: PlanWrite, user: Account, db: Database):
    return service.write(db, user, day_date, data)
