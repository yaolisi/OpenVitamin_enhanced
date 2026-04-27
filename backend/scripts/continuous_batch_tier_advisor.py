#!/usr/bin/env python3
"""
连续批处理门禁档位自动建议器。

输入：
- 若干 gate-result.json（由 continuous_batch_acceptance_gate.py 生成）
输出：
- 推荐档位：strict / balanced / lenient
- 推荐门禁参数
"""
from __future__ import annotations

import argparse
import glob
import json
import os
from dataclasses import dataclass
from typing import Any


TIERS: dict[str, dict[str, float]] = {
    "strict": {
        "min_throughput_ratio": 1.8,
        "max_first_response_ratio": 0.28,
        "min_success_rate": 0.995,
    },
    "balanced": {
        "min_throughput_ratio": 1.5,
        "max_first_response_ratio": 0.3333,
        "min_success_rate": 0.99,
    },
    "lenient": {
        "min_throughput_ratio": 1.35,
        "max_first_response_ratio": 0.45,
        "min_success_rate": 0.97,
    },
}


@dataclass
class GateRecord:
    ok: bool
    throughput_ratio: float
    first_response_ratio: float
    success_rate: float
    file_path: str


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _load_json(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"invalid gate file: {path}")
    return data


def _collect_files(input_path: str) -> list[str]:
    p = os.path.abspath(input_path)
    if os.path.isfile(p):
        return [p]
    # 目录模式：递归找 gate-result*.json
    if os.path.isdir(p):
        pattern = os.path.join(p, "**", "gate-result*.json")
        return sorted(glob.glob(pattern, recursive=True))
    # glob 模式
    return sorted(glob.glob(p, recursive=True))


def _to_record(path: str) -> GateRecord | None:
    try:
        obj = _load_json(path)
    except Exception:
        return None
    metrics = obj.get("metrics", {}) if isinstance(obj.get("metrics"), dict) else {}
    return GateRecord(
        ok=bool(obj.get("ok", False)),
        throughput_ratio=_safe_float(metrics.get("throughput_ratio"), 0.0),
        first_response_ratio=_safe_float(metrics.get("first_response_ratio"), 999.0),
        success_rate=_safe_float(metrics.get("success_rate"), 0.0),
        file_path=path,
    )


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _std(values: list[float]) -> float:
    if len(values) <= 1:
        return 0.0
    m = _mean(values)
    var = sum((x - m) ** 2 for x in values) / len(values)
    return var ** 0.5


def _recommend(records: list[GateRecord]) -> tuple[str, list[str]]:
    notes: list[str] = []
    if not records:
        return "lenient", ["无可用记录，默认建议 lenient"]

    pass_rate = sum(1 for r in records if r.ok) / len(records)
    thr_values = [r.throughput_ratio for r in records]
    first_values = [r.first_response_ratio for r in records]
    suc_values = [r.success_rate for r in records]
    thr_mean, first_mean, suc_mean = _mean(thr_values), _mean(first_values), _mean(suc_values)
    thr_std, first_std = _std(thr_values), _std(first_values)

    notes.append(f"样本数={len(records)} 通过率={pass_rate:.4f}")
    notes.append(f"均值 throughput={thr_mean:.4f}, first={first_mean:.4f}, success={suc_mean:.4f}")
    notes.append(f"波动 throughput_std={thr_std:.4f}, first_std={first_std:.4f}")

    # 升严格档条件：高通过率 + 指标显著优于 balanced + 低波动
    if (
        pass_rate >= 0.98
        and thr_mean >= 1.75
        and first_mean <= 0.30
        and suc_mean >= 0.993
        and thr_std <= 0.15
        and first_std <= 0.08
    ):
        notes.append("满足严格档条件：高通过率 + 高收益 + 低波动")
        return "strict", notes

    # 保持平衡档条件：通过率稳定，且满足核心目标附近
    if (
        pass_rate >= 0.90
        and thr_mean >= 1.45
        and first_mean <= 0.36
        and suc_mean >= 0.985
    ):
        notes.append("满足平衡档条件：通过率与收益稳定")
        return "balanced", notes

    notes.append("建议 lenient：当前波动或通过率不足以使用更严格阈值")
    return "lenient", notes


def main() -> int:
    parser = argparse.ArgumentParser(description="连续批处理门禁档位自动建议")
    parser.add_argument(
        "--input",
        default="backend/data/benchmarks/pipeline",
        help="输入文件/目录/glob（默认扫描 pipeline 目录下 gate-result*.json）",
    )
    parser.add_argument("--last-n", type=int, default=10, help="只取最近 N 条记录")
    parser.add_argument(
        "--output-file",
        default="backend/data/benchmarks/pipeline/tier-advice.json",
        help="建议结果输出路径",
    )
    args = parser.parse_args()

    files = _collect_files(str(args.input))
    if not files:
        print("no gate-result files found")
        return 2
    files = files[-max(1, int(args.last_n)) :]
    records = [r for r in (_to_record(p) for p in files) if r is not None]
    if not records:
        print("no valid gate records")
        return 2

    tier, notes = _recommend(records)
    payload = {
        "recommended_tier": tier,
        "recommended_thresholds": TIERS[tier],
        "records_used": len(records),
        "record_files": [r.file_path for r in records],
        "notes": notes,
    }
    out = os.path.abspath(str(args.output_file))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False, indent=2))

    print(f"recommended tier: {tier}")
    print(json.dumps(TIERS[tier], ensure_ascii=False))
    print(f"output: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
