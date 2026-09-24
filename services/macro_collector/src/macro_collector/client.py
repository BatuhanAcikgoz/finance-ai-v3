"""Macro data API clients for TCMB, TÜİK, BDDK."""
from typing import Any

import httpx

from macro_collector.config import settings


class TCMBEVDSClient:
    """Client for TCMB Electronic Data Delivery System (EVDS) API."""

    def __init__(self) -> None:
        """Initialize TCMB EVDS client."""
        self._base_url = settings.tcmb_evds_base_url
        self._client = httpx.AsyncClient(timeout=60.0)

    async def get_indicator(self, series_code: str, date_start: str, date_end: str) -> list[dict[str, Any]]:
        """
        Fetch indicator data from TCMB EVDS.

        Args:
            series_code: EVDS series code (e.g., TP.DK.USD.A, TP.KKH.TL)
            date_start: Start date in YYYY-MM-DD
            date_end: End date in YYYY-MM-DD

        Returns:
            List of indicator values
        """
        if not settings.tcmb_api_key:
            return []

        params = {
            "key": settings.tcmb_api_key,
            "code": series_code,
            "startDate": date_start,
            "endDate": date_end,
            "type": "json",
        }
        
        response = await self._client.get(
            f"{self._base_url}/service/evds",
            params=params,
        )
        response.raise_for_status()
        
        data = response.json()
        return data.get("data", [])

    async def close(self) -> None:
        """Close HTTP client."""
        await self._client.aclose()


class TUICKClient:
    """Client for TÜİK (Turkish Statistical Institute) data."""

    def __init__(self) -> None:
        """Initialize TÜİK client."""
        self._base_url = settings.tuik_base_url
        self._client = httpx.AsyncClient(timeout=60.0)

    async def get_indicator(self, indicator_code: str) -> dict[str, Any]:
        """
        Fetch indicator from TÜİK.

        Args:
            indicator_code: TÜİK indicator code

        Returns:
            Indicator value and metadata
        """
        # TÜİK provides data through their website - simplified placeholder
        response = await self._client.get(
            f"{self._base_url}/api/{indicator_code}",
        )
        
        if response.status_code == 404:
            return {}
        
        response.raise_for_status()
        return response.json()

    async def get_cpi(self) -> dict[str, Any]:
        """Get CPI (Consumer Price Index) data."""
        return await self.get_indicator("TÜFE")

    async def get_ppi(self) -> dict[str, Any]:
        """Get PPI (Producer Price Index) data."""
        return await self.get_indicator("ÜFE")

    async def get_unemployment(self) -> dict[str, Any]:
        """Get unemployment rate data."""
        return await self.get_indicator("ISSIZLIK")

    async def get_gdp(self) -> dict[str, Any]:
        """Get GDP data."""
        return await self.get_indicator("GSYIH")

    async def close(self) -> None:
        """Close HTTP client."""
        await self._client.aclose()


class BDDKClient:
    """Client for BDDK (Banking Regulation and Supervision Agency) data."""

    def __init__(self) -> None:
        """Initialize BDDK client."""
        self._base_url = settings.bddk_base_url
        self._client = httpx.AsyncClient(timeout=60.0)

    async def get_bulletin(self, bulletin_type: str = "weekly") -> dict[str, Any]:
        """
        Fetch BDDK bulletin.

        Args:
            bulletin_type: Type of bulletin (weekly, monthly)

        Returns:
            Bulletin data
        """
        response = await self._client.get(
            f"{self._base_url}/api/bulten/{bulletin_type}",
        )
        response.raise_for_status()
        return response.json()

    async def get_npl_ratio(self) -> dict[str, Any]:
        """Get sector NPL (non-performing loan) ratio."""
        bulletin = await self.get_bulletin("weekly")
        return {
            "indicator_code": "NPL_RATIO",
            "value": bulletin.get("nplRatio"),
            "unit": "percent",
        }

    async def get_capital_adequacy(self) -> dict[str, Any]:
        """Get capital adequacy ratio."""
        bulletin = await self.get_bulletin("weekly")
        return {
            "indicator_code": "CAPITAL_ADEQUACY",
            "value": bulletin.get("capitalAdequacy"),
            "unit": "percent",
        }

    async def close(self) -> None:
        """Close HTTP client."""
        await self._client.aclose()
