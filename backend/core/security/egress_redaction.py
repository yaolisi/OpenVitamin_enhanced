"""
出站推理正文脱敏：对发往外部大模型的 prompt / messages 做可配置掩码。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, List, Union

from config.settings import settings
from core.security.redaction import redact_payload
from core.types import Message

# 常见 PII / 密钥模式（确定性、可复现）
_PII_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("cn_mobile", re.compile(r"(?<!\d)(?:\+?86[-\s]?)?1[3-9]\d{9}(?!\d)")),
    ("cn_id_card", re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)|(?<!\d)\d{15}(?!\d)")),
    ("email", re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")),
    (
        "bank_card",
        re.compile(r"(?<!\d)(?:\d{16,19})(?!\d)"),
    ),
    ("ipv4", re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d?\d)(?:\.)){3}(?:25[0-5]|2[0-4]\d|[01]?\d?\d)\b")),
    (
        "api_secret",
        re.compile(
            r"\b(?:sk|pk|rk)-[A-Za-z0-9]{8,}\b|"
            r"\bBearer\s+[A-Za-z0-9._\-]{8,}\b",
            re.IGNORECASE,
        ),
    ),
]

_PLACEHOLDER = "[REDACTED]"


@dataclass(frozen=True)
class TextRedactionResult:
    text: str
    hit_count: int
    hit_kinds: tuple[str, ...]


def _load_sensitive_tokens() -> list[str]:
    raw = (getattr(settings, "data_redaction_sensitive_fields", "") or "").strip()
    tokens = [item.strip().lower() for item in raw.split(",") if item.strip()]
    return tokens or [
        "api_key",
        "password",
        "secret",
        "token",
        "authorization",
        "access_token",
        "refresh_token",
        "client_secret",
        "private_key",
    ]


def redact_plain_text(text: str) -> TextRedactionResult:
    """对自然语言正文应用 PII 正则与内嵌 JSON 敏感字段脱敏。"""
    if not text:
        return TextRedactionResult(text=text, hit_count=0, hit_kinds=())

    enabled = bool(getattr(settings, "inference_egress_redact_content", True))
    if not enabled:
        return TextRedactionResult(text=text, hit_count=0, hit_kinds=())

    out = text
    kinds: list[str] = []
    hits = 0
    for kind, pattern in _PII_PATTERNS:
        new_out, n = pattern.subn(_PLACEHOLDER, out)
        if n:
            hits += n
            kinds.append(kind)
            out = new_out

    # 行内疑似「字段: 密钥」结构（如 api_key: sk-xxx）
    for token in _load_sensitive_tokens():
        pat = re.compile(
            rf"(\b{re.escape(token)}\b\s*[:=]\s*)(\S+)",
            re.IGNORECASE,
        )
        new_out, n = pat.subn(rf"\1{_PLACEHOLDER}", out)
        if n:
            hits += n
            if "inline_secret" not in kinds:
                kinds.append("inline_secret")
            out = new_out

    return TextRedactionResult(text=out, hit_count=hits, hit_kinds=tuple(kinds))


def redact_message_content(content: Any) -> tuple[Any, int]:
    """脱敏单条 message 的 content（str 或多模态 list）。"""
    if isinstance(content, str):
        res = redact_plain_text(content)
        return res.text, res.hit_count

    if isinstance(content, list):
        total = 0
        new_items: list[Any] = []
        for item in content:
            if isinstance(item, dict):
                item_type = item.get("type")
                if item_type == "text" and isinstance(item.get("text"), str):
                    res = redact_plain_text(item["text"])
                    total += res.hit_count
                    new_items.append({**item, "text": res.text})
                else:
                    new_items.append(item)
                continue
            item_type = getattr(item, "type", None)
            if item_type == "text":
                text = getattr(item, "text", None)
                if isinstance(text, str):
                    res = redact_plain_text(text)
                    total += res.hit_count
                    try:
                        new_items.append(item.model_copy(update={"text": res.text}))
                    except Exception:
                        new_items.append(item)
                    continue
            new_items.append(item)
        return new_items, total

    return content, 0


def redact_messages_list(messages: list[Any]) -> tuple[list[Any], int]:
    total_hits = 0
    out: list[Any] = []
    for msg in messages:
        if isinstance(msg, Message):
            new_content, hits = redact_message_content(msg.content)
            total_hits += hits
            out.append(msg.model_copy(update={"content": new_content}))
            continue
        if isinstance(msg, dict):
            role = msg.get("role")
            content = msg.get("content")
            new_content, hits = redact_message_content(content)
            total_hits += hits
            out.append(Message(role=role, content=new_content))
            continue
        content = getattr(msg, "content", None)
        new_content, hits = redact_message_content(content)
        total_hits += hits
        try:
            out.append(msg.model_copy(update={"content": new_content}))
        except Exception:
            out.append(msg)
    return out, total_hits


def redact_structured_payload(payload: Any) -> tuple[Any, int]:
    """对 dict/list 请求体做字段名敏感脱敏（如 metadata 中的 token）。"""
    tokens = _load_sensitive_tokens()
    keep_prefix = int(getattr(settings, "data_redaction_mask_keep_prefix", 4))
    keep_suffix = int(getattr(settings, "data_redaction_mask_keep_suffix", 4))
    redacted = redact_payload(
        payload,
        sensitive_fields=tokens,
        keep_prefix=keep_prefix,
        keep_suffix=keep_suffix,
    )
    # redact_payload 不返回 hit count；出站审计以正文命中为主
    return redacted, 0
