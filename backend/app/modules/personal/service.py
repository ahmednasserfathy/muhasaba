from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import delete, func, select

from app.modules.journal import service as journal
from app.modules.journal.models import ActivityState, AdhkarCount
from app.modules.personal.models import CustomItem, GroupPlan
from app.modules.personal.schemas import PlanView


def definition(db, user, code, day_date):
    row = db.scalar(
        select(GroupPlan)
        .where(
            GroupPlan.user_id == user.id,
            GroupPlan.activity_code == code,
            GroupPlan.effective_from <= day_date,
        )
        .order_by(GroupPlan.effective_from.desc())
        .limit(1)
    )
    return (
        row.definition
        if row
        else dict(hiddenDefaultCodes=[], officialOrder=[], customItems=[], rowVersion=0)
    )


def for_day(db, user, day_date, day, release):
    if day is not None:
        return day.group_plans or {}
    return {
        a.code: definition(db, user, a.code, day_date)
        for a in release.activities
        if a.kind == "ADHKAR_SET"
    }


def group(db, user, code, day_date):
    day, release = journal.resolve(db, user, day_date)
    activity = next(
        (
            a
            for a in release.activities
            if a.code == code and a.kind == "ADHKAR_SET" and a.is_active
        ),
        None,
    )
    if activity is None:
        raise HTTPException(404, "Unknown adhkar group")
    return day, release, activity


def view(db, user, code, day_date):
    _, release, activity = group(db, user, code, day_date)
    plan = definition(db, user, code, day_date)
    version = (
        db.scalar(
            select(func.max(GroupPlan.row_version)).where(
                GroupPlan.user_id == user.id, GroupPlan.activity_code == code
            )
        )
        or 0
    )
    codes = {item.code for item in activity.items}
    return PlanView(
        activity_code=code,
        date=day_date,
        catalog_release=release.code,
        row_version=version,
        effective_from=plan.get("effectiveFrom"),
        hidden_default_codes=[c for c in plan["hiddenDefaultCodes"] if c in codes],
        official_order=[c for c in plan["officialOrder"] if c in codes],
        custom_items=plan["customItems"],
        official_items=[
            dict(code=i.code, textAr=i.text_ar, targetCount=i.target_count)
            for i in activity.items
        ],
    )


def apply(db, user, code, data):
    current = journal.today(user)
    if data.effective_from not in (current, current + timedelta(days=1)):
        raise HTTPException(422, "Choose today or tomorrow")
    day, release, activity = group(db, user, code, data.effective_from)
    if release.code != data.catalog_release:
        journal.conflict("CATALOG_CHANGED")
    version = (
        db.scalar(
            select(func.max(GroupPlan.row_version)).where(
                GroupPlan.user_id == user.id, GroupPlan.activity_code == code
            )
        )
        or 0
    )
    if version != data.expected_version:
        journal.conflict("CONFLICT")
    if day:
        progress = db.scalar(
            select(AdhkarCount.id)
            .where(
                AdhkarCount.journal_day_id == day.id,
                AdhkarCount.activity_id == activity.id,
                AdhkarCount.row_version > 0,
            )
            .limit(1)
        )
        state = db.scalar(
            select(ActivityState.id).where(
                ActivityState.journal_day_id == day.id,
                ActivityState.activity_id == activity.id,
            )
        )
        if progress or state:
            journal.conflict("GROUP_ALREADY_EDITED")
    codes = {i.code for i in activity.items}
    if (
        not set(data.hidden_default_codes) <= codes
        or not set(data.official_order) <= codes
    ):
        raise HTTPException(422, "Unknown official item")
    # Fixed group ownership keeps offline IDs unambiguous and edits atomic.
    existing = list(
        db.scalars(
            select(CustomItem).where(
                CustomItem.user_id == user.id, CustomItem.activity_code == code
            )
        )
    )
    selected = {item.id for item in data.custom_items}
    for item in data.custom_items:
        row = db.get(CustomItem, item.id)
        if row and (row.user_id != user.id or row.activity_code != code):
            raise HTTPException(404, "Unknown personal item")
        if row is None:
            row = CustomItem(id=item.id, user_id=user.id, activity_code=code)
            db.add(row)
        row.type, row.text_ar, row.target_count = (
            item.type,
            item.text_ar,
            item.target_count,
        )
        row.archived_at = None
    for row in existing:
        if row.id not in selected:
            row.archived_at = datetime.now(UTC)
    snapshot = dict(
        hiddenDefaultCodes=data.hidden_default_codes,
        officialOrder=data.official_order,
        customItems=[
            i.model_dump(mode="json", by_alias=True) for i in data.custom_items
        ],
        rowVersion=version + 1,
        effectiveFrom=str(data.effective_from),
    )
    row = db.scalar(
        select(GroupPlan).where(
            GroupPlan.user_id == user.id,
            GroupPlan.activity_code == code,
            GroupPlan.effective_from == data.effective_from,
        )
    )
    if row is None:
        row = GroupPlan(
            user_id=user.id, activity_code=code, effective_from=data.effective_from
        )
        db.add(row)
    row.row_version, row.definition = version + 1, snapshot
    # Do not reorder revisions: a new today revision would otherwise shadow a
    # preexisting tomorrow revision while its content silently reverts tomorrow.
    if data.effective_from == current:
        future = db.scalar(
            select(GroupPlan.id).where(
                GroupPlan.user_id == user.id,
                GroupPlan.activity_code == code,
                GroupPlan.effective_from > current,
            )
        )
        if future:
            journal.conflict("FUTURE_PLAN_EXISTS")
    db.flush()
    if day:
        day.group_plans = {**(day.group_plans or {}), code: snapshot}
        db.execute(
            delete(AdhkarCount).where(
                AdhkarCount.journal_day_id == day.id,
                AdhkarCount.activity_id == activity.id,
                AdhkarCount.source_type == "PERSONAL",
            )
        )
        snapshot_counts(db, day, activity, snapshot)
    db.flush()
    return view(db, user, code, data.effective_from).model_dump(
        mode="json", by_alias=True
    )


def snapshot_counts(db, day, activity, plan):
    from uuid import UUID

    for index, item in enumerate(plan.get("customItems", [])):
        db.add(
            AdhkarCount(
                journal_day_id=day.id,
                activity_id=activity.id,
                custom_item_id=UUID(item["id"]),
                item_code_snapshot=item["id"],
                text_ar_snapshot=item["textAr"],
                target_count_snapshot=item["targetCount"],
                source_type="PERSONAL",
                is_score_eligible_snapshot=False,
                sort_order=index,
            )
        )


def edit_item(db, user, data, key, operation):
    """Item CRUD changes the same dated group aggregate and concurrency version."""
    from app.modules.personal.schemas import PlanWrite

    row = db.get(CustomItem, key)
    if operation == "create":
        if row is not None:
            raise HTTPException(
                409 if row.user_id == user.id else 404, "Item unavailable"
            )
    elif (
        row is None or row.user_id != user.id or row.activity_code != data.activity_code
    ):
        raise HTTPException(404, "Unknown personal item")
    plan = view(db, user, data.activity_code, data.effective_from).model_dump(
        mode="json", by_alias=True
    )
    items = list(plan["customItems"])
    index = next((n for n, item in enumerate(items) if item["id"] == str(key)), None)
    if operation == "delete":
        if index is not None:
            items.pop(index)
    else:
        if data.item.id != key:
            raise HTTPException(422, "Item ID must match the route")
        item = data.item.model_dump(mode="json", by_alias=True)
        if index is None:
            items.append(item)
        else:
            items[index] = item
    if len(items) > 100:
        raise HTTPException(422, "Group supports at most 100 personal items")
    payload = PlanWrite(
        client_mutation_id=data.client_mutation_id,
        expected_version=data.expected_version,
        catalog_release=data.catalog_release,
        effective_from=data.effective_from,
        hidden_default_codes=plan["hiddenDefaultCodes"],
        official_order=plan["officialOrder"],
        custom_items=items,
    )
    return apply(db, user, data.activity_code, payload)
