"""Bundle 预览。"""
from __future__ import annotations

from core.demos.bundle_preview import preview_import_bundle


def test_preview_platform_bundle() -> None:
    bundle = {
        "schema_version": 1,
        "bundle_type": "platform",
        "bundle_id": "test",
        "agents": [{"bundle_key": "a1", "name": "A", "model_id": "__AUTO_LLM__"}],
        "workflows": [{"bundle_key": "w1", "dag": {"nodes": [], "edges": []}}],
    }
    out = preview_import_bundle(bundle, tenant_id="default", user_id="default")
    assert out["ok"] is True
    assert out["summary"]["agents"] == 1
