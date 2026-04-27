from scripts._http_utils import build_request_headers
from scripts.run_smart_routing_experiment import _acceptance_ok, _is_candidate_better
from scripts.smart_routing_param_scan import _estimated_level, _rank_results


def test_build_request_headers_empty_key_returns_empty() -> None:
    assert build_request_headers("", "X-Api-Key") == {}


def test_build_request_headers_uses_custom_header() -> None:
    headers = build_request_headers("k-123", "Authorization")
    assert headers == {"Authorization": "k-123"}


def test_is_candidate_better_all_thresholds_met() -> None:
    ok, reasons = _is_candidate_better(
        baseline_report={"summary": {"success_rate": 0.95, "avg_latency_ms": 1000, "realized_qps": 5}},
        current_report={"summary": {"success_rate": 0.97, "avg_latency_ms": 980, "realized_qps": 6}},
        min_success_rate_delta=0.01,
        max_latency_delta_ms=0.0,
        min_qps_delta=0.5,
    )
    assert ok is True
    assert len(reasons) == 3


def test_is_candidate_better_fails_when_latency_regresses() -> None:
    ok, reasons = _is_candidate_better(
        baseline_report={"summary": {"success_rate": 0.96, "avg_latency_ms": 900, "realized_qps": 6}},
        current_report={"summary": {"success_rate": 0.97, "avg_latency_ms": 1000, "realized_qps": 6.5}},
        min_success_rate_delta=0.0,
        max_latency_delta_ms=50.0,
        min_qps_delta=0.0,
    )
    assert ok is False
    assert any("latency_delta_ms" in line for line in reasons)


def test_acceptance_ok_reads_nested_flag() -> None:
    assert _acceptance_ok({"acceptance": {"ok": True}}) is True
    assert _acceptance_ok({"acceptance": {"ok": False}}) is False
    assert _acceptance_ok({}) is False


def test_rank_results_pass_only_filters_non_pass() -> None:
    results = [
        {"score": 10.0, "acceptance": {"ok": False}},
        {"score": 9.0, "acceptance": {"ok": True}},
        {"score": 8.0, "acceptance": {"ok": True}},
    ]
    ordered, pass_results, top = _rank_results(results, pass_only=True, top_k=5)
    assert len(ordered) == 3
    assert len(pass_results) == 2
    assert len(top) == 2
    assert all((item.get("acceptance", {}) or {}).get("ok") for item in top)


def test_estimated_level_ok_when_below_warn_ratio() -> None:
    level, ratio = _estimated_level(
        estimate_seconds=10 * 60,
        max_estimated_minutes=30,
        warn_ratio=0.7,
        fail_ratio=1.0,
    )
    assert level == "ok"
    assert ratio < 0.7


def test_estimated_level_warn_between_warn_and_fail() -> None:
    level, ratio = _estimated_level(
        estimate_seconds=24 * 60,
        max_estimated_minutes=30,
        warn_ratio=0.7,
        fail_ratio=1.0,
    )
    assert level == "warn"
    assert 0.7 <= ratio < 1.0


def test_estimated_level_fail_at_or_above_fail_ratio() -> None:
    level, ratio = _estimated_level(
        estimate_seconds=30 * 60,
        max_estimated_minutes=30,
        warn_ratio=0.7,
        fail_ratio=1.0,
    )
    assert level == "fail"
    assert ratio >= 1.0
