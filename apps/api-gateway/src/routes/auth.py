"""Auth endpoints — server-side session tokens backed by MySQL.

Replaces the previous X-Admin-Token / localStorage pair:

  POST /v1/auth/login     username + password  →  Set-Cookie + body token
  POST /v1/auth/logout    invalidate the current session
  POST /v1/auth/logout-all  sign out everywhere
  GET  /v1/auth/me        whoami (session-only)
  GET  /v1/auth/sessions  list active sessions
  POST /v1/auth/change-password  set a new password (auth-required)

Sessions are 30-day rotating tokens. The cleartext token is returned once
to the client; only the SHA-256 hash is stored in the DB. bcrypt is used
for password hashing (cost = 12 by default).

Default dev credentials: admin / admin (seeded on first boot if the
admin.users table is empty).
"""
from __future__ import annotations

import hashlib
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel

import bcrypt

import db

router = APIRouter()
logger = logging.getLogger(__name__)


SESSION_TTL_DAYS = int(os.getenv("AUTH_SESSION_TTL_DAYS", "30"))
BCRYPT_ROUNDS = int(os.getenv("BCRYPT_ROUNDS", "12"))


def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode()


def _check_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def _hash_token(tok: str) -> str:
    return hashlib.sha256(tok.encode("utf-8")).hexdigest()


def _new_token() -> str:
    return secrets.token_urlsafe(32)


# -- request / response models ----------------------------------------------

class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    user_id: str
    username: str
    role: str
    access_token: str
    expires_at: str
    must_change_password: bool = False


class WhoAmI(BaseModel):
    user_id: str
    username: str
    role: str
    must_change_password: bool = False
    expires_at: Optional[str] = None


class SessionInfo(BaseModel):
    session_id: str
    created_at: str
    last_seen_at: str
    expires_at: str
    ip_addr: Optional[str] = None
    user_agent: Optional[str] = None
    this_device: bool = False


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


# -- bootstrapping -----------------------------------------------------------

async def ensure_default_admin() -> None:
    """Seed an ``admin / admin`` user on first boot if the table is empty."""
    pool = await db.get_pool()
    if pool is None:
        return
    try:
        n = await db.fetchval("SELECT count(*) FROM admin.users")
        if n and n > 0:
            return
        await db.execute(
            "INSERT INTO admin.users (username, password_hash, role) "
            "VALUES ($1, $2, 'admin')",
            "admin",
            _hash_password("admin"),
        )
        logger.warning(
            "auth.bootstrap: seeded default admin/admin account — "
            "rotate the password before exposing the stack."
        )
    except Exception as exc:
        logger.warning("auth.bootstrap failed: %s", exc)


# -- session lookup ---------------------------------------------------------

async def _session_from_token(token: str) -> Optional[dict]:
    if not token:
        return None
    h = _hash_token(token)
    return await db.fetchrow(
        """
        SELECT s.session_id, s.user_id, s.expires_at, s.last_seen_at,
               u.username, u.role, u.disabled_at
        FROM admin.sessions s
        JOIN admin.users u ON u.user_id = s.user_id
        WHERE s.token_hash = $1
        """,
        h,
    )


async def _current_session(
    request: Request,
    authorization: Optional[str] = Header(default=None),
) -> Optional[dict]:
    """Resolve the caller's session, or ``None`` if no valid session.

    Used both as a real auth gate (when the caller wants 401 if no session
    exists) and as a soft probe inside ``_require_admin`` (where a missing
    session should fall through to the legacy token path instead of
    raising). Endpoints that need a hard 401 should call this directly.
    """
    token = None
    cookie_token = request.cookies.get("fasess")
    if cookie_token:
        token = cookie_token
    elif authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    if not token:
        return None
    sess = await _session_from_token(token)
    if sess is None:
        return None
    if sess["disabled_at"] is not None:
        return None
    expires = sess["expires_at"]
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < datetime.now(timezone.utc):
        return None
    try:
        await db.execute(
            "UPDATE admin.sessions SET last_seen_at = now() WHERE session_id = $1",
            sess["session_id"],
        )
    except Exception:
        pass
    return dict(sess)


async def _require_session_strict(
    request: Request,
    authorization: Optional[str] = Header(default=None),
) -> dict:
    """Strict version: raises 401 if no valid session (used by /v1/auth/me)."""
    sess = await _current_session(request, authorization=authorization)
    if sess is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing session cookie / Bearer token",
        )
    return sess


# -- endpoints --------------------------------------------------------------

@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest, request: Request, response: Response):
    """Username + password → 30-day session token (also Set-Cookie)."""
    pool = await db.get_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="db not available")
    user = await db.fetchrow(
        "SELECT user_id, username, password_hash, role, disabled_at "
        "FROM admin.users WHERE username = $1",
        req.username.strip(),
    )
    if user is None or not _check_password(req.password, user["password_hash"]):
        # Constant-time-ish (use bcrypt on missing user to avoid leak).
        if user is None:
            _check_password(req.password,
                            "$2b$12$abcdefghijklmnopqrstuuABCDEFGHIJKLMNOPQRSTUVWXYZ012")
        raise HTTPException(status_code=401, detail="invalid credentials")
    if user["disabled_at"] is not None:
        raise HTTPException(status_code=403, detail="user disabled")

    token = _new_token()
    expires = datetime.now(timezone.utc) + timedelta(days=SESSION_TTL_DAYS)
    ip = request.client.host if request.client else None
    ua = (request.headers.get("user-agent") or "")[:255]
    await db.execute(
        """
        INSERT INTO admin.sessions
            (user_id, token_hash, expires_at, ip_addr, user_agent)
        VALUES ($1, $2, $3, $4, $5)
        """,
        user["user_id"],
        _hash_token(token),
        expires,
        ip,
        ua,
    )
    await db.execute(
        "UPDATE admin.users SET last_login_at = now() WHERE user_id = $1",
        user["user_id"],
    )

    response.set_cookie(
        key="fasess",
        value=token,
        max_age=SESSION_TTL_DAYS * 24 * 3600,
        httponly=True,
        samesite="lax",
        path="/",
        secure=request.url.scheme == "https",
    )
    must_change = (req.username == "admin" and req.password == "admin")
    return LoginResponse(
        user_id=str(user["user_id"]),
        username=user["username"],
        role=user["role"],
        access_token=token,
        expires_at=expires.isoformat(),
        must_change_password=must_change,
    )


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response,
                 sess: dict = Depends(_require_session_strict)):
    """Invalidate the current session and clear the cookie."""
    await db.execute(
        "DELETE FROM admin.sessions WHERE session_id = $1",
        sess["session_id"],
    )
    response.delete_cookie("fasess", path="/")
    return Response(status_code=204)


@router.post("/logout-all", status_code=204)
async def logout_all(request: Request, response: Response,
                     sess: dict = Depends(_require_session_strict)):
    await db.execute(
        "DELETE FROM admin.sessions WHERE user_id = $1",
        sess["user_id"],
    )
    response.delete_cookie("fasess", path="/")
    return Response(status_code=204)


@router.get("/me", response_model=WhoAmI)
async def me(request: Request,
             sess: Optional[dict] = Depends(_require_session_strict)):
    if sess is None:
        raise HTTPException(status_code=401, detail="not signed in")
    must_change = False
    pool = await db.get_pool()
    if pool is not None:
        must_change_row = await db.fetchval(
            "SELECT password_hash FROM admin.users WHERE user_id = $1",
            sess["user_id"],
        )
        if must_change_row:
            # Cheap heuristic: still default admin/admin hash means it must rotate.
            try:
                must_change = bcrypt.checkpw(b"admin", must_change_row.encode())
            except Exception:
                must_change = False
    return WhoAmI(
        user_id=str(sess["user_id"]),
        username=sess["username"],
        role=sess["role"],
        must_change_password=must_change,
        expires_at=sess["expires_at"].isoformat() if sess["expires_at"] else None,
    )


@router.get("/sessions", response_model=list[SessionInfo])
async def list_sessions(request: Request,
                        sess: dict = Depends(_require_session_strict)):
    cookie_token = request.cookies.get("fasess", "")
    cur_token_hash = _hash_token(cookie_token) if cookie_token else None
    rows = await db.fetch(
        """
        SELECT session_id, created_at, last_seen_at, expires_at, ip_addr, user_agent, token_hash
        FROM admin.sessions
        WHERE user_id = $1
        ORDER BY last_seen_at DESC
        """,
        sess["user_id"],
    )
    out = []
    for r in rows:
        is_this = bool(cur_token_hash and r["token_hash"] == cur_token_hash)
        out.append(SessionInfo(
            session_id=str(r["session_id"]),
            created_at=r["created_at"].isoformat(),
            last_seen_at=r["last_seen_at"].isoformat(),
            expires_at=r["expires_at"].isoformat(),
            ip_addr=r["ip_addr"],
            user_agent=r["user_agent"],
            this_device=is_this,
        ))
    return out


@router.post("/change-password", status_code=204)
async def change_password(req: ChangePasswordRequest,
                          request: Request,
                          response: Response,
                          sess: dict = Depends(_require_session_strict)):
    """Change own password; invalidates every other session as a side effect."""
    pool = await db.get_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="db not available")
    row = await db.fetchrow(
        "SELECT password_hash FROM admin.users WHERE user_id = $1",
        sess["user_id"],
    )
    if row is None or not _check_password(req.current_password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="current password wrong")
    if len(req.new_password) < 6:
        raise HTTPException(status_code=400, detail="new password too short")
    await db.execute(
        "UPDATE admin.users SET password_hash = $1 WHERE user_id = $2",
        _hash_password(req.new_password),
        sess["user_id"],
    )
    # Sign out everywhere; current request is over.
    await db.execute(
        "DELETE FROM admin.sessions WHERE user_id = $1",
        sess["user_id"],
    )
    response.delete_cookie("fasess", path="/")
    return Response(status_code=204)


# -- backward compat: JWT decoder shim ------------------------------------
# Previously ws_market imported `decode_jwt` from this module. The new
# auth model is session-token based, but we keep the symbol around so the
# websocket module keeps compiling. Returns a claims dict with the same
# shape ws_market expects (subject/role/etc) or raises ValueError.
from typing import Any

async def decode_jwt(token: str) -> dict[str, Any]:
    """Deprecated: kept for backward compatibility.

    New code should resolve sessions via ``_session_from_token``. This
    shim returns a claims dict whose shape mirrors what the old JWT
    decoder produced: ``{"sub": <user_id>, "role": "admin", ...}``.
    """
    sess = await _session_from_token(token)
    if sess is None:
        raise ValueError("invalid token")
    return {
        "sub": str(sess["user_id"]),
        "username": sess["username"],
        "role": sess["role"],
    }


# ---- Backward-compatible aliases (legacy JWT tests) ----------------------
# Old code imported these symbols. The new auth is session-token based,
# but the names are kept so legacy tests / imports keep working.
JWT_ALGORITHM = "HS256"  # kept for tests / external imports
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-jwt-secret-change-me")
