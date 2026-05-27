"""从工作流 DAG / Agent 配置收集导出依赖 ID。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ExportDependencyIds:
    workflow_ids: set[str] = field(default_factory=set)
    agent_ids: set[str] = field(default_factory=set)
    knowledge_base_ids: set[str] = field(default_factory=set)
    skill_ids: set[str] = field(default_factory=set)
    mcp_server_ids: set[str] = field(default_factory=set)


from core.demos.bundle_refs import IMPORT_REF_PREFIX


def _add_agent_id(target: set[str], value: Any) -> None:
    if isinstance(value, str) and value.strip() and not value.startswith(IMPORT_REF_PREFIX):
        target.add(value.strip())



def collect_ids_from_dag(dag: dict[str, Any], *, workflow_id: Optional[str] = None) -> ExportDependencyIds:
    out = ExportDependencyIds()
    if workflow_id:
        out.workflow_ids.add(workflow_id)
    nodes = dag.get("nodes") if isinstance(dag.get("nodes"), list) else []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        cfg = node.get("config") if isinstance(node.get("config"), dict) else {}
        _add_agent_id(out.agent_ids, cfg.get("agent_id"))
        _add_agent_id(out.agent_ids, cfg.get("fallback_agent_id"))
        tool = cfg.get("tool_name") or cfg.get("skill_id")
        if isinstance(tool, str) and tool.strip() and not tool.startswith("builtin_"):
            out.skill_ids.add(tool.strip())
    gc = dag.get("global_config") if isinstance(dag.get("global_config"), dict) else {}
    refl = gc.get("reflector") if isinstance(gc.get("reflector"), dict) else {}
    _add_agent_id(out.agent_ids, refl.get("fallback_agent_id"))
    return out


def merge_dependency_ids(base: ExportDependencyIds, extra: ExportDependencyIds) -> ExportDependencyIds:
    return ExportDependencyIds(
        workflow_ids=base.workflow_ids | extra.workflow_ids,
        agent_ids=base.agent_ids | extra.agent_ids,
        knowledge_base_ids=base.knowledge_base_ids | extra.knowledge_base_ids,
        skill_ids=base.skill_ids | extra.skill_ids,
        mcp_server_ids=base.mcp_server_ids | extra.mcp_server_ids,
    )
