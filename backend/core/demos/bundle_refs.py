"""Bundle 内 $import: 引用与 bundle_key 生成。"""
from __future__ import annotations

import re
from typing import Any

IMPORT_REF_PREFIX = "$import:"


def is_import_ref(value: Any) -> bool:
    return isinstance(value, str) and value.startswith(IMPORT_REF_PREFIX)


def make_import_ref(bundle_key: str) -> str:
    return f"{IMPORT_REF_PREFIX}{bundle_key}"


def make_bundle_key(prefix: str, name: str, entity_id: str, used: set[str]) -> str:
    raw = re.sub(r"[^a-zA-Z0-9_]+", "_", (name or entity_id).lower()).strip("_")
    raw = (raw[:48] or re.sub(r"[^a-zA-Z0-9_]", "_", entity_id)[:12]).strip("_")
    candidate = f"{prefix}_{raw}" if raw else f"{prefix}_{entity_id[:8]}"
    base = candidate
    n = 2
    while candidate in used:
        candidate = f"{base}_{n}"
        n += 1
    used.add(candidate)
    return candidate
