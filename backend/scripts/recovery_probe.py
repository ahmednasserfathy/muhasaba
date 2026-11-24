"""Synthetic API recovery drill, guarded to explicitly selected *_test databases."""

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.db import get_engine
from app.main import app
from scripts.journal_demo import create_demo

EMAIL = "recovery-probe@example.com"
PASSWORD = "Synthetic recovery test password only 2026!"


def ok(response, status=200):
    if response.status_code != status:
        # Do not print response bodies, credentials or submitted private content.
        raise RuntimeError(
            f"Recovery probe received unexpected HTTP {response.status_code}"
        )
    return response.json()


def seed(client):
    day = str(datetime.now(ZoneInfo("Africa/Cairo")).date())
    with Session(get_engine()) as db:
        create_demo(db, datetime.fromisoformat(day).date())
        db.commit()
    tokens = ok(
        client.post(
            "/api/v1/auth/register",
            json={
                "email": EMAIL,
                "password": PASSWORD,
                "trackingStartDate": day,
            },
        ),
        201,
    )
    client.headers["Authorization"] = "Bearer " + tokens["accessToken"]
    initial = ok(client.get(f"/api/v1/days/{day}"))
    group = next(c for c in initial["activities"] if c["kind"] == "ADHKAR_SET")
    private_id = str(uuid4())
    ok(
        client.put(
            f"/api/v1/me/groups/{group['code']}/plan",
            json={
                "clientMutationId": str(uuid4()),
                "expectedVersion": 0,
                "catalogRelease": initial["catalogRelease"],
                "effectiveFrom": day,
                "hiddenDefaultCodes": [group["items"][1]["code"]],
                "officialOrder": [],
                "customItems": [
                    {
                        "id": private_id,
                        "type": "DUA",
                        "textAr": "Synthetic private recovery probe",
                        "targetCount": 1,
                    }
                ],
            },
        )
    )
    payload = {
        "clientMutationId": str(uuid4()),
        "catalogRelease": initial["catalogRelease"],
        "expectedVersion": 0,
        "completedCount": 1,
    }
    route = f"/api/v1/days/{day}/adhkar/{group['items'][0]['itemKey']}"
    receipt = ok(client.put(route, json=payload))
    final = ok(
        client.put(
            f"/api/v1/days/{day}/adhkar/personal:{private_id}",
            json={
                **payload,
                "clientMutationId": str(uuid4()),
                "expectedPlanVersion": 1,
            },
        )
    )
    old_group = next(c for c in receipt["activities"] if c["code"] == group["code"])
    new_group = next(c for c in final["activities"] if c["code"] == group["code"])
    assert old_group["earnedPoints"] == new_group["earnedPoints"]
    assert new_group["personalCompleted"] == 1
    assert new_group["hiddenOfficialIncomplete"] == 1
    return {
        "day": final,
        "receipt": receipt,
        "payload": payload,
        "route": route,
        "items": ok(client.get("/api/v1/me/custom-items")),
        "report": ok(client.get(f"/api/v1/reports/summary?from={day}&to={day}")),
    }


def verify(client, expected):
    tokens = ok(
        client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})
    )
    client.headers["Authorization"] = "Bearer " + tokens["accessToken"]
    day = expected["day"]["date"]
    assert ok(client.get("/ready")) == {"status": "ok"}
    assert ok(client.get(f"/api/v1/days/{day}")) == expected["day"]
    assert ok(client.get("/api/v1/me/custom-items")) == expected["items"]
    assert (
        ok(client.get(f"/api/v1/reports/summary?from={day}&to={day}"))
        == expected["report"]
    )
    assert (
        ok(client.put(expected["route"], json=expected["payload"]))
        == expected["receipt"]
    )
    assert ok(client.get(f"/api/v1/days/{day}")) == expected["day"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["seed", "verify"])
    parser.add_argument("expectations", type=Path)
    args = parser.parse_args()
    url = make_url(os.environ["DATABASE_URL"])
    if url.get_backend_name() != "postgresql" or not (url.database or "").endswith(
        "_test"
    ):
        raise SystemExit(
            "Recovery probe requires a disposable PostgreSQL *_test database"
        )
    with TestClient(app) as client:
        if args.action == "seed":
            # Fail before creating fixtures when a prior expectation file exists.
            with args.expectations.open("x", encoding="utf-8") as output:
                os.chmod(args.expectations, 0o600)
                json.dump(seed(client), output, ensure_ascii=False)
        else:
            verify(client, json.loads(args.expectations.read_text(encoding="utf-8")))
    print(f"Recovery {args.action}: PASS (synthetic account, snapshots and receipts)")


if __name__ == "__main__":
    main()
