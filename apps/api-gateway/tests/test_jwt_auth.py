"""Tests for the JWT + WS auth helpers (issue #5 / NFR-002)."""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(ROOT))

from routes.auth import JWT_ALGORITHM, _make_jwt, decode_jwt  # noqa: E402


def test_make_jwt_round_trip():
    token = _make_jwt("alice", expires_in_s=60)
    claims = decode_jwt(token)
    assert claims is not None
    assert claims["sub"] == "alice"
    assert claims["exp"] > int(time.time())
    assert claims["iat"] <= int(time.time())


def test_decode_jwt_invalid_returns_none():
    assert decode_jwt("not-a-token") is None
    assert decode_jwt("") is None


def test_decode_jwt_wrong_secret_returns_none():
    """A token signed with a different secret must not validate."""
    import jose.jwt as _jwt
    bad = _jwt.encode({"sub": "x", "exp": int(time.time()) + 60},
                       "different_secret", algorithm=JWT_ALGORITHM)
    assert decode_jwt(bad) is None


def test_decode_jwt_expired_returns_none():
    token = _make_jwt("alice", expires_in_s=-1)
    assert decode_jwt(token) is None


def test_jwt_payload_includes_extra_claims():
    token = _make_jwt("bob", scope="ws:read", role="dev")
    claims = decode_jwt(token)
    assert claims["scope"] == "ws:read"
    assert claims["role"] == "dev"
