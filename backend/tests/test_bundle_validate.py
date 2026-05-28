"""Bundle 校验与类型推断。"""
from __future__ import annotations

import pytest

from core.demos.bundle_validate import bundle_display_id, detect_bundle_kind, validate_bundle


def test_detect_workflow_by_dag() -> None:
    assert detect_bundle_kind({"schema_version": 1, "dag": {"nodes": [], "edges": []}}) == "workflow"


def test_detect_platform_by_agents() -> None:
    assert detect_bundle_kind({"schema_version": 1, "agents": []}) == "platform"


def test_validate_rejects_bad_schema() -> None:
    with pytest.raises(ValueError, match="schema_version"):
        validate_bundle({"dag": {}})


def test_bundle_display_id_prefers_bundle_id() -> None:
    assert bundle_display_id({"bundle_id": "x", "name": "y"}) == "x"


def test_validate_platform_bundle_with_mcp_only() -> None:
    assert (
        validate_bundle(
            {
                "schema_version": 1,
                "bundle_type": "platform",
                "mcp_servers": [{"bundle_key": "mcp1", "name": "MCP"}],
            }
        )
        == "platform"
    )


def test_collect_ids_from_dag() -> None:
    from core.demos.bundle_collect import collect_ids_from_dag

    deps = collect_ids_from_dag(
        {
            "nodes": [
                {"config": {"workflow_node_type": "agent", "agent_id": "agent-1"}},
                {"config": {"tool_name": "custom.skill"}},
            ]
        },
        workflow_id="wf-1",
    )
    assert deps.workflow_ids == {"wf-1"}
    assert deps.agent_ids == {"agent-1"}
    assert "custom.skill" in deps.skill_ids
