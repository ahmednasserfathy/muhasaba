import json
import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.core.db import get_session
from app.core.observability import request_event
from app.main import app


def events(caplog):
    return [
        json.loads(r.message)
        for r in caplog.records
        if r.message.startswith('{"event":')
    ]


def test_request_event_uses_route_template_and_server_generated_id(caplog):
    probe = FastAPI()
    probe.middleware("http")(request_event)

    @probe.put("/private/{item}")
    def private(item: str):
        return {"ok": True}

    with (
        caplog.at_level(logging.INFO, logger="uvicorn.error"),
        TestClient(probe) as client,
    ):
        response = client.put(
            "/private/secret-item?token=secret-query",
            headers={
                "Authorization": "Bearer secret-auth",
                "X-Request-ID": "secret-id",
            },
            json={"text": "secret-body"},
        )
        client.get("/missing-secret")
    event = events(caplog)[0]
    assert event["route"] == "/private/{item}" and event["status"] == 200
    assert len(event["requestId"]) == 32
    assert event["requestId"] == response.headers["x-request-id"]
    assert events(caplog)[1]["route"] == "unmatched"
    assert "secret" not in caplog.text


def test_unhandled_exception_is_generic_and_never_logged_with_payload(caplog):
    probe = FastAPI()
    probe.middleware("http")(request_event)

    @probe.get("/failure")
    def failure():
        raise RuntimeError("private-text-and-database-password")

    with (
        caplog.at_level(logging.INFO, logger="uvicorn.error"),
        TestClient(probe) as client,
    ):
        response = client.get("/failure")
    assert response.status_code == 500
    assert response.json()["detail"] == "Internal server error"
    assert response.headers["cache-control"] == "no-store"
    assert "private-text" not in response.text + caplog.text
    assert events(caplog)[0]["status"] == 500


def test_readiness_missing_database_does_not_break_liveness(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with TestClient(app) as client:
        assert client.get("/ready").status_code == 503
        assert client.get("/health").json() == {"status": "ok"}


def test_readiness_database_failure_does_not_expose_connection_details():
    class Unavailable:
        def execute(self, statement):
            raise OperationalError("private-dsn", {}, Exception("private-password"))

    app.dependency_overrides[get_session] = lambda: Unavailable()
    try:
        with TestClient(app) as client:
            response = client.get("/ready")
        assert response.status_code == 503 and "private" not in response.text
    finally:
        app.dependency_overrides.pop(get_session)
