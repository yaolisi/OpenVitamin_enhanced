"""Bundle 导入预览、差异与导入后步骤建议。"""
from __future__ import annotations

from typing import Any, Optional

from core.demos.bundle_conflicts import detect_import_conflicts
from core.demos.bundle_preflight import check_import_environment
from core.demos.bundle_validate import bundle_display_id, validate_bundle


def _count_docs(bundle: dict[str, Any]) -> int:
    n = 0
    for kb in bundle.get("knowledge_bases") or []:
        if isinstance(kb, dict):
            n += len(kb.get("documents") or [])
    return n


def preview_import_bundle(
    bundle: dict[str, Any],
    *,
    tenant_id: str,
    user_id: str,
    kind: Optional[str] = None,
) -> dict[str, Any]:
    resolved_kind = validate_bundle(bundle, kind=kind)  # type: ignore[arg-type]
    bid = bundle_display_id(bundle)
    mcp_disabled = sum(
        1
        for m in bundle.get("mcp_servers") or []
        if isinstance(m, dict) and not bool(m.get("enabled", True))
    )
    summary = {
        "bundle_id": bid,
        "kind": resolved_kind,
        "knowledge_bases": len(bundle.get("knowledge_bases") or []),
        "skills": len(bundle.get("skills") or []),
        "mcp_servers": len(bundle.get("mcp_servers") or []),
        "agents": len(bundle.get("agents") or []),
        "workflows": len(bundle.get("workflows") or []) if resolved_kind == "platform" else 1,
        "documents": _count_docs(bundle),
        "mcp_disabled_count": mcp_disabled,
    }
    ui = bundle.get("ui_hints") if isinstance(bundle.get("ui_hints"), dict) else {}
    return {
        "ok": True,
        "bundle_id": bid,
        "kind": resolved_kind,
        "summary": summary,
        "builtin_skill_catalog": list(bundle.get("builtin_skill_catalog") or []),
        "recommended_eval_suite": bundle.get("recommended_eval_suite") or ui.get("recommended_eval_suite"),
        "conflicts": detect_import_conflicts(bundle, tenant_id=tenant_id, user_id=user_id),
        "environment": check_import_environment(tenant_id=tenant_id, bundle=bundle),
        "next_steps_preview": build_next_steps_preview(bundle, kind=resolved_kind),
        "estimated_index_seconds": min(600, summary["documents"] * 15),
    }


def diff_bundle_against_environment(
    bundle: dict[str, Any],
    *,
    tenant_id: str,
    user_id: str,
) -> dict[str, Any]:
    conflicts = detect_import_conflicts(bundle, tenant_id=tenant_id, user_id=user_id)
    will_create = {
        "knowledge_bases": len(bundle.get("knowledge_bases") or []),
        "skills": len(bundle.get("skills") or []) - sum(1 for c in conflicts if c["kind"] == "skill"),
        "agents": len(bundle.get("agents") or []) - sum(1 for c in conflicts if c["kind"] == "agent"),
        "workflows": len(bundle.get("workflows") or []) or (1 if bundle.get("dag") else 0),
    }
    return {
        "will_create": will_create,
        "conflicts": conflicts,
        "unchanged_if_skip": [c for c in conflicts],
    }


def build_next_steps_preview(bundle: dict[str, Any], *, kind: str) -> list[dict[str, str]]:
    """导入前预览：静态路径填 href，依赖导入后 ID 的仅填 href_hint。"""
    steps: list[dict[str, str]] = []
    steps.append(
        {
            "id": "edit_workflow",
            "label": "open_workflow_editor",
            "href": "/workflow/create",
            "href_hint": "/workflow/{id}/edit",
        }
    )
    if bundle.get("knowledge_bases"):
        steps.append(
            {
                "id": "kb_index",
                "label": "check_kb_indexing",
                "href": "/knowledge",
                "href_hint": "/knowledge/{id}",
            }
        )
    if bundle.get("mcp_servers"):
        steps.append(
            {
                "id": "mcp_enable",
                "label": "enable_mcp_template",
                "href": "/settings/mcp",
                "href_hint": "/settings/mcp",
            }
        )
    wf = (bundle.get("workflows") or [None])[0] if kind == "platform" else bundle
    sample = None
    if isinstance(wf, dict):
        sample = wf.get("sample_input")
    elif bundle.get("sample_input"):
        sample = bundle.get("sample_input")
    if isinstance(sample, dict) and sample:
        steps.append(
            {
                "id": "trial_run",
                "label": "run_with_sample_input",
                "href_hint": "/workflow/{id}/run",
            }
        )
    ui = bundle.get("ui_hints") if isinstance(bundle.get("ui_hints"), dict) else {}
    eval_suite = bundle.get("recommended_eval_suite") or ui.get("recommended_eval_suite")
    if eval_suite:
        steps.append(
            {
                "id": "eval",
                "label": "run_eval_suite",
                "href": "/settings/eval",
                "href_hint": "/settings/eval",
            }
        )
    return steps


def build_next_steps_from_result(
    *,
    kind: str,
    response_hints: dict[str, Any],
    sample_input: Optional[dict[str, Any]],
    has_kb: bool,
    has_mcp: bool,
    recommended_eval: Optional[str],
) -> list[dict[str, str]]:
    steps: list[dict[str, str]] = []
    edit = response_hints.get("edit_url_hint")
    if edit:
        steps.append({"id": "edit_workflow", "label": "open_workflow_editor", "href": str(edit)})
    if has_kb:
        kb_hints = response_hints.get("knowledge_url_hints") or {}
        first_kb = next(iter(kb_hints.values()), None)
        if first_kb:
            steps.append({"id": "kb_index", "label": "check_kb_indexing", "href": str(first_kb)})
    if has_mcp:
        steps.append({"id": "mcp_enable", "label": "enable_mcp_template", "href": "/settings/mcp"})
    run = response_hints.get("run_url_hint")
    if run:
        steps.append({"id": "trial_run", "label": "run_with_sample_input", "href": str(run)})
    agents_hints = response_hints.get("agents_url_hints") or {}
    first_agent = next(iter(agents_hints.values()), None)
    if first_agent:
        steps.append({"id": "open_agent", "label": "open_agent_editor", "href": str(first_agent)})
    if recommended_eval:
        steps.append({"id": "eval", "label": "run_eval_suite", "href": "/settings/eval"})
    return steps
