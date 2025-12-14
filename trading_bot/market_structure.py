"""
Market Structure Analysis Module using Auction Market Theory (AMT).

This module provides comprehensive market structure analysis including:
- Time Price Opportunity (TPO) profiles
- Fair Value Area (FVA) calculation
- Volume Profile analysis
- Breakout and rejection detection
- Support and resistance identification

Author: AMT Trading Bot
Version: 1.0.0
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import statistics
from collections import defaultdict

from config import (
    OHLCV,
    TPOProfile,
    FairValueArea,
    VolumeProfile,
    MarketStructure,
    MarketCondition,
    TrendDirection,
    MarketStructureConfig,
    get_default_config,
)


class MarketStructureAnalyzer:
    """
    Analyzes market structure using Auction Market Theory principles.

    This analyzer identifies fair value areas, calculates TPO profiles,
    detects breakouts and rejections, and provides comprehensive market
    structure analysis.

    Attributes:
        config: Market structure configuration settings.
        tpo_history: Historical TPO profiles.
        fva_history: Historical fair value areas.
    """

    def __init__(self, config: Optional[MarketStructureConfig] = None):
        """
        Initialize the Market Structure Analyzer.

        Args:
            config: Optional configuration. Uses defaults if not provided.
        """
        self.config = config or get_default_config().market_structure
        self.tpo_history: List[TPOProfile] = []
        self.fva_history: List[FairValueArea] = []
        self.volume_profiles: List[VolumeProfile] = []
        self._price_history: List[float] = []
        self._atr_values: List[float] = []

    def calculate_tpo_profile(
        self,
        candles: List[OHLCV],
        tick_size: float = 0.01
    ) -> TPOProfile:
        """
        Calculate Time Price Opportunity (TPO) profile from candle data.

        The TPO profile shows the distribution of time spent at each price
        level, helping identify value areas and points of control.

        Args:
            candles: List of OHLCV candles to analyze.
            tick_size: Minimum price increment for grouping.

        Returns:
            TPOProfile with calculated values.
        """
        if not candles:
            return TPOProfile(timestamp=datetime.now())

        price_levels: Dict[float, int] = defaultdict(int)

        # Count TPOs at each price level
        for candle in candles:
            low_tick = int(candle.low / tick_size)
            high_tick = int(candle.high / tick_size)

            for tick in range(low_tick, high_tick + 1):
                price = round(tick * tick_size, 4)
                price_levels[price] += 1

        # Find Point of Control (highest TPO count)
        poc = max(price_levels.keys(), key=lambda x: price_levels[x]) if price_levels else 0.0

        # Calculate Value Area (70% of TPOs)
        val, vah = self._calculate_value_area(price_levels)

        # Calculate Initial Balance (first hour)
        ib_candles = candles[:min(4, len(candles))]  # Assuming 15-min candles
        ib_high = max(c.high for c in ib_candles) if ib_candles else 0.0
        ib_low = min(c.low for c in ib_candles) if ib_candles else 0.0

        profile = TPOProfile(
            timestamp=candles[-1].timestamp if candles else datetime.now(),
            price_levels=dict(price_levels),
            poc=poc,
            val=val,
            vah=vah,
            initial_balance_high=ib_high,
            initial_balance_low=ib_low,
        )

        self.tpo_history.append(profile)
        return profile

    def _calculate_value_area(
        self,
        price_levels: Dict[float, int]
    ) -> Tuple[float, float]:
        """
        Calculate the Value Area from TPO distribution.

        The Value Area contains approximately 70% of TPOs, centered around
        the Point of Control.

        Args:
            price_levels: Dictionary mapping prices to TPO counts.

        Returns:
            Tuple of (Value Area Low, Value Area High).
        """
        if not price_levels:
            return 0.0, 0.0

        total_tpos = sum(price_levels.values())
        target_tpos = total_tpos * (self.config.value_area_percent / 100)

        sorted_prices = sorted(price_levels.keys())
        poc = max(price_levels.keys(), key=lambda x: price_levels[x])
        poc_index = sorted_prices.index(poc)

        # Start with POC
        val_index = poc_index
        vah_index = poc_index
        current_tpos = price_levels[poc]

        # Expand outward from POC
        while current_tpos < target_tpos and (val_index > 0 or vah_index < len(sorted_prices) - 1):
            lower_tpos = price_levels.get(sorted_prices[val_index - 1], 0) if val_index > 0 else 0
            upper_tpos = price_levels.get(sorted_prices[vah_index + 1], 0) if vah_index < len(sorted_prices) - 1 else 0

            if lower_tpos >= upper_tpos and val_index > 0:
                val_index -= 1
                current_tpos += lower_tpos
            elif vah_index < len(sorted_prices) - 1:
                vah_index += 1
                current_tpos += upper_tpos
            else:
                break

        return sorted_prices[val_index], sorted_prices[vah_index]

    def calculate_volume_profile(
        self,
        candles: List[OHLCV],
        num_bins: Optional[int] = None
    ) -> VolumeProfile:
        """
        Calculate Volume Profile from candle data.

        Volume Profile shows the distribution of volume at each price level,
        identifying High Volume Nodes (HVN) and Low Volume Nodes (LVN).

        Args:
            candles: List of OHLCV candles to analyze.
            num_bins: Number of price bins. Uses config default if not specified.

        Returns:
            VolumeProfile with calculated values.
        """
        if not candles:
            return VolumeProfile()

        num_bins = num_bins or self.config.volume_profile_bins

        # Find price range
        all_prices = []
        for candle in candles:
            all_prices.extend([candle.high, candle.low])

        min_price = min(all_prices)
        max_price = max(all_prices)
        bin_size = (max_price - min_price) / num_bins if num_bins > 0 else 1

        # Distribute volume across bins
        price_levels: Dict[float, float] = defaultdict(float)

        for candle in candles:
            # Distribute candle volume across its price range
            low_bin = int((candle.low - min_price) / bin_size) if bin_size > 0 else 0
            high_bin = int((candle.high - min_price) / bin_size) if bin_size > 0 else 0
            high_bin = min(high_bin, num_bins - 1)

            bins_covered = high_bin - low_bin + 1
            volume_per_bin = candle.volume / bins_covered if bins_covered > 0 else 0

            for b in range(low_bin, high_bin + 1):
                bin_price = round(min_price + (b + 0.5) * bin_size, 4)
                price_levels[bin_price] += volume_per_bin

        # Find POC (highest volume price)
        poc = max(price_levels.keys(), key=lambda x: price_levels[x]) if price_levels else 0.0

        # Identify HVN and LVN
        hvn, lvn = self._identify_volume_nodes(price_levels)

        profile = VolumeProfile(
            price_levels=dict(price_levels),
            poc=poc,
            hvn=hvn,
            lvn=lvn,
        )

        self.volume_profiles.append(profile)
        return profile

    def _identify_volume_nodes(
        self,
        price_levels: Dict[float, float]
    ) -> Tuple[List[float], List[float]]:
        """
        Identify High Volume Nodes and Low Volume Nodes.

        Args:
            price_levels: Dictionary mapping prices to volume.

        Returns:
            Tuple of (list of HVN prices, list of LVN prices).
        """
        if not price_levels:
            return [], []

        volumes = list(price_levels.values())
        hvn_threshold = statistics.quantiles(volumes, n=100)[int(self.config.hvn_threshold_percentile) - 1]
        lvn_threshold = statistics.quantiles(volumes, n=100)[int(self.config.lvn_threshold_percentile) - 1]

        hvn = [price for price, vol in price_levels.items() if vol >= hvn_threshold]
        lvn = [price for price, vol in price_levels.items() if vol <= lvn_threshold]

        return hvn, lvn

    def calculate_fair_value_area(
        self,
        candles: List[OHLCV],
        use_volume: bool = True
    ) -> FairValueArea:
        """
        Calculate the Fair Value Area from market data.

        The Fair Value Area represents where the market perceives fair
        value, typically containing 70% of volume/time.

        Args:
            candles: List of OHLCV candles to analyze.
            use_volume: If True, uses volume profile. If False, uses TPO.

        Returns:
            FairValueArea with calculated values.
        """
        if not candles:
            return FairValueArea(vah=0, val=0, poc=0)

        if use_volume:
            profile = self.calculate_volume_profile(candles)
            val, vah = self._calculate_value_area_from_volume(profile.price_levels)
            poc = profile.poc
        else:
            tpo = self.calculate_tpo_profile(candles)
            val = tpo.val
            vah = tpo.vah
            poc = tpo.poc

        fva = FairValueArea(
            vah=vah,
            val=val,
            poc=poc,
            developing=True,
        )

        self.fva_history.append(fva)
        return fva

    def _calculate_value_area_from_volume(
        self,
        price_levels: Dict[float, float]
    ) -> Tuple[float, float]:
        """
        Calculate Value Area from volume distribution.

        Args:
            price_levels: Dictionary mapping prices to volume.

        Returns:
            Tuple of (Value Area Low, Value Area High).
        """
        if not price_levels:
            return 0.0, 0.0

        total_volume = sum(price_levels.values())
        target_volume = total_volume * (self.config.value_area_percent / 100)

        sorted_prices = sorted(price_levels.keys())
        poc = max(price_levels.keys(), key=lambda x: price_levels[x])
        poc_index = sorted_prices.index(poc)

        val_index = poc_index
        vah_index = poc_index
        current_volume = price_levels[poc]

        while current_volume < target_volume and (val_index > 0 or vah_index < len(sorted_prices) - 1):
            lower_vol = price_levels.get(sorted_prices[val_index - 1], 0) if val_index > 0 else 0
            upper_vol = price_levels.get(sorted_prices[vah_index + 1], 0) if vah_index < len(sorted_prices) - 1 else 0

            if lower_vol >= upper_vol and val_index > 0:
                val_index -= 1
                current_volume += lower_vol
            elif vah_index < len(sorted_prices) - 1:
                vah_index += 1
                current_volume += upper_vol
            else:
                break

        return sorted_prices[val_index], sorted_prices[vah_index]

    def detect_breakout(
        self,
        current_price: float,
        fva: FairValueArea,
        volume: float,
        avg_volume: float,
        atr: float
    ) -> Tuple[bool, Optional[TrendDirection]]:
        """
        Detect if a breakout from the value area is occurring.

        A valid breakout requires:
        - Price outside the value area by ATR threshold
        - Volume above average (confirmation)

        Args:
            current_price: Current market price.
            fva: Current Fair Value Area.
            volume: Current period volume.
            avg_volume: Average volume for comparison.
            atr: Current ATR value.

        Returns:
            Tuple of (is_breakout, breakout_direction).
        """
        breakout_threshold = atr * self.config.breakout_threshold_atr
        volume_confirmed = volume > (avg_volume * self.config.breakout_volume_multiple)

        # Check for upside breakout
        if current_price > fva.vah + breakout_threshold:
            if volume_confirmed:
                return True, TrendDirection.BULLISH
            return False, None

        # Check for downside breakout
        if current_price < fva.val - breakout_threshold:
            if volume_confirmed:
                return True, TrendDirection.BEARISH
            return False, None

        return False, None

    def detect_rejection(
        self,
        candle: OHLCV,
        fva: FairValueArea,
        avg_volume: float
    ) -> Tuple[bool, Optional[float]]:
        """
        Detect if a rejection from a key level is occurring.

        A rejection is identified by:
        - Long wick relative to body
        - Price testing and rejecting from value area boundary
        - Volume confirmation

        Args:
            candle: Current OHLCV candle.
            fva: Current Fair Value Area.
            avg_volume: Average volume for comparison.

        Returns:
            Tuple of (is_rejection, rejection_level).
        """
        body = candle.body
        upper_wick = candle.high - max(candle.open, candle.close)
        lower_wick = min(candle.open, candle.close) - candle.low

        volume_confirmed = candle.volume > (avg_volume * self.config.rejection_volume_threshold)

        # Check for rejection at VAH (resistance)
        if upper_wick > body * self.config.rejection_wick_ratio:
            if candle.high >= fva.vah and candle.close < fva.vah:
                if volume_confirmed:
                    return True, fva.vah

        # Check for rejection at VAL (support)
        if lower_wick > body * self.config.rejection_wick_ratio:
            if candle.low <= fva.val and candle.close > fva.val:
                if volume_confirmed:
                    return True, fva.val

        # Check for rejection at POC
        if candle.high >= fva.poc >= candle.low:
            if upper_wick > body * self.config.rejection_wick_ratio or \
               lower_wick > body * self.config.rejection_wick_ratio:
                if volume_confirmed:
                    return True, fva.poc

        return False, None

    def identify_support_resistance(
        self,
        candles: List[OHLCV],
        num_levels: int = 5
    ) -> Tuple[List[float], List[float]]:
        """
        Identify support and resistance levels from price data.

        Uses swing highs/lows and volume profile HVN to identify
        significant price levels.

        Args:
            candles: Historical OHLCV data.
            num_levels: Maximum number of levels to return per side.

        Returns:
            Tuple of (support_levels, resistance_levels).
        """
        if len(candles) < 5:
            return [], []

        current_price = candles[-1].close
        support_levels = []
        resistance_levels = []

        # Find swing highs and lows
        for i in range(2, len(candles) - 2):
            # Swing high
            if candles[i].high > candles[i-1].high and \
               candles[i].high > candles[i-2].high and \
               candles[i].high > candles[i+1].high and \
               candles[i].high > candles[i+2].high:
                if candles[i].high > current_price:
                    resistance_levels.append(candles[i].high)
                else:
                    support_levels.append(candles[i].high)

            # Swing low
            if candles[i].low < candles[i-1].low and \
               candles[i].low < candles[i-2].low and \
               candles[i].low < candles[i+1].low and \
               candles[i].low < candles[i+2].low:
                if candles[i].low < current_price:
                    support_levels.append(candles[i].low)
                else:
                    resistance_levels.append(candles[i].low)

        # Add volume profile levels
        if self.volume_profiles:
            latest_vp = self.volume_profiles[-1]
            for hvn in latest_vp.hvn:
                if hvn < current_price:
                    support_levels.append(hvn)
                else:
                    resistance_levels.append(hvn)

        # Sort and limit
        support_levels = sorted(set(support_levels), reverse=True)[:num_levels]
        resistance_levels = sorted(set(resistance_levels))[:num_levels]

        return support_levels, resistance_levels

    def determine_market_condition(
        self,
        candles: List[OHLCV],
        atr: float
    ) -> MarketCondition:
        """
        Determine the current market condition.

        Classifies the market as trending, ranging, or volatile based
        on price action and volatility analysis.

        Args:
            candles: Recent OHLCV data.
            atr: Current ATR value.

        Returns:
            MarketCondition classification.
        """
        if len(candles) < 20:
            return MarketCondition.UNKNOWN

        closes = [c.close for c in candles[-20:]]
        highs = [c.high for c in candles[-20:]]
        lows = [c.low for c in candles[-20:]]

        # Calculate trend
        price_change = closes[-1] - closes[0]
        avg_price = sum(closes) / len(closes)
        price_range = max(highs) - min(lows)

        # Trend strength
        if abs(price_change) > price_range * 0.4:
            if price_change > 0:
                return MarketCondition.TRENDING_UP
            else:
                return MarketCondition.TRENDING_DOWN

        # Volatility analysis
        recent_range = sum(c.range for c in candles[-5:]) / 5
        historical_range = sum(c.range for c in candles[-20:-5]) / 15 if len(candles) >= 20 else recent_range

        if recent_range > historical_range * 1.5:
            return MarketCondition.HIGH_VOLATILITY
        elif recent_range < historical_range * 0.5:
            return MarketCondition.LOW_VOLATILITY

        return MarketCondition.RANGING

    def determine_trend(
        self,
        candles: List[OHLCV],
        lookback: int = 20
    ) -> TrendDirection:
        """
        Determine the current trend direction.

        Uses price structure and moving average analysis to classify
        the trend as bullish, bearish, or neutral.

        Args:
            candles: Recent OHLCV data.
            lookback: Number of periods for trend analysis.

        Returns:
            TrendDirection classification.
        """
        if len(candles) < lookback:
            return TrendDirection.NEUTRAL

        closes = [c.close for c in candles[-lookback:]]

        # Simple trend: higher highs/lows vs lower highs/lows
        recent_half = closes[-lookback//2:]
        older_half = closes[:lookback//2]

        recent_avg = sum(recent_half) / len(recent_half)
        older_avg = sum(older_half) / len(older_half)

        # Count higher highs and higher lows
        higher_highs = 0
        higher_lows = 0
        lower_highs = 0
        lower_lows = 0

        for i in range(2, len(candles)):
            if candles[i].high > candles[i-1].high:
                higher_highs += 1
            else:
                lower_highs += 1

            if candles[i].low > candles[i-1].low:
                higher_lows += 1
            else:
                lower_lows += 1

        bullish_score = higher_highs + higher_lows
        bearish_score = lower_highs + lower_lows

        if recent_avg > older_avg * 1.01 and bullish_score > bearish_score:
            return TrendDirection.BULLISH
        elif recent_avg < older_avg * 0.99 and bearish_score > bullish_score:
            return TrendDirection.BEARISH
        else:
            return TrendDirection.NEUTRAL

    def analyze(
        self,
        candles: List[OHLCV],
        current_price: float,
        atr: float,
        avg_volume: Optional[float] = None
    ) -> MarketStructure:
        """
        Perform complete market structure analysis.

        This is the main analysis method that combines all market structure
        components into a comprehensive analysis result.

        Args:
            candles: Historical OHLCV data.
            current_price: Current market price.
            atr: Current ATR value.
            avg_volume: Optional average volume for comparisons.

        Returns:
            Complete MarketStructure analysis result.
        """
        if not candles:
            return MarketStructure(
                timestamp=datetime.now(),
                fva=FairValueArea(vah=0, val=0, poc=0),
                tpo_profile=TPOProfile(timestamp=datetime.now()),
                volume_profile=VolumeProfile(),
                current_price=current_price,
                condition=MarketCondition.UNKNOWN,
                trend=TrendDirection.NEUTRAL,
            )

        # Calculate average volume if not provided
        if avg_volume is None:
            avg_volume = sum(c.volume for c in candles) / len(candles)

        # Calculate profiles
        tpo = self.calculate_tpo_profile(candles)
        volume_profile = self.calculate_volume_profile(candles)
        fva = self.calculate_fair_value_area(candles)

        # Detect breakout
        is_breakout, breakout_direction = self.detect_breakout(
            current_price, fva, candles[-1].volume, avg_volume, atr
        )

        # Detect rejection
        is_rejection, rejection_level = self.detect_rejection(
            candles[-1], fva, avg_volume
        )

        # Identify support/resistance
        support, resistance = self.identify_support_resistance(candles)

        # Determine conditions
        condition = self.determine_market_condition(candles, atr)
        trend = self.determine_trend(candles)

        return MarketStructure(
            timestamp=candles[-1].timestamp,
            fva=fva,
            tpo_profile=tpo,
            volume_profile=volume_profile,
            current_price=current_price,
            condition=condition,
            trend=trend,
            is_breakout=is_breakout,
            breakout_direction=breakout_direction,
            is_rejection=is_rejection,
            rejection_level=rejection_level,
            support_levels=support,
            resistance_levels=resistance,
        )

    def get_previous_day_fva(self) -> Optional[FairValueArea]:
        """
        Get the previous day's Fair Value Area.

        Returns:
            Previous day's FVA or None if not available.
        """
        if len(self.fva_history) >= 2:
            return self.fva_history[-2]
        return None

    def get_fva_relationship(
        self,
        current_price: float,
        fva: FairValueArea
    ) -> str:
        """
        Describe the price relationship to the Fair Value Area.

        Args:
            current_price: Current market price.
            fva: Fair Value Area to compare against.

        Returns:
            String describing the relationship.
        """
        if current_price > fva.vah:
            distance = ((current_price - fva.vah) / fva.vah) * 100
            return f"Above VAH by {distance:.2f}%"
        elif current_price < fva.val:
            distance = ((fva.val - current_price) / fva.val) * 100
            return f"Below VAL by {distance:.2f}%"
        else:
            # Within value area
            position_in_va = (current_price - fva.val) / fva.range * 100
            return f"Within VA at {position_in_va:.1f}% level"

    def reset(self):
        """Reset all historical data."""
        self.tpo_history.clear()
        self.fva_history.clear()
        self.volume_profiles.clear()
        self._price_history.clear()
        self._atr_values.clear()


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def calculate_vwap(candles: List[OHLCV]) -> float:
    """
    Calculate Volume Weighted Average Price.

    Args:
        candles: List of OHLCV candles.

    Returns:
        VWAP value.
    """
    if not candles:
        return 0.0

    cumulative_tp_volume = 0.0
    cumulative_volume = 0.0

    for candle in candles:
        typical_price = (candle.high + candle.low + candle.close) / 3
        cumulative_tp_volume += typical_price * candle.volume
        cumulative_volume += candle.volume

    return cumulative_tp_volume / cumulative_volume if cumulative_volume > 0 else 0.0


def calculate_twap(candles: List[OHLCV]) -> float:
    """
    Calculate Time Weighted Average Price.

    Args:
        candles: List of OHLCV candles.

    Returns:
        TWAP value.
    """
    if not candles:
        return 0.0

    total = sum((c.high + c.low + c.close) / 3 for c in candles)
    return total / len(candles)


def find_balance_areas(
    candles: List[OHLCV],
    min_bars: int = 5,
    max_range_percent: float = 1.0
) -> List[Tuple[float, float, int]]:
    """
    Find areas where price has balanced (consolidated).

    Args:
        candles: List of OHLCV candles.
        min_bars: Minimum bars in a balance area.
        max_range_percent: Maximum range as percent of price.

    Returns:
        List of tuples (low, high, duration) for each balance area.
    """
    if len(candles) < min_bars:
        return []

    balance_areas = []
    i = 0

    while i < len(candles) - min_bars:
        # Check if this starts a balance area
        segment = candles[i:i + min_bars]
        high = max(c.high for c in segment)
        low = min(c.low for c in segment)
        range_pct = (high - low) / low * 100

        if range_pct <= max_range_percent:
            # Extend the balance area
            j = i + min_bars
            while j < len(candles):
                if candles[j].high > high * 1.005 or candles[j].low < low * 0.995:
                    break
                high = max(high, candles[j].high)
                low = min(low, candles[j].low)
                j += 1

            if j - i >= min_bars:
                balance_areas.append((low, high, j - i))

            i = j
        else:
            i += 1

    return balance_areas


def detect_poor_structure(
    candles: List[OHLCV],
    fva: FairValueArea
) -> List[str]:
    """
    Detect poor market structure (excess, single prints, etc.).

    Args:
        candles: List of OHLCV candles.
        fva: Current Fair Value Area.

    Returns:
        List of detected poor structure types.
    """
    issues = []

    if not candles or len(candles) < 3:
        return issues

    # Check for excess at highs/lows
    high_candle = max(candles, key=lambda c: c.high)
    low_candle = min(candles, key=lambda c: c.low)

    if high_candle.close < high_candle.high - (high_candle.range * 0.7):
        issues.append("Excess at highs (potential reversal)")

    if low_candle.close > low_candle.low + (low_candle.range * 0.7):
        issues.append("Excess at lows (potential reversal)")

    # Check for single prints (poor auction)
    for i in range(1, len(candles) - 1):
        prev_range = (candles[i-1].high, candles[i-1].low)
        curr_range = (candles[i].high, candles[i].low)
        next_range = (candles[i+1].high, candles[i+1].low)

        # Gap up with no fill
        if candles[i].low > candles[i-1].high and candles[i].low > candles[i+1].high:
            issues.append(f"Single print up at {candles[i].low:.2f}")

        # Gap down with no fill
        if candles[i].high < candles[i-1].low and candles[i].high < candles[i+1].low:
            issues.append(f"Single print down at {candles[i].high:.2f}")

    return issues


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    'MarketStructureAnalyzer',
    'calculate_vwap',
    'calculate_twap',
    'find_balance_areas',
    'detect_poor_structure',
]
