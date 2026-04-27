import json
from pathlib import Path

from scripts.continuous_batch_acceptance_gate import _evaluate
from scripts.continuous_batch_recommend import _pick_candidate
from scripts.continuous_batch_tier_advisor import _recommend, GateRecord


def test_recommend_pick_candidate_with_threshold_match():
    summary = {
        "top": [
            {
                "case": {"concurrency": 20, "wait_ms": 8, "max_size": 8},
                "improvement": {
                    "sync_batch_vs_sync_no_batch_throughput_ratio": 1.62,
                    "sync_batch_vs_sync_no_batch_first_response_ratio": 0.31,
                },
                "score": 1.2,
            }
        ]
    }
    picked = _pick_candidate(
        summary,
        min_throughput_ratio=1.5,
        max_first_ratio=0.3333,
    )
    assert picked["case"]["wait_ms"] == 8


def test_recommend_pick_candidate_fallback_first_item():
    summary = {
        "top": [
            {
                "case": {"concurrency": 10, "wait_ms": 16, "max_size": 12},
                "improvement": {
                    "sync_batch_vs_sync_no_batch_throughput_ratio": 1.2,
                    "sync_batch_vs_sync_no_batch_first_response_ratio": 0.6,
                },
                "score": 0.3,
            },
            {
                "case": {"concurrency": 20, "wait_ms": 12, "max_size": 8},
                "improvement": {
                    "sync_batch_vs_sync_no_batch_throughput_ratio": 1.3,
                    "sync_batch_vs_sync_no_batch_first_response_ratio": 0.5,
                },
                "score": 0.25,
            },
        ]
    }
    picked = _pick_candidate(
        summary,
        min_throughput_ratio=1.5,
        max_first_ratio=0.3333,
    )
    assert picked["case"]["concurrency"] == 10


def test_acceptance_evaluate_pass():
    ok, details = _evaluate(
        {"throughput_ratio": 1.7, "first_response_ratio": 0.30, "success_rate": 0.995},
        min_throughput_ratio=1.5,
        max_first_response_ratio=0.3333,
        min_success_rate=0.99,
    )
    assert ok is True
    assert len(details) == 3


def test_tier_advisor_recommend_lenient_on_low_pass_rate():
    records = [
        GateRecord(
            ok=False,
            throughput_ratio=1.2,
            first_response_ratio=0.5,
            success_rate=0.96,
            file_path="a.json",
        ),
        GateRecord(
            ok=False,
            throughput_ratio=1.1,
            first_response_ratio=0.7,
            success_rate=0.95,
            file_path="b.json",
        ),
    ]
    tier, notes = _recommend(records)
    assert tier == "lenient"
    assert any("lenient" in n for n in notes)


def test_tier_advisor_recommend_strict():
    records = [
        GateRecord(True, 1.9, 0.25, 0.997, "1.json"),
        GateRecord(True, 1.85, 0.26, 0.996, "2.json"),
        GateRecord(True, 1.82, 0.27, 0.998, "3.json"),
        GateRecord(True, 1.88, 0.24, 0.997, "4.json"),
    ]
    tier, _ = _recommend(records)
    assert tier == "strict"
