"""
本地 Eval 回归套件：JSON 用例批跑（Agent / Workflow），结果可归档。
"""
from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from core.agent_runtime.definition import get_agent_registry
from core.preflight.run_preflight import preflight_agent, preflight_workflow
from core.workflows.models import WorkflowExecutionCreateRequest
from core.workflows.services.workflow_execution_service import WorkflowExecutionService


def _case_id(case: Dict[str, Any], index: int) -> str:
    return str(case.get("id") or f"case-{index + 1}")


def run_eval_suite(
    db: Session,
    *,
    cases: List[Dict[str, Any]],
    tenant_id: str = "default",
    stop_on_failure: bool = False,
    run_preflight_first: bool = True,
) -> Dict[str, Any]:
    run_id = str(uuid.uuid4())
    started = time.time()
    results: List[Dict[str, Any]] = []
    passed = 0
    failed = 0

    for idx, case in enumerate(cases):
        cid = _case_id(case, idx)
        target = str(case.get("target") or "agent").strip().lower()
        row: Dict[str, Any] = {"id": cid, "target": target, "ok": False}
        t0 = time.time()

        try:
            if run_preflight_first:
                if target == "workflow":
                    wf_id = str(case.get("workflow_id") or "").strip()
                    pf = preflight_workflow(
                        wf_id,
                        version_id=case.get("version_id"),
                        tenant_id=tenant_id,
                        db=db,
                    )
                else:
                    ag_id = str(case.get("agent_id") or "").strip()
                    pf = preflight_agent(ag_id, tenant_id=tenant_id)
                row["preflight"] = pf
                if not pf.get("ready"):
                    row["error"] = "preflight_not_ready"
                    failed += 1
                    results.append(row)
                    if stop_on_failure:
                        break
                    continue

            expect = dict(case.get("expect") or {})
            if target == "workflow":
                row.update(_run_workflow_case(db, case, tenant_id=tenant_id, expect=expect))
            else:
                row.update(_run_agent_case(case, expect=expect))

            row["ok"] = bool(row.get("ok"))
            if row["ok"]:
                passed += 1
            else:
                failed += 1
        except Exception as exc:
            row["ok"] = False
            row["error"] = str(exc)
            failed += 1

        row["duration_ms"] = int((time.time() - t0) * 1000)
        results.append(row)
        if stop_on_failure and not row["ok"]:
            break

    return {
        "run_id": run_id,
        "total": len(cases),
        "executed": len(results),
        "passed": passed,
        "failed": failed,
        "duration_ms": int((time.time() - started) * 1000),
        "results": results,
    }


def _run_agent_case(case: Dict[str, Any], *, expect: Dict[str, Any]) -> Dict[str, Any]:
    agent_id = str(case.get("agent_id") or "").strip()
    registry = get_agent_registry()
    if registry.get_agent(agent_id) is None:
        return {"ok": False, "error": "agent_not_found"}

    if not bool(case.get("execute", False)):
        return {"ok": True, "skipped_run": True, "note": "preflight_only"}

    return {
        "ok": False,
        "error": "agent_execute_in_eval_requires_manual_run",
        "hint": "Set execute=false for preflight-only or run via UI/API",
    }


def _run_workflow_case(
    db: Session,
    case: Dict[str, Any],
    *,
    tenant_id: str,
    expect: Dict[str, Any],
) -> Dict[str, Any]:
    workflow_id = str(case.get("workflow_id") or "").strip()
    svc = WorkflowExecutionService(db)
    req = WorkflowExecutionCreateRequest(
        workflow_id=workflow_id,
        version_id=case.get("version_id"),
        input_data=dict(case.get("input_data") or {}),
        global_context=dict(case.get("global_context") or {}),
        trigger_type="eval",
    )
    execution = svc.create_execution(req, triggered_by="eval")
    expect_state = expect.get("state")
    state = execution.state.value if hasattr(execution.state, "value") else str(execution.state)
    ok = True
    if expect_state:
        ok = state == expect_state
    return {
        "ok": ok,
        "execution_id": execution.execution_id,
        "state": state,
    }
