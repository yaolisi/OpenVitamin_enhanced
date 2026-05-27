"""
企业能力探测与生产就绪评估（无副作用，可缓存于探针/控制台）。
"""
from __future__ import annotations

from typing import Any, Dict, List

from config.settings import settings


def build_enterprise_capabilities() -> Dict[str, Any]:
    oidc_on = bool(getattr(settings, "oidc_enabled", False))
    issuer = (getattr(settings, "oidc_issuer", "") or "").strip()
    jwks = (getattr(settings, "oidc_jwks_url", "") or "").strip()
    oidc_configured = oidc_on and bool(issuer or jwks)

    otel_on = bool(getattr(settings, "otel_enabled", False))
    otel_ep = (getattr(settings, "otel_exporter_otlp_endpoint", "") or "").strip()
    otel_ready = otel_on and bool(otel_ep)

    audit_on = bool(getattr(settings, "audit_log_enabled", False))
    rbac_on = bool(getattr(settings, "rbac_enabled", False))
    tenant_on = bool(getattr(settings, "tenant_enforcement_enabled", False))

    checks = evaluate_production_readiness()
    score = sum(1 for c in checks if c.get("status") == "ok")
    total = len(checks) or 1

    return {
        "oidc_enabled": oidc_on,
        "oidc_configured": oidc_configured,
        "oidc_issuer": issuer or None,
        "secret_resolver_mode": (getattr(settings, "secret_resolver_mode", "env") or "env").strip(),
        "otel_enabled": otel_on,
        "otel_exporter_configured": bool(otel_ep),
        "otel_ready": otel_ready,
        "ha_profile": (getattr(settings, "ha_profile", "") or "").strip() or "standard",
        "prometheus_enabled": bool(getattr(settings, "prometheus_enabled", True)),
        "audit_log_enabled": audit_on,
        "rbac_enabled": rbac_on,
        "tenant_enforcement_enabled": tenant_on,
        "identity_boundary_ready": _identity_boundary_ready(oidc_configured, rbac_on, tenant_on),
        "production_readiness": {
            "score": score,
            "total": total,
            "percent": round(100.0 * score / total, 1),
            "checks": checks,
        },
    }


def _identity_boundary_ready(oidc_configured: bool, rbac_on: bool, tenant_on: bool) -> bool:
    if oidc_configured:
        return True
    if rbac_on and bool(getattr(settings, "rbac_enforcement", False)):
        return True
    return tenant_on


def evaluate_production_readiness() -> List[Dict[str, Any]]:
    """生产就绪检查清单（信息性；不替代 K8s/等保测评）。"""
    debug = bool(getattr(settings, "debug", True))
    checks: List[Dict[str, Any]] = []

    def add(item_id: str, label: str, ok: bool, hint: str = "") -> None:
        checks.append(
            {
                "id": item_id,
                "label": label,
                "status": "ok" if ok else "warn",
                "hint": hint or None,
            }
        )

    add("debug_off", "非调试模式 (DEBUG=false)", not debug, "生产应关闭 DEBUG")
    add(
        "rbac",
        "RBAC 已启用",
        bool(getattr(settings, "rbac_enabled", False)),
        "设置 RBAC_ENABLED=true 并配置 API Key 分段",
    )
    add(
        "rbac_enforcement",
        "RBAC 写保护",
        bool(getattr(settings, "rbac_enforcement", False)),
        "设置 RBAC_ENFORCEMENT=true 限制 viewer 写操作",
    )
    add(
        "audit",
        "审计日志",
        bool(getattr(settings, "audit_log_enabled", False)),
        "AUDIT_LOG_ENABLED=true 并配置路径前缀",
    )
    add(
        "tenant",
        "租户隔离",
        bool(getattr(settings, "tenant_enforcement_enabled", False)),
        "TENANT_ENFORCEMENT_ENABLED=true",
    )
    oidc_on = bool(getattr(settings, "oidc_enabled", False))
    issuer = (getattr(settings, "oidc_issuer", "") or "").strip()
    jwks = (getattr(settings, "oidc_jwks_url", "") or "").strip()
    if oidc_on:
        add("oidc", "OIDC 已配置 Issuer/JWKS", bool(issuer or jwks), "设置 OIDC_ISSUER 或 OIDC_JWKS_URL")
    else:
        add("oidc", "OIDC（可选）", True, "企业 IdP 场景可启用 OIDC_ENABLED")
    add(
        "security_headers",
        "安全响应头",
        bool(getattr(settings, "security_headers_enabled", False)),
        "SECURITY_HEADERS_ENABLED=true",
    )
    add(
        "redaction",
        "敏感数据脱敏",
        bool(getattr(settings, "data_redaction_enabled", True)),
        "DATA_REDACTION_ENABLED=true",
    )
    cors = (getattr(settings, "cors_allowed_origins", "") or "").strip()
    add("cors", "CORS 白名单", bool(cors), "配置 CORS_ALLOWED_ORIGINS")
    add(
        "draft_exec",
        "禁止草稿执行（生产）",
        debug or not bool(getattr(settings, "workflow_allow_draft_execution", False)),
        "WORKFLOW_ALLOW_DRAFT_EXECUTION=false",
    )
    otel_on = bool(getattr(settings, "otel_enabled", False))
    otel_ep = (getattr(settings, "otel_exporter_otlp_endpoint", "") or "").strip()
    if otel_on:
        add("otel", "OTel OTLP 端点", bool(otel_ep), "OTEL_EXPORTER_OTLP_ENDPOINT")
    else:
        add("otel", "分布式追踪（可选）", True, "可启用 OTEL_ENABLED + OTLP")

    return checks


def enterprise_health_snapshot() -> Dict[str, Any]:
    """供 /api/health/ready 附带的轻量企业快照（不触发 503）。"""
    caps = build_enterprise_capabilities()
    pr = caps.get("production_readiness") or {}
    return {
        "identity_boundary_ready": caps.get("identity_boundary_ready"),
        "production_readiness_percent": pr.get("percent"),
        "oidc_configured": caps.get("oidc_configured"),
        "otel_ready": caps.get("otel_ready"),
    }
