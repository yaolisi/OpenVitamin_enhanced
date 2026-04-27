#!/usr/bin/env python3
"""
连续批处理验收门禁脚本（CI 友好）。

输入可选：
1) --summary-file: continuous_batch_grid_search 的 summary.json
2) --recommend-file: continuous_batch_recommend 生成的推荐文件（可选）

门禁条件（默认）：
- throughput_ratio >= 1.5
- first_response_ratio <= 0.3333
- success_rate >= 0.99
"""
from __future__ import annotations

import argparse
import json
import os
from typing import Any


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _load_json(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"invalid json root object: {path}")
    return data


def _pick_best_from_summary(summary: dict[str, Any]) -> dict[str, Any]:
    top = summary.get("top")
    all_results = summary.get("all_results")
    candidates = top if isinstance(top, list) and top else all_results
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("summary has no candidates in top/all_results")
    first = candidates[0]
    if not isinstance(first, dict):
        raise ValueError("invalid candidate item")
    return first


def _extract_metrics_from_candidate(candidate: dict[str, Any]) -> dict[str, float]:
    imp = candidate.get("improvement", {}) if isinstance(candidate.get("improvement"), dict) else {}
    summary = candidate.get("summary", {}) if isinstance(candidate.get("summary"), dict) else {}
    return {
        "throughput_ratio": _safe_float(imp.get("sync_batch_vs_sync_no_batch_throughput_ratio"), 0.0),
        "first_response_ratio": _safe_float(imp.get("sync_batch_vs_sync_no_batch_first_response_ratio"), 999.0),
        "success_rate": _safe_float(summary.get("sync_batch_success_rate"), 0.0),
    }


def _extract_metrics_from_recommend(rec: dict[str, Any]) -> dict[str, float]:
    imp = rec.get("selected_improvement", {}) if isinstance(rec.get("selected_improvement"), dict) else {}
    # recommend 文件默认无 success_rate，留空时判定为 1.0（不阻断）
    return {
        "throughput_ratio": _safe_float(imp.get("sync_batch_vs_sync_no_batch_throughput_ratio"), 0.0),
        "first_response_ratio": _safe_float(imp.get("sync_batch_vs_sync_no_batch_first_response_ratio"), 999.0),
        "success_rate": _safe_float(rec.get("selected_success_rate"), 1.0),
    }


def _evaluate(
    metrics: dict[str, float],
    *,
    min_throughput_ratio: float,
    max_first_response_ratio: float,
    min_success_rate: float,
) -> tuple[bool, list[str]]:
    details: list[str] = []
    thr = metrics.get("throughput_ratio", 0.0)
    first = metrics.get("first_response_ratio", 999.0)
    suc = metrics.get("success_rate", 0.0)

    ok_thr = thr >= min_throughput_ratio
    details.append(
        f"throughput_ratio={thr:.4f} {'>=' if ok_thr else '<'} required {min_throughput_ratio:.4f}"
    )
    ok_first = first <= max_first_response_ratio
    details.append(
        f"first_response_ratio={first:.4f} {'<=' if ok_first else '>'} limit {max_first_response_ratio:.4f}"
    )
    ok_suc = suc >= min_success_rate
    details.append(f"success_rate={suc:.4f} {'>=' if ok_suc else '<'} required {min_success_rate:.4f}")
    return (ok_thr and ok_first and ok_suc), details


def main() -> int:
    parser = argparse.ArgumentParser(description="连续批处理验收门禁")
    parser.add_argument("--summary-file", default="", help="grid search summary.json")
    parser.add_argument("--recommend-file", default="", help="recommend 结果文件（可选）")
    parser.add_argument("--min-throughput-ratio", type=float, default=1.5)
    parser.add_argument("--max-first-response-ratio", type=float, default=0.3333)
    parser.add_argument("--min-success-rate", type=float, default=0.99)
    parser.add_argument("--output-file", default="", help="可选：将门禁结果写入 JSON")
    args = parser.parse_args()

    summary_file = str(args.summary_file or "").strip()
    recommend_file = str(args.recommend_file or "").strip()
    if not summary_file and not recommend_file:
        raise ValueError("必须提供 --summary-file 或 --recommend-file 至少一个")

    source = ""
    metrics: dict[str, float]
    chosen_case: dict[str, Any] = {}
    if summary_file:
        summary_abs = os.path.abspath(summary_file)
        summary = _load_json(summary_abs)
        best = _pick_best_from_summary(summary)
        metrics = _extract_metrics_from_candidate(best)
        chosen_case = best.get("case", {}) if isinstance(best.get("case"), dict) else {}
        source = summary_abs
    else:
        rec_abs = os.path.abspath(recommend_file)
        rec = _load_json(rec_abs)
        metrics = _extract_metrics_from_recommend(rec)
        chosen_case = rec.get("selected_case", {}) if isinstance(rec.get("selected_case"), dict) else {}
        source = rec_abs

    ok, details = _evaluate(
        metrics,
        min_throughput_ratio=max(1.0, float(args.min_throughput_ratio)),
        max_first_response_ratio=max(0.01, float(args.max_first_response_ratio)),
        min_success_rate=max(0.0, min(1.0, float(args.min_success_rate))),
    )

    print("PASS" if ok else "FAIL")
    print(f"source: {source}")
    if chosen_case:
        print(f"case: {json.dumps(chosen_case, ensure_ascii=False)}")
    for line in details:
        print(f"- {line}")

    out = {
        "ok": ok,
        "source": source,
        "case": chosen_case,
        "metrics": metrics,
        "checks": details,
        "thresholds": {
            "min_throughput_ratio": float(args.min_throughput_ratio),
            "max_first_response_ratio": float(args.max_first_response_ratio),
            "min_success_rate": float(args.min_success_rate),
        },
    }
    if str(args.output_file or "").strip():
        out_path = os.path.abspath(args.output_file)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(out, ensure_ascii=False, indent=2))
        print(f"result file: {out_path}")

    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
