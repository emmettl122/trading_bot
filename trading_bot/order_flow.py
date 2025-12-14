"""
Order Flow Analysis Module.

This module provides comprehensive order flow analysis including:
- Delta calculation (buy vs sell volume)
- Cumulative delta tracking
- Order book imbalance detection
- Divergence detection between price and delta
- Breakout quality scoring
- Liquidity analysis

Author: AMT Trading Bot
Version: 1.0.0
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from collections import deque
import statistics

from config import (
    OHLCV,
    TickData,
    OrderBook,
    OrderBookLevel,
    DeltaData,
    OrderFlowAnalysis,
    OrderFlowConfig,
    TrendDirection,
    get_default_config,
)


class OrderFlowAnalyzer:
    """
    Analyzes order flow to understand market participant behavior.

    Order flow analysis reveals the battle between buyers and sellers,
    helping identify accumulation, distribution, and potential reversals.

    Attributes:
        config: Order flow configuration settings.
        delta_history: Historical delta values.
        cumulative_delta: Running cumulative delta.
    """

    def __init__(self, config: Optional[OrderFlowConfig] = None):
        """
        Initialize the Order Flow Analyzer.

        Args:
            config: Optional configuration. Uses defaults if not provided.
        """
        self.config = config or get_default_config().order_flow
        self.delta_history: List[DeltaData] = []
        self.cumulative_delta: float = 0.0
        self._price_history: deque = deque(maxlen=100)
        self._delta_history_values: deque = deque(maxlen=100)
        self._order_book_history: List[OrderBook] = []

    def calculate_delta(
        self,
        candle: OHLCV,
        ticks: Optional[List[TickData]] = None
    ) -> DeltaData:
        """
        Calculate delta (buying volume - selling volume) for a candle.

        If tick data is provided, uses actual buy/sell classification.
        Otherwise, estimates based on price position within the candle.

        Args:
            candle: OHLCV candle data.
            ticks: Optional list of tick data for precise calculation.

        Returns:
            DeltaData with calculated values.
        """
        if ticks:
            # Calculate from actual tick data
            buy_volume = sum(t.volume for t in ticks if t.side == 'buy')
            sell_volume = sum(t.volume for t in ticks if t.side == 'sell')
        else:
            # Estimate based on candle position
            buy_volume, sell_volume = self._estimate_delta_from_candle(candle)

        delta = buy_volume - sell_volume
        total_volume = buy_volume + sell_volume

        self.cumulative_delta += delta

        delta_data = DeltaData(
            timestamp=candle.timestamp,
            delta=delta,
            cumulative_delta=self.cumulative_delta,
            buy_volume=buy_volume,
            sell_volume=sell_volume,
            total_volume=total_volume,
        )

        self.delta_history.append(delta_data)
        self._delta_history_values.append(delta)
        self._price_history.append(candle.close)

        return delta_data

    def _estimate_delta_from_candle(
        self,
        candle: OHLCV
    ) -> Tuple[float, float]:
        """
        Estimate buy and sell volume from candle structure.

        Uses the close position within the range to estimate
        buying vs selling pressure.

        Args:
            candle: OHLCV candle data.

        Returns:
            Tuple of (buy_volume, sell_volume).
        """
        range_size = candle.high - candle.low
        if range_size == 0:
            # Doji candle - split evenly
            return candle.volume / 2, candle.volume / 2

        # Calculate close position within range (0 = low, 1 = high)
        close_position = (candle.close - candle.low) / range_size

        # Adjust for candle direction
        if candle.is_bullish:
            # Bullish candle - more buying pressure
            buy_ratio = 0.5 + (close_position * 0.3)
        else:
            # Bearish candle - more selling pressure
            buy_ratio = 0.3 + (close_position * 0.3)

        buy_volume = candle.volume * buy_ratio
        sell_volume = candle.volume * (1 - buy_ratio)

        return buy_volume, sell_volume

    def detect_delta_divergence(
        self,
        lookback: Optional[int] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Detect divergence between price and cumulative delta.

        Divergence occurs when price makes new highs/lows but delta
        fails to confirm, suggesting a potential reversal.

        Args:
            lookback: Number of periods to analyze. Uses config default.

        Returns:
            Tuple of (divergence_detected, divergence_type).
        """
        lookback = lookback or self.config.divergence_lookback

        if len(self._price_history) < lookback or len(self._delta_history_values) < lookback:
            return False, None

        prices = list(self._price_history)[-lookback:]
        deltas = list(self._delta_history_values)[-lookback:]

        # Find price trend
        price_start = statistics.mean(prices[:lookback//4])
        price_end = statistics.mean(prices[-lookback//4:])
        price_trending_up = price_end > price_start * 1.002
        price_trending_down = price_end < price_start * 0.998

        # Find cumulative delta trend
        delta_sum_start = sum(deltas[:lookback//2])
        delta_sum_end = sum(deltas[-lookback//2:])
        delta_trending_up = delta_sum_end > delta_sum_start
        delta_trending_down = delta_sum_end < delta_sum_start

        # Check for bearish divergence (price up, delta down)
        if price_trending_up and delta_trending_down:
            return True, 'bearish'

        # Check for bullish divergence (price down, delta up)
        if price_trending_down and delta_trending_up:
            return True, 'bullish'

        return False, None

    def calculate_imbalance_ratio(
        self,
        order_book: OrderBook,
        levels: int = 5
    ) -> float:
        """
        Calculate the bid/ask imbalance ratio from order book.

        A ratio > 1 indicates more bid (buying) pressure.
        A ratio < 1 indicates more ask (selling) pressure.

        Args:
            order_book: Current order book snapshot.
            levels: Number of levels to analyze.

        Returns:
            Imbalance ratio (bid_volume / ask_volume).
        """
        bid_volume = sum(
            level.size for level in order_book.bids[:levels]
        )
        ask_volume = sum(
            level.size for level in order_book.asks[:levels]
        )

        if ask_volume == 0:
            return float('inf') if bid_volume > 0 else 1.0

        return bid_volume / ask_volume

    def detect_aggressive_activity(
        self,
        delta: DeltaData,
        avg_delta: Optional[float] = None
    ) -> Tuple[bool, bool]:
        """
        Detect aggressive buying or selling activity.

        Aggressive activity is characterized by unusually high delta
        relative to historical averages.

        Args:
            delta: Current delta data.
            avg_delta: Optional historical average delta.

        Returns:
            Tuple of (aggressive_buying, aggressive_selling).
        """
        if avg_delta is None:
            if len(self._delta_history_values) >= 20:
                avg_delta = statistics.mean(
                    abs(d) for d in list(self._delta_history_values)[-20:]
                )
            else:
                return False, False

        threshold = avg_delta * self.config.delta_threshold * 3

        aggressive_buying = delta.delta > threshold
        aggressive_selling = delta.delta < -threshold

        return aggressive_buying, aggressive_selling

    def detect_absorption(
        self,
        candles: List[OHLCV],
        deltas: List[DeltaData]
    ) -> bool:
        """
        Detect volume absorption (large volume with little price movement).

        Absorption indicates that large orders are being absorbed by
        the market, often preceding a reversal.

        Args:
            candles: Recent OHLCV data.
            deltas: Corresponding delta data.

        Returns:
            True if absorption is detected.
        """
        if len(candles) < 3 or len(deltas) < 3:
            return False

        # Check last few candles
        recent_candles = candles[-3:]
        recent_deltas = deltas[-3:]

        # Calculate average metrics
        avg_volume = sum(c.volume for c in candles) / len(candles)
        avg_range = sum(c.range for c in candles) / len(candles)

        for candle, delta in zip(recent_candles, recent_deltas):
            # High volume but small range
            if candle.volume > avg_volume * 1.5 and candle.range < avg_range * 0.5:
                # High delta but price didn't move
                if abs(delta.delta) > abs(avg_volume) * self.config.absorption_threshold:
                    return True

        return False

    def calculate_breakout_quality(
        self,
        candle: OHLCV,
        delta: DeltaData,
        avg_volume: float,
        direction: TrendDirection
    ) -> float:
        """
        Calculate the quality score of a breakout (0-100).

        Higher scores indicate stronger breakouts with better
        follow-through potential.

        Args:
            candle: Breakout candle.
            delta: Delta data for the candle.
            avg_volume: Average volume for comparison.
            direction: Direction of the breakout.

        Returns:
            Quality score from 0 to 100.
        """
        score = 50.0  # Base score

        # Volume confirmation (max +20)
        volume_ratio = candle.volume / avg_volume if avg_volume > 0 else 1
        volume_score = min(20, (volume_ratio - 1) * 20)
        score += volume_score

        # Delta confirmation (max +20)
        if direction == TrendDirection.BULLISH and delta.delta > 0:
            delta_score = min(20, abs(delta.delta_percent) * 0.4)
            score += delta_score
        elif direction == TrendDirection.BEARISH and delta.delta < 0:
            delta_score = min(20, abs(delta.delta_percent) * 0.4)
            score += delta_score
        else:
            score -= 10  # Delta divergence penalty

        # Candle structure (max +10)
        if direction == TrendDirection.BULLISH:
            # Strong bullish candle closes near high
            close_position = (candle.close - candle.low) / candle.range if candle.range > 0 else 0.5
            if close_position > 0.7:
                score += 10
            elif close_position > 0.5:
                score += 5
        else:
            # Strong bearish candle closes near low
            close_position = (candle.high - candle.close) / candle.range if candle.range > 0 else 0.5
            if close_position > 0.7:
                score += 10
            elif close_position > 0.5:
                score += 5

        return max(0, min(100, score))

    def calculate_liquidity_score(
        self,
        order_book: OrderBook,
        recent_volume: float,
        spread_history: List[float]
    ) -> float:
        """
        Calculate a liquidity score for the current market (0-100).

        Higher scores indicate better liquidity conditions.

        Args:
            order_book: Current order book.
            recent_volume: Recent average volume.
            spread_history: Historical spread values.

        Returns:
            Liquidity score from 0 to 100.
        """
        score = 50.0  # Base score

        # Spread analysis (max +25)
        if order_book.spread and spread_history:
            avg_spread = statistics.mean(spread_history)
            if order_book.spread < avg_spread * 0.8:
                score += 25
            elif order_book.spread < avg_spread:
                score += 15
            elif order_book.spread > avg_spread * 1.5:
                score -= 15

        # Order book depth (max +25)
        bid_depth = sum(level.size for level in order_book.bids[:10])
        ask_depth = sum(level.size for level in order_book.asks[:10])
        total_depth = bid_depth + ask_depth

        if recent_volume > 0:
            depth_ratio = total_depth / recent_volume
            if depth_ratio > 0.5:
                score += 25
            elif depth_ratio > 0.2:
                score += 15
            elif depth_ratio < 0.1:
                score -= 10

        return max(0, min(100, score))

    def analyze(
        self,
        candle: OHLCV,
        order_book: Optional[OrderBook] = None,
        ticks: Optional[List[TickData]] = None,
        avg_volume: Optional[float] = None
    ) -> OrderFlowAnalysis:
        """
        Perform complete order flow analysis.

        This is the main analysis method that combines all order flow
        components into a comprehensive analysis result.

        Args:
            candle: Current OHLCV candle.
            order_book: Optional order book data.
            ticks: Optional tick data for precise delta calculation.
            avg_volume: Optional average volume for comparisons.

        Returns:
            Complete OrderFlowAnalysis result.
        """
        # Calculate delta
        delta = self.calculate_delta(candle, ticks)

        # Calculate average delta for comparisons
        avg_delta = None
        if len(self._delta_history_values) >= 10:
            avg_delta = statistics.mean(
                abs(d) for d in list(self._delta_history_values)[-10:]
            )

        # Detect aggressive activity
        aggressive_buying, aggressive_selling = self.detect_aggressive_activity(delta, avg_delta)

        # Detect divergence
        divergence_detected, divergence_type = self.detect_delta_divergence()

        # Detect absorption
        absorption_detected = False
        if len(self.delta_history) >= 3:
            # Create synthetic candle list from delta history
            absorption_detected = self.detect_absorption(
                [candle] * 3,  # Simplified - would need actual candles
                self.delta_history[-3:]
            )

        # Calculate imbalance ratio (if order book available)
        imbalance_ratio = 1.0
        bid_volume = 0.0
        ask_volume = 0.0

        if order_book:
            imbalance_ratio = self.calculate_imbalance_ratio(order_book)
            bid_volume = sum(level.size for level in order_book.bids[:5])
            ask_volume = sum(level.size for level in order_book.asks[:5])

        # Calculate breakout quality
        breakout_quality = 0.0
        if avg_volume:
            direction = TrendDirection.BULLISH if delta.delta > 0 else TrendDirection.BEARISH
            breakout_quality = self.calculate_breakout_quality(
                candle, delta, avg_volume, direction
            )

        # Calculate liquidity score
        liquidity_score = 50.0  # Default
        if order_book and avg_volume:
            spread_history = []
            for ob in self._order_book_history[-20:]:
                if ob.spread:
                    spread_history.append(ob.spread)
            if spread_history:
                liquidity_score = self.calculate_liquidity_score(
                    order_book, avg_volume, spread_history
                )

        # Store order book for history
        if order_book:
            self._order_book_history.append(order_book)
            if len(self._order_book_history) > 50:
                self._order_book_history.pop(0)

        return OrderFlowAnalysis(
            timestamp=candle.timestamp,
            delta=delta,
            bid_volume=bid_volume,
            ask_volume=ask_volume,
            imbalance_ratio=imbalance_ratio,
            aggressive_buying=aggressive_buying,
            aggressive_selling=aggressive_selling,
            absorption_detected=absorption_detected,
            divergence_detected=divergence_detected,
            divergence_type=divergence_type,
            breakout_quality=breakout_quality,
            liquidity_score=liquidity_score,
        )

    def get_delta_trend(self, periods: int = 10) -> TrendDirection:
        """
        Determine the recent delta trend direction.

        Args:
            periods: Number of periods to analyze.

        Returns:
            TrendDirection of the delta.
        """
        if len(self._delta_history_values) < periods:
            return TrendDirection.NEUTRAL

        recent_deltas = list(self._delta_history_values)[-periods:]
        first_half = sum(recent_deltas[:periods//2])
        second_half = sum(recent_deltas[periods//2:])

        if second_half > first_half * 1.2:
            return TrendDirection.BULLISH
        elif second_half < first_half * 0.8:
            return TrendDirection.BEARISH
        else:
            return TrendDirection.NEUTRAL

    def get_cumulative_delta_signal(self) -> str:
        """
        Get a signal based on cumulative delta analysis.

        Returns:
            Signal string: 'bullish', 'bearish', or 'neutral'.
        """
        if not self.delta_history:
            return 'neutral'

        cd = self.cumulative_delta
        recent_avg_delta = statistics.mean(
            d.delta for d in self.delta_history[-20:]
        ) if len(self.delta_history) >= 20 else 0

        # Strong cumulative delta + positive recent trend
        if cd > 0 and recent_avg_delta > 0:
            return 'bullish'
        elif cd < 0 and recent_avg_delta < 0:
            return 'bearish'
        else:
            return 'neutral'

    def reset(self):
        """Reset all historical data."""
        self.delta_history.clear()
        self.cumulative_delta = 0.0
        self._price_history.clear()
        self._delta_history_values.clear()
        self._order_book_history.clear()


# =============================================================================
# FOOTPRINT CHART ANALYSIS
# =============================================================================

@dataclass
class FootprintBar:
    """Footprint chart bar showing buy/sell volume at each price level."""
    timestamp: datetime
    price_levels: Dict[float, Tuple[float, float]] = field(default_factory=dict)  # price -> (buy_vol, sell_vol)
    high: float = 0.0
    low: float = 0.0
    total_buy_volume: float = 0.0
    total_sell_volume: float = 0.0

    @property
    def delta(self) -> float:
        """Calculate total delta for the bar."""
        return self.total_buy_volume - self.total_sell_volume

    @property
    def imbalances(self) -> List[Tuple[float, str, float]]:
        """Find imbalance levels (price, type, ratio)."""
        imbalances = []
        sorted_prices = sorted(self.price_levels.keys())

        for i, price in enumerate(sorted_prices):
            buy_vol, sell_vol = self.price_levels[price]

            # Check buy imbalance
            if sell_vol > 0 and buy_vol / sell_vol > 3:
                imbalances.append((price, 'buy', buy_vol / sell_vol))

            # Check sell imbalance
            if buy_vol > 0 and sell_vol / buy_vol > 3:
                imbalances.append((price, 'sell', sell_vol / buy_vol))

        return imbalances


class FootprintAnalyzer:
    """
    Analyzes footprint charts for detailed order flow insight.

    Footprint charts show buy and sell volume at each price level,
    revealing where the real buying and selling is occurring.
    """

    def __init__(self, tick_size: float = 0.01):
        """
        Initialize the Footprint Analyzer.

        Args:
            tick_size: Minimum price increment.
        """
        self.tick_size = tick_size
        self.bars: List[FootprintBar] = []

    def create_footprint_bar(
        self,
        ticks: List[TickData],
        candle: OHLCV
    ) -> FootprintBar:
        """
        Create a footprint bar from tick data.

        Args:
            ticks: List of tick data for the period.
            candle: Corresponding OHLCV candle.

        Returns:
            FootprintBar with volume distribution.
        """
        price_levels: Dict[float, Tuple[float, float]] = {}

        for tick in ticks:
            # Round to tick size
            price = round(tick.price / self.tick_size) * self.tick_size

            if price not in price_levels:
                price_levels[price] = (0.0, 0.0)

            buy_vol, sell_vol = price_levels[price]
            if tick.side == 'buy':
                price_levels[price] = (buy_vol + tick.volume, sell_vol)
            else:
                price_levels[price] = (buy_vol, sell_vol + tick.volume)

        total_buy = sum(bv for bv, sv in price_levels.values())
        total_sell = sum(sv for bv, sv in price_levels.values())

        bar = FootprintBar(
            timestamp=candle.timestamp,
            price_levels=price_levels,
            high=candle.high,
            low=candle.low,
            total_buy_volume=total_buy,
            total_sell_volume=total_sell,
        )

        self.bars.append(bar)
        return bar

    def find_stacked_imbalances(
        self,
        bar: FootprintBar,
        min_stack: int = 3
    ) -> List[Tuple[float, float, str]]:
        """
        Find stacked imbalances (consecutive imbalance levels).

        Stacked imbalances indicate strong institutional activity.

        Args:
            bar: Footprint bar to analyze.
            min_stack: Minimum consecutive levels to count as stacked.

        Returns:
            List of tuples (start_price, end_price, type).
        """
        imbalances = bar.imbalances
        if len(imbalances) < min_stack:
            return []

        stacked = []
        sorted_imbalances = sorted(imbalances, key=lambda x: x[0])

        i = 0
        while i < len(sorted_imbalances):
            current_type = sorted_imbalances[i][1]
            start_price = sorted_imbalances[i][0]
            end_price = start_price
            count = 1

            j = i + 1
            while j < len(sorted_imbalances):
                price_diff = abs(sorted_imbalances[j][0] - end_price)
                if price_diff <= self.tick_size * 2 and sorted_imbalances[j][1] == current_type:
                    end_price = sorted_imbalances[j][0]
                    count += 1
                    j += 1
                else:
                    break

            if count >= min_stack:
                stacked.append((start_price, end_price, current_type))

            i = j

        return stacked

    def detect_finished_auction(
        self,
        bar: FootprintBar
    ) -> Tuple[bool, Optional[str]]:
        """
        Detect if an auction has finished (exhaustion).

        A finished auction shows thin volume at extremes with
        rejection (excess) in the footprint.

        Args:
            bar: Footprint bar to analyze.

        Returns:
            Tuple of (auction_finished, direction).
        """
        if not bar.price_levels:
            return False, None

        sorted_prices = sorted(bar.price_levels.keys())

        # Check high
        high_prices = sorted_prices[-3:] if len(sorted_prices) >= 3 else sorted_prices
        high_buy_vol = sum(bar.price_levels[p][0] for p in high_prices)
        high_sell_vol = sum(bar.price_levels[p][1] for p in high_prices)

        # If sellers dominate at high - potential top
        if high_sell_vol > high_buy_vol * 2:
            return True, 'top'

        # Check low
        low_prices = sorted_prices[:3] if len(sorted_prices) >= 3 else sorted_prices
        low_buy_vol = sum(bar.price_levels[p][0] for p in low_prices)
        low_sell_vol = sum(bar.price_levels[p][1] for p in low_prices)

        # If buyers dominate at low - potential bottom
        if low_buy_vol > low_sell_vol * 2:
            return True, 'bottom'

        return False, None


# =============================================================================
# DOM (DEPTH OF MARKET) ANALYSIS
# =============================================================================

class DOMAnalyzer:
    """
    Analyzes Depth of Market (DOM) / Level 2 data.

    DOM analysis reveals pending orders and potential support/resistance
    levels based on where limit orders are clustered.
    """

    def __init__(self):
        """Initialize the DOM Analyzer."""
        self.snapshots: List[OrderBook] = []

    def find_large_orders(
        self,
        order_book: OrderBook,
        threshold_percentile: float = 90
    ) -> Tuple[List[OrderBookLevel], List[OrderBookLevel]]:
        """
        Find unusually large orders in the order book.

        Args:
            order_book: Current order book snapshot.
            threshold_percentile: Percentile threshold for "large" orders.

        Returns:
            Tuple of (large_bids, large_asks).
        """
        all_sizes = [l.size for l in order_book.bids + order_book.asks]
        if not all_sizes:
            return [], []

        threshold = statistics.quantiles(all_sizes, n=100)[int(threshold_percentile) - 1]

        large_bids = [l for l in order_book.bids if l.size >= threshold]
        large_asks = [l for l in order_book.asks if l.size >= threshold]

        return large_bids, large_asks

    def detect_spoofing(
        self,
        snapshots: List[OrderBook],
        min_snapshots: int = 5
    ) -> List[Tuple[float, str]]:
        """
        Detect potential spoofing activity.

        Spoofing is when large orders are placed and quickly cancelled,
        designed to manipulate price perception.

        Args:
            snapshots: Recent order book snapshots.
            min_snapshots: Minimum snapshots needed for detection.

        Returns:
            List of suspected spoofing levels (price, side).
        """
        if len(snapshots) < min_snapshots:
            return []

        suspected = []

        # Track large orders that appear and disappear quickly
        for i in range(1, len(snapshots)):
            prev = snapshots[i - 1]
            curr = snapshots[i]

            # Check bids
            prev_large_bids = {l.price: l.size for l in prev.bids if l.size > 1000}
            curr_bid_prices = {l.price for l in curr.bids}

            for price, size in prev_large_bids.items():
                if price not in curr_bid_prices:
                    # Large bid disappeared - check if price moved away
                    if curr.best_ask and price < curr.best_ask:
                        suspected.append((price, 'bid'))

            # Check asks
            prev_large_asks = {l.price: l.size for l in prev.asks if l.size > 1000}
            curr_ask_prices = {l.price for l in curr.asks}

            for price, size in prev_large_asks.items():
                if price not in curr_ask_prices:
                    if curr.best_bid and price > curr.best_bid:
                        suspected.append((price, 'ask'))

        return suspected

    def calculate_book_pressure(
        self,
        order_book: OrderBook,
        levels: int = 10
    ) -> float:
        """
        Calculate the buying/selling pressure from the order book.

        Positive values indicate buying pressure, negative indicates selling.

        Args:
            order_book: Current order book.
            levels: Number of levels to analyze.

        Returns:
            Pressure value (-100 to 100).
        """
        bid_volume = sum(l.size for l in order_book.bids[:levels])
        ask_volume = sum(l.size for l in order_book.asks[:levels])

        total = bid_volume + ask_volume
        if total == 0:
            return 0.0

        # Normalize to -100 to 100 scale
        pressure = ((bid_volume - ask_volume) / total) * 100
        return pressure


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    'OrderFlowAnalyzer',
    'FootprintBar',
    'FootprintAnalyzer',
    'DOMAnalyzer',
]
