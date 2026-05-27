"""工作流演示 bundle 导入（仅落库工作流 + 版本，不含 Agent/KB）。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from log import logger
from sqlalchemy.orm import Session

from core.demos.workflow_bundle_registry import load_workflow_bundle
from core.workflows.models.workflow import WorkflowCreateRequest
from core.workflows.models.workflow_version import WorkflowDAG
from core.workflows.services.workflow_version_service import WorkflowVersionService
from core.workflows.services.workflow_service import WorkflowService


@dataclass
class WorkflowBundleImportResult:
    bundle_id: str
    workflow_id: str
    version_id: str
    published: bool = False
    sample_input: Optional[dict[str, Any]] = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "workflow_id": self.workflow_id,
            "version_id": self.version_id,
            "published": self.published,
            "sample_input": self.sample_input,
            "warnings": self.warnings,
        }


def import_workflow_bundle(
    bundle_id: str,
    *,
    db: Session,
    user_id: str,
    tenant_id: str,
    namespace: Optional[str] = None,
    publish: bool = False,
) -> WorkflowBundleImportResult:
    bundle = load_workflow_bundle(bundle_id)
    return import_workflow_bundle_data(
        bundle,
        bundle_id=bundle_id,
        db=db,
        user_id=user_id,
        tenant_id=tenant_id,
        namespace=namespace,
        publish=publish,
    )


def import_workflow_bundle_data(
    bundle: dict[str, Any],
    *,
    bundle_id: str,
    db: Session,
    user_id: str,
    tenant_id: str,
    namespace: Optional[str] = None,
    publish: bool = False,
) -> WorkflowBundleImportResult:
    dag = bundle.get("dag")
    if not isinstance(dag, dict):
        raise ValueError("Invalid workflow bundle: missing dag")
    ns = (namespace or tenant_id or "default").strip()
    wf_service = WorkflowService(db)
    ver_service = WorkflowVersionService(db)
    wf_req = WorkflowCreateRequest(
        namespace=ns,
        name=str(bundle.get("workflow_name") or bundle.get("name") or bundle_id),
        description=str(bundle.get("description") or ""),
        tags=list(bundle.get("tags") or ["demo", "workflow-bundle"]),
        metadata={"demo_id": bundle_id, "import_kind": "workflow"},
    )
    workflow = wf_service.create_workflow(wf_req, user_id)
    wf_id = workflow.id
    definition = ver_service.create_definition(
        workflow_id=wf_id,
        description=f"Imported workflow bundle {bundle_id}",
        created_by=user_id,
    )
    version = ver_service.create_version(
        workflow_id=wf_id,
        definition_id=definition.definition_id,
        dag=WorkflowDAG.model_validate(dag),
        description=f"Workflow bundle {bundle_id}",
        created_by=user_id,
    )
    wf_service.repository.update(wf_id, {"latest_version_id": version.version_id}, user_id)
    published = False
    if publish:
        ver_service.publish_version(version.version_id, user_id)
        published = True
    sample = bundle.get("sample_input") if isinstance(bundle.get("sample_input"), dict) else None
    platform_hint = bundle.get("recommended_platform_bundle_id")
    warnings: list[str] = []
    if platform_hint:
        warnings.append(
            f"For full multi-agent setup (Agent/KB/Skill/MCP), import platform bundle: {platform_hint}"
        )
    logger.info("[WorkflowBundle] Imported %s -> workflow %s", bundle_id, wf_id)
    return WorkflowBundleImportResult(
        bundle_id=bundle_id,
        workflow_id=wf_id,
        version_id=version.version_id,
        published=published,
        sample_input=sample,
        warnings=warnings,
    )
