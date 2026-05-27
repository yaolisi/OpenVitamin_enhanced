"""
企业能力：能力探测、合规报告导出。
"""
from __future__ import annotations

import json
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.compliance.pdf_report import render_compliance_pdf
from core.compliance.workflow_execution_report import build_workflow_execution_compliance_report
from core.enterprise.capabilities import build_enterprise_capabilities
from core.workflows.publish_gate import evaluate_publish_gate
from core.data.base import get_db
from core.security.deps import require_audit_reader
from core.utils.tenant_request import resolve_api_tenant_id

router = APIRouter(prefix="/api/v1/enterprise", tags=["enterprise"])


class ProductionReadinessCheck(BaseModel):
    id: str
    label: str
    status: str
    hint: Optional[str] = None


class ProductionReadiness(BaseModel):
    score: int
    total: int
    percent: float
    checks: List[ProductionReadinessCheck] = Field(default_factory=list)


class EnterpriseCapabilitiesResponse(BaseModel):
    oidc_enabled: bool
    oidc_configured: bool = False
    oidc_issuer: Optional[str] = None
    secret_resolver_mode: str
    otel_enabled: bool
    otel_exporter_configured: bool
    otel_ready: bool = False
    ha_profile: str
    prometheus_enabled: bool
    audit_log_enabled: bool
    rbac_enabled: bool = False
    tenant_enforcement_enabled: bool
    identity_boundary_ready: bool = False
    production_readiness: Optional[ProductionReadiness] = None


@router.get("/capabilities", response_model=EnterpriseCapabilitiesResponse)
def get_enterprise_capabilities() -> EnterpriseCapabilitiesResponse:
    return EnterpriseCapabilitiesResponse(**build_enterprise_capabilities())


class ComplianceReportMeta(BaseModel):
    workflow_id: str
    execution_id: str
    format: str = Field(default="json")


@router.get(
    "/compliance/reports/workflow/{workflow_id}/executions/{execution_id}",
    summary="导出工作流执行合规留痕报告（JSON）",
)
def export_workflow_execution_compliance_report(
    workflow_id: str,
    execution_id: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    _role: Annotated[Any, Depends(require_audit_reader)],
    download: bool = False,
) -> Response:
    tenant_id = resolve_api_tenant_id(request)
    try:
        report = build_workflow_execution_compliance_report(
            db,
            workflow_id=workflow_id,
            execution_id=execution_id,
            tenant_id=tenant_id,
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="execution_not_found") from None

    body = json.dumps(report, ensure_ascii=False, indent=2)
    if download:
        filename = f"compliance-wf-{workflow_id[:8]}-ex-{execution_id[:8]}.json"
        return Response(
            content=body,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    return JSONResponse(content=report)


@router.get(
    "/compliance/reports/workflow/{workflow_id}/executions/{execution_id}/pdf",
    summary="导出合规留痕 PDF",
)
def export_workflow_compliance_pdf(
    workflow_id: str,
    execution_id: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    _role: Annotated[Any, Depends(require_audit_reader)],
) -> Response:
    tenant_id = resolve_api_tenant_id(request)
    try:
        report = build_workflow_execution_compliance_report(
            db,
            workflow_id=workflow_id,
            execution_id=execution_id,
            tenant_id=tenant_id,
        )
        pdf_bytes = render_compliance_pdf(report)
    except LookupError:
        raise HTTPException(status_code=404, detail="execution_not_found") from None
    except RuntimeError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc

    filename = f"compliance-wf-{workflow_id[:8]}-ex-{execution_id[:8]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


class PublishGateResponse(BaseModel):
    model_config = {"extra": "allow"}


@router.get(
    "/workflows/{workflow_id}/versions/{version_id}/publish-gate",
    response_model=PublishGateResponse,
    summary="发布门禁评估（预检 + 契约 diff）",
)
def get_workflow_publish_gate(
    workflow_id: str,
    version_id: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    _role: Annotated[Any, Depends(require_audit_reader)],
) -> PublishGateResponse:
    tenant_id = resolve_api_tenant_id(request)
    result = evaluate_publish_gate(
        db,
        workflow_id=workflow_id,
        version_id=version_id,
        tenant_id=tenant_id,
    )
    return PublishGateResponse(**result)
