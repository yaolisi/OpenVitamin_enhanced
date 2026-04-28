from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict

from core.plugins.manifest import PluginManifest


class PluginMarketValidationError(ValueError):
    pass


def validate_manifest_file(manifest_path: str) -> Dict[str, Any]:
    path = Path(manifest_path)
    if not path.exists():
        raise PluginMarketValidationError(f"manifest file not found: {manifest_path}")
    if not path.is_file():
        raise PluginMarketValidationError(f"manifest path is not file: {manifest_path}")
    raw = path.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise PluginMarketValidationError(f"manifest is not valid json: {e}") from e
    try:
        PluginManifest(**data)
    except Exception as e:
        raise PluginMarketValidationError(f"manifest schema invalid: {e}") from e
    return data


def build_signature_digest(signature: str, manifest_path: str) -> str:
    payload = f"{signature}:{manifest_path}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
