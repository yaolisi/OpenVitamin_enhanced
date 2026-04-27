#!/usr/bin/env python3
"""
从 continuous_batch_grid_search 的 summary.json 生成推荐配置。

能力：
1) 读取 summary.json 的 top 结果
2) 按阈值筛选（吞吐提升、首响应比例）
3) 输出推荐 payload（可直接 POST /api/system/config）
4) 可选直接应用到后端配置接口
"""
from __future__ import annotations

import argparse
import json
import os
from typing import Any

try:
    from scripts._http_utils import build_request_headers, http_post_json_with_status
except Exception:
    from _http_utils import build_request_headers, http_post_json_with_status  # type: ignore[no-redef]


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _load_summary(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("summary 文件格式错误：根对象不是 JSON object")
    return data


def _pick_candidate(
    summary: dict[str, Any],
    *,
    min_throughput_ratio: float,
    max_first_ratio: float,
) -> dict[str, Any]:
    top = summary.get("top")
    all_results = summary.get("all_results")
    candidates = top if isinstance(top, list) and top else all_results
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("summary 中没有可用候选（top/all_results 为空）")

    # 先按阈值找第一个满足者（排名已由 grid_search 处理）
    for item in candidates:
        if not isinstance(item, dict):
            continue
        imp = item.get("improvement", {}) if isinstance(item.get("improvement"), dict) else {}
        thr = _safe_float(imp.get("sync_batch_vs_sync_no_batch_throughput_ratio"), 0.0)
        first = _safe_float(imp.get("sync_batch_vs_sync_no_batch_first_response_ratio"), 999.0)
        if thr >= min_throughput_ratio and first <= max_first_ratio:
            return item

    # 没有满足阈值时，退回排名第一
    first_item = candidates[0]
    if not isinstance(first_item, dict):
        raise ValueError("候选结果格式错误")
    return first_item


def _build_payload_from_case(case_item: dict[str, Any]) -> dict[str, Any]:
    case = case_item.get("case", {}) if isinstance(case_item.get("case"), dict) else {}
    wait_ms = int(case.get("wait_ms", 12) or 12)
    max_size = int(case.get("max_size", 8) or 8)
    return {
        "continuousBatchEnabled": True,
        "continuousBatchWaitMs": wait_ms,
        "continuousBatchMaxSize": max_size,
    }


def _apply_payload(base_url: str, payload: dict[str, Any], headers: dict[str, str], timeout_seconds: float) -> tuple[int, dict[str, Any]]:
    code, body, _ = http_post_json_with_status(
        f"{base_url.rstrip('/')}/api/system/config",
        payload,
        timeout=timeout_seconds,
        request_headers=headers,
    )
    return int(code), body if isinstance(body, dict) else {"raw": body}


def main() -> int:
    parser = argparse.ArgumentParser(description="根据网格搜索结果生成/应用连续批处理推荐配置")
    parser.add_argument(
        "--summary-file",
        default="backend/data/benchmarks/grid/summary.json",
        help="grid search 生成的 summary.json 路径",
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--min-throughput-ratio", type=float, default=1.5)
    parser.add_argument("--max-first-response-ratio", type=float, default=0.3333)
    parser.add_argument("--output-file", default="backend/data/benchmarks/grid/recommended_config.json")
    parser.add_argument("--apply", action="store_true", help="是否直接应用到 /api/system/config")
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    parser.add_argument("--api-key", default="")
    parser.add_argument("--api-key-header", default="X-Api-Key")
    args = parser.parse_args()

    summary_path = os.path.abspath(args.summary_file)
    summary = _load_summary(summary_path)
    chosen = _pick_candidate(
        summary,
        min_throughput_ratio=max(1.0, float(args.min_throughput_ratio)),
        max_first_ratio=max(0.01, float(args.max_first_response_ratio)),
    )
    payload = _build_payload_from_case(chosen)
    out = {
        "source_summary": summary_path,
        "selected_case": chosen.get("case", {}),
        "selected_improvement": chosen.get("improvement", {}),
        "selected_score": chosen.get("score", 0.0),
        "config_payload": payload,
    }

    output_file = os.path.abspath(args.output_file)
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"[recommend] saved: {output_file}")
    print(json.dumps(payload, ensure_ascii=False))

    if args.apply:
        headers = build_request_headers(
            api_key=str(args.api_key or "").strip(),
            api_key_header=str(args.api_key_header or "X-Api-Key").strip(),
        )
        code, body = _apply_payload(
            base_url=str(args.base_url),
            payload=payload,
            headers=headers,
            timeout_seconds=float(args.timeout_seconds),
        )
        print(f"[recommend] apply status={code}")
        print(json.dumps(body, ensure_ascii=False))
        if code < 200 or code >= 300:
            return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
