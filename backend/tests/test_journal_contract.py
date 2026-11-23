from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.modules.journal import service
from app.modules.journal.schemas import CountWrite, SetWrite, StateWrite


def test_today_uses_account_zone_across_midnight(monkeypatch):
    class FixedTime:
        @staticmethod
        def now(zone):
            return datetime(2026, 11, 19, 23, 30, tzinfo=UTC).astimezone(zone)

    monkeypatch.setattr(service, "datetime", FixedTime)
    assert service.today(SimpleNamespace(timezone="Africa/Cairo")) == date(2026, 11, 20)
    assert service.today(SimpleNamespace(timezone="America/New_York")) == date(
        2026, 11, 19
    )


@pytest.mark.parametrize(
    "schema,fields",
    [
        (StateWrite, {"state": "COMPLETED", "expectedVersion": True}),
        (StateWrite, {"state": "COMPLETED", "expectedVersion": -1}),
        (CountWrite, {"completedCount": 1.5, "expectedVersion": 0}),
        (CountWrite, {"completedCount": 1001, "expectedVersion": 0}),
        (SetWrite, {"action": "TOGGLE", "expectedVersions": {}}),
        (SetWrite, {"action": "CLEAR_ALL", "expectedVersions": {"x": True}}),
    ],
)
def test_write_contract_rejects_ambiguous_counts_and_versions(schema, fields):
    with pytest.raises(ValidationError):
        schema(
            clientMutationId="00000000-0000-4000-8000-000000000001",
            catalogRelease="test",
            **fields,
        )
