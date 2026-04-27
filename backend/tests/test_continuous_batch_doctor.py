from pathlib import Path

from scripts.continuous_batch_doctor import _check_output_root, _check_scripts


def test_check_scripts_missing(tmp_path: Path):
    issues = _check_scripts(tmp_path)
    assert issues
    assert any("missing script" in i for i in issues)


def test_check_output_root_writable(tmp_path: Path):
    issues = _check_output_root(tmp_path, "artifacts/pipeline")
    assert issues == []
