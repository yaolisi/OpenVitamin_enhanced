"""
OpenTelemetry 可选接入：OTEL_ENABLED=true 且配置 OTLP 端点时启用。

未安装 opentelemetry 包时静默跳过，不影响网关启动。
"""
from __future__ import annotations

import logging
from typing import Optional

from config.settings import settings

logger = logging.getLogger(__name__)
_configured = False


def configure_opentelemetry(app: Optional[object] = None) -> bool:
    global _configured
    if _configured:
        return True
    if not bool(getattr(settings, "otel_enabled", False)):
        return False
    endpoint = (getattr(settings, "otel_exporter_otlp_endpoint", "") or "").strip()
    if not endpoint:
        logger.info("[OTel] otel_enabled but OTEL_EXPORTER_OTLP_ENDPOINT empty; skipped")
        return False
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError as exc:
        logger.warning("[OTel] packages not installed: %s", exc)
        return False

    service_name = (getattr(settings, "otel_service_name", "perilla-gateway") or "perilla-gateway").strip()
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=endpoint)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    if app is not None:
        FastAPIInstrumentor.instrument_app(app, excluded_urls="/api/health,/api/health/live,/api/health/ready,/metrics")
    _configured = True
    logger.info("[OTel] OTLP exporter enabled: %s service=%s", endpoint, service_name)
    return True
