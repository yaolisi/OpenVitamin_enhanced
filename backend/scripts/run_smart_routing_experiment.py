#!/usr/bin/env python3
"""
一键执行智能路由实验：
1) 读取当前策略作为 baseline
2) 应用 candidate 策略
3) 分别跑 baseline / candidate 压测并生成报告
4) 自动执行报告对比
5) 可选恢复原策略
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

try:
    from scripts._http_utils import build_request_headers, http_get_json, http_post_json
except Exception:
    from _http_utils import build_request_headers, http_get_json, http_post_json  # type: ignore[no-redef]


def _get_current_policy_text(base_url: str, request_headers: dict[str, str]) -> str:
    cfg = http_get_json(f"{base_url.rstrip('/')}/api/system/config", request_headers=request_headers)
    settings = cfg.get("settings", {}) if isinstance(cfg, dict) else {}
    text = str((settings or {}).get("inferenceSmartRoutingPoliciesJson", "") or "")
    return text


def _set_policy_text(base_url: str, policy_text: str, request_headers: dict[str, str]) -> None:
    payload = {
        "inferenceSmartRoutingEnabled": True,
        "inferenceSmartRoutingPoliciesJson": policy_text,
    }
    http_post_json(
        f"{base_url.rstrip('/')}/api/system/config",
        payload,
        request_headers=request_headers,
    )


def _run_cmd(cmd: list[str], cwd: Path) -> None:
    print(f"[experiment] run: {' '.join(cmd)}")
    subprocess.run(cmd, cwd=str(cwd), check=True)


def _load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_report(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _summary(report: dict[str, Any]) -> dict[str, float]:
    summary = report.get("summary", {}) if isinstance(report, dict) else {}
    return {
        "success_rate": float(summary.get("success_rate", 0.0) or 0.0),
        "avg_latency_ms": float(summary.get("avg_latency_ms", 0.0) or 0.0),
        "realized_qps": float(summary.get("realized_qps", 0.0) or 0.0),
    }


def _is_candidate_better(
    *,
    baseline_report: dict[str, Any],
    current_report: dict[str, Any],
    min_success_rate_delta: float,
    max_latency_delta_ms: float,
    min_qps_delta: float,
) -> tuple[bool, list[str]]:
    b = _summary(baseline_report)
    c = _summary(current_report)
    success_delta = c["success_rate"] - b["success_rate"]
    latency_delta = c["avg_latency_ms"] - b["avg_latency_ms"]
    qps_delta = c["realized_qps"] - b["realized_qps"]

    checks = [
        (
            success_delta >= min_success_rate_delta,
            f"success_delta={success_delta:+.4f} (required >= {min_success_rate_delta:+.4f})",
        ),
        (
            latency_delta <= max_latency_delta_ms,
            f"latency_delta_ms={latency_delta:+.2f} (required <= {max_latency_delta_ms:+.2f})",
        ),
        (
            qps_delta >= min_qps_delta,
            f"qps_delta={qps_delta:+.2f} (required >= {min_qps_delta:+.2f})",
        ),
    ]
    reasons = [msg for _, msg in checks]
    return all(ok for ok, _ in checks), reasons


def _acceptance_ok(report: dict[str, Any]) -> bool:
    acceptance = report.get("acceptance", {}) if isinstance(report, dict) else {}
    return bool((acceptance or {}).get("ok", False))


def _write_promote_report(path: str, payload: dict[str, Any]) -> None:
    out = os.path.abspath(path)
    parent = os.path.dirname(out)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"[experiment] promote report saved: {out}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="一键智能路由实验")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--model", required=True, help="压测 model/alias")
    parser.add_argument("--candidate-policy-file", required=True, help="candidate 策略 JSON 文件路径")
    parser.add_argument("--output-dir", default="./tmp/smart-routing-exp", help="实验输出目录")
    parser.add_argument("--duration-seconds", type=int, default=60)
    parser.add_argument("--rps", type=int, default=8)
    parser.add_argument("--concurrency", type=int, default=16)
    parser.add_argument("--large-ratio", type=float, default=0.6)
    parser.add_argument("--min-success-rate", type=float, default=0.95)
    parser.add_argument("--max-avg-latency-ms", type=float, default=2500.0)
    parser.add_argument("--min-gpu-ratio", type=float, default=0.0)
    parser.add_argument("--min-cpu-ratio", type=float, default=0.0)
    parser.add_argument("--min-fallback-ratio", type=float, default=0.0)
    parser.add_argument("--keep-candidate-policy", action="store_true", help="实验结束后保留 candidate 策略")
    parser.add_argument("--promote-only-if-better", action="store_true", help="仅当 candidate 指标优于 baseline 才保留 candidate 策略")
    parser.add_argument("--promote-require-pass", action="store_true", help="推广前要求 current 报告 acceptance.ok=true")
    parser.add_argument("--min-success-rate-delta", type=float, default=0.0, help="promote 判定：candidate-success - baseline-success 最小增量")
    parser.add_argument("--max-latency-delta-ms", type=float, default=0.0, help="promote 判定：candidate-latency - baseline-latency 最大增量（<=0 表示不允许更慢）")
    parser.add_argument("--min-qps-delta", type=float, default=0.0, help="promote 判定：candidate-qps - baseline-qps 最小增量")
    parser.add_argument("--promote-report-file", default="", help="可选：将推广决策写入 JSON 文件")
    parser.add_argument("--fail-on-no-promote", action="store_true", help="若最终未推广 candidate，则脚本返回非 0")
    parser.add_argument("--api-key", default="", help="可选：请求鉴权 API Key")
    parser.add_argument("--api-key-header", default="X-Api-Key", help="可选：鉴权 Header 名（默认 X-Api-Key）")
    return parser


def _build_request_headers(api_key: str, api_key_header: str) -> dict[str, str]:
    return build_request_headers(api_key=api_key, api_key_header=api_key_header)


def _run_load_test_script(
    *,
    script_dir: Path,
    args: Any,
    report_file: Path,
) -> None:
    _run_cmd(
        [
            sys.executable,
            str(script_dir / "smart_routing_load_test.py"),
            "--base-url",
            args.base_url,
            "--model",
            args.model,
            "--duration-seconds",
            str(args.duration_seconds),
            "--rps",
            str(args.rps),
            "--concurrency",
            str(args.concurrency),
            "--large-ratio",
            str(args.large_ratio),
            "--min-success-rate",
            str(args.min_success_rate),
            "--max-avg-latency-ms",
            str(args.max_avg_latency_ms),
            "--min-gpu-ratio",
            str(args.min_gpu_ratio),
            "--min-cpu-ratio",
            str(args.min_cpu_ratio),
            "--min-fallback-ratio",
            str(args.min_fallback_ratio),
            "--report-file",
            str(report_file),
            "--api-key",
            str(args.api_key or ""),
            "--api-key-header",
            str(args.api_key_header or "X-Api-Key"),
        ],
        cwd=script_dir.parent,
    )


def _evaluate_promote(
    *,
    args: Any,
    baseline_report: Path,
    current_report: Path,
    keep_candidate: bool,
) -> tuple[bool, list[str], bool]:
    promote_reasons: list[str] = []
    promote_pass_ok = False
    result_keep = bool(keep_candidate)
    if bool(args.promote_only_if_better):
        baseline_report_data = _read_report(baseline_report)
        current_report_data = _read_report(current_report)
        better, reasons = _is_candidate_better(
            baseline_report=baseline_report_data,
            current_report=current_report_data,
            min_success_rate_delta=float(args.min_success_rate_delta),
            max_latency_delta_ms=float(args.max_latency_delta_ms),
            min_qps_delta=float(args.min_qps_delta),
        )
        print("[experiment] promote decision:")
        for line in reasons:
            print(f"  - {line}")
        promote_reasons = list(reasons)
        result_keep = bool(better)
        print(f"[experiment] promote_only_if_better => keep_candidate_policy={result_keep}")
    if bool(args.promote_require_pass):
        current_report_data = _read_report(current_report)
        pass_ok = _acceptance_ok(current_report_data)
        promote_pass_ok = bool(pass_ok)
        print(f"[experiment] promote_require_pass => acceptance.ok={pass_ok}")
        result_keep = bool(result_keep and pass_ok)
        print(f"[experiment] promote_require_pass => keep_candidate_policy={result_keep}")
    return result_keep, promote_reasons, promote_pass_ok


def main() -> int:
    args = _build_parser().parse_args()
    request_headers = _build_request_headers(
        str(args.api_key or ""),
        str(args.api_key_header or "X-Api-Key"),
    )

    script_dir = Path(__file__).resolve().parent
    out_dir = Path(args.output_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    baseline_policy_file = out_dir / "baseline-policy.json"
    baseline_report = out_dir / "baseline-report.json"
    current_report = out_dir / "current-report.json"

    baseline_text = _get_current_policy_text(args.base_url, request_headers=request_headers)
    baseline_policy_file.write_text(baseline_text, encoding="utf-8")
    print(f"[experiment] baseline policy saved: {baseline_policy_file}")

    candidate_policy_text = _load_text(Path(args.candidate_policy_file).expanduser().resolve())

    keep_candidate = bool(args.keep_candidate_policy)
    promote_reasons: list[str] = []
    promote_pass_ok = False
    try:
        _run_load_test_script(script_dir=script_dir, args=args, report_file=baseline_report)

        # switch to candidate policy
        _set_policy_text(args.base_url, candidate_policy_text, request_headers=request_headers)
        print("[experiment] candidate policy applied")

        # candidate run
        _run_load_test_script(script_dir=script_dir, args=args, report_file=current_report)

        # compare
        _run_cmd(
            [
                sys.executable,
                str(script_dir / "compare_smart_routing_reports.py"),
                "--baseline",
                str(baseline_report),
                "--current",
                str(current_report),
            ],
            cwd=script_dir.parent,
        )

        keep_candidate, promote_reasons, promote_pass_ok = _evaluate_promote(
            args=args,
            baseline_report=baseline_report,
            current_report=current_report,
            keep_candidate=keep_candidate,
        )
    finally:
        if not keep_candidate:
            _set_policy_text(args.base_url, baseline_text, request_headers=request_headers)
            print("[experiment] policy restored to baseline")

    if str(args.promote_report_file or "").strip():
        baseline_report_data = _read_report(baseline_report) if baseline_report.exists() else {}
        current_report_data = _read_report(current_report) if current_report.exists() else {}
        promote_payload = {
            "generated_at_epoch": time.time(),
            "inputs": {
                "base_url": args.base_url,
                "model": args.model,
                "candidate_policy_file": args.candidate_policy_file,
                "promote_only_if_better": bool(args.promote_only_if_better),
                "promote_require_pass": bool(args.promote_require_pass),
                "min_success_rate_delta": float(args.min_success_rate_delta),
                "max_latency_delta_ms": float(args.max_latency_delta_ms),
                "min_qps_delta": float(args.min_qps_delta),
            },
            "reports": {
                "baseline_report": str(baseline_report),
                "current_report": str(current_report),
            },
            "summary": {
                "baseline": _summary(baseline_report_data),
                "current": _summary(current_report_data),
            },
            "decision": {
                "keep_candidate_policy": bool(keep_candidate),
                "promote_reasons": list(promote_reasons),
                "promote_pass_ok": bool(promote_pass_ok),
            },
        }
        _write_promote_report(str(args.promote_report_file), promote_payload)

    print(f"[experiment] done, outputs in: {out_dir}")
    if bool(args.fail_on_no_promote) and not bool(keep_candidate):
        print("[experiment] fail-on-no-promote: candidate not promoted, exiting with code 2")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
