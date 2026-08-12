from __future__ import annotations

import json
import os
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
    global _entra_jwks
    if _entra_jwks is not None:
        return _entra_jwks
    with urllib.request.urlopen(jwks_uri, timeout=10) as resp:  # nosec B310
        data = json.loads(resp.read())
    _entra_jwks = {key["kid"]: key for key in data["keys"]}
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
        if not authorization or authorization != f"Bearer {expected}":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Valid Authorization bearer token is required.",
            )
        # With a configured API key, identity comes from deployment
        # configuration only. Client-supplied x-user-id / x-user-role headers
        # are ignored: they are spoofable and must never feed audit records.
        user_id = os.getenv("APP_API_KEY_USER_ID", "api-key-operator")
        role = os.getenv("APP_API_KEY_USER_ROLE", "planner")
    else:
        user_id = "anonymous"
        role = "planner"
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
