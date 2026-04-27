#!/usr/bin/env python3
"""
连续批处理工具链预检（doctor）。

检查项：
1) 关键脚本是否存在
2) 输出目录可写
3) 可选：后端配置接口连通性（--check-api）
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

try:
    from scripts._http_utils import build_request_headers, http_get_json
except Exception:
    from _http_utils import build_request_headers, http_get_json  # type: ignore[no-redef]


REQUIRED_SCRIPTS = [
    "backend/scripts/continuous_batch_benchmark.py",
    "backend/scripts/continuous_batch_grid_search.py",
    "backend/scripts/continuous_batch_recommend.py",
    "backend/scripts/continuous_batch_rollback.py",
    "backend/scripts/continuous_batch_run_all.py",
    "backend/scripts/continuous_batch_acceptance_gate.py",
    "backend/scripts/continuous_batch_tier_advisor.py",
    "backend/scripts/continuous_batch_triage.py",
    "backend/scripts/continuous_batch_latest_report.py",
]


def _check_scripts(repo_root: Path) -> list[str]:
    issues: list[str] = []
    for rel in REQUIRED_SCRIPTS:
        if not (repo_root / rel).is_file():
            issues.append(f"missing script: {rel}")
    return issues


def _check_output_root(repo_root: Path, output_root: str) -> list[str]:
    issues: list[str] = []
    out = (repo_root / output_root).resolve()
    try:
        out.mkdir(parents=True, exist_ok=True)
        probe = out / ".doctor_write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except Exception as e:
        issues.append(f"output root not writable: {out} ({e})")
    return issues


def _check_api(base_url: str, timeout_seconds: float, api_key: str, api_key_header: str) -> list[str]:
    issues: list[str] = []
    headers = build_request_headers(api_key=api_key, api_key_header=api_key_header)
    try:
        resp: dict[str, Any] = http_get_json(
            f"{base_url.rstrip('/')}/api/system/config",
            timeout=timeout_seconds,
            request_headers=headers,
        )
        if not isinstance(resp, dict):
            issues.append("api check failed: /api/system/config response not json object")
    except Exception as e:
        issues.append(f"api check failed: {e}")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="连续批处理 doctor 预检")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--output-root", default="backend/data/benchmarks/pipeline")
    parser.add_argument("--check-api", action="store_true")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--timeout-seconds", type=float, default=10.0)
    parser.add_argument("--api-key", default="")
    parser.add_argument("--api-key-header", default="X-Api-Key")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    issues: list[str] = []
    issues.extend(_check_scripts(repo_root))
    issues.extend(_check_output_root(repo_root, str(args.output_root)))
    if args.check_api:
        issues.extend(
            _check_api(
                base_url=str(args.base_url),
                timeout_seconds=float(args.timeout_seconds),
                api_key=str(args.api_key),
                api_key_header=str(args.api_key_header),
            )
        )

    if issues:
        print("DOCTOR_FAIL")
        for issue in issues:
            print(f"- {issue}")
        return 2

    print("DOCTOR_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
