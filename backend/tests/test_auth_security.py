from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.modules.auth.schemas import RegisterRequest
from app.modules.auth.security import (
    RateLimiter,
    new_token,
    password_hasher,
    token_hash,
    verify_password,
)


def test_password_hashing_and_token_entropy():
    password = "a long test password"
    encoded = password_hasher.hash(password)
    assert encoded.startswith("$argon2id$")
    assert password not in encoded
    assert verify_password(password, encoded)
    assert not verify_password("wrong", encoded)
    assert not verify_password(password, None)
    assert not verify_password(password, "not-a-hash")
    values = {new_token("a_") for _ in range(100)}
    assert len(values) == 100
    assert all(len(value) == 45 for value in values)
    assert len(token_hash(next(iter(values)))) == 64


def test_rate_limit_expiry_and_bounded_storage():
    clock = [0]
    limiter = RateLimiter(capacity=2, clock=lambda: clock[0])
    limiter.check("login", 2, 60)
    limiter.check("login", 2, 60)
    with pytest.raises(HTTPException) as error:
        limiter.check("login", 2, 60)
    assert error.value.status_code == 429
    assert int(error.value.headers["Retry-After"]) > 0
    limiter.check("another", 2, 60)
    with pytest.raises(HTTPException):
        limiter.check("third", 2, 60)
    assert len(limiter.entries) == 2
    clock[0] = 61
    limiter.check("third", 2, 60)
    assert len(limiter.entries) == 1


def test_registration_normalizes_email_and_local_start_date():
    body = RegisterRequest(
        email="Person@EXAMPLE.COM",
        password="long-password-123",
        timezone="Pacific/Kiritimati",
    )
    assert body.email == "person@example.com"
    from zoneinfo import ZoneInfo

    assert (
        body.tracking_start_date == datetime.now(ZoneInfo("Pacific/Kiritimati")).date()
    )


@pytest.mark.parametrize(
    "extra",
    [
        dict(role="ADMIN"),
        dict(registrationSource="IMPORTED"),
        dict(id="forged"),
        dict(emailVerified=True),
        dict(timezone="not/a/zone"),
        dict(
            trackingStartDate=(datetime.now(UTC) + timedelta(days=2)).date().isoformat()
        ),
    ],
)
def test_registration_rejects_privilege_fields_and_invalid_dates(extra):
    with pytest.raises(ValidationError):
        RegisterRequest.model_validate(
            {"email": "test@example.com", "password": "long-password-123", **extra}
        )


def test_auth_validation_does_not_echo_secrets(monkeypatch):
    # Override DB dependency so validation can be exercised without PostgreSQL.
    from app.core.db import get_session

    app.dependency_overrides[get_session] = lambda: None
    try:
        with TestClient(app) as client:
            secret = "short-secret"
            response = client.post(
                "/api/v1/auth/register", json={"email": "bad", "password": secret}
            )
            assert response.status_code == 422
            assert secret not in response.text
            assert "input" not in response.text
            assert response.headers["cache-control"] == "no-store"
    finally:
        app.dependency_overrides.pop(get_session, None)
