"""开箱企业套件自动对标。"""
from __future__ import annotations

from core.enterprise.suite_benchmark import (
    build_competitive_benchmark,
    build_suite_benchmark_report,
    evaluate_probe,
    evaluate_suite_gate,
)


def test_evaluate_probe_health_endpoints() -> None:
    status, _, _ = evaluate_probe("health_endpoints")
    assert status == "pass"


def test_evaluate_probe_scene_oa() -> None:
    status, _, _ = evaluate_probe("scene_bundle:oa_approval")
    assert status == "pass"


def test_build_suite_benchmark_report_structure() -> None:
    report = build_suite_benchmark_report()
    assert report["report_type"] == "enterprise_suite_benchmark"
    assert report["checklist_items"]
    assert report["competitive_benchmark"]
    assert len(report["phases"]) == 3


def test_competitive_benchmark_has_mature_reference() -> None:
    rows = build_competitive_benchmark()
    assert rows
    assert "mature_commercial_paas" in (rows[0].get("reference_scores") or {})


def test_suite_gate_phase0_auto() -> None:
    ok, payload = evaluate_suite_gate(phase="phase0")
    assert "details" in payload
    # 仓库内 artifact 探针应使 phase0 自动门禁在 CI 通过
    assert ok is True


def test_evaluate_probe_settings_flag_rbac() -> None:
    status, _, _ = evaluate_probe("settings_flag:rbac")
    assert status == "pass"


def test_import_catalog_at_least_five() -> None:
    report = build_suite_benchmark_report(phases=["phase2"])
    item = next(x for x in report["checklist_items"] if x.get("id") == "2-C-01")
    assert item.get("status") == "pass"


def test_suite_gate_all_phases_static() -> None:
    ok, _ = evaluate_suite_gate(phase="all")
    assert ok is True


def test_uat_hybrid_items_pass_statically() -> None:
    report = build_suite_benchmark_report()
    uat_ids = {"0-C-02", "0-E1-04", "2-B-02"}
    for item in report["checklist_items"]:
        if item.get("id") in uat_ids:
            assert item.get("status") == "pass", item
