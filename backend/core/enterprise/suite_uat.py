"""开箱企业套件 UAT 探针（静态冒烟 + 可选 Live HTTP）。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from core.enterprise.suite_live import DEFAULT_TIMEOUT_S, _http_get, _normalize_base, live_probe_headers_from_env

Status = Literal["pass", "fail", "warn", "manual", "skip"]

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _repo_path(rel: str) -> Path:
    return _REPO_ROOT / rel


def _http_post_json(
    url: str,
    body: Dict[str, Any],
    *,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = DEFAULT_TIMEOUT_S,
) -> Tuple[int, str, Any]:
    payload = json.dumps(body).encode("utf-8")
    hdrs = {"Content-Type": "application/json", "Accept": "application/json", **(headers or {})}
    req = Request(url, data=payload, method="POST", headers=hdrs)
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                parsed: Any = json.loads(raw) if raw.strip() else None
            except json.JSONDecodeError:
                parsed = raw[:500]
            return int(resp.status), raw[:2000], parsed
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        return int(exc.code), raw[:500], None
    except Exception as exc:
        raise ConnectionError(str(exc)) from exc


def evaluate_uat_static(probe: str) -> Tuple[Status, str, Dict[str, Any]]:
    """仓库内 UAT 冒烟（无需运行网关）。"""
    evidence: Dict[str, Any] = {"probe": probe, "probe_type": "uat_static"}
    key = probe.split(":", 1)[1] if ":" in probe else probe

    if key == "approval_resume":
        test_py = _repo_path("backend/tests/test_workflow_approval_api_integration.py")
        svc_py = _repo_path("backend/core/workflows/services/workflow_approval_service.py")
        if not test_py.is_file() or not svc_py.is_file():
            return ("fail", "approval integration artifacts missing", evidence)
        text = test_py.read_text(encoding="utf-8")
        svc = svc_py.read_text(encoding="utf-8")
        ok = "/approve" in text and "approval_decisions" in text and "async def _resume" in svc
        return (
            "pass" if ok else "fail",
            "approval approve + resume path in tests/service",
            {**evidence, "test_file": str(test_py)},
        )

    if key == "oa_approval_pause":
        wf_path = _repo_path("demos/workflows/demo1-release-brief-gate.bundle.json")
        if not wf_path.is_file():
            return ("fail", "oa demo workflow bundle missing", evidence)
        data = json.loads(wf_path.read_text(encoding="utf-8"))
        nodes = (data.get("dag") or {}).get("nodes") or []
        ok = any(
            isinstance(n, dict)
            and str((n.get("config") or {}).get("workflow_node_type") or "") == "approval"
            for n in nodes
        )
        return (
            "pass" if ok else "fail",
            "release-brief-gate DAG has approval node",
            {**evidence, "bundle": str(wf_path)},
        )

    if key == "admin_import_bundle":
        imp_api = _repo_path("backend/api/import_api.py")
        if not imp_api.is_file():
            return ("fail", "import_api missing", evidence)
        text = imp_api.read_text(encoding="utf-8")
        ok = '"/preview"' in text and '"/run"' in text
        try:
            from core.demos.bundle_registry import load_platform_bundle

            bundle, _ = load_platform_bundle("release-brief-gate")
            ok = ok and bool(bundle.get("bundle_id"))
            msg = f"import API + load platform bundle {bundle.get('bundle_id')}"
        except Exception as exc:
            ok = False
            msg = str(exc)
        return ("pass" if ok else "fail", msg, evidence)

    return ("na", f"unknown uat probe: {probe}", evidence)


UAT_LIVE_SPECS: List[Dict[str, Any]] = [
    {
        "id": "UAT-2-B-02",
        "phase": "phase2",
        "priority": "P0",
        "label": "UAT Live · 管理员导入预览 release-brief-gate",
        "uat_key": "admin_import_bundle",
        "method": "POST",
        "path": "/api/v1/import/preview",
        "body": {
            "bundle_id": "release-brief-gate",
            "catalog_kind": "platform",
            "kind": "platform",
        },
        "expect": (200,),
        "json_key": "bundle_id",
        "auth_optional": True,
    },
    {
        "id": "UAT-0-E1-04",
        "phase": "phase0",
        "priority": "P0",
        "label": "UAT Live · 办文场景平台包可列举",
        "uat_key": "oa_approval_pause",
        "method": "GET",
        "path": "/api/v1/demos/platform-bundles",
        "expect": (200,),
        "json_contains": "release-brief-gate",
    },
    {
        "id": "UAT-0-C-02",
        "phase": "phase0",
        "priority": "P0",
        "label": "UAT Live · 审批 API 路由可达（OpenAPI）",
        "uat_key": "approval_resume",
        "method": "GET",
        "path": "/openapi.json",
        "expect": (200,),
        "json_contains": "/approvals/{task_id}/approve",
    },
]


def evaluate_uat_live_spec(
    spec: Dict[str, Any],
    *,
    base_url: str,
    headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    base = _normalize_base(base_url)
    path = str(spec.get("path") or "")
    url = f"{base}{path}"
    expect = tuple(spec.get("expect") or (200,))
    evidence: Dict[str, Any] = {"url": url, "probe_type": "uat_live", "uat_key": spec.get("uat_key")}
    method = str(spec.get("method") or "GET").upper()
    try:
        if method == "POST":
            status, snippet, parsed = _http_post_json(url, dict(spec.get("body") or {}), headers=headers)
        else:
            status, snippet, parsed = _http_get(url, headers=headers)
        evidence["http_status"] = status
        ok_status = status in expect
        ok_body = True
        msg = f"HTTP {status}"
        if spec.get("json_key") and isinstance(parsed, dict):
            ok_body = bool(parsed.get(str(spec["json_key"])))
            msg += f"; {spec['json_key']}={ok_body}"
        if spec.get("json_contains"):
            needle = str(spec["json_contains"])
            blob = json.dumps(parsed) if isinstance(parsed, (dict, list)) else str(parsed or snippet)
            ok_body = needle in blob
            msg += f"; contains {needle!r}={ok_body}"
        if status in (401, 403):
            st: Status = "warn"
            msg += " — set ENTERPRISE_SUITE_API_KEY (operator/admin)"
        elif ok_status and ok_body:
            st = "pass"
        else:
            st = "fail"
            if not ok_status:
                msg += f"; body={snippet[:120]}"
        return {
            "id": spec.get("id"),
            "phase": spec.get("phase"),
            "priority": spec.get("priority"),
            "label": spec.get("label"),
            "eval_mode": "uat_live",
            "status": st,
            "message": msg,
            "evidence": evidence,
        }
    except ConnectionError as exc:
        return {
            "id": spec.get("id"),
            "phase": spec.get("phase"),
            "priority": spec.get("priority"),
            "label": spec.get("label"),
            "eval_mode": "uat_live",
            "status": "fail",
            "message": str(exc),
            "evidence": evidence,
        }


def run_uat_live_probes(
    base_url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    phases: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    if not base_url.strip():
        return []
    phase_set = set(phases) if phases else None
    hdrs = headers if headers is not None else live_probe_headers_from_env()
    out: List[Dict[str, Any]] = []
    for spec in UAT_LIVE_SPECS:
        if phase_set is not None and spec.get("phase") not in phase_set:
            continue
        out.append(evaluate_uat_live_spec(spec, base_url=base_url, headers=hdrs))
    return out
