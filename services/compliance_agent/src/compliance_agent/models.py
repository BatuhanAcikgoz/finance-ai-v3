"""Compliance Agent Pydantic models."""
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class ComplianceStatus(str, Enum):
    """Compliance check result."""

    APPROVED = "APPROVED"
    BLOCKED = "BLOCKED"


class ViolationType(str, Enum):
    """Type of compliance violation."""

    FORBIDDEN_LANGUAGE = "FORBIDDEN_LANGUAGE"
    MISSING_DISCLAIMER = "MISSING_DISCLAIMER"
    MISSING_EVIDENCE_CITATION = "MISSING_EVIDENCE_CITATION"
    INVALID_CONFIDENCE = "INVALID_CONFIDENCE"
    POSITION_CONSTRAINT_VIOLATION = "POSITION_CONSTRAINT_VIOLATION"
    UNCLEAR_PAYLOAD = "UNCLEAR_PAYLOAD"


class Violation(BaseModel):
    """Single compliance violation."""

    type: ViolationType
    field: str | None = None
    message: str
    severity: str = "ERROR"


class ComplianceCheckResult(BaseModel):
    """Result of compliance check."""

    check_id: str = Field(default_factory=lambda: str(uuid4()))
    decision_id: str
    status: ComplianceStatus
    violations: list[Violation] = Field(default_factory=list)
    checked_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    agent_version: str = "v1"


class ComplianceAuditRecord(BaseModel):
    """Audit record for compliance checks."""

    audit_id: str = Field(default_factory=lambda: str(uuid4()))
    check_id: str
    decision_id: str
    portfolio_id: str
    ticker: str
    action: str
    original_confidence: float
    position_size_pct: float
    status: ComplianceStatus
    violations: list[Violation]
    reviewer_id: str | None = None  # For human review
    reviewed_at: str | None = None
    notes: str | None = None


class DecisionForReview(BaseModel):
    """Decision record submitted for compliance review."""

    decision_id: str
    portfolio_id: str
    ticker: str
    action: str
    confidence: float
    position_size_pct: float
    evidence: list[dict[str, Any]]
    supervisor_reasoning: str
    data_completeness: str
    disclaimer_tr: str
