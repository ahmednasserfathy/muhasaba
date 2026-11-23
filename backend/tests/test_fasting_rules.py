from datetime import date
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.modules.fasting.schemas import PlanWrite
from app.modules.fasting.service import base_policy
from scripts.ramadan_calendar import configure


@pytest.mark.parametrize(
    "day,expected", [(16, "WEEKLY"), (18, "UNPLANNED"), (19, "WEEKLY")]
)
def test_weekly_baseline(day, expected):
    assert base_policy(date(2026, 11, day), "EG", [])["baseReason"] == expected


@pytest.mark.parametrize(
    "region,status,expected",
    [
        ("EG", "CONFIRMED", "RAMADAN"),
        ("EG", "PROVISIONAL", "UNPLANNED"),
        ("OTHER", "CONFIRMED", "UNPLANNED"),
    ],
)
def test_only_matching_confirmed_region_changes_baseline(region, status, expected):
    period = SimpleNamespace(
        region_key=region,
        start_date=date(2026, 11, 18),
        end_date=date(2026, 11, 20),
        confirmation_status=status,
        source_url="https://example.test/calendar",
    )
    assert base_policy(date(2026, 11, 18), "EG", [period])["baseReason"] == expected
    assert base_policy(date(2026, 11, 21), "EG", [period])["baseReason"] == "UNPLANNED"


@pytest.mark.parametrize(
    "fields",
    [
        {"mode": "RAMADAN", "expectedVersion": 0},
        {"mode": "ADD", "fastType": "RAMADAN", "expectedVersion": 0},
        {"mode": "SKIP", "fastType": "MAKEUP", "expectedVersion": 0},
        {"mode": "DEFAULT", "expectedVersion": True},
        {"mode": "ADD", "expectedVersion": -1},
    ],
)
def test_plan_contract(fields):
    with pytest.raises(ValidationError):
        PlanWrite(clientMutationId="00000000-0000-4000-8000-000000000001", **fields)


def test_confirmed_configuration_requires_source_before_database_access():
    with pytest.raises(ValueError, match="source"):
        configure(None, "EG", date(2026, 1, 1), date(2026, 1, 29), "CONFIRMED", None)
