"""LLM client for Macro Analysis using LiteLLM."""
import json
from typing import Any

import structlog

from macro_analysis.config import settings

logger = structlog.get_logger(__name__)


class LiteLLMClient:
    """Client for calling LLM via LiteLLM for macro analysis."""

    def __init__(self) -> None:
        """Initialize LiteLLM client."""
        import litellm

        litellm.api_base = settings.litellm_api_base_url
        litellm.api_key = settings.litellm_api_key
        self._litellm = litellm

    def _build_system_prompt(self) -> str:
        """Build the system prompt for macro analysis."""
        return """You are the MACRO agent of Finance AI V3. You interpret macroeconomic releases from TCMB, TÜİK, and BDDK.

TURKISH MARKET CONTEXT:
- Trading hours: 10:00-18:00 TRT (Europe/Istanbul, UTC+3), weekdays only
- Pre-open auction: 09:45-10:00
- BIST ticker format: 4-5 uppercase letters (THYAO, GARAN, KCHOL)
- KAP = Kamuyu Aydınlatma Platformu (public disclosure platform)
- TEFAS = Turkish Electronic Fund Trading Platform
- TCMB = Türkiye Cumhuriyet Merkez Bankası
- TÜİK = Türkiye İstatistik Kurumu
- BDDK = Bankacılık Düzenleme ve Denetleme Kurumu
- All prices in TRY; BIST-100 is the benchmark index
- Holidays: official BIST trading calendar
- Currency: TRY (Turkish Lira), ISO 4217

TASK:
- Receive latest macro indicator + 12-month history.
- Estimate impact on BIST-100, USD/TRY, banking sector.
- Detect regime: BULL / BEAR / RANGE / CRISIS.
- Output macro signal.

OUTPUT FORMAT (strict JSON):
{
  "indicator_code": "string",
  "source": "TCMB | TUIKS | BDDK",
  "release_date": "ISO 8601",
  "actual_value": "float",
  "consensus_value": "float | null",
  "surprise": "float | null",
  "regime": "BULL | BEAR | RANGE | CRISIS",
  "regime_changed": "boolean",
  "impact_estimates": {
    "bist100_1d_pct": "float [-0.05, 0.05]",
    "usdtry_1d_pct": "float [-0.05, 0.05]",
    "banking_sector_1d_pct": "float [-0.05, 0.05]"
  },
  "confidence": "float [0, 1]",
  "reasoning": "string (Turkish, 2-3 sentences)",
  "data_completeness": "complete | partial | missing"
}

RULES:
- NEVER cite a historical analog that was not returned by Qdrant
- NEVER change regime without 3 confirming indicators
- NEVER output impact > 5% in absolute value
- NEVER fabricate consensus
- ALWAYS include surprise if consensus available (else null)
- ALWAYS set regime_changed: false unless 3 indicators confirm
- ALWAYS include data_completeness

Token Budget: Input max 6000 tokens, Output max 600 tokens. Temperature: 0.2"""

    def _build_user_prompt(
        self,
        indicator_code: str,
        source: str,
        actual_value: float,
        release_date: str,
        history: list[dict[str, Any]],
    ) -> str:
        """Build user prompt with macro indicator data."""
        prompt_parts = [
            f"INDICATOR CODE: {indicator_code}",
            f"SOURCE: {source}",
            f"RELEASE DATE: {release_date}",
            f"ACTUAL VALUE: {actual_value}",
            "",
            "12-MONTH HISTORY:",
        ]

        for h in history:
            prompt_parts.append(
                f"  {h.get('date', 'N/A')}: {h.get('value', 'N/A')} {h.get('unit', '')}"
            )

        prompt_parts.append("")
        prompt_parts.append("Analyze this macro release and provide your assessment.")

        return "\n".join(prompt_parts)

    async def analyze(
        self,
        indicator_code: str,
        source: str,
        actual_value: float,
        release_date: str,
        history: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Call LLM to analyze macro indicator.

        Args:
            indicator_code: TCMB/TÜİK/BDDK indicator code
            source: Data source (TCMB, TUIKS, BDDK)
            actual_value: Actual released value
            release_date: Release date
            history: 12-month history of the indicator

        Returns:
            LLM response as dictionary
        """
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(
            indicator_code, source, actual_value, release_date, history
        )

        try:
            response = self._litellm.completion(
                model=settings.litellm_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=settings.litellm_max_tokens,
                temperature=settings.litellm_temperature,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            usage = response.usage

            # Parse JSON response
            result = json.loads(content)

            # Add metadata
            result["_meta"] = {
                "tokens_in": usage.prompt_tokens if usage else None,
                "tokens_out": usage.completion_tokens if usage else None,
                "cost_usd": (
                    (usage.prompt_tokens * 0.00001 + usage.completion_tokens * 0.00003)
                    if usage
                    else None
                ),
            }

            logger.info(
                "llm_macro_response_received",
                indicator_code=indicator_code,
                regime=result.get("regime"),
                confidence=result.get("confidence"),
                tokens_in=result["_meta"]["tokens_in"],
                tokens_out=result["_meta"]["tokens_out"],
            )

            return result

        except json.JSONDecodeError as e:
            logger.error(
                "llm_json_decode_error",
                indicator_code=indicator_code,
                error=str(e),
            )
            raise
        except Exception as e:
            logger.error(
                "llm_call_error",
                indicator_code=indicator_code,
                error=str(e),
            )
            raise
