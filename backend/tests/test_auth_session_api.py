"""GET /api/v1/auth/session"""
from __future__ import annotations

from fastapi.testclient import TestClient

from main import app


def test_auth_session_defaults_operator() -> None:
    client = TestClient(app)
    r = client.get("/api/v1/auth/session")
    assert r.status_code == 200
    body = r.json()
    assert body["user_id"] == "default"
    assert body["platform_role"] in ("admin", "operator", "viewer")
    assert "auth_method" in body
    assert "display_label" in body
