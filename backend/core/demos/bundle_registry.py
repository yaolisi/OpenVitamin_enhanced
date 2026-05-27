"""仓库内 platform bundle 清单与加载。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[3]
PLATFORM_DIR = _REPO_ROOT / "demos" / "platform"


def platform_bundles_dir() -> Path:
    return PLATFORM_DIR


def list_platform_bundle_manifests() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    root = platform_bundles_dir()
    if not root.is_dir():
        return out
    for path in sorted(root.glob("*.platform-bundle.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        bundle_id = str(data.get("bundle_id") or path.stem.replace(".platform-bundle", ""))
        ui = data.get("ui_hints") if isinstance(data.get("ui_hints"), dict) else {}
        out.append(
            {
                "bundle_id": bundle_id,
                "name": str(data.get("name") or bundle_id),
                "description": str(data.get("description") or ""),
                "schema_version": data.get("schema_version"),
                "tags": list(ui.get("tags") or data.get("tags") or []),
                "estimated_minutes": ui.get("estimated_minutes"),
                "playbook_url": ui.get("playbook_url"),
                "scene": ui.get("scene"),
                "recommended_eval_suite": data.get("recommended_eval_suite") or ui.get("recommended_eval_suite"),
            }
        )
    return out


def load_platform_bundle(bundle_id: str) -> tuple[dict[str, Any], Path]:
    root = platform_bundles_dir()
    candidates = [
        root / f"{bundle_id}.platform-bundle.json",
        root / bundle_id,
    ]
    for path in candidates:
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            if str(data.get("bundle_id") or "") != bundle_id:
                data["bundle_id"] = bundle_id
            return data, path.parent
    raise FileNotFoundError(f"Platform bundle not found: {bundle_id}")
