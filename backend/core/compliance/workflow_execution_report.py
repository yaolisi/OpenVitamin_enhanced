"""
工作流执行合规留痕报告（结构化 JSON，供导出与归档）。
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from core.security.audit_service import query_audit_logs
from core.workflows.repository import WorkflowApprovalTaskRepository, WorkflowExecutionRepository
from core.workflows.services.workflow_execution_service import WorkflowExecutionService


def build_workflow_execution_compliance_report(
    db: Session,
    *,
    workflow_id: str,
    execution_id: str,
    tenant_id: str,
) -> Dict[str, Any]:
    exec_svc = WorkflowExecutionService(db)
    execution = exec_svc.get_execution(execution_id, tenant_id=tenant_id)
    if execution is None or execution.workflow_id != workflow_id:
        raise LookupError("execution_not_found")

    approval_repo = WorkflowApprovalTaskRepository(db)
    approvals = approval_repo.list_by_execution(execution_id, tenant_id)

    global_ctx = dict(execution.global_context or {})
    correlation_id = str(global_ctx.get("correlation_id") or "").strip()
    orchestrator = str(global_ctx.get("orchestrator_agent_id") or "").strip()

    nodes_summary: List[Dict[str, Any]] = []
    for ns in execution.node_states or []:
        state_val = getattr(ns, "state", None)
        nodes_summary.append(
            {
                "node_id": getattr(ns, "node_id", None),
                "status": state_val.value if hasattr(state_val, "value") else str(state_val),
                "started_at": (
                    ns.started_at.isoformat() if getattr(ns, "started_at", None) else None
                ),
                "finished_at": (
                    ns.finished_at.isoformat() if getattr(ns, "finished_at", None) else None
                ),
                "error_message": getattr(ns, "error_message", None),
            }
        )

    audit_items, audit_total = query_audit_logs(
        db,
        tenant_id=tenant_id,
        limit=50,
        offset=0,
        path_prefix=f"/api/v1/workflows/{workflow_id}",
        since=None,
    )
    audit_filtered = [
        x
        for x in audit_items
        if correlation_id
        and (
            correlation_id in json.dumps(x.get("detail") or {}, ensure_ascii=False)
            or execution_id in (x.get("path") or "")
        )
    ][:20]

    return {
        "schema_version": 1,
        "report_type": "workflow_execution_compliance",
        "generated_at": datetime.now(UTC).isoformat(),
        "tenant_id": tenant_id,
        "workflow_id": workflow_id,
        "execution_id": execution_id,
        "execution": {
            "state": execution.state.value if hasattr(execution.state, "value") else str(execution.state),
            "version_id": execution.version_id,
            "trigger_type": execution.trigger_type,
            "created_at": execution.created_at.isoformat() if execution.created_at else None,
            "started_at": execution.started_at.isoformat() if execution.started_at else None,
            "finished_at": execution.finished_at.isoformat() if execution.finished_at else None,
            "duration_ms": execution.duration_ms,
            "error_message": execution.error_message,
        },
        "collaboration": {
            "correlation_id": correlation_id or None,
            "orchestrator_agent_id": orchestrator or None,
        },
        "input_data": execution.input_data or {},
        "output_data": execution.output_data or {},
        "approval_tasks": [
            {
                "id": t.id,
                "node_id": t.node_id,
                "status": t.status,
                "decided_by": getattr(t, "decided_by", None),
                "created_at": t.created_at.isoformat() if getattr(t, "created_at", None) else None,
            }
            for t in approvals
        ],
        "node_timeline": nodes_summary,
        "audit_excerpt": {
            "total_matched_workflow_prefix": audit_total,
            "items": audit_filtered,
        },
        "disclaimer": "本报告为平台执行留痕摘要，不构成等保/密评合格证明。",
    }
