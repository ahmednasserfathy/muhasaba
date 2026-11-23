from datetime import date, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from test_auth import header, register
from test_journal import DAY, card, send
from test_journal import journal as _journal_fixture

from app.modules.auth import router as auth
from app.modules.auth.security import RateLimiter
from app.modules.fasting.models import CalendarPeriod, FastingOverride
from app.modules.journal import service as journal_service
from app.modules.journal.models import JournalDay, MutationReceipt
from scripts.ramadan_calendar import configure

journal_fixture = _journal_fixture


def plan(client, day=DAY, mode="ADD", version=0, **extra):
    body = {
        "clientMutationId": str(uuid4()),
        "mode": mode,
        "expectedVersion": version,
        **extra,
    }
    return client.put(f"/api/v1/days/{day}/fasting-plan", json=body), body


def period(
    session, start=DAY - timedelta(days=1), end=DAY, status="CONFIRMED", region="EG"
):
    row = CalendarPeriod(
        region_key=region,
        start_date=start,
        end_date=end,
        confirmation_status=status,
        source_url="https://example.test/fixture",
    )
    session.add(row)
    session.commit()
    return row


def test_wednesday_add_skip_default_and_idempotency(client, session, journal_fixture):
    day = DAY - timedelta(days=1)
    assert client.get(f"/api/v1/days/{day}").json()["summary"]["possible"] == 4
    added, body = plan(client, day, fastType="MAKEUP")
    assert added.status_code == 200 and added.json()["eligible"] is True
    result = client.get(f"/api/v1/days/{day}")
    assert result.json()["summary"] == {"earned": 0, "possible": 9, "percent": 0}
    assert result.json()["fasting"]["fastType"] == "MAKEUP"
    assert session.scalar(select(func.count()).select_from(JournalDay)) == 0
    skipped, _ = plan(client, day, "SKIP", 1)
    assert skipped.json()["eligible"] is False
    assert client.get(f"/api/v1/days/{day}").json()["summary"]["possible"] == 4
    default, _ = plan(client, day, "DEFAULT", 2)
    assert default.json()["rowVersion"] == 3
    assert default.json()["reason"] == "UNPLANNED"
    replay = client.put(f"/api/v1/days/{day}/fasting-plan", json=body)
    assert replay.json() == added.json()
    assert session.scalar(select(FastingOverride)).row_version == 3
    assert session.scalar(select(func.count()).select_from(MutationReceipt)) == 3


def test_ramadan_overlap_is_one_weight_and_skip_preserves_completion(
    client, session, journal_fixture
):
    period(session)
    result = client.get(f"/api/v1/days/{DAY}")
    assert result.json()["fasting"]["reason"] == "RAMADAN"
    assert result.json()["summary"]["possible"] == 9  # not 14 on Thursday
    assert sum(c["kind"] == "FASTING" for c in result.json()["activities"]) == 1
    done, _ = send(
        client,
        journal_fixture[0],
        "activities/fast",
        state="COMPLETED",
        expectedVersion=0,
    )
    assert done.json()["summary"]["earned"] == 5
    plan(client, mode="SKIP")
    skipped = client.get(f"/api/v1/days/{DAY}")
    assert skipped.json()["summary"] == {"earned": 0, "possible": 4, "percent": 0}
    plan(client, mode="DEFAULT", version=1)
    restored = client.get(f"/api/v1/days/{DAY}")
    assert restored.json()["summary"]["earned"] == 5
    assert card(restored, "fast")["rowVersion"] == 1


def test_provisional_missing_and_other_region_do_not_enable_ramadan(
    client, session, journal_fixture
):
    day = DAY - timedelta(days=1)
    row = period(session, status="PROVISIONAL")
    result = client.get(f"/api/v1/days/{day}").json()
    assert result["fasting"]["calendarStatus"] == "PROVISIONAL"
    assert result["summary"]["possible"] == 4
    row.region_key, row.confirmation_status = "OTHER", "CONFIRMED"
    session.commit()
    result = client.get(f"/api/v1/days/{day}").json()
    assert result["fasting"]["calendarStatus"] == "UNAVAILABLE"
    assert result["summary"]["possible"] == 4


def test_future_plan_without_catalog_never_completes_or_creates_journal(
    client, session, monkeypatch
):
    monkeypatch.setattr(auth, "limiter", RateLimiter())
    monkeypatch.setattr(journal_service, "today", lambda user: DAY)
    client.headers.update(header(register(client, trackingStartDate="2026-11-01")))
    future = DAY + timedelta(days=10)
    result, _ = plan(client, future)
    assert result.status_code == 200 and result.json()["reason"] == "ADDED"
    assert session.scalar(select(func.count()).select_from(JournalDay)) == 0
    assert client.get(f"/api/v1/days/{future}").status_code == 422
    assert (
        client.put(
            f"/api/v1/days/{future}/activities/fast",
            json={
                "clientMutationId": str(uuid4()),
                "catalogRelease": "any",
                "expectedVersion": 0,
                "state": "COMPLETED",
            },
        ).status_code
        == 422
    )
    calendar = client.get(f"/api/v1/fasting/calendar?from={future}&to={future}")
    assert calendar.status_code == 200
    assert calendar.json()["days"][0]["mode"] == "ADD"
    assert calendar.headers["cache-control"] == "no-store"


def test_plan_conflict_key_reuse_and_account_isolation(client, journal_fixture):
    result, body = plan(client)
    assert result.status_code == 200
    assert plan(client, mode="SKIP")[0].status_code == 409
    body["mode"] = "SKIP"
    assert (
        client.put(f"/api/v1/days/{DAY}/fasting-plan", json=body).json()["detail"][
            "code"
        ]
        == "IDEMPOTENCY_KEY_REUSE"
    )
    client.headers.update(
        header(register(client, "other@example.com", trackingStartDate="2026-11-01"))
    )
    calendar = client.get(f"/api/v1/fasting/calendar?from={DAY}&to={DAY}")
    assert calendar.json()["days"][0]["rowVersion"] == 0
    assert client.put(f"/api/v1/days/{DAY}/fasting-plan", json=body).status_code == 200
    client.headers.pop("Authorization")
    assert (
        client.get(f"/api/v1/fasting/calendar?from={DAY}&to={DAY}").status_code == 401
    )


def test_calendar_boundaries_and_range_validation(client, session, journal_fixture):
    period(session)
    result = client.get("/api/v1/fasting/calendar?from=2026-11-17&to=2026-11-20").json()
    assert [d["reason"] for d in result["days"]] == [
        "UNPLANNED",
        "RAMADAN",
        "RAMADAN",
        "UNPLANNED",
    ]
    for query in [
        "from=2026-11-20&to=2026-11-19",
        "from=2026-10-31&to=2026-11-19",
        "from=2026-11-19&to=2027-11-20",
    ]:
        assert client.get("/api/v1/fasting/calendar?" + query).status_code == 422
    assert plan(client, date(2026, 10, 31))[0].status_code == 422


def test_saved_day_baseline_survives_calendar_correction(
    client, session, journal_fixture
):
    row = period(session)
    send(client, journal_fixture[0], state="COMPLETED", expectedVersion=0)
    original = client.get(f"/api/v1/days/{DAY}").json()
    assert original["fasting"]["pinned"] is True
    row.confirmation_status = "PROVISIONAL"
    session.commit()
    assert client.get(f"/api/v1/days/{DAY}").json() == original
    assert (
        client.get("/api/v1/days/2026-11-18").json()["fasting"]["reason"] == "UNPLANNED"
    )


def test_operator_configuration_is_sourced_and_rejects_overlap(session):
    row = configure(
        session, "EG", date(2026, 2, 1), date(2026, 2, 28), "PROVISIONAL", None
    )
    assert row.confirmation_status == "PROVISIONAL"
    configure(
        session,
        "EG",
        date(2026, 2, 1),
        date(2026, 2, 28),
        "CONFIRMED",
        "https://example.test/reviewed-test-source",
    )
    assert row.confirmation_status == "CONFIRMED"
    with pytest.raises(ValueError, match="overlaps"):
        configure(
            session, "EG", date(2026, 2, 20), date(2026, 3, 10), "PROVISIONAL", None
        )


def test_upgrade_preserves_pr03_weekly_baseline(migrated_engine):
    from conftest import migration_config
    from sqlalchemy import text

    from alembic import command

    # PostgreSQL DDL and test rows roll back together, preserving the shared schema.
    with migrated_engine.connect() as connection:
        transaction = connection.begin()
        try:
            config = migration_config(connection)
            command.downgrade(config, "0004")
            user_id, day_id = uuid4(), uuid4()
            connection.execute(
                text(
                    "INSERT INTO users (id,registration_source,tracking_start_date) "
                    "VALUES (:id,'IMPORTED','2026-11-01')"
                ),
                {"id": user_id},
            )
            connection.execute(
                text(
                    "INSERT INTO journal_days "
                    "(id,user_id,local_date,catalog_release_id,timezone_at_creation) "
                    "SELECT :id,:user,'2026-11-19',id,'Africa/Cairo' "
                    "FROM catalog_releases WHERE code='2026-11-19-reference'"
                ),
                {"id": day_id, "user": user_id},
            )
            command.upgrade(config, "head")
            baseline = connection.scalar(
                text("SELECT fasting_baseline FROM journal_days WHERE id=:id"),
                {"id": day_id},
            )
            assert baseline == {
                "regionKey": "EG",
                "baseReason": "WEEKLY",
                "calendarStatus": "UNAVAILABLE",
                "sourceUrl": None,
            }
        finally:
            transaction.rollback()
