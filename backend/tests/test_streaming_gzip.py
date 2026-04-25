"""streaming_gzip：分块 GZip 与 chat 流式帧格式（轻量单测）。"""

from __future__ import annotations

import gzip
import json
from collections.abc import AsyncIterator

import pytest

from api.streaming_gzip import gzip_async_str_iterator


@pytest.mark.asyncio
async def test_gzip_async_str_iterator_round_trip() -> None:
    parts = ['data: {"k":1}\n\n', "data: [DONE]\n\n"]

    async def src() -> AsyncIterator[str]:
        for p in parts:
            yield p

    raw = b"".join([c async for c in gzip_async_str_iterator(src())])
    out = gzip.decompress(raw).decode("utf-8")
    assert out == "".join(parts)


def test_stream_delta_event_shapes() -> None:
    from api.chat import _stream_delta_event, _resolve_stream_format
    from core.types import ChatCompletionRequest, Message

    assert _resolve_stream_format(
        ChatCompletionRequest(model="m", messages=[Message(role="user", content="h")], stream=True)
    ) == "openai"
    s = _stream_delta_event(
        stream_format="openai",
        completion_id="c1",
        created_time=1,
        model_id="m",
        content="ab",
        cidx=0,
        char_off=0,
    )
    assert s.startswith("data: ")
    payload = s.removeprefix("data: ").split("\n\n", 1)[0].strip()
    d = json.loads(payload)
    assert d["object"] == "chat.completion.chunk"
    assert d["openvitamin"]["cidx"] == 0
    assert d["openvitamin"]["char_len"] == 2
    j = _stream_delta_event(
        stream_format="jsonl", completion_id="c1", created_time=1, model_id="m", content="x", cidx=1, char_off=2
    )
    p2 = j.removeprefix("data: ").split("\n\n", 1)[0].strip()
    d2 = json.loads(p2)
    assert d2["object"] == "openvitamin.stream.jsonl"
    assert d2["i"] == 1
    assert d2["c"] == "x"
