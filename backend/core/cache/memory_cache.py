from __future__ import annotations

import json
import threading
import time
from collections import OrderedDict
from typing import Any, Optional

from config.settings import settings


class MemoryCacheClient:
    """Thread-safe in-memory JSON cache with TTL and LRU eviction."""

    def __init__(self) -> None:
        self._enabled = bool(getattr(settings, "inference_cache_memory_enabled", True))
        self._max_entries = max(16, int(getattr(settings, "inference_cache_memory_max_entries", 2048) or 2048))
        self._lock = threading.Lock()
        self._store: OrderedDict[str, tuple[float, str]] = OrderedDict()

    def get_json(self, key: str) -> Optional[dict[str, Any]]:
        if not self._enabled:
            return None
        now = time.time()
        with self._lock:
            item = self._store.get(key)
            if item is None:
                return None
            expires_at, raw = item
            if expires_at <= now:
                self._store.pop(key, None)
                return None
            self._store.move_to_end(key)
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return None
        return None

    def set_json(self, key: str, payload: dict[str, Any], ttl_seconds: int) -> None:
        if not self._enabled:
            return
        ttl = max(1, int(ttl_seconds))
        expires_at = time.time() + ttl
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        with self._lock:
            self._store[key] = (expires_at, raw)
            self._store.move_to_end(key)
            while len(self._store) > self._max_entries:
                self._store.popitem(last=False)

    def clear_prefix(self, prefix: str) -> int:
        if not self._enabled:
            return 0
        removed = 0
        with self._lock:
            keys = [k for k in self._store.keys() if k.startswith(prefix)]
            for key in keys:
                self._store.pop(key, None)
                removed += 1
        return removed


_memory_cache_client: Optional[MemoryCacheClient] = None
_memory_cache_lock = threading.Lock()


def get_memory_cache_client() -> MemoryCacheClient:
    global _memory_cache_client
    with _memory_cache_lock:
        if _memory_cache_client is None:
            _memory_cache_client = MemoryCacheClient()
        return _memory_cache_client

