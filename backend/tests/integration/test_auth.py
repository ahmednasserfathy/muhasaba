from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.core.db import get_session
from app.modules.auth import router as auth
from app.modules.auth.models import AuthSession, ExternalIdentity, User, UserSettings
from app.modules.auth.schemas import RefreshRequest
from app.modules.auth.security import RateLimiter, password_hasher, token_hash

PASSWORD = "test-only-password-123"


@pytest.fixture(autouse=True)
def fresh_rate_limiter(monkeypatch):
    monkeypatch.setattr(auth, "limiter", RateLimiter())


def register(client, email="person@example.com", **extra):
    response = client.post(
        "/api/v1/auth/register", json={"email": email, "password": PASSWORD, **extra}
    )
    assert response.status_code == 201, response.text
    return response.json()


def header(tokens):
    return {"Authorization": "Bearer " + tokens["accessToken"]}


def test_register_login_and_own_profile(client, session):
    tokens = register(client, "Person@EXAMPLE.COM")
    assert tokens["tokenType"] == "bearer"
    assert tokens["expiresIn"] == 900
    user = session.get(User, UUID(tokens["user"]["id"]))
    assert user.email_normalized == "person@example.com"
    assert user.password_hash.startswith("$argon2id$")
    assert user.role == "USER" and user.registration_source == "NATIVE"
    assert user.email_verified_at is None
    assert session.get(UserSettings, user.id).reminder_settings == {}
    current = session.scalar(select(AuthSession))
    assert current.access_token_hash == token_hash(tokens["accessToken"])
    assert current.refresh_token_hash == token_hash(tokens["refreshToken"])
    assert tokens["refreshToken"] != current.refresh_token_hash
    response = client.get("/api/v1/me", headers=header(tokens))
    assert response.status_code == 200
    assert response.json() == tokens["user"]
    assert response.headers["cache-control"] == "no-store"
    assert (
        not {"passwordHash", "password", "refreshToken", "accessToken"}
        & response.json().keys()
    )
    login = client.post(
        "/api/v1/auth/login", json={"email": "PERSON@example.com", "password": PASSWORD}
    )
    assert login.status_code == 200
    assert login.json()["user"]["id"] == str(user.id)
    assert login.json()["accessToken"] != tokens["accessToken"]


def test_duplicate_and_account_isolation(client, session):
    first = register(client)
    second = register(client, "other@example.com")
    duplicate = client.post(
        "/api/v1/auth/register",
        json={"email": "PERSON@example.com", "password": PASSWORD},
    )
    assert duplicate.status_code == 409
    assert session.scalar(select(func.count()).select_from(User)) == 2
    # User IDs in a query never select another account.
    response = client.get(
        "/api/v1/me", params={"userId": second["user"]["id"]}, headers=header(first)
    )
    assert response.json()["id"] == first["user"]["id"]
    assert (
        client.get("/api/v1/me", headers=header(second)).json()["id"]
        == second["user"]["id"]
    )


def test_login_failures_are_generic(client):
    register(client)
    wrong = client.post(
        "/api/v1/auth/login", json={"email": "person@example.com", "password": "wrong"}
    )
    missing = client.post(
        "/api/v1/auth/login", json={"email": "absent@example.com", "password": "wrong"}
    )
    assert wrong.status_code == missing.status_code == 401
    assert wrong.json() == missing.json()
    assert wrong.headers["www-authenticate"] == "Bearer"


def test_rotation_rejects_replay_and_old_access(client):
    old = register(client)
    refreshed = client.post(
        "/api/v1/auth/refresh", json={"refreshToken": old["refreshToken"]}
    )
    assert refreshed.status_code == 200
    new = refreshed.json()
    assert new["refreshToken"] != old["refreshToken"]
    assert client.get("/api/v1/me", headers=header(old)).status_code == 401
    assert (
        client.post(
            "/api/v1/auth/refresh", json={"refreshToken": old["refreshToken"]}
        ).status_code
        == 401
    )
    assert client.get("/api/v1/me", headers=header(new)).status_code == 200


def test_logout_revokes_only_presented_session_and_is_repeatable(client):
    first = register(client)
    second = client.post(
        "/api/v1/auth/login", json={"email": "person@example.com", "password": PASSWORD}
    ).json()
    for _ in range(2):
        assert (
            client.post(
                "/api/v1/auth/logout", json={"refreshToken": first["refreshToken"]}
            ).status_code
            == 204
        )
    assert client.get("/api/v1/me", headers=header(first)).status_code == 401
    assert (
        client.post(
            "/api/v1/auth/refresh", json={"refreshToken": first["refreshToken"]}
        ).status_code
        == 401
    )
    assert client.get("/api/v1/me", headers=header(second)).status_code == 200


def test_access_expiry_allows_refresh_but_not_extended_session(client, session):
    tokens = register(client)
    row = session.scalar(select(AuthSession))
    original_expiry = row.expires_at
    row.access_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    session.flush()
    assert client.get("/api/v1/me", headers=header(tokens)).status_code == 401
    new = client.post(
        "/api/v1/auth/refresh", json={"refreshToken": tokens["refreshToken"]}
    ).json()
    session.refresh(row)
    assert row.expires_at == original_expiry
    row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    session.flush()
    assert (
        client.post(
            "/api/v1/auth/refresh", json={"refreshToken": new["refreshToken"]}
        ).status_code
        == 401
    )


def test_deleted_user_cannot_use_existing_sessions(client, session):
    tokens = register(client)
    user = session.get(User, UUID(tokens["user"]["id"]))
    user.deleted_at = datetime.now(UTC)
    session.flush()
    assert client.get("/api/v1/me", headers=header(tokens)).status_code == 401
    assert (
        client.post(
            "/api/v1/auth/refresh", json={"refreshToken": tokens["refreshToken"]}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": "person@example.com", "password": PASSWORD},
        ).status_code
        == 401
    )


def test_imported_account_needs_activation_and_never_merges_by_email(client, session):
    user = User(
        email_normalized="imported@example.com",
        registration_source="IMPORTED",
        tracking_start_date=date(2026, 11, 1),
    )
    session.add(user)
    session.flush()
    session.add(
        ExternalIdentity(
            user_id=user.id,
            source_system="test-provider",
            external_subject="123",
            link_status="VERIFIED",
            verified_at=datetime.now(UTC),
        )
    )
    session.flush()
    session.commit()
    credentials = {"email": "imported@example.com", "password": PASSWORD}
    assert client.post("/api/v1/auth/login", json=credentials).status_code == 401
    user.password_hash = password_hasher.hash(PASSWORD)
    session.commit()
    assert client.post("/api/v1/auth/login", json=credentials).status_code == 401
    assert client.post("/api/v1/auth/register", json=credentials).status_code == 409
    assert session.scalar(select(func.count()).select_from(User)) == 1
    # Simulate a future verified activation, not an exposed PR-02 endpoint.
    user.email_verified_at = datetime.now(UTC)
    session.flush()
    response = client.post("/api/v1/auth/login", json=credentials)
    assert response.status_code == 200
    assert response.json()["user"]["registrationSource"] == "IMPORTED"
    assert response.json()["user"]["id"] == str(user.id)


def test_external_identity_uniqueness_and_fk(session):
    user = User(registration_source="IMPORTED", tracking_start_date=date(2026, 11, 1))
    session.add(user)
    session.flush()
    session.add(
        ExternalIdentity(user_id=user.id, source_system="test", external_subject="123")
    )
    session.flush()
    with pytest.raises(IntegrityError):
        with session.begin_nested():
            session.add(
                ExternalIdentity(
                    user_id=user.id, source_system="test", external_subject="123"
                )
            )
            session.flush()


def test_bearer_and_refresh_are_not_interchangeable(client):
    tokens = register(client)
    assert client.get("/api/v1/me").status_code == 401
    assert (
        client.get(
            "/api/v1/me", headers={"Authorization": "Bearer " + tokens["refreshToken"]}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/auth/refresh", json={"refreshToken": tokens["accessToken"]}
        ).status_code
        == 401
    )
    assert (
        client.get(
            "/api/v1/me", headers={"Authorization": "Bearer a_" + "X" * 43}
        ).status_code
        == 401
    )


def test_role_is_server_owned_and_admin_dependency_checks_current_role(client, session):
    assert (
        client.post(
            "/api/v1/auth/register",
            json={"email": "person@example.com", "password": PASSWORD, "role": "ADMIN"},
        ).status_code
        == 422
    )
    tokens = register(client)
    admin_app = FastAPI()
    admin_app.dependency_overrides[get_session] = lambda: session

    @admin_app.get("/admin-test")
    def protected(user=Depends(auth.require_admin)):
        return {"id": str(user.id)}

    with TestClient(admin_app) as admin_client:
        assert (
            admin_client.get("/admin-test", headers=header(tokens)).status_code == 403
        )
        user = session.get(User, UUID(tokens["user"]["id"]))
        user.role = "ADMIN"
        session.flush()
        assert (
            admin_client.get("/admin-test", headers=header(tokens)).status_code == 200
        )
        user.role = "USER"
        session.flush()
        assert (
            admin_client.get("/admin-test", headers=header(tokens)).status_code == 403
        )


def test_login_rate_limit_returns_retry_after(client):
    for _ in range(10):
        assert (
            client.post(
                "/api/v1/auth/login",
                json={"email": "missing@example.com", "password": "wrong"},
            ).status_code
            == 401
        )
    response = client.post(
        "/api/v1/auth/login", json={"email": "missing@example.com", "password": "wrong"}
    )
    assert response.status_code == 429
    assert int(response.headers["retry-after"]) > 0


def test_concurrent_refresh_only_one_succeeds(migrated_engine):
    # Dedicated committed fixture so separate PostgreSQL connections see the row.
    with Session(migrated_engine) as db:
        user = User(
            email_normalized="race@example.com",
            password_hash=password_hasher.hash(PASSWORD),
            tracking_start_date=date(2026, 11, 1),
        )
        db.add(user)
        db.flush()
        user_id = user.id
        tokens = auth.issue_tokens(db, user)
        db.commit()
    try:

        def rotate():
            with Session(migrated_engine) as db:
                request = Request(
                    {"type": "http", "client": ("test", 1), "headers": []}
                )
                try:
                    auth.refresh(
                        RefreshRequest(refreshToken=tokens.refresh_token), request, db
                    )
                    return 200
                except HTTPException as error:
                    return error.status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            assert sorted(pool.map(lambda _: rotate(), range(2))) == [200, 401]
    finally:
        with migrated_engine.begin() as connection:
            connection.execute(
                delete(AuthSession).where(AuthSession.user_id == user_id)
            )
            connection.execute(delete(User).where(User.id == user_id))
