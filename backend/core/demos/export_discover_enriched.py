"""导出依赖发现（含可勾选展示项）。"""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from core.agent_runtime.definition import get_agent_registry
from core.demos.platform_bundle_export import discover_export_dependencies
from core.knowledge.knowledge_base_store import KnowledgeBaseStore
from core.mcp.persistence import get_mcp_server
from core.skills.store import get_skill_store
from core.workflows.services.workflow_service import WorkflowService


def discover_export_enriched(
    *,
    db: Session,
    workflow_ids: list[str],
    tenant_id: str,
    user_id: str,
    extra_agent_ids: Optional[list[str]] = None,
    extra_kb_ids: Optional[list[str]] = None,
    extra_skill_ids: Optional[list[str]] = None,
    extra_mcp_ids: Optional[list[str]] = None,
) -> dict[str, Any]:
    deps = discover_export_dependencies(
        db=db,
        workflow_ids=workflow_ids,
        tenant_id=tenant_id,
        extra_agent_ids=extra_agent_ids,
        extra_kb_ids=extra_kb_ids,
        extra_skill_ids=extra_skill_ids,
        extra_mcp_ids=extra_mcp_ids,
    )
    items: list[dict[str, Any]] = []
    wf_service = WorkflowService(db)
    for wid in sorted(deps.workflow_ids):
        wf = wf_service.get_workflow(wid, tenant_id=tenant_id)
        items.append(
            {
                "kind": "workflow",
                "id": wid,
                "label": wf.name if wf else wid,
                "selected": True,
            }
        )
    agent_reg = get_agent_registry()
    for aid in sorted(deps.agent_ids):
        a = agent_reg.get_agent(aid)
        items.append(
            {
                "kind": "agent",
                "id": aid,
                "label": a.name if a else aid,
                "selected": True,
            }
        )
    kb_store = KnowledgeBaseStore()
    for kid in sorted(deps.knowledge_base_ids):
        label = kid
        try:
            kb = kb_store.get_knowledge_base(kid, user_id=user_id, tenant_id=tenant_id)
            if kb:
                label = str(kb.get("name") or kid)
        except Exception:
            pass
        items.append({"kind": "knowledge_base", "id": kid, "label": label, "selected": True})
    skill_store = get_skill_store()
    for sid in sorted(deps.skill_ids):
        sk = skill_store.get(sid)
        items.append(
            {
                "kind": "skill",
                "id": sid,
                "label": sk.name if sk else sid,
                "selected": True,
            }
        )
    for mid in sorted(deps.mcp_server_ids):
        row = get_mcp_server(mid, tenant_id=tenant_id)
        items.append(
            {
                "kind": "mcp_server",
                "id": mid,
                "label": str(row.get("name") if row else mid),
                "selected": True,
            }
        )
    return {
        "workflow_ids": sorted(deps.workflow_ids),
        "agent_ids": sorted(deps.agent_ids),
        "knowledge_base_ids": sorted(deps.knowledge_base_ids),
        "skill_ids": sorted(deps.skill_ids),
        "mcp_server_ids": sorted(deps.mcp_server_ids),
        "items": items,
    }
