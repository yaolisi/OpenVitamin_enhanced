"""本地账号 Cookie 会话 → request.state.user_id / platform_role。"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from config.settings import settings
from core.data.base import SessionLocal
from core.security.local_auth import local_auth_enabled, resolve_session_token
from middleware.ops_paths import is_api_health_path


def _auth_public_path(path: str) -> bool:
    if is_api_health_path(path):
        return True
    if path.startswith("/api/v1/auth/"):
        return True
    if path in {"/docs", "/redoc", "/openapi.json"}:
        return True
    return False


class LocalAuthContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not local_auth_enabled():
            return await call_next(request)

        cookie_name = (getattr(settings, "local_auth_cookie_name", "perilla_session") or "perilla_session").strip()
        raw = (request.cookies.get(cookie_name) or "").strip()
        if raw:
            db = SessionLocal()
            try:
                user = resolve_session_token(db, raw)
                if user is not None:
                    request.state.user_id = user.id
                    request.state.platform_username = user.username
                    request.state.platform_display_name = user.display_name or user.username
                    from core.security.local_auth import platform_role_from_user

                    request.state.platform_role = platform_role_from_user(user)
                    request.state.auth_method = "local"
            finally:
                db.close()

        if bool(getattr(settings, "auth_require_login", False)):
            method = getattr(request.state, "auth_method", None)
            path = request.url.path or ""
            if method not in {"local", "oidc", "api_key"} and path.startswith("/api/"):
                if not _auth_public_path(path):
                    return JSONResponse(
                        status_code=401,
                        content={"detail": "authentication_required"},
                    )

        return await call_next(request)
