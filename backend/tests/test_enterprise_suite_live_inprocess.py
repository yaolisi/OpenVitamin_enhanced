"""In-process Live + UAT 门禁（TestClient）。"""
from __future__ import annotations

from core.enterprise.suite_benchmark import evaluate_suite_gate
from core.enterprise.suite_live_inprocess import enterprise_gate_test_client


def test_inprocess_live_gate_phase0() -> None:
    with enterprise_gate_test_client() as client:
        ok, payload = evaluate_suite_gate(
            phase="phase0",
            require_live=True,
            inprocess_client=client,
        )
    assert "details" in payload
    assert ok is True


def test_inprocess_live_uat_gate_all() -> None:
    with enterprise_gate_test_client() as client:
        ok, _ = evaluate_suite_gate(phase="all", require_live=True, inprocess_client=client)
    assert ok is True
