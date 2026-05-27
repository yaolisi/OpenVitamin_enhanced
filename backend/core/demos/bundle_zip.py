"""Bundle ZIP 打包与解包（manifest + documents/）。"""
from __future__ import annotations

import io
import json
import re
import zipfile
from pathlib import Path
from typing import Any

BUNDLE_JSON_NAMES = (
    "bundle.platform-bundle.json",
    "bundle.bundle.json",
    "manifest.json",
)
DOCUMENTS_DIR = "documents"


def pick_manifest_name(bundle: dict[str, Any], kind: str) -> str:
    bid = str(bundle.get("bundle_id") or bundle.get("demo_id") or "exported-bundle")
    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "-", bid).strip("-") or "exported-bundle"
    if kind == "workflow":
        return f"{safe}.bundle.json"
    return f"{safe}.platform-bundle.json"


def pack_bundle_zip(
    bundle: dict[str, Any],
    *,
    kind: str,
    sidecar_files: dict[str, bytes] | None = None,
) -> tuple[bytes, str]:
    """返回 (zip_bytes, manifest_filename)。"""
    manifest_name = pick_manifest_name(bundle, kind)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            manifest_name,
            json.dumps(bundle, ensure_ascii=False, indent=2).encode("utf-8"),
        )
        for rel_path, content in (sidecar_files or {}).items():
            rel = rel_path.lstrip("/").replace("\\", "/")
            if rel == manifest_name:
                continue
            zf.writestr(rel, content)
    return buf.getvalue(), manifest_name


def unpack_bundle_zip(data: bytes) -> tuple[dict[str, Any], Path, str]:
    """解压 ZIP，返回 (bundle_dict, bundle_dir, manifest_name)。"""
    import tempfile

    tmp = Path(tempfile.mkdtemp(prefix="perilla-bundle-"))
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        zf.extractall(tmp)
    manifest_path: Path | None = None
    for name in BUNDLE_JSON_NAMES:
        candidate = tmp / name
        if candidate.is_file():
            manifest_path = candidate
            break
    if manifest_path is None:
        for path in sorted(tmp.rglob("*.json")):
            if path.name.endswith(".platform-bundle.json") or path.name.endswith(".bundle.json"):
                manifest_path = path
                break
    if manifest_path is None:
        raise ValueError("ZIP does not contain a bundle JSON manifest (*.platform-bundle.json or *.bundle.json)")
    bundle = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(bundle, dict):
        raise ValueError("Bundle manifest root must be a JSON object")
    bundle_dir = manifest_path.parent
    return bundle, bundle_dir, manifest_path.name


def resolve_document_path(bundle_dir: Path, content_path: str) -> Path | None:
    rel = content_path.lstrip("/").replace("\\", "/")
    candidate = bundle_dir / rel
    if candidate.is_file():
        return candidate
    if rel.startswith(f"{DOCUMENTS_DIR}/"):
        return candidate if candidate.is_file() else None
    alt = bundle_dir / DOCUMENTS_DIR / Path(rel).name
    return alt if alt.is_file() else None
