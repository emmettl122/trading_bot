"""
Risk Management Module.

This module provides comprehensive risk management including:
- Position sizing calculations
- Trade validation
- Money management rules
- Exposure tracking
- Slippage estimation
- Risk metrics calculation

Author: AMT Trading Bot
Version: 1.0.0
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple
import statistics

from config import (
    PositionSize,
    TradeValidation,
    RiskMetrics,
    TradingSignal,
    Trade,
    Position,
    AccountInfo,
    RiskConfig,
    PositionSide,
    RiskLevel,
    get_default_config,
)


class RiskManager:
    """
    Manages all risk-related calculations and validations.

    This class ensures that trades comply with risk parameters and
    provides position sizing based on account size and risk tolerance.

    Attributes:
        config: Risk management configuration.
        account: Current account information.
        daily_pnl: Today's profit/loss.
    """

    def __init__(
        self,
        config: Optional[RiskConfig] = None,
        initial_capital: float = 100000.0
    ):
        """
        Initialize the Risk Manager.

        Args:
            config: Optional risk configuration. Uses defaults if not provided.
            initial_capital: Starting account balance.
        """
        self.config = config or get_default_config().risk
        self.initial_capital = initial_capital
        self.current_balance = initial_capital
        self.equity = initial_capital
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.positions: Dict[str, Position] = {}
        self.trade_history: List[Trade] = []
        self._last_reset_date: date = date.today()
        self._peak_equity = initial_capital
        self._drawdown_history: List[float] = []

    def calculate_position_size(
        self,
        signal: TradingSignal,
        current_price: float,
        atr: Optional[float] = None
    ) -> PositionSize:
        """
        Calculate the appropriate position size for a trade.

        Uses risk-based position sizing to ensure each trade risks
        only a specified percentage of the account.

        Args:
            signal: Trading signal with entry, stop, and target.
            current_price: Current market price.
            atr: Optional ATR for volatility-based sizing.

        Returns:
            PositionSize with calculated values.
        """
        # Calculate risk per share
        if signal.direction == PositionSide.LONG:
            risk_per_share = abs(signal.entry_price - signal.stop_loss)
        else:
            risk_per_share = abs(signal.stop_loss - signal.entry_price)

        if risk_per_share == 0:
            risk_per_share = current_price * 0.02  # Default 2% stop

        # Calculate maximum risk amount
        max_risk_amount = self.equity * (self.config.max_single_trade_risk_percent / 100)

        # Calculate position size based on risk
        shares_by_risk = int(max_risk_amount / risk_per_share)

        # Calculate maximum position size by account percentage
        max_position_value = self.equity * (self.config.max_position_size_percent / 100)
        shares_by_position = int(max_position_value / current_price)

        # Use the smaller of the two
        shares = min(shares_by_risk, shares_by_position)

        # Ensure minimum of 1 share
        shares = max(1, shares)

        # Calculate dollar amount and actual risk
        dollar_amount = shares * current_price
        risk_amount = shares * risk_per_share
        percent_of_account = (dollar_amount / self.equity) * 100

        # Estimate margin required (simplified)
        margin_required = dollar_amount * 0.5 if signal.direction == PositionSide.SHORT else dollar_amount

        return PositionSize(
            shares=shares,
            dollar_amount=dollar_amount,
            risk_amount=risk_amount,
            percent_of_account=percent_of_account,
            margin_required=margin_required,
        )

    def validate_trade(
        self,
        signal: TradingSignal,
        position_size: PositionSize
    ) -> TradeValidation:
        """
        Validate a trade against risk management rules.

        Checks various risk parameters to determine if the trade
        should be allowed.

        Args:
            signal: Trading signal to validate.
            position_size: Calculated position size.

        Returns:
            TradeValidation with validation result and reasons.
        """
        is_valid = True
        reasons = []
        warnings = []
        risk_score = 0.0

        # Check daily loss limit
        if self._check_daily_loss_limit():
            is_valid = False
            reasons.append("Daily loss limit reached")
            risk_score += 30

        # Check risk-reward ratio
        if signal.risk_reward_ratio < self.config.min_risk_reward_ratio:
            is_valid = False
            reasons.append(f"R:R ratio {signal.risk_reward_ratio:.2f} below minimum {self.config.min_risk_reward_ratio}")
            risk_score += 20

        # Check position size limits
        if position_size.percent_of_account > self.config.max_position_size_percent:
            is_valid = False
            reasons.append(f"Position size {position_size.percent_of_account:.1f}% exceeds limit")
            risk_score += 15

        # Check total exposure
        current_exposure = self._calculate_total_exposure()
        new_exposure = current_exposure + position_size.dollar_amount
        max_exposure = self.equity * (self.config.max_total_exposure_percent / 100)

        if new_exposure > max_exposure:
            is_valid = False
            reasons.append("Would exceed maximum total exposure")
            risk_score += 25

        # Check maximum open positions
        if len(self.positions) >= self.config.max_open_positions:
            is_valid = False
            reasons.append(f"Maximum {self.config.max_open_positions} positions already open")
            risk_score += 10

        # Check correlated positions
        correlated_count = self._count_correlated_positions(signal.symbol)
        if correlated_count >= self.config.max_correlated_positions:
            warnings.append(f"Already have {correlated_count} correlated positions")
            risk_score += 10

        # Check signal confidence
        if signal.confidence < 50:
            warnings.append(f"Low signal confidence: {signal.confidence:.1f}%")
            risk_score += 10

        # Check available margin
        if position_size.margin_required > self.equity:
            is_valid = False
            reasons.append("Insufficient margin available")
            risk_score += 30

        # Normalize risk score
        risk_score = min(100, risk_score)

        return TradeValidation(
            is_valid=is_valid,
            reasons=reasons,
            risk_score=risk_score,
            warnings=warnings,
        )

    def _check_daily_loss_limit(self) -> bool:
        """
        Check if daily loss limit has been reached.

        Returns:
            True if limit is reached.
        """
        self._reset_daily_if_needed()
        max_daily_loss = self.equity * (self.config.max_daily_loss_percent / 100)
        return self.daily_pnl <= -max_daily_loss

    def _reset_daily_if_needed(self):
        """Reset daily counters if it's a new day."""
        today = date.today()
        if today != self._last_reset_date:
            self.daily_pnl = 0.0
            self.daily_trades = 0
            self._last_reset_date = today

    def _calculate_total_exposure(self) -> float:
        """
        Calculate total current exposure.

        Returns:
            Total dollar exposure across all positions.
        """
        total = 0.0
        for position in self.positions.values():
            total += abs(position.quantity * position.current_price)
        return total

    def _count_correlated_positions(self, symbol: str) -> int:
        """
        Count positions in correlated assets.

        Args:
            symbol: Symbol to check correlations for.

        Returns:
            Number of correlated positions.
        """
        # Simplified correlation check
        # In production, would use actual correlation data
        sector_map = {
            'SPY': 'index', 'QQQ': 'index', 'IWM': 'index',
            'AAPL': 'tech', 'MSFT': 'tech', 'GOOGL': 'tech', 'AMZN': 'tech',
            'META': 'tech', 'NVDA': 'tech', 'TSLA': 'tech',
        }

        symbol_sector = sector_map.get(symbol, 'other')
        count = 0

        for pos_symbol in self.positions.keys():
            if sector_map.get(pos_symbol, 'other') == symbol_sector:
                count += 1

        return count

    def update_position(
        self,
        symbol: str,
        current_price: float
    ):
        """
        Update position P&L with current price.

        Args:
            symbol: Position symbol.
            current_price: Current market price.
        """
        if symbol in self.positions:
            position = self.positions[symbol]
            position.update_pnl(current_price)

            # Update equity
            self._update_equity()

    def _update_equity(self):
        """Update account equity based on position values."""
        unrealized_pnl = sum(
            pos.unrealized_pnl for pos in self.positions.values()
        )
        self.equity = self.current_balance + unrealized_pnl

        # Update peak equity and drawdown
        if self.equity > self._peak_equity:
            self._peak_equity = self.equity

        drawdown = (self._peak_equity - self.equity) / self._peak_equity * 100
        self._drawdown_history.append(drawdown)

    def open_position(
        self,
        signal: TradingSignal,
        position_size: PositionSize,
        fill_price: float
    ) -> Position:
        """
        Open a new position.

        Args:
            signal: Trading signal that generated the trade.
            position_size: Calculated position size.
            fill_price: Actual fill price (may differ from signal entry).

        Returns:
            New Position object.
        """
        # Apply slippage estimation
        slippage = fill_price * (self.config.slippage_percent / 100)
        if signal.direction == PositionSide.LONG:
            adjusted_price = fill_price + slippage
        else:
            adjusted_price = fill_price - slippage

        position = Position(
            symbol=signal.symbol,
            side=signal.direction,
            quantity=position_size.shares,
            entry_price=adjusted_price,
            current_price=fill_price,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
        )

        self.positions[signal.symbol] = position
        self.daily_trades += 1

        # Deduct commission
        self.current_balance -= self.config.commission_per_trade

        return position

    def close_position(
        self,
        symbol: str,
        fill_price: float,
        reason: str = "manual"
    ) -> Optional[Trade]:
        """
        Close an existing position.

        Args:
            symbol: Position symbol.
            fill_price: Exit fill price.
            reason: Reason for closing.

        Returns:
            Trade record or None if position doesn't exist.
        """
        if symbol not in self.positions:
            return None

        position = self.positions[symbol]

        # Apply slippage
        slippage = fill_price * (self.config.slippage_percent / 100)
        if position.side == PositionSide.LONG:
            adjusted_price = fill_price - slippage
        else:
            adjusted_price = fill_price + slippage

        # Calculate P&L
        if position.side == PositionSide.LONG:
            pnl = (adjusted_price - position.entry_price) * position.quantity
        else:
            pnl = (position.entry_price - adjusted_price) * position.quantity

        # Deduct commission
        pnl -= self.config.commission_per_trade

        pnl_percent = (pnl / (position.entry_price * position.quantity)) * 100

        # Create trade record
        trade = Trade(
            id=f"{symbol}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            timestamp=datetime.now(),
            symbol=symbol,
            side=position.side,
            entry_price=position.entry_price,
            exit_price=adjusted_price,
            stop_loss=position.stop_loss,
            take_profit=position.take_profit,
            quantity=position.quantity,
            status="closed",
            pnl=pnl,
            pnl_percent=pnl_percent,
            exit_reason=reason,
        )

        # Update balances
        self.current_balance += pnl
        self.daily_pnl += pnl

        # Remove position
        del self.positions[symbol]

        # Store trade
        self.trade_history.append(trade)

        # Update equity
        self._update_equity()

        return trade

    def check_stop_loss(
        self,
        symbol: str,
        current_price: float
    ) -> bool:
        """
        Check if stop loss has been hit.

        Args:
            symbol: Position symbol.
            current_price: Current market price.

        Returns:
            True if stop loss triggered.
        """
        if symbol not in self.positions:
            return False

        position = self.positions[symbol]

        if position.side == PositionSide.LONG:
            return current_price <= position.stop_loss
        else:
            return current_price >= position.stop_loss

    def check_take_profit(
        self,
        symbol: str,
        current_price: float
    ) -> bool:
        """
        Check if take profit has been hit.

        Args:
            symbol: Position symbol.
            current_price: Current market price.

        Returns:
            True if take profit triggered.
        """
        if symbol not in self.positions:
            return False

        position = self.positions[symbol]

        if position.side == PositionSide.LONG:
            return current_price >= position.take_profit
        else:
            return current_price <= position.take_profit

    def update_trailing_stop(
        self,
        symbol: str,
        current_price: float,
        atr: float
    ):
        """
        Update trailing stop for a position.

        Args:
            symbol: Position symbol.
            current_price: Current market price.
            atr: Current ATR for stop distance.
        """
        if not self.config.use_trailing_stop:
            return

        if symbol not in self.positions:
            return

        position = self.positions[symbol]
        trail_distance = atr * self.config.trailing_stop_atr_multiple

        if position.side == PositionSide.LONG:
            new_stop = current_price - trail_distance
            if new_stop > position.stop_loss:
                position.stop_loss = new_stop
        else:
            new_stop = current_price + trail_distance
            if new_stop < position.stop_loss:
                position.stop_loss = new_stop

    def calculate_risk_metrics(self) -> RiskMetrics:
        """
        Calculate current risk metrics for the portfolio.

        Returns:
            RiskMetrics with current portfolio risk data.
        """
        # Calculate exposure
        long_exposure = sum(
            pos.quantity * pos.current_price
            for pos in self.positions.values()
            if pos.side == PositionSide.LONG
        )
        short_exposure = sum(
            pos.quantity * pos.current_price
            for pos in self.positions.values()
            if pos.side == PositionSide.SHORT
        )

        total_exposure = long_exposure + short_exposure
        net_exposure = long_exposure - short_exposure
        gross_exposure = long_exposure + short_exposure

        # Calculate drawdown
        current_drawdown = (self._peak_equity - self.equity) / self._peak_equity * 100
        max_drawdown = max(self._drawdown_history) if self._drawdown_history else 0.0

        # Calculate trading statistics
        if self.trade_history:
            winners = [t for t in self.trade_history if t.pnl > 0]
            losers = [t for t in self.trade_history if t.pnl <= 0]

            win_rate = len(winners) / len(self.trade_history) * 100

            avg_win = statistics.mean([t.pnl for t in winners]) if winners else 0
            avg_loss = abs(statistics.mean([t.pnl for t in losers])) if losers else 1
            profit_factor = avg_win / avg_loss if avg_loss > 0 else 0

            # Calculate returns for Sharpe/Sortino
            returns = [t.pnl_percent for t in self.trade_history]
            if len(returns) >= 2:
                avg_return = statistics.mean(returns)
                std_return = statistics.stdev(returns)
                downside_returns = [r for r in returns if r < 0]
                downside_std = statistics.stdev(downside_returns) if len(downside_returns) >= 2 else 1

                sharpe = (avg_return / std_return) if std_return > 0 else 0
                sortino = (avg_return / downside_std) if downside_std > 0 else 0
            else:
                sharpe = 0.0
                sortino = 0.0
        else:
            win_rate = 0.0
            profit_factor = 0.0
            sharpe = 0.0
            sortino = 0.0

        # Simplified VaR calculation
        var_95 = self.equity * 0.02  # 2% VaR
        var_99 = self.equity * 0.035  # 3.5% VaR

        return RiskMetrics(
            timestamp=datetime.now(),
            total_exposure=total_exposure,
            long_exposure=long_exposure,
            short_exposure=short_exposure,
            net_exposure=net_exposure,
            gross_exposure=gross_exposure,
            var_95=var_95,
            var_99=var_99,
            max_drawdown=max_drawdown,
            current_drawdown=current_drawdown,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            win_rate=win_rate,
            profit_factor=profit_factor,
        )

    def get_risk_level(self) -> RiskLevel:
        """
        Determine current risk level.

        Returns:
            RiskLevel classification.
        """
        metrics = self.calculate_risk_metrics()

        if metrics.current_drawdown > 10 or len(self.positions) >= self.config.max_open_positions:
            return RiskLevel.EXTREME
        elif metrics.current_drawdown > 5 or metrics.gross_exposure > self.equity * 0.8:
            return RiskLevel.HIGH
        elif metrics.current_drawdown > 2 or metrics.gross_exposure > self.equity * 0.5:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW

    def get_account_info(self) -> AccountInfo:
        """
        Get current account information.

        Returns:
            AccountInfo with current account state.
        """
        unrealized_pnl = sum(pos.unrealized_pnl for pos in self.positions.values())
        realized_pnl = self.current_balance - self.initial_capital

        margin_used = sum(
            pos.quantity * pos.entry_price * 0.5  # Simplified margin
            for pos in self.positions.values()
        )

        return AccountInfo(
            account_id="paper_trading",
            balance=self.current_balance,
            equity=self.equity,
            margin_used=margin_used,
            margin_available=self.equity - margin_used,
            unrealized_pnl=unrealized_pnl,
            realized_pnl=realized_pnl,
            positions=list(self.positions.values()),
        )

    def estimate_slippage(
        self,
        price: float,
        volume: float,
        avg_volume: float,
        order_size: int
    ) -> float:
        """
        Estimate slippage for an order.

        Args:
            price: Current price.
            volume: Current volume.
            avg_volume: Average volume.
            order_size: Order size in shares.

        Returns:
            Estimated slippage in price units.
        """
        base_slippage = price * (self.config.slippage_percent / 100)

        # Adjust for volume
        if avg_volume > 0:
            volume_ratio = volume / avg_volume
            if volume_ratio < 0.5:
                # Low volume, higher slippage
                base_slippage *= 2
            elif volume_ratio > 2:
                # High volume, lower slippage
                base_slippage *= 0.5

        # Adjust for order size relative to volume
        if volume > 0:
            size_impact = order_size / volume
            if size_impact > 0.01:  # Order is >1% of volume
                base_slippage *= (1 + size_impact * 10)

        return base_slippage

    def reset(self):
        """Reset the risk manager to initial state."""
        self.current_balance = self.initial_capital
        self.equity = self.initial_capital
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.positions.clear()
        self.trade_history.clear()
        self._last_reset_date = date.today()
        self._peak_equity = self.initial_capital
        self._drawdown_history.clear()


# =============================================================================
# MONEY MANAGEMENT UTILITIES
# =============================================================================

def kelly_criterion(
    win_rate: float,
    avg_win: float,
    avg_loss: float
) -> float:
    """
    Calculate optimal position size using Kelly Criterion.

    Args:
        win_rate: Historical win rate (0-1).
        avg_win: Average winning trade amount.
        avg_loss: Average losing trade amount (positive number).

    Returns:
        Optimal fraction of capital to risk (0-1).
    """
    if avg_loss == 0:
        return 0.0

    b = avg_win / avg_loss  # Win/loss ratio
    p = win_rate
    q = 1 - win_rate

    kelly = (b * p - q) / b

    # Use fractional Kelly (half) to reduce variance
    return max(0, min(0.25, kelly * 0.5))


def calculate_optimal_f(
    trade_returns: List[float]
) -> float:
    """
    Calculate Optimal f for position sizing.

    Args:
        trade_returns: List of trade returns (as decimals).

    Returns:
        Optimal f value.
    """
    if not trade_returns or min(trade_returns) >= 0:
        return 0.0

    max_loss = abs(min(trade_returns))

    # Simple approximation of optimal f
    avg_return = statistics.mean(trade_returns)
    if avg_return <= 0:
        return 0.0

    optimal_f = avg_return / max_loss

    return max(0, min(0.25, optimal_f))


def calculate_risk_of_ruin(
    win_rate: float,
    risk_per_trade: float,
    bankroll_units: int = 100
) -> float:
    """
    Calculate risk of ruin probability.

    Args:
        win_rate: Historical win rate (0-1).
        risk_per_trade: Risk per trade as fraction of bankroll.
        bankroll_units: Number of risk units in bankroll.

    Returns:
        Probability of ruin (0-1).
    """
    if win_rate >= 1 or win_rate <= 0:
        return 0.0 if win_rate >= 0.5 else 1.0

    # Simplified risk of ruin formula
    q = 1 - win_rate
    p = win_rate

    if p == q:
        return 1 / bankroll_units

    a = q / p
    return (a ** bankroll_units) / (1 + a ** bankroll_units)


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    'RiskManager',
    'kelly_criterion',
    'calculate_optimal_f',
    'calculate_risk_of_ruin',
]
