import json
from argparse import Namespace
from pathlib import Path

from scripts import continuous_batch_run_all as run_all


def test_apply_auto_tier_fallback_when_disabled(tmp_path: Path):
    args = Namespace(
        auto_tier=False,
        auto_tier_output_file="",
        auto_tier_input="",
        auto_tier_last_n=10,
    )
    out = run_all._apply_auto_tier(
        args=args,
        repo_root=str(tmp_path),
        run_dir=str(tmp_path),
        gate_min_throughput_ratio=1.5,
        gate_max_first_response_ratio=0.3333,
        gate_min_success_rate=0.99,
    )
    assert out == (1.5, 0.3333, 0.99)


def test_apply_auto_tier_reads_thresholds(tmp_path: Path, monkeypatch):
    tier_file = tmp_path / "tier-advice.json"
    tier_file.write_text(
        json.dumps(
            {
                "recommended_thresholds": {
                    "min_throughput_ratio": 1.8,
                    "max_first_response_ratio": 0.28,
                    "min_success_rate": 0.995,
                }
            }
        ),
        encoding="utf-8",
    )
    args = Namespace(
        auto_tier=True,
        auto_tier_output_file=str(tier_file),
        auto_tier_input="x",
        auto_tier_last_n=10,
    )
    monkeypatch.setattr(run_all, "_run", lambda cmd, cwd: 0)
    out = run_all._apply_auto_tier(
        args=args,
        repo_root=str(tmp_path),
        run_dir=str(tmp_path),
        gate_min_throughput_ratio=1.5,
        gate_max_first_response_ratio=0.3333,
        gate_min_success_rate=0.99,
    )
    assert out == (1.8, 0.28, 0.995)


def test_run_gate_and_maybe_triage_triggers_triage(tmp_path: Path, monkeypatch):
    calls: list[list[str]] = []

    def fake_run(cmd, cwd):
        calls.append(list(cmd))
        # gate fails, triage succeeds
        if "continuous_batch_acceptance_gate.py" in " ".join(cmd):
            return 2
        return 0

    monkeypatch.setattr(run_all, "_run", fake_run)
    args = Namespace(
        gate=True,
        gate_output_file="",
        auto_triage=True,
        triage_output_file="",
    )
    gate_rc, gate_file = run_all._run_gate_and_maybe_triage(
        args=args,
        repo_root=str(tmp_path),
        run_dir=str(tmp_path),
        summary_file=str(tmp_path / "grid-summary.json"),
        gate_min_throughput_ratio=1.5,
        gate_max_first_response_ratio=0.3333,
        gate_min_success_rate=0.99,
    )
    assert gate_rc == 2
    assert gate_file.endswith("gate-result.json")
    assert any("continuous_batch_triage.py" in " ".join(c) for c in calls)


def test_main_skip_doctor_does_not_call_doctor(tmp_path: Path, monkeypatch):
    calls: list[list[str]] = []

    def fake_run(cmd, cwd):
        calls.append(list(cmd))
        # all steps succeed
        return 0

    monkeypatch.setattr(run_all, "_run", fake_run)
    monkeypatch.setattr(
        run_all,
        "_init_paths",
        lambda args, repo_root: {
            "run_dir": str(tmp_path / "run"),
            "snapshot_file": str(tmp_path / "run" / "snapshot.json"),
            "summary_file": str(tmp_path / "run" / "grid-summary.json"),
            "recommend_file": str(tmp_path / "run" / "recommended_config.json"),
            "grid_output_dir": str(tmp_path / "run" / "grid-cases"),
        },
    )
    class _FakeParser:
        def parse_args(self):
            return Namespace(
                base_url="http://127.0.0.1:8000",
                model="demo-model",
                requests=2,
                concurrency_list="1",
                wait_ms_list="4",
                max_size_list="4",
                timeout_seconds=10.0,
                top_k=1,
                min_throughput_ratio=1.5,
                max_first_response_ratio=0.3333,
                output_root="backend/data/benchmarks/pipeline",
                skip_doctor=True,
                apply=False,
                gate=False,
                gate_output_file="",
                gate_min_throughput_ratio=1.5,
                gate_max_first_response_ratio=0.3333,
                gate_min_success_rate=0.99,
                auto_tier=False,
                auto_tier_input="",
                auto_tier_last_n=10,
                auto_tier_output_file="",
                auto_triage=False,
                triage_output_file="",
                api_key="",
                api_key_header="X-Api-Key",
            )

    monkeypatch.setattr(run_all, "_build_parser", lambda: _FakeParser())

    rc = run_all.main()
    assert rc == 0
    assert not any("continuous_batch_doctor.py" in " ".join(c) for c in calls)
