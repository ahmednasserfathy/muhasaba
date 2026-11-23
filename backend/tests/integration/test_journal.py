from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session
from test_auth import header, register
from test_catalog import draft, publish

from app.modules.auth import router as auth
from app.modules.auth.models import User
from app.modules.auth.security import RateLimiter
from app.modules.catalog.models import Activity, AdhkarItem
from app.modules.journal import service
from app.modules.journal.models import (
    AdhkarCount,
    JournalDay,
    MutationReceipt,
)
from app.modules.journal.schemas import StateWrite

DAY = date(2026, 11, 19)  # Thursday, fixed account-local test date.


@pytest.fixture
def journal(client, session, monkeypatch):
    monkeypatch.setattr(auth, "limiter", RateLimiter())
    monkeypatch.setattr(service, "today", lambda user: DAY)
    release, group, item, library = draft(session, DAY - timedelta(days=5))
    item.target_count = 1
    session.add(
        AdhkarItem(
            activity_id=group.id,
            code="second",
            text_ar="اختبار فقط",
            sort_order=2,
            target_count=1,
            review_status="VERIFIED",
            source_name="Test",
            source_url="https://example.test",
            license_notes="Synthetic",
        )
    )
    session.add(
        Activity(
            catalog_release_id=release.id,
            category_id=group.category_id,
            code="dhuhr",
            title_ar="اختبار الظهر",
            sort_order=2,
            points=2,
            kind="TOGGLE",
        )
    )
    session.add(
        Activity(
            catalog_release_id=release.id,
            category_id=group.category_id,
            code="fast",
            title_ar="اختبار صيام",
            sort_order=3,
            points=5,
            kind="FASTING",
            schedule_kind="FASTING_DYNAMIC",
        )
    )
    session.flush()
    publish(session, release)
    session.commit()
    tokens = register(client, trackingStartDate="2026-11-01")
    client.headers.update(header(tokens))
    return release, tokens, library


def send(client, release, route="activities/dhuhr", **payload):
    body = {"catalogRelease": release.code, "clientMutationId": str(uuid4()), **payload}
    return client.put(f"/api/v1/days/{DAY}/{route}", json=body), body


def card(response, code):
    return next(a for a in response.json()["activities"] if a["code"] == code)


def test_get_does_not_create_day_and_toggle_undo_retry(client, session, journal):
    release, _, _ = journal
    initial = client.get(f"/api/v1/days/{DAY}")
    assert initial.status_code == 200
    assert initial.headers["cache-control"] == "no-store"
    assert initial.json()["summary"] == {"earned": 0, "possible": 9, "percent": 0}
    assert session.scalar(select(func.count()).select_from(JournalDay)) == 0
    first, body = send(client, release, state="COMPLETED", expectedVersion=0)
    assert first.status_code == 200
    assert first.json()["summary"]["earned"] == 2
    assert card(first, "dhuhr")["rowVersion"] == 1
    undo, _ = send(client, release, state="PENDING", expectedVersion=1)
    assert undo.json()["summary"]["earned"] == 0
    retry = client.put(f"/api/v1/days/{DAY}/activities/dhuhr", json=body)
    assert retry.json() == first.json()  # Original receipt, not a second write.
    assert card(client.get(f"/api/v1/days/{DAY}"), "dhuhr")["rowVersion"] == 2
    assert session.scalar(select(func.count()).select_from(AdhkarCount)) == 2
    assert session.scalar(select(func.count()).select_from(MutationReceipt)) == 2


def test_partial_counters_bulk_atomic_and_exclusion(client, journal):
    release, _, _ = journal
    response, _ = send(
        client,
        release,
        "adhkar/official:test_set:test_item",
        completedCount=1,
        expectedVersion=0,
    )
    assert card(response, "test_set")["earnedPoints"] == 1
    assert card(response, "test_set")["status"] == "PARTIAL"
    stale, _ = send(
        client,
        release,
        "adhkar-sets/test_set",
        action="COMPLETE_ALL",
        expectedVersions={"test_item": 0, "second": 0},
    )
    assert stale.status_code == 409
    assert (
        card(client.get(f"/api/v1/days/{DAY}"), "test_set")["items"][1][
            "completedCount"
        ]
        == 0
    )
    full, _ = send(
        client,
        release,
        "adhkar-sets/test_set",
        action="COMPLETE_ALL",
        expectedVersions={"test_item": 1, "second": 0},
    )
    assert card(full, "test_set")["earnedPoints"] == 2
    assert card(full, "test_set")["status"] == "COMPLETED"
    excluded, _ = send(
        client, release, "activities/test_set", state="EXCLUDED", expectedVersion=0
    )
    assert excluded.json()["summary"]["possible"] == 7
    restored, _ = send(
        client, release, "activities/test_set", state="PENDING", expectedVersion=1
    )
    assert card(restored, "test_set")["earnedPoints"] == 2
    undo, _ = send(
        client,
        release,
        "adhkar/official:test_set:test_item",
        completedCount=0,
        expectedVersion=2,
    )
    assert card(undo, "test_set")["earnedPoints"] == 1
    cleared, _ = send(
        client,
        release,
        "adhkar-sets/test_set",
        action="CLEAR_ALL",
        expectedVersions={"test_item": 3, "second": 1},
    )
    assert card(cleared, "test_set")["earnedPoints"] == 0


def test_conflicts_payload_reuse_and_release_change(client, journal):
    release, _, _ = journal
    good, body = send(client, release, state="COMPLETED", expectedVersion=0)
    assert good.status_code == 200
    stale, _ = send(client, release, state="PENDING", expectedVersion=0)
    assert stale.status_code == 409
    body["state"] = "PENDING"
    reused = client.put(f"/api/v1/days/{DAY}/activities/dhuhr", json=body)
    assert reused.json()["detail"]["code"] == "IDEMPOTENCY_KEY_REUSE"
    mismatch, _ = send(
        client, release, state="PENDING", expectedVersion=1, catalogRelease="other"
    )
    assert mismatch.json()["detail"]["code"] == "CATALOG_CHANGED"
    assert card(client.get(f"/api/v1/days/{DAY}"), "dhuhr")["state"] == "COMPLETED"


@pytest.mark.parametrize(
    "route,payload,status",
    [
        ("activities/test_set", {"state": "COMPLETED", "expectedVersion": 0}, 422),
        ("activities/missing", {"state": "COMPLETED", "expectedVersion": 0}, 404),
        (
            "adhkar/official:test_set:test_item",
            {"completedCount": 2, "expectedVersion": 0},
            422,
        ),
        (
            "adhkar/official:test_set:missing",
            {"completedCount": 1, "expectedVersion": 0},
            404,
        ),
        ("adhkar/personal:unknown", {"completedCount": 1, "expectedVersion": 0}, 404),
        (
            "adhkar/official:dhuhr:test_item",
            {"completedCount": 1, "expectedVersion": 0},
            422,
        ),
        (
            "adhkar/official:test_set:test_item",
            {"completedCount": -1, "expectedVersion": 0},
            422,
        ),
        (
            "adhkar/official:test_set:test_item",
            {"completedCount": True, "expectedVersion": 0},
            422,
        ),
    ],
)
def test_invalid_writes_leave_no_day(client, session, journal, route, payload, status):
    result, _ = send(client, journal[0], route, **payload)
    assert result.status_code == status
    assert session.scalar(select(func.count()).select_from(JournalDay)) == 0
    assert session.scalar(select(func.count()).select_from(MutationReceipt)) == 0


def test_history_pins_release_and_item_snapshot(client, session, journal):
    release, _, library = journal
    send(
        client,
        release,
        "adhkar/official:test_set:test_item",
        completedCount=1,
        expectedVersion=0,
    )
    original = client.get(f"/api/v1/days/{DAY}").json()
    library.text_ar = "تغيير اختبار"
    library.status = "ARCHIVED"
    newer, _, _, _ = draft(session, DAY - timedelta(days=1), points=10)
    publish(session, newer)
    session.commit()
    assert client.get(f"/api/v1/days/{DAY}").json() == original


def test_date_window_and_weekly_fasting(client, journal):
    release, _, _ = journal
    for day in ["2026-10-31", "2026-11-20"]:
        assert client.get(f"/api/v1/days/{day}").status_code == 422
        assert (
            client.put(
                f"/api/v1/days/{day}/activities/dhuhr",
                json={
                    "catalogRelease": release.code,
                    "clientMutationId": str(uuid4()),
                    "state": "COMPLETED",
                    "expectedVersion": 0,
                },
            ).status_code
            == 422
        )
    assert client.get("/api/v1/days/today").json()["date"] == str(DAY)
    assert client.get("/api/v1/days/2026-11-18").json()["summary"]["possible"] == 4
    assert (
        client.put(
            "/api/v1/days/2026-11-18/activities/fast",
            json={
                "catalogRelease": release.code,
                "clientMutationId": str(uuid4()),
                "state": "COMPLETED",
                "expectedVersion": 0,
            },
        ).status_code
        == 422
    )


def test_cross_user_isolation_and_mutation_ids(client, journal):
    release, _, _ = journal
    _, body = send(client, release, state="COMPLETED", expectedVersion=0)
    other = register(client, "second@example.com", trackingStartDate="2026-11-01")
    client.headers.update(header(other))
    assert client.get(f"/api/v1/days/{DAY}").json()["summary"]["earned"] == 0
    body["state"] = "PENDING"
    result = client.put(f"/api/v1/days/{DAY}/activities/dhuhr", json=body)
    assert result.status_code == 200  # Same UUID is scoped to its authenticated owner.
    client.headers.pop("Authorization")
    assert client.get(f"/api/v1/days/{DAY}").status_code == 401


def test_concurrent_first_writes_and_duplicate_receipts(migrated_engine, monkeypatch):
    from conftest import migration_config

    from alembic import command

    monkeypatch.setattr(service, "today", lambda user: DAY)
    # Independent schema: published fixtures cannot be deleted by seed downgrade.
    # migrated_engine already enforces a disposable PostgreSQL *_test database.
    schema = "journal_concurrency_" + uuid4().hex
    with migrated_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(
        migrated_engine.url, connect_args={"options": f"-csearch_path={schema}"}
    )
    try:
        with engine.begin() as connection:
            command.upgrade(migration_config(connection), "head")
        with Session(engine) as db:
            release, _, _, _ = draft(db, DAY - timedelta(days=10))
            publish(db, release)
            release_code = release.code
            user = User(registration_source="IMPORTED", tracking_start_date=DAY)
            db.add(user)
            db.commit()
            user_id = user.id
        data = StateWrite(
            clientMutationId=uuid4(),
            catalogRelease=release_code,
            state="EXCLUDED",
            expectedVersion=0,
        )

        def apply(payload):
            with Session(engine) as db:
                try:
                    result = service.write(
                        db, db.get(User, user_id), DAY, "state", "test_set", payload
                    )
                    return result.model_dump(mode="json")
                except HTTPException as exc:
                    return exc.status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(apply, [data, data]))
        assert results[0] == results[1] and isinstance(results[0], dict)
        with Session(engine) as db:
            assert db.scalar(select(func.count()).select_from(JournalDay)) == 1
            assert db.scalar(select(func.count()).select_from(MutationReceipt)) == 1
    finally:
        engine.dispose()
        with migrated_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))


def test_full_reference_day_has_34_cards_and_exact_74_69_denominators(
    client, session, monkeypatch
):
    from scripts.journal_demo import create_demo

    monkeypatch.setattr(auth, "limiter", RateLimiter())
    monkeypatch.setattr(service, "today", lambda user: DAY)
    create_demo(session, date(2026, 11, 16))
    session.commit()
    tokens = register(client, trackingStartDate="2026-11-01")
    client.headers.update(header(tokens))
    thursday = client.get(f"/api/v1/days/{DAY}").json()
    assert len(thursday["activities"]) == 34
    assert thursday["summary"]["possible"] == 74
    assert client.get("/api/v1/days/2026-11-18").json()["summary"]["possible"] == 69
    first = next(c for c in thursday["activities"] if c["kind"] == "ADHKAR_SET")
    body = {
        "catalogRelease": thursday["catalogRelease"],
        "clientMutationId": str(uuid4()),
        "completedCount": 1,
        "expectedVersion": 0,
    }
    result = client.put(
        f"/api/v1/days/{DAY}/adhkar/{first['items'][0]['itemKey']}", json=body
    )
    assert result.status_code == 200
    assert card(result, first["code"])["earnedPoints"] == first["weight"] / 2
    assert session.scalar(select(func.count()).select_from(AdhkarCount)) == 34
