"""
Main Strategy Engine Module.

This module combines all analysis components to generate trading signals:
- Market structure analysis (AMT)
- Order flow analysis
- Correlation analysis
- Technical indicators
- Risk management integration

Author: AMT Trading Bot
Version: 1.0.0
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING
from enum import Enum

if TYPE_CHECKING:
    from signal import Signal

from config import (
    OHLCV,
    OrderBook,
    TickData,
    TradingSignal,
    SignalType,
    PositionSide,
    TrendDirection,
    MarketCondition,
    StrategyConfig,
    BotConfig,
    get_default_config,
)

from market_structure import MarketStructureAnalyzer
from order_flow import OrderFlowAnalyzer
from correlation_analysis import CorrelationAnalyzer
from indicators import TechnicalIndicators
from risk_management import RiskManager


class SignalStrength(Enum):
    """Signal strength classification."""
    WEAK = 1
    MODERATE = 2
    STRONG = 3
    VERY_STRONG = 4


@dataclass
class AnalysisResult:
    """Combined analysis result from all components."""
    timestamp: datetime
    market_structure: Optional[object] = None
    order_flow: Optional[object] = None
    correlation: Optional[object] = None
    indicators: Optional[object] = None
    signal: Optional[TradingSignal] = None
    webhook_signal: Optional["Signal"] = None  # Standardized signal for webhooks
    signal_strength: SignalStrength = SignalStrength.WEAK
    confluence_score: float = 0.0
    notes: List[str] = field(default_factory=list)


class StrategyEngine:
    """
    Main strategy engine that combines all analysis components.

    This engine orchestrates all the analyzers and generates trading
    signals based on confluence of multiple factors.

    Attributes:
        config: Strategy configuration.
        market_analyzer: Market structure analyzer.
        order_flow: Order flow analyzer.
        correlation: Correlation analyzer.
        indicators: Technical indicators.
        risk_manager: Risk manager.
    """

    def __init__(
        self,
        config: Optional[BotConfig] = None,
        risk_manager: Optional[RiskManager] = None
    ):
        """
        Initialize the Strategy Engine.

        Args:
            config: Optional bot configuration. Uses defaults if not provided.
            risk_manager: Optional risk manager. Creates new one if not provided.
        """
        self.config = config or get_default_config()
        self.strategy_config = self.config.strategy

        # Initialize analyzers
        self.market_analyzer = MarketStructureAnalyzer(self.config.market_structure)
        self.order_flow = OrderFlowAnalyzer(self.config.order_flow)
        self.correlation = CorrelationAnalyzer(self.config.correlation)
        self.indicators = TechnicalIndicators(self.config.indicators)

        # Risk manager
        self.risk_manager = risk_manager or RiskManager(
            self.config.risk,
            self.config.initial_capital
        )

        # State
        self._last_signal: Optional[TradingSignal] = None
        self._signal_history: List[TradingSignal] = []
        self._candle_history: List[OHLCV] = []

    def analyze(
        self,
        candles: List[OHLCV],
        current_price: float,
        order_book: Optional[OrderBook] = None,
        ticks: Optional[List[TickData]] = None,
        mag7_prices: Optional[Dict[str, float]] = None,
        vix_level: Optional[float] = None,
        breadth_data: Optional[Dict] = None
    ) -> AnalysisResult:
        """
        Perform complete market analysis.

        This is the main analysis method that combines all components
        and optionally generates trading signals.

        Args:
            candles: Historical OHLCV data.
            current_price: Current market price.
            order_book: Optional order book data.
            ticks: Optional tick data.
            mag7_prices: Optional Mag7 stock prices.
            vix_level: Optional VIX level.
            breadth_data: Optional market breadth data.

        Returns:
            AnalysisResult with complete analysis.
        """
        result = AnalysisResult(timestamp=datetime.now())
        notes = []

        # Update candle history
        if candles:
            self._candle_history = candles
            for candle in candles:
                self.indicators.update(candle)

        # Calculate ATR for various calculations
        atr = self.indicators.calculate_atr(candles)

        # 1. Market Structure Analysis
        if candles:
            avg_volume = sum(c.volume for c in candles) / len(candles)
            market_structure = self.market_analyzer.analyze(
                candles, current_price, atr, avg_volume
            )
            result.market_structure = market_structure
            notes.append(f"Market: {market_structure.condition.name}, Trend: {market_structure.trend.name}")

            if market_structure.is_breakout:
                notes.append(f"Breakout detected: {market_structure.breakout_direction.name}")
            if market_structure.is_rejection:
                notes.append(f"Rejection at {market_structure.rejection_level:.2f}")

        # 2. Order Flow Analysis
        if candles:
            latest_candle = candles[-1]
            order_flow_analysis = self.order_flow.analyze(
                latest_candle,
                order_book,
                ticks,
                avg_volume if candles else None
            )
            result.order_flow = order_flow_analysis

            if order_flow_analysis.divergence_detected:
                notes.append(f"Order flow divergence: {order_flow_analysis.divergence_type}")
            if order_flow_analysis.aggressive_buying:
                notes.append("Aggressive buying detected")
            if order_flow_analysis.aggressive_selling:
                notes.append("Aggressive selling detected")

        # 3. Correlation Analysis
        if mag7_prices and vix_level:
            # Get previous prices if available
            prev_mag7 = None
            prev_index = None

            correlation_result = self.correlation.analyze(
                mag7_prices=mag7_prices,
                index_price=current_price,
                vix_level=vix_level,
                index_direction=market_structure.trend if market_structure else TrendDirection.NEUTRAL,
                breadth_data=breadth_data,
                prev_mag7_prices=prev_mag7,
                prev_index_price=prev_index,
            )
            result.correlation = correlation_result
            notes.append(f"Market health: {correlation_result.market_health_score:.1f}")

        # 4. Technical Indicators
        indicator_set = self.indicators.calculate_all()
        result.indicators = indicator_set

        if indicator_set.rsi.divergence:
            notes.append(f"RSI divergence: {indicator_set.rsi.divergence}")
        if indicator_set.macd.crossover:
            notes.append(f"MACD crossover: {indicator_set.macd.crossover}")
        if indicator_set.bollinger.squeeze:
            notes.append("Bollinger squeeze detected")

        # 5. Generate Signal
        signal = self._generate_signal(result, current_price, atr)
        result.signal = signal

        if signal and signal.signal_type != SignalType.NO_SIGNAL:
            self._last_signal = signal
            self._signal_history.append(signal)
            notes.append(f"Signal: {signal.signal_type.name} @ {signal.entry_price:.2f}")

            # Generate standardized webhook signal
            result.webhook_signal = signal.to_signal(
                self.strategy_config.primary_timeframe.value
            )

        # Calculate confluence and strength
        result.confluence_score = self._calculate_confluence(result)
        result.signal_strength = self._classify_signal_strength(result.confluence_score)
        result.notes = notes

        return result

    def _generate_signal(
        self,
        analysis: AnalysisResult,
        current_price: float,
        atr: float
    ) -> Optional[TradingSignal]:
        """
        Generate trading signal based on analysis results.

        Args:
            analysis: Combined analysis result.
            current_price: Current market price.
            atr: Current ATR value.

        Returns:
            TradingSignal or None if no signal.
        """
        market_structure = analysis.market_structure
        order_flow = analysis.order_flow
        indicators = analysis.indicators

        if not market_structure or not indicators:
            return None

        signal_type = SignalType.NO_SIGNAL
        direction = PositionSide.FLAT
        confidence = 0.0
        rationale = []

        # Check for breakout signals
        if self.strategy_config.enable_breakout_signals and market_structure.is_breakout:
            signal_type, direction, conf, reasons = self._check_breakout_signal(
                market_structure, order_flow, indicators
            )
            confidence += conf
            rationale.extend(reasons)

        # Check for rejection signals
        if signal_type == SignalType.NO_SIGNAL and self.strategy_config.enable_rejection_signals:
            if market_structure.is_rejection:
                signal_type, direction, conf, reasons = self._check_rejection_signal(
                    market_structure, order_flow, indicators, current_price
                )
                confidence += conf
                rationale.extend(reasons)

        # Check for divergence signals
        if signal_type == SignalType.NO_SIGNAL and self.strategy_config.enable_divergence_signals:
            signal_type, direction, conf, reasons = self._check_divergence_signal(
                order_flow, indicators
            )
            confidence += conf
            rationale.extend(reasons)

        # No signal found
        if signal_type == SignalType.NO_SIGNAL:
            return TradingSignal(
                timestamp=datetime.now(),
                symbol=self.config.symbol,
                signal_type=SignalType.NO_SIGNAL,
                direction=PositionSide.FLAT,
                entry_price=current_price,
                stop_loss=current_price,
                take_profit=current_price,
                confidence=0.0,
                rationale="No signal criteria met",
            )

        # Calculate stop loss and take profit
        stop_loss, take_profit = self._calculate_sl_tp(
            direction, current_price, atr, market_structure
        )

        # Count aligned indicators
        direction_str = 'bullish' if direction == PositionSide.LONG else 'bearish'
        aligned, total, aligned_names = self.indicators.get_signal_alignment(direction_str)

        # Adjust confidence based on alignment
        alignment_bonus = (aligned / total) * 30 if total > 0 else 0
        confidence = min(100, confidence + alignment_bonus)

        # Check minimum confidence
        if confidence < self.strategy_config.min_confidence:
            return TradingSignal(
                timestamp=datetime.now(),
                symbol=self.config.symbol,
                signal_type=SignalType.NO_SIGNAL,
                direction=PositionSide.FLAT,
                entry_price=current_price,
                stop_loss=current_price,
                take_profit=current_price,
                confidence=confidence,
                rationale=f"Confidence {confidence:.1f}% below minimum {self.strategy_config.min_confidence}%",
            )

        return TradingSignal(
            timestamp=datetime.now(),
            symbol=self.config.symbol,
            signal_type=signal_type,
            direction=direction,
            entry_price=current_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            confidence=confidence,
            rationale="; ".join(rationale),
            indicators_aligned=aligned,
            total_indicators=total,
        )

    def _check_breakout_signal(
        self,
        market_structure,
        order_flow,
        indicators
    ) -> Tuple[SignalType, PositionSide, float, List[str]]:
        """
        Check for breakout signal conditions.

        Returns:
            Tuple of (signal_type, direction, confidence, reasons).
        """
        confidence = 40.0  # Base confidence for breakout
        reasons = ["Breakout from value area detected"]

        if market_structure.breakout_direction == TrendDirection.BULLISH:
            signal_type = SignalType.BREAKOUT_LONG
            direction = PositionSide.LONG

            # Volume confirmation
            if self.strategy_config.require_volume_confirmation:
                if order_flow and order_flow.breakout_quality > 60:
                    confidence += 15
                    reasons.append(f"Volume confirmed (quality: {order_flow.breakout_quality:.1f})")
                else:
                    confidence -= 10
                    reasons.append("Volume confirmation weak")

            # Delta confirmation
            if order_flow and order_flow.delta.delta > 0:
                confidence += 10
                reasons.append("Positive delta")

            # Trend alignment
            if self.strategy_config.require_trend_alignment:
                if market_structure.trend == TrendDirection.BULLISH:
                    confidence += 10
                    reasons.append("Aligned with trend")

        else:  # Bearish breakout
            signal_type = SignalType.BREAKOUT_SHORT
            direction = PositionSide.SHORT

            if self.strategy_config.require_volume_confirmation:
                if order_flow and order_flow.breakout_quality > 60:
                    confidence += 15
                    reasons.append(f"Volume confirmed (quality: {order_flow.breakout_quality:.1f})")
                else:
                    confidence -= 10

            if order_flow and order_flow.delta.delta < 0:
                confidence += 10
                reasons.append("Negative delta")

            if self.strategy_config.require_trend_alignment:
                if market_structure.trend == TrendDirection.BEARISH:
                    confidence += 10
                    reasons.append("Aligned with trend")

        return signal_type, direction, confidence, reasons

    def _check_rejection_signal(
        self,
        market_structure,
        order_flow,
        indicators,
        current_price: float
    ) -> Tuple[SignalType, PositionSide, float, List[str]]:
        """
        Check for rejection signal conditions.

        Returns:
            Tuple of (signal_type, direction, confidence, reasons).
        """
        confidence = 35.0  # Base confidence for rejection
        reasons = [f"Rejection at {market_structure.rejection_level:.2f}"]

        fva = market_structure.fva
        rejection_level = market_structure.rejection_level

        # Determine direction based on rejection level
        if rejection_level and rejection_level >= fva.vah:
            # Rejection at resistance - short signal
            signal_type = SignalType.REJECTION_SHORT
            direction = PositionSide.SHORT
            reasons.append("Rejection at VAH (resistance)")

            if indicators.rsi.is_overbought:
                confidence += 15
                reasons.append("RSI overbought")

            if order_flow and order_flow.aggressive_selling:
                confidence += 10
                reasons.append("Aggressive selling detected")

        elif rejection_level and rejection_level <= fva.val:
            # Rejection at support - long signal
            signal_type = SignalType.REJECTION_LONG
            direction = PositionSide.LONG
            reasons.append("Rejection at VAL (support)")

            if indicators.rsi.is_oversold:
                confidence += 15
                reasons.append("RSI oversold")

            if order_flow and order_flow.aggressive_buying:
                confidence += 10
                reasons.append("Aggressive buying detected")

        else:
            # Rejection at POC - use trend for direction
            if market_structure.trend == TrendDirection.BULLISH:
                signal_type = SignalType.REJECTION_LONG
                direction = PositionSide.LONG
            else:
                signal_type = SignalType.REJECTION_SHORT
                direction = PositionSide.SHORT
            reasons.append("Rejection at POC")

        # Absorption bonus
        if order_flow and order_flow.absorption_detected:
            confidence += 10
            reasons.append("Volume absorption detected")

        return signal_type, direction, confidence, reasons

    def _check_divergence_signal(
        self,
        order_flow,
        indicators
    ) -> Tuple[SignalType, PositionSide, float, List[str]]:
        """
        Check for divergence signal conditions.

        Returns:
            Tuple of (signal_type, direction, confidence, reasons).
        """
        confidence = 0.0
        reasons = []
        signal_type = SignalType.NO_SIGNAL
        direction = PositionSide.FLAT

        divergences_found = 0

        # Check RSI divergence
        if indicators.rsi.divergence:
            divergences_found += 1
            if indicators.rsi.divergence == 'bullish':
                signal_type = SignalType.DIVERGENCE_LONG
                direction = PositionSide.LONG
                confidence += 25
                reasons.append("RSI bullish divergence")
            else:
                signal_type = SignalType.DIVERGENCE_SHORT
                direction = PositionSide.SHORT
                confidence += 25
                reasons.append("RSI bearish divergence")

        # Check MACD divergence (implied from crossover in opposite direction)
        if indicators.macd.crossover:
            if indicators.macd.crossover == 'bullish' and direction != PositionSide.SHORT:
                if signal_type == SignalType.NO_SIGNAL:
                    signal_type = SignalType.DIVERGENCE_LONG
                    direction = PositionSide.LONG
                confidence += 15
                reasons.append("MACD bullish crossover")
            elif indicators.macd.crossover == 'bearish' and direction != PositionSide.LONG:
                if signal_type == SignalType.NO_SIGNAL:
                    signal_type = SignalType.DIVERGENCE_SHORT
                    direction = PositionSide.SHORT
                confidence += 15
                reasons.append("MACD bearish crossover")

        # Check order flow divergence
        if order_flow and order_flow.divergence_detected:
            divergences_found += 1
            if order_flow.divergence_type == 'bullish':
                if signal_type == SignalType.NO_SIGNAL:
                    signal_type = SignalType.DIVERGENCE_LONG
                    direction = PositionSide.LONG
                if direction == PositionSide.LONG:
                    confidence += 20
                    reasons.append("Order flow bullish divergence")
            elif order_flow.divergence_type == 'bearish':
                if signal_type == SignalType.NO_SIGNAL:
                    signal_type = SignalType.DIVERGENCE_SHORT
                    direction = PositionSide.SHORT
                if direction == PositionSide.SHORT:
                    confidence += 20
                    reasons.append("Order flow bearish divergence")

        # Multiple divergence bonus
        if divergences_found >= 2:
            confidence += 15
            reasons.append("Multiple divergences confirmed")

        return signal_type, direction, confidence, reasons

    def _calculate_sl_tp(
        self,
        direction: PositionSide,
        current_price: float,
        atr: float,
        market_structure
    ) -> Tuple[float, float]:
        """
        Calculate stop loss and take profit levels.

        Args:
            direction: Trade direction.
            current_price: Current price.
            atr: Current ATR.
            market_structure: Market structure analysis.

        Returns:
            Tuple of (stop_loss, take_profit).
        """
        # Default ATR-based stops
        stop_distance = atr * 2
        target_distance = atr * 4  # 2:1 R:R minimum

        fva = market_structure.fva if market_structure else None

        if direction == PositionSide.LONG:
            # Stop below recent swing low or VAL
            stop_loss = current_price - stop_distance
            if fva and fva.val < current_price:
                stop_loss = min(stop_loss, fva.val - atr * 0.5)

            # Target at resistance or ATR-based
            take_profit = current_price + target_distance
            if fva and fva.vah > current_price:
                take_profit = max(take_profit, fva.vah + atr * 0.5)

            # Check support levels for tighter stop
            if market_structure and market_structure.support_levels:
                nearest_support = max(
                    [s for s in market_structure.support_levels if s < current_price],
                    default=None
                )
                if nearest_support:
                    stop_loss = max(stop_loss, nearest_support - atr * 0.25)

        else:  # SHORT
            stop_loss = current_price + stop_distance
            if fva and fva.vah > current_price:
                stop_loss = max(stop_loss, fva.vah + atr * 0.5)

            take_profit = current_price - target_distance
            if fva and fva.val < current_price:
                take_profit = min(take_profit, fva.val - atr * 0.5)

            if market_structure and market_structure.resistance_levels:
                nearest_resistance = min(
                    [r for r in market_structure.resistance_levels if r > current_price],
                    default=None
                )
                if nearest_resistance:
                    stop_loss = min(stop_loss, nearest_resistance + atr * 0.25)

        return round(stop_loss, 2), round(take_profit, 2)

    def _calculate_confluence(self, analysis: AnalysisResult) -> float:
        """
        Calculate overall confluence score.

        Args:
            analysis: Combined analysis result.

        Returns:
            Confluence score (0-100).
        """
        score = 0.0
        factors = 0

        # Market structure contribution
        if analysis.market_structure:
            ms = analysis.market_structure
            factors += 1
            if ms.is_breakout or ms.is_rejection:
                score += 25
            if ms.trend != TrendDirection.NEUTRAL:
                score += 10

        # Order flow contribution
        if analysis.order_flow:
            of = analysis.order_flow
            factors += 1
            score += of.breakout_quality * 0.2
            if of.divergence_detected:
                score += 15

        # Correlation contribution
        if analysis.correlation:
            corr = analysis.correlation
            factors += 1
            score += corr.market_health_score * 0.2

        # Indicator contribution
        if analysis.indicators:
            ind = analysis.indicators
            factors += 1
            score += ind.trend_strength * 0.2

        # Normalize
        if factors > 0:
            score = score / factors * (factors / 4)

        return min(100, score)

    def _classify_signal_strength(
        self,
        confluence_score: float
    ) -> SignalStrength:
        """
        Classify signal strength based on confluence.

        Args:
            confluence_score: Overall confluence score.

        Returns:
            SignalStrength classification.
        """
        if confluence_score >= 80:
            return SignalStrength.VERY_STRONG
        elif confluence_score >= 60:
            return SignalStrength.STRONG
        elif confluence_score >= 40:
            return SignalStrength.MODERATE
        else:
            return SignalStrength.WEAK

    def process_signal(
        self,
        signal: TradingSignal
    ) -> Optional[Tuple[bool, str]]:
        """
        Process a signal through risk management.

        Args:
            signal: Trading signal to process.

        Returns:
            Tuple of (can_trade, reason) or None if no signal.
        """
        if signal.signal_type == SignalType.NO_SIGNAL:
            return None

        # Calculate position size
        position_size = self.risk_manager.calculate_position_size(
            signal,
            signal.entry_price,
            self.indicators.calculate_atr()
        )

        # Validate trade
        validation = self.risk_manager.validate_trade(signal, position_size)

        if validation.is_valid:
            signal.position_size = position_size
            return True, f"Trade validated. Size: {position_size.shares} shares"
        else:
            reasons = "; ".join(validation.reasons)
            return False, f"Trade rejected: {reasons}"

    def get_market_summary(self) -> Dict:
        """
        Get a summary of current market conditions.

        Returns:
            Dictionary with market summary.
        """
        summary = {
            'timestamp': datetime.now().isoformat(),
            'symbol': self.config.symbol,
            'analysis_available': False,
        }

        if self._candle_history:
            summary['analysis_available'] = True
            summary['current_price'] = self._candle_history[-1].close

            # Market structure
            if self.market_analyzer.fva_history:
                fva = self.market_analyzer.fva_history[-1]
                summary['fair_value_area'] = {
                    'vah': fva.vah,
                    'val': fva.val,
                    'poc': fva.poc,
                }

            # Order flow
            if self.order_flow.delta_history:
                delta = self.order_flow.delta_history[-1]
                summary['order_flow'] = {
                    'delta': delta.delta,
                    'cumulative_delta': delta.cumulative_delta,
                }

            # Last signal
            if self._last_signal:
                summary['last_signal'] = {
                    'type': self._last_signal.signal_type.name,
                    'direction': self._last_signal.direction.name,
                    'confidence': self._last_signal.confidence,
                }

        return summary

    def reset(self):
        """Reset all analyzers and state."""
        self.market_analyzer.reset()
        self.order_flow.reset()
        self.correlation.reset()
        self.indicators.reset()
        self._last_signal = None
        self._signal_history.clear()
        self._candle_history.clear()


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    'StrategyEngine',
    'SignalStrength',
    'AnalysisResult',
]
