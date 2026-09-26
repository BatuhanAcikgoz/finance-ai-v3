
"""Auth endpoints — currently a minimal dev-token issuer (issue #5 / NFR-002).

Production hardening: wire /token to a real user table, /me to JWT
verification, and rotate the secret. The dev path here is intentionally
gated by an env flag so production deploys can disable it.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

logger = logging.getLogger(__name__)


# ---- shared JWT settings ---------------------------------------------------

JWT_SECRET = os.getenv("JWT_SECRET", "dev_jwt_secret_change_me")
JWT_ALGORITHM = "HS256"
DEV_AUTH_ENABLED = os.getenv("DEV_AUTH_ENABLED", "true").lower() in {"1", "true", "yes"}


def _make_jwt(sub: str, expires_in_s: int = 3600, **extra) -> str:
    payload = {
        "sub": sub,
        "iat": int(time.time()),
        "exp": int(time.time()) + expires_in_s,
    }
    payload.update(extra)
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_jwt(token: str) -> dict | None:
    """Return claims dict or None if the token is invalid / expired."""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError as exc:  # noqa: BLE001
        logger.debug("jwt decode failed: %s", exc)
        return None


# ---- models ----------------------------------------------------------------

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 3600


class User(BaseModel):
    user_id: str
    email: str
    is_active: bool = True


# ---- endpoints -------------------------------------------------------------

@router.post("/token", response_model=Token)
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]) -> Token:
    """Login and get JWT token (TODO: real user table)."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not implemented yet",
    )


@router.get("/me", response_model=User)
async def get_current_user(token: Annotated[str | None, Depends(oauth2_scheme)]) -> User:
    """Get current user info — accepts the JWT issued by /v1/auth/dev-token."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    claims = decode_jwt(token)
    if not claims:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    sub = claims.get("sub", "anon")
    return User(user_id=sub, email=f"{sub}@finance-ai.local", is_active=True)


@router.post("/dev-token", response_model=Token)
async def dev_token() -> Token:
    """Issue a short-lived dev JWT (issue #5 / NFR-002).

    Disabled unless DEV_AUTH_ENABLED=true. The token carries no real user
    identity; it's just enough to satisfy WS auth.
    """
    if not DEV_AUTH_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="dev-token endpoint disabled (set DEV_AUTH_ENABLED=true)",
        )
    return Token(
        access_token=_make_jwt("dev-user", expires_in_s=3600, scope="ws:read"),
        token_type="bearer",
        expires_in=3600,
    )
