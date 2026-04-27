#!/usr/bin/env python3
"""
连续批处理一键管道：
1) snapshot 当前配置
2) grid search 搜索参数
3) recommend 生成推荐配置
4) 可选 apply 推荐配置
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from typing import Sequence


def _run(cmd: Sequence[str], cwd: str) -> int:
    print("\n$ " + " ".join(cmd))
    proc = subprocess.run(cmd, cwd=cwd)
    return int(proc.returncode)


def _arg_list(flag: str, value: str) -> list[str]:
    v = str(value or "").strip()
    if not v:
        return []
    return [flag, v]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="连续批处理一键实验管道")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--model", required=True)
    parser.add_argument("--requests", type=int, default=120)
    parser.add_argument("--concurrency-list", default="10,20,30")
    parser.add_argument("--wait-ms-list", default="4,8,12,16")
    parser.add_argument("--max-size-list", default="4,8,12")
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--min-throughput-ratio", type=float, default=1.5)
    parser.add_argument("--max-first-response-ratio", type=float, default=0.3333)
    parser.add_argument(
        "--output-root",
        default="backend/data/benchmarks/pipeline",
        help="统一输出目录（会按时间戳创建子目录）",
    )
    parser.add_argument("--skip-doctor", action="store_true", help="跳过前置 doctor 预检（默认不跳过）")
    parser.add_argument("--apply", action="store_true", help="是否自动应用推荐配置")
    parser.add_argument("--gate", action="store_true", help="是否在流程末尾执行验收门禁")
    parser.add_argument("--gate-output-file", default="", help="门禁结果输出文件（可选）")
    parser.add_argument("--gate-min-throughput-ratio", type=float, default=1.5)
    parser.add_argument("--gate-max-first-response-ratio", type=float, default=0.3333)
    parser.add_argument("--gate-min-success-rate", type=float, default=0.99)
    parser.add_argument("--auto-tier", action="store_true", help="是否根据历史 gate 结果自动分档并覆盖门禁阈值")
    parser.add_argument(
        "--auto-tier-input",
        default="backend/data/benchmarks/pipeline",
        help="auto-tier 输入路径（目录/文件/glob）",
    )
    parser.add_argument("--auto-tier-last-n", type=int, default=10, help="auto-tier 使用最近 N 条记录")
    parser.add_argument("--auto-tier-output-file", default="", help="auto-tier 输出文件路径（可选）")
    parser.add_argument("--auto-triage", action="store_true", help="gate 失败时是否自动执行 triage 诊断")
    parser.add_argument("--triage-output-file", default="", help="triage 输出文件路径（可选）")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--api-key-header", default="X-Api-Key")
    return parser


def _init_paths(args: argparse.Namespace, repo_root: str) -> dict[str, str]:
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
    run_dir = os.path.abspath(os.path.join(repo_root, args.output_root, stamp))
    grid_output_dir = os.path.join(run_dir, "grid-cases")
    os.makedirs(grid_output_dir, exist_ok=True)
    return {
        "run_dir": run_dir,
        "snapshot_file": os.path.join(run_dir, "snapshot.json"),
        "summary_file": os.path.join(run_dir, "grid-summary.json"),
        "recommend_file": os.path.join(run_dir, "recommended_config.json"),
        "grid_output_dir": grid_output_dir,
    }


def _apply_auto_tier(
    *,
    args: argparse.Namespace,
    repo_root: str,
    run_dir: str,
    gate_min_throughput_ratio: float,
    gate_max_first_response_ratio: float,
    gate_min_success_rate: float,
) -> tuple[float, float, float]:
    if not args.auto_tier:
        return gate_min_throughput_ratio, gate_max_first_response_ratio, gate_min_success_rate
    auto_tier_output = str(args.auto_tier_output_file or "").strip() or os.path.join(run_dir, "tier-advice.json")
    tier_cmd = [
        "python",
        "backend/scripts/continuous_batch_tier_advisor.py",
        "--input",
        str(args.auto_tier_input),
        "--last-n",
        str(args.auto_tier_last_n),
        "--output-file",
        auto_tier_output,
    ]
    tier_rc = _run(tier_cmd, cwd=repo_root)
    if tier_rc != 0 or not os.path.isfile(auto_tier_output):
        print(f"[run-all] auto-tier failed rc={tier_rc}, fallback to manual thresholds")
        return gate_min_throughput_ratio, gate_max_first_response_ratio, gate_min_success_rate
    try:
        with open(auto_tier_output, "r", encoding="utf-8") as f:
            tier_obj = json.load(f)
        rec = tier_obj.get("recommended_thresholds", {}) if isinstance(tier_obj, dict) else {}
        out = (
            float(rec.get("min_throughput_ratio", gate_min_throughput_ratio)),
            float(rec.get("max_first_response_ratio", gate_max_first_response_ratio)),
            float(rec.get("min_success_rate", gate_min_success_rate)),
        )
        print(
            "[run-all] auto-tier applied thresholds: "
            f"throughput>={out[0]}, first<={out[1]}, success>={out[2]}"
        )
        return out
    except Exception as e:
        print(f"[run-all] auto-tier parse failed, fallback to manual thresholds: {e}")
        return gate_min_throughput_ratio, gate_max_first_response_ratio, gate_min_success_rate


def _run_snapshot(args: argparse.Namespace, repo_root: str, snapshot_file: str, common_auth: list[str]) -> int:
    cmd = [
        "python",
        "backend/scripts/continuous_batch_rollback.py",
        "--base-url",
        args.base_url,
        "--timeout-seconds",
        str(args.timeout_seconds),
        *common_auth,
        "snapshot",
        "--output-file",
        snapshot_file,
    ]
    return _run(cmd, cwd=repo_root)


def _run_doctor(args: argparse.Namespace, repo_root: str, common_auth: list[str]) -> int:
    cmd = [
        "python",
        "backend/scripts/continuous_batch_doctor.py",
        "--repo-root",
        ".",
        "--output-root",
        str(args.output_root),
        "--base-url",
        args.base_url,
        "--timeout-seconds",
        str(min(float(args.timeout_seconds), 30.0)),
        *common_auth,
    ]
    return _run(cmd, cwd=repo_root)


def _run_grid(args: argparse.Namespace, repo_root: str, summary_file: str, grid_output_dir: str, common_auth: list[str]) -> int:
    cmd = [
        "python",
        "backend/scripts/continuous_batch_grid_search.py",
        "--base-url",
        args.base_url,
        "--model",
        args.model,
        "--requests",
        str(args.requests),
        "--concurrency-list",
        args.concurrency_list,
        "--wait-ms-list",
        args.wait_ms_list,
        "--max-size-list",
        args.max_size_list,
        "--timeout-seconds",
        str(args.timeout_seconds),
        "--top-k",
        str(args.top_k),
        "--output-dir",
        grid_output_dir,
        "--summary-file",
        summary_file,
        *common_auth,
    ]
    return _run(cmd, cwd=repo_root)


def _run_recommend(
    args: argparse.Namespace,
    repo_root: str,
    summary_file: str,
    recommend_file: str,
    common_auth: list[str],
) -> int:
    cmd = [
        "python",
        "backend/scripts/continuous_batch_recommend.py",
        "--summary-file",
        summary_file,
        "--base-url",
        args.base_url,
        "--min-throughput-ratio",
        str(args.min_throughput_ratio),
        "--max-first-response-ratio",
        str(args.max_first_response_ratio),
        "--output-file",
        recommend_file,
        "--timeout-seconds",
        str(args.timeout_seconds),
        *common_auth,
    ]
    if args.apply:
        cmd.append("--apply")
    return _run(cmd, cwd=repo_root)


def _run_gate_and_maybe_triage(
    *,
    args: argparse.Namespace,
    repo_root: str,
    run_dir: str,
    summary_file: str,
    gate_min_throughput_ratio: float,
    gate_max_first_response_ratio: float,
    gate_min_success_rate: float,
) -> tuple[int, str]:
    gate_output_file = str(args.gate_output_file or "").strip() or os.path.join(run_dir, "gate-result.json")
    if not args.gate:
        return 0, gate_output_file
    gate_cmd = [
        "python",
        "backend/scripts/continuous_batch_acceptance_gate.py",
        "--summary-file",
        summary_file,
        "--min-throughput-ratio",
        str(gate_min_throughput_ratio),
        "--max-first-response-ratio",
        str(gate_max_first_response_ratio),
        "--min-success-rate",
        str(gate_min_success_rate),
        "--output-file",
        gate_output_file,
    ]
    gate_rc = _run(gate_cmd, cwd=repo_root)
    if gate_rc == 0 or not args.auto_triage:
        return gate_rc, gate_output_file
    triage_output_file = str(args.triage_output_file or "").strip() or os.path.join(run_dir, "triage.json")
    triage_cmd = [
        "python",
        "backend/scripts/continuous_batch_triage.py",
        "--run-dir",
        run_dir,
        "--gate-file",
        gate_output_file,
        "--summary-file",
        summary_file,
        "--output-file",
        triage_output_file,
    ]
    triage_rc = _run(triage_cmd, cwd=repo_root)
    if triage_rc != 0:
        print(f"[run-all] auto-triage failed rc={triage_rc}")
    return gate_rc, gate_output_file


def _print_summary(
    *,
    args: argparse.Namespace,
    paths: dict[str, str],
    gate_output_file: str,
    gate_rc: int,
) -> None:
    print("\n=== Pipeline Done ===")
    print(f"run_dir: {paths['run_dir']}")
    print(f"snapshot: {paths['snapshot_file']}")
    print(f"grid summary: {paths['summary_file']}")
    print(f"recommended config: {paths['recommend_file']}")
    print(f"applied: {'yes' if args.apply else 'no'}")
    print(f"gate: {'enabled' if args.gate else 'disabled'}")
    if args.gate:
        print(f"gate result file: {gate_output_file}")
        print(f"gate status: {'PASS' if gate_rc == 0 else 'FAIL'}")
    if args.auto_triage:
        print("auto-triage: enabled")


def main() -> int:
    args = _build_parser().parse_args()

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    paths = _init_paths(args, repo_root)
    run_dir = paths["run_dir"]

    common_auth = _arg_list("--api-key", args.api_key) + _arg_list("--api-key-header", args.api_key_header)
    gate_min_throughput_ratio, gate_max_first_response_ratio, gate_min_success_rate = _apply_auto_tier(
        args=args,
        repo_root=repo_root,
        run_dir=run_dir,
        gate_min_throughput_ratio=float(args.gate_min_throughput_ratio),
        gate_max_first_response_ratio=float(args.gate_max_first_response_ratio),
        gate_min_success_rate=float(args.gate_min_success_rate),
    )

    if not bool(args.skip_doctor):
        rc = _run_doctor(args, repo_root, common_auth)
        if rc != 0:
            print(f"[run-all] doctor failed, rc={rc}")
            return rc
    else:
        print("[run-all] skip-doctor enabled")

    rc = _run_snapshot(args, repo_root, paths["snapshot_file"], common_auth)
    if rc != 0:
        print(f"[run-all] snapshot failed, rc={rc}")
        return rc

    rc = _run_grid(args, repo_root, paths["summary_file"], paths["grid_output_dir"], common_auth)
    if rc != 0:
        print(f"[run-all] grid search failed, rc={rc}")
        return rc

    rc = _run_recommend(args, repo_root, paths["summary_file"], paths["recommend_file"], common_auth)
    if rc != 0:
        print(f"[run-all] recommend/apply failed, rc={rc}")
        return rc

    gate_rc, gate_output_file = _run_gate_and_maybe_triage(
        args=args,
        repo_root=repo_root,
        run_dir=run_dir,
        summary_file=paths["summary_file"],
        gate_min_throughput_ratio=gate_min_throughput_ratio,
        gate_max_first_response_ratio=gate_max_first_response_ratio,
        gate_min_success_rate=gate_min_success_rate,
    )
    _print_summary(args=args, paths=paths, gate_output_file=gate_output_file, gate_rc=gate_rc)
    return gate_rc if args.gate else 0


if __name__ == "__main__":
    raise SystemExit(main())
