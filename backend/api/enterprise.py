"""
企业能力：能力探测、合规报告导出。
"""
from __future__ import annotations

import json
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.compliance.pdf_report import render_compliance_pdf
from core.compliance.workflow_execution_report import build_workflow_execution_compliance_report
from core.enterprise.capabilities import build_enterprise_capabilities
from core.enterprise.suite_live import live_probe_headers_from_env
from core.enterprise.suite_benchmark import build_suite_benchmark_report, evaluate_suite_gate
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


class SuiteBenchmarkGateResponse(BaseModel):
    pass_: bool = Field(alias="pass")
    details: List[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


@router.get(
    "/suite-benchmark",
    summary="开箱企业套件自动对标（Phase 0–2 + 成熟商业 PaaS 参考维度）",
)
def get_enterprise_suite_benchmark(
    request: Request,
    phase: str = "all",
    include_live: bool = Query(False, description="对当前请求基址执行 Live 探针"),
) -> Dict[str, Any]:
    """返回验收 checklist 自动探针结果与竞争维度参考分。phase: all | phase0 | phase1 | phase2。"""
    phases = None if phase in ("all", "") else [phase]
    live_url = str(request.base_url).rstrip("/") if include_live else None
    return build_suite_benchmark_report(
        phases=phases,
        live_base_url=live_url,
        live_headers=live_probe_headers_from_env() if live_url else None,
    )


@router.get(
    "/suite-benchmark/gate",
    summary="企业套件自动门禁（自动 P0 探针须全部通过）",
    response_model=SuiteBenchmarkGateResponse,
)
def get_enterprise_suite_benchmark_gate(
    request: Request,
    phase: str = "all",
    include_live: bool = Query(False, description="包含 Live P0 探针"),
) -> SuiteBenchmarkGateResponse:
    live_url = str(request.base_url).rstrip("/") if include_live else None
    ok, payload = evaluate_suite_gate(
        phase=phase,
        live_base_url=live_url,
        live_headers=live_probe_headers_from_env() if live_url else None,
    )
    return SuiteBenchmarkGateResponse(pass_=ok, details=list(payload.get("details") or []))


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
