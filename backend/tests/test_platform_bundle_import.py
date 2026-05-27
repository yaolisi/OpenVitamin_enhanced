"""平台演示包：引用解析与清单加载。"""
from __future__ import annotations

from core.demos.bundle_registry import list_platform_bundle_manifests, load_platform_bundle
from core.demos.platform_bundle_import import deep_resolve_import_refs


def test_deep_resolve_import_refs() -> None:
    id_map = {"agent_web": "agent_abc", "kb_demo": "kb_xyz"}
    raw = {
        "nodes": [
            {
                "config": {
                    "agent_id": "$import:agent_web",
                    "rag_ids": ["$import:kb_demo"],
                }
            }
        ],
        "plain": "keep",
    }
    out = deep_resolve_import_refs(raw, id_map)
    assert out["nodes"][0]["config"]["agent_id"] == "agent_abc"
    assert out["nodes"][0]["config"]["rag_ids"] == ["kb_xyz"]
    assert out["plain"] == "keep"


def test_list_platform_bundles_includes_demos() -> None:
    items = list_platform_bundle_manifests()
    ids = {x["bundle_id"] for x in items}
    assert "rag-research-verify" in ids
    assert "release-brief-gate" in ids


def test_load_rag_research_bundle() -> None:
    bundle, bundle_dir = load_platform_bundle("rag-research-verify")
    assert bundle["bundle_id"] == "rag-research-verify"
    assert bundle_dir.is_dir()
    assert len(bundle.get("knowledge_bases") or []) >= 1
    assert len(bundle.get("agents") or []) >= 2
    assert len(bundle.get("skills") or []) >= 1
    assert len(bundle.get("mcp_servers") or []) >= 1


def test_resolve_skill_refs_in_agent_spec() -> None:
    id_map = {"skill_x": "demo.bundle.skill_x"}
    from core.demos.platform_bundle_import import _resolve_skill_id_list

    out = _resolve_skill_id_list(["builtin_web.search", "$import:skill_x"], id_map)
    assert out == ["builtin_web.search", "demo.bundle.skill_x"]
