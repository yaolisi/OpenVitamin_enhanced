"""
API Key -> tenant 绑定校验中间件。
"""
from __future__ import annotations

import json
from typing import Dict, List

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from config.settings import settings
from middleware.tenant_paths import is_tenant_enforcement_protected_path


_API_KEY_HEADER = getattr(settings, "api_rate_limit_api_key_header", "X-Api-Key")
_TENANT_HEADER = getattr(settings, "tenant_header_name", "X-Tenant-Id")
_TENANT_DEFAULT = getattr(settings, "tenant_default_id", "default")


def _parse_key_tenants(raw: str) -> Dict[str, List[str]]:
    try:
        data = json.loads(raw or "{}")
        if not isinstance(data, dict):
            return {}
        out: Dict[str, List[str]] = {}
        for k, v in data.items():
            if not isinstance(k, str) or not isinstance(v, list):
                continue
            out[k] = [str(x).strip() for x in v if str(x).strip()]
        return out
    except Exception:
        return {}


class TenantApiKeyBindingMiddleware:
    """API Key 租户绑定中间件（纯 ASGI）"""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if not getattr(settings, "tenant_api_key_binding_enabled", False):
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        if not is_tenant_enforcement_protected_path(request.url.path):
            await self.app(scope, receive, send)
            return

        tenant_id = str(getattr(request.state, "tenant_id", "") or "").strip()
        if not tenant_id:
            tenant_id = (request.headers.get(_TENANT_HEADER) or _TENANT_DEFAULT).strip()
        api_key = (request.headers.get(_API_KEY_HEADER) or "").strip()
        if not api_key:
            response = JSONResponse(status_code=403, content={"detail": "api key required for tenant-bound path"})
            await response(scope, receive, send)
            return

        mapping = _parse_key_tenants(getattr(settings, "tenant_api_key_tenants_json", "{}"))
        allowed_tenants = mapping.get(api_key, [])
        if not allowed_tenants:
            response = JSONResponse(status_code=403, content={"detail": "api key is not tenant-bound"})
            await response(scope, receive, send)
            return

        if "*" not in allowed_tenants and tenant_id not in allowed_tenants:
            response = JSONResponse(
                status_code=403,
                content={"detail": "tenant access denied for api key", "tenant_id": tenant_id},
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
