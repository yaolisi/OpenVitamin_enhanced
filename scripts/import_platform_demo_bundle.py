#!/usr/bin/env python3
"""从 demos/platform/*.platform-bundle.json 一键导入 Agent + 知识库 + 工作流。

用法:
  PYTHONPATH=backend python3 scripts/import_platform_demo_bundle.py rag-research-verify

环境变量:
  PERILLA_API_BASE   默认 http://127.0.0.1:8000
  PERILLA_API_KEY    可选（Cookie 登录场景可不设）
  X_TENANT_ID        多租户时设置
  PUBLISH            设为 1 则请求 publish_workflows=true
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
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
        with urllib.request.urlopen(req, timeout=600) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {exc.code} {method} {url}\n{detail}") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description="Import Perilla platform demo bundle")
    parser.add_argument("bundle_id", help="e.g. rag-research-verify")
    parser.add_argument("--publish", action="store_true", help="Publish workflow after import")
    args = parser.parse_args()

    base = os.environ.get("PERILLA_API_BASE", "http://127.0.0.1:8000").rstrip("/")
    headers: dict[str, str] = {}
    api_key = os.environ.get("PERILLA_API_KEY", "").strip()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
        headers["X-Api-Key"] = api_key
    tenant = os.environ.get("X_TENANT_ID", "").strip()
    if tenant:
        headers["X-Tenant-Id"] = tenant

    publish = args.publish or os.environ.get("PUBLISH", "").strip().lower() in ("1", "true", "yes")
    result = _request(
        "POST",
        f"{base}/api/v1/import/run",
        body={
            "kind": "platform",
            "bundle_id": args.bundle_id,
            "publish_workflows": publish,
            "wait_document_index": True,
        },
        headers=headers,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
