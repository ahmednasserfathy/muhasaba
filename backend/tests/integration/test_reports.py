from datetime import timedelta

from sqlalchemy import func, select
from test_auth import header, register
from test_journal import DAY, send
from test_journal import journal as _journal_fixture

from app.modules.journal.models import JournalDay

journal_fixture = _journal_fixture


def test_weighted_period_and_read_only_restore(client, session, journal_fixture):
    send(client, journal_fixture[0], state="COMPLETED", expectedVersion=0)
    url = "?from=2026-11-18&to=2026-11-19"
    report = client.get("/api/v1/reports/summary" + url)
    assert report.status_code == 200
    assert report.headers["cache-control"] == "no-store"
    assert report.json()["summary"] == {"earned": 2, "possible": 13, "percent": 15}
    assert report.json()["days"][0]["summary"]["earned"] == 0
    assert report.json()["days"][1]["fasting"]["eligible"] is True
    restored = client.get("/api/v1/days" + url)
    assert restored.status_code == 200
    assert restored.json()["days"][1] == client.get(f"/api/v1/days/{DAY}").json()
    assert session.scalar(select(func.count()).select_from(JournalDay)) == 1


def test_unavailable_catalog_is_explicit_not_zero_success(client, journal_fixture):
    result = client.get("/api/v1/reports/summary?from=2026-11-01&to=2026-11-19").json()
    assert len(result["unavailableDates"]) == 13
    assert len(result["days"]) == 6
    assert result["summary"]["possible"] > 0


def test_window_bounds_empty_period_and_auth(client, journal_fixture):
    for route in ["days", "reports/summary"]:
        for query in ["from=2026-11-19&to=2026-11-18", "from=2026-10-01&to=2026-11-01"]:
            assert client.get(f"/api/v1/{route}?{query}").status_code == 422
        result = client.get(f"/api/v1/{route}?from=2026-11-20&to=2026-11-30").json()
        assert result["days"] == [] and result["unavailableDates"] == []
        result = client.get(f"/api/v1/{route}?from=2026-10-25&to=2026-11-02").json()
        assert result["unavailableDates"] == ["2026-11-01", "2026-11-02"]
    client.headers.pop("Authorization")
    assert client.get("/api/v1/days?from=2026-11-18&to=2026-11-19").status_code == 401
    assert (
        client.get("/api/v1/reports/summary?from=2026-11-18&to=2026-11-19").status_code
        == 401
    )


def test_reports_isolate_accounts_and_keep_zero_denominator(client, journal_fixture):
    for code in ["dhuhr", "test_set", "fast"]:
        send(
            client,
            journal_fixture[0],
            f"activities/{code}",
            state="EXCLUDED",
            expectedVersion=0,
        )
    url = f"/api/v1/reports/summary?from={DAY}&to={DAY}"
    assert client.get(url).json()["summary"] == {
        "earned": 0,
        "possible": 0,
        "percent": None,
    }
    client.headers.update(
        header(register(client, "report@example.com", trackingStartDate=str(DAY)))
    )
    assert client.get(url).json()["summary"]["possible"] == 9


def test_today_and_tracking_start_clip_month(client, journal_fixture):
    client.headers.update(
        header(register(client, "new@example.com", trackingStartDate=str(DAY)))
    )
    result = client.get("/api/v1/reports/summary?from=2026-11-01&to=2026-11-30").json()
    assert [d["date"] for d in result["days"]] == [str(DAY)]
    assert result["unavailableDates"] == []


def test_fractional_report_matches_day_and_preserves_release(
    client, session, journal_fixture
):
    from test_catalog import draft, publish

    send(
        client,
        journal_fixture[0],
        "adhkar/official:test_set:test_item",
        completedCount=1,
        expectedVersion=0,
    )
    expected = client.get(f"/api/v1/days/{DAY}").json()["summary"]
    release, _, _, _ = draft(session, DAY - timedelta(days=1), points=10)
    publish(session, release)
    session.commit()
    result = client.get(f"/api/v1/reports/summary?from={DAY}&to={DAY}").json()
    assert result["summary"] == expected


def test_repeating_fractions_aggregate_before_rounding(
    client, session, journal_fixture
):
    from uuid import uuid4

    from test_catalog import draft, publish

    release, _, item, _ = draft(session, DAY - timedelta(days=1), points=3)
    item.target_count = 3
    publish(session, release)
    session.commit()
    for day in [DAY - timedelta(days=1), DAY]:
        response = client.put(
            f"/api/v1/days/{day}/adhkar/official:test_set:test_item",
            json={
                "catalogRelease": release.code,
                "clientMutationId": str(uuid4()),
                "expectedVersion": 0,
                "completedCount": 1,
            },
        )
        assert response.status_code == 200
    result = client.get("/api/v1/reports/summary?from=2026-11-18&to=2026-11-19").json()
    assert result["summary"] == {"earned": 2, "possible": 6, "percent": 33}
