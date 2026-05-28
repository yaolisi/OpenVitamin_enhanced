"""
推理出站数据驻留分类：本地运行时 vs 外部（远程）大模型端点。
"""
from __future__ import annotations

import ipaddress
from typing import Literal, Optional
from urllib.parse import urlparse

from config.settings import settings
from core.models.descriptor import ModelDescriptor

DataResidency = Literal["local", "external"]


def _csv_tokens(raw: str) -> set[str]:
    return {item.strip().lower() for item in (raw or "").split(",") if item.strip()}


def _local_provider_tokens() -> set[str]:
    default = (
        "ollama,llama_cpp,llamacpp,local,onnx,torch,pytorch,"
        "transformers,lmstudio,mlx,gguf"
    )
    raw = str(getattr(settings, "inference_egress_local_providers", "") or "").strip()
    return _csv_tokens(raw or default)


def _external_provider_tokens() -> set[str]:
    default = "openai,gemini,deepseek,kimi,anthropic,azure,openrouter"
    raw = str(getattr(settings, "inference_egress_external_providers", "") or "").strip()
    return _csv_tokens(raw or default)


def _is_private_or_loopback_host(host: str) -> bool:
    h = (host or "").strip().lower()
    if not h:
        return True
    if h in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        addr = ipaddress.ip_address(h)
        return addr.is_loopback or addr.is_private or addr.is_link_local
    except ValueError:
        return h.endswith(".local") or h.endswith(".internal")


def _base_url_residency(base_url: Optional[str]) -> Optional[DataResidency]:
    raw = (base_url or "").strip()
    if not raw:
        return None
    try:
        parsed = urlparse(raw if "://" in raw else f"http://{raw}")
    except Exception:
        return None
    host = parsed.hostname or ""
    if _is_private_or_loopback_host(host):
        return "local"
    if host:
        return "external"
    return None


def classify_model_residency(
    *,
    provider: str,
    runtime: str = "",
    base_url: Optional[str] = None,
    descriptor: Optional[ModelDescriptor] = None,
) -> DataResidency:
    """
    判定模型出站驻留类型。显式 descriptor.data_residency 优先，其次 provider/runtime 列表与 base_url。
    """
    if descriptor is not None:
        explicit = (getattr(descriptor, "data_residency", None) or "").strip().lower()
        if explicit in ("local", "external"):
            return explicit  # type: ignore[return-value]

    prov = (provider or "").strip().lower()
    runt = (runtime or "").strip().lower()
    if prov in _external_provider_tokens() or runt in _external_provider_tokens():
        return "external"
    if prov in _local_provider_tokens() or runt in _local_provider_tokens():
        return "local"

    url_res = _base_url_residency(base_url or (descriptor.base_url if descriptor else None))
    if url_res is not None:
        return url_res

    # 未知 provider：有公网 base_url 视为 external，否则 local（本地优先默认）
    if descriptor and (descriptor.base_url or "").strip():
        return "external"
    return "local"
