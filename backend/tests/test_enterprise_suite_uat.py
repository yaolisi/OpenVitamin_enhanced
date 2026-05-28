"""企业套件 UAT 探针。"""
from __future__ import annotations

from unittest.mock import patch

from core.enterprise.suite_uat import evaluate_uat_static, run_uat_live_probes


def test_uat_static_approval_resume() -> None:
    status, _, _ = evaluate_uat_static("uat:approval_resume")
    assert status == "pass"


def test_uat_static_oa_approval_pause() -> None:
    status, _, _ = evaluate_uat_static("uat:oa_approval_pause")
    assert status == "pass"


def test_uat_static_admin_import_bundle() -> None:
    status, _, _ = evaluate_uat_static("uat:admin_import_bundle")
    assert status == "pass"


def test_uat_live_import_preview_mock() -> None:
    with patch(
        "core.enterprise.suite_uat._http_post_json",
        return_value=(200, "{}", {"bundle_id": "release-brief-gate", "ok": True}),
    ):
        rows = run_uat_live_probes("http://127.0.0.1:8000", phases=["phase2"])
    preview = next(x for x in rows if x.get("id") == "UAT-2-B-02")
    assert preview["status"] == "pass"
