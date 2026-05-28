"""出站推理脱敏：数据驻留分类与 InferenceGateway 集成。"""
from __future__ import annotations

import pytest

from config.settings import settings
from core.inference.models.inference_request import InferenceRequest
from core.inference.router.model_router import RoutingResult
from core.models.descriptor import ModelDescriptor
from core.security.data_residency import classify_model_residency
from core.security.egress_redaction import redact_plain_text
from core.security.inference_egress_guard import (
    InferenceEgressBlockedError,
    guard_inference_request,
)
from core.types import Message


def test_classify_openai_as_external() -> None:
    assert (
        classify_model_residency(provider="openai", runtime="openai", base_url="https://api.openai.com/v1")
        == "external"
    )


def test_classify_ollama_localhost_as_local() -> None:
    assert (
        classify_model_residency(provider="ollama", runtime="ollama", base_url="http://127.0.0.1:11434")
        == "local"
    )


def test_descriptor_explicit_residency() -> None:
    desc = ModelDescriptor(
        id="custom:model",
        name="Custom",
        provider="openai",
        provider_model_id="gpt",
        runtime="openai",
        base_url="https://api.openai.com/v1",
        data_residency="local",
    )
    assert classify_model_residency(provider="openai", descriptor=desc) == "local"


def test_redact_plain_text_masks_phone_and_email() -> None:
    text = "联系人手机13800138000，邮箱 user@example.com"
    res = redact_plain_text(text)
    assert "[REDACTED]" in res.text
    assert "13800138000" not in res.text
    assert "user@example.com" not in res.text
    assert res.hit_count >= 2


def test_guard_skips_local_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "inference_egress_redaction_enabled", True)
    req = InferenceRequest(
        model_alias="fast",
        messages=[Message(role="user", content="手机13800138000")],
    )
    guarded, outcome = guard_inference_request(
        req, provider="ollama", model_id="ollama:llama3"
    )
    assert outcome.residency == "local"
    assert outcome.applied is False
    assert "13800138000" in guarded.messages[0].content  # type: ignore[index]


def test_guard_redacts_external_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "inference_egress_redaction_enabled", True)
    monkeypatch.setattr(settings, "inference_egress_redact_content", True)
    req = InferenceRequest(
        model_alias="reasoning",
        messages=[Message(role="user", content="手机13800138000")],
    )
    guarded, outcome = guard_inference_request(
        req, provider="openai", model_id="gpt-4"
    )
    assert outcome.residency == "external"
    assert outcome.applied is True
    assert outcome.redaction_hits >= 1
    assert "13800138000" not in str(guarded.messages[0].content)
    meta = guarded.metadata.model_dump()
    assert meta.get("egress_data_residency") == "external"
    assert meta.get("egress_redaction_applied") is True


def test_guard_blocks_external_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "inference_egress_redaction_enabled", True)
    monkeypatch.setattr(settings, "inference_egress_block_external", True)
    req = InferenceRequest(model_alias="reasoning", prompt="hello")
    with pytest.raises(InferenceEgressBlockedError):
        guard_inference_request(req, provider="openai", model_id="gpt-4")


@pytest.mark.asyncio
async def test_inference_gateway_applies_guard_before_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from core.inference.gateway.inference_gateway import InferenceGateway
    from core.inference.models.inference_response import InferenceResponse

    monkeypatch.setattr(settings, "inference_egress_redaction_enabled", True)
    monkeypatch.setattr(settings, "inference_cache_enabled", False)
    gw = InferenceGateway()
    captured: dict[str, str] = {}

    async def fake_generate(provider, model_id, request):  # type: ignore[no-untyped-def]
        captured["content"] = str(request.messages[0].content)
        return InferenceResponse(
            model_alias=request.model_alias,
            text="ok",
            provider=provider,
            model=model_id,
        )

    monkeypatch.setattr(gw.adapter, "generate", fake_generate)
    monkeypatch.setattr(
        gw.router,
        "resolve",
        lambda model_alias, request_metadata=None: RoutingResult(
            alias=None,
            provider="openai",
            model_id="gpt-4",
            resolved_via="direct",
        ),
    )
    monkeypatch.setattr(gw, "_descriptor_for_routing", lambda routing: None)

    req = InferenceRequest(
        model_alias="gpt-4",
        messages=[Message(role="user", content="手机13800138000")],
    )

    await gw.generate(req)
    assert "13800138000" not in captured.get("content", "")
