"""运维聚合 API。"""
from __future__ import annotations

from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.data.base import get_db
from core.ops.trace_linkage import build_trace_ops_view
from core.security.deps import require_audit_reader
from core.utils.tenant_request import resolve_api_tenant_id
from starlette.requests import Request

router = APIRouter(prefix="/api/v1/ops", tags=["ops"])


class TraceOpsResponse(BaseModel):
    model_config = {"extra": "allow"}


@router.get("/trace", response_model=TraceOpsResponse)
def get_trace_ops_view(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    _role: Annotated[Any, Depends(require_audit_reader)],
    trace_id: Optional[str] = Query(default=None),
    request_id: Optional[str] = Query(default=None),
    correlation_id: Optional[str] = Query(default=None),
) -> TraceOpsResponse:
    tenant_id = resolve_api_tenant_id(request)
    try:
        payload = build_trace_ops_view(
            db,
            trace_id=trace_id,
            request_id=request_id,
            correlation_id=correlation_id,
            tenant_id=tenant_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return TraceOpsResponse(**payload)
