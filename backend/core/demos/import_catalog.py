"""一键导入：统一目录（平台包 + 工作流包）。"""
from __future__ import annotations

from typing import Any, Literal

from core.demos.bundle_registry import list_platform_bundle_manifests
from core.demos.workflow_bundle_registry import list_workflow_bundle_manifests

ImportKind = Literal["platform", "workflow"]


def build_import_catalog() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for row in list_platform_bundle_manifests():
        items.append(
            {
                "kind": "platform",
                "bundle_id": row["bundle_id"],
                "name": row["name"],
                "description": row["description"],
                "schema_version": row.get("schema_version"),
                "includes": ["knowledge_base", "skills", "mcp", "agents", "workflow"],
            }
        )
    for row in list_workflow_bundle_manifests():
        items.append(
            {
                "kind": "workflow",
                "bundle_id": row["bundle_id"],
                "name": row["name"],
                "description": row["description"],
                "schema_version": row.get("schema_version"),
                "recommended_platform_bundle_id": row.get("recommended_platform_bundle_id"),
                "canvas_mode": row.get("canvas_mode"),
                "includes": ["workflow"],
            }
        )
    return items
