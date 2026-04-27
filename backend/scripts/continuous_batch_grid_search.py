#!/usr/bin/env python3
"""
连续批处理参数网格搜索脚本。

功能：
1) 批量运行 continuous_batch_benchmark.py
2) 汇总每组实验结果
3) 按目标（吞吐提升 + 首响应降低）排序，输出 Top-N
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from dataclasses import dataclass
from itertools import product
from typing import Any


@dataclass
class ExperimentCase:
    concurrency: int
    wait_ms: int
    max_size: int


def _parse_int_list(raw: str) -> list[int]:
    out: list[int] = []
    for part in (raw or "").split(","):
        s = part.strip()
        if not s:
            continue
        out.append(int(s))
    return sorted(set(out))


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _score(item: dict[str, Any]) -> float:
    # 越高越好：吞吐比高、首响应比低、成功率高
    imp = item.get("improvement", {}) if isinstance(item, dict) else {}
    summary = item.get("summary", {}) if isinstance(item, dict) else {}
    throughput_ratio = _safe_float(imp.get("sync_batch_vs_sync_no_batch_throughput_ratio"), 0.0)
    first_ratio = _safe_float(imp.get("sync_batch_vs_sync_no_batch_first_response_ratio"), 999.0)
    success_rate = _safe_float(summary.get("sync_batch_success_rate"), 0.0)
    # 惩罚首响应高于 1 的组合
    latency_term = 1.0 / max(0.05, first_ratio)
    return throughput_ratio * 0.65 + latency_term * 0.25 + success_rate * 0.10


def _run_case(
    *,
    repo_root: str,
    base_url: str,
    model: str,
    requests: int,
    concurrency: int,
    wait_ms: int,
    max_size: int,
    timeout_seconds: float,
    api_key: str,
    api_key_header: str,
    output_dir: str,
) -> dict[str, Any]:
    stamp = int(time.time() * 1000)
    report_file = os.path.join(
        output_dir,
        f"bench_c{concurrency}_w{wait_ms}_m{max_size}_{stamp}.json",
    )
    cmd = [
        "python",
        "backend/scripts/continuous_batch_benchmark.py",
        "--base-url",
        base_url,
        "--model",
        model,
        "--requests",
        str(requests),
        "--concurrency",
        str(concurrency),
        "--batch-wait-ms",
        str(wait_ms),
        "--batch-max-size",
        str(max_size),
        "--timeout-seconds",
        str(timeout_seconds),
        "--report-file",
        report_file,
    ]
    if api_key.strip():
        cmd.extend(["--api-key", api_key.strip(), "--api-key-header", api_key_header.strip() or "X-Api-Key"])

    started = time.perf_counter()
    proc = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True)
    elapsed = time.perf_counter() - started

    payload: dict[str, Any] = {
        "case": {"concurrency": concurrency, "wait_ms": wait_ms, "max_size": max_size},
        "ok": proc.returncode == 0,
        "returncode": int(proc.returncode),
        "elapsed_seconds": round(elapsed, 3),
        "report_file": report_file,
        "stdout_tail": (proc.stdout or "")[-3000:],
        "stderr_tail": (proc.stderr or "")[-3000:],
    }

    if os.path.isfile(report_file):
        try:
            with open(report_file, "r", encoding="utf-8") as f:
                report = json.load(f)
            imp = report.get("improvement", {}) if isinstance(report, dict) else {}
            s_no = report.get("sync_no_batch", {}) if isinstance(report, dict) else {}
            s_ba = report.get("sync_batch", {}) if isinstance(report, dict) else {}
            payload["improvement"] = {
                "sync_batch_vs_sync_no_batch_throughput_ratio": _safe_float(
                    imp.get("sync_batch_vs_sync_no_batch_throughput_ratio")
                ),
                "sync_batch_vs_sync_no_batch_first_response_ratio": _safe_float(
                    imp.get("sync_batch_vs_sync_no_batch_first_response_ratio")
                ),
            }
            payload["summary"] = {
                "sync_no_batch_success_rate": _safe_float(s_no.get("success"), 0.0)
                / max(1.0, _safe_float(s_no.get("total"), 0.0)),
                "sync_batch_success_rate": _safe_float(s_ba.get("success"), 0.0)
                / max(1.0, _safe_float(s_ba.get("total"), 0.0)),
                "sync_no_batch_first_response_ms": _safe_float(s_no.get("first_response_ms"), 0.0),
                "sync_batch_first_response_ms": _safe_float(s_ba.get("first_response_ms"), 0.0),
            }
            payload["score"] = _score(payload)
        except Exception as e:
            payload["parse_error"] = str(e)
            payload["score"] = 0.0
    else:
        payload["score"] = 0.0
    return payload


def _print_top(top: list[dict[str, Any]]) -> None:
    print("\n=== Top Candidates ===")
    for i, item in enumerate(top, start=1):
        case = item.get("case", {})
        imp = item.get("improvement", {})
        print(
            f"{i}. c={case.get('concurrency')} w={case.get('wait_ms')} m={case.get('max_size')} "
            f"score={_safe_float(item.get('score')):.4f} "
            f"thr={_safe_float(imp.get('sync_batch_vs_sync_no_batch_throughput_ratio')):.4f} "
            f"first={_safe_float(imp.get('sync_batch_vs_sync_no_batch_first_response_ratio')):.4f}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="连续批处理参数网格搜索")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--model", required=True)
    parser.add_argument("--requests", type=int, default=120)
    parser.add_argument("--concurrency-list", default="10,20,30")
    parser.add_argument("--wait-ms-list", default="4,8,12,16")
    parser.add_argument("--max-size-list", default="4,8,12")
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--output-dir", default="backend/data/benchmarks/grid")
    parser.add_argument("--summary-file", default="backend/data/benchmarks/grid/summary.json")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--api-key-header", default="X-Api-Key")
    args = parser.parse_args()

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    output_dir = os.path.abspath(os.path.join(repo_root, args.output_dir))
    os.makedirs(output_dir, exist_ok=True)

    conc_list = _parse_int_list(args.concurrency_list)
    wait_list = _parse_int_list(args.wait_ms_list)
    size_list = _parse_int_list(args.max_size_list)
    if not conc_list or not wait_list or not size_list:
        raise ValueError("concurrency/wait/max list 不能为空")

    cases = [ExperimentCase(c, w, m) for c, w, m in product(conc_list, wait_list, size_list)]
    print(f"[grid-search] total cases: {len(cases)}")

    results: list[dict[str, Any]] = []
    for idx, case in enumerate(cases, start=1):
        print(f"[{idx}/{len(cases)}] running c={case.concurrency} w={case.wait_ms} m={case.max_size}")
        r = _run_case(
            repo_root=repo_root,
            base_url=args.base_url,
            model=args.model,
            requests=max(1, int(args.requests)),
            concurrency=case.concurrency,
            wait_ms=case.wait_ms,
            max_size=case.max_size,
            timeout_seconds=float(args.timeout_seconds),
            api_key=str(args.api_key or ""),
            api_key_header=str(args.api_key_header or "X-Api-Key"),
            output_dir=output_dir,
        )
        results.append(r)

    ranked = sorted(results, key=lambda x: _safe_float(x.get("score"), 0.0), reverse=True)
    top_k = max(1, int(args.top_k))
    top = ranked[:top_k]
    _print_top(top)

    summary = {
        "generated_at_epoch": time.time(),
        "config": {
            "base_url": args.base_url,
            "model": args.model,
            "requests": int(args.requests),
            "concurrency_list": conc_list,
            "wait_ms_list": wait_list,
            "max_size_list": size_list,
            "timeout_seconds": float(args.timeout_seconds),
            "top_k": top_k,
        },
        "top": top,
        "all_results": ranked,
    }
    summary_file = os.path.abspath(os.path.join(repo_root, args.summary_file))
    os.makedirs(os.path.dirname(summary_file), exist_ok=True)
    with open(summary_file, "w", encoding="utf-8") as f:
        f.write(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\n[grid-search] summary: {summary_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
