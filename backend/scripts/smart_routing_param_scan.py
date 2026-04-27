#!/usr/bin/env python3
"""
智能路由参数扫描脚本：
在 candidate policy 的基础上，自动遍历参数组合并压测，输出最佳组合。
"""

from __future__ import annotations

import argparse
import itertools
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

try:
    from scripts._http_utils import build_request_headers, http_get_json, http_post_json
except Exception:
    from _http_utils import build_request_headers, http_get_json, http_post_json  # type: ignore[no-redef]


def _get_current_policy_text(base_url: str, request_headers: dict[str, str]) -> str:
    cfg = http_get_json(
        f"{base_url.rstrip('/')}/api/system/config",
        request_headers=request_headers,
    )
    settings = cfg.get("settings", {}) if isinstance(cfg, dict) else {}
    return str((settings or {}).get("inferenceSmartRoutingPoliciesJson", "") or "")


def _set_policy_text(base_url: str, policy_text: str, request_headers: dict[str, str]) -> None:
    http_post_json(
        f"{base_url.rstrip('/')}/api/system/config",
        {
            "inferenceSmartRoutingEnabled": True,
            "inferenceSmartRoutingPoliciesJson": policy_text,
        },
        request_headers=request_headers,
    )


def _split_csv_numbers(raw: str, tp: type) -> list[Any]:
    out: list[Any] = []
    for item in str(raw or "").split(","):
        v = item.strip()
        if not v:
            continue
        out.append(tp(v))
    return out


def _mutate_policy(
    policy: dict[str, Any],
    model_alias: str,
    gpu_weight: float,
    gpu_max_queue: int,
    cpu_weight: float,
) -> dict[str, Any]:
    new_policy = json.loads(json.dumps(policy))
    model_policy = new_policy.get(model_alias)
    if not isinstance(model_policy, dict):
        raise ValueError(f"model alias not found in policy: {model_alias}")
    candidates = model_policy.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError(f"policy candidates not found for model: {model_alias}")
    for item in candidates:
        if not isinstance(item, dict):
            continue
        device = str(item.get("device") or "").strip().lower()
        if device == "gpu":
            item["weight"] = gpu_weight
            item["max_queue_size"] = gpu_max_queue
        elif device == "cpu":
            item["weight"] = cpu_weight
    return new_policy


def _export_best_policy(
    *,
    best: dict[str, Any],
    candidate_policy: dict[str, Any],
    scan_alias: str,
    export_path: Path,
) -> None:
    policy = _mutate_policy(
        candidate_policy,
        scan_alias,
        gpu_weight=float(best.get("gpu_weight", 0.0)),
        gpu_max_queue=int(best.get("gpu_max_queue", 0)),
        cpu_weight=float(best.get("cpu_weight", 0.0)),
    )
    export_path.parent.mkdir(parents=True, exist_ok=True)
    export_path.write_text(json.dumps(policy, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[scan] best policy exported: {export_path}")


def _apply_best_policy(
    *,
    best: dict[str, Any],
    candidate_policy: dict[str, Any],
    scan_alias: str,
    base_url: str,
    request_headers: dict[str, str],
) -> None:
    policy = _mutate_policy(
        candidate_policy,
        scan_alias,
        gpu_weight=float(best.get("gpu_weight", 0.0)),
        gpu_max_queue=int(best.get("gpu_max_queue", 0)),
        cpu_weight=float(best.get("cpu_weight", 0.0)),
    )
    _set_policy_text(
        base_url,
        json.dumps(policy, ensure_ascii=False),
        request_headers=request_headers,
    )
    print("[scan] best policy applied to system config")


def _run_load_test(
    *,
    script_dir: Path,
    base_url: str,
    model: str,
    duration_seconds: int,
    rps: int,
    concurrency: int,
    large_ratio: float,
    report_file: Path,
    api_key: str,
    api_key_header: str,
) -> None:
    cmd = [
        sys.executable,
        str(script_dir / "smart_routing_load_test.py"),
        "--base-url",
        base_url,
        "--model",
        model,
        "--duration-seconds",
        str(duration_seconds),
        "--rps",
        str(rps),
        "--concurrency",
        str(concurrency),
        "--large-ratio",
        str(large_ratio),
        "--report-file",
        str(report_file),
        "--api-key",
        api_key,
        "--api-key-header",
        api_key_header,
    ]
    subprocess.run(cmd, cwd=str(script_dir.parent), check=True)


def _score(report: dict[str, Any]) -> float:
    summary = report.get("summary", {}) if isinstance(report, dict) else {}
    success_rate = float(summary.get("success_rate", 0.0) or 0.0)
    qps = float(summary.get("realized_qps", 0.0) or 0.0)
    latency = float(summary.get("avg_latency_ms", 0.0) or 0.0)
    # 越高越好：成功率优先，其次 QPS，延迟作为惩罚项
    return success_rate * 100.0 + qps * 0.2 - latency * 0.01


def _collect_scan_result(
    *,
    idx: int,
    gpu_w: float,
    gpu_q: int,
    cpu_w: float,
    report_file: Path,
) -> dict[str, Any]:
    report = json.loads(report_file.read_text(encoding="utf-8"))
    report_obj = report if isinstance(report, dict) else {}
    return {
        "index": idx,
        "gpu_weight": gpu_w,
        "gpu_max_queue": gpu_q,
        "cpu_weight": cpu_w,
        "score": _score(report_obj),
        "report_file": str(report_file),
        "summary": report_obj.get("summary", {}),
        "acceptance": report_obj.get("acceptance", {}),
    }


def _rank_results(
    results: list[dict[str, Any]],
    pass_only: bool,
    top_k: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    ordered = sorted(results, key=lambda x: float(x.get("score", 0.0)), reverse=True)
    pass_results = [
        r for r in ordered
        if bool((r.get("acceptance", {}) or {}).get("ok", False))
    ]
    pool = pass_results if pass_only else ordered
    return ordered, pass_results, pool[:top_k]


def _print_top(top_n: list[dict[str, Any]], pass_only: bool, pass_count: int, total: int, top_k: int) -> None:
    print("")
    print(f"=== Top {top_k} Combos ===")
    if pass_only:
        print("(pass-only mode enabled)")
    elif pass_count:
        print(f"(all mode; pass combos: {pass_count}/{total})")
    for r in top_n:
        s = r.get("summary", {}) if isinstance(r.get("summary"), dict) else {}
        print(
            f"#{r['index']} score={r['score']:.3f} "
            f"gpu_w={r['gpu_weight']} gpu_q={r['gpu_max_queue']} cpu_w={r['cpu_weight']} "
            f"success={float(s.get('success_rate', 0.0) or 0.0):.4f} "
            f"lat={float(s.get('avg_latency_ms', 0.0) or 0.0):.2f} "
            f"qps={float(s.get('realized_qps', 0.0) or 0.0):.2f}"
        )
    if not top_n:
        print("(no combos matched current ranking filter)")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="智能路由参数扫描")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--model", required=True, help="压测 model/alias")
    parser.add_argument("--candidate-policy-file", required=True, help="候选策略 JSON")
    parser.add_argument("--scan-model-alias", default="", help="策略中要扫描参数的 alias（默认与 --model 一致）")
    parser.add_argument("--gpu-weights", default="2,3,4")
    parser.add_argument("--gpu-max-queues", default="3,4,5,6")
    parser.add_argument("--cpu-weights", default="1,1.5,2")
    parser.add_argument("--duration-seconds", type=int, default=20)
    parser.add_argument("--rps", type=int, default=6)
    parser.add_argument("--concurrency", type=int, default=12)
    parser.add_argument("--large-ratio", type=float, default=0.6)
    parser.add_argument("--output-dir", default="./tmp/smart-routing-scan")
    parser.add_argument("--pass-only", action="store_true", help="仅保留 acceptance.ok=true 的组合用于排行")
    parser.add_argument("--top-k", type=int, default=5, help="输出前 N 名组合（默认 5）")
    parser.add_argument("--export-best-policy-file", default="", help="可选：导出最优组合对应的完整策略 JSON 文件")
    parser.add_argument("--apply-best-policy", action="store_true", help="扫描后将最优策略直接写入系统配置")
    parser.add_argument("--dry-run", action="store_true", help="仅评估与导出，不写入系统配置")
    parser.add_argument("--api-key", default="", help="可选：请求鉴权 API Key")
    parser.add_argument("--api-key-header", default="X-Api-Key", help="可选：鉴权 Header 名（默认 X-Api-Key）")
    parser.add_argument("--max-scan-combos", type=int, default=100, help="扫描组合上限，超出则直接失败（默认 100）")
    parser.add_argument("--max-estimated-minutes", type=float, default=45.0, help="预计耗时上限（分钟），超出则直接失败")
    parser.add_argument("--estimated-warn-ratio", type=float, default=0.7, help="预计耗时告警阈值（相对 max_estimated_minutes）")
    parser.add_argument("--estimated-fail-ratio", type=float, default=1.0, help="预计耗时失败阈值（相对 max_estimated_minutes）")
    return parser


def _build_request_headers(api_key: str, api_key_header: str) -> dict[str, str]:
    return build_request_headers(api_key=api_key, api_key_header=api_key_header)


def _run_scan_loop(
    *,
    combos: list[tuple[float, int, float]],
    candidate_policy: dict[str, Any],
    scan_alias: str,
    args: Any,
    request_headers: dict[str, str],
    script_dir: Path,
    out_dir: Path,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for idx, (gpu_w, gpu_q, cpu_w) in enumerate(combos, start=1):
        print(f"[scan] ({idx}/{len(combos)}) gpu_weight={gpu_w} gpu_max_queue={gpu_q} cpu_weight={cpu_w}")
        policy = _mutate_policy(candidate_policy, scan_alias, gpu_w, gpu_q, cpu_w)
        _maybe_apply_combo_policy(
            args.base_url,
            policy,
            bool(args.dry_run),
            request_headers=request_headers,
        )
        report_file = out_dir / f"report-{idx:03d}.json"
        _run_load_test(
            script_dir=script_dir,
            base_url=args.base_url,
            model=args.model,
            duration_seconds=max(1, int(args.duration_seconds)),
            rps=max(1, int(args.rps)),
            concurrency=max(1, int(args.concurrency)),
            large_ratio=min(1.0, max(0.0, float(args.large_ratio))),
            report_file=report_file,
            api_key=str(args.api_key or ""),
            api_key_header=str(args.api_key_header or "X-Api-Key"),
        )
        results.append(
            _collect_scan_result(
                idx=idx,
                gpu_w=gpu_w,
                gpu_q=gpu_q,
                cpu_w=cpu_w,
                report_file=report_file,
            )
        )
    return results


def _estimate_scan_time_seconds(
    combo_count: int,
    duration_seconds: int,
    rps: int,
    concurrency: int,
) -> float:
    # 粗略估计：单组合以 duration 为主，附加少量调度开销；
    # 并发越高，组合内排队额外开销越小。
    base = max(1.0, float(duration_seconds))
    load_factor = max(0.2, min(2.0, float(rps) / max(1.0, float(concurrency))))
    per_combo = base + (base * 0.15 * load_factor)
    return float(max(1, combo_count)) * per_combo


def _print_scan_estimate(combo_count: int, estimate_seconds: float) -> None:
    est_min = estimate_seconds / 60.0
    print(f"[scan] estimated runtime: ~{est_min:.1f} min for {combo_count} combos")
    if est_min >= 30:
        print("[scan] warning: estimated runtime exceeds 30 minutes")


def _estimated_level(
    estimate_seconds: float,
    max_estimated_minutes: float,
    warn_ratio: float,
    fail_ratio: float,
) -> tuple[str, float]:
    max_minutes = max(1.0, float(max_estimated_minutes))
    ratio = (estimate_seconds / 60.0) / max_minutes
    wr = max(0.0, float(warn_ratio))
    fr = max(wr, float(fail_ratio))
    if ratio >= fr:
        return "fail", ratio
    if ratio >= wr:
        return "warn", ratio
    return "ok", ratio


def _maybe_apply_combo_policy(
    base_url: str,
    policy: dict[str, Any],
    dry_run: bool,
    request_headers: dict[str, str],
) -> None:
    if not dry_run:
        _set_policy_text(
            base_url,
            json.dumps(policy, ensure_ascii=False),
            request_headers=request_headers,
        )
        return
    print("[scan] dry-run: skip applying policy to system config")


def _restore_policy(
    base_url: str,
    base_policy_text: str,
    dry_run: bool,
    request_headers: dict[str, str],
) -> None:
    if not dry_run:
        _set_policy_text(base_url, base_policy_text, request_headers=request_headers)
        print("[scan] policy restored")
        return
    print("[scan] dry-run: skip restoring policy")


def main() -> int:
    args = _build_parser().parse_args()
    request_headers = _build_request_headers(
        str(args.api_key or ""),
        str(args.api_key_header or "X-Api-Key"),
    )

    script_dir = Path(__file__).resolve().parent
    out_dir = Path(args.output_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    scan_alias = args.scan_model_alias.strip() or args.model
    gpu_weights = _split_csv_numbers(args.gpu_weights, float)
    gpu_max_queues = _split_csv_numbers(args.gpu_max_queues, int)
    cpu_weights = _split_csv_numbers(args.cpu_weights, float)
    combos = list(itertools.product(gpu_weights, gpu_max_queues, cpu_weights))
    if not combos:
        raise ValueError("No parameter combinations to scan")
    max_scan_combos = max(1, int(args.max_scan_combos))
    if len(combos) > max_scan_combos:
        raise ValueError(
            f"scan combinations too large: {len(combos)} > max_scan_combos={max_scan_combos}"
        )
    estimate_seconds = _estimate_scan_time_seconds(
        combo_count=len(combos),
        duration_seconds=max(1, int(args.duration_seconds)),
        rps=max(1, int(args.rps)),
        concurrency=max(1, int(args.concurrency)),
    )
    _print_scan_estimate(len(combos), estimate_seconds)
    max_estimated_minutes = max(1.0, float(args.max_estimated_minutes))
    estimate_level, estimate_ratio = _estimated_level(
        estimate_seconds=estimate_seconds,
        max_estimated_minutes=max_estimated_minutes,
        warn_ratio=float(args.estimated_warn_ratio),
        fail_ratio=float(args.estimated_fail_ratio),
    )
    if estimate_level == "warn":
        print(f"[scan] warning: estimated runtime ratio={estimate_ratio:.2f} exceeds warn threshold")
    if estimate_level == "fail":
        raise ValueError(
            f"estimated runtime too high: ratio={estimate_ratio:.2f} "
            f"(estimated={(estimate_seconds / 60.0):.1f}m, max={max_estimated_minutes:.1f}m)"
        )

    base_policy_text = _get_current_policy_text(
        args.base_url,
        request_headers=request_headers,
    )
    candidate_policy = json.loads(Path(args.candidate_policy_file).read_text(encoding="utf-8"))
    if not isinstance(candidate_policy, dict):
        raise ValueError("candidate policy must be JSON object")

    started = time.time()
    try:
        results = _run_scan_loop(
            combos=combos,
            candidate_policy=candidate_policy,
            scan_alias=scan_alias,
            args=args,
            request_headers=request_headers,
            script_dir=script_dir,
            out_dir=out_dir,
        )
    finally:
        _restore_policy(
            args.base_url,
            base_policy_text,
            bool(args.dry_run),
            request_headers=request_headers,
        )

    top_k = max(1, int(args.top_k))
    results, pass_results, top_n = _rank_results(
        results,
        pass_only=bool(args.pass_only),
        top_k=top_k,
    )
    _print_top(top_n, bool(args.pass_only), len(pass_results), len(results), top_k)

    summary_file = out_dir / "scan-summary.json"
    payload = {
        "generated_at_epoch": time.time(),
        "elapsed_seconds": time.time() - started,
        "estimated_elapsed_seconds": estimate_seconds,
        "estimated_level": estimate_level,
        "estimated_ratio": estimate_ratio,
        "base_url": args.base_url,
        "model": args.model,
        "scan_model_alias": scan_alias,
        "pass_only": bool(args.pass_only),
        "top_k": top_k,
        "combo_count": len(combos),
        "max_scan_combos": max_scan_combos,
        "max_estimated_minutes": max_estimated_minutes,
        "estimated_warn_ratio": float(args.estimated_warn_ratio),
        "estimated_fail_ratio": float(args.estimated_fail_ratio),
        "pass_combo_count": len(pass_results),
        "results": results,
        "pass_results": pass_results,
        "top": top_n,
    }
    summary_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[scan] summary saved: {summary_file}")

    if str(args.export_best_policy_file or "").strip() and top_n:
        _export_best_policy(
            best=top_n[0],
            candidate_policy=candidate_policy,
            scan_alias=scan_alias,
            export_path=Path(str(args.export_best_policy_file)).expanduser().resolve(),
        )
    if bool(args.apply_best_policy) and top_n and not args.dry_run:
        _apply_best_policy(
            best=top_n[0],
            candidate_policy=candidate_policy,
            scan_alias=scan_alias,
            base_url=args.base_url,
            request_headers=request_headers,
        )
    elif bool(args.apply_best_policy) and bool(args.dry_run):
        print("[scan] dry-run: --apply-best-policy ignored")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
