"""
Correlation and Market Breadth Analysis Module.

This module provides comprehensive correlation analysis including:
- Magnificent 7 (Mag7) stocks analysis
- VIX analysis and divergence detection
- Market breadth indicators
- Intermarket correlations
- Sector rotation analysis
- Market health scoring

Author: AMT Trading Bot
Version: 1.0.0
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import statistics
from collections import deque

from config import (
    CorrelationData,
    MarketBreadth,
    Mag7Analysis,
    VIXAnalysis,
    CorrelationAnalysisResult,
    CorrelationConfig,
    TrendDirection,
    get_default_config,
)


class CorrelationAnalyzer:
    """
    Analyzes correlations between assets and market breadth.

    This analyzer helps understand the broader market context and
    whether individual signals are confirmed by the overall market.

    Attributes:
        config: Correlation configuration settings.
        price_history: Historical price data by symbol.
    """

    def __init__(self, config: Optional[CorrelationConfig] = None):
        """
        Initialize the Correlation Analyzer.

        Args:
            config: Optional configuration. Uses defaults if not provided.
        """
        self.config = config or get_default_config().correlation
        self.price_history: Dict[str, deque] = {}
        self.correlation_history: List[CorrelationData] = []
        self._vix_history: deque = deque(maxlen=252)  # ~1 year of daily data
        self._breadth_history: List[MarketBreadth] = []

    def update_price(self, symbol: str, price: float):
        """
        Update price history for a symbol.

        Args:
            symbol: Asset symbol.
            price: Current price.
        """
        if symbol not in self.price_history:
            self.price_history[symbol] = deque(maxlen=self.config.correlation_lookback * 2)
        self.price_history[symbol].append(price)

    def calculate_correlation(
        self,
        symbol1: str,
        symbol2: str,
        lookback: Optional[int] = None
    ) -> CorrelationData:
        """
        Calculate correlation between two assets.

        Uses Pearson correlation coefficient on returns.

        Args:
            symbol1: First asset symbol.
            symbol2: Second asset symbol.
            lookback: Number of periods for correlation. Uses config default.

        Returns:
            CorrelationData with calculated values.
        """
        lookback = lookback or self.config.correlation_lookback

        if symbol1 not in self.price_history or symbol2 not in self.price_history:
            return CorrelationData(
                asset1=symbol1,
                asset2=symbol2,
                correlation=0.0,
                rolling_correlation=0.0,
                divergence_detected=False,
                correlation_regime='neutral',
            )

        prices1 = list(self.price_history[symbol1])
        prices2 = list(self.price_history[symbol2])

        # Need at least lookback prices
        min_len = min(len(prices1), len(prices2), lookback)
        if min_len < 5:
            return CorrelationData(
                asset1=symbol1,
                asset2=symbol2,
                correlation=0.0,
                rolling_correlation=0.0,
                divergence_detected=False,
                correlation_regime='neutral',
            )

        prices1 = prices1[-min_len:]
        prices2 = prices2[-min_len:]

        # Calculate returns
        returns1 = [(prices1[i] - prices1[i-1]) / prices1[i-1] for i in range(1, len(prices1))]
        returns2 = [(prices2[i] - prices2[i-1]) / prices2[i-1] for i in range(1, len(prices2))]

        # Calculate correlation
        correlation = self._pearson_correlation(returns1, returns2)

        # Calculate rolling correlation (shorter period)
        rolling_len = min(10, len(returns1))
        rolling_correlation = self._pearson_correlation(
            returns1[-rolling_len:],
            returns2[-rolling_len:]
        )

        # Detect divergence
        divergence = self._detect_correlation_divergence(
            correlation, rolling_correlation
        )

        # Determine regime
        regime = self._classify_correlation_regime(correlation)

        corr_data = CorrelationData(
            asset1=symbol1,
            asset2=symbol2,
            correlation=correlation,
            rolling_correlation=rolling_correlation,
            divergence_detected=divergence,
            correlation_regime=regime,
        )

        self.correlation_history.append(corr_data)
        return corr_data

    def _pearson_correlation(
        self,
        x: List[float],
        y: List[float]
    ) -> float:
        """
        Calculate Pearson correlation coefficient.

        Args:
            x: First data series.
            y: Second data series.

        Returns:
            Correlation coefficient (-1 to 1).
        """
        if len(x) != len(y) or len(x) < 2:
            return 0.0

        n = len(x)
        mean_x = sum(x) / n
        mean_y = sum(y) / n

        numerator = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
        denominator_x = sum((xi - mean_x) ** 2 for xi in x) ** 0.5
        denominator_y = sum((yi - mean_y) ** 2 for yi in y) ** 0.5

        if denominator_x == 0 or denominator_y == 0:
            return 0.0

        return numerator / (denominator_x * denominator_y)

    def _detect_correlation_divergence(
        self,
        long_term: float,
        short_term: float
    ) -> bool:
        """
        Detect if correlation is diverging from historical norm.

        Args:
            long_term: Long-term correlation.
            short_term: Short-term (rolling) correlation.

        Returns:
            True if significant divergence detected.
        """
        return abs(long_term - short_term) > self.config.divergence_threshold

    def _classify_correlation_regime(self, correlation: float) -> str:
        """
        Classify the correlation regime.

        Args:
            correlation: Correlation coefficient.

        Returns:
            Regime string: 'positive', 'negative', or 'neutral'.
        """
        if correlation > self.config.correlation_threshold:
            return 'positive'
        elif correlation < -self.config.correlation_threshold:
            return 'negative'
        else:
            return 'neutral'

    def analyze_mag7(
        self,
        mag7_prices: Dict[str, float],
        index_price: float,
        prev_mag7_prices: Optional[Dict[str, float]] = None,
        prev_index_price: Optional[float] = None
    ) -> Mag7Analysis:
        """
        Analyze Magnificent 7 stocks relative to the index.

        The Mag7 stocks often lead market moves and their
        confirmation (or divergence) is significant.

        Args:
            mag7_prices: Current prices for Mag7 stocks.
            index_price: Current index (e.g., SPY) price.
            prev_mag7_prices: Previous prices for comparison.
            prev_index_price: Previous index price.

        Returns:
            Mag7Analysis with calculated values.
        """
        performances = {}
        for symbol in self.config.mag7_symbols:
            if symbol in mag7_prices:
                current = mag7_prices[symbol]
                if prev_mag7_prices and symbol in prev_mag7_prices:
                    prev = prev_mag7_prices[symbol]
                    if prev > 0:
                        performances[symbol] = ((current - prev) / prev) * 100
                else:
                    performances[symbol] = 0.0

                # Update price history
                self.update_price(symbol, current)

        # Calculate average performance
        avg_performance = statistics.mean(performances.values()) if performances else 0.0

        # Calculate index performance
        index_performance = 0.0
        if prev_index_price and prev_index_price > 0:
            index_performance = ((index_price - prev_index_price) / prev_index_price) * 100

        # Calculate confirmation score
        # Positive if Mag7 confirms index direction, negative if diverging
        if index_performance > 0:
            if avg_performance > index_performance:
                confirmation_score = min(100, (avg_performance / index_performance - 1) * 100 + 50)
            else:
                confirmation_score = max(-100, (avg_performance / index_performance - 1) * 100 + 50)
        elif index_performance < 0:
            if avg_performance < index_performance:
                confirmation_score = min(100, (index_performance / avg_performance - 1) * 100 + 50)
            else:
                confirmation_score = max(-100, -(avg_performance / index_performance - 1) * 100 + 50)
        else:
            confirmation_score = 50.0  # Neutral

        # Calculate divergence from index
        divergence = avg_performance - index_performance

        # Leadership score: how much Mag7 is outperforming
        leadership_score = 50.0 + (avg_performance - index_performance) * 10
        leadership_score = max(0, min(100, leadership_score))

        return Mag7Analysis(
            timestamp=datetime.now(),
            stocks=performances,
            average_performance=avg_performance,
            confirmation_score=confirmation_score,
            divergence_from_index=divergence,
            leadership_score=leadership_score,
        )

    def analyze_vix(
        self,
        current_vix: float,
        index_direction: TrendDirection
    ) -> VIXAnalysis:
        """
        Analyze VIX (volatility index) for market signals.

        VIX typically moves inverse to the market. Divergence
        from this relationship can signal potential reversals.

        Args:
            current_vix: Current VIX level.
            index_direction: Current index trend direction.

        Returns:
            VIXAnalysis with calculated values.
        """
        self._vix_history.append(current_vix)

        # Calculate percentile rank
        if len(self._vix_history) >= 20:
            vix_list = list(self._vix_history)
            below_current = sum(1 for v in vix_list if v < current_vix)
            percentile_rank = (below_current / len(vix_list)) * 100
        else:
            percentile_rank = 50.0

        # Determine if elevated
        is_elevated = current_vix > self.config.vix_elevated_threshold

        # Determine term structure (simplified - would need VIX futures)
        # Using VIX trend as proxy
        if len(self._vix_history) >= 5:
            recent_avg = statistics.mean(list(self._vix_history)[-5:])
            older_avg = statistics.mean(list(self._vix_history)[-20:-5]) if len(self._vix_history) >= 20 else recent_avg

            if recent_avg < older_avg * 0.95:
                term_structure = 'contango'  # VIX declining
            elif recent_avg > older_avg * 1.05:
                term_structure = 'backwardation'  # VIX rising
            else:
                term_structure = 'flat'
        else:
            term_structure = 'flat'

        # Detect divergence
        is_diverging = False
        divergence_type = None

        if len(self._vix_history) >= 5:
            vix_trend = list(self._vix_history)[-5:]
            vix_rising = vix_trend[-1] > vix_trend[0]
            vix_falling = vix_trend[-1] < vix_trend[0]

            # Bullish divergence: market down, VIX down (fear decreasing)
            if index_direction == TrendDirection.BEARISH and vix_falling:
                is_diverging = True
                divergence_type = 'bullish'

            # Bearish divergence: market up, VIX up (fear increasing)
            if index_direction == TrendDirection.BULLISH and vix_rising:
                is_diverging = True
                divergence_type = 'bearish'

        return VIXAnalysis(
            timestamp=datetime.now(),
            current_level=current_vix,
            percentile_rank=percentile_rank,
            term_structure=term_structure,
            is_elevated=is_elevated,
            is_diverging=is_diverging,
            divergence_type=divergence_type,
        )

    def calculate_market_breadth(
        self,
        advances: int,
        declines: int,
        unchanged: int,
        new_highs: int,
        new_lows: int,
        above_50ma: float,
        above_200ma: float
    ) -> MarketBreadth:
        """
        Calculate market breadth indicators.

        Breadth measures the participation of stocks in a market move,
        helping validate whether moves are broad-based or narrow.

        Args:
            advances: Number of advancing stocks.
            declines: Number of declining stocks.
            unchanged: Number of unchanged stocks.
            new_highs: Number of stocks at new highs.
            new_lows: Number of stocks at new lows.
            above_50ma: Percentage of stocks above 50-day MA.
            above_200ma: Percentage of stocks above 200-day MA.

        Returns:
            MarketBreadth with calculated values.
        """
        # Advance/Decline ratio
        ad_ratio = advances / declines if declines > 0 else float('inf')

        # Advance/Decline line (cumulative)
        prev_ad_line = self._breadth_history[-1].advance_decline_line if self._breadth_history else 0.0
        ad_line = prev_ad_line + (advances - declines)

        # McClellan Oscillator (simplified)
        # Uses exponential moving averages of advance-decline difference
        ad_diff = advances - declines
        mcclellan = self._calculate_mcclellan(ad_diff)

        # Breadth thrust indicator
        total = advances + declines + unchanged
        breadth_thrust = (advances / total * 100) if total > 0 else 50.0

        breadth = MarketBreadth(
            timestamp=datetime.now(),
            advance_decline_ratio=ad_ratio,
            advance_decline_line=ad_line,
            new_highs=new_highs,
            new_lows=new_lows,
            percent_above_50ma=above_50ma,
            percent_above_200ma=above_200ma,
            mcclellan_oscillator=mcclellan,
            breadth_thrust=breadth_thrust,
        )

        self._breadth_history.append(breadth)
        return breadth

    def _calculate_mcclellan(self, ad_diff: float) -> float:
        """
        Calculate McClellan Oscillator.

        Simplified calculation using recent breadth data.

        Args:
            ad_diff: Today's advance-decline difference.

        Returns:
            McClellan Oscillator value.
        """
        if len(self._breadth_history) < 19:
            return 0.0

        # Get recent A-D differences (from A-D line changes)
        recent = [
            self._breadth_history[i].advance_decline_line - self._breadth_history[i-1].advance_decline_line
            for i in range(max(1, len(self._breadth_history) - 19), len(self._breadth_history))
        ]
        recent.append(ad_diff)

        # 19-day EMA
        ema_19 = self._calculate_ema(recent, 19)

        # 39-day EMA (use what we have)
        if len(self._breadth_history) >= 38:
            longer = [
                self._breadth_history[i].advance_decline_line - self._breadth_history[i-1].advance_decline_line
                for i in range(max(1, len(self._breadth_history) - 38), len(self._breadth_history))
            ]
            longer.append(ad_diff)
            ema_39 = self._calculate_ema(longer, 39)
        else:
            ema_39 = ema_19

        return ema_19 - ema_39

    def _calculate_ema(self, data: List[float], period: int) -> float:
        """
        Calculate Exponential Moving Average.

        Args:
            data: Price data.
            period: EMA period.

        Returns:
            EMA value.
        """
        if not data:
            return 0.0

        multiplier = 2 / (period + 1)
        ema = data[0]

        for price in data[1:]:
            ema = (price - ema) * multiplier + ema

        return ema

    def analyze_sector_rotation(
        self,
        sector_performances: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Analyze sector rotation patterns.

        Sector rotation reveals risk appetite and economic expectations.

        Args:
            sector_performances: Dictionary of sector -> performance.

        Returns:
            Dictionary with rotation signals.
        """
        if not sector_performances:
            return {}

        # Define sector characteristics
        cyclical = ['XLY', 'XLI', 'XLB', 'XLF']  # Consumer Discretionary, Industrials, Materials, Financials
        defensive = ['XLU', 'XLP', 'XLV', 'XLRE']  # Utilities, Consumer Staples, Health Care, Real Estate
        growth = ['XLK', 'XLC']  # Technology, Communication Services
        value = ['XLE', 'XLF']  # Energy, Financials

        # Calculate average performances
        cyclical_perf = statistics.mean(
            [sector_performances.get(s, 0) for s in cyclical if s in sector_performances]
        ) if any(s in sector_performances for s in cyclical) else 0.0

        defensive_perf = statistics.mean(
            [sector_performances.get(s, 0) for s in defensive if s in sector_performances]
        ) if any(s in sector_performances for s in defensive) else 0.0

        growth_perf = statistics.mean(
            [sector_performances.get(s, 0) for s in growth if s in sector_performances]
        ) if any(s in sector_performances for s in growth) else 0.0

        value_perf = statistics.mean(
            [sector_performances.get(s, 0) for s in value if s in sector_performances]
        ) if any(s in sector_performances for s in value) else 0.0

        return {
            'cyclical_vs_defensive': cyclical_perf - defensive_perf,
            'growth_vs_value': growth_perf - value_perf,
            'risk_appetite': (cyclical_perf + growth_perf) / 2 - (defensive_perf + value_perf) / 2,
            'cyclical_performance': cyclical_perf,
            'defensive_performance': defensive_perf,
            'growth_performance': growth_perf,
            'value_performance': value_perf,
        }

    def calculate_market_health_score(
        self,
        mag7: Mag7Analysis,
        vix: VIXAnalysis,
        breadth: MarketBreadth,
        sector_rotation: Dict[str, float]
    ) -> float:
        """
        Calculate overall market health score (0-100).

        Combines multiple market indicators into a single health metric.

        Args:
            mag7: Mag7 analysis result.
            vix: VIX analysis result.
            breadth: Market breadth data.
            sector_rotation: Sector rotation analysis.

        Returns:
            Market health score from 0 to 100.
        """
        score = 50.0  # Base score

        # Mag7 contribution (max +/- 15)
        score += (mag7.confirmation_score - 50) * 0.3

        # VIX contribution (max +/- 15)
        if vix.is_elevated:
            score -= 10
        if vix.is_diverging:
            if vix.divergence_type == 'bullish':
                score += 10
            elif vix.divergence_type == 'bearish':
                score -= 10
        # Lower VIX percentile is healthier
        score += (50 - vix.percentile_rank) * 0.1

        # Breadth contribution (max +/- 20)
        breadth_score = breadth.breadth_score
        score += (breadth_score - 50) * 0.4

        # Sector rotation contribution (max +/- 10)
        risk_appetite = sector_rotation.get('risk_appetite', 0)
        score += risk_appetite * 2

        return max(0, min(100, score))

    def analyze(
        self,
        mag7_prices: Dict[str, float],
        index_price: float,
        vix_level: float,
        index_direction: TrendDirection,
        breadth_data: Optional[Dict] = None,
        sector_performances: Optional[Dict[str, float]] = None,
        prev_mag7_prices: Optional[Dict[str, float]] = None,
        prev_index_price: Optional[float] = None
    ) -> CorrelationAnalysisResult:
        """
        Perform complete correlation and breadth analysis.

        This is the main analysis method that combines all correlation
        components into a comprehensive analysis result.

        Args:
            mag7_prices: Current Mag7 stock prices.
            index_price: Current index price.
            vix_level: Current VIX level.
            index_direction: Current index trend direction.
            breadth_data: Optional market breadth data.
            sector_performances: Optional sector performance data.
            prev_mag7_prices: Previous Mag7 prices.
            prev_index_price: Previous index price.

        Returns:
            Complete CorrelationAnalysisResult.
        """
        # Analyze Mag7
        mag7 = self.analyze_mag7(
            mag7_prices, index_price, prev_mag7_prices, prev_index_price
        )

        # Analyze VIX
        vix = self.analyze_vix(vix_level, index_direction)

        # Calculate breadth
        if breadth_data:
            breadth = self.calculate_market_breadth(
                advances=breadth_data.get('advances', 0),
                declines=breadth_data.get('declines', 0),
                unchanged=breadth_data.get('unchanged', 0),
                new_highs=breadth_data.get('new_highs', 0),
                new_lows=breadth_data.get('new_lows', 0),
                above_50ma=breadth_data.get('above_50ma', 50.0),
                above_200ma=breadth_data.get('above_200ma', 50.0),
            )
        else:
            # Default breadth
            breadth = MarketBreadth(
                timestamp=datetime.now(),
                advance_decline_ratio=1.0,
                advance_decline_line=0.0,
                new_highs=0,
                new_lows=0,
                percent_above_50ma=50.0,
                percent_above_200ma=50.0,
                mcclellan_oscillator=0.0,
                breadth_thrust=50.0,
            )

        # Analyze sector rotation
        sector_rotation = {}
        if sector_performances:
            sector_rotation = self.analyze_sector_rotation(sector_performances)

        # Calculate intermarket signals
        intermarket_signals = self._generate_intermarket_signals(
            mag7, vix, breadth, sector_rotation
        )

        # Calculate overall health score
        health_score = self.calculate_market_health_score(
            mag7, vix, breadth, sector_rotation
        )

        return CorrelationAnalysisResult(
            timestamp=datetime.now(),
            mag7=mag7,
            vix=vix,
            breadth=breadth,
            sector_rotation=sector_rotation,
            intermarket_signals=intermarket_signals,
            market_health_score=health_score,
        )

    def _generate_intermarket_signals(
        self,
        mag7: Mag7Analysis,
        vix: VIXAnalysis,
        breadth: MarketBreadth,
        sector_rotation: Dict[str, float]
    ) -> Dict[str, str]:
        """
        Generate intermarket relationship signals.

        Args:
            mag7: Mag7 analysis.
            vix: VIX analysis.
            breadth: Market breadth.
            sector_rotation: Sector rotation data.

        Returns:
            Dictionary of signal_type -> signal_description.
        """
        signals = {}

        # Mag7 leadership signal
        if mag7.leadership_score > 70:
            signals['mag7'] = 'Strong leadership - bullish confirmation'
        elif mag7.leadership_score < 30:
            signals['mag7'] = 'Weak leadership - potential concern'
        else:
            signals['mag7'] = 'Neutral leadership'

        # VIX signal
        if vix.is_diverging:
            signals['vix'] = f'{vix.divergence_type.capitalize()} divergence detected'
        elif vix.is_elevated:
            signals['vix'] = 'Elevated fear - caution warranted'
        else:
            signals['vix'] = 'Complacency zone'

        # Breadth signal
        if breadth.breadth_thrust > 70:
            signals['breadth'] = 'Strong breadth thrust - bullish'
        elif breadth.breadth_thrust < 30:
            signals['breadth'] = 'Weak breadth - bearish'
        else:
            signals['breadth'] = 'Normal breadth'

        # Risk appetite signal
        risk = sector_rotation.get('risk_appetite', 0)
        if risk > 1:
            signals['risk'] = 'Risk-on environment'
        elif risk < -1:
            signals['risk'] = 'Risk-off environment'
        else:
            signals['risk'] = 'Mixed risk sentiment'

        return signals

    def get_confirmation_level(
        self,
        signal_direction: TrendDirection,
        analysis: CorrelationAnalysisResult
    ) -> Tuple[float, List[str]]:
        """
        Get the level of confirmation for a signal direction.

        Args:
            signal_direction: Direction of the trading signal.
            analysis: Complete correlation analysis.

        Returns:
            Tuple of (confirmation_score, list of reasons).
        """
        score = 50.0
        reasons = []

        if signal_direction == TrendDirection.BULLISH:
            # Check bullish confirmations
            if analysis.mag7.confirmation_score > 60:
                score += 15
                reasons.append("Mag7 confirming bullish")
            if analysis.vix.divergence_type == 'bullish':
                score += 10
                reasons.append("VIX bullish divergence")
            if analysis.breadth.breadth_thrust > 60:
                score += 10
                reasons.append("Strong market breadth")
            if analysis.sector_rotation.get('risk_appetite', 0) > 0:
                score += 5
                reasons.append("Risk-on rotation")

            # Check bearish warnings
            if analysis.vix.is_elevated:
                score -= 10
                reasons.append("Warning: VIX elevated")
            if analysis.breadth.breadth_thrust < 40:
                score -= 10
                reasons.append("Warning: Weak breadth")

        elif signal_direction == TrendDirection.BEARISH:
            # Check bearish confirmations
            if analysis.mag7.confirmation_score < 40:
                score += 15
                reasons.append("Mag7 confirming bearish")
            if analysis.vix.divergence_type == 'bearish':
                score += 10
                reasons.append("VIX bearish divergence")
            if analysis.breadth.breadth_thrust < 40:
                score += 10
                reasons.append("Weak market breadth")
            if analysis.sector_rotation.get('risk_appetite', 0) < 0:
                score += 5
                reasons.append("Risk-off rotation")

            # Check bullish warnings
            if analysis.vix.divergence_type == 'bullish':
                score -= 10
                reasons.append("Warning: VIX bullish divergence")
            if analysis.breadth.breadth_thrust > 60:
                score -= 10
                reasons.append("Warning: Strong breadth")

        return max(0, min(100, score)), reasons

    def reset(self):
        """Reset all historical data."""
        self.price_history.clear()
        self.correlation_history.clear()
        self._vix_history.clear()
        self._breadth_history.clear()


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    'CorrelationAnalyzer',
]
