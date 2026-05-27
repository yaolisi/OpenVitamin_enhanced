"""导入/导出环境预检。"""
from __future__ import annotations

import shutil
from typing import Any, Literal, Optional

from core.models.registry import get_model_registry

CheckLevel = Literal["ok", "warn", "error"]


def _check(label: str, ok: bool, *, level: Optional[CheckLevel] = None, message: str = "", action_url: str = "") -> dict[str, Any]:
    if level is None:
        level = "ok" if ok else "error"
    return {
        "id": label,
        "ok": ok,
        "level": level,
        "message": message,
        "action_url": action_url,
    }


def check_import_environment(
    *,
    tenant_id: str,
    bundle: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    registry = get_model_registry()
    models = registry.list_models()
    has_llm = any(getattr(m, "model_type", None) == "llm" for m in models)
    has_embed = any(getattr(m, "model_type", None) == "embedding" for m in models)
    checks.append(
        _check(
            "llm_registered",
            has_llm,
            message="至少注册 1 个 LLM 模型" if has_llm else "未找到 LLM；请先在模型库添加",
            action_url="/models",
        )
    )
    needs_embed = bool(bundle and bundle.get("knowledge_bases"))
    if needs_embed or not bundle:
        checks.append(
            _check(
                "embedding_registered",
                has_embed,
                message="Embedding 已就绪" if has_embed else "平台包含知识库，需要 Embedding 模型",
                action_url="/models",
            )
        )
    has_mcp = bool(bundle and bundle.get("mcp_servers"))
    if has_mcp:
        npx_ok = bool(shutil.which("npx"))
        checks.append(
            _check(
                "npx_available",
                npx_ok,
                level="ok" if npx_ok else "warn",
                message="npx 可用（stdio MCP）" if npx_ok else "未检测到 npx；stdio MCP 模板可能无法 Probe",
                action_url="/settings/mcp",
            )
        )
    required = [c for c in checks if c["level"] == "error"]
    return {
        "ready": len(required) == 0,
        "tenant_id": tenant_id,
        "checks": checks,
    }
