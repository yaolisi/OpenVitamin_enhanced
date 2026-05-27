"""
统一密钥解析：环境变量 / Vault 环境变量别名 / 文件路径（企业部署）。

热路径仅读取进程内缓存的环境变量，不在请求中访问 Vault 网络。
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from config.settings import settings


def resolve_secret(
    logical_name: str,
    *,
    env_key: Optional[str] = None,
    vault_env_key: Optional[str] = None,
    file_env_key: Optional[str] = None,
) -> str:
    """
    按 settings.secret_resolver_mode 解析密钥。

    - env: 直接 os.environ[env_key or logical_name]
    - vault_env: os.environ[vault_env_key or f"VAULT_{logical_name}"]
    - file: os.environ[file_env_key] 指向的文件内容（单行 trim）
    """
    mode = (getattr(settings, "secret_resolver_mode", "env") or "env").strip().lower()
    ek = (env_key or logical_name or "").strip()
    if not ek:
        return ""

    if mode == "vault_env":
        vk = (vault_env_key or f"VAULT_{ek.upper()}").strip()
        return (os.environ.get(vk) or "").strip()

    if mode == "file":
        fek = (file_env_key or f"{ek.upper()}_FILE").strip()
        path_raw = (os.environ.get(fek) or "").strip()
        if not path_raw:
            return ""
        return _read_secret_file(path_raw)

    return (os.environ.get(ek) or "").strip()


def _read_secret_file(path_raw: str) -> str:
    path = Path(path_raw).expanduser()
    roots_raw = (getattr(settings, "secret_file_roots", "") or "").strip()
    if roots_raw:
        allowed = [Path(r).expanduser().resolve() for r in roots_raw.split(",") if r.strip()]
        resolved = path.resolve()
        if not any(resolved == root or root in resolved.parents for root in allowed):
            return ""
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


@lru_cache(maxsize=128)
def cached_env_secret(env_key: str) -> str:
    """进程内缓存的环境变量读取（供模型 Key 等高频路径）。"""
    return (os.environ.get(env_key) or "").strip()
