from pathlib import Path

from scripts.continuous_batch_latest_report import _latest_run_dir


def test_latest_run_dir_returns_none_for_missing_dir(tmp_path: Path):
    missing = tmp_path / "not-exist"
    assert _latest_run_dir(missing) is None


def test_latest_run_dir_picks_lexicographically_latest(tmp_path: Path):
    root = tmp_path / "pipeline"
    root.mkdir(parents=True, exist_ok=True)
    (root / "20260101-010101").mkdir()
    (root / "20260102-010101").mkdir()
    (root / "20251231-235959").mkdir()

    latest = _latest_run_dir(root)
    assert latest is not None
    assert latest.name == "20260102-010101"
