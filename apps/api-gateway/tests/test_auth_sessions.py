"""Auth tests — server-side session tokens backed by MySQL.

Replaces the previous X-Admin-Token / localStorage model. The new
flow is:
    POST /v1/auth/login   username + password  → Set-Cookie fasess=…
    POST /v1/auth/logout  invalidate session
    POST /v1/auth/change-password  rotate password
    GET  /v1/auth/me      whoami
    GET  /v1/auth/sessions list active sessions
"""
from datetime import datetime, timezone, timedelta
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

import db
import main as main_module


# In-memory fake DB --------------------------------------------------
class _Row(dict):
    def __getitem__(self, k):
        return dict.__getitem__(self, k)


class _FakeDB:
    def __init__(self) -> None:
        self.users: dict[str, dict[str, Any]] = {}
        self.sessions: dict[str, dict[str, Any]] = {}

    def reset(self) -> None:
        self.users.clear()
        self.sessions.clear()


_DB = _FakeDB()


def _fake_hash_password(plain: str) -> str:
    # Deterministic fake hash for tests; bcrypt.comparepw would also work
    # but slows the suite down. This fake format mirrors bcrypt's
    # `$2b$NN$<22-char-salt><31-char-hash>` shape and is good enough to
    # assert round-trip correctness via the real bcrypt helper in auth.py.
    import bcrypt
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=4)).decode()


def _make_fake_executor(db_: _FakeDB):
    async def _exec(query: str, *args: Any) -> str:
        q = " ".join(query.split())
        if "INSERT INTO admin.users" in q:
            username, password_hash = args[0], args[1]
            db_.users.setdefault(username, {
                "user_id": f"u-{username}",
                "username": username,
                "password_hash": password_hash,
                "role": "admin",
                "disabled_at": None,
            })
            return "INSERT 1"
        if "INSERT INTO admin.sessions" in q:
            user_id, token_hash, expires_at, ip_addr, user_agent = args
            sid = f"s-{len(db_.sessions)}"
            db_.sessions[sid] = {
                "session_id": sid,
                "user_id": user_id,
                "token_hash": token_hash,
                "expires_at": expires_at,
                "last_seen_at": datetime.now(timezone.utc),
                "ip_addr": ip_addr,
                "user_agent": user_agent,
            }
            return "INSERT 1"
        if "UPDATE admin.sessions SET last_seen_at" in q:
            sid = args[0]
            if sid in db_.sessions:
                db_.sessions[sid]["last_seen_at"] = datetime.now(timezone.utc)
            return "UPDATE 1"
        if "DELETE FROM admin.sessions WHERE session_id" in q:
            sid = args[0]
            db_.sessions.pop(sid, None)
            return "DELETE 1"
        if "DELETE FROM admin.sessions WHERE user_id" in q:
            uid = args[0]
            for k in list(db_.sessions.keys()):
                if db_.sessions[k]["user_id"] == uid:
                    db_.sessions.pop(k)
            return "DELETE 1"
        if "UPDATE admin.users SET password_hash" in q:
            new_hash, uid = args[0], args[1]
            for u in db_.users.values():
                if u["user_id"] == uid:
                    u["password_hash"] = new_hash
            return "UPDATE 1"
        if "UPDATE admin.users SET last_login_at" in q:
            return "UPDATE 1"
        if "SELECT password_hash FROM admin.users" in q:
            uid = args[0]
            for u in db_.users.values():
                if u["user_id"] == uid:
                    return _Row(password_hash=u["password_hash"])
            return None
        return ""
    return _exec


def _make_fake_fetchrow(db_: _FakeDB):
    async def _fr(query: str, *args: Any) -> Any:
        q = " ".join(query.split())
        if "WHERE s.token_hash" in q:
            token_hash = args[0]
            import sys
            for s in db_.sessions.values():
                if s["token_hash"] == token_hash:
                    u = next(u for u in db_.users.values() if u["user_id"] == s["user_id"])
                    return _Row(
                        session_id=s["session_id"],
                        user_id=s["user_id"],
                        username=u["username"],
                        role=u["role"],
                        disabled_at=u["disabled_at"],
                        expires_at=s["expires_at"],
                        last_seen_at=s["last_seen_at"],
                    )
            return None
        if "FROM admin.users WHERE username" in q:
            username = args[0]
            u = db_.users.get(username)
            if u is None:
                return None
            return _Row(
                user_id=u["user_id"],
                username=u["username"],
                password_hash=u["password_hash"],
                role=u["role"],
                disabled_at=u["disabled_at"],
            )
        if "SELECT password_hash FROM admin.users" in q:
            uid = args[0]
            for u in db_.users.values():
                if u["user_id"] == uid:
                    return _Row(password_hash=u["password_hash"])
            return None
        if "FROM admin.sessions WHERE user_id" in q:
            uid = args[0]
            out = []
            for s in db_.sessions.values():
                if s["user_id"] == uid:
                    out.append(_Row(
                        session_id=s["session_id"],
                        token_hash=s["token_hash"],
                        created_at=s.get("created_at", datetime.now(timezone.utc)),
                        last_seen_at=s["last_seen_at"],
                        expires_at=s["expires_at"],
                        ip_addr=s["ip_addr"],
                        user_agent=s["user_agent"],
                    ))
            return out
        return None
    return _fr


def _make_fake_fetchval(db_: _FakeDB):
    async def _fv(query: str, *args: Any) -> Any:
        q = " ".join(query.split())
        if "count(*) FROM admin.users" in q:
            return len(db_.users)
        if "password_hash FROM admin.users" in q:
            uid = args[0]
            for u in db_.users.values():
                if u["user_id"] == uid:
                    return u["password_hash"]
            return None
        return None
    return _fv


def _make_fake_fetch(db_: _FakeDB):
    async def _f(query: str, *args: Any):
        q = " ".join(query.split())
        if "FROM admin.sessions WHERE user_id" in q:
            uid = args[0]
            out = []
            for s in db_.sessions.values():
                if s["user_id"] == uid:
                    out.append(_Row(
                        session_id=s["session_id"],
                        token_hash=s["token_hash"],
                        created_at=s.get("created_at", datetime.now(timezone.utc)),
                        last_seen_at=s["last_seen_at"],
                        expires_at=s["expires_at"],
                        ip_addr=s["ip_addr"],
                        user_agent=s["user_agent"],
                    ))
            return out
        return []
    return _f


@pytest.fixture
async def auth_client(monkeypatch):
    _DB.reset()
    # Pre-seed an admin user
    _DB.users["admin"] = {
        "user_id": "u-admin",
        "username": "admin",
        "password_hash": _fake_hash_password("admin"),
        "role": "admin",
        "disabled_at": None,
    }
    monkeypatch.setattr(db, "execute", _make_fake_executor(_DB))
    monkeypatch.setattr(db, "fetchrow", _make_fake_fetchrow(_DB))
    monkeypatch.setattr(db, "fetchval", _make_fake_fetchval(_DB))
    monkeypatch.setattr(db, "fetch", _make_fake_fetch(_DB))

    async def _is_available() -> bool:
        return True
    monkeypatch.setattr(db, "is_available", _is_available)

    async def _get_pool():
        return object()  # any non-None sentinel
    monkeypatch.setattr(db, "get_pool", _get_pool)

    transport = ASGITransport(app=main_module.app)
    # cookies=None disables httpx's automatic Set-Cookie tracking — we
    # drive authentication by explicitly passing the bearer token so
    # tests stay deterministic regardless of which login produced the
    # most recent Set-Cookie.
    async with AsyncClient(transport=transport, base_url="http://test", cookies=None) as c:
        yield c


@pytest.fixture
async def auth_client_logged_in(auth_client):
    """Auth client with a session already established."""
    login = await auth_client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    auth_client.headers["Authorization"] = f"Bearer {token}"
    return auth_client


# Tests ---------------------------------------------------------------

@pytest.mark.asyncio
async def test_login_success_sets_cookie(auth_client):
    r = await auth_client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["username"] == "admin"
    assert body["role"] == "admin"
    assert "access_token" in body and body["access_token"]
    # cookie should be present
    assert "fasess" in r.cookies
    assert body["must_change_password"] is True  # default admin/admin


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(auth_client):
    r = await auth_client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "wrong"},
    )
    assert r.status_code == 401
    assert r.json()["detail"] == "invalid credentials"


@pytest.mark.asyncio
async def test_login_unknown_user_returns_401(auth_client):
    r = await auth_client.post(
        "/api/v1/auth/login",
        json={"username": "ghost", "password": "whatever"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_me_requires_session(auth_client):
    r = await auth_client.get("/api/v1/auth/me")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_me_with_cookie_returns_identity(auth_client):
    login = await auth_client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    assert login.status_code == 200
    me = await auth_client.get("/api/v1/auth/me")
    assert me.status_code == 200
    body = me.json()
    assert body["username"] == "admin"
    assert body["role"] == "admin"
    assert body["must_change_password"] is True


@pytest.mark.asyncio
async def test_me_with_bearer_token_works(auth_client):
    login = await auth_client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    token = login.json()["access_token"]
    r = await auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["username"] == "admin"


@pytest.mark.asyncio
async def test_logout_invalidates_session(auth_client):
    # Simulate two logins. We snapshot the bearer tokens from each
    # login response so we can target a specific session for logout
    # (httpx's automatic Set-Cookie handling would otherwise make the
    # second login's cookie win on every later request, which is fine
    # for the real browser flow but unhelpful for unit tests).
    r1 = await auth_client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    token1 = r1.json()["access_token"]
    # Forget the cookie the first login just set, so the second login
    # gets a fresh, untangled cookie jar.
    auth_client.cookies.clear()
    r2 = await auth_client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    token2 = r2.json()["access_token"]
    auth_client.cookies.clear()
    assert token1 != token2

    out = await auth_client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert out.status_code == 204
    # First token now invalid; second still works.
    me1 = await auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert me1.status_code == 401
    me2 = await auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert me2.status_code == 200


@pytest.mark.asyncio
async def test_logout_all_kills_every_session(auth_client):
    # Two separate logins (cookies are scoped to AsyncClient, so simulate
    # by clearing the cookie between logins).
    r1 = await auth_client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    token1 = r1.json()["access_token"]
    r2 = await auth_client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    token2 = r2.json()["access_token"]
    assert token1 != token2

    out = await auth_client.post(
        "/api/v1/auth/logout-all",
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert out.status_code == 204

    # Both tokens should now be invalid.
    for tok in (token1, token2):
        me = await auth_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {tok}"},
        )
        assert me.status_code == 401


@pytest.mark.asyncio
async def test_sessions_lists_active(auth_client):
    r1 = await auth_client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    token = r1.json()["access_token"]
    r = await auth_client.get(
        "/api/v1/auth/sessions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["this_device"] is True
    assert body[0]["ip_addr"] is not None


@pytest.mark.asyncio
async def test_change_password_invalidates_all_sessions(auth_client):
    r1 = await auth_client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    token = r1.json()["access_token"]
    out = await auth_client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "admin", "new_password": "newpw123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert out.status_code == 204
    # Old token should be invalidated.
    me = await auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me.status_code == 401
    # New password should now work.
    r2 = await auth_client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "newpw123"},
    )
    assert r2.status_code == 200
    # And must_change_password should now be False.
    assert r2.json()["must_change_password"] is False


@pytest.mark.asyncio
async def test_change_password_wrong_current_returns_401(auth_client):
    r1 = await auth_client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    token = r1.json()["access_token"]
    out = await auth_client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "WRONG", "new_password": "newpw123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert out.status_code == 401


@pytest.mark.asyncio
async def test_change_password_too_short_returns_400(auth_client):
    r1 = await auth_client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    token = r1.json()["access_token"]
    out = await auth_client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "admin", "new_password": "abc"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert out.status_code == 400


@pytest.mark.asyncio
async def test_session_expiry_rejected(auth_client):
    # Manually expire the session row.
    login = await auth_client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    token = login.json()["access_token"]
    # Patch expiry to the past.
    for s in _DB.sessions.values():
        s["expires_at"] = datetime.now(timezone.utc) - timedelta(days=1)
    me = await auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me.status_code == 401


@pytest.mark.asyncio
async def test_disabled_user_cannot_login(auth_client):
    _DB.users["admin"]["disabled_at"] = datetime.now(timezone.utc)
    r = await auth_client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    assert r.status_code == 403
