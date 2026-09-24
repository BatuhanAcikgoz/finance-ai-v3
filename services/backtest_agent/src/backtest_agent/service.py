"""Backtest Agent main service logic."""
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from asyncpg import Pool, create_pool

from backtest_agent.config import settings
from backtest_agent.models import (
    BacktestReport,
    ConfidenceBucket,
    DecisionOutcome,
    StreamStats,
    WeightAdjustment,
)

logger = structlog.get_logger()


# Default evidence weights (from decision engine)
DEFAULT_WEIGHTS: dict[str, float] = {
    "TECHNICAL": 0.20,
    "FUNDAMENTAL": 0.25,
    "MACRO": 0.20,
    "NEWS": 0.10,
    "SENTIMENT": 0.15,
    "SECTOR": 0.10,
}


class BacktestAgentService:
    """Service for running weekly backtests on decision accuracy."""

    def __init__(self) -> None:
        """Initialize the backtest agent service."""
        self._pool: Pool | None = None
        self._llm_client: Any = None  # LiteLLM client placeholder

    async def initialize(self) -> None:
        """Initialize database pool and LLM client."""
        self._pool = await create_pool(
            settings.database_url,
            min_size=2,
            max_size=5,
            command_timeout=60,
        )
        # LLM client initialization would go here (LiteLLM)
        logger.info("backtest_agent_initialized", lookback_weeks=settings.lookback_weeks)

    async def close(self) -> None:
        """Close database pool."""
        if self._pool:
            self._pool.close()
            await self._pool.wait_closed()
        logger.info("backtest_agent_shutdown")

    # -------------------------------------------------------------------------
    # Data Fetching
    # -------------------------------------------------------------------------

    async def _fetch_decisions(
        self, start_date: datetime, end_date: datetime
    ) -> list[dict[str, Any]]:
        """Fetch decisions from PostgreSQL within date range."""
        query = """
            SELECT
                decision_id,
                ticker,
                action,
                confidence,
                effective_at,
                evidence,
                prompt_versions
            FROM decision.decisions
            WHERE effective_at >= $1
              AND effective_at < $2
              AND compliance_status = 'APPROVED'
            ORDER BY effective_at ASC
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, start_date, end_date)
            return [dict(row) for row in rows]

    async def _fetch_prices_at_date(
        self, ticker: str, date: datetime
    ) -> float | None:
        """Fetch closing price for ticker at specific date."""
        query = """
            SELECT close
            FROM market_data.bars
            WHERE ticker = $1
              AND timeframe = '1day'
              AND open_time >= $2
              AND open_time < $3
            ORDER BY open_time ASC
            LIMIT 1
        """
        day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, ticker, day_start, day_end)
            return row["close"] if row else None

    async def _fetch_prices_in_range(
        self, ticker: str, start: datetime, end: datetime
    ) -> list[tuple[datetime, float]]:
        """Fetch all daily closing prices for ticker in date range."""
        query = """
            SELECT open_time, close
            FROM market_data.bars
            WHERE ticker = $1
              AND timeframe = '1day'
              AND open_time >= $2
              AND open_time < $3
            ORDER BY open_time ASC
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, ticker, start, end)
            return [(row["open_time"], row["close"]) for row in rows]

    # -------------------------------------------------------------------------
    # Core Computation
    # -------------------------------------------------------------------------

    async def _compute_outcomes(
        self, decisions: list[dict[str, Any]]
    ) -> list[DecisionOutcome]:
        """Match decisions with realized price outcomes."""
        outcomes: list[DecisionOutcome] = []

        for decision in decisions:
            ticker = decision["ticker"]
            effective_at = decision["effective_at"]
            decision_time = datetime.fromisoformat(effective_at.replace("Z", "+00:00"))

            # Get price at decision time
            price_at_decision = await self._fetch_prices_at_date(ticker, decision_time)
            if price_at_decision is None:
                logger.warning("no_price_at_decision", ticker=ticker, effective_at=effective_at)
                continue

            # Calculate horizon date (decision_time + horizon_days trading days)
            horizon_date = self._add_trading_days(decision_time, settings.horizon_days)

            # Get price after horizon
            price_after = await self._fetch_prices_at_date(ticker, horizon_date)
            if price_after is None:
                logger.warning(
                    "no_price_after_horizon",
                    ticker=ticker,
                    horizon_date=horizon_date,
                )
                continue

            # Calculate actual return and direction
            actual_return = (price_after - price_at_decision) / price_at_decision
            actual_direction = 1 if actual_return > 0 else -1

            # Determine predicted direction from action
            action = decision["action"]
            predicted_direction = 1 if action in ("BUY", "HOLD") else -1

            # Determine if hit
            is_hit = predicted_direction == actual_direction

            # Extract dominant stream from evidence
            evidence = decision.get("evidence", [])
            dominant_stream = self._extract_dominant_stream(evidence)

            outcomes.append(
                DecisionOutcome(
                    decision_id=decision["decision_id"],
                    ticker=ticker,
                    action=action,
                    confidence=decision["confidence"],
                    effective_at=effective_at,
                    price_at_decision=price_at_decision,
                    price_after_horizon=price_after,
                    actual_return=actual_return,
                    predicted_direction=predicted_direction,
                    actual_direction=actual_direction,
                    is_hit=is_hit,
                    stream=dominant_stream,  # type: ignore[arg]
                )
            )

        return outcomes

    def _extract_dominant_stream(self, evidence: list[dict[str, Any]]) -> str:
        """Extract the dominant (highest weight) evidence stream."""
        if not evidence:
            return "UNKNOWN"
        # Evidence has 'stream' and 'strength' fields
        max_strength = -1.0
        dominant = "UNKNOWN"
        for e in evidence:
            if e.get("strength", 0) > max_strength:
                max_strength = e.get("strength", 0)
                dominant = e.get("stream", "UNKNOWN")
        return dominant

    @staticmethod
    def _add_trading_days(start_date: datetime, days: int) -> datetime:
        """Add N trading days to a date (skip weekends)."""
        current = start_date
        added = 0
        while added < days:
            current += timedelta(days=1)
            # Skip weekends (Monday=0, Sunday=6)
            if current.weekday() < 5:
                added += 1
        return current

    def _compute_stream_stats(
        self, outcomes: list[DecisionOutcome]
    ) -> list[StreamStats]:
        """Compute hit-rate and Brier score per evidence stream."""
        stream_data: dict[str, list[DecisionOutcome]] = {}
        for outcome in outcomes:
            if outcome.stream not in stream_data:
                stream_data[outcome.stream] = []
            stream_data[outcome.stream].append(outcome)

        stats: list[StreamStats] = []
        for stream, outcomes_list in stream_data.items():
            total = len(outcomes_list)
            hits = sum(1 for o in outcomes_list if o.is_hit)
            hit_rate = hits / total if total > 0 else 0.0

            # Brier score: mean((confidence - actual)^2)
            # actual = 1 if correct, 0 if incorrect
            brier_scores = []
            for o in outcomes_list:
                actual_binary = 1.0 if o.is_hit else 0.0
                brier_scores.append((o.confidence - actual_binary) ** 2)
            brier_score = sum(brier_scores) / len(brier_scores) if brier_scores else 1.0

            avg_confidence = sum(o.confidence for o in outcomes_list) / total

            stats.append(
                StreamStats(
                    stream=stream,
                    total_decisions=total,
                    hits=hits,
                    misses=total - hits,
                    hit_rate=hit_rate,
                    avg_confidence=avg_confidence,
                    brier_score=brier_score,
                )
            )

        return stats

    def _compute_confidence_buckets(
        self, outcomes: list[DecisionOutcome]
    ) -> list[ConfidenceBucket]:
        """Compute hit-rate per confidence bucket."""
        bucket_ranges = [
            (0.0, 0.2, "0.0-0.2"),
            (0.2, 0.4, "0.2-0.4"),
            (0.4, 0.6, "0.4-0.6"),
            (0.6, 0.8, "0.6-0.8"),
            (0.8, 1.0, "0.8-1.0"),
        ]

        buckets: list[ConfidenceBucket] = []
        for low, high, label in bucket_ranges:
            bucket_outcomes = [
                o for o in outcomes if low <= o.confidence < high
            ]
            total = len(bucket_outcomes)
            if total == 0:
                continue

            hits = sum(1 for o in bucket_outcomes if o.is_hit)
            hit_rate = hits / total
            avg_confidence = sum(o.confidence for o in bucket_outcomes) / total

            # Calibration error: |avg_confidence - hit_rate|
            calibration_error = abs(avg_confidence - hit_rate)

            buckets.append(
                ConfidenceBucket(
                    bucket=label,
                    total_decisions=total,
                    hits=hits,
                    hit_rate=hit_rate,
                    avg_predicted_confidence=avg_confidence,
                    calibration_error=calibration_error,
                )
            )

        return buckets

    def _compute_weight_adjustments(
        self,
        stream_stats: list[StreamStats],
        low_sample: bool = False,
    ) -> list[WeightAdjustment]:
        """Propose weight adjustments based on hit-rate performance."""
        if low_sample:
            return []

        adjustments: list[WeightAdjustment] = []
        current_weights = DEFAULT_WEIGHTS.copy()

        # Compute performance relative to average
        total_hit_rate = sum(s.hit_rate * s.total_decisions for s in stream_stats)
        total_decisions = sum(s.total_decisions for s in stream_stats)
        avg_hit_rate = total_hit_rate / total_decisions if total_decisions > 0 else 0.5

        for stat in stream_stats:
            if stat.stream not in current_weights:
                continue

            current = current_weights[stat.stream]
            performance = stat.hit_rate - avg_hit_rate

            # Scale adjustment: performance * learning_rate (max 20%)
            # Positive performance → increase weight, negative → decrease
            adjustment = performance * 0.5  # Learning rate
            adjustment = max(-settings.max_weight_adjustment, adjustment)
            adjustment = min(settings.max_weight_adjustment, adjustment)

            proposed = current + adjustment

            # Normalize to ensure sum = 1.0 later (done externally)
            adjustments.append(
                WeightAdjustment(
                    stream=stat.stream,
                    current_weight=current,
                    proposed_weight=proposed,
                    delta=adjustment,
                    reason=f"Hit-rate {stat.hit_rate:.2%} vs avg {avg_hit_rate:.2%}",
                )
            )

        return adjustments

    async def _generate_llm_narrative(
        self,
        report: BacktestReport,
        outcomes: list[DecisionOutcome],
    ) -> str | None:
        """Generate LLM narrative explaining backtest findings."""
        # This would call LiteLLM in production
        # For now, generate a simple narrative
        narrative_parts = []

        narrative_parts.append(
            f"Toplam {report.total_decisions} karar test edildi. "
            f"Genel isabet oranı: %{report.overall_hit_rate * 100:.1f}."
        )

        # Find best and worst streams
        if report.stream_stats:
            sorted_streams = sorted(
                report.stream_stats, key=lambda s: s.hit_rate, reverse=True
            )
            best = sorted_streams[0]
            worst = sorted_streams[-1]
            narrative_parts.append(
                f"En iyi performans: {best.stream} (%{best.hit_rate * 100:.1f}). "
                f"En zayıf: {worst.stream} (%{worst.hit_rate * 100:.1f})."
            )

        # Check calibration
        high_calibration_errors = [
            b for b in report.confidence_buckets if b.calibration_error > 0.10
        ]
        if high_calibration_errors:
            narrative_parts.append(
                "Kalibrasyon sorunu tespit edildi. "
                "Yüksek güven aralıklarında isabet oranı güvenilirlikten sapıyor."
            )

        return " ".join(narrative_parts)

    # -------------------------------------------------------------------------
    # Main Backtest Run
    # -------------------------------------------------------------------------

    async def run_backtest(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> BacktestReport:
        """
        Run complete backtest for the configured lookback period.

        Args:
            start_date: Start of backtest period (default: lookback_weeks ago)
            end_date: End of backtest period (default: now)

        Returns:
            BacktestReport with hit-rate, calibration, and weight adjustments
        """
        if end_date is None:
            end_date = datetime.now(UTC)
        if start_date is None:
            start_date = end_date - timedelta(weeks=settings.lookback_weeks)

        logger.info(
            "backtest_started",
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
        )

        # Fetch decisions
        decisions = await self._fetch_decisions(start_date, end_date)
        logger.info("decisions_fetched", count=len(decisions))

        if len(decisions) < settings.min_sample_size:
            logger.warning(
                "low_sample_size",
                decisions=len(decisions),
                min_required=settings.min_sample_size,
            )

        # Compute outcomes
        outcomes = await self._compute_outcomes(decisions)
        logger.info("outcomes_computed", count=len(outcomes))

        if not outcomes:
            return BacktestReport(
                start_date=start_date.date().isoformat(),
                end_date=end_date.date().isoformat(),
                total_decisions=0,
                overall_hit_rate=0.0,
                overall_brier_score=1.0,
                stream_stats=[],
                confidence_buckets=[],
                weight_adjustments=[],
                low_sample_warning=True,
                critical_alert=False,
                calibration_issues=["No valid outcomes found"],
            )

        # Compute statistics
        stream_stats = self._compute_stream_stats(outcomes)
        confidence_buckets = self._compute_confidence_buckets(outcomes)

        # Overall metrics
        total_hits = sum(1 for o in outcomes if o.is_hit)
        overall_hit_rate = total_hits / len(outcomes)
        overall_brier = sum(
            (o.confidence - (1.0 if o.is_hit else 0.0)) ** 2 for o in outcomes
        ) / len(outcomes)

        # Weight adjustments
        low_sample = len(outcomes) < settings.min_sample_size
        weight_adjustments = self._compute_weight_adjustments(stream_stats, low_sample)

        # Critical alerts
        critical_alert = overall_hit_rate < settings.hit_rate_critical_threshold

        # Calibration issues
        calibration_issues: list[str] = []
        for bucket in confidence_buckets:
            if bucket.calibration_error > settings.calibration_error_threshold:
                calibration_issues.append(
                    f"Bucket {bucket.bucket}: "
                    f"calibration error {bucket.calibration_error:.2%}"
                )

        # Generate LLM narrative
        report = BacktestReport(
            start_date=start_date.date().isoformat(),
            end_date=end_date.date().isoformat(),
            total_decisions=len(outcomes),
            overall_hit_rate=overall_hit_rate,
            overall_brier_score=overall_brier,
            stream_stats=stream_stats,
            confidence_buckets=confidence_buckets,
            weight_adjustments=weight_adjustments,
            low_sample_warning=low_sample,
            critical_alert=critical_alert,
            calibration_issues=calibration_issues,
        )

        report.llm_narrative = await self._generate_llm_narrative(report, outcomes)

        logger.info(
            "backtest_completed",
            report_id=report.report_id,
            total_decisions=report.total_decisions,
            hit_rate=report.overall_hit_rate,
            critical=report.critical_alert,
        )

        return report

    # -------------------------------------------------------------------------
    # Audit Logging
    # -------------------------------------------------------------------------

    async def _insert_audit_record(
        self, report: BacktestReport, start_date: datetime, end_date: datetime
    ) -> None:
        """Insert backtest audit record to PostgreSQL."""
        query = """
            INSERT INTO backtest.backtests (
                report_id, start_date, end_date,
                total_decisions, hit_rate, generated_at
            ) VALUES ($1, $2, $3, $4, $5, $6)
        """
        async with self._pool.acquire() as conn:
            await conn.execute(
                query,
                report.report_id,
                start_date.date().isoformat(),
                end_date.date().isoformat(),
                report.total_decisions,
                report.overall_hit_rate,
                datetime.now(UTC).isoformat(),
            )

    async def run(self) -> None:
        """Run the backtest service (weekly job)."""
        await self.initialize()
        try:
            report = await self.run_backtest()
            await self._insert_audit_record(
                report,
                datetime.now(UTC) - timedelta(weeks=settings.lookback_weeks),
                datetime.now(UTC),
            )
            logger.info("backtest_run_completed", report_id=report.report_id)
        finally:
            await self.close()
