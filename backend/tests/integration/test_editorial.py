from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from test_journal import DAY
from test_journal import journal as _journal_fixture

from app.modules.auth.models import User
from app.modules.editorial import router as editorial

journal = _journal_fixture


def edit(version=0):
    return dict(clientMutationId=str(uuid4()), expectedVersion=version)


def library(**overrides):
    return {
        **edit(),
        "code": str(uuid4()),
        "type": "DHIKR",
        "textAr": "نص اختبار اصطناعي",
        "defaultTargetCount": 1,
        "sourceName": "Synthetic fixture",
        "sourceUrl": "https://example.test/source",
        "licenseNotes": "Test only",
        **overrides,
    }


@pytest.fixture
def admin(client, session, journal, monkeypatch):
    monkeypatch.setattr(editorial, "today", lambda user: DAY)
    user = session.scalar(select(User).where(User.email == "person@example.com"))
    user.role = "ADMIN"
    session.commit()
    return journal[0]


def test_admin_permission_matrix(client, journal):
    assert client.get("/api/v1/admin/library-items").status_code == 403
    assert client.post("/api/v1/admin/library-items", json=library()).status_code == 403
    client.headers.pop("Authorization")
    assert client.get("/api/v1/admin/library-items").status_code == 401


def test_review_publish_archive_and_immutable_history(client, admin):
    data = library()
    created = client.post("/api/v1/admin/library-items", json=data)
    assert created.status_code == 201
    assert (
        client.post("/api/v1/admin/library-items", json=data).json() == created.json()
    )
    source = created.json()
    release = client.post(
        "/api/v1/admin/catalog-releases",
        json={
            **edit(),
            "baseReleaseId": str(admin.id),
            "code": str(uuid4()),
            "effectiveFrom": str(DAY + timedelta(days=1)),
        },
    )
    assert release.status_code == 201
    key = release.json()["id"]
    binding = {
        **edit(1),
        "items": [{"libraryEntryId": source["id"], "code": "new", "targetCount": 1}],
    }
    route = f"/api/v1/admin/catalog-releases/{key}/groups/test_set/items"
    assert client.put(route, json=binding).status_code == 422
    verified = client.patch(
        f"/api/v1/admin/library-items/{source['id']}",
        json={**data, **edit(1), "verified": True},
    )
    assert verified.status_code == 200 and verified.json()["reviewedAt"]
    assert client.put(route, json=binding).status_code == 200
    published = client.post(
        f"/api/v1/admin/catalog-releases/{key}/publish", json=edit(2)
    )
    assert published.status_code == 200
    original = client.get(f"/api/v1/catalog?date={DAY + timedelta(days=1)}").json()
    assert client.put(route, json={**binding, **edit(3)}).status_code == 409
    assert (
        client.patch(
            f"/api/v1/admin/library-items/{source['id']}",
            json={**data, **edit(2), "textAr": "تعديل المصدر", "verified": True},
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/v1/admin/library-items/{source['id']}/archive", json=edit(3)
        ).status_code
        == 200
    )
    assert (
        client.get(f"/api/v1/catalog?date={DAY + timedelta(days=1)}").json() == original
    )
    assert client.get(f"/api/v1/catalog?date={DAY}").json()["release"] == admin.code


def test_empty_group_cannot_publish(client, admin):
    response = client.post(
        "/api/v1/admin/catalog-releases",
        json={
            **edit(),
            "baseReleaseId": str(admin.id),
            "code": str(uuid4()),
            "effectiveFrom": str(DAY + timedelta(days=1)),
        },
    )
    key = response.json()["id"]
    assert (
        client.put(
            f"/api/v1/admin/catalog-releases/{key}/groups/test_set/items",
            json={**edit(1), "items": []},
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/v1/admin/catalog-releases/{key}/publish", json=edit(2)
        ).status_code
        == 422
    )
