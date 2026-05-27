"""一键导入目录。"""
from __future__ import annotations

from core.demos.import_catalog import build_import_catalog


def test_import_catalog_has_platform_and_workflow() -> None:
    items = build_import_catalog()
    kinds = {x["kind"] for x in items}
    assert "platform" in kinds
    assert "workflow" in kinds
    assert len(items) >= 4
