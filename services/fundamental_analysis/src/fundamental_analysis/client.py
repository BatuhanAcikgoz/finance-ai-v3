"""LLM client for Fundamental Analysis using LiteLLM."""
import json
from typing import Any

import structlog

from fundamental_analysis.config import settings

logger = structlog.get_logger(__name__)


class LiteLLMClient:
    """Client for calling LLM via LiteLLM."""

    def __init__(self) -> None:
        """Initialize LiteLLM client."""
        import litellm

        litellm.api_base = settings.litellm_api_base_url
        litellm.api_key = settings.litellm_api_key
        self._litellm = litellm

    def _build_system_prompt(self) -> str:
        """Build the system prompt for fundamental analysis."""
        return """You are the FUNDAMENTAL agent of Finance AI V3. You parse KAP disclosures, extract financials, interpret ratios, and emit a fundamental signal.

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
- Receive KAP disclosure body + ticker.
- Extract: revenue, EBITDA, net_income, debt, cash, equity, EPS.
- Identify peer set (5-10 sector peers).
- Output BULLISH/BEARISH/NEUTRAL + confidence + reasoning.

OUTPUT FORMAT (strict JSON):
{
  "ticker": "string",
  "kap_publishing_id": "string",
  "direction": "BULLISH | BEARISH | NEUTRAL",
  "strength": "float [0, 1]",
  "confidence": "float [0, 1]",
  "extracted_financials": {
    "revenue": "float | null",
    "ebitda": "float | null",
    "net_income": "float | null",
    "total_debt": "float | null",
    "cash": "float | null",
    "equity": "float | null",
    "eps": "float | null"
  },
  "reasoning": "string (Turkish, 2-3 sentences)",
  "data_completeness": "complete | partial | missing",
  "source_citations": [{"field": "string", "kap_id": "string", "line_no": "int"}]
}

RULES:
- NEVER fabricate a financial number
- NEVER output a ratio that was not provided in extracted_financials
- NEVER skip source_citations for any non-null field
- ALWAYS cite KAP line_no for every extracted number
- ALWAYS flag data_completeness: partial if any key field is null
- If KAP has no financials (e.g. board change): output direction: NEUTRAL, confidence: 0, data_completeness: missing

Token Budget: Input max 8000 tokens, Output max 800 tokens. Temperature: 0.1"""

    def _build_user_prompt(
        self,
        ticker: str,
        publishing_id: str,
        title: str,
        body: str,
        market_cap: float | None = None,
        current_price: float | None = None,
    ) -> str:
        """Build user prompt with KAP disclosure content."""
        prompt_parts = [
            f"TICKER: {ticker}",
            f"KAP PUBLISHING ID: {publishing_id}",
            f"TITLE: {title}",
            "",
            "DISCLOSURE BODY:",
            body[:6000],  # Limit body to prevent token overflow
            "",
        ]

        if market_cap is not None:
            prompt_parts.append(f"MARKET CAP (TRY): {market_cap:,.2f}")
        if current_price is not None:
            prompt_parts.append(f"CURRENT PRICE (TRY): {current_price:.2f}")

        prompt_parts.append("")
        prompt_parts.append("Extract financial data from this disclosure and provide your analysis.")

        return "\n".join(prompt_parts)

    async def analyze(
        self,
        ticker: str,
        publishing_id: str,
        title: str,
        body: str,
        market_cap: float | None = None,
        current_price: float | None = None,
    ) -> dict[str, Any]:
        """
        Call LLM to analyze KAP disclosure.

        Args:
            ticker: BIST ticker symbol
            publishing_id: KAP publishing ID
            title: Disclosure title
            body: Disclosure body text
            market_cap: Market capitalization in TRY
            current_price: Current stock price in TRY

        Returns:
            LLM response as dictionary
        """
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(
            ticker, publishing_id, title, body, market_cap, current_price
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
                "llm_response_received",
                ticker=ticker,
                direction=result.get("direction"),
                confidence=result.get("confidence"),
                tokens_in=result["_meta"]["tokens_in"],
                tokens_out=result["_meta"]["tokens_out"],
            )

            return result

        except json.JSONDecodeError as e:
            logger.error(
                "llm_json_decode_error",
                ticker=ticker,
                error=str(e),
                content=content if "content" in dir() else "N/A",
            )
            raise
        except Exception as e:
            logger.error(
                "llm_call_error",
                ticker=ticker,
                error=str(e),
            )
            raise
