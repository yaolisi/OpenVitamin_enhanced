"""
Tenant context middleware.
为请求注入 tenant_id，并可对关键控制面启用租户强制校验。
"""
from __future__ import annotations

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from config.settings import settings
from middleware.tenant_paths import is_tenant_enforcement_protected_path


_HEADER = getattr(settings, "tenant_header_name", "X-Tenant-Id")


class TenantContextMiddleware:
    """租户上下文中间件（纯 ASGI，避免 BaseHTTPMiddleware 嵌套过深导致流式响应兼容性问题）"""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        header_tenant_id = (request.headers.get(_HEADER) or "").strip()
        tenant_id = (header_tenant_id or getattr(settings, "tenant_default_id", "default")).strip()
        if not tenant_id:
            tenant_id = getattr(settings, "tenant_default_id", "default")
        request.state.tenant_id = tenant_id

        if getattr(settings, "tenant_enforcement_enabled", False) and is_tenant_enforcement_protected_path(
            request.url.path
        ):
            if not header_tenant_id:
                response = JSONResponse(
                    status_code=400,
                    content={
                        "detail": "tenant id required for protected path",
                        "path": request.url.path,
                    },
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)
