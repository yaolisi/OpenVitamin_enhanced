"""
推理网关出站治理：仅对 external 驻留模型在调用前脱敏/阻断，并写入可审计 metadata。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from log import logger
from config.settings import settings
from core.inference.models.inference_request import InferenceRequest
from core.inference.models.embedding_request import EmbeddingRequest
from core.inference.models.asr_request import ASRRequest
from core.inference.models.metadata import InferenceMetadataJsonMap, inference_metadata_as_dict
from core.models.descriptor import ModelDescriptor
from core.security.data_residency import DataResidency, classify_model_residency
from core.security.egress_redaction import (
    redact_messages_list,
    redact_plain_text,
    redact_structured_payload,
)


class InferenceEgressBlockedError(RuntimeError):
    """外部模型出站被策略阻断。"""


@dataclass
class EgressGuardOutcome:
    residency: DataResidency
    applied: bool
    redaction_hits: int
    blocked: bool
    policy_version: str


_POLICY_VERSION = "egress-v1"


def egress_guard_enabled() -> bool:
    return bool(getattr(settings, "inference_egress_redaction_enabled", True))


def _merge_egress_metadata(
    metadata: Any,
    *,
    residency: DataResidency,
    applied: bool,
    hits: int,
    provider: str,
    model_id: str,
) -> InferenceMetadataJsonMap:
    meta = dict(inference_metadata_as_dict(metadata))
    meta["egress_data_residency"] = residency
    meta["egress_redaction_applied"] = applied
    meta["egress_redaction_hits"] = hits
    meta["egress_redaction_policy"] = _POLICY_VERSION
    meta["egress_provider"] = provider
    meta["egress_model_id"] = model_id
    return InferenceMetadataJsonMap.model_validate(meta)


def _should_block_external() -> bool:
    return bool(getattr(settings, "inference_egress_block_external", False))


def guard_inference_request(
    request: InferenceRequest,
    *,
    provider: str,
    model_id: str,
    descriptor: Optional[ModelDescriptor] = None,
) -> tuple[InferenceRequest, EgressGuardOutcome]:
    residency = classify_model_residency(
        provider=provider,
        runtime=(descriptor.runtime if descriptor else ""),
        base_url=(descriptor.base_url if descriptor else None),
        descriptor=descriptor,
    )
    outcome = EgressGuardOutcome(
        residency=residency,
        applied=False,
        redaction_hits=0,
        blocked=False,
        policy_version=_POLICY_VERSION,
    )

    if residency == "local" or not egress_guard_enabled():
        request.metadata = _merge_egress_metadata(
            request.metadata,
            residency=residency,
            applied=False,
            hits=0,
            provider=provider,
            model_id=model_id,
        )
        return request, outcome

    if _should_block_external():
        outcome.blocked = True
        raise InferenceEgressBlockedError(
            f"External inference blocked by policy (provider={provider}, model={model_id}). "
            "Set INFERENCE_EGRESS_BLOCK_EXTERNAL=false or use a local model."
        )

    hits = 0
    req = request.model_copy(deep=True)

    if isinstance(req.messages, list) and req.messages:
        new_messages, msg_hits = redact_messages_list(list(req.messages))
        req.messages = new_messages  # type: ignore[assignment]
        hits += msg_hits

    if isinstance(req.prompt, str) and req.prompt.strip():
        res = redact_plain_text(req.prompt)
        req.prompt = res.text
        hits += res.hit_count

    if isinstance(req.system_prompt, str) and req.system_prompt.strip():
        res = redact_plain_text(req.system_prompt)
        req.system_prompt = res.text
        hits += res.hit_count

    if req.metadata is not None:
        meta_dict = inference_metadata_as_dict(req.metadata)
        redacted_meta, _ = redact_structured_payload(meta_dict)
        req.metadata = InferenceMetadataJsonMap.model_validate(redacted_meta)

    outcome.applied = True
    outcome.redaction_hits = hits

    req.metadata = _merge_egress_metadata(
        req.metadata,
        residency=residency,
        applied=outcome.applied,
        hits=hits,
        provider=provider,
        model_id=model_id,
    )

    if hits:
        meta = inference_metadata_as_dict(req.metadata)
        logger.info(
            "[EgressGuard] external inference redacted provider=%s model=%s hits=%s trace_id=%s",
            provider,
            model_id,
            hits,
            meta.get("trace_id"),
        )

    return req, outcome


def guard_embedding_request(
    request: EmbeddingRequest,
    *,
    provider: str,
    model_id: str,
    descriptor: Optional[ModelDescriptor] = None,
) -> tuple[EmbeddingRequest, EgressGuardOutcome]:
    residency = classify_model_residency(
        provider=provider,
        runtime=(descriptor.runtime if descriptor else ""),
        base_url=(descriptor.base_url if descriptor else None),
        descriptor=descriptor,
    )
    outcome = EgressGuardOutcome(
        residency=residency,
        applied=False,
        redaction_hits=0,
        blocked=False,
        policy_version=_POLICY_VERSION,
    )
    if residency == "local" or not egress_guard_enabled():
        return request, outcome
    if _should_block_external():
        raise InferenceEgressBlockedError(
            f"External embedding blocked (provider={provider}, model={model_id})"
        )
    req = request.model_copy(deep=True)
    hits = 0
    if isinstance(getattr(req, "input", None), str):
        res = redact_plain_text(req.input)
        req.input = res.text
        hits += res.hit_count
    elif isinstance(req.input, list):
        new_inputs: list[str] = []
        for item in req.input:
            if isinstance(item, str):
                res = redact_plain_text(item)
                hits += res.hit_count
                new_inputs.append(res.text)
            else:
                new_inputs.append(item)
        req.input = new_inputs
    outcome.applied = True
    outcome.redaction_hits = hits
    return req, outcome


def guard_asr_request(
    request: ASRRequest,
    *,
    provider: str,
    model_id: str,
    descriptor: Optional[ModelDescriptor] = None,
) -> tuple[ASRRequest, EgressGuardOutcome]:
    """ASR 音频仍可能走外部；元数据脱敏，正文不适用正则。"""
    residency = classify_model_residency(
        provider=provider,
        runtime=(descriptor.runtime if descriptor else ""),
        base_url=(descriptor.base_url if descriptor else None),
        descriptor=descriptor,
    )
    outcome = EgressGuardOutcome(
        residency=residency,
        applied=False,
        redaction_hits=0,
        blocked=False,
        policy_version=_POLICY_VERSION,
    )
    if residency == "local" or not egress_guard_enabled():
        return request, outcome
    if _should_block_external():
        raise InferenceEgressBlockedError(
            f"External ASR blocked (provider={provider}, model={model_id})"
        )
    return request, outcome
