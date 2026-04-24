from __future__ import annotations

from core.knowledge.vector_index_snapshot import RedisVectorIndexSnapshot


class _FakeRedis:
    def __init__(self) -> None:
        self.data: dict[str, str] = {}

    def get(self, key: str):
        return self.data.get(key)

    def set(self, key: str, value: str):
        self.data[key] = value
        return True

    def delete(self, key: str):
        self.data.pop(key, None)
        return 1


def test_snapshot_save_load_delete_cycle() -> None:
    store = RedisVectorIndexSnapshot()
    store._enabled = True
    store._redis_url = "redis://fake"
    store._client = _FakeRedis()
    store._init_tried = True

    store.save_embedding("kb_a", 1, [0.1, 0.2])
    store.save_embedding("kb_a", 2, [0.3, 0.4])
    loaded = store.load_embeddings("kb_a")
    assert loaded[1] == [0.1, 0.2]
    assert loaded[2] == [0.3, 0.4]

    store.delete_embeddings("kb_a", [1])
    loaded2 = store.load_embeddings("kb_a")
    assert 1 not in loaded2
    assert loaded2[2] == [0.3, 0.4]

    store.clear_kb("kb_a")
    assert store.load_embeddings("kb_a") == {}

