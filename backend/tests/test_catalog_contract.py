import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


def test_catalog_without_database_is_unavailable_not_published(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with TestClient(app) as client:
        assert client.get("/api/v1/catalog?date=2026-11-19").status_code == 503
        assert client.get("/health").status_code == 200


def test_no_editorial_write_routes_exposed():
    with TestClient(app) as client:
        assert client.post("/api/v1/catalog", json={}).status_code == 405
        assert client.post("/api/v1/admin/library-items", json={}).status_code == 404


def test_openapi_matches_reviewed_contract():
    snapshot = Path(__file__).parents[1] / "openapi.json"
    assert app.openapi() == json.loads(snapshot.read_text())
