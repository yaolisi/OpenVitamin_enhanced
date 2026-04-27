#!/usr/bin/env python3
"""
对比 smart_routing_load_test.py 生成的两份报告。

示例：
  cd backend && python scripts/compare_smart_routing_reports.py \
    --baseline ./tmp/report-baseline.json \
    --current ./tmp/report-current.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_json(path: str) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Invalid report JSON object: {path}")
    return data


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _summary(report: dict[str, Any]) -> dict[str, float]:
    s = report.get("summary", {}) if isinstance(report, dict) else {}
    return {
        "success_rate": _safe_float(s.get("success_rate"), 0.0),
        "avg_latency_ms": _safe_float(s.get("avg_latency_ms"), 0.0),
        "realized_qps": _safe_float(s.get("realized_qps"), 0.0),
    }


def _ratio_by_device(report: dict[str, Any], device: str) -> float:
    dist = report.get("distribution", {}) if isinstance(report, dict) else {}
    resolved_model = dist.get("resolved_model", {}) if isinstance(dist, dict) else {}
    if not isinstance(resolved_model, dict) or not resolved_model:
        return 0.0
    routing_ctx = report.get("routing_context", {}) if isinstance(report, dict) else {}
    model_to_device = routing_ctx.get("model_to_device", {}) if isinstance(routing_ctx, dict) else {}
    if not isinstance(model_to_device, dict):
        return 0.0
    total = sum(int(v) for v in resolved_model.values() if isinstance(v, (int, float)))
    if total <= 0:
        return 0.0
    target = str(device).strip().lower()
    matched = 0
    for model_id, cnt in resolved_model.items():
        if str(model_to_device.get(str(model_id), "")).strip().lower() == target:
            matched += int(cnt) if isinstance(cnt, (int, float)) else 0
    return matched / total


def _fallback_ratio(report: dict[str, Any]) -> float:
    dist = report.get("distribution", {}) if isinstance(report, dict) else {}
    resolved_via = dist.get("resolved_via", {}) if isinstance(dist, dict) else {}
    if not isinstance(resolved_via, dict) or not resolved_via:
        return 0.0
    total = sum(int(v) for v in resolved_via.values() if isinstance(v, (int, float)))
    if total <= 0:
        return 0.0
    fallback = 0
    for k, v in resolved_via.items():
        if "fallback" in str(k).lower():
            fallback += int(v) if isinstance(v, (int, float)) else 0
    return fallback / total


def _delta(cur: float, base: float) -> float:
    return cur - base


def _pct_change(cur: float, base: float) -> float:
    if abs(base) < 1e-9:
        return 0.0
    return (cur - base) / base


def _fmt_pct(v: float) -> str:
    return f"{v * 100:.2f}%"


def main() -> int:
    parser = argparse.ArgumentParser(description="智能路由压测报告对比")
    parser.add_argument("--baseline", required=True, help="基线报告 JSON 路径")
    parser.add_argument("--current", required=True, help="当前报告 JSON 路径")
    args = parser.parse_args()

    baseline = _load_json(args.baseline)
    current = _load_json(args.current)

    base_s = _summary(baseline)
    cur_s = _summary(current)

    base_gpu = _ratio_by_device(baseline, "gpu")
    cur_gpu = _ratio_by_device(current, "gpu")
    base_cpu = _ratio_by_device(baseline, "cpu")
    cur_cpu = _ratio_by_device(current, "cpu")
    base_fallback = _fallback_ratio(baseline)
    cur_fallback = _fallback_ratio(current)

    print("=== Smart Routing Report Diff ===")
    print(f"baseline: {args.baseline}")
    print(f"current : {args.current}")
    print("")
    print("核心指标:")
    print(
        f"- success_rate: {base_s['success_rate']:.4f} -> {cur_s['success_rate']:.4f} "
        f"(delta={_delta(cur_s['success_rate'], base_s['success_rate']):+.4f})"
    )
    print(
        f"- avg_latency_ms: {base_s['avg_latency_ms']:.2f} -> {cur_s['avg_latency_ms']:.2f} "
        f"(delta={_delta(cur_s['avg_latency_ms'], base_s['avg_latency_ms']):+.2f}, "
        f"change={_fmt_pct(_pct_change(cur_s['avg_latency_ms'], base_s['avg_latency_ms']))})"
    )
    print(
        f"- realized_qps: {base_s['realized_qps']:.2f} -> {cur_s['realized_qps']:.2f} "
        f"(delta={_delta(cur_s['realized_qps'], base_s['realized_qps']):+.2f}, "
        f"change={_fmt_pct(_pct_change(cur_s['realized_qps'], base_s['realized_qps']))})"
    )
    print("")
    print("路由占比:")
    print(f"- gpu_ratio: {_fmt_pct(base_gpu)} -> {_fmt_pct(cur_gpu)} (delta={_fmt_pct(_delta(cur_gpu, base_gpu))})")
    print(f"- cpu_ratio: {_fmt_pct(base_cpu)} -> {_fmt_pct(cur_cpu)} (delta={_fmt_pct(_delta(cur_cpu, base_cpu))})")
    print(
        f"- fallback_ratio: {_fmt_pct(base_fallback)} -> {_fmt_pct(cur_fallback)} "
        f"(delta={_fmt_pct(_delta(cur_fallback, base_fallback))})"
    )

    print("")
    print("解读建议:")
    if cur_s["success_rate"] >= base_s["success_rate"]:
        print("- 成功率未下降，路由变更稳定性可接受。")
    else:
        print("- 成功率下降，优先收紧高风险候选的 max_queue_size / max_error_rate。")
    if cur_s["avg_latency_ms"] <= base_s["avg_latency_ms"]:
        print("- 平均延迟改善，当前分流策略在性能上有效。")
    else:
        print("- 平均延迟上升，建议降低 CPU 候选权重或提高 GPU 保障配额。")
    if cur_fallback > base_fallback:
        print("- fallback 占比上升，说明主路径压力变大，可适度放宽主设备阈值。")
    else:
        print("- fallback 占比稳定/下降，主路径健康度较好。")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
