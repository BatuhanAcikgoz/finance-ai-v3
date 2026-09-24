"""Technical indicators computation."""
from typing import Any

import pandas as pd
import pandas_ta as ta

from technical_analysis.config import settings


class TechnicalIndicators:
    """Compute technical indicators for financial data."""

    @staticmethod
    def compute_all(closes: pd.Series, highs: pd.Series, lows: pd.Series, volumes: pd.Series) -> dict[str, Any]:
        """
        Compute all technical indicators.

        Args:
            closes: Closing prices
            highs: High prices
            lows: Low prices
            volumes: Volume data

        Returns:
            Dictionary of computed indicators
        """
        indicators = {}

        # Trend indicators
        indicators.update(TechnicalIndicators._compute_trend(closes, highs, lows))

        # Momentum indicators
        indicators.update(TechnicalIndicators._compute_momentum(closes, highs, lows))

        # Volatility indicators
        indicators.update(TechnicalIndicators._compute_volatility(closes, highs, lows))

        # Volume indicators
        indicators.update(TechnicalIndicators._compute_volume(closes, volumes))

        # Signal events
        indicators["signals"] = TechnicalIndicators._detect_signals(closes, volumes, indicators)

        return indicators

    @staticmethod
    def _compute_trend(closes: pd.Series, highs: pd.Series, lows: pd.Series) -> dict[str, Any]:
        """Compute trend indicators."""
        result = {}

        # SMA
        for period in settings.sma_periods:
            if len(closes) >= period:
                result[f"sma_{period}"] = float(closes.rolling(period).mean().iloc[-1])

        # EMA
        for period in settings.ema_periods:
            if len(closes) >= period:
                result[f"ema_{period}"] = float(closes.ewm(span=period).mean().iloc[-1])

        # MACD
        if len(closes) >= settings.macd_slow:
            macd = ta.macd(closes, fast=settings.macd_fast, slow=settings.macd_slow, signal=settings.macd_signal)
            result["macd"] = float(macd[f"MACD_{settings.macd_fast}_{settings.macd_slow}_{settings.macd_signal}"].iloc[-1])
            result["macd_signal"] = float(macd[f"MACDs_{settings.macd_fast}_{settings.macd_slow}_{settings.macd_signal}"].iloc[-1])
            result["macd_hist"] = float(macd[f"MACDh_{settings.macd_fast}_{settings.macd_slow}_{settings.macd_signal}"].iloc[-1])

        # ADX
        if len(closes) >= 14:
            adx = ta.adx(high=closes, low=closes, close=closes, length=14)
            result["adx"] = float(adx["ADX_14"].iloc[-1])

        # Parabolic SAR
        if len(closes) >= 2:
            psar = ta.psar(high=highs, low=lows, close=closes)
            result["psar"] = float(psar["PSARl_0.02_0.2"].iloc[-1])

        return result

    @staticmethod
    def _compute_momentum(closes: pd.Series, highs: pd.Series, lows: pd.Series) -> dict[str, Any]:
        """Compute momentum indicators."""
        result = {}

        # RSI
        if len(closes) >= settings.rsi_period:
            rsi = ta.rsi(closes, length=settings.rsi_period)
            result["rsi"] = float(rsi.iloc[-1])

        # Stochastic
        if len(closes) >= settings.stochastic_period:
            stoch = ta.stoch(high=highs, low=lows, close=closes, k=settings.stochastic_period)
            result["stoch_k"] = float(stoch[f"STOCHk_{settings.stochastic_period}_3_3"].iloc[-1])
            result["stoch_d"] = float(stoch[f"STOCHd_{settings.stochastic_period}_3_3"].iloc[-1])

        # Williams %R
        if len(closes) >= 14:
            willr = ta.willr(high=highs, low=lows, close=closes, length=14)
            result["williams_r"] = float(willr.iloc[-1])

        # CCI
        if len(closes) >= 20:
            cci = ta.cci(high=highs, low=lows, close=closes, length=20)
            result["cci"] = float(cci.iloc[-1])

        return result

    @staticmethod
    def _compute_volatility(closes: pd.Series, highs: pd.Series, lows: pd.Series) -> dict[str, Any]:
        """Compute volatility indicators."""
        result = {}

        # Bollinger Bands
        if len(closes) >= settings.bollinger_period:
            bb = ta.bbands(close=closes, length=settings.bollinger_period, std=settings.bollinger_std)
            result["bb_upper"] = float(bb[f"BBU_{settings.bollinger_period}_{settings.bollinger_std}"].iloc[-1])
            result["bb_middle"] = float(bb[f"BBM_{settings.bollinger_period}_{settings.bollinger_std}"].iloc[-1])
            result["bb_lower"] = float(bb[f"BBL_{settings.bollinger_period}_{settings.bollinger_std}"].iloc[-1])
            result["bb_width"] = float(bb[f"BBB_{settings.bollinger_period}_{settings.bollinger_std}"].iloc[-1])
            result["bb_percent"] = float(bb[f"BBP_{settings.bollinger_period}_{settings.bollinger_std}"].iloc[-1])

        # ATR
        if len(closes) >= settings.atr_period:
            atr = ta.atr(high=highs, low=lows, close=closes, length=settings.atr_period)
            result["atr"] = float(atr.iloc[-1])

        # Keltner Channels
        if len(closes) >= 20:
            kc = ta.kc(high=highs, low=lows, close=closes, length=20)
            result["kc_upper"] = float(kc["KCUu_20_2"].iloc[-1])
            result["kc_middle"] = float(kc["KCBu_20_2"].iloc[-1])
            result["kc_lower"] = float(kc["KCLu_20_2"].iloc[-1])

        return result

    @staticmethod
    def _compute_volume(closes: pd.Series, volumes: pd.Series) -> dict[str, Any]:
        """Compute volume indicators."""
        result = {}

        # OBV
        if len(volumes) > 0:
            result["obv"] = float(ta.obv(close=closes, volume=volumes).iloc[-1])

        # VWAP
        if len(volumes) >= 1:
            typical_price = (closes * volumes).sum() / volumes.sum() if volumes.sum() > 0 else closes.iloc[-1]
            result["vwap"] = float(typical_price)

        # MFI
        if len(closes) >= 14:
            mfi = ta.mfi(high=closes, low=closes, close=closes, volume=volumes, length=14)
            result["mfi"] = float(mfi.iloc[-1])

        # CMF
        if len(closes) >= 20:
            cmf = ta.cmf(high=closes, low=closes, close=closes, volume=volumes, length=20)
            result["cmf"] = float(cmf.iloc[-1])

        return result

    @staticmethod
    def _detect_signals(
        closes: pd.Series,
        volumes: pd.Series,
        indicators: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Detect trading signals from indicators."""
        signals = []

        # Golden Cross / Death Cross
        if "sma_50" in indicators and "sma_200" in indicators:
            if len(closes) >= 51:
                sma_50_prev = closes.rolling(50).mean().iloc[-2]
                sma_200_prev = closes.rolling(200).mean().iloc[-2]
                sma_50_curr = indicators["sma_50"]
                sma_200_curr = indicators["sma_200"]

                if sma_50_prev <= sma_200_prev and sma_50_curr > sma_200_curr:
                    signals.append({
                        "type": "GOLDEN_CROSS",
                        "direction": "BULLISH",
                        "strength": 0.9,
                        "description": "SMA50 crossed above SMA200",
                    })
                elif sma_50_prev >= sma_200_prev and sma_50_curr < sma_200_curr:
                    signals.append({
                        "type": "DEATH_CROSS",
                        "direction": "BEARISH",
                        "strength": 0.9,
                        "description": "SMA50 crossed below SMA200",
                    })

        # RSI signals
        if "rsi" in indicators:
            rsi = indicators["rsi"]
            if rsi > 70:
                signals.append({
                    "type": "RSI_OVERBOUGHT",
                    "direction": "BEARISH",
                    "strength": 0.7,
                    "description": f"RSI at {rsi:.2f} - overbought",
                })
            elif rsi < 30:
                signals.append({
                    "type": "RSI_OVERSOLD",
                    "direction": "BULLISH",
                    "strength": 0.7,
                    "description": f"RSI at {rsi:.2f} - oversold",
                })

        # MACD crossover
        if "macd" in indicators and "macd_signal" in indicators:
            if len(closes) >= 27:
                macd_prev = ta.macd(closes, fast=12, slow=26, signal=9)
                macd_curr = indicators["macd"]
                signal_curr = indicators["macd_signal"]
                macd_line_prev = macd_prev["MACD_12_26_9"].iloc[-2]
                signal_line_prev = macd_prev["MACDs_12_26_9"].iloc[-2]

                if macd_line_prev <= signal_line_prev and macd_curr > signal_curr:
                    signals.append({
                        "type": "MACD_BULLISH_CROSSOVER",
                        "direction": "BULLISH",
                        "strength": 0.6,
                        "description": "MACD crossed above signal line",
                    })
                elif macd_line_prev >= signal_line_prev and macd_curr < signal_curr:
                    signals.append({
                        "type": "MACD_BEARISH_CROSSOVER",
                        "direction": "BEARISH",
                        "strength": 0.6,
                        "description": "MACD crossed below signal line",
                    })

        # Bollinger breakout
        if "bb_upper" in indicators and "bb_lower" in indicators:
            current_price = closes.iloc[-1]
            if current_price > indicators["bb_upper"]:
                signals.append({
                    "type": "BOLLINGER_UPPER_BREAKOUT",
                    "direction": "BULLISH",
                    "strength": 0.5,
                    "description": "Price broke above upper Bollinger Band",
                })
            elif current_price < indicators["bb_lower"]:
                signals.append({
                    "type": "BOLLINGER_LOWER_BREAKOUT",
                    "direction": "BEARISH",
                    "strength": 0.5,
                    "description": "Price broke below lower Bollinger Band",
                })

        # Volume spike
        if len(volumes) >= 20:
            vol_mean = volumes.rolling(20).mean().iloc[-1]
            vol_std = volumes.rolling(20).std().iloc[-1]
            current_vol = volumes.iloc[-1]
            if vol_std > 0:
                z_score = (current_vol - vol_mean) / vol_std
                if z_score > settings.volume_spike_threshold:
                    signals.append({
                        "type": "VOLUME_SPIKE",
                        "direction": "NEUTRAL",
                        "strength": min(z_score / 5, 1.0),
                        "description": f"Volume spike: {z_score:.1f} standard deviations",
                    })

        return signals
