"""从当前环境导出平台 bundle（JSON + documents/ 侧车文件）。"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from log import logger
from sqlalchemy.orm import Session

from core.agent_runtime.definition import get_agent_registry
from core.demos.bundle_collect import ExportDependencyIds, collect_ids_from_dag, merge_dependency_ids
from core.demos.bundle_refs import make_bundle_key, make_import_ref
from core.demos.bundle_zip import DOCUMENTS_DIR
from core.demos.platform_bundle_import import AUTO_EMBEDDING, AUTO_LLM
from core.knowledge.file_storage import FileStorage
from core.knowledge.knowledge_base_store import KnowledgeBaseStore
from core.mcp.persistence import get_mcp_server
from core.skills.store import get_skill_store
from core.workflows.services.workflow_service import WorkflowService
from core.workflows.services.workflow_version_service import WorkflowVersionService

TEXT_DOC_EXTS = {".txt", ".md", ".markdown"}


@dataclass
class PlatformBundleExportResult:
    bundle: dict[str, Any]
    sidecar_files: dict[str, bytes] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    discovered: ExportDependencyIds = field(default_factory=ExportDependencyIds)


def _kb_store() -> KnowledgeBaseStore:
    return KnowledgeBaseStore()


def discover_export_dependencies(
    *,
    db: Session,
    workflow_ids: list[str],
    tenant_id: str,
    extra_agent_ids: Optional[list[str]] = None,
    extra_kb_ids: Optional[list[str]] = None,
    extra_skill_ids: Optional[list[str]] = None,
    extra_mcp_ids: Optional[list[str]] = None,
) -> ExportDependencyIds:
    deps = ExportDependencyIds(
        workflow_ids=set(workflow_ids),
        agent_ids=set(extra_agent_ids or []),
        knowledge_base_ids=set(extra_kb_ids or []),
        skill_ids=set(extra_skill_ids or []),
        mcp_server_ids=set(extra_mcp_ids or []),
    )
    ver_service = WorkflowVersionService(db)
    wf_service = WorkflowService(db)
    for wf_id in workflow_ids:
        wf = wf_service.get_workflow(wf_id, tenant_id=tenant_id)
        if not wf or not wf.latest_version_id:
            continue
        ver = ver_service.get_version(wf.latest_version_id)
        if not ver or not ver.dag:
            continue
        dag_dict = ver.dag.model_dump(mode="json")
        partial = collect_ids_from_dag(dag_dict, workflow_id=wf_id)
        deps = merge_dependency_ids(deps, partial)
    agent_registry = get_agent_registry()
    pending_agents = list(deps.agent_ids)
    seen_agents: set[str] = set()
    while pending_agents:
        aid = pending_agents.pop()
        if aid in seen_agents:
            continue
        seen_agents.add(aid)
        agent = agent_registry.get_agent(aid)
        if not agent:
            continue
        for rid in agent.rag_ids or []:
            deps.knowledge_base_ids.add(rid)
        for sid in agent.enabled_skills or []:
            if sid.startswith("builtin_"):
                continue
            deps.skill_ids.add(sid)
    skill_store = get_skill_store()
    for sid in list(deps.skill_ids):
        skill = skill_store.get(sid)
        if skill and skill.is_mcp_skill():
            srv = (skill.definition or {}).get("server_config_id")
            if isinstance(srv, str) and srv.strip():
                deps.mcp_server_ids.add(srv.strip())
    return deps


def export_platform_bundle(
    *,
    db: Session,
    user_id: str,
    tenant_id: str,
    bundle_id: str,
    name: str,
    description: str = "",
    workflow_ids: list[str],
    agent_ids: Optional[list[str]] = None,
    knowledge_base_ids: Optional[list[str]] = None,
    skill_ids: Optional[list[str]] = None,
    mcp_server_ids: Optional[list[str]] = None,
    use_model_placeholders: bool = True,
    include_documents: bool = True,
    export_mcp_tool_imports: bool = True,
) -> PlatformBundleExportResult:
    warnings: list[str] = []
    discovered = discover_export_dependencies(
        db=db,
        workflow_ids=workflow_ids,
        tenant_id=tenant_id,
        extra_agent_ids=agent_ids,
        extra_kb_ids=knowledge_base_ids,
        extra_skill_ids=skill_ids,
        extra_mcp_ids=mcp_server_ids,
    )
    id_to_bkey: dict[str, str] = {}
    used_keys: set[str] = set()
    sidecar: dict[str, bytes] = {}

    def ref_for(entity_id: str) -> str:
        return make_import_ref(id_to_bkey[entity_id])

    bundle: dict[str, Any] = {
        "schema_version": 1,
        "bundle_type": "platform",
        "bundle_id": bundle_id,
        "name": name,
        "description": description,
        "knowledge_bases": [],
        "skills": [],
        "mcp_servers": [],
        "mcp_tool_imports": [],
        "agents": [],
        "workflows": [],
    }

    store = _kb_store()
    for kb_id in sorted(discovered.knowledge_base_ids):
        try:
            kb = store.get_knowledge_base(kb_id, user_id=user_id, tenant_id=tenant_id)
        except Exception as exc:
            warnings.append(f"Skip knowledge base {kb_id}: {exc}")
            continue
        if not kb:
            warnings.append(f"Knowledge base not found: {kb_id}")
            continue
        bkey = make_bundle_key("kb", str(kb.get("name") or ""), kb_id, used_keys)
        id_to_bkey[kb_id] = bkey
        embed = str(kb.get("embedding_model_id") or "")
        if use_model_placeholders:
            embed = AUTO_EMBEDDING
        kb_spec: dict[str, Any] = {
            "bundle_key": bkey,
            "name": kb.get("name") or bkey,
            "description": kb.get("description") or "",
            "embedding_model_id": embed,
            "chunk_size": int(kb.get("chunk_size") or 512),
            "chunk_overlap": int(kb.get("chunk_overlap") or 50),
            "documents": [],
        }
        docs = store.list_documents(kb_id, user_id=user_id, tenant_id=tenant_id)
        for doc in docs:
            if not isinstance(doc, dict):
                continue
            filename = str(doc.get("source") or doc.get("filename") or "document.txt")
            doc_id = str(doc.get("id") or "")
            file_path = FileStorage.get_file_path(kb_id, doc_id, filename)
            doc_entry: dict[str, Any] = {"filename": filename}
            ext = Path(filename).suffix.lower()
            if include_documents and file_path and file_path.is_file():
                raw = file_path.read_bytes()
                rel = f"{DOCUMENTS_DIR}/{filename}"
                if ext in TEXT_DOC_EXTS:
                    try:
                        doc_entry["content"] = raw.decode("utf-8")
                    except UnicodeDecodeError:
                        sidecar[rel] = raw
                        doc_entry["content_path"] = rel
                else:
                    sidecar[rel] = raw
                    doc_entry["content_path"] = rel
                    if ext not in {".pdf", ".docx"}:
                        warnings.append(f"Document {filename}: exported as binary at {rel}")
            else:
                warnings.append(f"Document {filename} skipped (file missing or include_documents=false)")
            kb_spec["documents"].append(doc_entry)
        bundle["knowledge_bases"].append(kb_spec)

    skill_store = get_skill_store()
    for sid in sorted(discovered.skill_ids):
        skill = skill_store.get(sid)
        if not skill:
            warnings.append(f"Skill not found: {sid}")
            continue
        if skill.is_mcp_skill():
            warnings.append(f"Skill {sid} is MCP-derived; export MCP server + use mcp_tool_imports on re-import")
            continue
        bkey = make_bundle_key("skill", skill.name, sid, used_keys)
        id_to_bkey[sid] = bkey
        bundle["skills"].append(
            {
                "bundle_key": bkey,
                "skill_id": skill.id,
                "name": skill.name,
                "description": skill.description,
                "category": skill.category or "exported",
                "type": skill.type,
                "definition": dict(skill.definition or {}),
                "input_schema": dict(skill.input_schema or {}),
                "enabled": bool(skill.enabled),
            }
        )

    for mcp_id in sorted(discovered.mcp_server_ids):
        row = get_mcp_server(mcp_id, tenant_id=tenant_id)
        if not row:
            warnings.append(f"MCP server not found: {mcp_id}")
            continue
        bkey = make_bundle_key("mcp", str(row.get("name") or ""), mcp_id, used_keys)
        id_to_bkey[mcp_id] = bkey
        bundle["mcp_servers"].append(
            {
                "bundle_key": bkey,
                "name": row.get("name") or bkey,
                "description": row.get("description") or "",
                "transport": row.get("transport") or "stdio",
                "command": list(row.get("command") or []),
                "base_url": row.get("base_url") or None,
                "cwd": row.get("cwd") or None,
                "env": dict(row.get("env") or {}),
                "enabled": bool(row.get("enabled")),
                "optional": True,
            }
        )
        if export_mcp_tool_imports:
            bundle["mcp_tool_imports"].append(
                {
                    "server_bundle_key": bkey,
                    "optional": True,
                    "skip_if_disabled": True,
                }
            )

    agent_registry = get_agent_registry()
    for aid in sorted(discovered.agent_ids):
        agent = agent_registry.get_agent(aid)
        if not agent:
            warnings.append(f"Agent not found: {aid}")
            continue
        bkey = make_bundle_key("agent", agent.name, aid, used_keys)
        id_to_bkey[aid] = bkey
        model_id = agent.model_id
        if use_model_placeholders:
            model_id = AUTO_LLM
        enabled_skills: list[str] = []
        for sid in agent.enabled_skills or []:
            if sid.startswith("builtin_"):
                enabled_skills.append(sid)
            elif sid in id_to_bkey:
                enabled_skills.append(ref_for(sid))
            else:
                enabled_skills.append(sid)
                warnings.append(f"Agent {agent.name}: skill {sid} not exported, kept raw id")
        rag_ids = [ref_for(r) if r in id_to_bkey else r for r in (agent.rag_ids or [])]
        spec: dict[str, Any] = {
            "bundle_key": bkey,
            "name": agent.name,
            "description": agent.description or "",
            "model_id": model_id,
            "enabled_skills": enabled_skills,
            "rag_ids": rag_ids,
            "system_prompt": agent.system_prompt or "",
            "max_steps": int(agent.max_steps or 20),
            "temperature": float(agent.temperature if agent.temperature is not None else 0.7),
        }
        if agent.slug:
            spec["slug"] = agent.slug
        if agent.execution_mode:
            spec["execution_mode"] = agent.execution_mode
        bundle["agents"].append(spec)

    ver_service = WorkflowVersionService(db)
    wf_service = WorkflowService(db)
    from core.demos.platform_bundle_import import deep_resolve_import_refs

    for wf_id in workflow_ids:
        wf = wf_service.get_workflow(wf_id, tenant_id=tenant_id)
        if not wf:
            warnings.append(f"Workflow not found: {wf_id}")
            continue
        if not wf.latest_version_id:
            warnings.append(f"Workflow {wf_id} has no version")
            continue
        ver = ver_service.get_version(wf.latest_version_id)
        if not ver or not ver.dag:
            warnings.append(f"Workflow {wf_id} version missing DAG")
            continue
        wf_bkey = make_bundle_key("wf", wf.name, wf_id, used_keys)
        id_to_bkey[wf_id] = wf_bkey
        dag_dict = ver.dag.model_dump(mode="json")
        dag_export = deep_resolve_import_refs(dag_dict, id_to_bkey)
        wf_spec: dict[str, Any] = {
            "bundle_key": wf_bkey,
            "workflow_name": wf.name,
            "description": wf.description or "",
            "tags": list(wf.tags or []) if hasattr(wf, "tags") and wf.tags else [],
            "dag": dag_export,
        }
        meta = wf.metadata if isinstance(getattr(wf, "metadata", None), dict) else {}
        if isinstance(meta.get("sample_input"), dict):
            wf_spec["sample_input"] = meta["sample_input"]
        bundle["workflows"].append(wf_spec)

    if not bundle["workflows"]:
        raise ValueError("Export produced no workflows; check workflow_ids and tenant access")

    logger.info("[PlatformBundle] Exported bundle %s (%d workflows)", bundle_id, len(bundle["workflows"]))
    return PlatformBundleExportResult(
        bundle=bundle,
        sidecar_files=sidecar,
        warnings=warnings,
        discovered=discovered,
    )
