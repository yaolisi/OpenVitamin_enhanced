"""认证：会话、本地账号登录/注册、与 OIDC 并列（内网 / 本机，非公网 SaaS）。"""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from config.settings import settings
from core.data.base import get_db
from core.security.deps import get_platform_role, local_dev_control_plane_unlocked
from core.security.local_auth import (
    authenticate_user,
    create_session,
    local_auth_enabled,
    register_user,
    registration_allowed,
    revoke_session,
)
from core.security.rbac import PlatformRole
from core.utils.user_context import get_user_id

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class AuthConfigResponse(BaseModel):
    local_auth_enabled: bool
    local_auth_allow_registration: bool
    oidc_enabled: bool
    auth_require_login: bool


class AuthSessionResponse(BaseModel):
    authenticated: bool
    user_id: str
    username: Optional[str] = None
    display_name: Optional[str] = None
    platform_role: str
    auth_method: str
    rbac_enabled: bool
    oidc_enabled: bool
    oidc_signed_in: bool
    local_auth_enabled: bool
    local_dev_admin: bool
    require_login: bool
    display_label: str


class LocalRegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=8, max_length=128)
    email: Optional[str] = Field(default=None, max_length=255)
    display_name: Optional[str] = Field(default=None, max_length=128)


class LocalLoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class LocalAuthUserResponse(BaseModel):
    id: str
    username: str
    display_name: str
    platform_role: str
    email: Optional[str] = None


def _auth_method(request: Request) -> str:
    explicit = getattr(request.state, "auth_method", None)
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    api_key_header = getattr(settings, "api_rate_limit_api_key_header", "X-Api-Key")
    if (request.headers.get(api_key_header) or "").strip():
        return "api_key"
    auth = (request.headers.get("Authorization") or "").strip()
    if auth.lower().startswith("bearer "):
        return "oidc"
    return "anonymous"


def _display_label(
    role: PlatformRole,
    auth_method: str,
    user_id: str,
    username: Optional[str] = None,
    display_name: Optional[str] = None,
) -> str:
    if display_name:
        return display_name
    if username:
        return username
    if auth_method == "oidc" and user_id and user_id != "default":
        return user_id
    if role == PlatformRole.ADMIN:
        return "admin"
    if role == PlatformRole.OPERATOR:
        return "operator"
    if role == PlatformRole.VIEWER:
        return "viewer"
    return user_id or "default"


def _session_cookie_name() -> str:
    return (getattr(settings, "local_auth_cookie_name", "perilla_session") or "perilla_session").strip()


def _set_session_cookie(response: Response, raw_token: str) -> None:
    max_age = int(getattr(settings, "local_auth_session_ttl_hours", 168) or 168) * 3600
    secure = bool(getattr(settings, "local_auth_cookie_secure", False) or (not bool(getattr(settings, "debug", True))))
    response.set_cookie(
        key=_session_cookie_name(),
        value=raw_token,
        max_age=max_age,
        path="/",
        httponly=True,
        samesite="lax",
        secure=secure,
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=_session_cookie_name(), path="/")


def _is_authenticated(method: str, local_admin: bool) -> bool:
    if local_admin:
        return True
    return method in {"local", "oidc", "api_key"}


@router.get("/config", response_model=AuthConfigResponse)
def get_auth_config() -> AuthConfigResponse:
    return AuthConfigResponse(
        local_auth_enabled=local_auth_enabled(),
        local_auth_allow_registration=registration_allowed(),
        oidc_enabled=bool(getattr(settings, "oidc_enabled", False)),
        auth_require_login=bool(getattr(settings, "auth_require_login", False)),
    )


@router.get("/session", response_model=AuthSessionResponse)
def get_auth_session(request: Request) -> AuthSessionResponse:
    role = get_platform_role(request)
    user_id = get_user_id(request)
    method = _auth_method(request)
    oidc_on = bool(getattr(settings, "oidc_enabled", False))
    oidc_signed_in = method == "oidc"
    local_admin = local_dev_control_plane_unlocked()
    effective_role = PlatformRole.ADMIN if local_admin else role
    username = getattr(request.state, "platform_username", None)
    display_name = getattr(request.state, "platform_display_name", None)
    require_login = bool(getattr(settings, "auth_require_login", False))
    if require_login and not local_auth_enabled() and not oidc_on:
        require_login = False
    authenticated = _is_authenticated(method, local_admin)
    return AuthSessionResponse(
        authenticated=authenticated,
        user_id=user_id,
        username=username if isinstance(username, str) else None,
        display_name=display_name if isinstance(display_name, str) else None,
        platform_role=effective_role.value,
        auth_method=method,
        rbac_enabled=bool(getattr(settings, "rbac_enabled", False)),
        oidc_enabled=oidc_on,
        oidc_signed_in=oidc_signed_in,
        local_auth_enabled=local_auth_enabled(),
        local_dev_admin=local_admin,
        require_login=require_login,
        display_label=_display_label(
            effective_role,
            method,
            user_id,
            username if isinstance(username, str) else None,
            display_name,
        ),
    )


@router.post("/register", response_model=LocalAuthUserResponse)
def local_register(
    body: LocalRegisterRequest,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> LocalAuthUserResponse:
    if not local_auth_enabled():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="local_auth_disabled")
    user, err = register_user(
        db,
        username=body.username,
        password=body.password,
        email=body.email,
        display_name=body.display_name,
    )
    if user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err or "registration_failed")
    token = create_session(db, user.id)
    _set_session_cookie(response, token)
    pub = user.to_public_dict()
    return LocalAuthUserResponse(
        id=pub["id"],
        username=pub["username"],
        display_name=pub["display_name"],
        platform_role=pub["platform_role"],
        email=pub.get("email"),
    )


@router.post("/login", response_model=LocalAuthUserResponse)
def local_login(
    body: LocalLoginRequest,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> LocalAuthUserResponse:
    if not local_auth_enabled():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="local_auth_disabled")
    user, err = authenticate_user(db, username=body.username, password=body.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=err or "invalid_credentials",
        )
    token = create_session(db, user.id)
    _set_session_cookie(response, token)
    pub = user.to_public_dict()
    return LocalAuthUserResponse(
        id=pub["id"],
        username=pub["username"],
        display_name=pub["display_name"],
        platform_role=pub["platform_role"],
        email=pub.get("email"),
    )


@router.post("/logout")
def local_logout(
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    raw = (request.cookies.get(_session_cookie_name()) or "").strip()
    if raw:
        revoke_session(db, raw)
    _clear_session_cookie(response)
    return {"ok": True}
