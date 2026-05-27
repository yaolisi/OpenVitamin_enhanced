"""OIDC PKCE 登录辅助 API（不含完整 IdP UI，由前端 /auth/callback 完成）。"""
from __future__ import annotations

import secrets
from typing import Annotated, Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from config.settings import settings
from core.security.oidc_pkce import build_authorize_url, exchange_code_for_tokens, generate_pkce_pair

router = APIRouter(prefix="/api/v1/auth/oidc", tags=["auth-oidc"])


class OidcLoginConfigResponse(BaseModel):
    enabled: bool
    client_id: Optional[str] = None
    issuer: Optional[str] = None
    redirect_uri: Optional[str] = None
    scopes: Optional[str] = None


class OidcAuthorizePrepareResponse(BaseModel):
    authorize_url: str
    state: str
    code_verifier: str


class OidcTokenExchangeRequest(BaseModel):
    code: str
    code_verifier: str
    redirect_uri: Optional[str] = None


class OidcTokenExchangeResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: Optional[int] = None
    refresh_token: Optional[str] = None
    id_token: Optional[str] = None


@router.get("/config", response_model=OidcLoginConfigResponse)
def get_oidc_login_config() -> OidcLoginConfigResponse:
    on = bool(getattr(settings, "oidc_enabled", False))
    return OidcLoginConfigResponse(
        enabled=on,
        client_id=(getattr(settings, "oidc_client_id", "") or "").strip() or None,
        issuer=(getattr(settings, "oidc_issuer", "") or "").strip() or None,
        redirect_uri=(getattr(settings, "oidc_redirect_uri", "") or "").strip() or None,
        scopes=(getattr(settings, "oidc_scopes", "") or "").strip() or None,
    )


@router.post("/authorize-prepare", response_model=OidcAuthorizePrepareResponse)
def prepare_oidc_authorize() -> OidcAuthorizePrepareResponse:
    if not bool(getattr(settings, "oidc_enabled", False)):
        raise HTTPException(status_code=400, detail="oidc_disabled")
    verifier, challenge = generate_pkce_pair()
    state = secrets.token_urlsafe(24)
    url = build_authorize_url(state=state, code_challenge=challenge)
    return OidcAuthorizePrepareResponse(
        authorize_url=url,
        state=state,
        code_verifier=verifier,
    )


@router.post("/token", response_model=OidcTokenExchangeResponse)
async def exchange_oidc_token(body: OidcTokenExchangeRequest) -> OidcTokenExchangeResponse:
    if not bool(getattr(settings, "oidc_enabled", False)):
        raise HTTPException(status_code=400, detail="oidc_disabled")
    try:
        tokens = await exchange_code_for_tokens(
            code=body.code.strip(),
            code_verifier=body.code_verifier.strip(),
            redirect_uri=body.redirect_uri,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"token_exchange_failed:{exc}") from exc
    access = str(tokens.get("access_token") or "").strip()
    if not access:
        raise HTTPException(status_code=400, detail="missing_access_token")
    return OidcTokenExchangeResponse(
        access_token=access,
        token_type=str(tokens.get("token_type") or "Bearer"),
        expires_in=tokens.get("expires_in"),
        refresh_token=tokens.get("refresh_token"),
        id_token=tokens.get("id_token"),
    )
