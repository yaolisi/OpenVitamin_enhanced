from __future__ import annotations

from config.settings import settings
from core.enterprise.capabilities import build_enterprise_capabilities, evaluate_production_readiness


def test_production_readiness_has_checks() -> None:
    checks = evaluate_production_readiness()
    assert len(checks) >= 8
    assert all("id" in c and "status" in c for c in checks)


def test_capabilities_shape() -> None:
    caps = build_enterprise_capabilities()
    assert "production_readiness" in caps
    assert "percent" in caps["production_readiness"]


def test_oidc_guardrail_issue_when_enabled_without_issuer(monkeypatch) -> None:
    from config import settings as settings_mod

    monkeypatch.setattr(settings, "debug", False, raising=False)
    monkeypatch.setattr(settings, "oidc_enabled", True, raising=False)
    monkeypatch.setattr(settings, "oidc_issuer", "", raising=False)
    monkeypatch.setattr(settings, "oidc_jwks_url", "", raising=False)
    issues = settings_mod.validate_production_security_guardrails(settings)
    assert any("oidc_enabled" in i for i in issues)
