"""Live 探针（mock HTTP）。"""
from __future__ import annotations

from unittest.mock import patch

from core.enterprise.suite_live import evaluate_live_probe, run_live_probes


def test_evaluate_live_probe_health_pass() -> None:
    spec = {
        "id": "L0-B-01",
        "phase": "phase0",
        "priority": "P0",
        "label": "health",
        "path": "/api/health",
        "expect": (200,),
    }
    with patch(
        "core.enterprise.suite_live._http_get",
        return_value=(200, "{}", {"status": "ok"}),
    ):
        row = evaluate_live_probe(spec, base_url="http://127.0.0.1:8000")
    assert row["status"] == "pass"


def test_run_live_probes_filters_phase() -> None:
    with patch(
        "core.enterprise.suite_live._http_get",
        return_value=(200, "{}", {"items": [{"bundle_id": "x"}]}),
    ):
        rows = run_live_probes("http://127.0.0.1:8000", phases=["phase0"])
    assert rows
    assert all(x.get("phase") == "phase0" for x in rows)


def test_evaluate_live_probe_connection_fail() -> None:
    spec = {
        "id": "L0-B-01",
        "phase": "phase0",
        "priority": "P0",
        "label": "health",
        "path": "/api/health",
        "expect": (200,),
    }
    with patch(
        "core.enterprise.suite_live._http_get",
        side_effect=ConnectionError("refused"),
    ):
        row = evaluate_live_probe(spec, base_url="http://127.0.0.1:9")
    assert row["status"] == "fail"
