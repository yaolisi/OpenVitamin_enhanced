"""工具失败反思：配置开关与 JSON 形态（不调用真实推理）。"""
import pytest

from core.agent_runtime.definition import AgentDefinition
from core.agent_runtime.reflection import tool_failure_suggest as tfr
from core.agent_runtime.v2.models import Step, StepStatus, StepType, ExecutorType


def _minimal_agent(**kwargs) -> AgentDefinition:
    base = dict(
        agent_id="a_test",
        name="Test",
        model_id="any-model",
    )
    base.update(kwargs)
    return AgentDefinition(**base)


def test_tool_failure_reflection_enabled_defaults_off():
    agent = _minimal_agent()
    assert tfr.tool_failure_reflection_enabled(agent) is False


def test_tool_failure_reflection_enabled_on():
    agent = _minimal_agent(
        model_params={"tool_failure_reflection": {"enabled": True, "mode": "suggest_only"}}
    )
    assert tfr.tool_failure_reflection_enabled(agent) is True


def test_parse_json_object_from_fence():
    raw = 'Here:\n```json\n{"a": 1, "b": "x"}\n```\n'
    out = tfr._parse_json_object(raw)
    assert out == {"a": 1, "b": "x"}


@pytest.mark.asyncio
async def test_run_tool_failure_suggestion_skips_when_disabled():
    agent = _minimal_agent()
    step = Step(
        type=StepType.ATOMIC,
        executor=ExecutorType.SKILL,
        inputs={"skill_id": "x.y", "inputs": {}},
        status=StepStatus.FAILED,
        error="failed",
    )
    out = await tfr.run_tool_failure_suggestion(
        agent=agent, session=None, step=step, plan_goal="goal"
    )
    assert out is None
