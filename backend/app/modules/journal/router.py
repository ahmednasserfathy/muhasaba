from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.modules.auth.models import User
from app.modules.auth.router import Database, current_user
from app.modules.journal import service
from app.modules.journal.schemas import CountWrite, DayView, SetWrite, StateWrite

router = APIRouter(prefix="/api/v1/days", tags=["journal"])
Account = Annotated[User, Depends(current_user)]


@router.get("/today", response_model=DayView)
def get_today(user: Account, db: Database):
    day_date = service.today(user)
    db.scalar(select(User).where(User.id == user.id).with_for_update(read=True))
    service.validate_date(user, day_date)
    return service.day_view(db, user, day_date)


@router.get("/{day_date}", response_model=DayView)
def get_day(day_date: date, user: Account, db: Database):
    db.scalar(select(User).where(User.id == user.id).with_for_update(read=True))
    service.validate_date(user, day_date)
    return service.day_view(db, user, day_date)


@router.put("/{day_date}/activities/{code}", response_model=DayView)
def set_state(day_date: date, code: str, data: StateWrite, user: Account, db: Database):
    return service.write(db, user, day_date, "state", code, data)


@router.put("/{day_date}/adhkar/{item_key}", response_model=DayView)
def set_count(
    day_date: date, item_key: str, data: CountWrite, user: Account, db: Database
):
    return service.write(db, user, day_date, "count", item_key, data)


@router.put("/{day_date}/adhkar-sets/{code}", response_model=DayView)
def set_all(day_date: date, code: str, data: SetWrite, user: Account, db: Database):
    return service.write(db, user, day_date, "set", code, data)
