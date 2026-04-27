#!/usr/bin/env python3
"""
连续批处理门禁失败快速诊断工具。

输入：
- run_dir（优先）：包含 gate-result.json / grid-summary.json / snapshot.json
- 或直接传 gate-result.json
输出：
- 诊断类型：capacity_issue / threshold_too_strict / likely_noise / unknown
- 建议动作列表
"""
from __future__ import annotations

import argparse
import json
import os
from typing import Any


def _load_json(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    if not isinstance(obj, dict):
        raise ValueError(f"invalid json object: {path}")
    return obj


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _resolve_inputs(run_dir: str, gate_file: str, summary_file: str) -> tuple[str, str]:
    rd = os.path.abspath(run_dir) if run_dir else ""
    gf = os.path.abspath(gate_file) if gate_file else ""
    sf = os.path.abspath(summary_file) if summary_file else ""
    if rd:
        if not gf:
            gf = os.path.join(rd, "gate-result.json")
        if not sf:
            sf = os.path.join(rd, "grid-summary.json")
    if not gf:
        raise ValueError("缺少 gate 输入：请传 --run-dir 或 --gate-file")
    return gf, sf


def _extract_metrics(gate_obj: dict[str, Any]) -> dict[str, float]:
    m = gate_obj.get("metrics", {}) if isinstance(gate_obj.get("metrics"), dict) else {}
    return {
        "throughput_ratio": _safe_float(m.get("throughput_ratio"), 0.0),
        "first_response_ratio": _safe_float(m.get("first_response_ratio"), 999.0),
        "success_rate": _safe_float(m.get("success_rate"), 0.0),
    }


def _extract_thresholds(gate_obj: dict[str, Any]) -> dict[str, float]:
    t = gate_obj.get("thresholds", {}) if isinstance(gate_obj.get("thresholds"), dict) else {}
    return {
        "min_throughput_ratio": _safe_float(t.get("min_throughput_ratio"), 1.5),
        "max_first_response_ratio": _safe_float(t.get("max_first_response_ratio"), 0.3333),
        "min_success_rate": _safe_float(t.get("min_success_rate"), 0.99),
    }


def _summarize_summary_file(summary_obj: dict[str, Any]) -> dict[str, float]:
    top = summary_obj.get("top")
    if not isinstance(top, list) or not top:
        return {}
    first = top[0]
    if not isinstance(first, dict):
        return {}
    imp = first.get("improvement", {}) if isinstance(first.get("improvement"), dict) else {}
    return {
        "top_throughput_ratio": _safe_float(imp.get("sync_batch_vs_sync_no_batch_throughput_ratio"), 0.0),
        "top_first_response_ratio": _safe_float(imp.get("sync_batch_vs_sync_no_batch_first_response_ratio"), 999.0),
    }


def _diagnose(metrics: dict[str, float], thresholds: dict[str, float]) -> tuple[str, list[str]]:
    thr = metrics["throughput_ratio"]
    first = metrics["first_response_ratio"]
    suc = metrics["success_rate"]
    min_thr = thresholds["min_throughput_ratio"]
    max_first = thresholds["max_first_response_ratio"]
    min_suc = thresholds["min_success_rate"]

    actions: list[str] = []
    # 1) 容量问题：成功率明显下降通常是资源/超时/错误
    if suc < min_suc - 0.01:
        actions.extend(
            [
                "优先回滚到 snapshot 配置，恢复稳定性",
                "检查服务错误日志与超时配置，确认是否资源瓶颈",
                "降低并发压测强度后复测，区分系统容量与参数问题",
            ]
        )
        return "capacity_issue", actions

    # 2) 阈值过严：成功率高，但指标轻微不达标
    slight_thr_miss = (thr < min_thr) and (thr >= min_thr * 0.92)
    slight_first_miss = (first > max_first) and (first <= max_first * 1.15)
    if suc >= min_suc and (slight_thr_miss or slight_first_miss):
        actions.extend(
            [
                "优先降一档门禁阈值（strict->balanced 或 balanced->lenient）",
                "保持参数不变重跑 1~2 次验证稳定性",
                "若连续通过，再逐步收紧阈值",
            ]
        )
        return "threshold_too_strict", actions

    # 3) 噪声：成功率高但波动项单独偶发
    if suc >= min_suc and (thr <= 0 or first >= 900):
        actions.extend(
            [
                "检查结果文件是否缺失关键指标（可能脚本中断或解析异常）",
                "重跑 pipeline 生成完整报告",
            ]
        )
        return "likely_noise", actions

    # 4) 其他：参数策略不佳
    actions.extend(
        [
            "执行 cb-grid 重新搜参，重点调整 wait_ms/max_size/concurrency",
            "优先降低 wait_ms 控制首响应，再提高 max_size 拉吞吐",
            "确认批处理命中（batch_groups>0）后再做门禁判定",
        ]
    )
    return "unknown", actions


def main() -> int:
    parser = argparse.ArgumentParser(description="连续批处理门禁诊断")
    parser.add_argument("--run-dir", default="", help="pipeline 输出目录（推荐）")
    parser.add_argument("--gate-file", default="", help="gate-result.json 路径")
    parser.add_argument("--summary-file", default="", help="grid-summary.json 路径（可选）")
    parser.add_argument("--output-file", default="", help="输出诊断 JSON 路径")
    args = parser.parse_args()

    gate_file, summary_file = _resolve_inputs(args.run_dir, args.gate_file, args.summary_file)
    gate = _load_json(gate_file)
    metrics = _extract_metrics(gate)
    thresholds = _extract_thresholds(gate)
    diagnosis, actions = _diagnose(metrics, thresholds)

    summary_metrics: dict[str, float] = {}
    if summary_file and os.path.isfile(summary_file):
        try:
            summary_metrics = _summarize_summary_file(_load_json(summary_file))
        except Exception:
            summary_metrics = {}

    out = {
        "diagnosis": diagnosis,
        "ok": bool(gate.get("ok", False)),
        "gate_file": gate_file,
        "summary_file": summary_file if summary_file and os.path.isfile(summary_file) else "",
        "metrics": metrics,
        "thresholds": thresholds,
        "summary_metrics": summary_metrics,
        "actions": actions,
    }

    print(f"diagnosis: {diagnosis}")
    for line in actions:
        print(f"- {line}")

    output = str(args.output_file or "").strip()
    if output:
        out_path = os.path.abspath(output)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(out, ensure_ascii=False, indent=2))
        print(f"output: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
