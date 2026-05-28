#!/usr/bin/env python3
"""
开箱企业套件自动对标门禁（CI / 发布前）。

  PYTHONPATH=backend python3 backend/scripts/enterprise_suite_acceptance_gate.py
  PYTHONPATH=backend python3 backend/scripts/enterprise_suite_acceptance_gate.py --phase phase0
  ENTERPRISE_SUITE_LIVE_URL=http://127.0.0.1:8000 python3 ... --live
  PYTHONPATH=backend python3 backend/scripts/enterprise_suite_acceptance_gate.py --json-out report.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from core.enterprise.suite_live import live_probe_headers_from_env  # noqa: E402
from core.enterprise.suite_benchmark import build_suite_benchmark_report, evaluate_suite_gate  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Enterprise suite auto benchmark gate")
    parser.add_argument("--phase", default="all", help="all | phase0 | phase1 | phase2")
    parser.add_argument("--min-auto-p0-pass-rate", type=float, default=100.0)
    parser.add_argument("--json-out", default="", help="write full report JSON")
    parser.add_argument(
        "--live-base-url",
        default=os.environ.get("ENTERPRISE_SUITE_LIVE_URL", "").strip(),
        help="running gateway base URL for live probes",
    )
    parser.add_argument(
        "--require-live",
        action="store_true",
        help="fail if --live-base-url / ENTERPRISE_SUITE_LIVE_URL unset",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="shorthand: run live probes (uses --live-base-url or ENTERPRISE_SUITE_LIVE_URL)",
    )
    parser.add_argument(
        "--inprocess",
        action="store_true",
        help="run Live+UAT probes via FastAPI TestClient (no running server)",
    )
    args = parser.parse_args()

    live_url = (args.live_base_url or "").strip()
    if args.live and not live_url and not args.inprocess:
        live_url = "http://127.0.0.1:8000"
    if args.live or args.inprocess:
        args.require_live = True

    phase_list = None if args.phase in ("all", "") else [args.phase]
    if args.inprocess:
        from core.enterprise.suite_live_inprocess import enterprise_gate_test_client

        with enterprise_gate_test_client() as client:
            ok, payload = evaluate_suite_gate(
                phase=args.phase,
                min_auto_p0_pass_rate=args.min_auto_p0_pass_rate,
                live_headers=live_probe_headers_from_env(),
                require_live=True,
                inprocess_client=client,
            )
            report = payload.get("report") or build_suite_benchmark_report(
                phases=phase_list,
                inprocess_client=client,
            )
    else:
        ok, payload = evaluate_suite_gate(
            phase=args.phase,
            min_auto_p0_pass_rate=args.min_auto_p0_pass_rate,
            live_base_url=live_url or None,
            live_headers=live_probe_headers_from_env() if live_url else None,
            require_live=args.require_live,
        )
        report = payload.get("report") or build_suite_benchmark_report(
            phases=phase_list,
            live_base_url=live_url or None,
            live_headers=live_probe_headers_from_env() if live_url else None,
        )
    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    print("=== Enterprise Suite Benchmark Gate ===")
    for line in payload.get("details") or []:
        print(line)
    comp = report.get("competitive_summary") or {}
    print(f"competitive avg gap vs mature commercial: {comp.get('avg_gap_vs_mature_commercial')}")
    print(f"overall_auto_gate_pass: {report.get('overall_auto_gate_pass')}")
    if report.get("live_base_url"):
        print(f"live_base_url: {report.get('live_base_url')}")
        print(f"live_gate_pass: {report.get('live_gate_pass')}")
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
