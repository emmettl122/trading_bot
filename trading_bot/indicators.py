"""
Technical Indicators Module.

This module provides comprehensive technical indicator calculations including:
- RSI (Relative Strength Index)
- MACD (Moving Average Convergence Divergence)
- Bollinger Bands
- ATR (Average True Range)
- Stochastic Oscillator
- Divergence detection
- Moving averages (SMA, EMA)

Author: AMT Trading Bot
Version: 1.0.0
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from collections import deque

from config import (
    OHLCV,
    RSIData,
    MACDData,
    BollingerBands,
    StochasticData,
    IndicatorSet,
    IndicatorConfig,
    get_default_config,
)


class TechnicalIndicators:
    """
    Calculates and tracks technical indicators.

    This class provides methods for calculating common technical
    indicators used in trading analysis.

    Attributes:
        config: Indicator configuration settings.
    """

    def __init__(self, config: Optional[IndicatorConfig] = None):
        """
        Initialize the Technical Indicators calculator.

        Args:
            config: Optional configuration. Uses defaults if not provided.
        """
        self.config = config or get_default_config().indicators
        self._price_history: deque = deque(maxlen=500)
        self._high_history: deque = deque(maxlen=500)
        self._low_history: deque = deque(maxlen=500)
        self._close_history: deque = deque(maxlen=500)
        self._volume_history: deque = deque(maxlen=500)
        self._rsi_history: deque = deque(maxlen=100)
        self._macd_history: deque = deque(maxlen=100)

    def update(self, candle: OHLCV):
        """
        Update indicator history with new candle data.

        Args:
            candle: New OHLCV candle.
        """
        self._price_history.append(candle.close)
        self._high_history.append(candle.high)
        self._low_history.append(candle.low)
        self._close_history.append(candle.close)
        self._volume_history.append(candle.volume)

    def calculate_sma(
        self,
        data: Optional[List[float]] = None,
        period: int = 20
    ) -> float:
        """
        Calculate Simple Moving Average.

        Args:
            data: Price data. Uses internal history if not provided.
            period: SMA period.

        Returns:
            SMA value.
        """
        if data is None:
            data = list(self._close_history)

        if len(data) < period:
            return data[-1] if data else 0.0

        return sum(data[-period:]) / period

    def calculate_ema(
        self,
        data: Optional[List[float]] = None,
        period: int = 20
    ) -> float:
        """
        Calculate Exponential Moving Average.

        Args:
            data: Price data. Uses internal history if not provided.
            period: EMA period.

        Returns:
            EMA value.
        """
        if data is None:
            data = list(self._close_history)

        if len(data) < period:
            return data[-1] if data else 0.0

        multiplier = 2 / (period + 1)
        ema = sum(data[:period]) / period  # Start with SMA

        for price in data[period:]:
            ema = (price - ema) * multiplier + ema

        return ema

    def calculate_rsi(
        self,
        data: Optional[List[float]] = None,
        period: Optional[int] = None
    ) -> RSIData:
        """
        Calculate Relative Strength Index.

        RSI measures the magnitude of recent price changes to evaluate
        overbought or oversold conditions.

        Args:
            data: Price data. Uses internal history if not provided.
            period: RSI period. Uses config default if not provided.

        Returns:
            RSIData with calculated values.
        """
        period = period or self.config.rsi_period

        if data is None:
            data = list(self._close_history)

        if len(data) < period + 1:
            return RSIData(value=50.0, is_overbought=False, is_oversold=False)

        # Calculate price changes
        changes = [data[i] - data[i-1] for i in range(1, len(data))]

        # Separate gains and losses
        gains = [max(0, c) for c in changes]
        losses = [abs(min(0, c)) for c in changes]

        # Calculate average gain/loss using Wilder's smoothing
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period

        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        # Calculate RSI
        if avg_loss == 0:
            rsi = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))

        # Check for divergence
        divergence = self._detect_rsi_divergence(data, rsi)

        self._rsi_history.append(rsi)

        return RSIData(
            value=rsi,
            is_overbought=rsi > self.config.rsi_overbought,
            is_oversold=rsi < self.config.rsi_oversold,
            divergence=divergence,
        )

    def _detect_rsi_divergence(
        self,
        prices: List[float],
        current_rsi: float
    ) -> Optional[str]:
        """
        Detect RSI divergence from price.

        Args:
            prices: Recent price data.
            current_rsi: Current RSI value.

        Returns:
            'bullish', 'bearish', or None.
        """
        if len(self._rsi_history) < 10 or len(prices) < 10:
            return None

        recent_prices = prices[-10:]
        recent_rsi = list(self._rsi_history)[-10:]
        recent_rsi.append(current_rsi)

        # Find price trend
        price_higher = recent_prices[-1] > recent_prices[0]
        price_lower = recent_prices[-1] < recent_prices[0]

        # Find RSI trend
        rsi_higher = recent_rsi[-1] > recent_rsi[0]
        rsi_lower = recent_rsi[-1] < recent_rsi[0]

        # Bearish divergence: price higher high, RSI lower high
        if price_higher and rsi_lower and current_rsi > 50:
            return 'bearish'

        # Bullish divergence: price lower low, RSI higher low
        if price_lower and rsi_higher and current_rsi < 50:
            return 'bullish'

        return None

    def calculate_macd(
        self,
        data: Optional[List[float]] = None,
        fast: Optional[int] = None,
        slow: Optional[int] = None,
        signal: Optional[int] = None
    ) -> MACDData:
        """
        Calculate MACD (Moving Average Convergence Divergence).

        MACD shows the relationship between two moving averages of price.

        Args:
            data: Price data. Uses internal history if not provided.
            fast: Fast EMA period. Uses config default if not provided.
            slow: Slow EMA period. Uses config default if not provided.
            signal: Signal line period. Uses config default if not provided.

        Returns:
            MACDData with calculated values.
        """
        fast = fast or self.config.macd_fast
        slow = slow or self.config.macd_slow
        signal = signal or self.config.macd_signal

        if data is None:
            data = list(self._close_history)

        if len(data) < slow + signal:
            return MACDData(
                macd_line=0.0,
                signal_line=0.0,
                histogram=0.0,
                is_bullish=True,
                crossover=None,
            )

        # Calculate EMAs
        fast_ema = self.calculate_ema(data, fast)
        slow_ema = self.calculate_ema(data, slow)

        # MACD line
        macd_line = fast_ema - slow_ema

        # Signal line (EMA of MACD)
        # We need historical MACD values
        macd_values = []
        for i in range(slow + signal, len(data) + 1):
            subset = data[:i]
            f_ema = self.calculate_ema(subset, fast)
            s_ema = self.calculate_ema(subset, slow)
            macd_values.append(f_ema - s_ema)

        signal_line = self.calculate_ema(macd_values, signal) if macd_values else macd_line

        # Histogram
        histogram = macd_line - signal_line

        # Detect crossover
        crossover = None
        if len(self._macd_history) > 0:
            prev_macd, prev_signal = self._macd_history[-1]
            if prev_macd <= prev_signal and macd_line > signal_line:
                crossover = 'bullish'
            elif prev_macd >= prev_signal and macd_line < signal_line:
                crossover = 'bearish'

        self._macd_history.append((macd_line, signal_line))

        return MACDData(
            macd_line=macd_line,
            signal_line=signal_line,
            histogram=histogram,
            is_bullish=macd_line > signal_line,
            crossover=crossover,
        )

    def calculate_bollinger_bands(
        self,
        data: Optional[List[float]] = None,
        period: Optional[int] = None,
        std_dev: Optional[float] = None
    ) -> BollingerBands:
        """
        Calculate Bollinger Bands.

        Bollinger Bands measure volatility and identify overbought/oversold levels.

        Args:
            data: Price data. Uses internal history if not provided.
            period: BB period. Uses config default if not provided.
            std_dev: Standard deviation multiplier. Uses config default.

        Returns:
            BollingerBands with calculated values.
        """
        period = period or self.config.bb_period
        std_dev = std_dev or self.config.bb_std_dev

        if data is None:
            data = list(self._close_history)

        if len(data) < period:
            current = data[-1] if data else 0.0
            return BollingerBands(
                upper=current,
                middle=current,
                lower=current,
                bandwidth=0.0,
                percent_b=0.5,
                squeeze=False,
            )

        # Calculate middle band (SMA)
        middle = sum(data[-period:]) / period

        # Calculate standard deviation
        variance = sum((x - middle) ** 2 for x in data[-period:]) / period
        stdev = variance ** 0.5

        # Calculate bands
        upper = middle + (std_dev * stdev)
        lower = middle - (std_dev * stdev)

        # Bandwidth
        bandwidth = (upper - lower) / middle if middle > 0 else 0.0

        # %B (where price is relative to bands)
        current_price = data[-1]
        if upper != lower:
            percent_b = (current_price - lower) / (upper - lower)
        else:
            percent_b = 0.5

        # Squeeze detection
        squeeze = bandwidth < self.config.bb_squeeze_threshold

        return BollingerBands(
            upper=upper,
            middle=middle,
            lower=lower,
            bandwidth=bandwidth,
            percent_b=percent_b,
            squeeze=squeeze,
        )

    def calculate_atr(
        self,
        candles: Optional[List[OHLCV]] = None,
        period: Optional[int] = None
    ) -> float:
        """
        Calculate Average True Range.

        ATR measures market volatility by decomposing the entire range of
        an asset price for the period.

        Args:
            candles: OHLCV data. Uses internal history if not provided.
            period: ATR period. Uses config default if not provided.

        Returns:
            ATR value.
        """
        period = period or self.config.atr_period

        if candles is None:
            # Reconstruct from history
            if len(self._high_history) < period + 1:
                return 0.0

            highs = list(self._high_history)
            lows = list(self._low_history)
            closes = list(self._close_history)

            # Calculate true ranges
            true_ranges = []
            for i in range(1, len(highs)):
                high_low = highs[i] - lows[i]
                high_close = abs(highs[i] - closes[i-1])
                low_close = abs(lows[i] - closes[i-1])
                true_ranges.append(max(high_low, high_close, low_close))
        else:
            if len(candles) < period + 1:
                return 0.0

            # Calculate true ranges
            true_ranges = []
            for i in range(1, len(candles)):
                high_low = candles[i].high - candles[i].low
                high_close = abs(candles[i].high - candles[i-1].close)
                low_close = abs(candles[i].low - candles[i-1].close)
                true_ranges.append(max(high_low, high_close, low_close))

        if len(true_ranges) < period:
            return sum(true_ranges) / len(true_ranges) if true_ranges else 0.0

        # Calculate ATR using Wilder's smoothing
        atr = sum(true_ranges[:period]) / period

        for tr in true_ranges[period:]:
            atr = (atr * (period - 1) + tr) / period

        return atr

    def calculate_stochastic(
        self,
        candles: Optional[List[OHLCV]] = None,
        k_period: Optional[int] = None,
        d_period: Optional[int] = None
    ) -> StochasticData:
        """
        Calculate Stochastic Oscillator.

        The Stochastic Oscillator compares closing price to the price
        range over a given time period.

        Args:
            candles: OHLCV data. Uses internal history if not provided.
            k_period: %K period. Uses config default if not provided.
            d_period: %D period. Uses config default if not provided.

        Returns:
            StochasticData with calculated values.
        """
        k_period = k_period or self.config.stoch_k_period
        d_period = d_period or self.config.stoch_d_period

        if candles is None:
            highs = list(self._high_history)
            lows = list(self._low_history)
            closes = list(self._close_history)
        else:
            highs = [c.high for c in candles]
            lows = [c.low for c in candles]
            closes = [c.close for c in candles]

        if len(closes) < k_period:
            return StochasticData(
                k=50.0,
                d=50.0,
                is_overbought=False,
                is_oversold=False,
                crossover=None,
            )

        # Calculate %K values
        k_values = []
        for i in range(k_period - 1, len(closes)):
            period_highs = highs[i - k_period + 1:i + 1]
            period_lows = lows[i - k_period + 1:i + 1]

            highest_high = max(period_highs)
            lowest_low = min(period_lows)

            if highest_high != lowest_low:
                k = ((closes[i] - lowest_low) / (highest_high - lowest_low)) * 100
            else:
                k = 50.0

            k_values.append(k)

        current_k = k_values[-1] if k_values else 50.0

        # Calculate %D (SMA of %K)
        if len(k_values) >= d_period:
            current_d = sum(k_values[-d_period:]) / d_period
        else:
            current_d = current_k

        # Detect crossover
        crossover = None
        if len(k_values) >= d_period + 1:
            prev_k = k_values[-2]
            prev_d = sum(k_values[-d_period-1:-1]) / d_period
            if prev_k <= prev_d and current_k > current_d:
                crossover = 'bullish'
            elif prev_k >= prev_d and current_k < current_d:
                crossover = 'bearish'

        return StochasticData(
            k=current_k,
            d=current_d,
            is_overbought=current_k > self.config.stoch_overbought,
            is_oversold=current_k < self.config.stoch_oversold,
            crossover=crossover,
        )

    def calculate_trend_strength(
        self,
        data: Optional[List[float]] = None,
        period: int = 20
    ) -> float:
        """
        Calculate trend strength indicator (0-100).

        Uses ADX-like calculation to measure trend strength.

        Args:
            data: Price data. Uses internal history if not provided.
            period: Calculation period.

        Returns:
            Trend strength from 0 (no trend) to 100 (strong trend).
        """
        if data is None:
            data = list(self._close_history)

        if len(data) < period:
            return 0.0

        highs = list(self._high_history)[-period:]
        lows = list(self._low_history)[-period:]

        if len(highs) < period or len(lows) < period:
            return 0.0

        # Calculate directional movements
        plus_dm = []
        minus_dm = []
        tr_values = []

        for i in range(1, len(highs)):
            high_diff = highs[i] - highs[i-1]
            low_diff = lows[i-1] - lows[i]

            if high_diff > low_diff and high_diff > 0:
                plus_dm.append(high_diff)
            else:
                plus_dm.append(0)

            if low_diff > high_diff and low_diff > 0:
                minus_dm.append(low_diff)
            else:
                minus_dm.append(0)

            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - data[i-1]) if i < len(data) else 0,
                abs(lows[i] - data[i-1]) if i < len(data) else 0
            )
            tr_values.append(tr)

        if not tr_values or sum(tr_values) == 0:
            return 0.0

        # Smooth the values
        smooth_plus_dm = sum(plus_dm) / len(plus_dm)
        smooth_minus_dm = sum(minus_dm) / len(minus_dm)
        smooth_tr = sum(tr_values) / len(tr_values)

        # Calculate DI+ and DI-
        di_plus = (smooth_plus_dm / smooth_tr) * 100 if smooth_tr > 0 else 0
        di_minus = (smooth_minus_dm / smooth_tr) * 100 if smooth_tr > 0 else 0

        # Calculate DX
        di_sum = di_plus + di_minus
        if di_sum > 0:
            dx = abs(di_plus - di_minus) / di_sum * 100
        else:
            dx = 0

        return min(100, dx)

    def calculate_all(
        self,
        candles: Optional[List[OHLCV]] = None
    ) -> IndicatorSet:
        """
        Calculate all technical indicators.

        This is the main method that calculates all indicators and
        returns them in a single IndicatorSet.

        Args:
            candles: Optional list of OHLCV candles.

        Returns:
            IndicatorSet with all calculated indicators.
        """
        # Update history if candles provided
        if candles:
            for candle in candles:
                self.update(candle)

        # Get price data
        closes = list(self._close_history)

        # Calculate all indicators
        rsi = self.calculate_rsi(closes)
        macd = self.calculate_macd(closes)
        bollinger = self.calculate_bollinger_bands(closes)
        atr = self.calculate_atr()
        stochastic = self.calculate_stochastic()
        trend_strength = self.calculate_trend_strength(closes)

        return IndicatorSet(
            timestamp=datetime.now(),
            rsi=rsi,
            macd=macd,
            bollinger=bollinger,
            atr=atr,
            stochastic=stochastic,
            trend_strength=trend_strength,
        )

    def detect_indicator_divergence(
        self,
        indicator_name: str,
        lookback: int = 20
    ) -> Optional[str]:
        """
        Detect divergence between price and any indicator.

        Args:
            indicator_name: Name of indicator ('rsi', 'macd', 'stochastic').
            lookback: Number of periods to analyze.

        Returns:
            'bullish', 'bearish', or None.
        """
        prices = list(self._close_history)[-lookback:]

        if len(prices) < lookback:
            return None

        if indicator_name == 'rsi':
            indicator_values = list(self._rsi_history)[-lookback:]
        elif indicator_name == 'macd':
            indicator_values = [m[0] for m in list(self._macd_history)[-lookback:]]
        else:
            return None

        if len(indicator_values) < lookback:
            return None

        # Find swing highs and lows
        price_highs = self._find_swing_points(prices, 'high')
        price_lows = self._find_swing_points(prices, 'low')
        ind_highs = self._find_swing_points(indicator_values, 'high')
        ind_lows = self._find_swing_points(indicator_values, 'low')

        # Bearish divergence: higher price highs, lower indicator highs
        if len(price_highs) >= 2 and len(ind_highs) >= 2:
            if price_highs[-1][1] > price_highs[-2][1] and ind_highs[-1][1] < ind_highs[-2][1]:
                return 'bearish'

        # Bullish divergence: lower price lows, higher indicator lows
        if len(price_lows) >= 2 and len(ind_lows) >= 2:
            if price_lows[-1][1] < price_lows[-2][1] and ind_lows[-1][1] > ind_lows[-2][1]:
                return 'bullish'

        return None

    def _find_swing_points(
        self,
        data: List[float],
        point_type: str
    ) -> List[Tuple[int, float]]:
        """
        Find swing high or low points in data.

        Args:
            data: Price or indicator data.
            point_type: 'high' or 'low'.

        Returns:
            List of (index, value) tuples for swing points.
        """
        swings = []

        for i in range(2, len(data) - 2):
            if point_type == 'high':
                if data[i] > data[i-1] and data[i] > data[i-2] and \
                   data[i] > data[i+1] and data[i] > data[i+2]:
                    swings.append((i, data[i]))
            else:  # low
                if data[i] < data[i-1] and data[i] < data[i-2] and \
                   data[i] < data[i+1] and data[i] < data[i+2]:
                    swings.append((i, data[i]))

        return swings

    def get_signal_alignment(
        self,
        direction: str
    ) -> Tuple[int, int, List[str]]:
        """
        Check how many indicators align with a given direction.

        Args:
            direction: 'bullish' or 'bearish'.

        Returns:
            Tuple of (aligned_count, total_count, list of aligned indicators).
        """
        closes = list(self._close_history)
        aligned = []
        total = 5  # RSI, MACD, BB, Stochastic, Trend

        rsi = self.calculate_rsi(closes)
        macd = self.calculate_macd(closes)
        bollinger = self.calculate_bollinger_bands(closes)
        stochastic = self.calculate_stochastic()

        if direction == 'bullish':
            if rsi.is_oversold or rsi.divergence == 'bullish':
                aligned.append('RSI')
            if macd.is_bullish or macd.crossover == 'bullish':
                aligned.append('MACD')
            if bollinger.percent_b < 0.2:
                aligned.append('BB')
            if stochastic.is_oversold or stochastic.crossover == 'bullish':
                aligned.append('Stochastic')
            if len(closes) >= 20:
                sma = self.calculate_sma(closes, 20)
                if closes[-1] > sma:
                    aligned.append('Trend')
        else:  # bearish
            if rsi.is_overbought or rsi.divergence == 'bearish':
                aligned.append('RSI')
            if not macd.is_bullish or macd.crossover == 'bearish':
                aligned.append('MACD')
            if bollinger.percent_b > 0.8:
                aligned.append('BB')
            if stochastic.is_overbought or stochastic.crossover == 'bearish':
                aligned.append('Stochastic')
            if len(closes) >= 20:
                sma = self.calculate_sma(closes, 20)
                if closes[-1] < sma:
                    aligned.append('Trend')

        return len(aligned), total, aligned

    def reset(self):
        """Reset all indicator history."""
        self._price_history.clear()
        self._high_history.clear()
        self._low_history.clear()
        self._close_history.clear()
        self._volume_history.clear()
        self._rsi_history.clear()
        self._macd_history.clear()


# =============================================================================
# STANDALONE INDICATOR FUNCTIONS
# =============================================================================

def calculate_sma(prices: List[float], period: int) -> float:
    """
    Calculate Simple Moving Average.

    Args:
        prices: List of prices.
        period: SMA period.

    Returns:
        SMA value.
    """
    if len(prices) < period:
        return prices[-1] if prices else 0.0
    return sum(prices[-period:]) / period


def calculate_ema(prices: List[float], period: int) -> float:
    """
    Calculate Exponential Moving Average.

    Args:
        prices: List of prices.
        period: EMA period.

    Returns:
        EMA value.
    """
    if len(prices) < period:
        return prices[-1] if prices else 0.0

    multiplier = 2 / (period + 1)
    ema = sum(prices[:period]) / period

    for price in prices[period:]:
        ema = (price - ema) * multiplier + ema

    return ema


def calculate_vwma(
    prices: List[float],
    volumes: List[float],
    period: int
) -> float:
    """
    Calculate Volume Weighted Moving Average.

    Args:
        prices: List of prices.
        volumes: List of volumes.
        period: VWMA period.

    Returns:
        VWMA value.
    """
    if len(prices) < period or len(volumes) < period:
        return prices[-1] if prices else 0.0

    prices = prices[-period:]
    volumes = volumes[-period:]

    total_volume = sum(volumes)
    if total_volume == 0:
        return sum(prices) / period

    return sum(p * v for p, v in zip(prices, volumes)) / total_volume


def calculate_pivot_points(
    high: float,
    low: float,
    close: float
) -> Dict[str, float]:
    """
    Calculate classic pivot points.

    Args:
        high: Period high.
        low: Period low.
        close: Period close.

    Returns:
        Dictionary with PP, R1, R2, R3, S1, S2, S3.
    """
    pp = (high + low + close) / 3

    return {
        'PP': pp,
        'R1': 2 * pp - low,
        'R2': pp + (high - low),
        'R3': high + 2 * (pp - low),
        'S1': 2 * pp - high,
        'S2': pp - (high - low),
        'S3': low - 2 * (high - pp),
    }


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    'TechnicalIndicators',
    'calculate_sma',
    'calculate_ema',
    'calculate_vwma',
    'calculate_pivot_points',
]
