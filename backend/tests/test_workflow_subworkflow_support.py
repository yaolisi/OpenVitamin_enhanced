from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.workflows.models.workflow_version import (
    WorkflowDAG,
    WorkflowNode,
    WorkflowVersion,
    WorkflowVersionState,
)
from core.workflows.models.workflow_execution import WorkflowExecution, WorkflowExecutionState
from core.workflows.runtime.graph_runtime_adapter import GraphRuntimeAdapter
from core.workflows.runtime.subworkflow import apply_output_mapping, build_child_input
from core.workflows.services.workflow_version_service import WorkflowVersionService
from execution_kernel.engine.context import GraphContext
from api.workflows import _build_execution_call_chain
from config.settings import settings


def _build_version(*, workflow_id: str, version_id: str, nodes: list[WorkflowNode]) -> WorkflowVersion:
    dag = WorkflowDAG(nodes=nodes, edges=[], entry_node=nodes[0].id if nodes else None, global_config={})
    return WorkflowVersion(
        version_id=version_id,
        workflow_id=workflow_id,
        definition_id=f"def-{workflow_id}",
        version_number="1.0.0",
        dag=dag,
        checksum=dag.compute_checksum(),
        state=WorkflowVersionState.PUBLISHED,
    )


def test_graph_runtime_adapter_accepts_sub_workflow_node() -> None:
    sub_node = WorkflowNode(
        id="sub-1",
        type="tool",
        config={
            "workflow_node_type": "sub_workflow",
            "target_workflow_id": "wf-child",
            "target_version_selector": "fixed",
            "target_version": "1.0.0",
        },
    )
    version = _build_version(workflow_id="wf-parent", version_id="v-parent", nodes=[sub_node])
    errors = GraphRuntimeAdapter.validate_compatibility(version)
    assert errors == []


def test_subworkflow_mapping_helpers_support_expression_and_output_mapping() -> None:
    context = GraphContext(
        global_data={"tenant": "t1", "input_data": {"seed": 7}},
        node_outputs={"n1": {"score": 88}},
        current_node_input={"user": {"name": "alice"}, "x": 1},
    )
    child_input = build_child_input(
        input_mapping={
            "name": {"type": "path", "from": "input.user.name"},
            "tenant": "${global.tenant}",
            "score": {"type": "path", "from": "nodes.n1.output.score"},
        },
        context=context,
        node_input={"user": {"name": "alice"}, "x": 1},
    )
    assert child_input == {"name": "alice", "tenant": "t1", "score": 88}

    mapped = apply_output_mapping(
        child_output={"result": {"ok": True}, "score": 90},
        output_mapping={"approved": "output.result.ok", "final_score": "score"},
    )
    assert mapped == {"approved": True, "final_score": 90}


def test_workflow_version_service_detects_subworkflow_cycles() -> None:
    service = WorkflowVersionService(db=None)  # type: ignore[arg-type]
    root_dag = WorkflowDAG(
        nodes=[
            WorkflowNode(
                id="sub-b",
                type="tool",
                config={
                    "workflow_node_type": "sub_workflow",
                    "target_workflow_id": "wf-b",
                    "target_version_selector": "fixed",
                    "target_version_id": "v-b",
                },
            )
        ],
        edges=[],
        entry_node="sub-b",
        global_config={},
    )
    wf_b_version = _build_version(
        workflow_id="wf-b",
        version_id="v-b",
        nodes=[
            WorkflowNode(
                id="sub-a",
                type="tool",
                config={
                    "workflow_node_type": "sub_workflow",
                    "target_workflow_id": "wf-a",
                    "target_version_selector": "fixed",
                    "target_version_id": "v-a",
                },
            )
        ],
    )
    wf_a_version = _build_version(
        workflow_id="wf-a",
        version_id="v-a",
        nodes=root_dag.nodes,
    )

    def _get_version_by_id(version_id: str):
        if version_id == "v-b":
            return wf_b_version
        if version_id == "v-a":
            return wf_a_version
        return None

    service.repository = SimpleNamespace(  # type: ignore[assignment]
        get_version_by_id=_get_version_by_id,
        get_version_by_number=lambda workflow_id, version: None,
        get_published_version=lambda workflow_id: None,
    )

    with pytest.raises(ValueError, match="Sub-workflow cycle detected"):
        service._validate_sub_workflow_cycles("wf-a", "v-a", root_dag)  # noqa: SLF001


def test_workflow_version_service_impact_analysis_marks_fixed_and_latest() -> None:
    service = WorkflowVersionService(db=None)  # type: ignore[arg-type]
    target_version = _build_version(
        workflow_id="wf-target",
        version_id="v-target-1",
        nodes=[WorkflowNode(id="n0", type="tool", config={"tool_name": "builtin_shell.run"})],
    )
    fixed_parent = _build_version(
        workflow_id="wf-parent-fixed",
        version_id="v-parent-fixed",
        nodes=[
            WorkflowNode(
                id="sub-fixed",
                type="tool",
                config={
                    "workflow_node_type": "sub_workflow",
                    "target_workflow_id": "wf-target",
                    "target_version_selector": "fixed",
                    "target_version_id": "v-target-1",
                },
            )
        ],
    )
    latest_parent = _build_version(
        workflow_id="wf-parent-latest",
        version_id="v-parent-latest",
        nodes=[
            WorkflowNode(
                id="sub-latest",
                type="tool",
                config={
                    "workflow_node_type": "sub_workflow",
                    "target_workflow_id": "wf-target",
                    "target_version_selector": "latest",
                },
            )
        ],
    )
    service.repository = SimpleNamespace(  # type: ignore[assignment]
        get_version_by_id=lambda version_id: target_version if version_id == "v-target-1" else None,
        list_versions=lambda state=None, limit=5000, offset=0: [fixed_parent, latest_parent],
        list_versions_by_workflow=lambda workflow_id, state=None, limit=20, offset=0: [],
    )

    impact = service.analyze_subworkflow_impact("wf-target", target_version_id="v-target-1")
    assert impact["total_impacted"] == 2
    kinds = {item["impact_kind"] for item in impact["impacted"]}
    assert kinds == {"fixed_version_match", "latest_reference"}


def test_workflow_version_service_impact_analysis_marks_breaking_when_contract_breaks() -> None:
    service = WorkflowVersionService(db=None)  # type: ignore[arg-type]
    baseline = _build_version(
        workflow_id="wf-target",
        version_id="v-target-base",
        nodes=[WorkflowNode(id="n0", type="tool", config={"tool_name": "builtin_shell.run"})],
    )
    target = _build_version(
        workflow_id="wf-target",
        version_id="v-target-new",
        nodes=[WorkflowNode(id="n0", type="tool", config={"tool_name": "builtin_shell.run"})],
    )
    baseline = baseline.model_copy(
        update={
            "dag": baseline.dag.model_copy(
                update={
                    "global_config": {
                        "input_schema": {
                            "type": "object",
                            "properties": {"name": {"type": "string"}},
                            "required": [],
                        },
                        "output_schema": {
                            "type": "object",
                            "properties": {"ok": {"type": "boolean"}},
                        },
                    }
                }
            )
        }
    )
    target = target.model_copy(
        update={
            "dag": target.dag.model_copy(
                update={
                    "global_config": {
                        "input_schema": {
                            "type": "object",
                            "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
                            "required": ["age"],
                        },
                        "output_schema": {
                            "type": "object",
                            "properties": {},
                        },
                    }
                }
            )
        }
    )
    parent = _build_version(
        workflow_id="wf-parent-fixed",
        version_id="v-parent-fixed",
        nodes=[
            WorkflowNode(
                id="sub-fixed",
                type="tool",
                config={
                    "workflow_node_type": "sub_workflow",
                    "target_workflow_id": "wf-target",
                    "target_version_selector": "fixed",
                    "target_version_id": "v-target-new",
                },
            )
        ],
    )
    def _get_version_by_id(version_id: str):
        if version_id == "v-target-new":
            return target
        if version_id == "v-target-base":
            return baseline
        return None

    service.repository = SimpleNamespace(  # type: ignore[assignment]
        get_version_by_id=_get_version_by_id,
        list_versions=lambda state=None, limit=5000, offset=0: [parent],
        list_versions_by_workflow=lambda workflow_id, state=None, limit=20, offset=0: [target, baseline],
    )

    impact = service.analyze_subworkflow_impact(
        "wf-target",
        target_version_id="v-target-new",
        baseline_version_id="v-target-base",
    )
    assert impact["risk_summary"]["breaking"] == 1
    assert impact["contract_diff"]["breaking_changes"]
    assert impact["impacted"][0]["risk_level"] == "breaking"
    assert "breaking contract changes" in impact["impacted"][0]["impact_reason"]


def test_workflow_version_service_contract_policy_and_exemption_controls_risk() -> None:
    service = WorkflowVersionService(db=None)  # type: ignore[arg-type]
    baseline = _build_version(
        workflow_id="wf-target",
        version_id="v-base",
        nodes=[WorkflowNode(id="n0", type="tool", config={"tool_name": "builtin_shell.run"})],
    )
    target = _build_version(
        workflow_id="wf-target",
        version_id="v-new",
        nodes=[WorkflowNode(id="n0", type="tool", config={"tool_name": "builtin_shell.run"})],
    )
    baseline = baseline.model_copy(
        update={
            "dag": baseline.dag.model_copy(
                update={
                    "global_config": {
                        "input_schema": {
                            "type": "object",
                            "properties": {"name": {"type": "string"}},
                            "required": [],
                        },
                        "output_schema": {
                            "type": "object",
                            "properties": {"ok": {"type": "boolean"}},
                        },
                    }
                }
            )
        }
    )
    target = target.model_copy(
        update={
            "dag": target.dag.model_copy(
                update={
                    "global_config": {
                        "input_schema": {
                            "type": "object",
                            "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
                            "required": ["age"],
                        },
                        "output_schema": {
                            "type": "object",
                            "properties": {"ok": {"type": "boolean"}, "debug": {"type": "string"}},
                        },
                    }
                }
            )
        }
    )
    parent = _build_version(
        workflow_id="wf-parent",
        version_id="v-parent",
        nodes=[
            WorkflowNode(
                id="sub-fixed",
                type="tool",
                config={
                    "workflow_node_type": "sub_workflow",
                    "target_workflow_id": "wf-target",
                    "target_version_selector": "fixed",
                    "target_version_id": "v-new",
                },
            )
        ],
    )
    def _get_version_by_id(version_id: str):
        if version_id == "v-new":
            return target
        if version_id == "v-base":
            return baseline
        return None

    service.repository = SimpleNamespace(  # type: ignore[assignment]
        get_version_by_id=_get_version_by_id,
        list_versions=lambda state=None, limit=5000, offset=0: [parent],
        list_versions_by_workflow=lambda workflow_id, state=None, limit=20, offset=0: [target, baseline],
    )

    old_required_policy = settings.workflow_contract_required_input_added_breaking
    old_output_policy = settings.workflow_contract_output_added_risky
    old_exemptions = settings.workflow_contract_field_exemptions
    try:
        settings.workflow_contract_required_input_added_breaking = False
        settings.workflow_contract_output_added_risky = False
        settings.workflow_contract_field_exemptions = "input.age"
        impact = service.analyze_subworkflow_impact(
            "wf-target",
            target_version_id="v-new",
            baseline_version_id="v-base",
        )
        assert impact["risk_summary"]["breaking"] == 0
        assert impact["risk_summary"]["risky"] == 0
        assert impact["contract_diff"]["info_changes"]
        assert impact["contract_diff"]["policy"]["required_input_added_breaking"] is False
    finally:
        settings.workflow_contract_required_input_added_breaking = old_required_policy
        settings.workflow_contract_output_added_risky = old_output_policy
        settings.workflow_contract_field_exemptions = old_exemptions


def test_build_execution_call_chain_collects_parent_and_child_by_correlation() -> None:
    root = WorkflowExecution(
        execution_id="e-root",
        workflow_id="wf-a",
        version_id="v1",
        state=WorkflowExecutionState.RUNNING,
        global_context={"correlation_id": "cid-1"},
    )
    child = WorkflowExecution(
        execution_id="e-child",
        workflow_id="wf-b",
        version_id="v2",
        state=WorkflowExecutionState.COMPLETED,
        global_context={
            "correlation_id": "cid-1",
            "parent_execution_id": "e-root",
            "parent_node_id": "sub-1",
        },
    )
    other = WorkflowExecution(
        execution_id="e-other",
        workflow_id="wf-c",
        version_id="v3",
        state=WorkflowExecutionState.COMPLETED,
        global_context={"correlation_id": "cid-2"},
    )
    chain = _build_execution_call_chain(root, [other, child, root])
    assert chain["correlation_id"] == "cid-1"
    ids = [item["execution_id"] for item in chain["items"]]
    assert ids == ["e-root", "e-child"]
