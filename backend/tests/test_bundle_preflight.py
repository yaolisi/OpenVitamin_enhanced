"""环境预检。"""
from __future__ import annotations

from core.demos.bundle_preflight import check_import_environment


def test_preflight_structure() -> None:
    env = check_import_environment(tenant_id="default")
    assert "ready" in env
    assert "checks" in env
    assert isinstance(env["checks"], list)
