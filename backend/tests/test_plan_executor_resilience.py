"""
PlanBasedExecutor: parallel_group 分段、重试/超时 辅助逻辑单测
"""
from core.agent_runtime.v2.executor_v2 import PlanBasedExecutor
from core.agent_runtime.v2.models import (
    Plan,
    Step,
    create_atomic_step,
    ExecutorType,
    StepType,
)
from core.agent_runtime.definition import AgentDefinition
from core.agent_runtime.v2.runtime import _apply_agent_plan_execution_defaults


def test_group_step_indices_serial_and_parallel():
    a = create_atomic_step(ExecutorType.SKILL, {"skill_id": "s1", "inputs": {}})
    b = create_atomic_step(ExecutorType.SKILL, {"skill_id": "s2", "inputs": {}})
    c = create_atomic_step(ExecutorType.SKILL, {"skill_id": "s3", "inputs": {}})
    a.parallel_group = "g1"
    b.parallel_group = "g1"
    c.parallel_group = None
    g = PlanBasedExecutor._group_step_indices([a, b, c])
    assert g == [[0, 1], [2]]


def test_group_step_indices_inputs_parallel_group():
    a = create_atomic_step(ExecutorType.SKILL, {"_parallel_group": "g", "skill_id": "a", "inputs": {}})
    b = create_atomic_step(ExecutorType.SKILL, {"_parallel_group": "g", "skill_id": "b", "inputs": {}})
    g = PlanBasedExecutor._group_step_indices([a, b])
    assert g == [[0, 1]]


def test_base_failure_strategy_timeout_overrides():
    ex = PlanBasedExecutor()
    agent = AgentDefinition(
        agent_id="a1",
        name="t",
        description="",
        model_id="m",
        on_failure_strategy="stop",
    )
    plan = Plan()
    plan.failure_strategy = "stop"
    st = Step(type=StepType.ATOMIC, executor=ExecutorType.SKILL, inputs={})
    st.on_timeout_strategy = "continue"
    ctx = {"_last_failure_kind": "timeout"}
    s = ex._base_failure_strategy(plan, agent, st, ctx)  # noqa: SLF001
    assert s == "continue"
    st.on_timeout_strategy = None
    plan.default_on_timeout_strategy = "replan"
    assert ex._base_failure_strategy(plan, agent, st, ctx) == "replan"  # noqa: SLF001


def test_merge_batch_parallel_two_skills():
    ex = PlanBasedExecutor()
    s1 = create_atomic_step(ExecutorType.SKILL, {"skill_id": "a", "inputs": {}})
    s1.outputs = {"o": 1}
    s2 = create_atomic_step(ExecutorType.SKILL, {"skill_id": "b", "inputs": {}})
    s2.outputs = {"o": 2}
    p = Plan(steps=[s1, s2])
    ls, ll = ex._merge_batch_stream_outputs(p, [0, 1], None, None)  # noqa: SLF001
    assert ll is None
    assert isinstance(ls, dict)
    assert ls["result"]["parallel_group"] is True
    assert s1.step_id in ls["result"]["by_step"]
    assert s2.step_id in ls["result"]["by_step"]


def test_apply_agent_plan_execution_defaults_from_model_params():
    plan = Plan(steps=[])
    agent = AgentDefinition(
        agent_id="a1",
        name="t",
        description="",
        model_id="m",
        model_params={
            "plan_execution": {
                "max_parallel_in_group": 3,
                "default_timeout_seconds": 12.0,
                "default_max_retries": 2,
                "default_retry_interval_seconds": 0.5,
                "default_on_timeout_strategy": "continue",
            }
        },
    )
    _apply_agent_plan_execution_defaults(plan, agent)
    assert plan.max_parallel_in_group == 3
    assert plan.default_timeout_seconds == 12.0
    assert plan.default_max_retries == 2
    assert plan.default_retry_interval_seconds == 0.5
    assert plan.default_on_timeout_strategy == "continue"
