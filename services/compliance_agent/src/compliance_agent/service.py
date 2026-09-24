"""Compliance Agent main service logic."""
import json
import re
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import asyncpg
import structlog
from redis.asyncio import Redis

from compliance_agent.config import settings
from compliance_agent.models import (
    ComplianceAuditRecord,
    ComplianceCheckResult,
    ComplianceStatus,
    DecisionForReview,
    Violation,
    ViolationType,
)

logger = structlog.get_logger(__name__)


class ComplianceAgentService:
    """Service for compliance review of decisions before delivery."""

    def __init__(self) -> None:
        """Initialize compliance agent service."""
        self._redis: Redis | None = None
        self._pool: asyncpg.Pool | None = None
        self._forbidden_regex = [re.compile(p, re.IGNORECASE) for p in settings.forbidden_patterns]

    async def initialize(self) -> None:
        """Initialize Redis and database connections."""
        self._redis = Redis.from_url(settings.redis_url, decode_responses=True)
        self._pool = await asyncpg.create_pool(settings.database_url, min_size=2, max_size=10)

    async def close(self) -> None:
        """Close all connections."""
        if self._redis:
            await self._redis.close()
        if self._pool:
            await self._pool.close()

    def _scan_forbidden_language(self, text: str) -> list[Violation]:
        """Scan text for forbidden language patterns."""
        violations = []
        for pattern in self._forbidden_regex:
            match = pattern.search(text)
            if match:
                violations.append(
                    Violation(
                        type=ViolationType.FORBIDDEN_LANGUAGE,
                        field="supervisor_reasoning",
                        message=f"Forbidden language detected: '{match.group()}'",
                        severity="ERROR",
                    )
                )
        return violations

    def _validate_disclaimer(self, text: str) -> list[Violation]:
        """Validate that disclaimer is present."""
        violations = []
        if settings.disclaimer_tr not in text:
            violations.append(
                Violation(
                    type=ViolationType.MISSING_DISCLAIMER,
                    field="disclaimer_tr",
                    message="Required disclaimer not found in output",
                    severity="ERROR",
                )
            )
        return violations

    def _validate_evidence_citations(self, evidence: list[dict[str, Any]]) -> list[Violation]:
        """Validate that all evidence items have source_url."""
        violations = []
        for i, e in enumerate(evidence):
            if not e.get("source_id"):
                violations.append(
                    Violation(
                        type=ViolationType.MISSING_EVIDENCE_CITATION,
                        field=f"evidence[{i}].source_id",
                        message=f"Evidence item {i} missing source_id",
                        severity="ERROR",
                    )
                )
        return violations

    def _validate_confidence(self, confidence: float) -> list[Violation]:
        """Validate confidence is in [0, 1]."""
        violations = []
        if not (0.0 <= confidence <= 1.0):
            violations.append(
                Violation(
                    type=ViolationType.INVALID_CONFIDENCE,
                    field="confidence",
                    message=f"Confidence {confidence} is outside valid range [0, 1]",
                    severity="ERROR",
                )
            )
        return violations

    def _validate_position_constraints(
        self, position_size_pct: float, max_position_pct: float = 0.25
    ) -> list[Violation]:
        """Validate position size within constraints."""
        violations = []
        if position_size_pct > max_position_pct:
            violations.append(
                Violation(
                    type=ViolationType.POSITION_CONSTRAINT_VIOLATION,
                    field="position_size_pct",
                    message=f"Position size {position_size_pct:.2%} exceeds max {max_position_pct:.2%}",
                    severity="ERROR",
                )
            )
        return violations

    async def _insert_audit_record(self, audit: ComplianceAuditRecord) -> None:
        """Insert compliance audit record into PostgreSQL."""
        if not self._pool:
            raise RuntimeError("Database pool not initialized")

        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO audit.compliance_audits
                (audit_id, check_id, decision_id, portfolio_id, ticker, action,
                 original_confidence, position_size_pct, status, violations,
                 reviewer_id, reviewed_at, notes)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                """,
                audit.audit_id,
                audit.check_id,
                audit.decision_id,
                audit.portfolio_id,
                audit.ticker,
                audit.action,
                audit.original_confidence,
                audit.position_size_pct,
                audit.status.value,
                json.dumps([v.model_dump() for v in audit.violations]),
                audit.reviewer_id,
                audit.reviewed_at,
                audit.notes,
            )

    async def _update_decision_compliance(
        self, decision_id: str, status: ComplianceStatus, reason: str | None = None
    ) -> None:
        """Update decision record with compliance status."""
        if not self._pool:
            raise RuntimeError("Database pool not initialized")

        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE decision.decisions
                SET compliance_status = $1, compliance_reason = $2
                WHERE decision_id = $3
                """,
                status.value,
                reason,
                decision_id,
            )

    async def _emit_compliance_event(
        self, decision_id: str, status: ComplianceStatus, violations: list[Violation]
    ) -> None:
        """Emit compliance event to Redis."""
        if not self._redis:
            raise RuntimeError("Redis not initialized")

        event = {
            "event_type": "compliance.checked",
            "check_id": str(uuid4()),
            "decision_id": decision_id,
            "status": status.value,
            "violations": [v.message for v in violations],
            "timestamp": datetime.now(UTC).isoformat(),
        }
        channel = "compliance.approved" if status == ComplianceStatus.APPROVED else "compliance.blocked"
        await self._redis.publish(channel, json.dumps(event))

    async def review_decision(self, decision: DecisionForReview) -> ComplianceCheckResult:
        """
        Perform compliance review on a decision.

        Checks:
        1. Forbidden language in supervisor reasoning
        2. Disclaimer presence
        3. Evidence citations
        4. Confidence range
        5. Position constraints

        Returns APPROVED if all checks pass, BLOCKED otherwise.
        """
        check_id = str(uuid4())
        violations: list[Violation] = []

        # Collect all text to scan for forbidden language
        all_text = f"{decision.supervisor_reasoning} {decision.action} {decision.ticker}"

        # Check 1: Forbidden language
        violations.extend(self._scan_forbidden_language(all_text))

        # Check 2: Disclaimer
        violations.extend(self._validate_disclaimer(decision.disclaimer_tr))

        # Check 3: Evidence citations
        violations.extend(self._validate_evidence_citations(decision.evidence))

        # Check 4: Confidence range
        violations.extend(self._validate_confidence(decision.confidence))

        # Check 5: Position constraints
        violations.extend(self._validate_position_constraints(decision.position_size_pct))

        # Determine status
        status = ComplianceStatus.APPROVED if not violations else ComplianceStatus.BLOCKED

        # Build result
        result = ComplianceCheckResult(
            check_id=check_id,
            decision_id=decision.decision_id,
            status=status,
            violations=violations,
        )

        # Create audit record
        audit = ComplianceAuditRecord(
            check_id=check_id,
            decision_id=decision.decision_id,
            portfolio_id=decision.portfolio_id,
            ticker=decision.ticker,
            action=decision.action,
            original_confidence=decision.confidence,
            position_size_pct=decision.position_size_pct,
            status=status,
            violations=violations,
        )

        # Persist audit record
        try:
            await self._insert_audit_record(audit)
        except Exception as e:
            logger.error("audit_insert_failed", check_id=check_id, error=str(e))

        # Update decision compliance status
        try:
            reason = "; ".join(v.message for v in violations) if violations else None
            await self._update_decision_compliance(decision.decision_id, status, reason)
        except Exception as e:
            logger.error("decision_update_failed", decision_id=decision.decision_id, error=str(e))

        # Emit event
        try:
            await self._emit_compliance_event(decision.decision_id, status, violations)
        except Exception as e:
            logger.error("event_emit_failed", check_id=check_id, error=str(e))

        logger.info(
            "compliance_review_complete",
            decision_id=decision.decision_id,
            status=status.value,
            violation_count=len(violations),
        )

        return result

    async def run(self) -> None:
        """Run the compliance agent as a background service."""
        logger.info("compliance_agent_service_started")
        while True:
            # Listen for decisions to review
            if self._redis is None:
                await self.initialize()

            try:
                pubsub = self._redis.pubsub()
                await pubsub.subscribe("decision.pending_compliance")

                async for message in pubsub.listen():
                    if message["type"] != "message":
                        continue

                    try:
                        data = json.loads(message["data"])
                        if data.get("event_type") == "decision.pending_compliance":
                            decision = DecisionForReview(**data)
                            await self.review_decision(decision)
                    except Exception as e:
                        logger.error("decision_review_failed", error=str(e))
            except Exception as e:
                logger.error("compliance_listener_failed", error=str(e))

            import asyncio
            await asyncio.sleep(1)
