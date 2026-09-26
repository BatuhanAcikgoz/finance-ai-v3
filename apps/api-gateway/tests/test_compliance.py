"""Tests for the compliance agent (issue #2 / FR-091)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(ROOT))

from services.compliance import (  # noqa: E402
    DEFAULT_DISCLAIMER,
    DEFAULT_APPROVED_UNIVERSE,
    review,
)


def _dec(**overrides):
    base = {
        "ticker": "THYAO",
        "action": "BUY",
        "confidence": 0.65,
        "position_size_pct": 0.08,
    }
    base.update(overrides)
    return base


def test_approved_buy_in_universe():
    r = review(_dec())
    assert r.status == "APPROVED"
    assert r.disclaimer_text == DEFAULT_DISCLAIMER
    assert any("auto_approved" in n for n in r.notes)


def test_blocked_ticker_outside_universe():
    r = review(_dec(ticker="FOOBAR"))
    assert r.status == "BLOCKED"
    assert any("universe_violation" in n for n in r.notes)


def test_blocked_position_size():
    r = review(_dec(position_size_pct=0.25))
    assert r.status == "BLOCKED"
    assert any("position_size_violation" in n for n in r.notes)


def test_low_confidence_pending():
    r = review(_dec(confidence=0.30))
    assert r.status == "PENDING"
    assert any("low_confidence" in n for n in r.notes)


def test_insufficient_evidence_pending():
    r = review(_dec(action="INSUFFICIENT_EVIDENCE", confidence=0.0))
    assert r.status == "PENDING"
    assert any("insufficient_evidence" in n for n in r.notes)


def test_hold_action_with_low_confidence_approved():
    # HOLD never triggers low_confidence PENDING.
    r = review(_dec(action="HOLD", confidence=0.20))
    assert r.status == "APPROVED"


def test_disclaimer_text_is_non_empty():
    assert DEFAULT_DISCLAIMER
    assert "yatırım tavsiyesi değildir" in DEFAULT_DISCLAIMER
    assert "not investment advice" in DEFAULT_DISCLAIMER


def test_approved_universe_has_seeded_tickers():
    assert "THYAO" in DEFAULT_APPROVED_UNIVERSE
    assert "AKBNK" in DEFAULT_APPROVED_UNIVERSE
