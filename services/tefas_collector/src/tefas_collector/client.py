"""TEFAS API client for fetching fund data."""
from typing import Any

import httpx

from tefas_collector.config import settings


class TEFASAPIClient:
    """Client for TEFAS (Turkish Electronic Fund Distribution Platform) API."""

    def __init__(self) -> None:
        """Initialize TEFAS API client."""
        self._base_url = settings.tefas_api_base_url
        self._client = httpx.AsyncClient(timeout=60.0)

    async def get_all_funds(self) -> list[dict[str, Any]]:
        """
        Fetch list of all funds from TEFAS.

        Returns:
            List of fund records
        """
        response = await self._client.get(f"{self._base_url}/funds")
        response.raise_for_status()
        return response.json()

    async def get_fund_nav(self, fund_code: str) -> dict[str, Any]:
        """
        Fetch NAV (Net Asset Value) for a specific fund.

        Args:
            fund_code: TEFAS fund code

        Returns:
            NAV record with date, value, change
        """
        response = await self._client.get(f"{self._base_url}/nav/{fund_code}")
        response.raise_for_status()
        return response.json()

    async def get_fund_flows(self, fund_code: str, date: str) -> dict[str, Any]:
        """
        Fetch daily fund flows (subscriptions/redemptions).

        Args:
            fund_code: TEFAS fund code
            date: Date in YYYY-MM-DD format

        Returns:
            Flow record with subscription and redemption amounts
        """
        response = await self._client.get(
            f"{self._base_url}/flows/{fund_code}",
            params={"date": date},
        )
        response.raise_for_status()
        return response.json()

    async def get_fund_details(self, fund_code: str) -> dict[str, Any]:
        """
        Fetch detailed fund information.

        Args:
            fund_code: TEFAS fund code

        Returns:
            Fund details including manager, inception date, category
        """
        response = await self._client.get(f"{self._base_url}/fund/{fund_code}")
        response.raise_for_status()
        return response.json()

    async def close(self) -> None:
        """Close HTTP client."""
        await self._client.aclose()
