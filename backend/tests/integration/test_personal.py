import hashlib
import json
from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from test_auth import header, register
from test_journal import DAY, card, send
from test_journal import journal as _journal_fixture

from app.modules.auth.models import User
from app.modules.journal import service
from app.modules.journal.models import MutationReceipt
from app.modules.journal.schemas import CountWrite

journal = _journal_fixture
PLAN = "/api/v1/me/groups/test_set/plan"


def body(release, **overrides):
    return dict(
        clientMutationId=str(uuid4()),
        expectedVersion=0,
        catalogRelease=release.code,
        effectiveFrom=str(DAY),
        hiddenDefaultCodes=["second"],
        officialOrder=["second", "test_item"],
        customItems=[
            dict(id=str(uuid4()), type="DUA", textAr="نص شخصي للاختبار", targetCount=2)
        ],
        **overrides,
    )


def test_private_completion_hidden_official_bulk_and_undo(client, journal):
    release = journal[0]
    plan = body(release)
    assert client.put(PLAN, json=plan).status_code == 200
    item_id = plan["customItems"][0]["id"]
    before = card(client.get(f"/api/v1/days/{DAY}"), "test_set")
    assert before["items"][0]["hidden"] and before["possiblePoints"] == 2
    result, _ = send(
        client,
        release,
        f"adhkar/personal:{item_id}",
        completedCount=2,
        expectedVersion=0,
        expectedPlanVersion=1,
    )
    group = card(result, "test_set")
    assert group["earnedPoints"] == 0 and group["personalCompleted"] == 1
    full, _ = send(
        client,
        release,
        "adhkar-sets/test_set",
        action="COMPLETE_ALL",
        expectedVersions={"test_item": 0, "second": 0},
    )
    assert card(full, "test_set")["earnedPoints"] == 2
    cleared, _ = send(
        client,
        release,
        "adhkar-sets/test_set",
        action="CLEAR_ALL",
        expectedVersions={"test_item": 1, "second": 1},
    )
    group = card(cleared, "test_set")
    assert group["earnedPoints"] == 0 and group["personalCompleted"] == 1
    undo, _ = send(
        client,
        release,
        f"adhkar/personal:{item_id}",
        completedCount=0,
        expectedVersion=1,
        expectedPlanVersion=1,
    )
    assert card(undo, "test_set")["personalCompleted"] == 0
    assert card(undo, "test_set")["possiblePoints"] == 2


def test_plan_receipts_versions_and_private_input_redaction(client, journal):
    payload = body(journal[0])
    first = client.put(PLAN, json=payload)
    assert first.status_code == 200 and first.headers["cache-control"] == "no-store"
    assert client.put(PLAN, json=payload).json() == first.json()
    changed = {**payload, "officialOrder": []}
    assert (
        client.put(PLAN, json=changed).json()["detail"]["code"]
        == "IDEMPOTENCY_KEY_REUSE"
    )
    changed["clientMutationId"] = str(uuid4())
    assert client.put(PLAN, json=changed).status_code == 409
    changed["customItems"][0]["targetCount"] = 0
    invalid = client.put(PLAN, json=changed)
    assert invalid.status_code == 422
    assert "نص شخصي" not in invalid.text


def test_private_owner_and_admin_cannot_override_ownership(client, session, journal):
    payload = body(journal[0])
    assert client.put(PLAN, json=payload).status_code == 200
    other = register(client, "other@example.com", trackingStartDate="2026-11-01")
    client.headers.update(header(other))
    user = session.scalar(
        select(User).where(User.email_normalized == "other@example.com")
    )
    user.role = "ADMIN"
    session.commit()
    assert client.get("/api/v1/me/custom-items").json() == []
    assert (
        client.put(PLAN, json={**payload, "clientMutationId": str(uuid4())}).status_code
        == 404
    )
    result, _ = send(
        client,
        journal[0],
        f"adhkar/personal:{payload['customItems'][0]['id']}",
        completedCount=1,
        expectedVersion=0,
        expectedPlanVersion=1,
    )
    assert result.status_code == 404
    assert "نص شخصي" not in client.get(f"/api/v1/catalog?date={DAY}").text


def test_future_edit_archive_restore_never_rewrites_history(
    client, journal, monkeypatch
):
    payload = body(journal[0])
    assert client.put(PLAN, json=payload).status_code == 200
    send(client, journal[0], state="COMPLETED", expectedVersion=0)
    original = client.get(f"/api/v1/days/{DAY}").json()
    edited = {
        **payload,
        "clientMutationId": str(uuid4()),
        "expectedVersion": 1,
        "effectiveFrom": str(DAY + timedelta(days=1)),
        "customItems": [
            {**payload["customItems"][0], "textAr": "تعديل لاحق", "targetCount": 5}
        ],
    }
    assert client.put(PLAN, json=edited).status_code == 200
    assert client.get(f"/api/v1/days/{DAY}").json() == original
    restored = {**edited, "clientMutationId": str(uuid4()), "expectedVersion": 2}
    response = client.post("/api/v1/me/groups/test_set/restore-defaults", json=restored)
    assert response.status_code == 200 and response.json()["customItems"] == []
    assert client.get("/api/v1/me/custom-items").json()[0]["archived"]
    assert client.get(f"/api/v1/days/{DAY}").json() == original
    monkeypatch.setattr(service, "today", lambda user: DAY + timedelta(days=1))
    assert (
        card(client.get(f"/api/v1/days/{DAY + timedelta(days=1)}"), "test_set")[
            "personalTotal"
        ]
        == 0
    )


def test_today_edit_rejected_after_undone_progress_and_old_dates(client, journal):
    release = journal[0]
    send(
        client,
        release,
        "adhkar/official:test_set:test_item",
        completedCount=1,
        expectedVersion=0,
    )
    send(
        client,
        release,
        "adhkar/official:test_set:test_item",
        completedCount=0,
        expectedVersion=1,
    )
    payload = body(release)
    result = client.put(PLAN, json=payload)
    assert result.json()["detail"]["code"] == "GROUP_ALREADY_EDITED"
    payload["effectiveFrom"] = str(DAY - timedelta(days=1))
    assert client.put(PLAN, json=payload).status_code == 422
    payload["effectiveFrom"] = str(DAY + timedelta(days=1))
    assert client.put(PLAN, json=payload).status_code == 200


def test_stale_personal_plan_and_future_plan_do_not_silently_revert(client, journal):
    release = journal[0]
    payload = body(release)
    assert client.put(PLAN, json=payload).status_code == 200
    result, _ = send(
        client,
        release,
        f"adhkar/personal:{payload['customItems'][0]['id']}",
        completedCount=1,
        expectedVersion=0,
    )
    assert result.json()["detail"]["code"] == "PLAN_CHANGED"
    payload.update(
        clientMutationId=str(uuid4()),
        expectedVersion=1,
        effectiveFrom=str(DAY + timedelta(days=1)),
    )
    assert client.put(PLAN, json=payload).status_code == 200
    payload.update(
        clientMutationId=str(uuid4()), expectedVersion=2, effectiveFrom=str(DAY)
    )
    assert (
        client.put(PLAN, json=payload).json()["detail"]["code"] == "FUTURE_PLAN_EXISTS"
    )


def test_pre_upgrade_official_receipt_replays(client, session, journal):
    release = journal[0]
    response, payload = send(
        client,
        release,
        "adhkar/official:test_set:test_item",
        completedCount=1,
        expectedVersion=0,
    )
    old_body = CountWrite.model_validate(payload).model_dump(mode="json")
    old_body.pop("expected_plan_version")
    receipt = session.scalar(
        select(MutationReceipt).where(
            MutationReceipt.id == UUID(payload["clientMutationId"])
        )
    )
    receipt.payload_hash = hashlib.sha256(
        json.dumps(
            [str(DAY), "count", "official:test_set:test_item", old_body],
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    session.commit()
    retry = client.put(
        f"/api/v1/days/{DAY}/adhkar/official:test_set:test_item", json=payload
    )
    assert retry.status_code == 200 and retry.json() == response.json()


def test_item_crud_updates_dated_plan_and_archives_without_deletion(client, journal):
    release = journal[0]
    item = body(release)["customItems"][0]
    context = dict(
        clientMutationId=str(uuid4()),
        expectedVersion=0,
        catalogRelease=release.code,
        effectiveFrom=str(DAY + timedelta(days=1)),
        activityCode="test_set",
    )
    response = client.post("/api/v1/me/custom-items", json={**context, "item": item})
    assert response.status_code == 201 and response.json()["customItems"] == [item]
    context.update(clientMutationId=str(uuid4()), expectedVersion=1)
    item["targetCount"] = 3
    response = client.patch(
        f"/api/v1/me/custom-items/{item['id']}", json={**context, "item": item}
    )
    assert (
        response.status_code == 200
        and response.json()["customItems"][0]["targetCount"] == 3
    )
    context.update(clientMutationId=str(uuid4()), expectedVersion=2)
    response = client.request(
        "DELETE", f"/api/v1/me/custom-items/{item['id']}", json=context
    )
    assert response.status_code == 200 and response.json()["customItems"] == []
    assert client.get("/api/v1/me/custom-items").json()[0]["archived"]


def test_five_official_three_complete_hidden_two_personal_still_one_point_two(
    client, session, journal
):
    from test_catalog import draft, publish

    from app.modules.catalog.models import AdhkarItem

    release, group, item, _ = draft(session, DAY - timedelta(days=1))
    item.target_count = 1
    for index in range(1, 5):
        session.add(
            AdhkarItem(
                activity_id=group.id,
                code=f"item{index}",
                text_ar="اختبار",
                sort_order=index + 1,
                target_count=1,
                review_status="VERIFIED",
                source_name="Test",
                source_url="https://example.test",
                license_notes="Synthetic",
            )
        )
    session.flush()
    publish(session, release)
    session.commit()
    payload = body(release)
    payload.update(hiddenDefaultCodes=["item3", "item4"], officialOrder=[])
    assert client.put(PLAN, json=payload).status_code == 200
    for code in ["test_item", "item1", "item2"]:
        response, _ = send(
            client,
            release,
            f"adhkar/official:test_set:{code}",
            completedCount=1,
            expectedVersion=0,
        )
        assert response.status_code == 200
    response, _ = send(
        client,
        release,
        f"adhkar/personal:{payload['customItems'][0]['id']}",
        completedCount=2,
        expectedVersion=0,
        expectedPlanVersion=1,
    )
    group = card(response, "test_set")
    assert group["earnedPoints"] == 1.2 and group["possiblePoints"] == 2
    assert group["hiddenOfficialIncomplete"] == 2 and group["personalCompleted"] == 1


def test_new_catalog_drops_obsolete_display_codes_but_preserves_private_plan(
    client, session, journal
):
    from test_catalog import draft, publish

    payload = body(journal[0])
    assert client.put(PLAN, json=payload).status_code == 200
    newer, _, _, _ = draft(session, DAY + timedelta(days=1))
    publish(session, newer)
    session.commit()
    result = client.get(f"{PLAN}?date={DAY + timedelta(days=1)}").json()
    assert result["hiddenDefaultCodes"] == []
    assert result["officialOrder"] == ["test_item"]
    assert result["customItems"] == payload["customItems"]
    context = dict(
        clientMutationId=str(uuid4()),
        expectedVersion=1,
        catalogRelease=newer.code,
        effectiveFrom=str(DAY + timedelta(days=1)),
        activityCode="test_set",
    )
    result = client.patch(
        f"/api/v1/me/custom-items/{payload['customItems'][0]['id']}",
        json={**context, "item": {**payload["customItems"][0], "targetCount": 3}},
    )
    assert result.status_code == 200
