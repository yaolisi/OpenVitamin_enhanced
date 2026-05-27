"""
OIDC Authorization Code + PKCE（SPA 友好：前端存 verifier，后端换 token）。
"""
from __future__ import annotations

import base64
import hashlib
import secrets
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlencode

import httpx

from config.settings import settings


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def generate_pkce_pair() -> Tuple[str, str]:
    verifier = _b64url(secrets.token_bytes(32))
    challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    return verifier, challenge


def build_authorize_url(*, state: str, code_challenge: str) -> str:
    issuer = (getattr(settings, "oidc_issuer", "") or "").strip().rstrip("/")
    auth_ep = (getattr(settings, "oidc_authorization_endpoint", "") or "").strip()
    if not auth_ep and issuer:
        auth_ep = f"{issuer}/authorize"
    client_id = (getattr(settings, "oidc_client_id", "") or "").strip()
    redirect_uri = (getattr(settings, "oidc_redirect_uri", "") or "").strip()
    if not auth_ep or not client_id or not redirect_uri:
        raise ValueError("oidc_client_id, oidc_redirect_uri and authorization endpoint required")

    scope = (getattr(settings, "oidc_scopes", "openid profile email") or "openid profile email").strip()
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{auth_ep}?{urlencode(params)}"


async def exchange_code_for_tokens(
    *,
    code: str,
    code_verifier: str,
    redirect_uri: Optional[str] = None,
) -> Dict[str, Any]:
    issuer = (getattr(settings, "oidc_issuer", "") or "").strip().rstrip("/")
    token_ep = (getattr(settings, "oidc_token_endpoint", "") or "").strip()
    if not token_ep and issuer:
        token_ep = f"{issuer}/token"
    client_id = (getattr(settings, "oidc_client_id", "") or "").strip()
    client_secret = (getattr(settings, "oidc_client_secret", "") or "").strip()
    redir = redirect_uri or (getattr(settings, "oidc_redirect_uri", "") or "").strip()
    if not token_ep or not client_id or not redir:
        raise ValueError("token endpoint, client_id and redirect_uri required")

    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redir,
        "client_id": client_id,
        "code_verifier": code_verifier,
    }
    if client_secret:
        data["client_secret"] = client_secret

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(token_ep, data=data)
        resp.raise_for_status()
        return resp.json()
