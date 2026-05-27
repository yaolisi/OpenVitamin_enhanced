"""演示包 API：一键导入 Agent + 知识库 + 工作流。"""
from __future__ import annotations

from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.errors import raise_api_error
from core.data.base import get_db
from core.demos.bundle_registry import list_platform_bundle_manifests, load_platform_bundle
from core.demos.platform_bundle_import import import_platform_bundle
from core.security.deps import require_platform_write
from core.utils.tenant_request import get_effective_tenant_id
from core.utils.user_context import get_user_id

router = APIRouter(prefix="/api/v1/demos", tags=["demos"])


class PlatformBundleManifest(BaseModel):
    bundle_id: str
    name: str
    description: str = ""
    schema_version: Optional[int] = None


class PlatformBundleListResponse(BaseModel):
    items: list[PlatformBundleManifest]


class PlatformBundleImportRequest(BaseModel):
    publish_workflows: bool = False
    wait_document_index: bool = True
    namespace: Optional[str] = Field(default=None, description="默认与当前租户一致")


class PlatformBundleImportResponse(BaseModel):
    bundle_id: str
    knowledge_bases: dict[str, str]
    skills: dict[str, str] = Field(default_factory=dict)
    mcp_servers: dict[str, str] = Field(default_factory=dict)
    mcp_skills_imported: list[str] = Field(default_factory=list)
    agents: dict[str, str]
    workflows: dict[str, str]
    workflow_versions: dict[str, str]
    published: dict[str, bool]
    documents_indexed: list[str]
    warnings: list[str]
    edit_url_hints: dict[str, str] = Field(default_factory=dict)
    run_url_hints: dict[str, str] = Field(default_factory=dict)
    knowledge_url_hints: dict[str, str] = Field(default_factory=dict)
    agents_url_hints: dict[str, str] = Field(default_factory=dict)
    skills_url_hints: dict[str, str] = Field(default_factory=dict)
    mcp_url_hints: dict[str, str] = Field(default_factory=dict)


@router.get("/platform-bundles", response_model=PlatformBundleListResponse)
async def list_platform_bundles() -> PlatformBundleListResponse:
    items = [PlatformBundleManifest.model_validate(x) for x in list_platform_bundle_manifests()]
    return PlatformBundleListResponse(items=items)


@router.post(
    "/platform-bundles/{bundle_id}/import",
    response_model=PlatformBundleImportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def import_platform_bundle_by_id(
    bundle_id: str,
    body: PlatformBundleImportRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    _role: Annotated[Any, Depends(require_platform_write)],
) -> PlatformBundleImportResponse:
    try:
        bundle, bundle_dir = load_platform_bundle(bundle_id)
    except FileNotFoundError:
        raise_api_error(
            status_code=404,
            code="platform_bundle_not_found",
            message=f"Platform bundle not found: {bundle_id}",
        )
    user_id = get_user_id(request)
    tenant_id = get_effective_tenant_id(request)
    wait_index = body.wait_document_index
    try:
        result = import_platform_bundle(
            bundle,
            bundle_dir=bundle_dir,
            db=db,
            user_id=user_id,
            tenant_id=tenant_id,
            namespace=body.namespace or tenant_id,
            publish_workflows=body.publish_workflows,
            wait_document_index=wait_index,
        )
    except ValueError as exc:
        raise_api_error(
            status_code=400,
            code="platform_bundle_import_invalid",
            message=str(exc),
        )
    except Exception as exc:
        raise_api_error(
            status_code=500,
            code="platform_bundle_import_failed",
            message=str(exc),
        )

    wf_hints = {k: f"/workflow/{vid}/edit" for k, vid in result.workflows.items()}
    run_hints = {k: f"/workflow/{vid}/run" for k, vid in result.workflows.items()}
    kb_hints = {k: f"/knowledge/{kid}" for k, kid in result.knowledge_bases.items()}
    agent_hints = {k: f"/agents/{aid}/edit" for k, aid in result.agents.items()}
    skill_hints = {k: f"/skills/{sid}" for k, sid in result.skills.items()}
    mcp_hints = {k: "/settings/mcp" for k in result.mcp_servers}
    payload = result.to_dict()
    payload["edit_url_hints"] = wf_hints
    payload["run_url_hints"] = run_hints
    payload["knowledge_url_hints"] = kb_hints
    payload["agents_url_hints"] = agent_hints
    payload["skills_url_hints"] = skill_hints
    payload["mcp_url_hints"] = mcp_hints
    return PlatformBundleImportResponse.model_validate(payload)
