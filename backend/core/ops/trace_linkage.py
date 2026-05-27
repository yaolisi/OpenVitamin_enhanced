"""
Trace / request_id / correlation_id 串联运维视图（只读聚合）。
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from core.data.models.audit import AuditLogORM
from core.data.models.session import AgentSession as AgentSessionORM


def build_trace_ops_view(
    db: Session,
    *,
    trace_id: Optional[str] = None,
    request_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    tenant_id: str = "default",
    limit: int = 30,
) -> Dict[str, Any]:
    tid = (trace_id or "").strip()
    rid = (request_id or "").strip()
    cid = (correlation_id or "").strip()
    if not tid and not rid and not cid:
        raise ValueError("trace_id, request_id or correlation_id required")

    audit_rows = _query_audit_slice(db, tenant_id=tenant_id, trace_id=tid, request_id=rid, limit=limit)
    agent_sessions = _query_agent_sessions(db, tenant_id=tenant_id, trace_id=tid, correlation_id=cid, limit=limit)

    return {
        "trace_id": tid or None,
        "request_id": rid or None,
        "correlation_id": cid or None,
        "tenant_id": tenant_id,
        "audit_logs": audit_rows,
        "agent_sessions": agent_sessions,
        "hints": {
            "workflow_executions": "按 correlation_id 在工作流运行页 global_context 中检索",
            "agent_trace": "使用 agent_sessions[].session_id 打开 /agents/{id}/trace",
        },
    }


def _query_audit_slice(
    db: Session,
    *,
    tenant_id: str,
    trace_id: str,
    request_id: str,
    limit: int,
) -> List[Dict[str, Any]]:
    q = select(AuditLogORM).where(AuditLogORM.tenant_id == tenant_id)
    if trace_id:
        q = q.where(AuditLogORM.trace_id == trace_id)
    if request_id:
        q = q.where(AuditLogORM.request_id == request_id)
    q = q.order_by(desc(AuditLogORM.created_at)).limit(limit)
    rows = db.execute(q).scalars().all()
    out: List[Dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "id": r.id,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "method": r.method,
                "path": r.path,
                "status_code": r.status_code,
                "trace_id": r.trace_id,
                "request_id": r.request_id,
            }
        )
    return out


def _query_agent_sessions(
    db: Session,
    *,
    tenant_id: str,
    trace_id: str,
    correlation_id: str,
    limit: int,
) -> List[Dict[str, Any]]:
    q = select(AgentSessionORM)
    if hasattr(AgentSessionORM, "tenant_id"):
        q = q.where(AgentSessionORM.tenant_id == tenant_id)
    rows = db.execute(q.order_by(desc(AgentSessionORM.updated_at)).limit(500)).scalars().all()
    out: List[Dict[str, Any]] = []
    for r in rows:
        state_raw = r.state_json if hasattr(r, "state_json") else None
        coll = ""
        tr = getattr(r, "trace_id", None) or ""
        if state_raw:
            try:
                st = json.loads(state_raw) if isinstance(state_raw, str) else state_raw
                collab = (st or {}).get("collaboration") or {}
                coll = str(collab.get("correlation_id") or "")
                tr = tr or str((st or {}).get("trace_id") or "")
            except (json.JSONDecodeError, TypeError):
                pass
        if trace_id and tr != trace_id:
            continue
        if correlation_id and coll != correlation_id:
            continue
        if not trace_id and not correlation_id:
            continue
        out.append(
            {
                "session_id": r.session_id,
                "agent_id": r.agent_id,
                "status": r.status,
                "trace_id": tr or None,
                "correlation_id": coll or None,
                "updated_at": r.updated_at.isoformat() if getattr(r, "updated_at", None) else None,
            }
        )
        if len(out) >= limit:
            break
    return out
