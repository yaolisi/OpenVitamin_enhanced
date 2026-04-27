"""
V2.9 Runtime Stabilization Layer - Inference queue.

Per-model concurrency limit via asyncio.Semaphore.
"""
import asyncio
import threading
import time
from dataclasses import dataclass
from typing import Dict, TypeVar, AsyncIterator, Optional, Literal
from log import logger

from core.runtime.config import get_max_concurrency
from core.system.runtime_settings import (
    get_inference_queue_slo_enabled,
    get_inference_queue_slo_high_ms,
    get_inference_queue_slo_medium_ms,
    get_inference_queue_slo_low_ms,
    get_inference_queue_preemption_enabled,
    get_inference_queue_preemption_max_per_high_request,
    get_inference_queue_preemption_max_per_task,
    get_inference_queue_preemption_cooldown_ms,
)

T = TypeVar("T")
QueuePriority = Literal["high", "medium", "low"]


@dataclass
class _RunningTaskInfo:
    task: asyncio.Task[object]
    priority: QueuePriority
    started_at: float
    preemption_key: str


class InferenceQueue:
    """
    Limits concurrent inference for one model.
    Uses a semaphore; run(coro) runs the coroutine under the semaphore.
    """

    def __init__(self, model_id: str, max_concurrency: int):
        self.model_id = model_id
        self._max_concurrency = max(1, max_concurrency)
        self._available_slots = self._max_concurrency
        self._in_flight = 0
        self._waiting = 0
        self._waiting_high = 0
        self._waiting_medium = 0
        self._waiting_low = 0
        self._waiting_since: Dict[QueuePriority, list[float]] = {"high": [], "medium": [], "low": []}
        self._running_tasks: Dict[int, _RunningTaskInfo] = {}
        self._preemption_counts: Dict[str, int] = {}
        self._preemption_last_ts: Dict[str, float] = {}
        self._preemptions_total = 0
        self._preemption_skipped_limit_total = 0
        self._preemption_skipped_cooldown_total = 0
        self._lock = asyncio.Lock()
        self._cond = asyncio.Condition(self._lock)

    @property
    def preemptions_total(self) -> int:
        return self._preemptions_total

    @property
    def preemption_skipped_limit_total(self) -> int:
        return self._preemption_skipped_limit_total

    @property
    def preemption_skipped_cooldown_total(self) -> int:
        return self._preemption_skipped_cooldown_total

    @property
    def max_concurrency(self) -> int:
        return self._max_concurrency

    def try_update_max_concurrency(self, new_max: int) -> bool:
        """
        Best-effort update of max_concurrency for this queue.

        Safety:
        - Only updates when idle (no waiting + no in-flight), so we don't change
          semaphore behavior mid-run.
        - Returns False if queue is busy or new_max is invalid/same.
        """
        new_max = max(1, int(new_max))
        if new_max == self._max_concurrency:
            return False
        # Best-effort check (not atomic); good enough to avoid surprising changes.
        if self._in_flight != 0 or self._waiting != 0:
            return False
        self._max_concurrency = new_max
        self._available_slots = new_max
        return True

    async def _inc_usage(self) -> None:
        async with self._lock:
            self._in_flight += 1
            self._notify_queue_size()

    async def _dec_usage(self) -> None:
        async with self._lock:
            self._in_flight = max(0, self._in_flight - 1)
            self._notify_queue_size()

    def _notify_queue_size(self) -> None:
        try:
            from core.runtime.manager.runtime_metrics import get_runtime_metrics
            get_runtime_metrics().set_queue_size(self.model_id, self._waiting + self._in_flight)
        except Exception:
            pass

    @staticmethod
    def _normalize_priority(priority: str | None) -> QueuePriority:
        val = (priority or "medium").strip().lower()
        if val in {"high", "medium", "low"}:
            return val  # type: ignore[return-value]
        return "medium"

    async def _acquire_slot(self, priority: QueuePriority) -> None:
        async with self._cond:
            enqueued_at = time.monotonic()
            self._waiting += 1
            self._waiting_since[priority].append(enqueued_at)
            if priority == "high":
                self._waiting_high += 1
            elif priority == "low":
                self._waiting_low += 1
            else:
                self._waiting_medium += 1
            self._notify_queue_size()
            try:
                if priority == "high":
                    self._preempt_for_high_locked()
                await self._cond.wait_for(lambda: self._can_run(priority))
                self._available_slots -= 1
            finally:
                self._waiting = max(0, self._waiting - 1)
                if self._waiting_since[priority]:
                    self._waiting_since[priority].pop(0)
                if priority == "high":
                    self._waiting_high = max(0, self._waiting_high - 1)
                elif priority == "low":
                    self._waiting_low = max(0, self._waiting_low - 1)
                else:
                    self._waiting_medium = max(0, self._waiting_medium - 1)
                self._notify_queue_size()

    async def _release_slot(self) -> None:
        async with self._cond:
            self._available_slots = min(self._max_concurrency, self._available_slots + 1)
            self._cond.notify_all()

    def _can_run(self, priority: QueuePriority) -> bool:
        if self._available_slots <= 0:
            return False
        if self._is_slo_breached(priority):
            return True
        if priority == "high":
            return True
        if priority == "medium":
            return self._waiting_high == 0
        return self._waiting_high == 0 and self._waiting_medium == 0

    def _is_slo_breached(self, priority: QueuePriority) -> bool:
        if not get_inference_queue_slo_enabled():
            return False
        queue = self._waiting_since.get(priority) or []
        if not queue:
            return False
        oldest_wait_ms = (time.monotonic() - queue[0]) * 1000.0
        if priority == "high":
            slo_ms = get_inference_queue_slo_high_ms()
        elif priority == "medium":
            slo_ms = get_inference_queue_slo_medium_ms()
        else:
            slo_ms = get_inference_queue_slo_low_ms()
        return oldest_wait_ms >= float(slo_ms)

    def _preempt_for_high_locked(self) -> None:
        if not get_inference_queue_preemption_enabled():
            return
        if self._available_slots > 0:
            return
        now = time.monotonic()
        cooldown_seconds = max(0.0, float(get_inference_queue_preemption_cooldown_ms()) / 1000.0)
        max_per_task = max(1, int(get_inference_queue_preemption_max_per_task()))
        max_victims = max(1, int(get_inference_queue_preemption_max_per_high_request()))
        base_candidates = [
            info for info in self._running_tasks.values()
            if info.priority in {"low", "medium"}
        ]
        allowed_candidates = []
        skipped_limit = 0
        skipped_cooldown = 0
        for info in base_candidates:
            if self._preemption_counts.get(info.preemption_key, 0) >= max_per_task:
                skipped_limit += 1
                continue
            if (
                cooldown_seconds > 0
                and now - self._preemption_last_ts.get(info.preemption_key, -10**9) < cooldown_seconds
            ):
                skipped_cooldown += 1
                continue
            allowed_candidates.append(info)
        self._preemption_skipped_limit_total += skipped_limit
        self._preemption_skipped_cooldown_total += skipped_cooldown
        victims = sorted(
            allowed_candidates,
            key=lambda info: (
                0 if info.priority == "low" else 1,
                time.monotonic() - info.started_at,
            ),
        )
        selected = victims[:max_victims]
        for victim in selected:
            victim.task.cancel("preempted_by_high_priority_request")
            self._preemption_counts[victim.preemption_key] = self._preemption_counts.get(victim.preemption_key, 0) + 1
            self._preemption_last_ts[victim.preemption_key] = now
            self._preemptions_total += 1
            logger.warning(
                "[RuntimeStabilization] Preempted task model_id=%s victim_priority=%s",
                self.model_id,
                victim.priority,
            )

    def current_usage(self) -> int:
        """Best-effort: in-flight count (waiting not tracked atomically)."""
        return self._in_flight

    async def run(self, coro, priority: str = "medium", preemption_key: str | None = None):
        """
        Run coroutine with concurrency limit.
        Returns the result of the coroutine.
        """
        normalized_priority = self._normalize_priority(priority)
        acquired = False
        current_task = asyncio.current_task()
        normalized_preemption_key = (preemption_key or "").strip() or f"task:{id(current_task)}"
        try:
            await self._acquire_slot(normalized_priority)
            acquired = True
            if current_task is not None:
                async with self._lock:
                    self._running_tasks[id(current_task)] = _RunningTaskInfo(
                        task=current_task,
                        priority=normalized_priority,
                        started_at=time.monotonic(),
                        preemption_key=normalized_preemption_key,
                    )
            await self._inc_usage()
            try:
                return await coro
            finally:
                await self._dec_usage()
        finally:
            if current_task is not None:
                async with self._lock:
                    self._running_tasks.pop(id(current_task), None)
            if acquired:
                await self._release_slot()

    async def run_stream(
        self,
        agen: AsyncIterator[T],
        priority: str = "medium",
        preemption_key: str | None = None,
    ) -> AsyncIterator[T]:
        """
        Run async generator under the semaphore.
        Semaphore is held for the entire consumption of the stream.
        """
        normalized_priority = self._normalize_priority(priority)
        acquired = False
        current_task = asyncio.current_task()
        normalized_preemption_key = (preemption_key or "").strip() or f"task:{id(current_task)}"
        try:
            await self._acquire_slot(normalized_priority)
            acquired = True
            if current_task is not None:
                async with self._lock:
                    self._running_tasks[id(current_task)] = _RunningTaskInfo(
                        task=current_task,
                        priority=normalized_priority,
                        started_at=time.monotonic(),
                        preemption_key=normalized_preemption_key,
                    )
            await self._inc_usage()
            try:
                async for item in agen:
                    yield item
            finally:
                await self._dec_usage()
        finally:
            if current_task is not None:
                async with self._lock:
                    self._running_tasks.pop(id(current_task), None)
            if acquired:
                await self._release_slot()


class InferenceQueueManager:
    """
    Per-model inference queues.
    Creates one InferenceQueue per model_id with max_concurrency from config (by runtime_type).
    """

    def __init__(self):
        self._queues: Dict[str, InferenceQueue] = {}
        self._lock = threading.Lock()

    def get_queue(self, model_id: str, runtime_type: str) -> InferenceQueue:
        """Get or create queue for model_id; concurrency from model metadata > settings > MODEL_RUNTIME_CONFIG."""
        with self._lock:
            max_concurrency = get_max_concurrency(runtime_type, model_id=model_id)
            if model_id in self._queues:
                q = self._queues[model_id]
                if q.try_update_max_concurrency(max_concurrency):
                    logger.info(
                        "[RuntimeStabilization] Updated queue max_concurrency model_id=%s runtime=%s max_concurrency=%s",
                        model_id,
                        runtime_type,
                        max_concurrency,
                    )
                return q
            q = InferenceQueue(model_id=model_id, max_concurrency=max_concurrency)
            self._queues[model_id] = q
            return q

    def list_queues(self) -> Dict[str, InferenceQueue]:
        with self._lock:
            return dict(self._queues)


# Singleton (thread-safe for first access)
_queue_manager: Optional[InferenceQueueManager] = None
_queue_manager_lock = threading.Lock()


def get_inference_queue_manager() -> InferenceQueueManager:
    global _queue_manager
    with _queue_manager_lock:
        if _queue_manager is None:
            _queue_manager = InferenceQueueManager()
        return _queue_manager
