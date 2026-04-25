"""
流式聊天响应：GZip 压缩器（GZip 中间件对 text/event-stream 不压缩，故显式在路由层做）。
"""
from __future__ import annotations

import zlib
from typing import AsyncIterator


async def gzip_async_str_iterator(
    source: AsyncIterator[str],
) -> AsyncIterator[bytes]:
    comp = zlib.compressobj(9, zlib.DEFLATED, 16 + zlib.MAX_WBITS)
    async for text in source:
        data = text.encode("utf-8")
        out = comp.compress(data)
        if out:
            yield out
    final = comp.flush()
    if final:
        yield final
