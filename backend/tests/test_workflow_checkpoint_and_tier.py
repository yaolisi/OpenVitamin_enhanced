"""Workflow checkpoint 节点与 LLM model_tier 分档路由。"""

from unittest.mock import MagicMock, patch

import pytest

from core.workflows.models.workflow_version import (
    WorkflowDAG,
    WorkflowNode,
    WorkflowVersion,
    WorkflowVersionState,
)
from core.workflows.runtime.graph_runtime_adapter import GraphRuntimeAdapter
from core.workflows.runtime.workflow_runtime import WorkflowRuntime


def _build_version(*, nodes: list[WorkflowNode]) -> WorkflowVersion:
    dag = WorkflowDAG(nodes=nodes, edges=[], entry_node=nodes[0].id if nodes else None, global_config={})
    return WorkflowVersion(
        version_id="v-test",
        workflow_id="wf-test",
        definition_id="def-wf-test",
        version_number="1.0.0",
        dag=dag,
        checksum=dag.compute_checksum(),
        state=WorkflowVersionState.PUBLISHED,
    )


def test_checkpoint_passes_with_required_keys() -> None:
    cfg = {
        "workflow_node_type": "checkpoint",
        "required_keys": ["text", "summary"],
        "forbid_error_key": True,
    }
    out = WorkflowRuntime._handle_checkpoint_node(
        cfg, {"text": "ok", "summary": "done"}
    )
    assert out["passed"] is True
    assert out["type"] == "checkpoint_passed"


def test_checkpoint_fails_when_key_missing() -> None:
    cfg = {"workflow_node_type": "checkpoint", "required_keys": ["text"]}
    out = WorkflowRuntime._handle_checkpoint_node(cfg, {"other": 1})
    assert out["passed"] is False
    assert out["type"] == "checkpoint_failed"
    assert "error" in out


def test_checkpoint_fails_on_upstream_error() -> None:
    cfg = {
        "workflow_node_type": "checkpoint",
        "required_keys": ["text"],
        "forbid_error_key": True,
    }
    out = WorkflowRuntime._handle_checkpoint_node(
        cfg, {"text": "x", "error": "boom"}
    )
    assert out["passed"] is False


def test_graph_runtime_adapter_rejects_checkpoint_without_criteria() -> None:
    node = WorkflowNode(
        id="cp-bad",
        type="tool",
        config={"workflow_node_type": "checkpoint"},
    )
    errors = GraphRuntimeAdapter.validate_compatibility(_build_version(nodes=[node]))
    assert any("Checkpoint node" in e for e in errors)


def test_graph_runtime_adapter_accepts_llm_with_model_tier() -> None:
    node = WorkflowNode(
        id="llm-tier",
        type="llm",
        config={"model_tier": "standard"},
    )
    errors = GraphRuntimeAdapter.validate_compatibility(_build_version(nodes=[node]))
    assert errors == []


def test_resolve_llm_model_uses_tier_when_no_model_id() -> None:
    mock_desc = MagicMock()
    mock_desc.id = "local:fast-model"
    with patch(
        "core.workflows.runtime.workflow_runtime.ModelSelector"
    ) as mock_selector_cls:
        mock_selector_cls.return_value.resolve.return_value = mock_desc
        model, err = WorkflowRuntime._resolve_llm_model({"model_tier": "low"})
    assert err is None
    assert model == "local:fast-model"
    mock_selector_cls.return_value.resolve.assert_called_once_with(model_require="fast")


def test_fork_node_passthrough() -> None:
    from execution_kernel.models.graph_definition import NodeDefinition, NodeType

    node = NodeDefinition(id="f1", type=NodeType.TOOL, config={"workflow_node_type": "fork"})
    out = WorkflowRuntime._handle_fork_node(node, {}, {"task": "x"})
    assert out.get("fork_ready") is True
    assert out.get("task") == "x"


def test_join_node_collects_branches() -> None:
    out = WorkflowRuntime._handle_join_node(
        {"merge_mode": "flat"},
        {"branches": {"a": {"text": "1"}, "b": {"text": "2"}}, "extra": "ok"},
    )
    assert out.get("branch_count") == 2
    assert out.get("join_ready") is True
    assert "branches" in out


def test_graph_runtime_adapter_accepts_fork_join_verify_loop() -> None:
    nodes = [
        WorkflowNode(id="fork-1", type="fork", config={"workflow_node_type": "fork"}),
        WorkflowNode(
            id="join-1",
            type="join",
            config={"workflow_node_type": "join", "dependency_mode": "all"},
        ),
        WorkflowNode(
            id="vl-1",
            type="verify_loop",
            config={
                "workflow_node_type": "verify_loop",
                "max_iterations": 3,
                "required_keys": ["text"],
                "loop_body": {"type": "llm", "model_tier": "standard", "prompt": "hi"},
            },
        ),
    ]
    errors = GraphRuntimeAdapter.validate_compatibility(_build_version(nodes=nodes))
    assert errors == []
