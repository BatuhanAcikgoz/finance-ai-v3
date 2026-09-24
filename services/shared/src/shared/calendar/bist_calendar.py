"""BIST trading calendar - handles Turkish trading days and holidays."""

from datetime import date, datetime, timedelta
from typing import ClassVar

import structlog

logger = structlog.get_logger()


class BISTCalendar:
    """
    Borsa Istanbul (BIST) trading calendar.
    
    BIST trading hours (TRT, UTC+3):
    - Pre-open auction: 09:45 - 10:00
    - Continuous trading: 10:00 - 18:00
    - Closing auction: 18:00 - 18:15 (for some instruments)
    
    Trading days: Monday - Friday (except public holidays)
    """

    # BIST official holidays (fixed dates)
    FIXED_HOLIDAYS: ClassVar[dict[tuple[int, int], str]] = {
        (1, 1): "New Year's Day",       # January 1
        (4, 23): "National Sovereignty Day",  # April 23
        (5, 1): "Labor Day",            # May 1
        (5, 19): "Commemoration of Atatürk",  # May 19
        (7, 15): "Democracy and National Unity Day",  # July 15
        (8, 30): "Victory Day",         # August 30
        (10, 29): "Republic Day",       # October 29
    }

    # Approximate Ramadan dates (should be updated annually)
    RAMADAN_HOLIDAYS: ClassVar[list[date]] = [
        # 2024: March 10-12 (Eid al-Fitr)
        # 2025: February 28 - March 2
        # 2026: February 17-19
    ]

    # Approximate Eid al-Adha dates (should be updated annually)
    EID_AL_ADHA_HOLIDAYS: ClassVar[list[date]] = [
        # 2024: June 16-20
        # 2025: June 5-9
        # 2026: May 25-29
    ]

    def __init__(self, year: int | None = None):
        self.year = year or datetime.now().year
        self._holidays_cache: set[date] | None = None

    def _build_holidays(self) -> set[date]:
        """Build the complete holiday set for the year."""
        if self._holidays_cache is not None:
            return self._holidays_cache

        holidays = set()

        # Add fixed holidays
        for (month, day), name in self.FIXED_HOLIDAYS.items():
            try:
                holidays.add(date(self.year, month, day))
            except ValueError:
                logger.warning("invalid_holiday_date", year=self.year, month=month, day=day)

        # Add Ramadan holidays (approximate - should verify annually)
        for d in self.RAMADAN_HOLIDAYS:
            try:
                holidays.add(date(self.year, d.month, d.day))
            except (AttributeError, ValueError):
                pass

        # Add Eid al-Adha holidays (approximate - should verify annually)
        for d in self.EID_AL_ADHA_HOLIDAYS:
            try:
                holidays.add(date(self.year, d.month, d.day))
            except (AttributeError, ValueError):
                pass

        self._holidays_cache = holidays
        return holidays

    def is_holiday(self, d: date) -> bool:
        """Check if a date is a BIST holiday."""
        return d in self._build_holidays()

    def is_weekend(self, d: date) -> bool:
        """Check if a date is a weekend (Saturday or Sunday)."""
        return d.weekday() >= 5  # 5 = Saturday, 6 = Sunday

    def is_trading_day(self, d: date) -> bool:
        """Check if a date is a trading day."""
        return not self.is_weekend(d) and not self.is_holiday(d)

    def is_market_open(self, dt: datetime | None = None) -> bool:
        """Check if the market is currently open."""
        if dt is None:
            dt = datetime.now()

        # Convert to TRT (Europe/Istanbul)
        # Assuming dt is already in TRT or we need to localize
        d = dt.date()

        if not self.is_trading_day(d):
            return False

        # Trading hours: 10:00 - 18:00 TRT
        hour = dt.hour
        return 10 <= hour < 18

    def get_next_trading_day(self, d: date) -> date:
        """Get the next trading day after the given date."""
        next_day = d + timedelta(days=1)
        max_days = 14  # Safety limit

        for _ in range(max_days):
            if self.is_trading_day(next_day):
                return next_day
            next_day += timedelta(days=1)

        logger.warning("next_trading_day_not_found", start_date=d)
        return next_day

    def get_previous_trading_day(self, d: date) -> date:
        """Get the previous trading day before the given date."""
        prev_day = d - timedelta(days=1)
        max_days = 14  # Safety limit

        for _ in range(max_days):
            if self.is_trading_day(prev_day):
                return prev_day
            prev_day -= timedelta(days=1)

        logger.warning("previous_trading_day_not_found", start_date=d)
        return prev_day

    def get_trading_days_between(self, start: date, end: date) -> list[date]:
        """Get all trading days between two dates (inclusive)."""
        days = []
        current = start

        while current <= end:
            if self.is_trading_day(current):
                days.append(current)
            current += timedelta(days=1)

        return days


# Module-level convenience functions
_calendar_cache: dict[int, BISTCalendar] = {}


def get_calendar(year: int | None = None) -> BISTCalendar:
    """Get or create a calendar for the given year."""
    if year is None:
        year = datetime.now().year

    if year not in _calendar_cache:
        _calendar_cache[year] = BISTCalendar(year)

    return _calendar_cache[year]


def is_trading_day(d: date) -> bool:
    """Check if a date is a trading day."""
    return get_calendar(d.year).is_trading_day(d)


def next_trading_day(d: date) -> date:
    """Get the next trading day after the given date."""
    return get_calendar(d.year).get_next_trading_day(d)


def is_market_open(dt: datetime | None = None) -> bool:
    """Check if the market is currently open."""
    return get_calendar().is_market_open(dt)
