"""对已运行网关执行 Live 探针（开箱企业套件验收）。"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Literal, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

Status = Literal["pass", "fail", "warn", "skip"]

DEFAULT_TIMEOUT_S = float(os.environ.get("ENTERPRISE_SUITE_LIVE_TIMEOUT", "8"))


def _normalize_base(url: str) -> str:
    return url.rstrip("/")


def _http_get(
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = DEFAULT_TIMEOUT_S,
) -> Tuple[int, str, Any]:
    req = Request(url, method="GET", headers=dict(headers or {}))
    try:
        with urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            try:
                parsed: Any = json.loads(body) if body.strip() else None
            except json.JSONDecodeError:
                parsed = body[:500]
            return int(resp.status), body[:2000], parsed
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        return int(exc.code), raw[:500], None
    except URLError as exc:
        raise ConnectionError(str(exc.reason or exc)) from exc


def live_probe_headers_from_env() -> Dict[str, str]:
    headers: Dict[str, str] = {"Accept": "application/json"}
    api_key = (os.environ.get("ENTERPRISE_SUITE_API_KEY") or os.environ.get("PERILLA_API_KEY") or "").strip()
    if api_key:
        headers["X-Api-Key"] = api_key
    tenant = (os.environ.get("ENTERPRISE_SUITE_TENANT_ID") or os.environ.get("X_TENANT_ID") or "").strip()
    if tenant:
        headers["X-Tenant-Id"] = tenant
    return headers


# (probe_id, phase, priority, label, path, expect_status, json_key_optional)
LIVE_PROBE_SPECS: List[Dict[str, Any]] = [
    {
        "id": "L0-B-01",
        "phase": "phase0",
        "priority": "P0",
        "label": "Live · /api/health",
        "path": "/api/health",
        "expect": (200, 204),
    },
    {
        "id": "L0-B-02",
        "phase": "phase0",
        "priority": "P0",
        "label": "Live · /api/health/ready",
        "path": "/api/health/ready",
        "expect": (200, 204),
    },
    {
        "id": "L0-E-00",
        "phase": "phase0",
        "priority": "P0",
        "label": "Live · 导入目录 /api/v1/import/catalog",
        "path": "/api/v1/import/catalog",
        "expect": (200,),
        "json_list_key": "items",
    },
    {
        "id": "L0-E-01",
        "phase": "phase0",
        "priority": "P1",
        "label": "Live · 导入预检 /api/v1/import/preflight",
        "path": "/api/v1/import/preflight",
        "expect": (200,),
        "auth_optional": True,
    },
    {
        "id": "L1-E-00",
        "phase": "phase1",
        "priority": "P0",
        "label": "Live · 企业能力 /api/v1/enterprise/capabilities",
        "path": "/api/v1/enterprise/capabilities",
        "expect": (200,),
        "json_key": "production_readiness",
    },
    {
        "id": "L1-E-01",
        "phase": "phase1",
        "priority": "P0",
        "label": "Live · 套件对标 /api/v1/enterprise/suite-benchmark",
        "path": "/api/v1/enterprise/suite-benchmark?phase=phase0",
        "expect": (200,),
        "json_key": "checklist_items",
    },
    {
        "id": "L2-G-01",
        "phase": "phase2",
        "priority": "P1",
        "label": "Live · 套件门禁 /api/v1/enterprise/suite-benchmark/gate",
        "path": "/api/v1/enterprise/suite-benchmark/gate?phase=phase0",
        "expect": (200,),
        "json_key": "pass",
    },
    {
        "id": "L1-M-01",
        "phase": "phase1",
        "priority": "P1",
        "label": "Live · Prometheus /metrics",
        "path": "/metrics",
        "expect": (200,),
        "auth_optional": True,
    },
    {
        "id": "L0-W-01",
        "phase": "phase0",
        "priority": "P1",
        "label": "Live · 工作流列表 /api/v1/workflows",
        "path": "/api/v1/workflows",
        "expect": (200,),
        "auth_optional": True,
    },
    {
        "id": "L0-D-01",
        "phase": "phase0",
        "priority": "P1",
        "label": "Live · 平台演示包列表 /api/v1/demos/platform-bundles",
        "path": "/api/v1/demos/platform-bundles",
        "expect": (200,),
        "auth_optional": True,
        "json_list_key": "items",
    },
]


def evaluate_live_probe(
    spec: Dict[str, Any],
    *,
    base_url: str,
    headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    base = _normalize_base(base_url)
    path = str(spec.get("path") or "")
    url = f"{base}{path}"
    expect = tuple(spec.get("expect") or (200,))
    evidence: Dict[str, Any] = {"url": url, "probe_type": "live"}
    try:
        status, snippet, parsed = _http_get(url, headers=headers)
        evidence["http_status"] = status
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
        if status == 401 and spec.get("auth_optional"):
            st: Status = "warn"
            msg = "HTTP 401 — set ENTERPRISE_SUITE_API_KEY for authenticated preflight"
        elif status == 403 and spec.get("auth_optional"):
            st = "warn"
            msg = "HTTP 403 — check API key / tenant headers"
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
            "eval_mode": "live",
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
            "eval_mode": "live",
            "status": "fail",
            "message": str(exc),
            "evidence": evidence,
        }


def run_live_probes(
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
    for spec in LIVE_PROBE_SPECS:
        if phase_set is not None and spec.get("phase") not in phase_set:
            continue
        out.append(evaluate_live_probe(spec, base_url=base_url, headers=hdrs))
    return out


def live_phase_summary(items: List[Dict[str, Any]], phase: str) -> Dict[str, Any]:
    phase_items = [x for x in items if x.get("phase") == phase]
    live_p0 = [x for x in phase_items if x.get("priority") == "P0"]
    live_p0_pass = sum(1 for x in live_p0 if x.get("status") == "pass")
    return {
        "phase": phase,
        "live_p0_total": len(live_p0),
        "live_p0_pass": live_p0_pass,
        "live_p0_pass_rate": round(100.0 * live_p0_pass / len(live_p0), 1) if live_p0 else 100.0,
        "live_gate_pass": len(live_p0) == 0 or live_p0_pass == len(live_p0),
    }
