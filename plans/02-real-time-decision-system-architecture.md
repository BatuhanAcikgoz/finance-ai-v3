# Kural Bazlı Real-Time Trading Robot - Teknik Tasarım

**Versiyon:** 1.0 | **Tarih:** 2026-07-31 | **Durum:** Tasarım Aşamasında

---

## 🎯 Sistem Özeti

```
┌─────────────────────────────────────────────────────────────────┐
│                    KURAL BAZLI TRADING ROBOT                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  [BIST WebSocket] ──► [Feature Store] ──► [Rule Engine] ──┐    │
│                        (Redis)             │                │    │
│  [Broker APIs] ──────► [Portföy Cache] ────►               │    │
│  (Midas + Akbank)                              │                │
│                                                ▼                │
│                                    [Karar: BUY/SELL/HOLD]       │
│                                                │                │
│                              ┌─────────────────┼─────────────┐  │
│                              ▼                 ▼             ▼  │
│                       [Web Panel]      [Auto-Execute]   [Bildirim] │
│                       (Anlık göster)  (Broker API)    (Telegram) │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📋 İçindekiler

1. [Giriş ve Motivasyon](#1-giriş-ve-motivasyon)
2. [Maliyet Analizi](#2-maliyet-analizi)
3. [Kural Seti (Strategy)](#3-kural-seti-strategy)
4. [Karar Motoru](#4-karar-motoru)
5. [Risk Yönetimi](#5-risk-yönetimi)
6. [Broker API Entegrasyonları](#6-broker-api-entegrasyonları)
7. [Veritabanı Şeması](#7-veritabanı-şeması)
8. [Web Panel Tasarımı](#8-web-panel-tasarımı)
9. [Servis Yapısı](#9-servis-yapısı)
10. [Performans Hedefleri](#10-performans-hedefleri)
11. [Implementasyon Planı](#11-implementasyon-planı)

---

## 1. Giriş ve Motivasyon

### Problem Tanımı
Mevcut sistem 24 saatlik periyotlarla karar üretiyor. Bu:
- ⚠️ Piyasa anormalliklerine geç tepki
- ⚠️ Anlık fırsatları kaçırma
- ⚠️ Broker API entegrasyonu yok
- ⚠️ **Ortalama maliyet dikkate alınmıyor**
- ⚠️ Sadece raporlama, otomatik işlem yok

### Hedef
Gerçek zamanlı (sub-second), kural bazlı, broker API'li, kullanıcının ortalama maliyetini dikkate alan karar sistemi.

### Neden Kural Bazlı?
- ML modelleri çoğu zaman basit kurallardan daha iyi performans göstermiyor
- Overfitting riski yüksek
- Anlaşılır, debug edilebilir, bakımı kolay
- Düşük maliyetli altyapı yeterli

---

## 2. Maliyet Analizi

### Aylık Maliyet

| Bileşen | Miktar |
|---------|--------|
| Redis (Cloud) | $15 |
| Web sunucu (mevcut) | $0 |
| Domain + SSL | $10 |
| **Toplam** | **~$25-35/ay** |

### Performans vs Maliyet Karşılaştırması

| Yaklaşım | Maliyet/ay | Performans |
|----------|------------|------------|
| GPU + ML + Triton | $500-1000 | Overkill |
| CPU + ML (ONNX) | $50-100 | Orta |
| **Redis + Kurallar** | **$25-35** | **Yeterli** |

---

## 3. Kural Seti (Strategy)

### 3.1 Giriş (ENTRY) Kuralları

```python
# services/trading_robot/src/trading_robot/rules.py

class TradingRules:
    """
    Trading kararları için kural seti.
    Tüm kurallar bağımsız test edilebilir.
    """
    
    # ─────────────────────────────────────────────────────────────
    # GİRİŞ (ENTRY) KURALLARI
    # ─────────────────────────────────────────────────────────────
    
    @staticmethod
    def should_buy(rsi: float, macd_histogram: float, price_vs_sma: float) -> tuple[bool, str]:
        """
        ALım sinyali kontrolü.
        
        Args:
            rsi: RSI değeri (0-100)
            macd_histogram: MACD histogram değeri
            price_vs_sma: Fiyatın SMA'ya göre yüzdesi
        
        Returns:
            (signal, reason)
        """
        # Kural 1: RSI aşırı satım bölgesinde
        if rsi < 35:
            return True, f"RSI={rsi:.1f} aşırı satım bölgesinde"
        
        # Kural 2: MACD pozitif kesişim
        if macd_histogram > 0 and price_vs_sma > 0:
            return True, f"MACD pozitif, fiyat SMA üzerinde"
        
        # Kural 3: Dipte güçlenme (RSI 40-50 + pozitif MACD)
        if 40 <= rsi <= 50 and macd_histogram > -0.2:
            return True, f"RSI={rsi:.1f} güçlenme sinyali"
        
        return False, "Alım için yeterli sinyal yok"
```

### 3.2 Çıkış (EXIT) Kuralları

```python
    # ─────────────────────────────────────────────────────────────
    # ÇIKIŞ (EXIT) KURALLARI
    # ─────────────────────────────────────────────────────────────
    
    @staticmethod
    def should_sell(
        rsi: float, 
        macd_histogram: float, 
        unrealized_pnl_pct: float,
        price_vs_sma: float
    ) -> tuple[bool, str]:
        """
        Satım/Redüksiyon sinyali kontrolü.
        
        Args:
            rsi: RSI değeri
            macd_histogram: MACD histogram
            unrealized_pnl_pct: Kar/Zarar yüzdesi
            price_vs_sma: Fiyatın SMA'ya göre durumu
        """
        # Kural 1: RSI aşırı alım
        if rsi > 70:
            return True, f"RSI={rsi:.1f} aşırı alım"
        
        # Kural 2: MACD negatif kesişim
        if macd_histogram < 0 and price_vs_sma < 0:
            return True, "MACD negatif, fiyat SMA altında"
        
        # Kural 3: Kar realizasyonu (RSI > 60 + kar > %5)
        if rsi > 60 and unrealized_pnl_pct > 5:
            return True, f"Kar realizasyonu: %{unrealized_pnl_pct:.1f}"
        
        # Kural 4: SMA kesiti aşağı
        if price_vs_sma < -3:
            return True, f"Fiyat SMA'nın %{price_vs_sma:.1f} altında"
        
        return False, "Satım için yeterli sinyal yok"
```

### 3.3 Stop-Loss Kuralları

```python
    # ─────────────────────────────────────────────────────────────
    # STOP-LOSS KURALLARI
    # ─────────────────────────────────────────────────────────────
    
    @staticmethod
    def should_stop_loss(
        unrealized_pnl_pct: float,
        consecutive_red_days: int,
        market_crash: bool
    ) -> tuple[bool, str, str]:
        """
        Stop-loss tetikleme.
        
        Returns:
            (triggered, reason, action)
            action: "STOP_LOSS" | "REDUCE" | "HOLD"
        """
        # Kritik stop-loss: %10 zarar
        if unrealized_pnl_pct < -10:
            return True, f"Zarar limiti: %{unrealized_pnl_pct:.1f}", "STOP_LOSS"
        
        # Güçlü düşüş trendi: %7 zarar + 3 gün düşüş
        if unrealized_pnl_pct < -7 and consecutive_red_days >= 3:
            return True, f"Teknik kırılma: %{unrealized_pnl_pct:.1f} + {consecutive_red_days} düşüş", "STOP_LOSS"
        
        # Piyasa çöküşü: %5 zarar + market_crash
        if market_crash and unrealized_pnl_pct < -5:
            return True, f"Piyasa çöküşü: %{unrealized_pnl_pct:.1f}", "REDUCE"
        
        # Azalt: %5 zarar
        if unrealized_pnl_pct < -5:
            return True, f"Zarar azaltma: %{unrealized_pnl_pct:.1f}", "REDUCE"
        
        return False, "Stop-loss yok", "HOLD"
```

### 3.4 Pozisyon Boyutlandırma

```python
    # ─────────────────────────────────────────────────────────────
    # POZİSYON BOYUTLANDIRMA
    # ─────────────────────────────────────────────────────────────
    
    @staticmethod
    def calculate_position_size(
        action: str,
        current_weight: float,
        kelly_fraction: float,
        confidence: float,
        unrealized_pnl_pct: float
    ) -> float:
        """
        Yeni pozisyon büyüklüğünü hesapla.
        
        Returns:
            Yeni pozisyon ağırlığı (0.0 - 0.25 arası)
        """
        max_weight = 0.25  # Max %25 tek hisse
        min_weight = 0.02  # Min %2 (çok küçük pozisyon alma)
        
        if action == "BUY":
            # Kelly fraction * güven skoru
            base_size = kelly_fraction * confidence
            
            # Karda pozisyon azalt
            if unrealized_pnl_pct > 10:
                base_size *= 0.5
            
            # Yeni pozisyon
            new_weight = current_weight + base_size
            return min(new_weight, max_weight)
        
        elif action in ("REDUCE", "SELL"):
            # Satış: Kelly fraction kadar azalt
            reduce_amount = kelly_fraction * 0.5
            new_weight = max(current_weight - reduce_amount, 0)
            return new_weight
        
        elif action == "STOP_LOSS":
            # Tam satış
            return 0.0
        
        return current_weight  # HOLD
```

---

## 4. Karar Motoru

```python
# services/trading_robot/src/trading_robot/decision_engine.py

class RuleBasedDecisionEngine:
    """
    Kural setine dayalı karar motoru.
    ML yok, sadece kurallar.
    """
    
    def __init__(self):
        self.rules = TradingRules()
    
    async def make_decision(
        self,
        ticker: str,
        portfolio: PortfolioState,
        market_data: MarketIndicators
    ) -> TradingDecision:
        """
        Karar üret.
        """
        # 1. Stop-loss kontrolü (önce risk!)
        stop_triggered, stop_reason, stop_action = self.rules.should_stop_loss(
            unrealized_pnl_pct=portfolio.unrealized_pnl_pct,
            consecutive_red_days=market_data.consecutive_red_days,
            market_crash=market_data.is_market_crash
        )
        
        if stop_triggered:
            return TradingDecision(
                action=stop_action,
                ticker=ticker,
                confidence=0.95,
                reason=stop_reason,
                urgency="HIGH"
            )
        
        # 2. Satım sinyali kontrolü
        should_sell, sell_reason = self.rules.should_sell(
            rsi=market_data.rsi,
            macd_histogram=market_data.macd_histogram,
            unrealized_pnl_pct=portfolio.unrealized_pnl_pct,
            price_vs_sma=market_data.price_vs_sma_pct
        )
        
        if should_sell:
            new_weight = self.rules.calculate_position_size(
                action="SELL",
                current_weight=portfolio.current_weight,
                kelly_fraction=portfolio.kelly_fraction,
                confidence=0.7,
                unrealized_pnl_pct=portfolio.unrealized_pnl_pct
            )
            return TradingDecision(
                action="SELL" if new_weight == 0 else "REDUCE",
                ticker=ticker,
                confidence=0.75,
                reason=sell_reason,
                target_weight=new_weight,
                urgency="MEDIUM"
            )
        
        # 3. Alım sinyali kontrolü
        should_buy, buy_reason = self.rules.should_buy(
            rsi=market_data.rsi,
            macd_histogram=market_data.macd_histogram,
            price_vs_sma=market_data.price_vs_sma_pct
        )
        
        if should_buy:
            new_weight = self.rules.calculate_position_size(
                action="BUY",
                current_weight=portfolio.current_weight,
                kelly_fraction=portfolio.kelly_fraction,
                confidence=0.7,
                unrealized_pnl_pct=0  # Yeni pozisyon için 0
            )
            
            # Mevcut pozisyon varsa HOLD
            if portfolio.current_weight > 0.05:
                return TradingDecision(
                    action="HOLD",
                    ticker=ticker,
                    confidence=0.6,
                    reason=f"Mevcut pozisyon var: %{portfolio.current_weight*100:.1f}",
                    urgency="LOW"
                )
            
            return TradingDecision(
                action="BUY",
                ticker=ticker,
                confidence=0.7,
                reason=buy_reason,
                target_weight=new_weight,
                urgency="MEDIUM"
            )
        
        # 4. Hiçbir sinyal yok = HOLD
        return TradingDecision(
            action="HOLD",
            ticker=ticker,
            confidence=0.5,
            reason="Yeterli sinyal yok",
            urgency="LOW"
        )
```

---

## 5. Risk Yönetimi

```python
# services/trading_robot/src/trading_robot/risk_manager.py

class RiskManager:
    """
    Risk kontrol katmanı.
    Karar uygulanmadan önce tüm kontrollerden geçer.
    """
    
    @staticmethod
    def validate(decision: TradingDecision, portfolio: PortfolioState) -> RiskCheck:
        """
        Risk kontrolü yap.
        """
        checks = []
        
        # 1. Pozisyon büyüklüğü kontrolü
        if decision.target_weight and decision.target_weight > 0.25:
            checks.append(RiskResult(
                rule="MAX_POSITION",
                passed=False,
                message="Pozisyon %25 geçemez"
            ))
        else:
            checks.append(RiskResult(
                rule="MAX_POSITION",
                passed=True
            ))
        
        # 2. Günlük işlem sayısı
        daily_trades = portfolio.daily_trade_count
        if daily_trades >= 5:
            checks.append(RiskResult(
                rule="DAILY_TRADE_LIMIT",
                passed=False,
                message=f"Günlük işlem limiti doldu: {daily_trades}/5"
            ))
        else:
            checks.append(RiskResult(
                rule="DAILY_TRADE_LIMIT",
                passed=True
            ))
        
        # 3. Günlük zarar limiti
        if portfolio.daily_pnl_pct < -3:
            checks.append(RiskResult(
                rule="DAILY_LOSS_LIMIT",
                passed=False,
                message=f"Günlük zarar limiti: %{portfolio.daily_pnl_pct:.1f}"
            ))
        else:
            checks.append(RiskResult(
                rule="DAILY_LOSS_LIMIT",
                passed=True
            ))
        
        # 4. Likidite kontrolü (opsiyonel)
        if decision.action in ("BUY", "SELL") and not portfolio.has_sufficient_cash:
            checks.append(RiskResult(
                rule="LIQUIDITY",
                passed=False,
                message="Yetersiz nakit"
            ))
        else:
            checks.append(RiskResult(
                rule="LIQUIDITY",
                passed=True
            ))
        
        all_passed = all(c.passed for c in checks)
        
        return RiskCheck(
            passed=all_passed,
            checks=checks,
            can_execute=all_passed or decision.urgency == "HIGH"
        )
```

### Risk Kuralları Özeti

| Kural | Limit | Açıklama |
|-------|-------|----------|
| MAX_POSITION | %25 | Tek hisse portföyün %25'ini geçemez |
| DAILY_TRADE_LIMIT | 5 | Günde max 5 işlem |
| DAILY_LOSS_LIMIT | -%3 | Günlük zarar %3'ü geçemez |
| MIN_CONFIDENCE | 0.6 | Min %60 güven eşiği |
| STOP_LOSS_HARD | -%10 | Zorunlu stop-loss |

---

## 6. Broker API Entegrasyonları

### 6.1 Midas API

```python
# services/trading_robot/src/trading_robot/broker_clients/midas.py

class MidasClient:
    """
    Midas API client - Borsa İstanbul yatırımcıları için.
    """
    
    BASE_URL = "https://api.midas.com.tr/v1"
    
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
    
    async def get_portfolio(self) -> list[Position]:
        """
        Portföydeki tüm pozisyonları getir.
        
        Returns:
            [{"ticker": "THYAO", "quantity": 100, "avg_cost": 245.50}, ...]
        """
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.BASE_URL}/portfolio",
                headers=self._get_headers()
            ) as resp:
                data = await resp.json()
                return [Position(**p) for p in data.get("positions", [])]
    
    async def get_position(self, ticker: str) -> Position | None:
        """Belirli bir hissenin detayı"""
        positions = await self.get_portfolio()
        for p in positions:
            if p.ticker == ticker:
                return p
        return None
    
    async def place_order(
        self, 
        ticker: str, 
        side: str, 
        quantity: int, 
        price: float
    ) -> OrderResult:
        """
        Emir gönder.
        
        Args:
            ticker: Hisse kodu (örn: "THYAO")
            side: "BUY" veya "SELL"
            quantity: Lot sayısı (BIST'te 1 lot = 100 adet)
            price: Emir fiyatı
        """
        async with aiohttp.ClientSession() as session:
            payload = {
                "symbol": ticker,
                "side": side,
                "quantity": quantity,
                "price": price,
                "order_type": "LIMIT"
            }
            async with session.post(
                f"{self.BASE_URL}/orders",
                json=payload,
                headers=self._get_headers()
            ) as resp:
                data = await resp.json()
                return OrderResult(**data)
    
    async def cancel_order(self, order_id: str) -> bool:
        """Bekleyen emri iptal et"""
        async with aiohttp.ClientSession() as session:
            async with session.delete(
                f"{self.BASE_URL}/orders/{order_id}",
                headers=self._get_headers()
            ) as resp:
                return resp.status == 200
    
    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "X-API-Secret": self.api_secret,
            "Content-Type": "application/json"
        }
```

### 6.2 Akbank API

```python
# services/trading_robot/src/trading_robot/broker_clients/akbank.py

class AkbankClient:
    """
    Akbank/Ak Yatırım API client.
    """
    
    BASE_URL = "https://api.akbank.com.tr/investment/v1"
    
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
    
    async def get_holdings(self) -> list[AkbankPosition]:
        """
        Dönen pozisyonları getir.
        
        Returns:
            [{"symbol": "THYAO", "amount": 500, "avgPrice": 242.30}, ...]
        """
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.BASE_URL}/holdings",
                headers=self._get_headers()
            ) as resp:
                data = await resp.json()
                return [AkbankPosition(**h) for h in data.get("holdings", [])]
    
    async def get_account_balance(self) -> AccountBalance:
        """Nakit bakiye"""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.BASE_URL}/account/balance",
                headers=self._get_headers()
            ) as resp:
                data = await resp.json()
                return AccountBalance(**data)
    
    async def send_order(self, order: OrderRequest) -> OrderResponse:
        """Emir gönder"""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.BASE_URL}/orders",
                json=order.model_dump(),
                headers=self._get_headers()
            ) as resp:
                data = await resp.json()
                return OrderResponse(**data)
    
    def _get_headers(self) -> dict:
        return {
            "API-Key": self.api_key,
            "API-Secret": self.api_secret,
            "Content-Type": "application/json"
        }
```

### 6.3 Modeller

```python
# services/trading_robot/src/trading_robot/models.py

from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from enum import Enum

class Action(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    REDUCE = "REDUCE"
    HOLD = "HOLD"
    STOP_LOSS = "STOP_LOSS"

class Position(BaseModel):
    ticker: str
    quantity: int           # Lot (BIST: 100 adet = 1 lot)
    avg_cost: float        # Ortalama maliyet TL
    current_price: float
    unrealized_pnl: float  # Kar/Zarar TL
    unrealized_pnl_pct: float

class PortfolioState(BaseModel):
    portfolio_id: str
    total_value: float
    cash: float
    positions: list[Position]
    daily_pnl_pct: float
    daily_trade_count: int
    kelly_fraction: float = 0.25
    has_sufficient_cash: bool = True

class MarketIndicators(BaseModel):
    ticker: str
    price: float
    rsi: float
    macd: float
    macd_signal: float
    macd_histogram: float
    sma_20: float
    sma_50: float
    price_vs_sma_pct: float
    volume: int
    consecutive_red_days: int = 0
    is_market_crash: bool = False

class TradingDecision(BaseModel):
    decision_id: str
    ticker: str
    action: Action
    confidence: float
    reason: str
    urgency: str  # HIGH, MEDIUM, LOW
    target_weight: Optional[float] = None
    estimated_lot_change: Optional[int] = None

class RiskResult(BaseModel):
    rule: str
    passed: bool
    message: Optional[str] = None

class RiskCheck(BaseModel):
    passed: bool
    checks: list[RiskResult]
    can_execute: bool
```

---

## 7. Veritabanı Şeması

### 7.1 Trading Decisions

```sql
-- Trading decisions log
CREATE TABLE trading.decisions (
    id BIGSERIAL PRIMARY KEY,
    decision_id UUID NOT NULL UNIQUE,
    portfolio_id UUID NOT NULL,
    ticker VARCHAR(10) NOT NULL,
    action VARCHAR(20) NOT NULL,
    confidence DECIMAL(3, 2) NOT NULL,
    reason TEXT NOT NULL,
    urgency VARCHAR(10) NOT NULL,
    
    -- Piyasa durumu
    rsi DECIMAL(5, 2),
    macd_histogram DECIMAL(10, 4),
    price_vs_sma_pct DECIMAL(5, 2),
    
    -- Portföy durumu
    current_weight DECIMAL(5, 4),
    target_weight DECIMAL(5, 4),
    unrealized_pnl_pct DECIMAL(5, 2),
    
    -- Risk
    risk_check_passed BOOLEAN,
    risk_details JSONB,
    
    -- Execution
    execution_mode VARCHAR(20) NOT NULL,  -- 'advisory' | 'auto_trade'
    status VARCHAR(20) NOT NULL,         -- 'pending' | 'approved' | 'executed' | 'rejected'
    executed_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_trading_decisions_portfolio_ticker 
ON trading.decisions(portfolio_id, ticker, created_at DESC);

CREATE INDEX idx_trading_decisions_created_at 
ON trading.decisions(created_at DESC);
```

### 7.2 Technical Indicators

```sql
-- Teknik indicator history (cache)
CREATE TABLE market_data.technical_indicators (
    id BIGSERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    rsi_14 DECIMAL(5, 2),
    macd DECIMAL(10, 4),
    macd_signal DECIMAL(10, 4),
    macd_histogram DECIMAL(10, 4),
    sma_20 DECIMAL(10, 2),
    sma_50 DECIMAL(10, 2),
    price DECIMAL(10, 2),
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_technical_indicators_ticker_time 
ON market_data.technical_indicators(ticker, recorded_at DESC);
```

### 7.3 Broker Connections

```sql
-- Broker entegrasyonları
CREATE TABLE integrations.broker_connections (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL,
    broker VARCHAR(20) NOT NULL,          -- 'midas' | 'akbank'
    api_key_encrypted BYTEA NOT NULL,       -- Şifreli
    api_secret_encrypted BYTEA NOT NULL,    -- Şifreli
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_sync_at TIMESTAMPTZ
);

CREATE INDEX idx_broker_connections_user 
ON integrations.broker_connections(user_id);
```

### 7.4 Real-time Features (Redis backup)

```sql
-- Feature store (historical, Redis'ten backup)
CREATE TABLE features.realtime_features (
    id BIGSERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    portfolio_id UUID NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Fiyat
    price DECIMAL(10, 2),
    
    -- Teknik
    rsi_14 DECIMAL(5, 2),
    macd DECIMAL(10, 4),
    macd_histogram DECIMAL(10, 4),
    sma_20 DECIMAL(10, 2),
    price_vs_sma_pct DECIMAL(5, 2),
    
    -- Portföy
    user_avg_cost DECIMAL(10, 2),
    user_position_size DECIMAL(5, 4),
    unrealized_pnl_pct DECIMAL(5, 2),
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_realtime_features_ticker_time 
ON features.realtime_features(ticker, recorded_at DESC);
```

---

## 8. Web Panel Tasarımı

### 8.1 Ana Dashboard

```
┌─────────────────────────────────────────────────────────────────────────┐
│  TRADING ROBOT - REAL-TIME                                    [⚙️] [👤]│
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌────────────────────────┐  ┌────────────────────────────────────────┐│
│  │ PORTFÖY                 │  │ 📊 AKTİF POZİSYONLAR                   ││
│  │ ────────────           │  │ ────────────────────────────            ││
│  │ Toplam: ₺1,245,000     │  │                                        ││
│  │ Bugün: +₺12,450 (+1%) │  │ THYAO  ●●●●●  %15    +₺5,000  Karda   ││
│  │ Hafta: +₺34,200 (+2.8%)│  │ EREGL  ●●●○○  %8     +₺890    Karda   ││
│  │                         │  │ ASELS  ●●○○○  %5     -₺1,200  Zararda  ││
│  │ Kural: Aktif 🟢        │  │                                        ││
│  │ Mode: Auto ● Manual    │  │                                        ││
│  └────────────────────────┘  └────────────────────────────────────────┘│
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐│
│  │ SON KARARLAR                                                        ││
│  │ ────────────                                                        ││
│  │ 14:32  THYAO  BUY   %15 → %18    ✅ Uygulandı                     ││
│  │        RSI=32, aşırı satım bölgesi                                 ││
│  │                                                                       ││
│  │ 13:45  ASELS  REDUCE %8 → %5      ✅ Uygulandı                     ││
│  │        Kar realizasyonu: +%6.2                                         ││
│  │                                                                       ││
│  │ 11:20  EREGL  HOLD             ❌ Reddedildi (risk kontrolü)        ││
│  │        Pozisyon limiti aşıldı                                        ││
│  └────────────────────────────────────────────────────────────────────┘│
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐│
│  │ GRAFİK: THYAO  [1D] [1H] [15m]                        📊 [Ayarlar]││
│  │                                                                       ││
│  │  RSI: 32 🟢 (aşırı satım)                                           ││
│  │  MACD: ▲ Pozitif                                                    ││
│  │  SMA: Fiyat SMA20 üzerinde (+%2.3)                                  ││
│  │                                                                       ││
│  │  Ortalama Maliyet: ₺245  ─ ─ ─  Piyasa: ₺250                       ││
│  └────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────┘
```

### 8.2 Karar Kartı

```
┌────────────────────────────────────────┐
│ THYAO  ●  BUY                         │
│ ────────────────────────────────────── │
│                                        │
│ Güven Skoru: ●●●●○ (%72)             │
│                                        │
│ 📊 Sinyaller:                          │
│   • RSI: 32 🟢 (aşırı satım)         │
│   • MACD: ▲ Pozitif histogram         │
│   • SMA: Fiyat SMA20 üzerinde         │
│                                        │
│ 💰 Pozisyonum:                         │
│   • Mevcut: 1000 lot (%15)           │
│   • Ort. Maliyet: ₺245                │
│   • Kar: +₺5,000 (+%2.04)            │
│                                        │
│ 🎯 Öneri:                              │
│   • Yeni pozisyon: +200 lot           │
│   • Hedef ağırlık: %18               │
│   • Stop-loss: ₺235 (-%4)            │
│                                        │
│ [✓ Onayla]  [✗ Reddet]  [⏸ı Beklet]   │
│                                        │
└────────────────────────────────────────┘
```

---

## 9. Servis Yapısı

```
services/
├── trading_robot/
│   ├── pyproject.toml
│   └── src/
│       └── trading_robot/
│           ├── __init__.py
│           ├── __main__.py
│           ├── config.py
│           ├── models.py              # Pydantic models
│           ├── rules.py               # Trading kuralları
│           ├── decision_engine.py     # Karar motoru
│           ├── risk_manager.py        # Risk kontrolü
│           ├── broker_clients/        # Broker API clients
│           │   ├── __init__.py
│           │   ├── base.py
│           │   ├── midas.py
│           │   └── akbank.py
│           ├── feature_store.py       # Redis cache
│           ├── handlers.py            # API endpoints
│           └── service.py             # Main service
```

---

## 10. Performans Hedefleri

| Metric | Hedef | Acceptable |
|--------|-------|------------|
| Karar gecikmesi (fiyat → karar) | < 200ms | < 500ms |
| Web panel güncelleme | < 100ms | < 200ms |
| Broker emir gönderim | < 500ms | < 1000ms |
| Sistem uptime | > 99.5% | > 99% |
| Yanlış sinyal oranı | < %30 | < %40 |

### Redis Key Yapısı

```
# Real-time features
feature:{ticker}:price           # Anlık fiyat
feature:{ticker}:rsi             # RSI değeri
feature:{ticker}:macd_histogram  # MACD histogram
feature:{ticker}:sma_20           # SMA20 değeri

# Portföy cache
portfolio:{portfolio_id}:{ticker}:position    # Pozisyon bilgisi
portfolio:{portfolio_id}:{ticker}:avg_cost    # Ortalama maliyet
portfolio:{portfolio_id}:cash                  # Nakit

# Sistem durumu
system:portfolio:{portfolio_id}:daily_trades   # Günlük işlem sayısı
system:portfolio:{portfolio_id}:daily_pnl     # Günlük kar/zarar
```

---

## 11. Implementasyon Planı

| Faz | Görev | Süre | Öncelik |
|-----|-------|------|----------|
| 1 | Broker API clients (Midas + Akbank) | 3 gün | 🔴 Yüksek |
| 2 | Feature store (Redis) | 2 gün | 🔴 Yüksek |
| 3 | Rule engine + Decision logic | 3 gün | 🔴 Yüksek |
| 4 | Risk manager | 2 gün | 🔴 Yüksek |
| 5 | WebSocket + Real-time updates | 3 gün | 🟡 Orta |
| 6 | Web panel (Next.js) | 5 gün | 🟡 Orta |
| 7 | Entegrasyon test + deployment | 3 gün | 🟡 Orta |

**Toplam: ~3 hafta**

### Aşama Detayları

#### Faz 1: Broker API (3 gün)
- Midas client implementasyonu
- Akbank client implementasyonu
- Credential encryption
- Rate limiting handling

#### Faz 2: Feature Store (2 gün)
- Redis connection pool
- Feature update handlers
- Cache invalidation
- Backup to PostgreSQL

#### Faz 3: Rule Engine (3 gün)
- Trading rules sınıfı
- Decision engine
- Unit test'ler
- Backtest script

#### Faz 4: Risk Manager (2 gün)
- Risk validation
- Position sizing
- Daily limits
- Emergency stop

#### Faz 5: WebSocket (3 gün)
- Redis pub/sub
- Client connection management
- Real-time updates
- Reconnection handling

#### Faz 6: Web Panel (5 gün)
- Next.js app setup
- Dashboard layout
- Real-time karar gösterimi
- Onay/reddet mekanizması

#### Faz 7: Entegrasyon (3 gün)
- End-to-end test
- Load test
- Deployment
- Monitoring setup

---

## 📎 Ekler

### A. Ortalama Maliyet Hesabı

```python
def calculate_average_cost(trades: list[Trade]) -> float:
    """
    Ortalama maliyet = Σ(Alım lot × fiyat) - Σ(Satım lot × fiyat) / Net lot
    """
    total_cost = 0
    net_lot = 0
    
    for trade in sorted(trades, key=lambda t: t.timestamp):
        if trade.side == "BUY":
            total_cost += trade.quantity * trade.price
            net_lot += trade.quantity
        else:
            remaining = trade.quantity
            while remaining > 0 and net_lot > 0:
                if remaining <= net_lot:
                    avg_buy_price = total_cost / net_lot
                    total_cost -= remaining * avg_buy_price
                    net_lot -= remaining
                    remaining = 0
                else:
                    remaining -= net_lot
                    net_lot = 0
                    total_cost = 0
    
    return total_cost / net_lot if net_lot > 0 else 0
```

### B. Kelly Criterion

```python
def calculate_kelly_fraction(win_rate: float, avg_win: float, avg_loss: float) -> float:
    """
    Kelly Criterion: Optimal bahis büyüklüğü
    
    Kelly % = W - (1-W)/R
    W = Kazanma oranı
    R = Ortalama kazanç / Ortalama kayıp
    """
    if avg_loss == 0:
        return 0.25  # Default max
    
    win_loss_ratio = avg_win / avg_loss
    kelly = win_rate - ((1 - win_rate) / win_loss_ratio)
    
    # Kelly'yi max %25 ile sınırla (conservative)
    return min(max(kelly, 0), 0.25)
```

---

**Doküman Versiyonları:**

| Versiyon | Tarih | Yazar | Değişiklik |
|----------|-------|-------|------------|
| 1.0 | 2026-07-31 | AI Assistant | İlk taslak - Kural bazlı sistem |

---

*Bu doküman FinanceAutomations projesi için hazırlanmıştır.*
