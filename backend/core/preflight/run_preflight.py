"""
运行前预检（Harness 式「Shift-left」门禁的本地等价物）：Agent / Workflow 可运行性检查。

仅读检查，不触发推理、不写库。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from config.settings import settings
from core.agent_runtime.definition import get_agent_registry
from core.models.registry import get_model_registry


def _check(label: str, ok: bool, *, severity: str = "error", hint: str = "") -> Dict[str, Any]:
    return {
        "check": label,
        "ok": ok,
        "severity": severity if not ok else "info",
        "hint": hint or None,
    }


def preflight_agent(agent_id: str, *, tenant_id: str = "default") -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []
    registry = get_agent_registry()
    agent = registry.get_agent(agent_id)
    if agent is None:
        checks.append(_check("agent_exists", False, hint="智能体不存在或无权访问"))
        return {"target": "agent", "agent_id": agent_id, "ready": False, "checks": checks}

    checks.append(_check("agent_exists", True))
    model_id = (getattr(agent, "model_id", None) or "").strip()
    if not model_id:
        checks.append(_check("model_bound", False, hint="请绑定 model_id"))
    else:
        checks.append(_check("model_bound", True))
        try:
            reg = get_model_registry()
            models = reg.list_models() if hasattr(reg, "list_models") else []
            model_ids = {getattr(m, "id", str(m)) for m in models}
            checks.append(
                _check(
                    "model_registered",
                    model_id in model_ids,
                    hint=f"模型 {model_id} 未在网关注册",
                )
            )
        except Exception as exc:
            checks.append(
                _check("model_registered", False, severity="warn", hint=str(exc))
            )

    skills = list(getattr(agent, "enabled_skills", None) or [])
    checks.append(
        _check(
            "skills_nonempty",
            len(skills) > 0,
            severity="warn",
            hint="未启用技能时部分计划模式能力受限",
        )
    )

    mode = (getattr(agent, "execution_mode", None) or "legacy").strip()
    if mode == "plan_based":
        checks.append(
            _check(
                "plan_mode_kernel",
                True,
                severity="info",
                hint="Plan-Based 模式：确认全局 Execution Kernel 与 max_steps 合理",
            )
        )

    blocking = [c for c in checks if not c["ok"] and c.get("severity") == "error"]
    return {
        "target": "agent",
        "agent_id": agent_id,
        "tenant_id": tenant_id,
        "ready": len(blocking) == 0,
        "checks": checks,
    }


def preflight_workflow(
    workflow_id: str,
    *,
    version_id: Optional[str] = None,
    tenant_id: str = "default",
    db: Any = None,
) -> Dict[str, Any]:
    from core.data.base import sessionmaker_for_engine, get_engine
    from core.workflows.repository import WorkflowRepository, WorkflowVersionRepository
    from core.workflows.services.workflow_version_service import WorkflowVersionService

    checks: List[Dict[str, Any]] = []
    if db is None:
        from sqlalchemy.orm import Session

        SessionLocal = sessionmaker_for_engine(get_engine())
        session: Session = SessionLocal()
        try:
            return preflight_workflow(
                workflow_id,
                version_id=version_id,
                tenant_id=tenant_id,
                db=session,
            )
        finally:
            session.close()

    wf_repo = WorkflowRepository(db)
    wf = wf_repo.get_by_id(workflow_id, tenant_id)
    if wf is None:
        checks.append(_check("workflow_exists", False, hint="工作流不存在"))
        return {
            "target": "workflow",
            "workflow_id": workflow_id,
            "ready": False,
            "checks": checks,
        }
    checks.append(_check("workflow_exists", True))

    ver_repo = WorkflowVersionRepository(db)
    version = None
    if version_id:
        version = ver_repo.get_version_by_id(version_id)
    else:
        version = ver_repo.get_published_version(workflow_id)

    if version is None:
        checks.append(
            _check(
                "published_version",
                False,
                hint="无已发布版本：请先发布或指定 version_id",
            )
        )
        return {
            "target": "workflow",
            "workflow_id": workflow_id,
            "ready": False,
            "checks": checks,
        }
    checks.append(_check("published_version", True))

    debug = bool(getattr(settings, "debug", True))
    from core.workflows.models import WorkflowVersionState

    if version.state == WorkflowVersionState.DRAFT and not debug:
        allow_draft = bool(getattr(settings, "workflow_allow_draft_execution", False))
        checks.append(
            _check(
                "not_draft_in_production",
                allow_draft,
                hint="生产环境禁止执行草稿：请发布版本",
            )
        )
    else:
        checks.append(_check("not_draft_in_production", True))

    dag_errors: List[str] = []
    try:
        dag_errors = version.dag.validate_dag() or []
    except Exception as exc:
        dag_errors = [str(exc)]

    checks.append(
        _check(
            "dag_valid",
            len(dag_errors) == 0,
            hint="; ".join(dag_errors[:5]) if dag_errors else None,
        )
    )

    # 审批/门控节点提示（易用性）
    node_types = [n.type for n in (version.dag.nodes or [])]
    if "approval" in node_types:
        checks.append(
            _check(
                "approval_nodes",
                True,
                severity="info",
                hint="含审批节点：运行中将等待人工决策",
            )
        )

    blocking = [c for c in checks if not c["ok"] and c.get("severity") == "error"]
    return {
        "target": "workflow",
        "workflow_id": workflow_id,
        "version_id": version.version_id,
        "tenant_id": tenant_id,
        "ready": len(blocking) == 0,
        "checks": checks,
    }
