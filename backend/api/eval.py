"""Eval 回归套件 API。"""
from __future__ import annotations

from typing import Annotated, Any, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.data.base import get_db
from core.eval.regression_suite import run_eval_suite
from core.security.deps import require_authenticated_platform_admin

router = APIRouter(prefix="/api/v1/eval", tags=["eval"])


class EvalCase(BaseModel):
    id: Optional[str] = None
    target: str = "agent"
    agent_id: Optional[str] = None
    workflow_id: Optional[str] = None
    version_id: Optional[str] = None
    input: Optional[str] = None
    input_data: dict = Field(default_factory=dict)
    global_context: dict = Field(default_factory=dict)
    execute: bool = False
    expect: dict = Field(default_factory=dict)


class EvalRunRequest(BaseModel):
    suite_id: Optional[str] = None
    cases: List[EvalCase] = Field(default_factory=list)
    stop_on_failure: bool = False
    run_preflight_first: bool = True


class EvalRunResponse(BaseModel):
    run_id: str
    suite_id: Optional[str] = None
    total: int
    executed: int
    passed: int
    failed: int
    duration_ms: int
    results: list


@router.post("/suites/run", response_model=EvalRunResponse)
def run_regression_suite(
    body: EvalRunRequest,
    db: Annotated[Session, Depends(get_db)],
    _role: Annotated[Any, Depends(require_authenticated_platform_admin)],
) -> EvalRunResponse:
    if not body.cases:
        return EvalRunResponse(
            run_id="",
            suite_id=body.suite_id,
            total=0,
            executed=0,
            passed=0,
            failed=0,
            duration_ms=0,
            results=[],
        )
    raw_cases = [c.model_dump(mode="json") for c in body.cases]
    result = run_eval_suite(
        db,
        cases=raw_cases,
        stop_on_failure=body.stop_on_failure,
        run_preflight_first=body.run_preflight_first,
    )
    return EvalRunResponse(suite_id=body.suite_id, **result)
