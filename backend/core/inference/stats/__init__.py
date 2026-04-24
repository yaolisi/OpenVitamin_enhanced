"""
V2.8 Inference Gateway Layer - Stats Module

Provides inference statistics tracking.
"""
from core.inference.stats.tracker import (
    InferenceStatsTracker,
    get_inference_stats,
    record_inference,
    record_inference_cache_hit,
    record_inference_cache_miss,
    estimate_tokens,
)

__all__ = [
    "InferenceStatsTracker",
    "get_inference_stats",
    "record_inference",
    "record_inference_cache_hit",
    "record_inference_cache_miss",
    "estimate_tokens",
]
