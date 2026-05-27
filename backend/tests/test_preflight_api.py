"""运行前预检 API 测试。"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from api import preflight as preflight_api
from core.security.deps import require_platform_write
from core.security.rbac import PlatformRole

from tests.helpers import make_fastapi_app_router_only


def _client() -> TestClient:
    app = make_fastapi_app_router_only(preflight_api)
    app.dependency_overrides[require_platform_write] = lambda: PlatformRole.OPERATOR
    return TestClient(app)


def test_agent_preflight_missing() -> None:
    with patch("core.preflight.run_preflight.get_agent_registry") as reg:
        reg.return_value.get_agent.return_value = None
        resp = _client().get("/api/v1/preflight/agents/missing-id")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ready"] is False
    assert body["target"] == "agent"


def test_agent_preflight_ready() -> None:
    agent = MagicMock()
    agent.model_id = "m1"
    agent.enabled_skills = ["s1"]
    agent.execution_mode = "legacy"
    model = MagicMock()
    model.id = "m1"
    with (
        patch("core.preflight.run_preflight.get_agent_registry") as reg,
        patch("core.preflight.run_preflight.get_model_registry") as mreg,
    ):
        reg.return_value.get_agent.return_value = agent
        mreg.return_value.list_models.return_value = [model]
        resp = _client().get("/api/v1/preflight/agents/a1")
    assert resp.status_code == 200
    assert resp.json()["ready"] is True
