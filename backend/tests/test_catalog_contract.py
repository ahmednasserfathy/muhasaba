import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


def test_catalog_without_database_is_unavailable_not_published(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with TestClient(app) as client:
        assert client.get("/api/v1/catalog?date=2026-11-19").status_code == 503
        assert client.get("/health").status_code == 200


def test_public_catalog_is_read_only():
    with TestClient(app) as client:
        assert client.post("/api/v1/catalog", json={}).status_code == 405


def test_openapi_matches_reviewed_contract():
    snapshot = Path(__file__).parents[1] / "openapi.json"
    assert app.openapi() == json.loads(snapshot.read_text())
