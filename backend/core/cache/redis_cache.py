from __future__ import annotations

import json
import threading
from typing import Any, Optional

from config.settings import settings
from log import logger


class RedisCacheClient:
    """Lightweight async Redis JSON cache wrapper."""

    def __init__(self) -> None:
        self._enabled = bool(getattr(settings, "inference_cache_enabled", False))
        self._redis_url = str(getattr(settings, "inference_cache_redis_url", "") or "").strip()
        self._client: Any = None
        self._client_init_attempted = False
        self._lock = threading.Lock()

    def _get_client(self) -> Any:
        if not self._enabled or not self._redis_url:
            return None
        if self._client is not None:
            return self._client

        with self._lock:
            if self._client is not None:
                return self._client
            if self._client_init_attempted:
                return None
            self._client_init_attempted = True
            try:
                from redis.asyncio import Redis
            except Exception as exc:
                logger.warning("[RedisCache] redis package unavailable, cache disabled: %s", exc)
                return None
            try:
                self._client = Redis.from_url(self._redis_url, decode_responses=True)
                return self._client
            except Exception as exc:
                logger.warning("[RedisCache] redis init failed, cache disabled: %s", exc)
                self._client = None
                return None

    async def get_json(self, key: str) -> Optional[dict[str, Any]]:
        client = self._get_client()
        if client is None:
            return None
        try:
            raw = await client.get(key)
            if not raw:
                return None
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
            return None
        except Exception as exc:
            logger.debug("[RedisCache] get failed key=%s err=%s", key, exc)
            return None

    async def set_json(self, key: str, payload: dict[str, Any], ttl_seconds: int) -> None:
        client = self._get_client()
        if client is None:
            return
        ttl = max(1, int(ttl_seconds))
        try:
            await client.setex(key, ttl, json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        except Exception as exc:
            logger.debug("[RedisCache] set failed key=%s err=%s", key, exc)

    async def clear_prefix(self, prefix: str, batch_size: int = 200) -> int:
        client = self._get_client()
        if client is None:
            return 0
        deleted = 0
        pattern = f"{prefix}*"
        try:
            keys: list[str] = []
            async for key in client.scan_iter(match=pattern, count=max(10, int(batch_size))):
                keys.append(key)
                if len(keys) >= batch_size:
                    deleted += int(await client.delete(*keys) or 0)
                    keys = []
            if keys:
                deleted += int(await client.delete(*keys) or 0)
        except Exception as exc:
            logger.debug("[RedisCache] clear_prefix failed prefix=%s err=%s", prefix, exc)
        return deleted

    async def incr_with_expire(self, key: str, ttl_seconds: int) -> Optional[int]:
        """
        Atomically increment key and ensure TTL is set on first hit.
        Returns current count, or None when unavailable/failure.
        """
        client = self._get_client()
        if client is None:
            return None
        ttl = max(1, int(ttl_seconds))
        try:
            count = await client.incr(key)
            if int(count) == 1:
                await client.expire(key, ttl)
            return int(count)
        except Exception as exc:
            logger.debug("[RedisCache] incr_with_expire failed key=%s err=%s", key, exc)
            return None

    async def ttl(self, key: str) -> Optional[int]:
        client = self._get_client()
        if client is None:
            return None
        try:
            value = int(await client.ttl(key))
            return value
        except Exception as exc:
            logger.debug("[RedisCache] ttl failed key=%s err=%s", key, exc)
            return None

    async def delete(self, key: str) -> bool:
        client = self._get_client()
        if client is None:
            return False
        try:
            deleted = int(await client.delete(key) or 0)
            return deleted > 0
        except Exception as exc:
            logger.debug("[RedisCache] delete failed key=%s err=%s", key, exc)
            return False


_redis_cache_client: Optional[RedisCacheClient] = None
_redis_cache_lock = threading.Lock()


def get_redis_cache_client() -> RedisCacheClient:
    global _redis_cache_client
    with _redis_cache_lock:
        if _redis_cache_client is None:
            _redis_cache_client = RedisCacheClient()
        return _redis_cache_client
