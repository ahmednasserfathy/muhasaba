from datetime import date, timedelta
from fractions import Fraction
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.modules.auth.models import User
from app.modules.auth.router import Database
from app.modules.catalog.scoring import display_percent
from app.modules.fasting.schemas import FastingView
from app.modules.journal import service
from app.modules.journal.router import Account
from app.modules.journal.schemas import DayView, JournalModel, Summary

router = APIRouter(prefix="/api/v1", tags=["reports"])


class Window(JournalModel):
    today: date
    tracking_start_date: date
    from_date: date
    to_date: date
    unavailable_dates: list[date]


class RestoreView(Window):
    days: list[DayView]


class ReportDay(JournalModel):
    date: date
    summary: Summary
    fasting: FastingView | None


class ReportView(Window):
    days: list[ReportDay]
    summary: Summary


def read_window(db, user, start, end):
    if end < start or (end - start).days >= 31:
        raise HTTPException(422, "Choose an inclusive range of 1 to 31 days")
    db.scalar(select(User).where(User.id == user.id).with_for_update(read=True))
    current = service.today(user)
    first, last = max(start, user.tracking_start_date), min(end, current)
    days, missing = [], []
    earned, possible = Fraction(0), 0
    cursor = first
    while cursor <= last:
        try:
            day, score = service.day_view_with_score(db, user, cursor)
        except HTTPException as error:
            if error.status_code != 404:
                raise
            missing.append(cursor)
        else:
            days.append(day)
            earned += score.earned
            possible += int(score.possible)
        cursor += timedelta(days=1)
    metadata = dict(
        today=current,
        tracking_start_date=user.tracking_start_date,
        from_date=start,
        to_date=end,
        unavailable_dates=missing,
    )
    summary = Summary(
        earned=float(earned),
        possible=possible,
        percent=display_percent(100 * earned / possible if possible else None),
    )
    return metadata, days, summary


@router.get("/days", response_model=RestoreView)
def restore_days(
    user: Account,
    db: Database,
    start: Annotated[date, Query(alias="from")],
    end: Annotated[date, Query(alias="to")],
):
    metadata, days, _ = read_window(db, user, start, end)
    return RestoreView(**metadata, days=days)


@router.get("/reports/summary", response_model=ReportView)
def report_summary(
    user: Account,
    db: Database,
    start: Annotated[date, Query(alias="from")],
    end: Annotated[date, Query(alias="to")],
):
    metadata, days, summary = read_window(db, user, start, end)
    return ReportView(
        **metadata,
        summary=summary,
        days=[
            ReportDay(date=d.date, summary=d.summary, fasting=d.fasting) for d in days
        ],
    )
