"""
model_params.tool_failure_reflection 的 API 校验（不启动 ASGI）。
"""

import pytest

from api.agents import _validate_model_params_tool_failure_reflection
from api.errors import APIException


def test_allows_absent():
    _validate_model_params_tool_failure_reflection({})
    _validate_model_params_tool_failure_reflection(None)
    _validate_model_params_tool_failure_reflection({"intent_rules": []})


def test_allows_valid():
    _validate_model_params_tool_failure_reflection(
        {"tool_failure_reflection": {"enabled": True, "mode": "suggest_only"}}
    )
    _validate_model_params_tool_failure_reflection(
        {"tool_failure_reflection": {"enabled": False}}
    )
    _validate_model_params_tool_failure_reflection(
        {"tool_failure_reflection": {"enabled": True}}
    )


def test_rejects_non_object():
    with pytest.raises(APIException) as exc:
        _validate_model_params_tool_failure_reflection(
            {"tool_failure_reflection": "yes"},
        )
    assert exc.value.status_code == 400


def test_rejects_extra_key():
    with pytest.raises(APIException) as exc:
        _validate_model_params_tool_failure_reflection(
            {"tool_failure_reflection": {"enabled": True, "foo": 1}},
        )
    assert exc.value.status_code == 400


def test_rejects_bad_mode():
    with pytest.raises(APIException) as exc:
        _validate_model_params_tool_failure_reflection(
            {"tool_failure_reflection": {"enabled": True, "mode": "auto_fix"}},
        )
    assert exc.value.status_code == 400
