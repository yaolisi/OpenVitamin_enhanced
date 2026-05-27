"""
注入平台角色（PlatformRole）到 request.state.platform_role。
"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from config.settings import settings
from core.security.oidc_validator import resolve_platform_role_from_token
from core.security.rbac import PlatformRole, parse_api_key_list, resolve_role_from_api_key


class RBACContextMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, api_key_header: str = "X-Api-Key"):
        super().__init__(app)
        self._api_key_header = api_key_header

    async def dispatch(self, request: Request, call_next):
        oidc_on = bool(getattr(settings, "oidc_enabled", False))
        if not getattr(settings, "rbac_enabled", False):
            if not oidc_on:
                request.state.platform_role = PlatformRole.OPERATOR
                return await call_next(request)
            bearer_role, oidc_err = self._role_from_bearer(request)
            if oidc_err:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "oidc_invalid_token", "error": oidc_err},
                )
            if bearer_role is not None:
                request.state.platform_role = bearer_role
                request.state.auth_method = "oidc"
            else:
                request.state.platform_role = PlatformRole.OPERATOR
            return await call_next(request)

        api_key = request.headers.get(self._api_key_header)
        admin_keys = parse_api_key_list(getattr(settings, "rbac_admin_api_keys", "") or "")
        operator_keys = parse_api_key_list(getattr(settings, "rbac_operator_api_keys", "") or "")
        viewer_keys = parse_api_key_list(getattr(settings, "rbac_viewer_api_keys", "") or "")
        default_s = (getattr(settings, "rbac_default_role", "operator") or "operator").lower()
        try:
            default_role = PlatformRole(default_s)
        except ValueError:
            default_role = PlatformRole.OPERATOR

        if (api_key or "").strip():
            role = resolve_role_from_api_key(
                api_key, admin_keys, operator_keys, viewer_keys, default_role
            )
            request.state.platform_role = role
            request.state.auth_method = "api_key"
            return await call_next(request)

        if oidc_on:
            bearer_role, oidc_err = self._role_from_bearer(request)
            if oidc_err:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "oidc_invalid_token", "error": oidc_err},
                )
            if bearer_role is not None:
                request.state.platform_role = bearer_role
                request.state.auth_method = "oidc"
                return await call_next(request)

        role = resolve_role_from_api_key(
            api_key, admin_keys, operator_keys, viewer_keys, default_role
        )
        request.state.platform_role = role
        return await call_next(request)

    def _role_from_bearer(self, request: Request) -> tuple[PlatformRole | None, str | None]:
        auth = (request.headers.get("Authorization") or "").strip()
        if not auth.lower().startswith("bearer "):
            return None, None
        token = auth[7:].strip()
        role, sub, err = resolve_platform_role_from_token(token)
        if role is None:
            return None, err or "invalid_token"
        if sub:
            request.state.user_id = sub
            request.state.oidc_subject = sub
        return role, None
