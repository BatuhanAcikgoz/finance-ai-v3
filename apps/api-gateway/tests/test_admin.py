"""Admin endpoint tests — uses monkeypatched db helpers for in-memory state."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

import db
import main as main_module


ADMIN_TOKEN = "dev_admin_token_change_me"
HEADERS = {"X-Admin-Token": ADMIN_TOKEN}


# ---------------------------------------------------------------------------
# In-memory fake DB.
#
# Replaces asyncpg-backed db.fetch / db.fetchrow / db.execute with simple
# versions that read/write Python lists. Keeps the suite self-contained.
# ---------------------------------------------------------------------------


class _Row(dict):
    """dict that supports both indexing and .get(), like asyncpg.Record."""

    def __getitem__(self, k):
        return dict.__getitem__(self, k)


class _FakeDB:
    def __init__(self):
        self.llm_keys: list[_Row] = []
        self.audit_log: list[_Row] = []


def _make_fake_executor(fake: _FakeDB):
    """Build a fake ``db.execute`` that mimics asyncpg status strings."""
    async def fake_execute(query: str, *args):
        q = " ".join(query.split())
        if "INSERT INTO admin.llm_keys" in q:
            fake.llm_keys.append(_Row({
                "key_id": args[0],
                "provider": args[1],
                "model": args[2],
                "label": args[3],
                "api_key": args[4],
                "masked_key": args[5],
                "status": "active",
                "cost_usd_total": Decimal("0"),
                "calls_total": 0,
                "last_used_at": None,
                "last_error": None,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }))
            return "INSERT 0 1"
        if "INSERT INTO admin.audit_log" in q:
            import json as _json
            summary = args[4]
            if isinstance(summary, str):
                try:
                    summary = _json.loads(summary)
                except Exception:
                    pass
            fake.audit_log.append(_Row({
                "log_id": "00000000-0000-0000-0000-000000000099",
                "ts": datetime.now(timezone.utc),
                "actor": args[0],
                "action": args[1],
                "target_type": args[2],
                "target_id": args[3],
                "summary": summary,
                "ip_addr": args[5],
            }))
            return "INSERT 0 1"
        if "INSERT INTO admin.llm_key_usage" in q:
            return "INSERT 0 1"
        if "UPDATE admin.llm_keys" in q and "SET status" in q:
            # /test endpoint — args: key_uuid, status, error
            for r in fake.llm_keys:
                if str(r.get("key_id")) == str(args[0]):
                    r["status"] = args[1]
                    r["last_error"] = args[2]
                    r["updated_at"] = datetime.now(timezone.utc)
                    if r.get("last_used_at") is None:
                        r["last_used_at"] = datetime.now(timezone.utc)
                    return "UPDATE 1"
            return "UPDATE 0"
        if "UPDATE admin.llm_keys" in q and "calls_total" in q:
            # /use endpoint — args: key_uuid, cost_usd
            for r in fake.llm_keys:
                if str(r.get("key_id")) == str(args[0]):
                    r["calls_total"] = int(r.get("calls_total") or 0) + 1
                    r["cost_usd_total"] = (
                        Decimal(str(r.get("cost_usd_total") or 0))
                        + Decimal(str(args[1]))
                    )
                    r["last_used_at"] = datetime.now(timezone.utc)
                    r["updated_at"] = datetime.now(timezone.utc)
                    return "UPDATE 1"
            return "UPDATE 0"
        if "UPDATE admin.llm_keys" in q:
            # PATCH — last arg is key_uuid, preceding args in SET order.
            key_uuid = args[-1]
            set_part = q.split("SET", 1)[1].split("WHERE", 1)[0]
            updates: dict[str, Any] = {}
            arg_idx = 0
            for chunk in set_part.split(","):
                chunk = chunk.strip()
                if "=" not in chunk or "updated_at" in chunk:
                    continue
                arg_idx += 1
                lhs = chunk.split("=", 1)[0].strip()
                updates[lhs] = args[arg_idx - 1]
            for r in fake.llm_keys:
                if str(r.get("key_id")) == str(key_uuid):
                    for k, v in updates.items():
                        r[k] = v
                    r["updated_at"] = datetime.now(timezone.utc)
                    return "UPDATE 1"
            return "UPDATE 0"
        if "DELETE FROM admin.llm_keys" in q:
            for i, r in enumerate(fake.llm_keys):
                if str(r.get("key_id")) == str(args[0]):
                    del fake.llm_keys[i]
                    return "DELETE 1"
            return "DELETE 0"
        return ""
    return fake_execute


def _make_fake_fetchrow(fake: _FakeDB):
    async def fake_fetchrow(query: str, *args):
        q = " ".join(query.split())
        if "FROM admin.llm_keys" in q and args:
            for r in fake.llm_keys:
                if str(r.get("key_id")) == str(args[0]):
                    return r
        return None
    return fake_fetchrow


def _make_fake_fetch(fake: _FakeDB):
    async def fake_fetch(query: str, *args):
        q = " ".join(query.split())
        if "FROM admin.llm_keys" in q:
            return sorted(
                fake.llm_keys,
                key=lambda r: r.get("created_at") or datetime.min,
                reverse=True,
            )
        if "FROM admin.audit_log" in q:
            return sorted(
                fake.audit_log,
                key=lambda r: r.get("ts") or datetime.min,
                reverse=True,
            )
        return []
    return fake_fetch


@pytest.fixture
def fake_db() -> _FakeDB:
    return _FakeDB()


@pytest.fixture
async def client(fake_db, monkeypatch):
    """ASGI client with DB helpers wired to an in-memory store."""
    monkeypatch.setattr(db, "fetch", _make_fake_fetch(fake_db))
    monkeypatch.setattr(db, "fetchrow", _make_fake_fetchrow(fake_db))
    monkeypatch.setattr(db, "execute", _make_fake_executor(fake_db))

    async def is_available() -> bool:
        return True
    monkeypatch.setattr(db, "is_available", is_available)

    transport = ASGITransport(app=main_module.app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_list_keys_returns_empty_initially(client):
    r = await client.get("/v1/admin/llm/keys", headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body == {"items": [], "count": 0}


async def test_post_key_returns_201_and_masked_key(client):
    r = await client.post(
        "/v1/admin/llm/keys",
        headers=HEADERS,
        json={
            "provider": "openai",
            "model": "gpt-4o-mini",
            "api_key": "sk-supersecret1234abcd",
            "label": "primary",
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert "key_id" in body
    masked = body["masked_key"]
    # Spec: masked_key must end with the last 4 chars of the supplied key.
    assert masked.endswith("abcd"), f"masked_key={masked!r} should end with 'abcd'"
    assert body["provider"] == "openai"
    assert body["model"] == "gpt-4o-mini"
    # API must NOT echo the plaintext api_key.
    assert "api_key" not in body
    assert "supersecret" not in masked


async def test_patch_key_updates_label(client):
    create = await client.post(
        "/v1/admin/llm/keys",
        headers=HEADERS,
        json={
            "provider": "minimax",
            "model": "MiniMax-M3",
            "api_key": "sk-MiniMaxXYZtest-key-4321",
            "label": "before",
        },
    )
    assert create.status_code == 201
    key_id = create.json()["key_id"]

    patch_resp = await client.patch(
        f"/v1/admin/llm/keys/{key_id}",
        headers=HEADERS,
        json={"label": "after"},
    )
    assert patch_resp.status_code == 200, patch_resp.text
    body = patch_resp.json()
    assert body["label"] == "after"
    assert body["provider"] == "minimax"
    assert body["model"] == "MiniMax-M3"


async def test_delete_key_removes_it(client):
    create = await client.post(
        "/v1/admin/llm/keys",
        headers=HEADERS,
        json={
            "provider": "anthropic",
            "model": "claude-3-5-haiku-20241022",
            "api_key": "sk-ant-test1234zzzz",
            "label": "to-delete",
        },
    )
    assert create.status_code == 201
    key_id = create.json()["key_id"]

    delete = await client.delete(
        f"/v1/admin/llm/keys/{key_id}", headers=HEADERS,
    )
    assert delete.status_code == 204, delete.text

    listing = await client.get("/v1/admin/llm/keys", headers=HEADERS)
    assert listing.status_code == 200
    assert listing.json() == {"items": [], "count": 0}


async def test_providers_returns_six_entries(client):
    r = await client.get("/v1/admin/llm/providers", headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 6
    names = {p["name"] for p in body["items"]}
    assert names == {"openai", "anthropic", "minimax", "deepseek", "ollama", "custom"}
    # minimax is required to be present with the documented base URL.
    minimax = next(p for p in body["items"] if p["name"] == "minimax")
    assert minimax["base_url"] == "https://api.MiniMax.chat/v1"
    assert minimax["default_model"] == "MiniMax-M3"
    assert minimax["requires_key"] is True


async def test_missing_admin_token_returns_401(client):
    # No header at all → 401.
    r = await client.get("/v1/admin/llm/keys")
    assert r.status_code == 401
    # Wrong header → 401.
    r = await client.get(
        "/v1/admin/llm/keys",
        headers={"X-Admin-Token": "not-the-right-token"},
    )
    assert r.status_code == 401
    # Every admin endpoint should be guarded.
    for path in (
        "/v1/admin/llm/providers",
        "/v1/admin/system",
        "/v1/admin/audit-log",
    ):
        r = await client.get(path)
        assert r.status_code == 401, f"{path} allowed unauthenticated access"