"""
运行前预检 API（平台易用性 / 生产门禁辅助）。
"""
from __future__ import annotations

from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.data.base import get_db
from core.preflight.run_preflight import preflight_agent, preflight_workflow
from core.security.deps import require_platform_write

router = APIRouter(prefix="/api/v1/preflight", tags=["preflight"])


class PreflightCheckItem(BaseModel):
    check: str
    ok: bool
    severity: str = "error"
    hint: Optional[str] = None


class PreflightResponse(BaseModel):
    target: str
    ready: bool
    checks: list[PreflightCheckItem] = Field(default_factory=list)
    agent_id: Optional[str] = None
    workflow_id: Optional[str] = None
    version_id: Optional[str] = None
    tenant_id: Optional[str] = None


@router.get("/agents/{agent_id}", response_model=PreflightResponse)
def get_agent_preflight(
    agent_id: str,
    _role: Annotated[Any, Depends(require_platform_write)],
) -> PreflightResponse:
    result = preflight_agent(agent_id)
    return PreflightResponse(**result)


@router.get("/workflows/{workflow_id}", response_model=PreflightResponse)
def get_workflow_preflight(
    workflow_id: str,
    db: Annotated[Session, Depends(get_db)],
    _role: Annotated[Any, Depends(require_platform_write)],
    version_id: Optional[str] = Query(default=None),
) -> PreflightResponse:
    result = preflight_workflow(workflow_id, version_id=version_id, db=db)
    return PreflightResponse(**result)
