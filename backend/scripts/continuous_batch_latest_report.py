#!/usr/bin/env python3
"""
连续批处理最近一次运行快速报告。

默认扫描 backend/data/benchmarks/pipeline 下最新时间戳目录，
汇总 gate / triage / recommend 关键信息，便于值班快速查看。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    return data


def _latest_run_dir(root: Path) -> Path | None:
    if not root.is_dir():
        return None
    dirs = [p for p in root.iterdir() if p.is_dir()]
    if not dirs:
        return None
    return max(dirs)


def _safe_get_num(obj: dict[str, Any], key: str) -> str:
    v = obj.get(key)
    return "n/a" if v is None else str(v)


def _print_gate(gate: dict[str, Any] | None) -> None:
    if not gate:
        print("gate: n/a")
        return
    metrics = gate.get("metrics", {}) if isinstance(gate.get("metrics"), dict) else {}
    thresholds = gate.get("thresholds", {}) if isinstance(gate.get("thresholds"), dict) else {}
    print(f"gate.ok: {bool(gate.get('ok', False))}")
    print(
        "gate.metrics: "
        f"throughput={_safe_get_num(metrics, 'throughput_ratio')} "
        f"(min {_safe_get_num(thresholds, 'min_throughput_ratio')}), "
        f"first={_safe_get_num(metrics, 'first_response_ratio')} "
        f"(max {_safe_get_num(thresholds, 'max_first_response_ratio')}), "
        f"success={_safe_get_num(metrics, 'success_rate')} "
        f"(min {_safe_get_num(thresholds, 'min_success_rate')})"
    )


def _print_triage(triage: dict[str, Any] | None) -> None:
    if not triage:
        print("triage: n/a")
        return
    print(f"triage.diagnosis: {triage.get('diagnosis', 'n/a')}")
    actions = triage.get("actions", [])
    if isinstance(actions, list) and actions:
        print(f"triage.action[0]: {actions[0]}")


def _print_recommend(rec: dict[str, Any] | None) -> None:
    if not rec:
        print("recommend: n/a")
        return
    print(f"recommend.case: {rec.get('selected_case', {})}")
    print(f"recommend.payload: {rec.get('config_payload', {})}")


def _print_summary_top(summary: dict[str, Any] | None) -> None:
    if not summary:
        print("summary: n/a")
        return
    top = summary.get("top")
    if isinstance(top, list) and top:
        first = top[0] if isinstance(top[0], dict) else {}
        print(f"summary.top_case: {first.get('case', {})}")
        return
    print("summary: n/a")


def main() -> int:
    parser = argparse.ArgumentParser(description="连续批处理最近运行报告")
    parser.add_argument(
        "--pipeline-root",
        default="backend/data/benchmarks/pipeline",
        help="pipeline 结果根目录",
    )
    parser.add_argument(
        "--run-dir",
        default="",
        help="指定 run 目录；为空则自动选最新目录",
    )
    parser.add_argument(
        "--output-file",
        default="",
        help="可选：输出 JSON 文件",
    )
    args = parser.parse_args()

    root = Path(args.pipeline_root).resolve()
    run_dir = Path(args.run_dir).resolve() if str(args.run_dir or "").strip() else _latest_run_dir(root)
    if run_dir is None or not run_dir.is_dir():
        print(f"未找到可用 run 目录: {root}")
        return 2

    gate = _load_json(run_dir / "gate-result.json")
    triage = _load_json(run_dir / "triage.json")
    rec = _load_json(run_dir / "recommended_config.json")
    summary = _load_json(run_dir / "grid-summary.json")

    print(f"run_dir: {run_dir}")
    _print_gate(gate)
    _print_triage(triage)
    _print_recommend(rec)
    _print_summary_top(summary)

    payload = {
        "run_dir": str(run_dir),
        "gate": gate or {},
        "triage": triage or {},
        "recommend": rec or {},
        "summary": summary or {},
    }
    if str(args.output_file or "").strip():
        out = Path(args.output_file).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"output: {out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
