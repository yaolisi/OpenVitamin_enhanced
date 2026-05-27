"""导出工作流 bundle（仅 DAG）。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy.orm import Session

from core.workflows.services.workflow_service import WorkflowService
from core.workflows.services.workflow_version_service import WorkflowVersionService


@dataclass
class WorkflowBundleExportResult:
    bundle: dict[str, Any]
    warnings: list[str] = field(default_factory=list)


def export_workflow_bundle(
    *,
    db: Session,
    tenant_id: str,
    bundle_id: str,
    name: str,
    description: str = "",
    workflow_id: str,
) -> WorkflowBundleExportResult:
    warnings: list[str] = []
    wf_service = WorkflowService(db)
    ver_service = WorkflowVersionService(db)
    wf = wf_service.get_workflow(workflow_id, tenant_id=tenant_id)
    if not wf:
        raise ValueError(f"Workflow not found: {workflow_id}")
    if not wf.latest_version_id:
        raise ValueError(f"Workflow has no version: {workflow_id}")
    ver = ver_service.get_version(wf.latest_version_id)
    if not ver or not ver.dag:
        raise ValueError(f"Workflow version has no DAG: {workflow_id}")
    meta = wf.metadata if isinstance(getattr(wf, "metadata", None), dict) else {}
    bundle: dict[str, Any] = {
        "schema_version": 1,
        "bundle_type": "workflow",
        "bundle_id": bundle_id,
        "name": name,
        "workflow_name": wf.name,
        "description": description or (wf.description or ""),
        "tags": list(wf.tags) if getattr(wf, "tags", None) else [],
        "dag": ver.dag.model_dump(mode="json"),
    }
    if isinstance(meta.get("sample_input"), dict):
        bundle["sample_input"] = meta["sample_input"]
    if meta.get("recommended_platform_bundle_id"):
        bundle["recommended_platform_bundle_id"] = meta["recommended_platform_bundle_id"]
    else:
        warnings.append(
            "Agent/KB bindings use live IDs in DAG; for portable multi-agent env use platform export"
        )
    return WorkflowBundleExportResult(bundle=bundle, warnings=warnings)
