"""企业能力 API 与合规报告构建单元测试。"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api import enterprise as enterprise_api
from config.settings import settings
from core.compliance.workflow_execution_report import build_workflow_execution_compliance_report
from core.security.deps import require_audit_reader
from core.security.rbac import PlatformRole
from core.security.secret_resolver import resolve_secret
from core.workflows.models import WorkflowExecution, WorkflowExecutionState

from tests.helpers import make_fastapi_app_router_only


def _client() -> TestClient:
    app = make_fastapi_app_router_only(enterprise_api)
    app.dependency_overrides[require_audit_reader] = lambda: PlatformRole.ADMIN
    return TestClient(app)


def test_enterprise_capabilities_endpoint() -> None:
    resp = _client().get("/api/v1/enterprise/capabilities")
    assert resp.status_code == 200
    body = resp.json()
    assert "oidc_enabled" in body
    assert "otel_enabled" in body
    assert body["secret_resolver_mode"] in ("env", "vault_env", "file")


def test_resolve_secret_env_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "secret_resolver_mode", "env", raising=False)
    monkeypatch.setenv("TEST_SECRET_KEY", "abc123")
    assert resolve_secret("TEST_SECRET_KEY") == "abc123"


def test_compliance_report_structure() -> None:
    db_session = MagicMock()
    execution = WorkflowExecution(
        execution_id="ex-test-1",
        workflow_id="wf-test-1",
        version_id="ver-1",
        tenant_id="default",
        state=WorkflowExecutionState.COMPLETED,
        trigger_type="manual",
        global_context={"correlation_id": "corr-abc"},
    )
    mock_svc = MagicMock()
    mock_svc.get_execution.return_value = execution

    mock_approval_repo = MagicMock()
    mock_approval_repo.list_by_execution.return_value = []

    with (
        patch(
            "core.compliance.workflow_execution_report.WorkflowExecutionService",
            return_value=mock_svc,
        ),
        patch(
            "core.compliance.workflow_execution_report.WorkflowApprovalTaskRepository",
            return_value=mock_approval_repo,
        ),
        patch(
            "core.compliance.workflow_execution_report.query_audit_logs",
            return_value=([], 0),
        ),
    ):
        report = build_workflow_execution_compliance_report(
            db_session,
            workflow_id="wf-test-1",
            execution_id="ex-test-1",
            tenant_id="default",
        )

    assert report["report_type"] == "workflow_execution_compliance"
    assert report["collaboration"]["correlation_id"] == "corr-abc"
    assert report["execution"]["state"] == "completed"


def test_oidc_validator_disabled() -> None:
    from core.security.oidc_validator import validate_bearer_token

    with patch.object(settings, "oidc_enabled", False):
        claims, err = validate_bearer_token("dummy")
    assert claims is None
    assert err == "oidc_disabled"
