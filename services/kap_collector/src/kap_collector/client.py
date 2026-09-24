"""KAP API client for fetching disclosures."""
from typing import Any

import httpx

from kap_collector.config import settings


class KAPAPIClient:
    """Client for KAP (Public Disclosure Platform) REST API."""

    def __init__(self) -> None:
        """Initialize KAP API client."""
        self._base_url = settings.kap_api_base_url
        self._client = httpx.AsyncClient(timeout=30.0)

    async def get_disclosures(
        self, since: str | None = None, max_results: int = 100
    ) -> list[dict[str, Any]]:
        """
        Fetch list of disclosures from KAP API.

        Args:
            since: ISO timestamp to fetch disclosures since
            max_results: Maximum number of results to return

        Returns:
            List of disclosure summary records
        """
        params: dict[str, Any] = {"maxResults": max_results}
        if since:
            params["date"] = since

        response = await self._client.get(
            f"{self._base_url}/v1/disclosures",
            params=params,
        )
        response.raise_for_status()
        return response.json()

    async def get_disclosure_detail(self, publishing_id: str) -> dict[str, Any]:
        """
        Fetch full disclosure detail by publishing ID.

        Args:
            publishing_id: KAP publishing ID

        Returns:
            Full disclosure record with body text
        """
        response = await self._client.get(
            f"{self._base_url}/v1/disclosures/{publishing_id}",
        )
        response.raise_for_status()
        return response.json()

    async def close(self) -> None:
        """Close HTTP client."""
        await self._client.aclose()
