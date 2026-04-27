"""
连续动态批处理器（仅用于非流式 chat）。

设计目标：
1) 将短时间窗口内同模型请求聚合处理，降低排队抖动。
2) 将 preprocess / infer / postprocess 分阶段，便于后续扩展流水线观测。
3) 对 runtime 不要求强制实现 batch 接口；若支持 chat_batch 则优先走原生批推理。
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Optional

from log import logger
from core.runtimes.factory import get_runtime_factory
from core.runtime.queue.inference_queue import get_inference_queue_manager
from core.runtime.manager.runtime_metrics import get_runtime_metrics
from core.system.runtime_settings import get_continuous_batch_max_size, get_continuous_batch_wait_ms


@dataclass
class _BatchItem:
    req: Any
    future: asyncio.Future[str]
    enqueued_at: float


class _ModelBatchWorker:
    def __init__(self, model_id: str, runtime_type: str) -> None:
        self.model_id = model_id
        self.runtime_type = runtime_type
        self._queue: asyncio.Queue[_BatchItem] = asyncio.Queue()
        self._stopped = False
        self._task: Optional[asyncio.Task[None]] = None

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop())

    async def submit(self, req: Any) -> str:
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[str] = loop.create_future()
        await self._queue.put(_BatchItem(req=req, future=fut, enqueued_at=time.time()))
        return await fut

    async def _loop(self) -> None:
        while not self._stopped:
            first = await self._queue.get()
            batch = [first]
            max_batch = get_continuous_batch_max_size()
            wait_ms = get_continuous_batch_wait_ms()
            deadline = time.monotonic() + (wait_ms / 1000.0)

            while len(batch) < max_batch:
                timeout = deadline - time.monotonic()
                if timeout <= 0:
                    break
                try:
                    nxt = await asyncio.wait_for(self._queue.get(), timeout=timeout)
                    batch.append(nxt)
                except asyncio.TimeoutError:
                    break

            await self._execute_batch(batch)

    async def _execute_batch(self, batch: list[_BatchItem]) -> None:
        if not batch:
            return

        queue = get_inference_queue_manager().get_queue(self.model_id, self.runtime_type)
        runtime_factory = get_runtime_factory()
        from core.runtime.manager.model_instance_manager import get_model_instance_manager
        from core.models.registry import get_model_registry

        descriptor = get_model_registry().get_model(self.model_id)
        if descriptor is None:
            error = RuntimeError(f"Model not found for batching: {self.model_id}")
            for item in batch:
                if not item.future.done():
                    item.future.set_exception(error)
            return

        runtime = await get_model_instance_manager().get_instance(self.model_id)
        metrics = get_runtime_metrics()

        # preprocess 阶段（当前保持轻量，后续可插入输入裁剪/模板编译等）
        requests = [item.req for item in batch]

        async def _infer_batch() -> list[str]:
            if hasattr(runtime, "chat_batch") and callable(getattr(runtime, "chat_batch")):
                results = await runtime.chat_batch(descriptor, requests)  # type: ignore[attr-defined]
                return [str(x or "") for x in results]
            return await asyncio.gather(*(runtime.chat(descriptor, r) for r in requests))

        try:
            use_native_batch = hasattr(runtime, "chat_batch") and callable(getattr(runtime, "chat_batch"))
            async with runtime_factory.model_usage(self.model_id):
                texts = await queue.run(_infer_batch())
            wait_ms = max(0.0, (time.time() - min(item.enqueued_at for item in batch)) * 1000.0)
            metrics.record_batch_group(
                self.model_id,
                batch_size=len(batch),
                wait_ms=wait_ms,
                native_batch=use_native_batch,
            )
            if len(texts) != len(batch):
                raise RuntimeError("Batched result size mismatch")
            # postprocess 阶段
            for item, text in zip(batch, texts):
                if not item.future.done():
                    item.future.set_result(str(text or ""))
        except Exception as e:
            logger.error(
                "[ContinuousBatching] execute batch failed model=%s size=%s err=%s",
                self.model_id,
                len(batch),
                str(e)[:300],
            )
            for item in batch:
                if not item.future.done():
                    item.future.set_exception(e)


class ContinuousBatcher:
    def __init__(self) -> None:
        self._workers: dict[str, _ModelBatchWorker] = {}
        self._lock = asyncio.Lock()

    async def submit(self, model_id: str, runtime_type: str, req: Any) -> str:
        async with self._lock:
            worker = self._workers.get(model_id)
            if worker is None:
                worker = _ModelBatchWorker(model_id=model_id, runtime_type=runtime_type)
                worker.start()
                self._workers[model_id] = worker
        return await worker.submit(req)


_batcher: Optional[ContinuousBatcher] = None


def get_continuous_batcher() -> ContinuousBatcher:
    global _batcher
    if _batcher is None:
        _batcher = ContinuousBatcher()
    return _batcher
