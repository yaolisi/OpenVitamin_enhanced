"""工作流演示 bundle（仅 DAG，位于 demos/workflows/）。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW_DIR = _REPO_ROOT / "demos" / "workflows"


def list_workflow_bundle_manifests() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    root = WORKFLOW_DIR
    if not root.is_dir():
        return out
    for path in sorted(root.glob("*.bundle.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        demo_id = str(data.get("demo_id") or path.stem.replace(".bundle", ""))
        out.append(
            {
                "bundle_id": demo_id,
                "name": str(data.get("name") or demo_id),
                "description": str(data.get("description") or ""),
                "schema_version": data.get("schema_version"),
                "recommended_platform_bundle_id": data.get("recommended_platform_bundle_id"),
                "canvas_mode": data.get("canvas_mode"),
            }
        )
    return out


def load_workflow_bundle(bundle_id: str) -> dict[str, Any]:
    path = WORKFLOW_DIR / f"{bundle_id}.bundle.json"
    if not path.is_file():
        for candidate in WORKFLOW_DIR.glob("*.bundle.json"):
            data = json.loads(candidate.read_text(encoding="utf-8"))
            if str(data.get("demo_id") or "") == bundle_id:
                return data
        raise FileNotFoundError(f"Workflow bundle not found: {bundle_id}")
    return json.loads(path.read_text(encoding="utf-8"))
