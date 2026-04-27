#!/usr/bin/env python3
"""
连续批处理与异步执行基准脚本。

对比三种模式：
1) sync_no_batch: 同步 + 关闭连续批处理
2) sync_batch: 同步 + 开启连续批处理
3) async_batch: 异步提交 + 开启连续批处理
"""
from __future__ import annotations

import argparse
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any
from urllib import parse

try:
    from scripts._http_utils import build_request_headers, http_get_json, http_post_json_with_status
except Exception:
    from _http_utils import build_request_headers, http_get_json, http_post_json_with_status  # type: ignore[no-redef]


@dataclass
class BenchResult:
    name: str
    total: int
    success: int
    failed: int
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    throughput_rps: float
    first_response_ms: float
    wall_time_s: float


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    arr = sorted(values)
    idx = int(round((len(arr) - 1) * q))
    idx = max(0, min(len(arr) - 1, idx))
    return float(arr[idx])


def _post_config(base_url: str, payload: dict[str, Any], timeout: float, headers: dict[str, str]) -> None:
    code, body, _ = http_post_json_with_status(
        f"{base_url.rstrip('/')}/api/system/config",
        payload,
        timeout=timeout,
        request_headers=headers,
    )
    if code < 200 or code >= 300:
        raise RuntimeError(f"update config failed: code={code}, body={body}")


def _build_payload(model: str, i: int) -> dict[str, Any]:
    return {
        "model": model,
        "stream": False,
        "messages": [{"role": "user", "content": f"请用一句话解释什么是动态批处理。#{i}"}],
    }


def _run_sync_case(
    *,
    name: str,
    base_url: str,
    model: str,
    total_requests: int,
    concurrency: int,
    timeout_seconds: float,
    headers: dict[str, str],
) -> BenchResult:
    latencies: list[float] = []
    lock = threading.Lock()
    success = 0
    failed = 0
    first_response_ms = 0.0
    started = time.perf_counter()

    def _one(idx: int) -> None:
        nonlocal success, failed, first_response_ms
        code, _, elapsed = http_post_json_with_status(
            f"{base_url.rstrip('/')}/v1/chat/completions",
            _build_payload(model, idx),
            timeout=timeout_seconds,
            request_headers=headers,
        )
        with lock:
            if first_response_ms <= 0:
                first_response_ms = elapsed
            latencies.append(elapsed)
            if 200 <= code < 300:
                success += 1
            else:
                failed += 1

    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        futures = [pool.submit(_one, i) for i in range(total_requests)]
        for fut in as_completed(futures):
            fut.result()
    wall = max(1e-6, time.perf_counter() - started)
    return BenchResult(
        name=name,
        total=total_requests,
        success=success,
        failed=failed,
        avg_latency_ms=(sum(latencies) / len(latencies)) if latencies else 0.0,
        p50_latency_ms=_percentile(latencies, 0.5),
        p95_latency_ms=_percentile(latencies, 0.95),
        throughput_rps=float(success) / wall,
        first_response_ms=first_response_ms,
        wall_time_s=wall,
    )


def _poll_async_result(base_url: str, request_id: str, timeout_seconds: float, headers: dict[str, str]) -> tuple[bool, float]:
    started = time.perf_counter()
    while True:
        url = f"{base_url.rstrip('/')}/v1/chat/completions/async/{parse.quote(request_id)}"
        resp = http_get_json(url, timeout=timeout_seconds, request_headers=headers)
        status = str(resp.get("status") or "")
        if status == "succeeded":
            return True, (time.perf_counter() - started) * 1000.0
        if status == "failed":
            return False, (time.perf_counter() - started) * 1000.0
        if time.perf_counter() - started > timeout_seconds:
            return False, (time.perf_counter() - started) * 1000.0
        time.sleep(0.05)


def _run_async_case(
    *,
    name: str,
    base_url: str,
    model: str,
    total_requests: int,
    concurrency: int,
    timeout_seconds: float,
    headers: dict[str, str],
) -> BenchResult:
    latencies: list[float] = []
    lock = threading.Lock()
    success = 0
    failed = 0
    first_response_ms = 0.0
    started = time.perf_counter()

    def _one(idx: int) -> None:
        nonlocal success, failed, first_response_ms
        code, body, submit_ms = http_post_json_with_status(
            f"{base_url.rstrip('/')}/v1/chat/completions/async",
            _build_payload(model, idx),
            timeout=timeout_seconds,
            request_headers=headers,
        )
        with lock:
            if first_response_ms <= 0:
                first_response_ms = submit_ms
        if code < 200 or code >= 300:
            with lock:
                failed += 1
            return
        request_id = str((body or {}).get("request_id") or "")
        if not request_id:
            with lock:
                failed += 1
            return
        ok, poll_ms = _poll_async_result(base_url, request_id, timeout_seconds, headers)
        with lock:
            latencies.append(poll_ms)
            if ok:
                success += 1
            else:
                failed += 1

    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        futures = [pool.submit(_one, i) for i in range(total_requests)]
        for fut in as_completed(futures):
            fut.result()
    wall = max(1e-6, time.perf_counter() - started)
    return BenchResult(
        name=name,
        total=total_requests,
        success=success,
        failed=failed,
        avg_latency_ms=(sum(latencies) / len(latencies)) if latencies else 0.0,
        p50_latency_ms=_percentile(latencies, 0.5),
        p95_latency_ms=_percentile(latencies, 0.95),
        throughput_rps=float(success) / wall,
        first_response_ms=first_response_ms,
        wall_time_s=wall,
    )


def _print_result(r: BenchResult) -> None:
    print(f"[{r.name}] total={r.total} success={r.success} failed={r.failed}")
    print(
        f"[{r.name}] avg={r.avg_latency_ms:.2f}ms p50={r.p50_latency_ms:.2f}ms "
        f"p95={r.p95_latency_ms:.2f}ms first={r.first_response_ms:.2f}ms "
        f"throughput={r.throughput_rps:.2f} rps wall={r.wall_time_s:.2f}s"
    )


def _summary(a: BenchResult, b: BenchResult, c: BenchResult) -> dict[str, Any]:
    def _safe_ratio(new: float, old: float) -> float:
        if old <= 0:
            return 0.0
        return new / old

    return {
        "sync_no_batch": a.__dict__,
        "sync_batch": b.__dict__,
        "async_batch": c.__dict__,
        "improvement": {
            "sync_batch_vs_sync_no_batch_throughput_ratio": round(_safe_ratio(b.throughput_rps, a.throughput_rps), 4),
            "sync_batch_vs_sync_no_batch_first_response_ratio": round(_safe_ratio(b.first_response_ms, a.first_response_ms), 4),
            "async_batch_vs_sync_no_batch_throughput_ratio": round(_safe_ratio(c.throughput_rps, a.throughput_rps), 4),
            "async_batch_vs_sync_no_batch_first_response_ratio": round(_safe_ratio(c.first_response_ms, a.first_response_ms), 4),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="连续批处理与异步执行基准测试")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--model", required=True)
    parser.add_argument("--requests", type=int, default=60)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--timeout-seconds", type=float, default=90.0)
    parser.add_argument("--batch-wait-ms", type=int, default=12)
    parser.add_argument("--batch-max-size", type=int, default=8)
    parser.add_argument("--report-file", default="")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--api-key-header", default="X-Api-Key")
    args = parser.parse_args()

    headers = build_request_headers(api_key=str(args.api_key or ""), api_key_header=str(args.api_key_header or "X-Api-Key"))
    base_url = str(args.base_url).rstrip("/")
    timeout = float(args.timeout_seconds)
    requests = max(1, int(args.requests))
    concurrency = max(1, int(args.concurrency))

    # 1) 关闭批处理 -> 同步基线
    _post_config(base_url, {"continuousBatchEnabled": False}, timeout=timeout, headers=headers)
    baseline = _run_sync_case(
        name="sync_no_batch",
        base_url=base_url,
        model=args.model,
        total_requests=requests,
        concurrency=concurrency,
        timeout_seconds=timeout,
        headers=headers,
    )
    _print_result(baseline)

    # 2) 开启批处理 -> 同步对比
    _post_config(
        base_url,
        {
            "continuousBatchEnabled": True,
            "continuousBatchWaitMs": int(args.batch_wait_ms),
            "continuousBatchMaxSize": int(args.batch_max_size),
        },
        timeout=timeout,
        headers=headers,
    )
    sync_batch = _run_sync_case(
        name="sync_batch",
        base_url=base_url,
        model=args.model,
        total_requests=requests,
        concurrency=concurrency,
        timeout_seconds=timeout,
        headers=headers,
    )
    _print_result(sync_batch)

    # 3) 开启批处理 -> 异步提交对比
    async_batch = _run_async_case(
        name="async_batch",
        base_url=base_url,
        model=args.model,
        total_requests=requests,
        concurrency=concurrency,
        timeout_seconds=timeout,
        headers=headers,
    )
    _print_result(async_batch)

    # 拉取 runtime metrics 快照，便于核对 batch 指标
    metrics = http_get_json(f"{base_url}/api/system/runtime-metrics", timeout=timeout, request_headers=headers)
    print("[runtime-metrics] fetched")

    report = _summary(baseline, sync_batch, async_batch)
    report["runtime_metrics"] = metrics
    print(json.dumps(report["improvement"], ensure_ascii=False))

    report_file = str(args.report_file or "").strip()
    if report_file:
        out = os.path.abspath(report_file)
        parent = os.path.dirname(out)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            f.write(json.dumps(report, ensure_ascii=False, indent=2))
        print(f"[report] {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
