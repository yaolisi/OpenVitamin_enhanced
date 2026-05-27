"""
工作流发布门禁：预检 + 契约 diff + 子流程影响（发布前只读评估）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from config.settings import settings
from core.preflight.run_preflight import preflight_workflow
from core.workflows.repository import WorkflowVersionRepository
from core.workflows.services.workflow_version_service import WorkflowVersionService


def evaluate_publish_gate(
    db: Session,
    *,
    workflow_id: str,
    version_id: str,
    tenant_id: str,
) -> Dict[str, Any]:
    issues: List[Dict[str, Any]] = []

    preflight = preflight_workflow(
        workflow_id,
        version_id=version_id,
        tenant_id=tenant_id,
        db=db,
    )
    if not preflight.get("ready"):
        for c in preflight.get("checks") or []:
            if not c.get("ok") and c.get("severity") == "error":
                issues.append(
                    {
                        "code": "preflight_failed",
                        "check": c.get("check"),
                        "hint": c.get("hint"),
                    }
                )

    ver_repo = WorkflowVersionRepository(db)
    version = ver_repo.get_version_by_id(version_id)
    if version is None or version.workflow_id != workflow_id:
        return {
            "allowed": False,
            "workflow_id": workflow_id,
            "version_id": version_id,
            "issues": [{"code": "version_not_found"}],
            "preflight": preflight,
            "contract_diff": None,
            "impact": None,
        }

    version_service = WorkflowVersionService(db)
    published = ver_repo.get_published_version(workflow_id)
    baseline_id = published.version_id if published and published.version_id != version_id else None

    impact = version_service.analyze_subworkflow_impact(
        target_workflow_id=workflow_id,
        target_version_id=version_id,
        include_only_published=True,
        baseline_version_id=baseline_id,
    )
    contract_diff = impact.get("contract_diff") or {}
    breaking_changes = list(contract_diff.get("breaking_changes") or [])
    risky_changes = list(contract_diff.get("risky_changes") or [])

    if breaking_changes:
        issues.append(
            {
                "code": "contract_breaking",
                "count": len(breaking_changes),
                "items": breaking_changes[:10],
            }
        )

    breaking_impact = int((impact.get("risk_summary") or {}).get("breaking") or 0)
    if breaking_impact > 0 and bool(
        getattr(settings, "workflow_block_publish_on_subworkflow_breaking_impact", True)
    ):
        issues.append(
            {
                "code": "subworkflow_breaking_impact",
                "count": breaking_impact,
            }
        )

    allowed = len(issues) == 0
    return {
        "allowed": allowed,
        "workflow_id": workflow_id,
        "version_id": version_id,
        "baseline_version_id": baseline_id,
        "preflight": preflight,
        "contract_diff": contract_diff,
        "risky_change_count": len(risky_changes),
        "impact_summary": impact.get("risk_summary"),
        "impacted_count": impact.get("total_impacted"),
        "issues": issues,
    }
