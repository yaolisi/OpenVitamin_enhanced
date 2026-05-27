"""
OIDC JWT 校验（RS256 + JWKS）。默认关闭；启用后由中间件解析 Bearer Token。
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import httpx
import jwt
from jwt import PyJWKClient

from config.settings import settings
from core.security.rbac import PlatformRole


@dataclass
class OidcClaims:
    subject: str
    roles: List[str]
    raw: Dict[str, Any]


_jwks_client: Optional[PyJWKClient] = None
_jwks_url_loaded: str = ""


def _jwks_url() -> str:
    explicit = (getattr(settings, "oidc_jwks_url", "") or "").strip()
    if explicit:
        return explicit
    issuer = (getattr(settings, "oidc_issuer", "") or "").strip().rstrip("/")
    if not issuer:
        return ""
    return f"{issuer}/.well-known/jwks.json"


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client, _jwks_url_loaded
    url = _jwks_url()
    if not url:
        raise ValueError("oidc_jwks_url or oidc_issuer required when oidc_enabled")
    if _jwks_client is None or _jwks_url_loaded != url:
        _jwks_client = PyJWKClient(url, cache_keys=True, lifespan=3600)
        _jwks_url_loaded = url
    return _jwks_client


def _extract_roles(claims: Dict[str, Any]) -> List[str]:
    claim_name = (getattr(settings, "oidc_role_claim", "roles") or "roles").strip()
    raw = claims.get(claim_name)
    if isinstance(raw, str):
        return [x.strip() for x in raw.replace(",", " ").split() if x.strip()]
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    return []


def _map_roles_to_platform(roles: List[str]) -> PlatformRole:
    role_set = {r.lower() for r in roles}
    admin_names = {
        x.strip().lower()
        for x in (getattr(settings, "oidc_admin_roles", "admin") or "admin").split(",")
        if x.strip()
    }
    operator_names = {
        x.strip().lower()
        for x in (getattr(settings, "oidc_operator_roles", "operator") or "operator").split(",")
        if x.strip()
    }
    if role_set & admin_names:
        return PlatformRole.ADMIN
    if role_set & operator_names:
        return PlatformRole.OPERATOR
    default_s = (getattr(settings, "oidc_default_role", "viewer") or "viewer").lower()
    try:
        return PlatformRole(default_s)
    except ValueError:
        return PlatformRole.VIEWER


def validate_bearer_token(token: str) -> Tuple[Optional[OidcClaims], Optional[str]]:
    """返回 (claims, error_message)。"""
    if not bool(getattr(settings, "oidc_enabled", False)):
        return None, "oidc_disabled"
    tok = (token or "").strip()
    if not tok:
        return None, "empty_token"
    audience = (getattr(settings, "oidc_audience", "") or "").strip()
    issuer = (getattr(settings, "oidc_issuer", "") or "").strip()
    try:
        client = _get_jwks_client()
        signing_key = client.get_signing_key_from_jwt(tok)
        options = {"require": ["exp", "sub"]}
        decode_kwargs: Dict[str, Any] = {
            "algorithms": ["RS256", "ES256"],
            "options": options,
        }
        if audience:
            decode_kwargs["audience"] = audience
        if issuer:
            decode_kwargs["issuer"] = issuer
        claims = jwt.decode(tok, signing_key.key, **decode_kwargs)
        if not isinstance(claims, dict):
            return None, "invalid_claims"
        sub = str(claims.get("sub") or "").strip()
        if not sub:
            return None, "missing_sub"
        roles = _extract_roles(claims)
        return OidcClaims(subject=sub, roles=roles, raw=claims), None
    except jwt.PyJWTError as exc:
        return None, str(exc)
    except httpx.HTTPError as exc:
        return None, f"jwks_fetch_failed:{exc}"
    except Exception as exc:
        return None, str(exc)


def resolve_platform_role_from_token(token: str) -> Tuple[Optional[PlatformRole], Optional[str], Optional[str]]:
    """返回 (platform_role, oidc_subject, error)。"""
    claims, err = validate_bearer_token(token)
    if err or claims is None:
        return None, None, err
    return _map_roles_to_platform(claims.roles), claims.subject, None
