"""
KnowledgeBaseStore 单元测试：CRUD、向量检索、统一表路径。

运行（在 backend 目录）：
  pytest tests/test_knowledge_base_store.py -v
  pytest tests/test_knowledge_base_store.py -v -k "test_crud"  # 仅 CRUD

说明：
- 默认 store 使用临时 DB，未跑 Alembic，故 _use_unified_chunks_table() 为 False。
- store_with_unified 会在同一临时 DB 上创建 embedding_chunks 表，用于测试统一表路径。
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from core.knowledge.knowledge_base_store import (
    UNIFIED_CHUNKS_TABLE,
    KnowledgeBaseConfig,
    KnowledgeBaseStore,
)
from core.knowledge.status import KnowledgeBaseStatus, DocumentStatus
from core.utils.user_context import ResourceNotFoundError


def _create_embedding_chunks_table(store: KnowledgeBaseStore) -> None:
    """在 store 的 DB 中创建 embedding_chunks 表（与 Alembic a1b2c3d4e5f6 一致），便于测试统一表路径。"""
    with store._connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS embedding_chunks (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                knowledge_base_id VARCHAR NOT NULL,
                document_id VARCHAR NOT NULL,
                chunk_id VARCHAR NOT NULL,
                content TEXT NOT NULL
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_embedding_chunks_kb_id ON embedding_chunks (knowledge_base_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_embedding_chunks_doc_id ON embedding_chunks (document_id)"
        )
        conn.commit()


@pytest.fixture
def db_path() -> Path:
    _fd, path = tempfile.mkstemp(suffix=".db")
    Path(path).unlink(missing_ok=True)
    return Path(path)


@pytest.fixture
def store(db_path: Path) -> KnowledgeBaseStore:
    return KnowledgeBaseStore(KnowledgeBaseConfig(db_path=db_path))


@pytest.fixture
def store_with_unified(db_path: Path) -> KnowledgeBaseStore:
    """Store 使用同一临时 DB，并已创建 embedding_chunks 表，_use_unified_chunks_table() 为 True。"""
    s = KnowledgeBaseStore(KnowledgeBaseConfig(db_path=db_path))
    _create_embedding_chunks_table(s)
    return s


class TestKnowledgeBaseCRUD:
    """知识库 CRUD 测试（不依赖 sqlite-vec）。"""

    def test_create_and_get_knowledge_base(self, store: KnowledgeBaseStore) -> None:
        kb_id = store.create_knowledge_base(
            name="Test KB",
            description="Desc",
            embedding_model_id="embedding:test",
            chunk_size=512,
            chunk_overlap=40,
            chunk_size_overrides_json='{"pdf":256,"md":512}',
        )
        assert kb_id.startswith("kb_")
        kb = store.get_knowledge_base(kb_id)
        assert kb is not None
        assert kb["name"] == "Test KB"
        assert kb["description"] == "Desc"
        assert kb["embedding_model_id"] == "embedding:test"
        assert kb["status"] == KnowledgeBaseStatus.EMPTY
        assert kb["chunk_size"] == 512
        assert kb["chunk_overlap"] == 40
        assert kb["chunk_size_overrides_json"] == '{"pdf":256,"md":512}'

    def test_list_knowledge_bases(self, store: KnowledgeBaseStore) -> None:
        assert store.list_knowledge_bases() == []
        store.create_knowledge_base("A", None, "emb:1")
        store.create_knowledge_base("B", "B desc", "emb:1")
        lst = store.list_knowledge_bases()
        assert len(lst) == 2
        names = {x["name"] for x in lst}
        assert names == {"A", "B"}

    def test_update_and_delete_knowledge_base(self, store: KnowledgeBaseStore) -> None:
        kb_id = store.create_knowledge_base("Original", None, "emb:1")
        store.update_knowledge_base(
            kb_id,
            name="Updated",
            description="New desc",
            chunk_size=640,
            chunk_overlap=32,
            chunk_size_overrides_json='{"pdf":320}',
        )
        kb = store.get_knowledge_base(kb_id)
        assert kb["name"] == "Updated"
        assert kb["description"] == "New desc"
        assert kb["chunk_size"] == 640
        assert kb["chunk_overlap"] == 32
        assert kb["chunk_size_overrides_json"] == '{"pdf":320}'
        assert store.delete_knowledge_base(kb_id) is True
        with pytest.raises(ResourceNotFoundError):
            store.get_knowledge_base(kb_id)

    def test_create_and_list_documents(self, store: KnowledgeBaseStore) -> None:
        kb_id = store.create_knowledge_base("KB", None, "emb:1")
        doc_id = store.create_document(
            knowledge_base_id=kb_id,
            source="file.pdf",
            doc_type="pdf",
        )
        assert doc_id.startswith("doc_")
        docs = store.list_documents(kb_id)
        assert len(docs) == 1
        assert docs[0]["source"] == "file.pdf"
        assert docs[0]["doc_type"] == "pdf"
        assert docs[0]["status"] == DocumentStatus.UPLOADED

    def test_get_and_delete_document(self, store: KnowledgeBaseStore) -> None:
        kb_id = store.create_knowledge_base("KB", None, "emb:1")
        doc_id = store.create_document(kb_id, "x.txt", "text")
        doc = store.get_document(doc_id)
        assert doc is not None
        assert doc["knowledge_base_id"] == kb_id
        assert store.delete_document(doc_id) is True
        assert store.get_document(doc_id) is None


class TestKnowledgeBaseUnifiedChunks:
    """统一表 embedding_chunks 相关测试。"""

    def test_use_unified_table_detection_without_table(self, store: KnowledgeBaseStore) -> None:
        """临时 DB 未创建 embedding_chunks 时，应为 False。"""
        assert store._use_unified_chunks_table() is False

    def test_use_unified_table_detection_with_table(self, store_with_unified: KnowledgeBaseStore) -> None:
        """创建 embedding_chunks 表后，应为 True（与 Alembic 迁移后行为一致）。"""
        assert store_with_unified._use_unified_chunks_table() is True

    def test_list_chunks_empty(self, store: KnowledgeBaseStore) -> None:
        kb_id = store.create_knowledge_base("KB", None, "emb:1")
        chunks = store.list_chunks(knowledge_base_id=kb_id, limit=10)
        assert chunks == []

    def test_list_chunks_empty_unified_path(self, store_with_unified: KnowledgeBaseStore) -> None:
        """统一表路径下无 chunk 时 list_chunks 返回空。"""
        kb_id = store_with_unified.create_knowledge_base("KB", None, "emb:1")
        chunks = store_with_unified.list_chunks(knowledge_base_id=kb_id, limit=10)
        assert chunks == []

    def test_get_chunk_count_empty(self, store: KnowledgeBaseStore) -> None:
        kb_id = store.create_knowledge_base("KB", None, "emb:1")
        assert store.get_chunk_count(knowledge_base_id=kb_id) == 0
        assert store.get_chunk_count(knowledge_base_id=None) >= 0

    def test_get_chunk_count_empty_unified_path(self, store_with_unified: KnowledgeBaseStore) -> None:
        """统一表路径下 get_chunk_count 为 0。"""
        kb_id = store_with_unified.create_knowledge_base("KB", None, "emb:1")
        assert store_with_unified.get_chunk_count(knowledge_base_id=kb_id) == 0

    def test_keyword_search_multi_kb(self, store_with_unified: KnowledgeBaseStore) -> None:
        kb_id = store_with_unified.create_knowledge_base("KB", None, "emb:1")
        doc_id = store_with_unified.create_document(kb_id, "openvino_gpu.md", "md")
        with store_with_unified._connect() as conn:
            conn.execute(
                f"""
                INSERT INTO {UNIFIED_CHUNKS_TABLE}
                (knowledge_base_id, document_id, chunk_id, content)
                VALUES (?, ?, ?, ?)
                """,
                (kb_id, doc_id, "chunk_gpu", "如何配置 OpenVINO 的 GPU 设备：设置 device=GPU。"),
            )
            conn.execute(
                f"""
                INSERT INTO {UNIFIED_CHUNKS_TABLE}
                (knowledge_base_id, document_id, chunk_id, content)
                VALUES (?, ?, ?, ?)
                """,
                (kb_id, doc_id, "chunk_cpu", "OpenVINO CPU 配置指南，适用于 CPU 推理。"),
            )
            conn.commit()
        results = store_with_unified.search_chunks_keyword_multi_kb(
            knowledge_base_ids=[kb_id],
            query_text="如何配置 OpenVINO 的 GPU 设备",
            limit=5,
        )
        assert results
        assert results[0]["chunk_id"] == "chunk_gpu"
        assert results[0]["keyword_score"] >= results[-1]["keyword_score"]

    def test_hybrid_search_fallback_without_vector(self, store_with_unified: KnowledgeBaseStore) -> None:
        kb_id = store_with_unified.create_knowledge_base("KB", None, "emb:1")
        doc_id = store_with_unified.create_document(kb_id, "openvino_gpu.md", "md")
        with store_with_unified._connect() as conn:
            conn.execute(
                f"""
                INSERT INTO {UNIFIED_CHUNKS_TABLE}
                (knowledge_base_id, document_id, chunk_id, content)
                VALUES (?, ?, ?, ?)
                """,
                (kb_id, doc_id, "chunk_gpu", "OpenVINO GPU 配置步骤，设置推理设备为 GPU。"),
            )
            conn.commit()

        results = store_with_unified.hybrid_search_chunks_multi_kb(
            knowledge_base_ids=[kb_id],
            query_text="OpenVINO GPU 配置",
            query_embedding=[0.0] * 16,
            keyword_limit=10,
            vector_limit=10,
            rerank_limit=5,
            min_relevance_score=0.1,
        )
        assert results
        assert results[0]["chunk_id"] == "chunk_gpu"
        assert "relevance_score" in results[0]

    def test_kb_version_and_incremental_hash(self, store_with_unified: KnowledgeBaseStore) -> None:
        kb_id = store_with_unified.create_knowledge_base("KB", None, "emb:1")
        version_id = store_with_unified.create_kb_version(kb_id, "v2")
        versions = store_with_unified.list_kb_versions(kb_id)
        assert versions
        assert any(v["id"] == version_id for v in versions)
        resolved = store_with_unified.resolve_kb_version_id(kb_id=kb_id, version_label="v2")
        assert resolved == version_id

        doc_id = store_with_unified.create_document(kb_id, "a.txt", "txt", content_hash="h1")
        store_with_unified.add_document_version(doc_id, kb_id, version_id, "h1")
        assert store_with_unified.should_reindex_document(doc_id, "h1") is False
        assert store_with_unified.should_reindex_document(doc_id, "h2") is True

    def test_graph_upsert_and_search(self, store_with_unified: KnowledgeBaseStore) -> None:
        kb_id = store_with_unified.create_knowledge_base("KB", None, "emb:1")
        version_id = store_with_unified.create_kb_version(kb_id, "v1")
        inserted = store_with_unified.upsert_graph_triples(
            kb_id=kb_id,
            version_id=version_id,
            source_doc_id="doc_a",
            triples=[
                {"source": "Intel", "relation": "开发", "target": "OpenVINO", "confidence": 0.9},
                {"source": "OpenVINO", "relation": "属于", "target": "AI框架", "confidence": 0.7},
            ],
        )
        assert inserted == 2
        results = store_with_unified.search_graph_relations(
            kb_id=kb_id,
            query_text="Intel 开发了什么",
            limit=5,
        )
        assert results
        assert any(r["target_entity"] == "OpenVINO" for r in results)

    def test_keyword_search_with_version_filter(self, store_with_unified: KnowledgeBaseStore) -> None:
        kb_id = store_with_unified.create_knowledge_base("KB", None, "emb:1")
        doc_id = store_with_unified.create_document(kb_id, "vdoc.md", "md")
        with store_with_unified._connect() as conn:
            try:
                conn.execute(f"ALTER TABLE {UNIFIED_CHUNKS_TABLE} ADD COLUMN version_id TEXT")
            except Exception:
                pass
            conn.execute(
                f"""
                INSERT INTO {UNIFIED_CHUNKS_TABLE}
                (knowledge_base_id, document_id, chunk_id, content, version_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (kb_id, doc_id, "chunk_v1", "OpenVINO GPU 配置 v1", "v1"),
            )
            conn.execute(
                f"""
                INSERT INTO {UNIFIED_CHUNKS_TABLE}
                (knowledge_base_id, document_id, chunk_id, content, version_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (kb_id, doc_id, "chunk_v2", "OpenVINO GPU 配置 v2", "v2"),
            )
            conn.commit()
        v1 = store_with_unified.search_chunks_keyword_multi_kb(
            knowledge_base_ids=[kb_id],
            query_text="OpenVINO GPU 配置",
            limit=10,
            version_id="v1",
        )
        assert v1
        assert all((x.get("version_id") in ("v1", None)) for x in v1)


def _vec_available(store: KnowledgeBaseStore) -> bool:
    return getattr(store, "_vec_available", False)


@pytest.mark.skipif(
    True,  # 仅当 sqlite-vec 可用且统一表存在时可改为 False，或通过 env 控制
    reason="Optional: run with sqlite-vec and unified table to test vector path",
)
class TestKnowledgeBaseVectorSearch:
    """向量检索测试（需 sqlite-vec + 统一表）。"""

    def test_insert_and_search_chunks(self, store: KnowledgeBaseStore) -> None:
        if not _vec_available(store) or not store._use_unified_chunks_table():
            pytest.skip("sqlite-vec or unified table not available")
        kb_id = store.create_knowledge_base("KB", None, "emb:1")
        doc_id = store.create_document(kb_id, "doc1", "txt")
        vec = [0.1] * 256 + [0.9] * 256  # 512-dim placeholder
        store.insert_chunk(kb_id, doc_id, "chunk_1", "hello world", vec)
        results = store.search_chunks(kb_id, vec, limit=5)
        assert len(results) >= 1
        assert results[0]["content"] == "hello world"
        assert results[0]["document_id"] == doc_id
        assert results[0]["chunk_id"] == "chunk_1"


class TestRAGFlowIntegration:
    """RAG 检索流程集成测试（轻量：只测接口与返回结构）。"""

    def test_search_chunks_return_shape(self, store: KnowledgeBaseStore) -> None:
        kb_id = store.create_knowledge_base("KB", None, "emb:1")
        # 无向量时 search_chunks 可能抛或返回 []，取决于是否启用 vec
        try:
            results = store.search_chunks(
                knowledge_base_id=kb_id,
                query_embedding=[0.0] * 512,
                limit=5,
            )
            for r in results:
                assert "content" in r
                assert "distance" in r
                assert "document_id" in r
                assert "chunk_id" in r
                assert "doc_source" in r or "doc_type" in r
        except RuntimeError as e:
            if "sqlite-vec is not available" in str(e) or "Vector search provider" in str(e):
                pytest.skip("Vector search not available")

    def test_search_chunks_multi_kb_return_shape(self, store: KnowledgeBaseStore) -> None:
        kb1 = store.create_knowledge_base("KB1", None, "emb:1")
        try:
            results = store.search_chunks_multi_kb(
                knowledge_base_ids=[kb1],
                query_embedding=[0.0] * 512,
                limit=5,
            )
            for r in results:
                assert "content" in r
                assert "distance" in r
                assert "knowledge_base_id" in r
        except RuntimeError as e:
            if "sqlite-vec is not available" in str(e):
                pytest.skip("Vector search not available")
