#!/usr/bin/env python3
"""
Seed development data for Finance AI V3.

This script populates the database with sample tickers for development and testing.
Run with: uv run python scripts/seed_dev_data.py
"""

import asyncio
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# Sample tickers for Phase 1 MVP (THYAO focus)
SAMPLE_TICKERS = [
    # THYAO - Turkish Airlines (MVP focus)
    {"ticker": "THYAO", "name": "Türk Hava Yolları A.O.", "sector": "Transportation", "subsector": "Air Transportation"},
    
    # Banking sector
    {"ticker": "GARAN", "name": "Garanti BBVA A.Ş.", "sector": "Financials", "subsector": "Banking"},
    {"ticker": "AKBNK", "name": "Akbank T.A.Ş.", "sector": "Financials", "subsector": "Banking"},
    {"ticker": "ISCTR", "name": "İşbank A.Ş.", "sector": "Financials", "subsector": "Banking"},
    {"ticker": "HALKB", "name": "Halkbank A.Ş.", "sector": "Financials", "subsector": "Banking"},
    {"ticker": "YKBNK", "name": "Yapı ve Kredi Bankası A.Ş.", "sector": "Financials", "subsector": "Banking"},
    
    # Industrial sector
    {"ticker": "EREGL", "name": "Ereğli Demir ve Çelik Fabrikaları T.A.Ş.", "sector": "Basic Materials", "subsector": "Iron and Steel"},
    {"ticker": "ASELS", "name": "Aselsan Elektronik Sanayi ve Ticaret A.Ş.", "sector": "Technology", "subsector": "Defense Electronics"},
    {"ticker": "KCHOL", "name": "Koç Holding A.Ş.", "sector": "Conglomerates", "subsector": "Holding"},
    {"ticker": "SAHOL", "name": "Sabancı Holding A.Ş.", "sector": "Conglomerates", "subsector": "Holding"},
    
    # BIST Index
    {"ticker": "XU100", "name": "BIST 100 Index", "sector": None, "subsector": None, "is_index": True},
]

# Sample fund data
SAMPLE_FUNDS = [
    {"fund_code": "THYAO", "fund_name": "THY Yatırım Fonu", "fund_type": "MUTUAL"},
    {"fund_code": "AKD", "fund_name": "Akdeniz Katılım Fonu", "fund_type": "PARTICIPATION"},
    {"fund_code": "GOLD1", "fund_name": "Altın Fonu", "fund_type": "GOLD"},
]

# Sample portfolio for development
SAMPLE_PORTFOLIO = {
    "user_id": "dev-user-001",
    "name": "Geliştirme Portföyü",
    "holdings": [
        {"ticker": "THYAO", "shares": 1000, "cost_basis_try": 250000.00, "target_weight": 0.30},
        {"ticker": "GARAN", "shares": 5000, "cost_basis_try": 175000.00, "target_weight": 0.25},
        {"ticker": "EREGL", "shares": 2000, "cost_basis_try": 100000.00, "target_weight": 0.15},
        {"ticker": "ASELS", "shares": 3000, "cost_basis_try": 125000.00, "target_weight": 0.20},
        {"ticker": "AKBNK", "shares": 4000, "cost_basis_try": 100000.00, "target_weight": 0.10},
    ],
}


async def seed_tickers(db_pool) -> int:
    """Seed ticker data."""
    from services.shared.src.shared.db import get_db_pool
    
    pool = get_db_pool()
    
    query = """
        INSERT INTO market_data.tickers (ticker, name, sector, subsector, is_index, is_active)
        VALUES ($1, $2, $3, $4, $5, true)
        ON CONFLICT (ticker) DO UPDATE SET
            name = EXCLUDED.name,
            sector = EXCLUDED.sector,
            subsector = EXCLUDED.subsector,
            updated_at = NOW()
    """
    
    count = 0
    async with pool.connection() as conn:
        for ticker in SAMPLE_TICKERS:
            await conn.execute(
                query,
                ticker["ticker"],
                ticker["name"],
                ticker.get("sector"),
                ticker.get("subsector"),
                ticker.get("is_index", False),
            )
            count += 1
    
    print(f"  ✓ Seeded {count} tickers")
    return count


async def seed_funds(db_pool) -> int:
    """Seed fund data."""
    pool = get_db_pool()
    
    query = """
        INSERT INTO tefas.funds (fund_code, fund_name, fund_type, active)
        VALUES ($1, $2, $3, true)
        ON CONFLICT (fund_code) DO UPDATE SET
            fund_name = EXCLUDED.fund_name,
            fund_type = EXCLUDED.fund_type
    """
    
    count = 0
    async with pool.connection() as conn:
        for fund in SAMPLE_FUNDS:
            await conn.execute(query, fund["fund_code"], fund["fund_name"], fund["fund_type"])
            count += 1
    
    print(f"  ✓ Seeded {count} funds")
    return count


async def seed_portfolio(db_pool) -> int:
    """Seed sample portfolio."""
    pool = get_db_pool()
    
    import uuid
    
    portfolio_id = uuid.uuid4()
    
    # Insert portfolio
    portfolio_query = """
        INSERT INTO portfolio.portfolios (portfolio_id, user_id, name, base_currency)
        VALUES ($1, $2, $3, 'TRY')
        ON CONFLICT (portfolio_id) DO NOTHING
    """
    
    holdings_query = """
        INSERT INTO portfolio.holdings (portfolio_id, ticker, shares, cost_basis_try, target_weight)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (portfolio_id, ticker) DO UPDATE SET
            shares = EXCLUDED.shares,
            cost_basis_try = EXCLUDED.cost_basis_try,
            target_weight = EXCLUDED.target_weight
    """
    
    count = 0
    async with pool.connection() as conn:
        await conn.execute(portfolio_query, portfolio_id, SAMPLE_PORTFOLIO["user_id"], SAMPLE_PORTFOLIO["name"])
        
        for holding in SAMPLE_PORTFOLIO["holdings"]:
            await conn.execute(
                holdings_query,
                portfolio_id,
                holding["ticker"],
                holding["shares"],
                holding["cost_basis_try"],
                holding["target_weight"],
            )
            count += 1
    
    print(f"  ✓ Seeded 1 portfolio with {count} holdings")
    return count


async def seed_sample_bars(db_pool, ticker: str = "THYAO") -> int:
    """Seed sample bar data for THYAO for the last 30 trading days."""
    pool = get_db_pool()
    
    import random
    
    # Base price for THYAO ~280 TRY
    base_price = 280.0
    bars_per_day = 78  # 10:00-18:00 in 5-minute intervals
    
    bars = []
    
    # Generate 30 days of sample data
    from services.shared.src.shared.calendar import get_calendar
    
    calendar = get_calendar()
    today = date.today()
    
    count = 0
    async with pool.connection() as conn:
        for days_ago in range(30, 0, -1):
            trade_date = today - timedelta(days=days_ago)
            
            if not calendar.is_trading_day(trade_date):
                continue
            
            # Generate bars for this day
            price = base_price + random.uniform(-10, 10)
            
            for bar_num in range(bars_per_day):
                bar_start_hour = 10 + (bar_num // 12)
                bar_start_min = (bar_num % 12) * 5
                
                # Random price movement
                price += random.uniform(-1, 1)
                open_price = price
                high_price = price + random.uniform(0, 2)
                low_price = price - random.uniform(0, 2)
                close_price = price + random.uniform(-0.5, 0.5)
                volume = random.randint(100000, 500000)
                
                bar_start = datetime.combine(trade_date, datetime.min.time()).replace(
                    hour=bar_start_hour, minute=bar_start_min, tzinfo=None
                )
                bar_end = bar_start + timedelta(minutes=5)
                
                bars.append((
                    ticker, "5m", open_price, high_price, low_price, close_price,
                    volume, bar_start, bar_end
                ))
                
                count += 1
        
        # Batch insert
        if bars:
            query = """
                INSERT INTO market_data.bars 
                (ticker, timeframe, open, high, low, close, volume, bar_start, bar_end)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (ticker, timeframe, bar_start) DO NOTHING
            """
            await conn.executemany(query, bars)
    
    print(f"  ✓ Seeded {count} sample bars for {ticker}")
    return count


async def main():
    """Main seeding function."""
    print("=== Finance AI V3 - Seed Dev Data ===\n")
    
    print("Seeding database...")
    
    try:
        # Initialize database pool
        from services.shared.src.shared.db import init_db
        await init_db()
        
        # Seed data
        await seed_tickers(None)
        await seed_funds(None)
        await seed_portfolio(None)
        await seed_sample_bars(None, "THYAO")
        
        print("\n✅ Seeding complete!")
        print("\nSample portfolio:")
        print(f"  Portfolio ID: dev-user-001")
        print(f"  Holdings: THYAO, GARAN, EREGL, ASELS, AKBNK")
        
    except Exception as e:
        print(f"\n❌ Seeding failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
