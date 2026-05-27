"""本地账号注册 / 登录 / 会话。"""
from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient

import main
from config import settings as settings_module


@pytest.fixture()
def local_auth_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    settings_module.settings.local_auth_enabled = True
    settings_module.settings.local_auth_allow_registration = True
    settings_module.settings.auth_require_login = False
    settings_module.settings.csrf_enabled = False
    importlib.reload(main)
    with TestClient(main.app) as client:
        yield client


def test_register_login_session_logout(local_auth_client: TestClient) -> None:
    r = local_auth_client.post(
        "/api/v1/auth/register",
        json={"username": "alice", "password": "password123", "display_name": "Alice"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["username"] == "alice"
    assert r.json()["platform_role"] == "admin"

    session = local_auth_client.get("/api/v1/auth/session")
    assert session.status_code == 200
    body = session.json()
    assert body["authenticated"] is True
    assert body["auth_method"] == "local"
    assert body["username"] == "alice"

    local_auth_client.post("/api/v1/auth/logout")
    after = local_auth_client.get("/api/v1/auth/session")
    assert after.json()["auth_method"] == "anonymous"


def test_login_invalid_credentials(local_auth_client: TestClient) -> None:
    local_auth_client.post(
        "/api/v1/auth/register",
        json={"username": "bob", "password": "password123"},
    )
    bad = local_auth_client.post(
        "/api/v1/auth/login",
        json={"username": "bob", "password": "wrong-password"},
    )
    assert bad.status_code == 401
