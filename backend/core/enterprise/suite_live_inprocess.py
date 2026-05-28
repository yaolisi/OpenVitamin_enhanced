"""对已挂载的 FastAPI TestClient 执行 Live / UAT 探针（CI 无需起 uvicorn）。"""
from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional

from core.enterprise.suite_live import LIVE_PROBE_SPECS, Status
from core.enterprise.suite_uat import UAT_LIVE_SPECS


def _eval_http_result(
    spec: Dict[str, Any],
    *,
    status: int,
    parsed: Any,
    snippet: str,
    evidence: Dict[str, Any],
) -> Dict[str, Any]:
    expect = tuple(spec.get("expect") or (200,))
    ok_status = status in expect
    ok_body = True
    msg_parts = [f"HTTP {status}"]
    if spec.get("json_list_key") and isinstance(parsed, dict):
        items = parsed.get(str(spec["json_list_key"]))
        ok_body = isinstance(items, list) and len(items) > 0
        msg_parts.append(f"items={len(items) if isinstance(items, list) else 0}")
    elif spec.get("json_key") and isinstance(parsed, dict):
        ok_body = str(spec["json_key"]) in parsed
        msg_parts.append(f"has {spec['json_key']}={ok_body}")
    if spec.get("json_contains"):
        needle = str(spec["json_contains"])
        blob = json.dumps(parsed) if isinstance(parsed, (dict, list)) else str(parsed or snippet)
        ok_body = needle in blob
        msg_parts.append(f"contains {needle!r}={ok_body}")
    if status in (401, 403) and spec.get("auth_optional"):
        st: Status = "warn"
        msg = f"HTTP {status} — auth/csrf optional in inprocess"
    elif ok_status and ok_body:
        st = "pass"
        msg = ", ".join(msg_parts)
    else:
        st = "fail"
        msg = ", ".join(msg_parts) + (f"; body={snippet[:120]}" if not ok_status else "")
    return {
        "id": spec.get("id"),
        "phase": spec.get("phase"),
        "priority": spec.get("priority"),
        "label": spec.get("label"),
        "eval_mode": spec.get("eval_mode") or "live",
        "status": st,
        "message": msg,
        "evidence": {**evidence, "http_status": status, "probe_type": "inprocess"},
    }


def _request_inprocess(
    client: Any,
    spec: Dict[str, Any],
    *,
    headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    path = str(spec.get("path") or "")
    evidence: Dict[str, Any] = {"path": path}
    method = str(spec.get("method") or "GET").upper()
    hdrs = dict(headers or {})
    try:
        if method == "POST":
            resp = client.post(path, json=dict(spec.get("body") or {}), headers=hdrs)
        else:
            resp = client.get(path, headers=hdrs)
        status = int(resp.status_code)
        try:
            parsed: Any = resp.json()
            snippet = json.dumps(parsed)[:500]
        except Exception:
            parsed = None
            snippet = (resp.text or "")[:500]
        return _eval_http_result(spec, status=status, parsed=parsed, snippet=snippet, evidence=evidence)
    except Exception as exc:
        return {
            "id": spec.get("id"),
            "phase": spec.get("phase"),
            "priority": spec.get("priority"),
            "label": spec.get("label"),
            "eval_mode": spec.get("eval_mode") or "live",
            "status": "fail",
            "message": str(exc),
            "evidence": evidence,
        }


def run_live_probes_inprocess(
    client: Any,
    *,
    headers: Optional[Dict[str, str]] = None,
    phases: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    phase_set = set(phases) if phases else None
    out: List[Dict[str, Any]] = []
    for spec in LIVE_PROBE_SPECS:
        if phase_set is not None and spec.get("phase") not in phase_set:
            continue
        row = _request_inprocess(client, spec, headers=headers)
        row["eval_mode"] = "live"
        out.append(row)
    return out


def run_uat_live_probes_inprocess(
    client: Any,
    *,
    headers: Optional[Dict[str, str]] = None,
    phases: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    phase_set = set(phases) if phases else None
    out: List[Dict[str, Any]] = []
    for spec in UAT_LIVE_SPECS:
        if phase_set is not None and spec.get("phase") not in phase_set:
            continue
        row = _request_inprocess(client, spec, headers=headers)
        row["eval_mode"] = "uat_live"
        out.append(row)
    return out


@contextmanager
def enterprise_gate_test_client() -> Iterator[Any]:
    """全应用 TestClient；导入预览等写操作需 operator 角色。"""
    import main as main_mod
    from config.settings import settings
    from core.security.deps import require_platform_write
    from core.security.rbac import PlatformRole
    from fastapi.testclient import TestClient

    prev_csrf = bool(getattr(settings, "csrf_enabled", True))
    settings.csrf_enabled = False
    main_mod.app.dependency_overrides[require_platform_write] = lambda: PlatformRole.OPERATOR
    with TestClient(main_mod.app) as client:
        try:
            yield client
        finally:
            main_mod.app.dependency_overrides.pop(require_platform_write, None)
            settings.csrf_enabled = prev_csrf
