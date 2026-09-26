"""Compliance agent (issue #2 / FR-091).

Rule-based compliance review for every decision. Runs synchronously inside
the synthesize endpoint and inside the live decision loop. No LLM calls —
just deterministic policy checks against the user's settings.

Returns a result with:
  - status: 'APPROVED' | 'BLOCKED' | 'PENDING'
  - notes: list[str] of human-readable violation / approval reasons
  - disclaimer_text: the canonical disclaimer text attached to every decision
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# Canonical disclaimer text (Turkish first, English in parens per spec 2.3).
DEFAULT_DISCLAIMER = (
    "Bu rapor yatırım tavsiyesi değildir. / This report is not investment advice. "
    "Yatırım kararlarınızı kendi araştırmanıza ve/veya profesyonel danışmanlığa dayandırın. "
    "/ Base investment decisions on your own research and/or professional advice."
)


@dataclass
class ComplianceResult:
    status: str  # 'APPROVED' | 'BLOCKED' | 'PENDING'
    notes: list[str] = field(default_factory=list)
    disclaimer_text: str = DEFAULT_DISCLAIMER

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "notes": list(self.notes),
            "disclaimer_text": self.disclaimer_text,
        }


# Default universe of approved tickers for BIST (matches the 10 we seed in dev).
DEFAULT_APPROVED_UNIVERSE = {
    "THYAO", "GARAN", "AKBNK", "ISCTR", "KCHOL",
    "EREGL", "TUPRS", "BIMAS", "ASELS", "KRDMD",
    # Plus a few extras from later seeds:
    "SISE", "SAHOL",
}


def _max_position_pct() -> float:
    try:
        return float(os.getenv("RISK_MAX_POSITION_PCT", "0.10"))
    except (TypeError, ValueError):
        return 0.10


def _approved_universe() -> set[str]:
    env = os.getenv("APPROVED_TICKER_UNIVERSE")
    if env:
        return {t.strip().upper() for t in env.split(",") if t.strip()}
    return DEFAULT_APPROVED_UNIVERSE


def review(decision: dict[str, Any]) -> ComplianceResult:
    """Run all compliance checks against a decision dict.

    Decision dict shape (matches what we insert into decision.decisions):
      {ticker, action, confidence, position_size_pct, evidence, ...}
    """
    notes: list[str] = []
    status = "APPROVED"

    ticker = str(decision.get("ticker", "")).upper()
    action = str(decision.get("action", "HOLD")).upper()
    try:
        position_pct = float(decision.get("position_size_pct") or 0.0)
    except (TypeError, ValueError):
        position_pct = 0.0
    try:
        confidence = float(decision.get("confidence") or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0

    # 1. Universe check — ticker must be in the approved universe for BUY.
    universe = _approved_universe()
    if action == "BUY" and ticker not in universe:
        notes.append(
            f"universe_violation: ticker {ticker!r} not in approved universe"
        )
        status = "BLOCKED"

    # 2. Position-size cap — anything over the policy max is blocked.
    max_pos = _max_position_pct()
    if position_pct > max_pos:
        notes.append(
            f"position_size_violation: {position_pct:.4f} > {max_pos:.4f} (policy cap)"
        )
        status = "BLOCKED"

    # 3. Low-confidence BUY/SELL — downgrade to PENDING (human review).
    if action in {"BUY", "SELL"} and confidence < 0.40:
        notes.append(
            f"low_confidence: {confidence:.3f} < 0.40 (requires supervisor review)"
        )
        if status != "BLOCKED":
            status = "PENDING"

    # 4. INSUFFICIENT_EVIDENCE always stays PENDING.
    if action == "INSUFFICIENT_EVIDENCE":
        notes.append("insufficient_evidence: requires manual review")
        status = "PENDING"

    # Default — approved with no notes.
    if not notes:
        notes.append("auto_approved: all checks passed")

    return ComplianceResult(
        status=status,
        notes=notes,
        disclaimer_text=DEFAULT_DISCLAIMER,
    )


__all__ = [
    "ComplianceResult",
    "DEFAULT_DISCLAIMER",
    "DEFAULT_APPROVED_UNIVERSE",
    "review",
]
