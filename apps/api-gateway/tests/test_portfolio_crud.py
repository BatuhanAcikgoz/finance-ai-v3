"""Tests for the multi-portfolio CRUD endpoints (issue #4 / FR-046)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(ROOT))

import uuid  # noqa: E402

import db  # noqa: E402


def _portfolio_payload(name: str = "Test"):
    return {"name": name, "base_currency": "TRY"}


async def test_create_list_delete_portfolio():
    """Round-trip: create -> list shows it -> delete -> list no longer shows it."""
    name = f"tmp-{uuid.uuid4().hex[:6]}"
    create = await db.fetchrow(
        """
        INSERT INTO portfolio.portfolios (portfolio_id, name, base_currency, created_at, updated_at)
        VALUES (gen_random_uuid(), $1, 'TRY', NOW(), NOW())
        RETURNING portfolio_id, name
        """,
        name,
    )
    assert create is not None
    pid = create["portfolio_id"]

    listed = await db.fetch(
        "SELECT name FROM portfolio.portfolios WHERE portfolio_id = $1",
        pid,
    )
    assert any(r["name"] == name for r in listed)

    await db.execute(
        "DELETE FROM portfolio.holdings WHERE portfolio_id = $1",
        pid,
    )
    await db.execute(
        "DELETE FROM portfolio.portfolios WHERE portfolio_id = $1",
        pid,
    )

    after = await db.fetch(
        "SELECT name FROM portfolio.portfolios WHERE portfolio_id = $1",
        pid,
    )
    assert after == []


async def test_patch_portfolio_name():
    """PATCH updates only the fields provided."""
    name = f"pat-{uuid.uuid4().hex[:6]}"
    row = await db.fetchrow(
        """
        INSERT INTO portfolio.portfolios (portfolio_id, name, base_currency, created_at, updated_at)
        VALUES (gen_random_uuid(), $1, 'TRY', NOW(), NOW())
        RETURNING portfolio_id
        """,
        name,
    )
    pid = row["portfolio_id"]
    try:
        await db.execute(
            "UPDATE portfolio.portfolios SET name = $1, updated_at = NOW() "
            "WHERE portfolio_id = $2",
            "Renamed",
            pid,
        )
        updated = await db.fetchrow(
            "SELECT name, base_currency FROM portfolio.portfolios WHERE portfolio_id = $1",
            pid,
        )
        assert updated["name"] == "Renamed"
        assert updated["base_currency"] == "TRY"
    finally:
        await db.execute(
            "DELETE FROM portfolio.holdings WHERE portfolio_id = $1",
            pid,
        )
        await db.execute(
            "DELETE FROM portfolio.portfolios WHERE portfolio_id = $1",
            pid,
        )
