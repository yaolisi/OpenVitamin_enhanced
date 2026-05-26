#!/usr/bin/env python3
"""从 demos/workflows/*.bundle.json 导入工作流定义与版本。

用法:
  PYTHONPATH=backend python3 scripts/import_demo_workflow.py \\
    demos/workflows/demo1-release-brief-gate.bundle.json

环境变量:
  PERILLA_API_BASE   默认 http://127.0.0.1:8000
  PERILLA_API_KEY    可选
  X_TENANT_ID        多租户时设置
  PUBLISH            设为 1 则创建后发布版本
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def _request(
    method: str,
    url: str,
    *,
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    data = None
    hdrs = {"Content-Type": "application/json", "Accept": "application/json"}
    if headers:
        hdrs.update(headers)
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {exc.code} {method} {url}\n{detail}") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description="Import Perilla demo workflow bundle JSON")
    parser.add_argument("bundle_path", type=Path, help="Path to *.bundle.json")
    parser.add_argument("--namespace", default="default", help="Workflow namespace")
    parser.add_argument("--publish", action="store_true", help="Publish version after create")
    args = parser.parse_args()

    bundle_path = args.bundle_path.resolve()
    if not bundle_path.is_file():
        raise SystemExit(f"Bundle not found: {bundle_path}")

    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    dag = bundle.get("dag")
    if not isinstance(dag, dict):
        raise SystemExit("Invalid bundle: missing dag object")

    base = os.environ.get("PERILLA_API_BASE", "http://127.0.0.1:8000").rstrip("/")
    headers: dict[str, str] = {}
    api_key = os.environ.get("PERILLA_API_KEY", "").strip()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    tenant = os.environ.get("X_TENANT_ID", "").strip()
    if tenant:
        headers["X-Tenant-Id"] = tenant

    wf_name = str(bundle.get("workflow_name") or bundle.get("name") or "Demo Workflow")
    description = str(bundle.get("description") or "")
    tags = bundle.get("tags") if isinstance(bundle.get("tags"), list) else ["demo"]

    created = _request(
        "POST",
        f"{base}/api/v1/workflows",
        body={
            "namespace": args.namespace,
            "name": wf_name,
            "description": description,
            "tags": tags,
            "metadata": {"demo_id": bundle.get("demo_id"), "imported_from": str(bundle_path.name)},
        },
        headers=headers,
    )
    workflow_id = str(created.get("id") or "")
    if not workflow_id:
        raise SystemExit(f"Unexpected create response: {created}")

    version = _request(
        "POST",
        f"{base}/api/v1/workflows/{workflow_id}/versions",
        body={
            "dag": dag,
            "description": f"Imported from {bundle_path.name}",
        },
        headers=headers,
    )
    version_id = str(version.get("version_id") or "")
    published = False
    if args.publish or os.environ.get("PUBLISH", "").strip() in ("1", "true", "yes"):
        if version_id:
            _request(
                "POST",
                f"{base}/api/v1/workflows/{workflow_id}/versions/{version_id}/publish",
                body={},
                headers=headers,
            )
            published = True

    sample = bundle.get("sample_input")
    print(json.dumps({
        "workflow_id": workflow_id,
        "version_id": version_id,
        "published": published,
        "edit_url_hint": f"/workflow/{workflow_id}/edit",
        "run_url_hint": f"/workflow/{workflow_id}/run",
        "sample_input": sample,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
