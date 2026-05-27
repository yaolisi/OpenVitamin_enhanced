"""平台演示包导入：知识库、Skill、MCP、Agent、工作流（含 ID 重映射）。"""
from __future__ import annotations

import asyncio
import copy
import hashlib
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from log import logger
from sqlalchemy.orm import Session

from api.knowledge import CreateKnowledgeBaseRequest, index_document_background
from core.agent_runtime.definition import AgentDefinition, AgentModelParamsJsonMap
from core.knowledge.file_storage import FileStorage
from core.knowledge.knowledge_base_store import KnowledgeBaseStore
from core.knowledge.status import DocumentStatus
from core.models.registry import get_model_registry
from core.workflows.models.workflow import WorkflowCreateRequest
from core.workflows.services.workflow_version_service import WorkflowVersionService
from core.workflows.services.workflow_service import WorkflowService

IMPORT_REF_PREFIX = "$import:"
AUTO_LLM = "__AUTO_LLM__"
AUTO_EMBEDDING = "__AUTO_EMBEDDING__"


@dataclass
class PlatformBundleImportResult:
    bundle_id: str
    knowledge_bases: dict[str, str] = field(default_factory=dict)
    skills: dict[str, str] = field(default_factory=dict)
    mcp_servers: dict[str, str] = field(default_factory=dict)
    mcp_skills_imported: list[str] = field(default_factory=list)
    agents: dict[str, str] = field(default_factory=dict)
    workflows: dict[str, str] = field(default_factory=dict)
    workflow_versions: dict[str, str] = field(default_factory=dict)
    published: dict[str, bool] = field(default_factory=dict)
    documents_indexed: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "knowledge_bases": self.knowledge_bases,
            "skills": self.skills,
            "mcp_servers": self.mcp_servers,
            "mcp_skills_imported": self.mcp_skills_imported,
            "agents": self.agents,
            "workflows": self.workflows,
            "workflow_versions": self.workflow_versions,
            "published": self.published,
            "documents_indexed": self.documents_indexed,
            "warnings": self.warnings,
        }


def _is_import_ref(value: Any) -> bool:
    return isinstance(value, str) and value.startswith(IMPORT_REF_PREFIX)


def _resolve_import_ref(value: str, id_map: dict[str, str]) -> str:
    key = value[len(IMPORT_REF_PREFIX) :].strip()
    if key not in id_map:
        raise ValueError(f"Unresolved import reference: {value}")
    return id_map[key]


def deep_resolve_import_refs(obj: Any, id_map: dict[str, str]) -> Any:
    if _is_import_ref(obj):
        return _resolve_import_ref(obj, id_map)
    if isinstance(obj, dict):
        return {k: deep_resolve_import_refs(v, id_map) for k, v in obj.items()}
    if isinstance(obj, list):
        return [deep_resolve_import_refs(v, id_map) for v in obj]
    return obj


def _resolve_skill_id_list(raw: list[Any], id_map: dict[str, str]) -> list[str]:
    out: list[str] = []
    for item in raw:
        s = str(item).strip()
        if not s:
            continue
        if _is_import_ref(s):
            out.append(_resolve_import_ref(s, id_map))
        else:
            out.append(s)
    return out


def resolve_auto_model_id(token: str, *, kind: str) -> str:
    registry = get_model_registry()
    models = registry.list_models()
    if token not in (AUTO_LLM, AUTO_EMBEDDING):
        return token
    if token == AUTO_EMBEDDING or kind == "embedding":
        for m in models:
            if getattr(m, "model_type", None) == "embedding":
                return m.id
        raise ValueError("No embedding model registered; add an embedding model first.")
    for m in models:
        if getattr(m, "model_type", None) == "llm":
            return m.id
    raise ValueError("No LLM registered; add a chat model first.")


def _kb_store() -> KnowledgeBaseStore:
    from api.knowledge import _kb_store as store

    return store


def _upload_kb_document(
    *,
    kb_id: str,
    filename: str,
    content: bytes,
    user_id: str,
    tenant_id: str,
    wait_index: bool,
) -> str:
    store = _kb_store()
    file_ext = Path(filename).suffix.lower()
    if file_ext not in {".pdf", ".txt", ".md", ".docx"}:
        raise ValueError(f"Unsupported document type: {file_ext}")
    content_hash = hashlib.sha256(content).hexdigest()
    version_id = store.ensure_default_kb_version(kb_id)
    doc_id = store.create_document(
        knowledge_base_id=kb_id,
        source=filename,
        doc_type=file_ext[1:] if file_ext else None,
        status=DocumentStatus.UPLOADED,
        user_id=user_id,
        content_hash=content_hash,
        tenant_id=tenant_id,
    )
    file_path = FileStorage.save_file(kb_id, doc_id, content, filename)
    store.update_document_file_path(doc_id, str(file_path))
    store.update_document_status(doc_id, DocumentStatus.UPLOADED)
    if wait_index:
        index_document_background(
            kb_id=kb_id,
            doc_id=doc_id,
            file_path=file_path,
            doc_type=file_ext[1:] if file_ext else None,
            content_hash=content_hash,
            version_id=version_id,
        )
    return doc_id


def _create_agent_from_spec(
  spec: dict[str, Any],
  *,
  user_id: str,
  tenant_id: str,
  id_map: dict[str, str],
) -> str:
    from api.agents import (
        _apply_response_mode,
        _normalize_id_list,
        _normalize_skill_ids,
        get_agent_registry,
    )
    from core.skills.registry import SkillRegistry

    model_id = resolve_auto_model_id(str(spec.get("model_id") or AUTO_LLM), kind="llm")
    model_registry = get_model_registry()
    if not any(m.id == model_id for m in model_registry.list_models()):
        raise ValueError(f"Model not found: {model_id}")
    rag_raw = spec.get("rag_ids") or []
    rag_ids = []
    for item in rag_raw:
        if _is_import_ref(item):
            rag_ids.append(_resolve_import_ref(item, id_map))
        else:
            rag_ids.append(str(item))
    rag_ids = _normalize_id_list(rag_ids)

    enabled_skills = _resolve_skill_id_list(list(spec.get("enabled_skills") or []), id_map)
    enabled_skills = _normalize_skill_ids(enabled_skills)
    for skill_id in enabled_skills:
        if not SkillRegistry.get(skill_id):
            raise ValueError(f"Skill not found: {skill_id}")

    registry = get_agent_registry()
    agent_id = f"agent_{uuid.uuid4().hex[:8]}"
    model_params = spec.get("model_params")
    mp_dict = model_params if isinstance(model_params, dict) else None
    agent = AgentDefinition(
        agent_id=agent_id,
        name=str(spec.get("name") or "Agent").strip(),
        description=str(spec.get("description") or "").strip(),
        model_id=model_id,
        system_prompt=str(spec.get("system_prompt") or "").strip(),
        enabled_skills=enabled_skills,
        tool_ids=[s[8:] for s in enabled_skills if s.startswith("builtin_")],
        rag_ids=rag_ids,
        max_steps=int(spec.get("max_steps") or 20),
        temperature=float(spec.get("temperature") if spec.get("temperature") is not None else 0.7),
        slug=(str(spec["slug"]).strip() if spec.get("slug") else None),
        execution_mode=str(spec.get("execution_mode") or "legacy"),
        model_params=AgentModelParamsJsonMap.model_validate(
            _apply_response_mode(mp_dict, spec.get("response_mode"), enabled_skills) or {}
        ),
    )
    if not registry.create_agent(agent):
        raise RuntimeError(f"Failed to create agent: {agent.name}")
    logger.info("[PlatformBundle] Created agent %s (%s)", agent_id, agent.name)
    return agent_id


def _create_skill_from_spec(spec: dict[str, Any], *, id_map: dict[str, str]) -> str:
    from core.skills.registry import SkillRegistry
    from core.skills.store import get_skill_store

    bkey = str(spec.get("bundle_key") or "")
    if not bkey:
        raise ValueError("skills[].bundle_key is required")
    store = get_skill_store()
    desired_id = str(spec.get("skill_id") or "").strip() or None
    if desired_id and store.get(desired_id):
        id_map[bkey] = desired_id
        return desired_id
    definition = deep_resolve_import_refs(dict(spec.get("definition") or {}), id_map)
    skill = store.create(
        name=str(spec.get("name") or bkey),
        description=str(spec.get("description") or ""),
        category=str(spec.get("category") or "demo"),
        type=str(spec.get("type") or "prompt"),
        definition=definition,
        input_schema=dict(
            spec.get("input_schema")
            or {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}
        ),
        enabled=bool(spec.get("enabled", True)),
        skill_id=desired_id,
    )
    SkillRegistry.register(skill.to_v2())
    id_map[bkey] = skill.id
    logger.info("[PlatformBundle] Created skill %s (%s)", skill.id, skill.name)
    return skill.id


def _create_mcp_server_from_spec(
    spec: dict[str, Any],
    *,
    tenant_id: str,
    id_map: dict[str, str],
) -> str:
    from core.mcp.persistence import create_mcp_server

    bkey = str(spec.get("bundle_key") or "")
    if not bkey:
        raise ValueError("mcp_servers[].bundle_key is required")
    transport = str(spec.get("transport") or "stdio").strip().lower()
    command = list(spec.get("command") or [])
    row = create_mcp_server(
        name=str(spec.get("name") or bkey),
        description=str(spec.get("description") or ""),
        transport=transport,
        command=command,
        base_url=str(spec.get("base_url") or "").strip() or None,
        cwd=str(spec.get("cwd") or "").strip() or None,
        env=dict(spec.get("env") or {}) if isinstance(spec.get("env"), dict) else None,
        enabled=bool(spec.get("enabled", True)),
        server_id=str(spec.get("server_id") or "").strip() or None,
        tenant_id=tenant_id,
    )
    sid = str(row.get("id") or "")
    id_map[bkey] = sid
    logger.info("[PlatformBundle] Created MCP server %s (%s)", sid, row.get("name"))
    return sid


async def _import_mcp_tools_optional(
    server_id: str,
    *,
    tenant_id: str,
    tool_names: Optional[list[str]],
    optional: bool,
) -> tuple[list[str], Optional[str]]:
    from core.mcp.service import import_mcp_tools_as_skills

    try:
        raw = await import_mcp_tools_as_skills(
            server_id,
            tool_names=tool_names,
            tenant_id=tenant_id,
        )
        return list(raw.get("imported") or []), None
    except Exception as exc:
        msg = str(exc)
        if optional:
            return [], msg
        raise


def import_platform_bundle(
    bundle: dict[str, Any],
    *,
    bundle_dir: Path,
    db: Session,
    user_id: str,
    tenant_id: str,
    namespace: Optional[str] = None,
    publish_workflows: bool = False,
    wait_document_index: bool = True,
) -> PlatformBundleImportResult:
    if int(bundle.get("schema_version") or 0) != 1:
        raise ValueError("Unsupported platform bundle schema_version (expected 1)")
    bundle_id = str(bundle.get("bundle_id") or "unknown")
    result = PlatformBundleImportResult(bundle_id=bundle_id)
    id_map: dict[str, str] = {}
    ns = (namespace or tenant_id or "default").strip()

    for kb_spec in bundle.get("knowledge_bases") or []:
        if not isinstance(kb_spec, dict):
            continue
        bkey = str(kb_spec.get("bundle_key") or "")
        if not bkey:
            raise ValueError("knowledge_bases[].bundle_key is required")
        embed_id = resolve_auto_model_id(
            str(kb_spec.get("embedding_model_id") or AUTO_EMBEDDING),
            kind="embedding",
        )
        req = CreateKnowledgeBaseRequest(
            name=str(kb_spec.get("name") or bkey),
            description=kb_spec.get("description"),
            embedding_model_id=embed_id,
            chunk_size=int(kb_spec.get("chunk_size") or 512),
            chunk_overlap=int(kb_spec.get("chunk_overlap") or 50),
        )
        store = _kb_store()
        kb_id = store.create_knowledge_base(
            name=req.name,
            description=req.description,
            embedding_model_id=req.embedding_model_id,
            user_id=user_id,
            chunk_size=req.chunk_size,
            chunk_overlap=req.chunk_overlap,
            tenant_id=tenant_id,
        )
        id_map[bkey] = kb_id
        result.knowledge_bases[bkey] = kb_id

        for doc in kb_spec.get("documents") or []:
            if not isinstance(doc, dict):
                continue
            filename = str(doc.get("filename") or "doc.md")
            content: Optional[bytes] = None
            if doc.get("content") is not None:
                content = str(doc["content"]).encode("utf-8")
            elif doc.get("content_path"):
                rel = Path(str(doc["content_path"]))
                doc_path = (bundle_dir / rel).resolve()
                if not doc_path.is_file():
                    doc_path = (bundle_dir / "documents" / rel.name).resolve()
                content = doc_path.read_bytes()
            if content is None:
                result.warnings.append(f"Skipped document without content: {filename}")
                continue
            doc_id = _upload_kb_document(
                kb_id=kb_id,
                filename=filename,
                content=content,
                user_id=user_id,
                tenant_id=tenant_id,
                wait_index=wait_document_index,
            )
            result.documents_indexed.append(doc_id)

    for skill_spec in bundle.get("skills") or []:
        if not isinstance(skill_spec, dict):
            continue
        bkey = str(skill_spec.get("bundle_key") or "")
        skill_id = _create_skill_from_spec(skill_spec, id_map=id_map)
        result.skills[bkey] = skill_id

    for mcp_spec in bundle.get("mcp_servers") or []:
        if not isinstance(mcp_spec, dict):
            continue
        bkey = str(mcp_spec.get("bundle_key") or "")
        sid = _create_mcp_server_from_spec(mcp_spec, tenant_id=tenant_id, id_map=id_map)
        result.mcp_servers[bkey] = sid

    for imp_spec in bundle.get("mcp_tool_imports") or []:
        if not isinstance(imp_spec, dict):
            continue
        server_key = str(imp_spec.get("server_bundle_key") or "")
        if not server_key or server_key not in id_map:
            result.warnings.append(f"MCP tool import skipped: unknown server {server_key}")
            continue
        server_id = id_map[server_key]
        mcp_row = None
        for mcp_spec in bundle.get("mcp_servers") or []:
            if isinstance(mcp_spec, dict) and str(mcp_spec.get("bundle_key") or "") == server_key:
                mcp_row = mcp_spec
                break
        if imp_spec.get("skip_if_disabled") and mcp_row and not bool(mcp_row.get("enabled", True)):
            result.warnings.append(
                f"MCP tool import skipped (server disabled): {server_key}; enable in Settings → MCP then Probe/Import"
            )
            continue
        optional = bool(imp_spec.get("optional", True))
        tool_names = imp_spec.get("tool_names")
        tn = [str(x) for x in tool_names] if isinstance(tool_names, list) else None
        imported, err = asyncio.run(
            _import_mcp_tools_optional(
                server_id,
                tenant_id=tenant_id,
                tool_names=tn,
                optional=optional,
            )
        )
        result.mcp_skills_imported.extend(imported)
        for sid in imported:
            id_map[f"mcp_skill:{sid}"] = sid
        if err:
            result.warnings.append(f"MCP tool import ({server_key}): {err}")

    for agent_spec in bundle.get("agents") or []:
        if not isinstance(agent_spec, dict):
            continue
        bkey = str(agent_spec.get("bundle_key") or "")
        if not bkey:
            raise ValueError("agents[].bundle_key is required")
        agent_id = _create_agent_from_spec(
            agent_spec,
            user_id=user_id,
            tenant_id=tenant_id,
            id_map=id_map,
        )
        id_map[bkey] = agent_id
        result.agents[bkey] = agent_id

    wf_service = WorkflowService(db)
    ver_service = WorkflowVersionService(db)
    for wf_spec in bundle.get("workflows") or []:
        if not isinstance(wf_spec, dict):
            continue
        bkey = str(wf_spec.get("bundle_key") or "main")
        dag_raw = wf_spec.get("dag")
        if not isinstance(dag_raw, dict):
            raise ValueError(f"workflows[{bkey}].dag must be an object")
        dag = deep_resolve_import_refs(copy.deepcopy(dag_raw), id_map)
        wf_req = WorkflowCreateRequest(
            namespace=ns,
            name=str(wf_spec.get("workflow_name") or wf_spec.get("name") or bkey),
            description=str(wf_spec.get("description") or ""),
            tags=list(wf_spec.get("tags") or ["demo", "platform-bundle"]),
            metadata={
                "bundle_id": bundle_id,
                "workflow_bundle_key": bkey,
            },
        )
        workflow = wf_service.create_workflow(wf_req, user_id)
        wf_id = workflow.id
        definition = ver_service.create_definition(
            workflow_id=wf_id,
            description=f"Imported platform bundle {bundle_id}",
            created_by=user_id,
        )
        from core.workflows.models.workflow_version import WorkflowDAG

        version = ver_service.create_version(
            workflow_id=wf_id,
            definition_id=definition.definition_id,
            dag=WorkflowDAG.model_validate(dag),
            description=f"Platform bundle {bundle_id}",
            created_by=user_id,
        )
        wf_service.repository.update(
            wf_id,
            {"latest_version_id": version.version_id},
            user_id,
        )
        id_map[bkey] = wf_id
        result.workflows[bkey] = wf_id
        result.workflow_versions[bkey] = version.version_id
        if publish_workflows:
            ver_service.publish_version(version.version_id, user_id)
            result.published[bkey] = True

    return result
