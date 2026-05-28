"""
开箱企业套件自动对标：Phase 0–2 验收探针 + 成熟商业 PaaS 参考维度评分。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from config.settings import settings
from core.demos.import_catalog import build_import_catalog
from core.enterprise.capabilities import build_enterprise_capabilities, evaluate_production_readiness
from core.enterprise.suite_benchmark_matrix import (
    COMPETITIVE_DIMENSIONS,
    ENTERPRISE_SCENE_BUNDLES,
    SUITE_BENCHMARK_ITEMS,
    BenchmarkItem,
)
from core.enterprise.suite_live import live_phase_summary, run_live_probes
from core.enterprise.suite_live_inprocess import run_live_probes_inprocess, run_uat_live_probes_inprocess
from core.enterprise.suite_uat import evaluate_uat_static, run_uat_live_probes

_REPO_ROOT = Path(__file__).resolve().parents[3]
Status = Literal["pass", "fail", "warn", "manual", "na"]


def _repo_path(rel: str) -> Path:
    return _REPO_ROOT / rel


def _readiness_ok(readiness_id: str) -> bool:
    for row in evaluate_production_readiness():
        if row.get("id") == readiness_id:
            return row.get("status") == "ok"
    return False


def _catalog_rows() -> list[dict[str, Any]]:
    return build_import_catalog()


def _scene_bundle_ok(scene_key: str) -> tuple[bool, str]:
    spec = ENTERPRISE_SCENE_BUNDLES.get(scene_key)
    if not spec:
        return False, f"unknown scene {scene_key}"
    catalog = _catalog_rows()
    platform_id = str(spec.get("platform_bundle_id") or "")
    workflow_id = str(spec.get("workflow_bundle_id") or "")
    has_platform = any(
        x.get("kind") == "platform" and x.get("bundle_id") == platform_id for x in catalog
    )
    has_workflow = any(
        x.get("kind") == "workflow" and x.get("bundle_id") == workflow_id for x in catalog
    )
    if has_platform and has_workflow:
        return True, f"platform={platform_id}, workflow={workflow_id}"
    missing = []
    if not has_platform:
        missing.append(f"platform:{platform_id}")
    if not has_workflow:
        missing.append(f"workflow:{workflow_id}")
    return False, "missing " + ", ".join(missing)


def evaluate_probe(probe: str) -> tuple[Status, str, Dict[str, Any]]:
    """执行单项自动探针，返回 status, message, evidence。"""
    evidence: Dict[str, Any] = {"probe": probe}

    if probe.startswith("artifact:"):
        rel = probe.split(":", 1)[1]
        path = _repo_path(rel)
        ok = path.exists()
        return ("pass" if ok else "fail", str(path), {"path": str(path), "exists": ok})

    if probe.startswith("scene_bundle:"):
        scene = probe.split(":", 1)[1]
        ok, detail = _scene_bundle_ok(scene)
        evidence["scene"] = scene
        evidence["detail"] = detail
        return ("pass" if ok else "fail", detail, evidence)

    if probe.startswith("import_catalog_min:"):
        n = int(probe.split(":", 1)[1])
        count = len(_catalog_rows())
        evidence["count"] = count
        return ("pass" if count >= n else "fail", f"catalog items={count}, need>={n}", evidence)

    if probe == "import_catalog_api":
        count = len(_catalog_rows())
        evidence["count"] = count
        return ("pass" if count > 0 else "fail", f"{count} catalog items", evidence)

    if probe == "import_catalog_has_descriptions":
        rows = _catalog_rows()
        missing = [x.get("bundle_id") for x in rows if not str(x.get("description") or "").strip()]
        evidence["missing"] = missing
        return ("pass" if not missing else "warn", f"missing descriptions: {len(missing)}", evidence)

    if probe.startswith("settings_flag:"):
        flag = probe.split(":", 1)[1]
        settings_py = _repo_path("backend/config/settings.py")
        helm_values = _repo_path("deploy/helm/perilla-backend/values.yaml")
        helm_deploy = _repo_path("deploy/helm/perilla-backend/templates/deployment.yaml")
        stext = settings_py.read_text(encoding="utf-8") if settings_py.is_file() else ""
        htext = helm_values.read_text(encoding="utf-8") if helm_values.is_file() else ""
        dtext = helm_deploy.read_text(encoding="utf-8") if helm_deploy.is_file() else ""
        mapping: dict[str, tuple[str, str, str]] = {
            "rbac": ("rbac_enabled", "RBAC_ENABLED", "rbacEnabled"),
            "rbac_enforcement": ("rbac_enforcement", "RBAC_ENFORCEMENT", "rbacEnforcement"),
            "tenant": ("tenant_enforcement_enabled", "TENANT_ENFORCEMENT", "tenantEnforcement"),
            "redaction": ("data_redaction_enabled", "DATA_REDACTION", "dataRedaction"),
            "audit": ("audit_log_enabled", "AUDIT_LOG", "auditLogEnabled"),
        }
        if flag == "debug_off":
            ok = "debug" in stext and (
                "debug:" in htext.lower() or "DEBUG" in dtext or "validate_production_security" in stext
            )
            return (
                "pass" if ok else "fail",
                "settings + helm debug guardrails present",
                {"settings": settings_py.is_file(), "helm_values": helm_values.is_file()},
            )
        spec = mapping.get(flag)
        if not spec:
            return ("na", f"unknown settings_flag:{flag}", evidence)
        field, env_name, helm_key = spec
        ok = field in stext and env_name in dtext and helm_key in htext
        evidence.update({"field": field, "env": env_name, "helm_key": helm_key})
        return ("pass" if ok else "fail", f"settings+helm {flag}", evidence)

    if probe.startswith("readiness:"):
        rid = probe.split(":", 1)[1]
        ok = _readiness_ok(rid)
        return ("pass" if ok else "warn", f"readiness:{rid}={'ok' if ok else 'warn'}", evidence)

    if probe == "health_endpoints":
        # 静态：main 注册 health 路由（部署后 UAT 再验 live）
        main_py = _repo_path("backend/main.py")
        text = main_py.read_text(encoding="utf-8") if main_py.is_file() else ""
        ok = "/api/health" in text
        return ("pass" if ok else "fail", "health routes in main.py", evidence)

    if probe == "model_registry_nonempty":
        try:
            from core.models.registry import get_model_registry

            models = get_model_registry().list_models()
            evidence["count"] = len(models)
            return ("pass" if models else "warn", f"models={len(models)}", evidence)
        except Exception as exc:
            return ("warn", str(exc), evidence)

    if probe == "workflow_approval_api":
        wf_api = _repo_path("backend/api/workflows.py")
        text = wf_api.read_text(encoding="utf-8") if wf_api.is_file() else ""
        ok = "/approvals" in text and "approve_execution_approval" in text
        return ("pass" if ok else "fail", "approval routes present", evidence)

    if probe == "workflow_reject_api":
        wf_api = _repo_path("backend/api/workflows.py")
        text = wf_api.read_text(encoding="utf-8") if wf_api.is_file() else ""
        ok = "reject_execution_approval" in text
        return ("pass" if ok else "fail", "reject approval route", evidence)

    if probe == "workflow_fork_join_runtime":
        rt = _repo_path("backend/core/workflows/runtime/workflow_runtime.py")
        text = rt.read_text(encoding="utf-8") if rt.is_file() else ""
        ok = "fork" in text.lower() and "join" in text.lower()
        return ("pass" if ok else "fail", "fork/join in runtime", evidence)

    if probe == "workflow_checkpoint_runtime":
        rt = _repo_path("backend/core/workflows/runtime/workflow_runtime.py")
        text = rt.read_text(encoding="utf-8") if rt.is_file() else ""
        ok = "checkpoint" in text.lower()
        return ("pass" if ok else "fail", "checkpoint in runtime", evidence)

    if probe == "workflow_verify_loop_runtime":
        rt = _repo_path("backend/core/workflows/runtime/workflow_runtime.py")
        text = rt.read_text(encoding="utf-8") if rt.is_file() else ""
        ok = "verify_loop" in text.lower()
        return ("pass" if ok else "fail", "verify_loop in runtime", evidence)

    if probe == "compliance_report_api":
        ent = _repo_path("backend/api/enterprise.py")
        text = ent.read_text(encoding="utf-8") if ent.is_file() else ""
        ok = "compliance/reports/workflow" in text
        return ("pass" if ok else "fail", "compliance export API", evidence)

    if probe == "compliance_pdf_api":
        ent = _repo_path("backend/api/enterprise.py")
        text = ent.read_text(encoding="utf-8") if ent.is_file() else ""
        ok = "/pdf" in text and "compliance" in text
        return ("pass" if ok else "fail", "compliance PDF route", evidence)

    if probe == "publish_gate_api":
        ent = _repo_path("backend/api/enterprise.py")
        text = ent.read_text(encoding="utf-8") if ent.is_file() else ""
        ok = "publish-gate" in text
        return ("pass" if ok else "fail", "publish gate route", evidence)

    if probe == "import_api_routes":
        main_py = _repo_path("backend/main.py")
        text = main_py.read_text(encoding="utf-8") if main_py.is_file() else ""
        ok = "import_router" in text or "import_api" in text
        return ("pass" if ok else "fail", "import router mounted", evidence)

    if probe == "import_preflight_api":
        imp = _repo_path("backend/api/import_api.py")
        text = imp.read_text(encoding="utf-8") if imp.is_file() else ""
        ok = "/preflight" in text
        return ("pass" if ok else "fail", "import preflight route", evidence)

    if probe == "workflow_execution_timeline_api":
        wf_api = _repo_path("backend/api/workflows.py")
        text = wf_api.read_text(encoding="utf-8") if wf_api.is_file() else ""
        ok = "timeline" in text.lower() or "node_states" in text
        return ("pass" if ok else "fail", "execution detail/timeline", evidence)

    if probe == "agents_no_hidden_prompt_policy":
        agents_md = _repo_path("AGENTS.md")
        text = agents_md.read_text(encoding="utf-8") if agents_md.is_file() else ""
        ok = "禁止隐藏 Prompt" in text or "不得注入隐藏 Prompt" in text
        return ("pass" if ok else "fail", "AGENTS.md policy", evidence)

    if probe == "prometheus_enabled":
        ok = bool(getattr(settings, "prometheus_enabled", True))
        return ("pass" if ok else "warn", f"prometheus_enabled={ok}", evidence)

    if probe == "oidc_configured_or_documented":
        caps = build_enterprise_capabilities()
        if caps.get("oidc_configured"):
            return ("pass", "OIDC configured", {"oidc_configured": True})
        oidc_doc = _repo_path("tutorials/tutorial-auth-login-roles-zh.md").is_file()
        return (
            "warn" if oidc_doc else "fail",
            "OIDC not configured; auth doc present" if oidc_doc else "OIDC not configured",
            {"oidc_configured": False, "auth_doc": oidc_doc},
        )

    if probe.startswith("uat:"):
        return evaluate_uat_static(probe)

    return ("na", f"unknown probe: {probe}", evidence)


def _evaluate_item(item: BenchmarkItem) -> Dict[str, Any]:
    mode = item.get("eval_mode") or "manual"
    probe = str(item.get("probe") or "")
    if mode == "manual":
        return {
            **item,
            "status": "manual",
            "message": item.get("hint") or "需人工 UAT",
            "evidence": {"probe": probe},
        }
    status, message, evidence = evaluate_probe(probe)
    if mode == "hybrid" and status == "warn":
        status = "pass"
        message = f"{message} (hybrid: acceptable for pilot)"
    return {**item, "status": status, "message": message, "evidence": evidence}


def _phase_summary(
    items: List[Dict[str, Any]],
    phase: str,
    *,
    live_items: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    phase_items = [x for x in items if x.get("phase") == phase]
    auto_p0 = [
        x
        for x in phase_items
        if x.get("priority") == "P0" and x.get("eval_mode") in ("auto", "hybrid")
    ]
    auto_p0_pass = sum(1 for x in auto_p0 if x.get("status") == "pass")
    manual_p0 = [
        x for x in phase_items if x.get("priority") == "P0" and x.get("eval_mode") == "manual"
    ]
    live_summary = live_phase_summary(live_items or [], phase) if live_items is not None else None
    gate_pass = len(auto_p0) == 0 or auto_p0_pass == len(auto_p0)
    if live_summary and live_summary.get("live_p0_total"):
        gate_pass = gate_pass and bool(live_summary.get("live_gate_pass"))
    out: Dict[str, Any] = {
        "phase": phase,
        "total": len(phase_items),
        "auto_p0_total": len(auto_p0),
        "auto_p0_pass": auto_p0_pass,
        "auto_p0_pass_rate": round(100.0 * auto_p0_pass / len(auto_p0), 1) if auto_p0 else 100.0,
        "manual_p0_total": len(manual_p0),
        "gate_pass": gate_pass,
    }
    if live_summary:
        out.update(live_summary)
    return out


def _probe_score(probe: str) -> float:
    status, _, _ = evaluate_probe(probe)
    if status == "pass":
        return 5.0
    if status == "warn":
        return 3.0
    if status == "manual":
        return 2.5
    if status == "fail":
        return 1.0
    return 0.0


def build_competitive_benchmark() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for dim in COMPETITIVE_DIMENSIONS:
        probes = dim.get("perilla_probes") or []
        if not probes:
            perilla_score = 0.0
        else:
            perilla_score = round(sum(_probe_score(p) for p in probes) / len(probes), 2)
        ref = dim.get("reference") or {}
        mature = float(ref.get("mature_commercial_paas") or 0)
        gap = round(perilla_score - mature, 2)
        rows.append(
            {
                "id": dim.get("id"),
                "label": dim.get("label"),
                "weight": dim.get("weight"),
                "perilla_score": perilla_score,
                "reference_scores": ref,
                "gap_vs_mature_commercial": gap,
                "probes": probes,
            }
        )
    return rows


def build_suite_benchmark_report(
    *,
    phases: Optional[List[str]] = None,
    live_base_url: Optional[str] = None,
    live_headers: Optional[Dict[str, str]] = None,
    inprocess_client: Any = None,
) -> Dict[str, Any]:
    """生成完整对标报告。live_base_url 非空时追加 Live 探针结果。"""
    phase_filter = set(phases) if phases else None
    phase_list = None if phase_filter is None else list(phase_filter)
    items = [
        _evaluate_item(dict(x))
        for x in SUITE_BENCHMARK_ITEMS
        if phase_filter is None or x.get("phase") in phase_filter
    ]
    live_items: List[Dict[str, Any]] = []
    uat_live_items: List[Dict[str, Any]] = []
    if inprocess_client is not None:
        live_items = run_live_probes_inprocess(
            inprocess_client, headers=live_headers, phases=phase_list
        )
        uat_live_items = run_uat_live_probes_inprocess(
            inprocess_client, headers=live_headers, phases=phase_list
        )
        items = items + live_items + uat_live_items
        live_base_url = live_base_url or "inprocess://testclient"
    elif live_base_url and live_base_url.strip():
        base = live_base_url.strip()
        live_items = run_live_probes(base, headers=live_headers, phases=phase_list)
        uat_live_items = run_uat_live_probes(base, headers=live_headers, phases=phase_list)
        items = items + live_items + uat_live_items
    caps = build_enterprise_capabilities()
    competitive = build_competitive_benchmark()
    weighted_gap = 0.0
    weight_sum = 0.0
    for row in competitive:
        w = float(row.get("weight") or 1.0)
        weighted_gap += w * float(row.get("gap_vs_mature_commercial") or 0)
        weight_sum += w
    avg_gap = round(weighted_gap / weight_sum, 2) if weight_sum else 0.0

    combined_live_for_phase = (live_items + uat_live_items) if (live_items or uat_live_items) else None
    phase_summaries = [
        _phase_summary(
            items,
            p,
            live_items=combined_live_for_phase if live_base_url else None,
        )
        for p in ("phase0", "phase1", "phase2")
        if not phase_filter or p in phase_filter
    ]
    overall_gate = all(s.get("gate_pass") for s in phase_summaries)
    live_gate = True
    uat_live_gate = True
    combined_live = live_items + uat_live_items
    if combined_live:
        live_p0 = [x for x in combined_live if x.get("priority") == "P0"]
        live_gate = all(x.get("status") in ("pass", "warn") for x in live_p0) if live_p0 else True
        uat_live_gate = all(
            x.get("status") in ("pass", "warn")
            for x in uat_live_items
            if x.get("priority") == "P0"
        ) if uat_live_items else True
        overall_gate = overall_gate and live_gate

    return {
        "schema_version": 1,
        "report_type": "enterprise_suite_benchmark",
        "goal": "开箱企业套件 · 对标成熟商业 PaaS",
        "live_base_url": live_base_url.strip() if live_base_url else None,
        "phases": phase_summaries,
        "overall_auto_gate_pass": overall_gate,
        "live_gate_pass": live_gate if combined_live else None,
        "uat_live_gate_pass": uat_live_gate if uat_live_items else None,
        "production_readiness": caps.get("production_readiness"),
        "enterprise_capabilities": {
            "identity_boundary_ready": caps.get("identity_boundary_ready"),
            "ha_profile": caps.get("ha_profile"),
            "tenant_enforcement_enabled": caps.get("tenant_enforcement_enabled"),
        },
        "checklist_items": items,
        "live_checklist_items": live_items,
        "uat_live_checklist_items": uat_live_items,
        "competitive_benchmark": competitive,
        "competitive_summary": {
            "avg_gap_vs_mature_commercial": avg_gap,
            "interpretation": (
                "gap>0 表示该维度自动探针得分高于参考基线；"
                "参考分为选型锚点，非第三方实测。"
            ),
        },
        "enterprise_scene_bundles": ENTERPRISE_SCENE_BUNDLES,
    }


def evaluate_suite_gate(
    *,
    phase: str = "all",
    min_auto_p0_pass_rate: float = 100.0,
    live_base_url: Optional[str] = None,
    live_headers: Optional[Dict[str, str]] = None,
    require_live: bool = False,
    inprocess_client: Any = None,
) -> tuple[bool, Dict[str, Any]]:
    phases = None if phase in ("all", "") else [phase]
    live_url = (live_base_url or "").strip() or None
    if require_live and not live_url and inprocess_client is None:
        return False, {
            "pass": False,
            "details": [
                "live probes required but no base URL "
                "(set --live-base-url, ENTERPRISE_SUITE_LIVE_URL, or --inprocess)"
            ],
            "report": {},
        }
    report = build_suite_benchmark_report(
        phases=phases,
        live_base_url=live_url,
        live_headers=live_headers,
        inprocess_client=inprocess_client,
    )
    summaries = report.get("phases") or []
    ok = True
    details: List[str] = []
    for s in summaries:
        rate = float(s.get("auto_p0_pass_rate") or 0)
        gate = bool(s.get("gate_pass")) and rate >= min_auto_p0_pass_rate
        details.append(
            f"{s.get('phase')}: auto P0 pass {s.get('auto_p0_pass')}/{s.get('auto_p0_total')} "
            f"({rate}%) gate={'PASS' if gate else 'FAIL'}"
        )
        ok = ok and gate
    if live_url:
        all_live = list(report.get("live_checklist_items") or []) + list(
            report.get("uat_live_checklist_items") or []
        )
        if all_live:
            live_p0 = [x for x in all_live if x.get("priority") == "P0"]
            live_ok = all(x.get("status") in ("pass", "warn") for x in live_p0) if live_p0 else True
            details.append(
                f"live+uat: P0 pass/warn {sum(1 for x in live_p0 if x.get('status') in ('pass', 'warn'))}/{len(live_p0)} "
                f"gate={'PASS' if live_ok else 'FAIL'} @ {live_url}"
            )
            ok = ok and live_ok
    return ok, {"pass": ok, "details": details, "report": report}
