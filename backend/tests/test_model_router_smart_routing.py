from core.inference.registry.model_registry import ModelAlias
from core.inference.router.model_router import ModelRouter


class _FakeRegistry:
    def __init__(self) -> None:
        self._aliases = {
            "reasoning-model": ModelAlias(alias="reasoning-model", provider="openai", model_id="stable-v1"),
            "stable-v1": ModelAlias(alias="stable-v1", provider="openai", model_id="stable-v1"),
            "canary-v2": ModelAlias(alias="canary-v2", provider="openai", model_id="canary-v2"),
            "blue-v1": ModelAlias(alias="blue-v1", provider="openai", model_id="blue-v1"),
            "green-v2": ModelAlias(alias="green-v2", provider="openai", model_id="green-v2"),
            "worker-a": ModelAlias(alias="worker-a", provider="openai", model_id="worker-a"),
            "worker-b": ModelAlias(alias="worker-b", provider="openai", model_id="worker-b"),
        }

    def resolve(self, alias_name: str):
        return self._aliases.get(alias_name)

    def list_aliases(self):
        return list(self._aliases.keys())


def test_blue_green_admin_sticky_to_stable(monkeypatch):
    router = ModelRouter(registry=_FakeRegistry())
    monkeypatch.setattr(
        "core.inference.router.model_router.get_inference_smart_routing_policies_json",
        lambda: '{"reasoning-model":{"strategy":"blue_green","stable":"blue-v1","candidate":"green-v2","candidate_percent":100}}',
    )
    monkeypatch.setattr(
        "core.inference.router.model_router.get_inference_smart_routing_enabled",
        lambda: True,
    )
    result = router.resolve("reasoning-model", request_metadata={"role": "admin", "user_id": "u1"})
    assert result.model_id == "blue-v1"
    assert "blue_green" in result.resolved_via


def test_canary_uses_deterministic_bucket(monkeypatch):
    router = ModelRouter(registry=_FakeRegistry())
    monkeypatch.setattr(
        "core.inference.router.model_router.get_inference_smart_routing_policies_json",
        lambda: '{"reasoning-model":{"strategy":"canary","stable":"stable-v1","canary":"canary-v2","canary_percent":100}}',
    )
    monkeypatch.setattr(
        "core.inference.router.model_router.get_inference_smart_routing_enabled",
        lambda: True,
    )
    result = router.resolve("reasoning-model", request_metadata={"user_id": "normal-user"})
    assert result.model_id == "canary-v2"
    assert "canary" in result.resolved_via


def test_least_loaded_picks_lower_queue(monkeypatch):
    router = ModelRouter(registry=_FakeRegistry())
    monkeypatch.setattr(
        "core.inference.router.model_router.get_inference_smart_routing_policies_json",
        lambda: '{"reasoning-model":{"strategy":"least_loaded","candidates":["worker-a","worker-b"]}}',
    )
    monkeypatch.setattr(
        "core.inference.router.model_router.get_inference_smart_routing_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "core.inference.router.model_router.ModelRouter._queue_size",
        staticmethod(lambda model_id: 10 if model_id == "worker-a" else 2),
    )
    result = router.resolve("reasoning-model", request_metadata={"user_id": "u2"})
    assert result.model_id == "worker-b"
    assert "least_loaded" in result.resolved_via


def test_smart_routing_can_be_disabled(monkeypatch):
    router = ModelRouter(registry=_FakeRegistry())
    monkeypatch.setattr(
        "core.inference.router.model_router.get_inference_smart_routing_policies_json",
        lambda: '{"reasoning-model":{"strategy":"blue_green","stable":"blue-v1","candidate":"green-v2","candidate_percent":100}}',
    )
    monkeypatch.setattr(
        "core.inference.router.model_router.get_inference_smart_routing_enabled",
        lambda: False,
    )
    result = router.resolve("reasoning-model", request_metadata={"user_id": "u2"})
    assert result.model_id == "stable-v1"
    assert result.resolved_via == "alias"


def test_device_aware_prefers_gpu_for_large_profile(monkeypatch):
    router = ModelRouter(registry=_FakeRegistry())
    monkeypatch.setattr(
        "core.inference.router.model_router.get_inference_smart_routing_policies_json",
        lambda: (
            '{"reasoning-model":{"strategy":"device_aware","fallback":"worker-a","candidates":['
            '{"target":"worker-a","device":"gpu","weight":3},'
            '{"target":"worker-b","device":"cpu","weight":1}'
            "]}}"
        ),
    )
    monkeypatch.setattr(
        "core.inference.router.model_router.get_inference_smart_routing_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "core.inference.router.model_router.ModelRouter._model_metrics",
        staticmethod(
            lambda model_id: {"queue_size": 1, "avg_latency_ms": 80, "requests": 100, "requests_failed": 1}
        ),
    )
    result = router.resolve(
        "reasoning-model",
        request_metadata={"inference_profile": "large", "preferred_device": "gpu", "input_tokens": 4096},
    )
    assert result.model_id == "worker-a"
    assert "device_aware" in result.resolved_via


def test_device_aware_fallback_to_cpu_when_gpu_overloaded(monkeypatch):
    router = ModelRouter(registry=_FakeRegistry())
    monkeypatch.setattr(
        "core.inference.router.model_router.get_inference_smart_routing_policies_json",
        lambda: (
            '{"reasoning-model":{"strategy":"device_aware","fallback":"worker-b","candidates":['
            '{"target":"worker-a","device":"gpu","weight":3,"max_queue_size":2},'
            '{"target":"worker-b","device":"cpu","weight":1,"max_queue_size":8}'
            "]}}"
        ),
    )
    monkeypatch.setattr(
        "core.inference.router.model_router.get_inference_smart_routing_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "core.inference.router.model_router.ModelRouter._model_metrics",
        staticmethod(
            lambda model_id: (
                {"queue_size": 6, "avg_latency_ms": 120, "requests": 100, "requests_failed": 2}
                if model_id == "worker-a"
                else {"queue_size": 1, "avg_latency_ms": 140, "requests": 100, "requests_failed": 2}
            )
        ),
    )
    result = router.resolve(
        "reasoning-model",
        request_metadata={"inference_profile": "large", "input_tokens": 2048},
    )
    assert result.model_id == "worker-b"
    assert "device_aware" in result.resolved_via


def test_device_aware_uses_explicit_fallback_when_all_unhealthy(monkeypatch):
    router = ModelRouter(registry=_FakeRegistry())
    monkeypatch.setattr(
        "core.inference.router.model_router.get_inference_smart_routing_policies_json",
        lambda: (
            '{"reasoning-model":{"strategy":"device_aware","fallback":"stable-v1","candidates":['
            '{"target":"worker-a","device":"gpu","max_queue_size":1},'
            '{"target":"worker-b","device":"cpu","max_queue_size":1}'
            "]}}"
        ),
    )
    monkeypatch.setattr(
        "core.inference.router.model_router.get_inference_smart_routing_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "core.inference.router.model_router.ModelRouter._model_metrics",
        staticmethod(
            lambda model_id: {"queue_size": 9, "avg_latency_ms": 500, "requests": 100, "requests_failed": 10}
        ),
    )
    result = router.resolve("reasoning-model", request_metadata={"inference_profile": "small"})
    assert result.model_id == "stable-v1"
    assert "device_aware+fallback" in result.resolved_via

