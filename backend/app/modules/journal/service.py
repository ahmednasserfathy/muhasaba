import hashlib
import json
from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.modules.auth.models import User
from app.modules.catalog.models import Activity, CatalogRelease
from app.modules.catalog.scoring import (
    ItemProgress,
    display_percent,
    score_card,
    score_day,
)
from app.modules.fasting import service as fasting_service
from app.modules.journal.models import (
    ActivityState,
    AdhkarCount,
    JournalDay,
    MutationReceipt,
)
from app.modules.journal.schemas import CardView, DayView, ItemView, Summary
from app.modules.personal import service as personal_service


def today(user):
    return datetime.now(ZoneInfo(user.timezone)).date()


def validate_date(user, day_date):
    if not user.tracking_start_date <= day_date <= today(user):
        raise HTTPException(422, "Date must be within the account tracking history")


def resolve(db, user, day_date):
    day = db.scalar(
        select(JournalDay).where(
            JournalDay.user_id == user.id, JournalDay.local_date == day_date
        )
    )
    query = select(CatalogRelease).where(CatalogRelease.status == "PUBLISHED")
    if day:
        query = query.where(CatalogRelease.id == day.catalog_release_id)
    else:
        query = (
            query.where(CatalogRelease.effective_from <= day_date)
            .order_by(CatalogRelease.effective_from.desc())
            .limit(1)
        )
    release = db.scalar(
        query.options(
            selectinload(CatalogRelease.activities).selectinload(Activity.items),
            selectinload(CatalogRelease.activities).selectinload(Activity.category),
        )
    )
    if release is None:
        raise HTTPException(404, "No published catalog for this date")
    return day, release


def day_view(db, user, day_date):
    return day_view_with_score(db, user, day_date)[0]


def day_view_with_score(db, user, day_date):
    day, release = resolve(db, user, day_date)
    states = (
        {}
        if day is None
        else {
            s.activity_id: s
            for s in db.scalars(
                select(ActivityState).where(ActivityState.journal_day_id == day.id)
            )
        }
    )
    counts = (
        {}
        if day is None
        else {
            (c.source_type, c.adhkar_item_id or c.custom_item_id): c
            for c in db.scalars(
                select(AdhkarCount).where(AdhkarCount.journal_day_id == day.id)
            )
        }
    )
    fasting = fasting_service.view(db, user, day_date, day)
    plans = personal_service.for_day(db, user, day_date, day, release)
    cards, scores = [], []
    for a in sorted(
        release.activities, key=lambda a: (a.category.sort_order, a.sort_order)
    ):
        if not a.is_active:
            continue
        state = states.get(a.id)
        plan = plans.get(a.code, {})
        order = plan.get("officialOrder", [])
        items = []
        for i in a.items:
            c = counts.get(("OFFICIAL", i.id))
            items.append(
                ItemView(
                    item_key=f"official:{a.code}:{i.code}",
                    code=i.code,
                    hidden=i.code in plan.get("hiddenDefaultCodes", []),
                    sort_order=order.index(i.code)
                    if i.code in order
                    else len(order) + i.sort_order,
                    text_ar=c.text_ar_snapshot if c else i.text_ar,
                    target_count=c.target_count_snapshot if c else i.target_count,
                    completed_count=c.completed_count if c else 0,
                    row_version=c.row_version if c else 0,
                    is_score_eligible=c.is_score_eligible_snapshot
                    if c
                    else i.is_score_eligible,
                    source_name=i.source_name,
                    source_url=i.source_url,
                    license_notes=i.license_notes,
                )
            )
        for index, custom in enumerate(plan.get("customItems", [])):
            c = counts.get(("PERSONAL", UUID(custom["id"])))
            items.append(
                ItemView(
                    item_key=f"personal:{custom['id']}",
                    code=custom["id"],
                    text_ar=c.text_ar_snapshot if c else custom["textAr"],
                    target_count=c.target_count_snapshot
                    if c
                    else custom["targetCount"],
                    completed_count=c.completed_count if c else 0,
                    row_version=c.row_version if c else 0,
                    source_type="PERSONAL",
                    is_score_eligible=False,
                    sort_order=10000 + index,
                )
            )
        items.sort(key=lambda i: i.sort_order)
        eligible = (a.kind != "FASTING" or fasting.eligible) and (
            state is None or state.state != "EXCLUDED"
        )
        score = score_card(
            a.points,
            a.kind,
            eligible=eligible,
            completed=state is not None and state.state == "COMPLETED",
            items=tuple(
                ItemProgress(
                    i.code,
                    i.target_count,
                    i.completed_count,
                    is_score_eligible=i.is_score_eligible,
                    source_type=i.source_type,
                )
                for i in items
            ),
        )
        scores.append(score)
        official = [i for i in items if i.is_score_eligible]
        cards.append(
            CardView(
                plan_version=plan.get("rowVersion", 0),
                hidden_official_incomplete=sum(
                    i.hidden
                    and i.is_score_eligible
                    and i.completed_count < i.target_count
                    for i in items
                ),
                personal_total=sum(i.source_type == "PERSONAL" for i in items),
                personal_completed=sum(
                    i.source_type == "PERSONAL" and i.completed_count == i.target_count
                    for i in items
                ),
                code=a.code,
                category_code=a.category.code,
                category_title_ar=a.category.title_ar,
                title_ar=a.title_ar,
                kind=a.kind,
                weight=a.points,
                state=state.state if state else "PENDING",
                status=score.status,
                row_version=state.row_version if state else 0,
                eligible=eligible,
                earned_points=float(score.earned),
                possible_points=int(score.possible),
                official_completed=sum(
                    i.completed_count == i.target_count for i in official
                ),
                official_total=len(official),
                items=items,
            )
        )
    summary = score_day(tuple(scores))
    view = DayView(
        date=day_date,
        today=today(user),
        tracking_start_date=user.tracking_start_date,
        timezone=user.timezone,
        catalog_release=release.code,
        fasting=fasting.model_dump(mode="json", by_alias=True),
        activities=cards,
        summary=Summary(
            earned=float(summary.earned),
            possible=int(summary.possible),
            percent=display_percent(summary.percent),
        ),
    )

    return view, summary


def conflict(code, canonical=None):
    raise HTTPException(
        409,
        {
            "code": code,
            "messageAr": "تغيّرت البيانات. راجع النسخة المحفوظة قبل المتابعة.",
            "canonical": canonical,
        },
    )


def write(db, user, day_date, kind, key, data):
    try:
        return _write(db, user, day_date, kind, key, data)
    except Exception:
        db.rollback()
        raise


def _write(db, user, day_date, kind, key, data):
    # One lock per account serializes first-day creation, receipts and all bulk rows.
    # No process-local lock: separate workers/connections share PostgreSQL ordering.
    db.scalar(select(User).where(User.id == user.id).with_for_update())
    body = data.model_dump(mode="json")
    # Keep official counter receipt hashes compatible with pre-personal clients.
    if (
        kind == "count"
        and key.startswith("official:")
        and data.expected_plan_version == 0
    ):
        body.pop("expected_plan_version", None)
    payload = json.dumps(
        [str(day_date), kind, key, body],
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(payload.encode()).hexdigest()
    receipt = db.get(MutationReceipt, (user.id, data.client_mutation_id))
    if receipt:
        if receipt.payload_hash != digest:
            conflict("IDEMPOTENCY_KEY_REUSE")
        result = DayView.model_validate(receipt.result_json)
        db.commit()
        return result
    validate_date(user, day_date)
    day, release = resolve(db, user, day_date)
    if release.code != data.catalog_release:
        conflict(
            "CATALOG_CHANGED",
            day_view(db, user, day_date).model_dump(mode="json", by_alias=True),
        )
    activity_code = key
    item_code = None
    custom_id = None
    if kind == "count":
        parts = key.split(":")
        if len(parts) == 2 and parts[0] == "personal":
            plans = personal_service.for_day(db, user, day_date, day, release)
            activity_code = next(
                (
                    code
                    for code, plan in plans.items()
                    if any(i["id"] == parts[1] for i in plan.get("customItems", []))
                ),
                None,
            )
            if activity_code is None:
                raise HTTPException(404, "Unknown personal item")
            if data.expected_plan_version != plans[activity_code].get("rowVersion", 0):
                conflict("PLAN_CHANGED")
            custom_id = item_code = parts[1]
        elif len(parts) == 3 and parts[0] == "official":
            _, activity_code, item_code = parts
        else:
            raise HTTPException(404, "Unknown item")
    activity = next(
        (a for a in release.activities if a.code == activity_code and a.is_active), None
    )
    if activity is None:
        raise HTTPException(404, "Unknown activity")
    if kind == "state":
        if activity.kind == "ADHKAR_SET" and data.state == "COMPLETED":
            raise HTTPException(422, "Set completion is derived from counters")
        if (
            activity.kind == "FASTING"
            and not fasting_service.view(db, user, day_date, day).eligible
            and data.state == "COMPLETED"
        ):
            raise HTTPException(422, "Fasting is not planned for this date")
    elif activity.kind != "ADHKAR_SET":
        raise HTTPException(422, "Only adhkar sets have counters")
    if (
        kind == "count"
        and not custom_id
        and not any(i.code == item_code for i in activity.items)
    ):
        raise HTTPException(404, "Unknown item in this activity")
    # First successful edit pins the entire official day, including zero counters.
    if day is None:
        day = JournalDay(
            user_id=user.id,
            local_date=day_date,
            catalog_release_id=release.id,
            timezone_at_creation=user.timezone,
            fasting_baseline=fasting_service.baseline(db, user, day_date),
            group_plans=personal_service.for_day(db, user, day_date, None, release),
        )
        db.add(day)
        db.flush()
        for a in release.activities:
            if a.is_active:
                personal_service.snapshot_counts(
                    db, day, a, (day.group_plans or {}).get(a.code, {})
                )
                for i in a.items:
                    db.add(
                        AdhkarCount(
                            journal_day_id=day.id,
                            activity_id=a.id,
                            adhkar_item_id=i.id,
                            item_code_snapshot=i.code,
                            text_ar_snapshot=i.text_ar,
                            target_count_snapshot=i.target_count,
                            is_score_eligible_snapshot=i.is_score_eligible,
                            sort_order=i.sort_order,
                        )
                    )
        db.flush()
    if kind == "state":
        row = db.scalar(
            select(ActivityState).where(
                ActivityState.journal_day_id == day.id,
                ActivityState.activity_id == activity.id,
            )
        )
        version = row.row_version if row else 0
        if data.expected_version != version:
            conflict(
                "CONFLICT",
                {"state": row.state if row else "PENDING", "rowVersion": version},
            )
        if row is None:
            row = ActivityState(journal_day_id=day.id, activity_id=activity.id)
            db.add(row)
        row.state, row.row_version = data.state, version + 1
    else:
        rows = list(
            db.scalars(
                select(AdhkarCount).where(
                    AdhkarCount.journal_day_id == day.id,
                    AdhkarCount.activity_id == activity.id,
                )
            )
        )
        if kind == "count":
            row = next(
                c
                for c in rows
                if c.item_code_snapshot == item_code
                and c.source_type == ("PERSONAL" if custom_id else "OFFICIAL")
            )
            if data.completed_count > row.target_count_snapshot:
                raise HTTPException(422, "Count exceeds target")
            if data.expected_version != row.row_version:
                conflict(
                    "CONFLICT",
                    {
                        "completedCount": row.completed_count,
                        "rowVersion": row.row_version,
                    },
                )
            row.completed_count, row.row_version = (
                data.completed_count,
                row.row_version + 1,
            )
        else:
            rows = [c for c in rows if c.source_type == "OFFICIAL"]
            expected = {c.item_code_snapshot: c.row_version for c in rows}
            if data.expected_versions != expected:
                conflict("CONFLICT", expected)
            for row in rows:
                row.completed_count = (
                    row.target_count_snapshot if data.action == "COMPLETE_ALL" else 0
                )
                row.row_version += 1
    day.updated_at = datetime.now(ZoneInfo("UTC"))
    db.flush()
    result = day_view(db, user, day_date)
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
