"""一键导入执行（内置 catalog / 上传 JSON / ZIP 共用）。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional, Union

from sqlalchemy.orm import Session

from core.demos.bundle_registry import load_platform_bundle
from core.demos.bundle_validate import (
    ImportKind,
    bundle_display_id,
    validate_bundle,
)
from core.demos.bundle_zip import resolve_document_path, unpack_bundle_zip
from core.demos.platform_bundle_import import PlatformBundleImportResult, import_platform_bundle
from core.demos.workflow_bundle_import import WorkflowBundleImportResult, import_workflow_bundle_data
from core.demos.workflow_bundle_registry import load_workflow_bundle

ImportResult = Union[PlatformBundleImportResult, WorkflowBundleImportResult]

UPLOAD_BUNDLE_DIR = Path("/tmp/perilla-bundle-upload")


def parse_upload_bytes(raw: bytes, *, filename: str = "") -> tuple[dict[str, Any], Path, list[str]]:
    """解析上传的 JSON 或 ZIP，返回 bundle、bundle_dir（供 content_path 解析）。"""
    warnings: list[str] = []
    name = (filename or "").lower()
    if name.endswith(".zip") or raw[:2] == b"PK":
        bundle, bundle_dir, _manifest = unpack_bundle_zip(raw)
        return bundle, bundle_dir, warnings
    try:
        bundle = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid JSON upload: {exc}") from exc
    if not isinstance(bundle, dict):
        raise ValueError("Bundle root must be a JSON object")
    return bundle, UPLOAD_BUNDLE_DIR, warnings


def _normalize_upload_documents(
    bundle: dict[str, Any], bundle_dir: Path, warnings: list[str]
) -> None:
    for kb in bundle.get("knowledge_bases") or []:
        if not isinstance(kb, dict):
            continue
        for doc in kb.get("documents") or []:
            if not isinstance(doc, dict):
                continue
            cp = doc.get("content_path")
            if cp and doc.get("content") is None:
                resolved = resolve_document_path(bundle_dir, str(cp))
                if resolved is None:
                    warnings.append(
                        f"Document {doc.get('filename')}: content_path not found ({cp}); "
                        "use ZIP with documents/ or inline content"
                    )


def execute_catalog_import(
    *,
    kind: ImportKind,
    bundle_id: str,
    db: Session,
    user_id: str,
    tenant_id: str,
    namespace: Optional[str],
    publish_workflows: bool,
    wait_document_index: bool,
) -> ImportResult:
    if kind == "platform":
        bundle, bundle_dir = load_platform_bundle(bundle_id)
        return import_platform_bundle(
            bundle,
            bundle_dir=bundle_dir,
            db=db,
            user_id=user_id,
            tenant_id=tenant_id,
            namespace=namespace,
            publish_workflows=publish_workflows,
            wait_document_index=wait_document_index,
        )
    bundle = load_workflow_bundle(bundle_id)
    return import_workflow_bundle_data(
        bundle,
        bundle_id=bundle_id,
        db=db,
        user_id=user_id,
        tenant_id=tenant_id,
        namespace=namespace,
        publish=publish_workflows,
    )


def execute_upload_import(
    bundle: dict[str, Any],
    *,
    bundle_dir: Path,
    kind: ImportKind | None,
    db: Session,
    user_id: str,
    tenant_id: str,
    namespace: Optional[str],
    publish_workflows: bool,
    wait_document_index: bool,
    extra_warnings: Optional[list[str]] = None,
) -> ImportResult:
    warnings = list(extra_warnings or [])
    _normalize_upload_documents(bundle, bundle_dir, warnings)
    resolved = validate_bundle(bundle, kind=kind)
    bid = bundle_display_id(bundle)
    if resolved == "platform":
        result = import_platform_bundle(
            bundle,
            bundle_dir=bundle_dir,
            db=db,
            user_id=user_id,
            tenant_id=tenant_id,
            namespace=namespace,
            publish_workflows=publish_workflows,
            wait_document_index=wait_document_index,
        )
        result.warnings = warnings + result.warnings
        return result
    result = import_workflow_bundle_data(
        bundle,
        bundle_id=bid,
        db=db,
        user_id=user_id,
        tenant_id=tenant_id,
        namespace=namespace,
        publish=publish_workflows,
    )
    result.warnings = warnings + result.warnings
    return result
