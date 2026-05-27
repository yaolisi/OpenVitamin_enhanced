"""一键导入 / 导出：内置 catalog、JSON/ZIP 上传、环境导出。"""
from __future__ import annotations

from typing import Annotated, Any, Literal, Optional

from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.demos import PlatformBundleImportResponse
from api.errors import raise_api_error
from core.data.base import get_db
from core.demos.bundle_validate import ImportKind, bundle_display_id, validate_bundle
from core.demos.bundle_zip import pack_bundle_zip
from core.demos.import_catalog import build_import_catalog
from core.demos.import_runner import (
    UPLOAD_BUNDLE_DIR,
    execute_catalog_import,
    execute_upload_import,
    parse_upload_bytes,
)
from core.demos.platform_bundle_export import discover_export_dependencies, export_platform_bundle
from core.demos.platform_bundle_import import PlatformBundleImportResult
from core.demos.workflow_bundle_export import export_workflow_bundle
from core.demos.workflow_bundle_import import WorkflowBundleImportResult
from core.security.deps import require_platform_write
from core.utils.tenant_request import get_effective_tenant_id
from core.utils.user_context import get_user_id

router = APIRouter(prefix="/api/v1/import", tags=["import"])


class ImportCatalogItem(BaseModel):
    kind: Literal["platform", "workflow"]
    bundle_id: str
    name: str
    description: str = ""
    schema_version: Optional[int] = None
    includes: list[str] = Field(default_factory=list)
    recommended_platform_bundle_id: Optional[str] = None
    canvas_mode: Optional[str] = None


class ImportCatalogResponse(BaseModel):
    items: list[ImportCatalogItem]


class ImportRunRequest(BaseModel):
    kind: Literal["platform", "workflow"]
    bundle_id: str = Field(..., min_length=1)
    publish_workflows: bool = False
    wait_document_index: bool = True
    namespace: Optional[str] = None


class ImportRunBodyRequest(BaseModel):
    bundle: dict[str, Any]
    kind: Optional[Literal["platform", "workflow"]] = None
    publish_workflows: bool = False
    wait_document_index: bool = True
    namespace: Optional[str] = None


class ImportValidateRequest(BaseModel):
    bundle: dict[str, Any]
    kind: Optional[Literal["platform", "workflow"]] = None


class ImportValidateResponse(BaseModel):
    ok: bool
    kind: Optional[ImportKind] = None
    bundle_id: Optional[str] = None
    message: Optional[str] = None


class ExportDiscoverRequest(BaseModel):
    workflow_ids: list[str] = Field(..., min_length=1)
    agent_ids: list[str] = Field(default_factory=list)
    knowledge_base_ids: list[str] = Field(default_factory=list)
    skill_ids: list[str] = Field(default_factory=list)
    mcp_server_ids: list[str] = Field(default_factory=list)


class ExportDiscoverResponse(BaseModel):
    workflow_ids: list[str]
    agent_ids: list[str]
    knowledge_base_ids: list[str]
    skill_ids: list[str]
    mcp_server_ids: list[str]


class ExportBundleRequest(BaseModel):
    kind: Literal["platform", "workflow"] = "platform"
    format: Literal["json", "zip"] = "zip"
    bundle_id: str = Field(..., min_length=1, max_length=128)
    name: str = Field(..., min_length=1, max_length=256)
    description: str = ""
    workflow_ids: list[str] = Field(..., min_length=1)
    agent_ids: list[str] = Field(default_factory=list)
    knowledge_base_ids: list[str] = Field(default_factory=list)
    skill_ids: list[str] = Field(default_factory=list)
    mcp_server_ids: list[str] = Field(default_factory=list)
    use_model_placeholders: bool = True
    include_documents: bool = True
    export_mcp_tool_imports: bool = True


class ExportBundleJsonResponse(BaseModel):
    kind: ImportKind
    bundle_id: str
    filename: str
    bundle: dict[str, Any]
    warnings: list[str] = Field(default_factory=list)


class ImportRunResponse(BaseModel):
    kind: str
    bundle_id: str
    platform: Optional[PlatformBundleImportResponse] = None
    workflow_id: Optional[str] = None
    version_id: Optional[str] = None
    published: bool = False
    sample_input: Optional[dict[str, Any]] = None
    warnings: list[str] = Field(default_factory=list)
    edit_url_hint: Optional[str] = None
    run_url_hint: Optional[str] = None
    knowledge_url_hints: dict[str, str] = Field(default_factory=dict)
    agents_url_hints: dict[str, str] = Field(default_factory=dict)
    skills_url_hints: dict[str, str] = Field(default_factory=dict)
    mcp_url_hints: dict[str, str] = Field(default_factory=dict)


def _platform_response(bundle_id: str, result: PlatformBundleImportResult) -> ImportRunResponse:
    wf_key = next(iter(result.workflows), None)
    wf_id = result.workflows.get(wf_key) if wf_key else None
    payload = result.to_dict()
    payload["edit_url_hints"] = {k: f"/workflow/{vid}/edit" for k, vid in result.workflows.items()}
    payload["run_url_hints"] = {k: f"/workflow/{vid}/run" for k, vid in result.workflows.items()}
    payload["knowledge_url_hints"] = {k: f"/knowledge/{kid}" for k, kid in result.knowledge_bases.items()}
    payload["agents_url_hints"] = {k: f"/agents/{aid}/edit" for k, aid in result.agents.items()}
    payload["skills_url_hints"] = {k: f"/skills/{sid}" for k, sid in result.skills.items()}
    payload["mcp_url_hints"] = {k: "/settings/mcp" for k in result.mcp_servers}
    platform_resp = PlatformBundleImportResponse.model_validate(payload)
    return ImportRunResponse(
        kind="platform",
        bundle_id=bundle_id,
        platform=platform_resp,
        workflow_id=wf_id,
        version_id=result.workflow_versions.get(wf_key) if wf_key else None,
        published=bool(result.published.get(wf_key)) if wf_key else False,
        sample_input=None,
        warnings=result.warnings,
        edit_url_hint=f"/workflow/{wf_id}/edit" if wf_id else None,
        run_url_hint=f"/workflow/{wf_id}/run" if wf_id else None,
        knowledge_url_hints=payload["knowledge_url_hints"],
        agents_url_hints=payload["agents_url_hints"],
        skills_url_hints=payload["skills_url_hints"],
        mcp_url_hints=payload["mcp_url_hints"],
    )


def _workflow_response(bundle_id: str, wf_result: WorkflowBundleImportResult) -> ImportRunResponse:
    return ImportRunResponse(
        kind="workflow",
        bundle_id=bundle_id,
        workflow_id=wf_result.workflow_id,
        version_id=wf_result.version_id,
        published=wf_result.published,
        sample_input=wf_result.sample_input,
        warnings=wf_result.warnings,
        edit_url_hint=f"/workflow/{wf_result.workflow_id}/edit",
        run_url_hint=f"/workflow/{wf_result.workflow_id}/run",
    )


def _result_to_response(bundle_id: str, result: PlatformBundleImportResult | WorkflowBundleImportResult) -> ImportRunResponse:
    if isinstance(result, PlatformBundleImportResult):
        return _platform_response(bundle_id, result)
    return _workflow_response(bundle_id, result)


def _run_import_common(
    *,
    bundle_id: str,
    result: PlatformBundleImportResult | WorkflowBundleImportResult,
) -> ImportRunResponse:
    return _result_to_response(bundle_id, result)


@router.get("/catalog", response_model=ImportCatalogResponse)
async def get_import_catalog() -> ImportCatalogResponse:
    items = [ImportCatalogItem.model_validate(x) for x in build_import_catalog()]
    return ImportCatalogResponse(items=items)


@router.post("/validate", response_model=ImportValidateResponse)
async def validate_import_bundle(
    body: ImportValidateRequest,
    _role: Annotated[Any, Depends(require_platform_write)],
) -> ImportValidateResponse:
    try:
        kind = validate_bundle(body.bundle, kind=body.kind)
        return ImportValidateResponse(
            ok=True,
            kind=kind,
            bundle_id=bundle_display_id(body.bundle),
        )
    except ValueError as exc:
        return ImportValidateResponse(ok=False, message=str(exc))


@router.post("/run", response_model=ImportRunResponse, status_code=status.HTTP_201_CREATED)
async def run_one_click_import(
    body: ImportRunRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    _role: Annotated[Any, Depends(require_platform_write)],
) -> ImportRunResponse:
    user_id = get_user_id(request)
    tenant_id = get_effective_tenant_id(request)
    ns = body.namespace or tenant_id
    try:
        result = execute_catalog_import(
            kind=body.kind,
            bundle_id=body.bundle_id,
            db=db,
            user_id=user_id,
            tenant_id=tenant_id,
            namespace=ns,
            publish_workflows=body.publish_workflows,
            wait_document_index=body.wait_document_index,
        )
    except FileNotFoundError:
        raise_api_error(
            status_code=404,
            code="import_bundle_not_found",
            message=f"Bundle not found: {body.bundle_id}",
        )
    except ValueError as exc:
        raise_api_error(status_code=400, code="import_invalid", message=str(exc))
    except Exception as exc:
        raise_api_error(status_code=500, code="import_failed", message=str(exc))
    return _run_import_common(bundle_id=body.bundle_id, result=result)


@router.post("/run-body", response_model=ImportRunResponse, status_code=status.HTTP_201_CREATED)
async def run_import_from_body(
    body: ImportRunBodyRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    _role: Annotated[Any, Depends(require_platform_write)],
) -> ImportRunResponse:
    user_id = get_user_id(request)
    tenant_id = get_effective_tenant_id(request)
    ns = body.namespace or tenant_id
    bid = bundle_display_id(body.bundle)
    try:
        result = execute_upload_import(
            body.bundle,
            bundle_dir=UPLOAD_BUNDLE_DIR,
            kind=body.kind,
            db=db,
            user_id=user_id,
            tenant_id=tenant_id,
            namespace=ns,
            publish_workflows=body.publish_workflows,
            wait_document_index=body.wait_document_index,
        )
    except ValueError as exc:
        raise_api_error(status_code=400, code="import_invalid", message=str(exc))
    except Exception as exc:
        raise_api_error(status_code=500, code="import_failed", message=str(exc))
    return _run_import_common(bundle_id=bid, result=result)


@router.post("/upload", response_model=ImportRunResponse, status_code=status.HTTP_201_CREATED)
async def upload_and_import_bundle(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    _role: Annotated[Any, Depends(require_platform_write)],
    file: UploadFile = File(...),
    kind: Optional[Literal["platform", "workflow"]] = Form(default=None),
    publish_workflows: bool = Form(default=False),
    wait_document_index: bool = Form(default=True),
    namespace: Optional[str] = Form(default=None),
) -> ImportRunResponse:
    raw = await file.read()
    if not raw:
        raise_api_error(status_code=400, code="import_invalid", message="Empty file")
    user_id = get_user_id(request)
    tenant_id = get_effective_tenant_id(request)
    ns = namespace or tenant_id
    try:
        bundle, bundle_dir, parse_warnings = parse_upload_bytes(raw, filename=file.filename or "")
    except ValueError as exc:
        raise_api_error(status_code=400, code="import_invalid", message=str(exc))
    bid = bundle_display_id(bundle)
    try:
        result = execute_upload_import(
            bundle,
            bundle_dir=bundle_dir,
            kind=kind,
            db=db,
            user_id=user_id,
            tenant_id=tenant_id,
            namespace=ns,
            publish_workflows=publish_workflows,
            wait_document_index=wait_document_index,
            extra_warnings=parse_warnings,
        )
    except ValueError as exc:
        raise_api_error(status_code=400, code="import_invalid", message=str(exc))
    except Exception as exc:
        raise_api_error(status_code=500, code="import_failed", message=str(exc))
    return _run_import_common(bundle_id=bid, result=result)


@router.post(
    "/export/discover",
    response_model=ExportDiscoverResponse,
    summary="发现工作流导出依赖",
    description="根据 workflow_ids 扫描 DAG 与 Agent，返回建议一并导出的 Agent/KB/Skill/MCP ID。OpenAPI: Import → export/discover",
)
async def discover_bundle_export(
    body: ExportDiscoverRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    _role: Annotated[Any, Depends(require_platform_write)],
) -> ExportDiscoverResponse:
    tenant_id = get_effective_tenant_id(request)
    deps = discover_export_dependencies(
        db=db,
        workflow_ids=body.workflow_ids,
        tenant_id=tenant_id,
        extra_agent_ids=body.agent_ids,
        extra_kb_ids=body.knowledge_base_ids,
        extra_skill_ids=body.skill_ids,
        extra_mcp_ids=body.mcp_server_ids,
    )
    return ExportDiscoverResponse(
        workflow_ids=sorted(deps.workflow_ids),
        agent_ids=sorted(deps.agent_ids),
        knowledge_base_ids=sorted(deps.knowledge_base_ids),
        skill_ids=sorted(deps.skill_ids),
        mcp_server_ids=sorted(deps.mcp_server_ids),
    )


@router.post(
    "/export",
    summary="导出环境为 bundle（JSON 或 ZIP）",
    description=(
        "从当前租户环境导出平台包或工作流包。ZIP 格式包含 manifest JSON 与 documents/ 目录。"
        "需要 operator+ 权限。OpenAPI: Import → export"
    ),
    responses={
        200: {
            "description": "format=json 时返回 ExportBundleJsonResponse；format=zip 时返回 application/zip",
            "content": {
                "application/json": {"schema": {"$ref": "#/components/schemas/ExportBundleJsonResponse"}},
                "application/zip": {"schema": {"type": "string", "format": "binary"}},
            },
        }
    },
)
async def export_environment_bundle(
    body: ExportBundleRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    _role: Annotated[Any, Depends(require_platform_write)],
    download: bool = Query(False, description="为 true 时设置 Content-Disposition 附件下载"),
):
    user_id = get_user_id(request)
    tenant_id = get_effective_tenant_id(request)
    sidecar_files: dict[str, bytes] = {}
    try:
        if body.kind == "workflow":
            if len(body.workflow_ids) != 1:
                raise ValueError("Workflow export supports exactly one workflow_id")
            wf_result = export_workflow_bundle(
                db=db,
                tenant_id=tenant_id,
                bundle_id=body.bundle_id,
                name=body.name,
                description=body.description,
                workflow_id=body.workflow_ids[0],
            )
            bundle = wf_result.bundle
            warnings = wf_result.warnings
            kind: ImportKind = "workflow"
        else:
            pf_result = export_platform_bundle(
                db=db,
                user_id=user_id,
                tenant_id=tenant_id,
                bundle_id=body.bundle_id,
                name=body.name,
                description=body.description,
                workflow_ids=body.workflow_ids,
                agent_ids=body.agent_ids,
                knowledge_base_ids=body.knowledge_base_ids,
                skill_ids=body.skill_ids,
                mcp_server_ids=body.mcp_server_ids,
                use_model_placeholders=body.use_model_placeholders,
                include_documents=body.include_documents,
                export_mcp_tool_imports=body.export_mcp_tool_imports,
            )
            bundle = pf_result.bundle
            warnings = pf_result.warnings
            sidecar_files = pf_result.sidecar_files
            kind = "platform"
    except ValueError as exc:
        raise_api_error(status_code=400, code="export_invalid", message=str(exc))
    except Exception as exc:
        raise_api_error(status_code=500, code="export_failed", message=str(exc))

    if body.format == "zip":
        zip_bytes, _manifest_name = pack_bundle_zip(bundle, kind=kind, sidecar_files=sidecar_files)
        fname = f"{body.bundle_id}.zip"
        headers: dict[str, str] = {}
        if download:
            headers["Content-Disposition"] = f'attachment; filename="{fname}"'
        return Response(content=zip_bytes, media_type="application/zip", headers=headers)

    from core.demos.bundle_zip import pick_manifest_name

    filename = pick_manifest_name(bundle, kind)
    payload = ExportBundleJsonResponse(
        kind=kind,
        bundle_id=body.bundle_id,
        filename=filename,
        bundle=bundle,
        warnings=warnings,
    )
    if download:
        import json as json_mod

        raw = json_mod.dumps(payload.model_dump(), ensure_ascii=False, indent=2).encode("utf-8")
        return Response(
            content=raw,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    return payload
