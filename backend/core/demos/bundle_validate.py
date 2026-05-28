"""Bundle JSON 校验与类型推断。"""
from __future__ import annotations

from typing import Any, Literal

ImportKind = Literal["platform", "workflow"]


def detect_bundle_kind(bundle: dict[str, Any]) -> ImportKind:
    explicit = str(bundle.get("bundle_type") or "").strip().lower()
    if explicit == "platform":
        return "platform"
    if explicit in ("workflow", "workflow_canvas"):
        return "workflow"
    if any(
        k in bundle
        for k in ("knowledge_bases", "agents", "mcp_servers", "workflows", "skills", "mcp_tool_imports")
    ):
        return "platform"
    if bundle.get("dag"):
        return "workflow"
    raise ValueError(
        "Cannot detect bundle kind: set bundle_type to 'platform' or 'workflow', "
        "or include dag (workflow) / workflows|agents|knowledge_bases (platform)"
    )


def validate_bundle(bundle: dict[str, Any], *, kind: ImportKind | None = None) -> ImportKind:
    if int(bundle.get("schema_version") or 0) != 1:
        raise ValueError("Unsupported schema_version (expected 1)")
    resolved = kind or detect_bundle_kind(bundle)
    if resolved == "workflow":
        if not isinstance(bundle.get("dag"), dict):
            raise ValueError("Workflow bundle requires object field 'dag'")
    else:
        if not (
            bundle.get("workflows")
            or bundle.get("agents")
            or bundle.get("knowledge_bases")
            or bundle.get("skills")
            or bundle.get("mcp_servers")
            or bundle.get("mcp_tool_imports")
        ):
            raise ValueError(
                "Platform bundle needs at least one of: workflows, agents, knowledge_bases, "
                "skills, mcp_servers, mcp_tool_imports"
            )
    return resolved


def bundle_display_id(bundle: dict[str, Any]) -> str:
    return str(
        bundle.get("bundle_id")
        or bundle.get("demo_id")
        or bundle.get("name")
        or "uploaded-bundle"
    )
