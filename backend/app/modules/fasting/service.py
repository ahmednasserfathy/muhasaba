import hashlib
import json

from fastapi import HTTPException
from sqlalchemy import select

from app.modules.auth.models import User
from app.modules.fasting.models import CalendarPeriod, FastingOverride
from app.modules.fasting.schemas import FastingView
from app.modules.journal.models import JournalDay, MutationReceipt


def base_policy(day_date, region_key, periods):
    matches = [
        p
        for p in periods
        if p.region_key == region_key and p.start_date <= day_date <= p.end_date
    ]
    confirmed = sorted(
        (p for p in matches if p.confirmation_status == "CONFIRMED"),
        key=lambda p: p.start_date,
        reverse=True,
    )
    return {
        "regionKey": region_key,
        "baseReason": "RAMADAN"
        if confirmed
        else "WEEKLY"
        if day_date.weekday() in (0, 3)
        else "UNPLANNED",
        "calendarStatus": "CONFIRMED"
        if confirmed
        else "PROVISIONAL"
        if matches
        else "UNAVAILABLE",
        "sourceUrl": confirmed[0].source_url if confirmed else None,
    }


def baseline(db, user, day_date):
    periods = db.scalars(
        select(CalendarPeriod).where(
            CalendarPeriod.region_key == user.region_key,
            CalendarPeriod.start_date <= day_date,
            CalendarPeriod.end_date >= day_date,
        )
    ).all()
    return base_policy(day_date, user.region_key, periods)


def view(db, user, day_date, day=None):
    if day is None:
        day = db.scalar(
            select(JournalDay).where(
                JournalDay.user_id == user.id, JournalDay.local_date == day_date
            )
        )
    base = (
        day.fasting_baseline
        if day and day.fasting_baseline
        else baseline(db, user, day_date)
    )
    row = db.scalar(
        select(FastingOverride).where(
            FastingOverride.user_id == user.id, FastingOverride.local_date == day_date
        )
    )
    mode = row.mode if row else "DEFAULT"
    reason = (
        "SKIP" if mode == "SKIP" else "ADDED" if mode == "ADD" else base["baseReason"]
    )
    return FastingView(
        date=day_date,
        **base,
        mode=mode,
        fast_type=row.fast_type if row else None,
        row_version=row.row_version if row else 0,
        reason=reason,
        eligible=reason not in ("SKIP", "UNPLANNED"),
        pinned=bool(day and day.fasting_baseline),
    )


def write(db, user, day_date, data):
    from app.modules.journal.service import conflict

    try:
        db.scalar(select(User).where(User.id == user.id).with_for_update())
        payload = json.dumps(
            [str(day_date), "fasting-plan", data.model_dump(mode="json")],
            sort_keys=True,
            separators=(",", ":"),
        )
        digest = hashlib.sha256(payload.encode()).hexdigest()
        receipt = db.get(MutationReceipt, (user.id, data.client_mutation_id))
        if receipt:
            if receipt.payload_hash != digest:
                conflict("IDEMPOTENCY_KEY_REUSE")
            result = FastingView.model_validate(receipt.result_json)
            db.commit()
            return result
        if day_date < user.tracking_start_date:
            raise HTTPException(422, "Date precedes tracking start")
        row = db.scalar(
            select(FastingOverride).where(
                FastingOverride.user_id == user.id,
                FastingOverride.local_date == day_date,
            )
        )
        version = row.row_version if row else 0
        if version != data.expected_version:
            conflict(
                "CONFLICT",
                view(db, user, day_date).model_dump(mode="json", by_alias=True),
            )
        if row is None:
            row = FastingOverride(user_id=user.id, local_date=day_date)
            db.add(row)
        row.mode, row.fast_type, row.row_version = (
            data.mode,
            data.fast_type,
            version + 1,
        )
        db.flush()
        result = view(db, user, day_date)
        db.add(
            MutationReceipt(
                user_id=user.id,
                id=data.client_mutation_id,
                payload_hash=digest,
                result_json=result.model_dump(mode="json", by_alias=True),
            )
        )
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
