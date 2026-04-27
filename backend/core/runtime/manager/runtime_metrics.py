"""
V2.9 Runtime Stabilization Layer - Runtime metrics.

Thread-safe aggregation: requests, latency, queue_size, tokens_generated.
"""
import threading
import time
from collections import deque
from typing import Dict, Any, Optional, Literal
from dataclasses import dataclass, field

PriorityLabel = Literal["high", "medium", "low"]


def _normalize_priority(priority: str | None) -> PriorityLabel:
    val = (priority or "medium").strip().lower()
    if val in {"high", "medium", "low"}:
        return val  # type: ignore[return-value]
    return "medium"


def _default_priority_bucket() -> dict[str, Any]:
    return {
        "requests": 0,
        "requests_failed": 0,
        "total_latency_ms": 0.0,
        "latencies_ms": deque(maxlen=512),
        "slo_target_ms": 0,
        "slo_met_count": 0,
    }


def _compute_percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    idx = int(round((len(sorted_values) - 1) * percentile))
    idx = max(0, min(len(sorted_values) - 1, idx))
    return float(sorted_values[idx])

@dataclass
class ModelMetrics:
    """Per-model metrics snapshot."""
    model_id: str
    requests: int = 0
    requests_failed: int = 0
    total_latency_ms: float = 0.0
    tokens_generated: int = 0
    queue_size: int = 0  # current waiting + in-flight (best-effort)
    by_priority: Dict[str, Dict[str, Any]] = field(
        default_factory=lambda: {
            "high": _default_priority_bucket(),
            "medium": _default_priority_bucket(),
            "low": _default_priority_bucket(),
        }
    )

    @property
    def avg_latency_ms(self) -> float:
        if self.requests <= 0:
            return 0.0
        return self.total_latency_ms / self.requests

    def to_dict(self) -> Dict[str, Any]:
        by_priority: Dict[str, Dict[str, Any]] = {}
        for p, bucket in self.by_priority.items():
            requests = int(bucket["requests"])
            slo_target = int(bucket["slo_target_ms"] or 0)
            slo_met = int(bucket["slo_met_count"] or 0)
            p95 = _compute_percentile(list(bucket["latencies_ms"]), 0.95)
            by_priority[p] = {
                "requests": requests,
                "requests_failed": int(bucket["requests_failed"]),
                "avg_latency_ms": round((float(bucket["total_latency_ms"]) / requests), 2) if requests > 0 else 0.0,
                "p95_latency_ms": round(p95, 2),
                "slo_target_ms": slo_target,
                "slo_met_count": slo_met,
                "slo_met_rate": round((slo_met / requests), 4) if requests > 0 else 0.0,
            }
        return {
            "model_id": self.model_id,
            "requests": self.requests,
            "requests_failed": self.requests_failed,
            "total_latency_ms": round(self.total_latency_ms, 2),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "tokens_generated": self.tokens_generated,
            "queue_size": self.queue_size,
            "by_priority": by_priority,
        }


class RuntimeMetrics:
    """
    Thread-safe runtime metrics.
    Records requests, latency, tokens; supports optional queue_size updates.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._by_model: Dict[str, ModelMetrics] = {}
        self._queue_sizes: Dict[str, int] = {}  # model_id -> current queue size (set by queue)

    def record_request(self, model_id: str, priority: str = "medium") -> None:
        """Increment request count for model."""
        if not model_id:
            return
        normalized_priority = _normalize_priority(priority)
        with self._lock:
            m = self._by_model.setdefault(model_id, ModelMetrics(model_id=model_id))
            m.requests += 1
            m.by_priority[normalized_priority]["requests"] += 1
            m.queue_size = self._queue_sizes.get(model_id, 0)

    def record_request_failed(self, model_id: str, priority: str = "medium") -> None:
        """Increment failed request count for model."""
        if not model_id:
            return
        normalized_priority = _normalize_priority(priority)
        with self._lock:
            m = self._by_model.setdefault(model_id, ModelMetrics(model_id=model_id))
            m.requests_failed += 1
            m.by_priority[normalized_priority]["requests_failed"] += 1
            m.queue_size = self._queue_sizes.get(model_id, 0)

    def record_latency(
        self,
        model_id: str,
        latency_ms: float,
        priority: str = "medium",
        slo_target_ms: int = 0,
    ) -> None:
        """Record inference latency for model."""
        if not model_id or latency_ms < 0:
            return
        normalized_priority = _normalize_priority(priority)
        with self._lock:
            m = self._by_model.setdefault(model_id, ModelMetrics(model_id=model_id))
            m.total_latency_ms += latency_ms
            pb = m.by_priority[normalized_priority]
            pb["total_latency_ms"] += latency_ms
            pb["latencies_ms"].append(latency_ms)
            if int(slo_target_ms) > 0:
                pb["slo_target_ms"] = int(slo_target_ms)
                if latency_ms <= float(slo_target_ms):
                    pb["slo_met_count"] += 1
            m.queue_size = self._queue_sizes.get(model_id, 0)

    def record_tokens(self, model_id: str, tokens: int) -> None:
        """Record tokens generated for model."""
        if not model_id or tokens < 0:
            return
        with self._lock:
            m = self._by_model.setdefault(model_id, ModelMetrics(model_id=model_id))
            m.tokens_generated += tokens
            m.queue_size = self._queue_sizes.get(model_id, 0)

    def set_queue_size(self, model_id: str, size: int) -> None:
        """Update current queue size for model (called by InferenceQueue)."""
        if not model_id:
            return
        with self._lock:
            self._queue_sizes[model_id] = max(0, size)
            if model_id in self._by_model:
                self._by_model[model_id].queue_size = self._queue_sizes[model_id]

    def get_metrics(self) -> Dict[str, Any]:
        """Return full metrics: global summary + per-model."""
        with self._lock:
            models = {}
            total_requests = 0
            total_failed = 0
            total_latency_ms = 0.0
            total_tokens = 0
            for mid, m in self._by_model.items():
                m.queue_size = self._queue_sizes.get(mid, 0)
                models[mid] = m.to_dict()
                total_requests += m.requests
                total_failed += m.requests_failed
                total_latency_ms += m.total_latency_ms
                total_tokens += m.tokens_generated
            priority_summary = {
                "high": _default_priority_bucket(),
                "medium": _default_priority_bucket(),
                "low": _default_priority_bucket(),
            }
            for m in self._by_model.values():
                for p in ("high", "medium", "low"):
                    src = m.by_priority[p]
                    dst = priority_summary[p]
                    dst["requests"] += int(src["requests"])
                    dst["requests_failed"] += int(src["requests_failed"])
                    dst["total_latency_ms"] += float(src["total_latency_ms"])
                    dst["latencies_ms"].extend(list(src["latencies_ms"]))
                    if int(src["slo_target_ms"]) > 0:
                        dst["slo_target_ms"] = int(src["slo_target_ms"])
                    dst["slo_met_count"] += int(src["slo_met_count"])
            priority_summary_out: Dict[str, Dict[str, Any]] = {}
            for p, b in priority_summary.items():
                req = int(b["requests"])
                p95 = _compute_percentile(list(b["latencies_ms"]), 0.95)
                slo_target = int(b["slo_target_ms"] or 0)
                slo_met = int(b["slo_met_count"] or 0)
                priority_summary_out[p] = {
                    "requests": req,
                    "requests_failed": int(b["requests_failed"]),
                    "avg_latency_ms": round((float(b["total_latency_ms"]) / req), 2) if req > 0 else 0.0,
                    "p95_latency_ms": round(p95, 2),
                    "slo_target_ms": slo_target,
                    "slo_met_count": slo_met,
                    "slo_met_rate": round((slo_met / req), 4) if req > 0 else 0.0,
                }
            return {
                "summary": {
                    "total_requests": total_requests,
                    "total_requests_failed": total_failed,
                    "total_latency_ms": round(total_latency_ms, 2),
                    "total_tokens_generated": total_tokens,
                    "models_count": len(models),
                },
                "by_priority_summary": priority_summary_out,
                "by_model": models,
            }

    def get_model_metrics(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Return metrics for one model."""
        with self._lock:
            m = self._by_model.get(model_id)
            if not m:
                return None
            m.queue_size = self._queue_sizes.get(model_id, 0)
            return m.to_dict()


# Singleton for process-wide metrics
_metrics: Optional[RuntimeMetrics] = None
_metrics_lock = threading.Lock()


def get_runtime_metrics() -> RuntimeMetrics:
    global _metrics
    with _metrics_lock:
        if _metrics is None:
            _metrics = RuntimeMetrics()
        return _metrics
