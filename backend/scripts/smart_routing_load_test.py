#!/usr/bin/env python3
"""
智能路由压测脚本（持续压测 + 路由分布统计）。

示例：
  cd backend && python scripts/smart_routing_load_test.py \
    --base-url http://127.0.0.1:8000 \
    --model ollama:deepseek-r1:32b \
    --duration-seconds 60 \
    --rps 5 \
    --concurrency 10
"""

from __future__ import annotations

import argparse
import json
import os
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any

try:
    from scripts._http_utils import (
        build_request_headers,
        http_get_json,
        http_post_json_with_status,
    )
except Exception:
    from _http_utils import (  # type: ignore[no-redef]
        build_request_headers,
        http_get_json,
        http_post_json_with_status,
    )


@dataclass
class RunStat:
    total: int = 0
    success: int = 0
    failed: int = 0
    latency_ms_total: float = 0.0

    def avg_latency_ms(self) -> float:
        if self.success <= 0:
            return 0.0
        return self.latency_ms_total / self.success


@dataclass
class AcceptanceResult:
    ok: bool
    details: list[str]


@dataclass
class RoutingContext:
    model_to_device: dict[str, str]


def _build_payload(model: str, user_id: str, large: bool) -> dict[str, Any]:
    if large:
        profile = "large"
        preferred = "gpu"
        input_tokens = 4096
        message = "请详细分析系统容量规划、SLO、告警阈值、灰度和回滚策略。"
    else:
        profile = "small"
        preferred = "cpu"
        input_tokens = 128
        message = "用两句话解释什么是熔断。"

    return {
        "model": model,
        "stream": False,
        "metadata": {
            "user_id": user_id,
            "inference_profile": profile,
            "preferred_device": preferred,
            "input_tokens": input_tokens,
        },
        "messages": [{"role": "user", "content": message}],
    }


def _single_request(
    *,
    base_url: str,
    model: str,
    user_id: str,
    large: bool,
    timeout_seconds: float,
    request_headers: dict[str, str],
) -> tuple[bool, float, str, str]:
    payload = _build_payload(model=model, user_id=user_id, large=large)
    code, body, elapsed_ms = http_post_json_with_status(
        f"{base_url.rstrip('/')}/v1/chat/completions",
        payload,
        timeout=timeout_seconds,
        request_headers=request_headers,
    )
    metadata = body.get("metadata", {}) if isinstance(body, dict) else {}
    resolved_via = str(metadata.get("resolved_via", "unknown"))
    resolved_model = str(metadata.get("resolved_model", "unknown"))
    return 200 <= code < 300, elapsed_ms, resolved_via, resolved_model


def _fetch_runtime_metrics(base_url: str, timeout_seconds: float, request_headers: dict[str, str]) -> dict[str, Any]:
    return http_get_json(
        f"{base_url.rstrip('/')}/api/system/runtime-metrics",
        timeout=timeout_seconds,
        request_headers=request_headers,
    )


def _fetch_system_config(base_url: str, timeout_seconds: float, request_headers: dict[str, str]) -> dict[str, Any]:
    return http_get_json(
        f"{base_url.rstrip('/')}/api/system/config",
        timeout=timeout_seconds,
        request_headers=request_headers,
    )


def _load_routing_context(
    base_url: str,
    timeout_seconds: float,
    model_alias: str,
    request_headers: dict[str, str],
) -> RoutingContext:
    try:
        cfg = _fetch_system_config(
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            request_headers=request_headers,
        )
        return _extract_routing_context(cfg=cfg, model_alias=model_alias)
    except Exception:
        return RoutingContext(model_to_device={})


def _extract_routing_context(cfg: dict[str, Any], model_alias: str) -> RoutingContext:
    settings = cfg.get("settings", {}) if isinstance(cfg, dict) else {}
    raw_policy = str((settings or {}).get("inferenceSmartRoutingPoliciesJson", "") or "").strip()
    if not raw_policy:
        return RoutingContext(model_to_device={})
    candidates = _extract_candidates(raw_policy=raw_policy, model_alias=model_alias)
    if not isinstance(candidates, list):
        return RoutingContext(model_to_device={})
    model_to_device: dict[str, str] = {}
    for item in candidates:
        if not isinstance(item, dict):
            continue
        target = str(item.get("target") or item.get("model_id") or "").strip()
        device = str(item.get("device") or "").strip().lower()
        if target and device:
            model_to_device[target] = device
    return RoutingContext(model_to_device=model_to_device)


def _extract_candidates(raw_policy: str, model_alias: str) -> Any:
    try:
        policy_all = json.loads(raw_policy)
    except Exception:
        return None
    if not isinstance(policy_all, dict):
        return None
    policy = policy_all.get(model_alias)
    if not isinstance(policy, dict):
        return None
    return policy.get("candidates")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="智能路由压测（持续负载 + 路由统计）")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="后端地址")
    parser.add_argument("--model", required=True, help="请求使用的 model/alias")
    parser.add_argument("--duration-seconds", type=int, default=60, help="压测时长（秒）")
    parser.add_argument("--rps", type=int, default=5, help="每秒请求数")
    parser.add_argument("--concurrency", type=int, default=10, help="并发线程上限")
    parser.add_argument("--timeout-seconds", type=float, default=90.0, help="单请求超时")
    parser.add_argument("--large-ratio", type=float, default=0.5, help="大输入占比（0-1）")
    parser.add_argument("--min-success-rate", type=float, default=0.95, help="验收：最小成功率（0-1）")
    parser.add_argument("--max-avg-latency-ms", type=float, default=0.0, help="验收：最大平均延迟，<=0 表示不检查")
    parser.add_argument("--min-gpu-ratio", type=float, default=0.0, help="验收：最小 GPU 命中占比（按策略中的 device 映射统计）")
    parser.add_argument("--min-cpu-ratio", type=float, default=0.0, help="验收：最小 CPU 命中占比")
    parser.add_argument("--min-fallback-ratio", type=float, default=0.0, help="验收：最小 fallback 占比（按 resolved_via 含 fallback 统计）")
    parser.add_argument("--report-file", default="", help="可选：将压测报告写入 JSON 文件")
    parser.add_argument("--api-key", default="", help="可选：请求鉴权 API Key")
    parser.add_argument("--api-key-header", default="X-Api-Key", help="可选：鉴权 Header 名（默认 X-Api-Key）")
    return parser


def _print_routing_context(context: RoutingContext) -> None:
    if context.model_to_device:
        print("[smart-routing-load-test] routing device map loaded:")
        for model_id, device in sorted(context.model_to_device.items()):
            print(f"  {model_id} -> {device}")
        return
    print("[smart-routing-load-test] routing device map unavailable, gpu/cpu ratio checks may be skipped")


def _write_report_file(report_file: str, payload: dict[str, Any]) -> None:
    out = os.path.abspath(report_file)
    parent = os.path.dirname(out)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"[smart-routing-load-test] report saved: {out}")


def _match_ratio(counter: Counter[str], keyword: str) -> float:
    total = sum(counter.values())
    if total <= 0:
        return 0.0
    matched = sum(v for k, v in counter.items() if keyword in str(k).lower())
    return matched / total


def _device_ratio(model_counter: Counter[str], context: RoutingContext, device: str) -> float:
    total = sum(model_counter.values())
    if total <= 0:
        return 0.0
    dev = str(device or "").strip().lower()
    if not dev:
        return 0.0
    matched = 0
    for model_id, count in model_counter.items():
        if context.model_to_device.get(str(model_id), "") == dev:
            matched += count
    return matched / total


def _evaluate_acceptance(
    *,
    stat: RunStat,
    via_counter: Counter[str],
    model_counter: Counter[str],
    min_success_rate: float,
    max_avg_latency_ms: float,
    min_gpu_ratio: float,
    min_cpu_ratio: float,
    min_fallback_ratio: float,
    routing_context: RoutingContext,
) -> AcceptanceResult:
    details: list[str] = []
    success_rate = (stat.success / stat.total) if stat.total > 0 else 0.0
    avg_latency = stat.avg_latency_ms()
    gpu_ratio = _device_ratio(model_counter, routing_context, "gpu")
    cpu_ratio = _device_ratio(model_counter, routing_context, "cpu")
    fallback_ratio = _match_ratio(via_counter, "fallback")

    checks = [
        _check_min("success_rate", success_rate, min_success_rate, 4),
        _check_max("avg_latency_ms", avg_latency, max_avg_latency_ms, 2),
        _check_min("gpu_ratio", gpu_ratio, min_gpu_ratio, 4),
        _check_min("cpu_ratio", cpu_ratio, min_cpu_ratio, 4),
        _check_min("fallback_ratio", fallback_ratio, min_fallback_ratio, 4),
    ]
    for item in checks:
        details.append(item["message"])
    ok = all(bool(item["ok"]) for item in checks)
    return AcceptanceResult(ok=ok, details=details)


def _check_min(name: str, value: float, required: float, digits: int) -> dict[str, Any]:
    if required <= 0:
        return {"ok": True, "message": f"{name} check skipped (required <= 0)"}
    ok = value >= required
    op = ">=" if ok else "<"
    return {
        "ok": ok,
        "message": f"{name}={value:.{digits}f} {op} required {required:.{digits}f}",
    }


def _check_max(name: str, value: float, limit: float, digits: int) -> dict[str, Any]:
    if limit <= 0:
        return {"ok": True, "message": f"{name} check skipped (limit <= 0)"}
    ok = value <= limit
    op = "<=" if ok else ">"
    return {
        "ok": ok,
        "message": f"{name}={value:.{digits}f} {op} limit {limit:.{digits}f}",
    }


def _build_report_payload(
    *,
    args: Any,
    duration_seconds: int,
    rps: int,
    concurrency: int,
    large_ratio: float,
    stat: RunStat,
    success_rate: float,
    qps_real: float,
    routing_context: RoutingContext,
    via_counter: Counter[str],
    model_counter: Counter[str],
    runtime_metrics: dict[str, Any],
    acceptance: AcceptanceResult,
) -> dict[str, Any]:
    return {
        "generated_at_epoch": time.time(),
        "config": {
            "base_url": args.base_url,
            "model": args.model,
            "duration_seconds": duration_seconds,
            "rps": rps,
            "concurrency": concurrency,
            "large_ratio": large_ratio,
            "timeout_seconds": float(args.timeout_seconds),
            "acceptance_thresholds": {
                "min_success_rate": float(args.min_success_rate),
                "max_avg_latency_ms": float(args.max_avg_latency_ms),
                "min_gpu_ratio": float(args.min_gpu_ratio),
                "min_cpu_ratio": float(args.min_cpu_ratio),
                "min_fallback_ratio": float(args.min_fallback_ratio),
            },
        },
        "summary": {
            "total": stat.total,
            "success": stat.success,
            "failed": stat.failed,
            "success_rate": success_rate,
            "avg_latency_ms": stat.avg_latency_ms(),
            "realized_qps": qps_real,
        },
        "routing_context": {"model_to_device": dict(routing_context.model_to_device)},
        "distribution": {
            "resolved_via": dict(via_counter),
            "resolved_model": dict(model_counter),
        },
        "runtime_metrics": runtime_metrics,
        "acceptance": {"ok": acceptance.ok, "details": list(acceptance.details)},
    }


def _print_runtime_metrics(
    base_url: str,
    timeout_seconds: float,
    request_headers: dict[str, str],
) -> dict[str, Any]:
    print("")
    print("runtime-metrics snapshot:")
    runtime_metrics: dict[str, Any] = {}
    try:
        runtime_metrics = _fetch_runtime_metrics(
            base_url,
            timeout_seconds=timeout_seconds,
            request_headers=request_headers,
        )
        print(json.dumps(runtime_metrics, ensure_ascii=False))
    except Exception as exc:
        print(f"  failed to fetch /api/system/runtime-metrics: {exc}")
    return runtime_metrics


def _maybe_write_report(args: Any, payload: dict[str, Any]) -> None:
    if str(args.report_file or "").strip():
        _write_report_file(str(args.report_file), payload)


def _build_request_headers(api_key: str, api_key_header: str) -> dict[str, str]:
    return build_request_headers(api_key=api_key, api_key_header=api_key_header)


def _run_load(
    *,
    base_url: str,
    model: str,
    timeout_seconds: float,
    large_ratio: float,
    duration_seconds: int,
    rps: int,
    concurrency: int,
    request_headers: dict[str, str],
) -> tuple[RunStat, Counter[str], Counter[str], float]:
    stat = RunStat()
    via_counter: Counter[str] = Counter()
    model_counter: Counter[str] = Counter()
    lock = threading.Lock()
    total_planned = duration_seconds * rps

    def _run_one(i: int) -> None:
        large = (i % 100) < int(large_ratio * 100)
        ok, latency_ms, resolved_via, resolved_model = _single_request(
            base_url=base_url,
            model=model,
            user_id=f"smart-route-user-{i}",
            large=large,
            timeout_seconds=timeout_seconds,
            request_headers=request_headers,
        )
        with lock:
            stat.total += 1
            if ok:
                stat.success += 1
                stat.latency_ms_total += latency_ms
            else:
                stat.failed += 1
            via_counter[resolved_via] += 1
            model_counter[resolved_model] += 1

    started = time.time()
    sent = 0
    futures = []
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        while sent < total_planned:
            elapsed = time.time() - started
            expected = min(total_planned, int(elapsed * rps))
            to_send = max(0, expected - sent)
            for _ in range(to_send):
                futures.append(pool.submit(_run_one, sent))
                sent += 1
            time.sleep(0.02)
        for fut in as_completed(futures):
            fut.result()
    wall_time = max(0.001, time.time() - started)
    return stat, via_counter, model_counter, wall_time


def main() -> int:
    args = _build_parser().parse_args()
    request_headers = _build_request_headers(str(args.api_key or ""), str(args.api_key_header or "X-Api-Key"))

    duration_seconds = max(1, int(args.duration_seconds))
    rps = max(1, int(args.rps))
    concurrency = max(1, int(args.concurrency))
    large_ratio = min(1.0, max(0.0, float(args.large_ratio)))

    total_planned = duration_seconds * rps
    print(f"[smart-routing-load-test] plan={total_planned} duration={duration_seconds}s rps={rps} concurrency={concurrency}")
    print(f"[smart-routing-load-test] model={args.model} large_ratio={large_ratio}")
    routing_context = _load_routing_context(
        base_url=args.base_url,
        timeout_seconds=float(args.timeout_seconds),
        model_alias=args.model,
        request_headers=request_headers,
    )
    _print_routing_context(routing_context)

    stat, via_counter, model_counter, wall_time = _run_load(
        base_url=args.base_url,
        model=args.model,
        timeout_seconds=float(args.timeout_seconds),
        large_ratio=large_ratio,
        duration_seconds=duration_seconds,
        rps=rps,
        concurrency=concurrency,
        request_headers=request_headers,
    )
    qps_real = stat.total / wall_time
    success_rate = (stat.success / stat.total) if stat.total > 0 else 0.0

    print("")
    print("=== Load Test Summary ===")
    print(f"total={stat.total} success={stat.success} failed={stat.failed} success_rate={success_rate:.4f}")
    print(f"avg_latency_ms={stat.avg_latency_ms():.2f} realized_qps={qps_real:.2f}")
    print("")
    print("resolved_via distribution:")
    for key, count in via_counter.most_common():
        print(f"  {key}: {count}")
    print("")
    print("resolved_model distribution:")
    for key, count in model_counter.most_common():
        print(f"  {key}: {count}")

    runtime_metrics = _print_runtime_metrics(
        args.base_url,
        timeout_seconds=float(args.timeout_seconds),
        request_headers=request_headers,
    )

    acceptance = _evaluate_acceptance(
        stat=stat,
        via_counter=via_counter,
        model_counter=model_counter,
        min_success_rate=min(1.0, max(0.0, float(args.min_success_rate))),
        max_avg_latency_ms=float(args.max_avg_latency_ms),
        min_gpu_ratio=min(1.0, max(0.0, float(args.min_gpu_ratio))),
        min_cpu_ratio=min(1.0, max(0.0, float(args.min_cpu_ratio))),
        min_fallback_ratio=min(1.0, max(0.0, float(args.min_fallback_ratio))),
        routing_context=routing_context,
    )
    print("")
    print("=== Acceptance ===")
    print("PASS" if acceptance.ok else "FAIL")
    for line in acceptance.details:
        print(f"  - {line}")

    _maybe_write_report(
        args,
        _build_report_payload(
            args=args,
            duration_seconds=duration_seconds,
            rps=rps,
            concurrency=concurrency,
            large_ratio=large_ratio,
            stat=stat,
            success_rate=success_rate,
            qps_real=qps_real,
            routing_context=routing_context,
            via_counter=via_counter,
            model_counter=model_counter,
            runtime_metrics=runtime_metrics,
            acceptance=acceptance,
        ),
    )

    return 0 if acceptance.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
