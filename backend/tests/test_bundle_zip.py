"""Bundle ZIP 打包/解包。"""
from __future__ import annotations

from core.demos.bundle_zip import pack_bundle_zip, pick_manifest_name, unpack_bundle_zip


def test_zip_roundtrip_with_documents() -> None:
    bundle = {
        "schema_version": 1,
        "bundle_type": "platform",
        "bundle_id": "test-export",
        "name": "Test",
        "knowledge_bases": [
            {
                "bundle_key": "kb_demo",
                "name": "KB",
                "documents": [{"filename": "a.md", "content_path": "documents/a.md"}],
            }
        ],
    }
    sidecar = {"documents/a.md": b"# hello\n"}
    raw, _ = pack_bundle_zip(bundle, kind="platform", sidecar_files=sidecar)
    loaded, bundle_dir, _ = unpack_bundle_zip(raw)
    assert loaded["bundle_id"] == "test-export"
    doc_path = bundle_dir / "documents" / "a.md"
    assert doc_path.is_file()
    assert doc_path.read_text(encoding="utf-8") == "# hello\n"


def test_pick_manifest_name() -> None:
    assert pick_manifest_name({"bundle_id": "my-pack"}, "platform").endswith(".platform-bundle.json")
    assert pick_manifest_name({"bundle_id": "wf"}, "workflow").endswith(".bundle.json")
