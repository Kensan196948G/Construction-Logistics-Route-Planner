from __future__ import annotations

import hmac
import json
import os
import threading
import time
import urllib.request
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from jose import JWTError, jwt
from jose import jwk as jose_jwk
from pydantic import BaseModel


class UserInfo(BaseModel):
    user_id: str
    display_name: str
    email: str
    role: str


# Minimal RBAC for the first production sprint: admin / planner / site_user / viewer.
# Priority order matters: _extract_role() returns the first matching role in this tuple.
ROLES: tuple[str, ...] = ("admin", "planner", "site_user", "viewer")

_entra_jwks: dict[str, dict] | None = None
_entra_jwks_fetched_at: float = 0.0
_entra_jwks_lock = threading.Lock()
_JWKS_CACHE_TTL_SECONDS = 6 * 60 * 60


def _is_production_mode() -> bool:
    """Whether the deployment claims to be production (fail-closed)."""

    return os.getenv("PRODUCTION_MODE", "").strip().lower() in {"1", "true", "yes", "on"}


def _auth_configured() -> bool:
    return bool(os.getenv("APP_API_KEY")) or _is_oidc_enabled()


def _poc_anonymous_role() -> str:
    """Role for the open PoC identity (no auth configured, not production).

    The default stays ``planner``. A local demo deployment can opt into
    ``admin`` so every workflow (approve, audit-log view/export) is exercisable
    without a key. Production mode is fail-closed and never uses this path.
    """

    role = os.getenv("POC_ANONYMOUS_ROLE", "planner").strip()
    return role if role in ROLES else "planner"


def _is_oidc_enabled() -> bool:
    return bool(os.getenv("ENTRA_TENANT_ID"))


def _entra_config() -> dict:
    tenant_id = os.getenv("ENTRA_TENANT_ID")
    client_id = os.getenv("ENTRA_CLIENT_ID", "")
    return {
        "tenant_id": tenant_id,
        "client_id": client_id,
        "issuer": f"https://login.microsoftonline.com/{tenant_id}/v2.0",
        "jwks_uri": f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys",
    }


def _fetch_entra_jwks(jwks_uri: str) -> dict[str, dict]:
    """Fetch and cache Entra signing keys with a TTL and refresh on kid miss.

    A global cache without expiry breaks token validation after a key rotation;
    a cache that never refreshes on an unknown ``kid`` forces a process restart.
    Both failure modes are avoided here: stale entries are re-fetched after the
    TTL, and an unknown kid triggers one immediate refresh before giving up.
    """

    global _entra_jwks, _entra_jwks_fetched_at
    now = time.monotonic()
    with _entra_jwks_lock:
        if _entra_jwks is not None and now - _entra_jwks_fetched_at < _JWKS_CACHE_TTL_SECONDS:
            return _entra_jwks
        with urllib.request.urlopen(jwks_uri, timeout=10) as resp:  # nosec B310
            data = json.loads(resp.read())
        keys = {key["kid"]: key for key in data.get("keys", [])}
        if not keys:
            raise RuntimeError("Entra JWKS endpoint returned no keys")
        _entra_jwks = keys
        _entra_jwks_fetched_at = now
        return _entra_jwks


def _refresh_entra_jwks(jwks_uri: str) -> dict[str, dict]:
    """Force one JWKS refresh (used when the cached keys do not contain the kid)."""

    global _entra_jwks, _entra_jwks_fetched_at
    with _entra_jwks_lock:
        with urllib.request.urlopen(jwks_uri, timeout=10) as resp:  # nosec B310
            data = json.loads(resp.read())
        keys = {key["kid"]: key for key in data.get("keys", [])}
        if not keys:
            raise RuntimeError("Entra JWKS endpoint returned no keys")
        _entra_jwks = keys
        _entra_jwks_fetched_at = time.monotonic()
        return _entra_jwks


async def get_current_user(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> UserInfo:
    if _is_oidc_enabled():
        user = await _oidc_auth(authorization, _entra_config())
    else:
        user = _api_key_auth(request, authorization)
    request.state.user = user
    return user


async def _oidc_auth(authorization: str | None, config: dict) -> UserInfo:
    if not config.get("client_id"):
        # ENTRA_TENANT_ID without ENTRA_CLIENT_ID is a deployment error, not a
        # reason to fall back to open access. Fail closed with a clear signal.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OIDC is enabled but ENTRA_CLIENT_ID is not configured.",
        )
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization bearer token is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization.removeprefix("Bearer ").strip()

    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token header.",
        )

    kid = unverified_header.get("kid")
    jwks = _fetch_entra_jwks(config["jwks_uri"])
    jwk_data = jwks.get(kid)
    if jwk_data is None:
        # Possible key rotation: refresh once before rejecting the token.
        jwks = _refresh_entra_jwks(config["jwks_uri"])
        jwk_data = jwks.get(kid)
    if jwk_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Signing key not found for token.",
        )
    key = jose_jwk.construct(jwk_data)

    try:
        payload = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=config["client_id"],
            issuer=config["issuer"],
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token validation failed.",
        ) from exc

    roles_claim: list[str] = payload.get("roles", [])
    role = _extract_role(roles_claim)
    sub = payload.get("sub") or payload.get("oid", "unknown")

    return UserInfo(
        user_id=sub,
        display_name=payload.get("name", sub),
        email=payload.get("email") or payload.get("preferred_username", ""),
        role=role,
    )


def _api_key_auth(request: Request, authorization: str | None) -> UserInfo:
    expected = os.getenv("APP_API_KEY")
    if expected:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Valid Authorization bearer token is required.",
            )
        provided = authorization.removeprefix("Bearer ").strip()
        if not hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8")):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Valid Authorization bearer token is required.",
            )
        # With a configured API key, identity comes from deployment
        # configuration only. Client-supplied x-user-id / x-user-role headers
        # are ignored: they are spoofable and must never feed audit records.
        user_id = os.getenv("APP_API_KEY_USER_ID", "api-key-operator")
        role = os.getenv("APP_API_KEY_USER_ROLE", "planner")
    elif _is_production_mode():
        # Production mode must never run open. Without APP_API_KEY or Entra ID
        # configured, every protected operation is refused with a clear 503 so
        # the deployment error surfaces instead of an authorization bypass.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Authentication is not configured for production mode. "
                "Set APP_API_KEY or ENTRA_TENANT_ID/ENTRA_CLIENT_ID."
            ),
        )
    else:
        # PoC/local mode only: no key configured means open access with a
        # fixed non-spoofable identity. This is intentional and documented;
        # PRODUCTION_MODE=1 switches it to fail-closed.
        user_id = "anonymous"
        role = _poc_anonymous_role()
    if role not in ROLES:
        role = "planner"

    return UserInfo(
        user_id=user_id,
        display_name=user_id,
        email=f"{user_id}@local",
        role=role,
    )


def _extract_role(roles_claim: list[str]) -> str:
    for role in ROLES:
        if role in roles_claim:
            return role
    return "viewer"


def require_role(*roles: str):
    async def _require(user: Annotated[UserInfo, Depends(get_current_user)]) -> UserInfo:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required role(s): {', '.join(roles)}.",
            )
        return user

    return Depends(_require)
