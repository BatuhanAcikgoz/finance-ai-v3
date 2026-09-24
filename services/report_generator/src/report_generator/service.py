"""Report Generator main service logic."""
import json
import uuid
from datetime import UTC, datetime
from typing import Any

import asyncpg
import structlog
from jinja2 import Template
from redis.asyncio import Redis

from report_generator.config import settings

logger = structlog.get_logger(__name__)

# Turkish disclaimer
TURKISH_DISCLAIMER = """
BU BİLDİRİM YATIRIM TAVSİYESİ DEĞİLDİR.
Yapay zeka destekli analiz sistemi tarafından oluşturulmuştur.
Yatırım kararları kendi araştırmanızı yaparak alınmalıdır.
Finance AI V3, kayıtlı bir yatırım danışmanı değildir.
"""


class ReportGeneratorService:
    """Service for generating reports (morning briefing, evening summary, etc.)."""

    def __init__(self) -> None:
        """Initialize report generator service."""
        self._redis: Redis | None = None
        self._pool: asyncpg.Pool | None = None

    async def initialize(self) -> None:
        """Initialize Redis and database connections."""
        self._redis = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
        )
        self._pool = await asyncpg.create_pool(
            settings.database_url,
            min_size=2,
            max_size=10,
        )

    async def close(self) -> None:
        """Close all connections."""
        if self._redis:
            await self._redis.close()
        if self._pool:
            await self._pool.close()

    async def generate_report(
        self,
        report_type: str,
        portfolio_id: str,
        period_start: str,
        period_end: str,
    ) -> dict[str, Any]:
        """
        Generate a report of the specified type.

        Args:
            report_type: One of MORNING_BRIEFING, EVENING_SUMMARY, WEEKLY, MONTHLY
            portfolio_id: Portfolio identifier
            period_start: ISO timestamp for period start
            period_end: ISO timestamp for period end

        Returns:
            Generated report payload
        """
        report_id = str(uuid.uuid4())

        # Check idempotency
        date_iso = datetime.now(UTC).date().isoformat()
        idempotency_key = f"report:{report_type}:{date_iso}"

        if self._redis and await self._redis.exists(idempotency_key):
            logger.info("report_already_generated_today", report_type=report_type)
            cached = await self._redis.get(f"{idempotency_key}:data")
            if cached:
                return json.loads(cached)

        # Fetch decisions for the period
        decisions = await self._fetch_decisions(portfolio_id, period_start, period_end)

        # Generate report content
        if decisions:
            content = await self._generate_narrative(decisions, report_type)
            narrative = content["narrative_tr"]
            decision_groups = content["decision_groups"]
            action_items = content["action_items_tr"]
        else:
            narrative = "Bugün için işlem yapılmadı."
            decision_groups = []
            action_items = ["Piyasayı izlemeye devam edin."]

        # Render HTML
        html_body = self._render_html(
            report_type=report_type,
            narrative=narrative,
            decision_groups=decision_groups,
            action_items=action_items,
            period_start=period_start,
            period_end=period_end,
        )

        # Build report payload
        report = {
            "report_id": report_id,
            "report_type": report_type,
            "period_start": period_start,
            "period_end": period_end,
            "portfolio_id": portfolio_id,
            "executive_summary_tr": narrative[:600],
            "decisions_count": len(decisions),
            "decision_groups": decision_groups,
            "action_items_tr": action_items[:3],
            "disclaimer_tr": TURKISH_DISCLAIMER.strip(),
            "html_body": html_body,
            "word_count": len(narrative.split()),
            "generated_at": datetime.now(UTC).isoformat(),
            "data_completeness": "complete" if decisions else "partial",
        }

        # Insert into database
        await self._insert_report(report)

        # Cache in Redis
        if self._redis:
            await self._redis.setex(idempotency_key, settings.idempotency_key_ttl_seconds, "1")
            await self._redis.setex(
                f"{idempotency_key}:data",
                settings.idempotency_key_ttl_seconds,
                json.dumps(report),
            )

        # Emit event
        await self._emit_report_event(report)

        logger.info(
            "report_generated",
            report_id=report_id,
            report_type=report_type,
            decisions_count=len(decisions),
        )

        return report

    async def _fetch_decisions(
        self, portfolio_id: str, period_start: str, period_end: str
    ) -> list[dict[str, Any]]:
        """Fetch decisions for the reporting period."""
        if not self._pool:
            raise RuntimeError("Database pool not initialized")

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT decision_id, ticker, decision_type, action, rationale,
                       confidence, created_at
                FROM decision.decisions
                WHERE portfolio_id = $1
                  AND created_at BETWEEN $2 AND $3
                ORDER BY created_at DESC
                """,
                portfolio_id,
                period_start,
                period_end,
            )
            return [dict(row) for row in rows]

    async def _generate_narrative(
        self, decisions: list[dict[str, Any]], report_type: str
    ) -> dict[str, Any]:
        """
        Generate narrative using LLM.

        In production, this would call LiteLLM. For now, generates placeholder.
        """
        # Group decisions by ticker
        ticker_groups: dict[str, list[dict]] = {}
        for decision in decisions:
            ticker = decision.get("ticker", "UNKNOWN")
            if ticker not in ticker_groups:
                ticker_groups[ticker] = []
            ticker_groups[ticker].append(decision)

        # Build decision groups
        decision_groups = []
        for ticker, ticker_decisions in ticker_groups.items():
            decision_ids = [d["decision_id"] for d in ticker_decisions]
            # Simple narrative - in production this would be LLM-generated
            actions = [d.get("action", "HOLD") for d in ticker_decisions]
            narrative = f"{ticker} için {len(ticker_decisions)} karar alındı. Önerilen işlemler: {', '.join(set(actions))}."
            decision_groups.append({
                "ticker": ticker,
                "decision_ids": decision_ids,
                "narrative_tr": narrative,
            })

        # Generate action items
        action_items = [
            f"{len(decisions)} karar analiz edildi.",
            "Portföy performansını izlemeye devam edin.",
            "Risk seviyenizi gözden geçirin.",
        ]

        # Generate executive summary
        narrative = f"Bu {report_type.lower().replace('_', ' ')} döneminde {len(decisions)} karar analiz edildi. " + " ".join(
            [g["narrative_tr"] for g in decision_groups[:3]]
        )

        return {
            "narrative_tr": narrative,
            "decision_groups": decision_groups,
            "action_items_tr": action_items,
        }

    def _render_html(
        self,
        report_type: str,
        narrative: str,
        decision_groups: list[dict],
        action_items: list[str],
        period_start: str,
        period_end: str,
    ) -> str:
        """Render HTML email body using Jinja2 template."""
        template_str = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{{ report_type }} - Finance AI V3</title>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 20px; }
        .header { background: #1a365d; color: white; padding: 20px; text-align: center; border-radius: 8px; }
        .content { padding: 20px 0; }
        .decision-group { background: #f7fafc; padding: 15px; margin: 10px 0; border-radius: 8px; }
        .ticker { font-weight: bold; color: #1a365d; }
        .action-items { background: #fffbeb; padding: 15px; border-radius: 8px; margin-top: 20px; }
        .disclaimer { font-size: 12px; color: #666; margin-top: 30px; padding-top: 10px; border-top: 1px solid #ddd; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Finance AI V3</h1>
        <p>{{ report_type.replace('_', ' ') }}</p>
    </div>
    <div class="content">
        <h2>Özet</h2>
        <p>{{ narrative }}</p>

        {% if decision_groups %}
        <h2>Kararlar</h2>
        {% for group in decision_groups %}
        <div class="decision-group">
            <span class="ticker">{{ group.ticker }}</span>
            <p>{{ group.narrative_tr }}</p>
        </div>
        {% endfor %}
        {% endif %}

        <div class="action-items">
            <h3>Önerilen Aksiyonlar</h3>
            <ul>
            {% for item in action_items %}
                <li>{{ item }}</li>
            {% endfor %}
            </ul>
        </div>
    </div>
    <div class="disclaimer">
        {{ disclaimer }}
    </div>
</body>
</html>
        """
        template = Template(template_str)
        return template.render(
            report_type=report_type,
            narrative=narrative,
            decision_groups=decision_groups,
            action_items=action_items,
            period_start=period_start,
            period_end=period_end,
            disclaimer=TURKISH_DISCLAIMER,
        )

    async def _insert_report(self, report: dict[str, Any]) -> None:
        """Insert report into database."""
        if not self._pool:
            raise RuntimeError("Database pool not initialized")

        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO reports.reports (
                    report_id, report_type, period_start, period_end,
                    portfolio_id, executive_summary_tr, decisions_count,
                    decision_groups, action_items_tr, disclaimer_tr,
                    html_body, word_count, generated_at, data_completeness
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                """,
                report["report_id"],
                report["report_type"],
                report["period_start"],
                report["period_end"],
                report["portfolio_id"],
                report["executive_summary_tr"],
                report["decisions_count"],
                json.dumps(report["decision_groups"]),
                json.dumps(report["action_items_tr"]),
                report["disclaimer_tr"],
                report["html_body"],
                report["word_count"],
                report["generated_at"],
                report["data_completeness"],
            )

    async def _emit_report_event(self, report: dict[str, Any]) -> None:
        """Emit report generated event to Redis."""
        if not self._redis:
            raise RuntimeError("Redis not initialized")

        event = {
            "event_type": "report.generated",
            "report_id": report["report_id"],
            "report_type": report["report_type"],
            "portfolio_id": report["portfolio_id"],
            "timestamp": datetime.now(UTC).isoformat(),
        }

        await self._redis.publish("report.generated", str(event))
