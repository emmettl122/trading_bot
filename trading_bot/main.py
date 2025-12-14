"""
Main Bot Application Module.

This module provides the main trading bot application including:
- TradingBot class for orchestrating all components
- DataHandler for managing market data
- Session management
- Logging and monitoring
- Paper trading execution

Author: AMT Trading Bot
Version: 1.0.0
"""

import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from typing import Dict, List, Optional, Callable, Any
from enum import Enum
import random
import json

from config import (
    OHLCV,
    OrderBook,
    OrderBookLevel,
    TickData,
    TradingSignal,
    Trade,
    Position,
    AccountInfo,
    SessionStats,
    SessionType,
    SignalType,
    PositionSide,
    BotMode,
    BotConfig,
    get_default_config,
    validate_config,
)

from strategy import StrategyEngine, AnalysisResult
from risk_management import RiskManager
from signal import Signal
from webhook_dispatcher import WebhookDispatcher, DispatchResult


# =============================================================================
# LOGGING SETUP
# =============================================================================

def setup_logging(level: str = "INFO") -> logging.Logger:
    """
    Set up logging for the trading bot.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR).

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger("AMTBot")
    logger.setLevel(getattr(logging, level.upper()))

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)

    # Format
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)

    # Add handler if not already present
    if not logger.handlers:
        logger.addHandler(console_handler)

    return logger


# =============================================================================
# DATA HANDLER
# =============================================================================

class DataHandler:
    """
    Handles market data management and simulation.

    This class manages incoming market data, maintains history,
    and provides data access for analysis.

    Attributes:
        symbol: Trading symbol.
        candles: Historical candle data.
        ticks: Recent tick data.
        order_book: Current order book.
    """

    def __init__(self, symbol: str = "SPY"):
        """
        Initialize the Data Handler.

        Args:
            symbol: Trading symbol.
        """
        self.symbol = symbol
        self.candles: List[OHLCV] = []
        self.ticks: List[TickData] = []
        self.order_book: Optional[OrderBook] = None
        self._callbacks: List[Callable] = []
        self._max_candles = 500
        self._max_ticks = 10000

    def add_candle(self, candle: OHLCV):
        """
        Add a new candle to history.

        Args:
            candle: OHLCV candle to add.
        """
        self.candles.append(candle)

        # Trim history if needed
        if len(self.candles) > self._max_candles:
            self.candles = self.candles[-self._max_candles:]

        # Notify callbacks
        for callback in self._callbacks:
            callback('candle', candle)

    def add_tick(self, tick: TickData):
        """
        Add a new tick to history.

        Args:
            tick: Tick data to add.
        """
        self.ticks.append(tick)

        if len(self.ticks) > self._max_ticks:
            self.ticks = self.ticks[-self._max_ticks:]

        for callback in self._callbacks:
            callback('tick', tick)

    def update_order_book(self, order_book: OrderBook):
        """
        Update the current order book.

        Args:
            order_book: New order book snapshot.
        """
        self.order_book = order_book

        for callback in self._callbacks:
            callback('order_book', order_book)

    def get_recent_candles(self, count: int = 100) -> List[OHLCV]:
        """
        Get recent candles.

        Args:
            count: Number of candles to return.

        Returns:
            List of recent OHLCV candles.
        """
        return self.candles[-count:] if self.candles else []

    def get_current_price(self) -> Optional[float]:
        """
        Get the current market price.

        Returns:
            Current price or None if no data.
        """
        if self.candles:
            return self.candles[-1].close
        return None

    def get_average_volume(self, periods: int = 20) -> float:
        """
        Calculate average volume over recent periods.

        Args:
            periods: Number of periods to average.

        Returns:
            Average volume.
        """
        if not self.candles:
            return 0.0

        recent = self.candles[-periods:]
        return sum(c.volume for c in recent) / len(recent)

    def register_callback(self, callback: Callable):
        """
        Register a callback for data updates.

        Args:
            callback: Function to call on data updates.
        """
        self._callbacks.append(callback)

    def clear(self):
        """Clear all data."""
        self.candles.clear()
        self.ticks.clear()
        self.order_book = None


# =============================================================================
# SESSION MANAGER
# =============================================================================

class SessionManager:
    """
    Manages trading sessions and time-based logic.

    Tracks session types, handles session transitions,
    and maintains session statistics.
    """

    def __init__(self, config: BotConfig):
        """
        Initialize the Session Manager.

        Args:
            config: Bot configuration with session times.
        """
        self.config = config
        self.current_session = SessionType.CLOSED
        self.session_stats = SessionStats(
            session_date=datetime.now(),
            session_type=SessionType.CLOSED,
        )
        self._session_start_time: Optional[datetime] = None

    def update_session(self, current_time: Optional[datetime] = None) -> SessionType:
        """
        Update and return the current session type.

        Args:
            current_time: Optional time to check. Uses now if not provided.

        Returns:
            Current SessionType.
        """
        if current_time is None:
            current_time = datetime.now()

        current_t = current_time.time()

        # Determine session
        if current_t < self.config.pre_market_start:
            new_session = SessionType.OVERNIGHT
        elif current_t < self.config.market_open:
            new_session = SessionType.PRE_MARKET
        elif current_t < self.config.market_close:
            new_session = SessionType.REGULAR
        elif current_t < self.config.post_market_end:
            new_session = SessionType.POST_MARKET
        else:
            new_session = SessionType.CLOSED

        # Handle session transition
        if new_session != self.current_session:
            self._on_session_change(self.current_session, new_session)
            self.current_session = new_session

        return self.current_session

    def _on_session_change(
        self,
        old_session: SessionType,
        new_session: SessionType
    ):
        """
        Handle session transition.

        Args:
            old_session: Previous session type.
            new_session: New session type.
        """
        # Reset stats for new regular session
        if new_session == SessionType.REGULAR and old_session != SessionType.REGULAR:
            self.session_stats = SessionStats(
                session_date=datetime.now(),
                session_type=SessionType.REGULAR,
            )
            self._session_start_time = datetime.now()

    def record_trade(self, trade: Trade):
        """
        Record a trade in session statistics.

        Args:
            trade: Completed trade to record.
        """
        self.session_stats.trades_taken += 1
        self.session_stats.gross_pnl += trade.pnl

        if trade.pnl > 0:
            self.session_stats.winners += 1
        else:
            self.session_stats.losers += 1

    def is_trading_allowed(self) -> bool:
        """
        Check if trading is allowed in current session.

        Returns:
            True if trading is allowed.
        """
        return self.current_session in [
            SessionType.REGULAR,
            SessionType.PRE_MARKET,
            SessionType.POST_MARKET,
        ]

    def get_session_summary(self) -> Dict:
        """
        Get summary of current session.

        Returns:
            Dictionary with session summary.
        """
        return {
            'session_type': self.current_session.name,
            'trades_taken': self.session_stats.trades_taken,
            'winners': self.session_stats.winners,
            'losers': self.session_stats.losers,
            'win_rate': self.session_stats.win_rate,
            'gross_pnl': self.session_stats.gross_pnl,
        }


# =============================================================================
# MAIN TRADING BOT
# =============================================================================

class TradingBot:
    """
    Main trading bot application.

    Orchestrates all components including data handling, strategy
    execution, risk management, and trade execution.

    Attributes:
        config: Bot configuration.
        strategy: Strategy engine.
        risk_manager: Risk management.
        data_handler: Market data handler.
        session_manager: Session management.
        logger: Logging instance.
    """

    def __init__(
        self,
        config: Optional[BotConfig] = None,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize the Trading Bot.

        Args:
            config: Optional bot configuration.
            logger: Optional logger instance.
        """
        self.config = config or get_default_config()

        # Validate configuration
        is_valid, errors = validate_config(self.config)
        if not is_valid:
            raise ValueError(f"Invalid configuration: {errors}")

        # Setup logging
        self.logger = logger or setup_logging(self.config.log_level)

        # Initialize components
        self.risk_manager = RiskManager(
            self.config.risk,
            self.config.initial_capital
        )
        self.strategy = StrategyEngine(self.config, self.risk_manager)
        self.data_handler = DataHandler(self.config.symbol)
        self.session_manager = SessionManager(self.config)

        # Webhook dispatcher (respects BotMode)
        self.webhook_dispatcher = WebhookDispatcher(
            config=self.config.webhook,
            mode=self.config.mode
        )

        # State
        self.is_running = False
        self._last_analysis: Optional[AnalysisResult] = None
        self._trade_callbacks: List[Callable] = []
        self._signal_callbacks: List[Callable[[Signal], None]] = []

        # Register data callback
        self.data_handler.register_callback(self._on_data_update)

        self.logger.info(f"Trading bot initialized for {self.config.symbol}")
        self.logger.info(f"Mode: {self.config.mode.value}")
        self.logger.info(f"Paper trading: {self.config.paper_trading}")
        self.logger.info(f"Initial capital: ${self.config.initial_capital:,.2f}")

    def _on_data_update(self, data_type: str, data: Any):
        """
        Callback for data updates.

        Args:
            data_type: Type of data ('candle', 'tick', 'order_book').
            data: The data object.
        """
        if data_type == 'candle':
            self._process_candle(data)

    def _process_candle(self, candle: OHLCV):
        """
        Process a new candle.

        Args:
            candle: New OHLCV candle.
        """
        # Update session
        self.session_manager.update_session(candle.timestamp)

        # Check if trading is allowed
        if not self.session_manager.is_trading_allowed():
            return

        # Run analysis
        analysis = self.analyze()

        # Process any signals
        if analysis and analysis.signal:
            self._process_signal(analysis.signal)

        # Check existing positions
        self._check_positions(candle.close)

    def analyze(
        self,
        mag7_prices: Optional[Dict[str, float]] = None,
        vix_level: Optional[float] = None,
        breadth_data: Optional[Dict] = None
    ) -> Optional[AnalysisResult]:
        """
        Run market analysis.

        Args:
            mag7_prices: Optional Mag7 stock prices.
            vix_level: Optional VIX level.
            breadth_data: Optional market breadth data.

        Returns:
            AnalysisResult or None if no data.
        """
        candles = self.data_handler.get_recent_candles(100)
        current_price = self.data_handler.get_current_price()

        if not candles or not current_price:
            return None

        analysis = self.strategy.analyze(
            candles=candles,
            current_price=current_price,
            order_book=self.data_handler.order_book,
            ticks=self.data_handler.ticks[-1000:] if self.data_handler.ticks else None,
            mag7_prices=mag7_prices,
            vix_level=vix_level,
            breadth_data=breadth_data,
        )

        self._last_analysis = analysis

        # Log analysis notes
        for note in analysis.notes:
            self.logger.debug(note)

        return analysis

    def _process_signal(self, signal: TradingSignal):
        """
        Process a trading signal through the complete execution pipeline.

        Pipeline stages:
        1. Signal received from strategy
        2. Risk validation
        3. Convert to TradingView payload (if validated)
        4. Dispatch to webhook (if mode == TRADINGVIEW_PAPER)
        5. Execute paper trade (if paper_trading enabled)

        Args:
            signal: Trading signal to process.
        """
        if signal.signal_type == SignalType.NO_SIGNAL:
            return

        # =====================================================================
        # STAGE 1: Signal Received
        # =====================================================================
        self.logger.info("=" * 50)
        self.logger.info("SIGNAL PIPELINE START")
        self.logger.info("=" * 50)
        self.logger.info(
            f"[STAGE 1] Signal Received: {signal.signal_type.name} | "
            f"Direction: {signal.direction.name} | "
            f"Entry: ${signal.entry_price:.2f} | "
            f"Confidence: {signal.confidence:.1f}%"
        )

        # =====================================================================
        # STAGE 2: Risk Validation
        # =====================================================================
        self.logger.info(f"[STAGE 2] Risk Validation...")

        try:
            result = self.strategy.process_signal(signal)

            if result is None:
                self.logger.warning("[STAGE 2] Risk validation returned None - skipping")
                return

            can_trade, reason = result
            self.logger.info(f"[STAGE 2] Validation Result: {reason}")

            if not can_trade:
                self.logger.info(f"[STAGE 2] Signal REJECTED by risk engine")
                self._notify_signal_callbacks(signal, validated=False)
                return

            self.logger.info(f"[STAGE 2] Signal APPROVED by risk engine")

        except Exception as e:
            self.logger.error(f"[STAGE 2] Risk validation error: {e}")
            return

        # =====================================================================
        # STAGE 3: Convert to TradingView Payload
        # =====================================================================
        self.logger.info(f"[STAGE 3] Converting to TradingView payload...")

        try:
            webhook_signal = signal.to_signal(
                self.config.strategy.primary_timeframe.value
            )

            if webhook_signal is None:
                self.logger.error("[STAGE 3] Failed to convert signal to webhook format")
                return

            self.logger.info(
                f"[STAGE 3] Payload created: {webhook_signal.side} {webhook_signal.symbol} "
                f"@ ${webhook_signal.entry_price:.2f}, "
                f"SL: ${webhook_signal.stop_loss:.2f}, "
                f"Targets: {[f'${t:.2f}' for t in webhook_signal.targets]}"
            )
            self.logger.debug(f"[STAGE 3] Full payload: {webhook_signal.to_json()}")

        except Exception as e:
            self.logger.error(f"[STAGE 3] Payload conversion error: {e}")
            return

        # =====================================================================
        # STAGE 4: TradingView Webhook Dispatch
        # =====================================================================
        self.logger.info(f"[STAGE 4] Webhook Dispatch (mode: {self.mode.value})...")

        try:
            dispatch_result = self.webhook_dispatcher.send_signal(webhook_signal)

            if dispatch_result.status.value == "mode_blocked":
                self.logger.info(
                    f"[STAGE 4] Dispatch SKIPPED - mode is {self.mode.value} "
                    f"(requires TRADINGVIEW_PAPER)"
                )
            elif dispatch_result.is_success():
                self.logger.info(
                    f"[STAGE 4] Dispatch SUCCESS - status: {dispatch_result.status.value}"
                )
                if dispatch_result.response_code:
                    self.logger.info(f"[STAGE 4] Response code: {dispatch_result.response_code}")
            else:
                self.logger.warning(
                    f"[STAGE 4] Dispatch FAILED - {dispatch_result.status.value}: "
                    f"{dispatch_result.error_message}"
                )

        except Exception as e:
            self.logger.error(f"[STAGE 4] Webhook dispatch error: {e}")
            # Continue to paper trading even if webhook fails

        # =====================================================================
        # STAGE 5: Paper Trade Execution
        # =====================================================================
        if self.config.paper_trading:
            self.logger.info(f"[STAGE 5] Paper Trade Execution...")
            try:
                self._execute_paper_trade(signal)
                self.logger.info(f"[STAGE 5] Paper trade executed")
            except Exception as e:
                self.logger.error(f"[STAGE 5] Paper trade error: {e}")
        else:
            self.logger.info(f"[STAGE 5] Paper trading disabled - skipping")

        # Notify callbacks
        self._notify_signal_callbacks(signal, validated=True, webhook_signal=webhook_signal)

        self.logger.info("=" * 50)
        self.logger.info("SIGNAL PIPELINE COMPLETE")
        self.logger.info("=" * 50)

    def _notify_signal_callbacks(
        self,
        signal: TradingSignal,
        validated: bool,
        webhook_signal: Optional[Signal] = None
    ):
        """
        Notify registered signal callbacks.

        Args:
            signal: The original TradingSignal.
            validated: Whether the signal passed risk validation.
            webhook_signal: The converted webhook Signal (if available).
        """
        if not webhook_signal and validated:
            # Convert if not already done
            try:
                webhook_signal = signal.to_signal(
                    self.config.strategy.primary_timeframe.value
                )
            except Exception:
                pass

        if webhook_signal:
            for callback in self._signal_callbacks:
                try:
                    callback(webhook_signal)
                except Exception as e:
                    self.logger.error(f"Signal callback error: {e}")

    def _execute_paper_trade(self, signal: TradingSignal):
        """
        Execute a paper trade.

        Args:
            signal: Trading signal with position size.
        """
        if not signal.position_size:
            self.logger.warning("No position size calculated")
            return

        # Simulate fill with slippage
        slippage = signal.entry_price * 0.001
        if signal.direction == PositionSide.LONG:
            fill_price = signal.entry_price + slippage
        else:
            fill_price = signal.entry_price - slippage

        # Open position
        position = self.risk_manager.open_position(
            signal, signal.position_size, fill_price
        )

        self.logger.info(
            f"PAPER TRADE: {signal.direction.name} {position.quantity} shares @ {fill_price:.2f}"
        )
        self.logger.info(
            f"  Stop: {signal.stop_loss:.2f} | Target: {signal.take_profit:.2f}"
        )

        # Notify callbacks
        for callback in self._trade_callbacks:
            callback('open', signal, position)

    def _check_positions(self, current_price: float):
        """
        Check and manage open positions.

        Args:
            current_price: Current market price.
        """
        positions_to_close = []

        for symbol, position in self.risk_manager.positions.items():
            # Update P&L
            self.risk_manager.update_position(symbol, current_price)

            # Check stop loss
            if self.risk_manager.check_stop_loss(symbol, current_price):
                positions_to_close.append((symbol, 'stop_loss'))
                continue

            # Check take profit
            if self.risk_manager.check_take_profit(symbol, current_price):
                positions_to_close.append((symbol, 'take_profit'))
                continue

            # Update trailing stop
            atr = self.strategy.indicators.calculate_atr()
            self.risk_manager.update_trailing_stop(symbol, current_price, atr)

        # Close positions
        for symbol, reason in positions_to_close:
            trade = self.risk_manager.close_position(symbol, current_price, reason)
            if trade:
                self.session_manager.record_trade(trade)
                self.logger.info(
                    f"CLOSED: {trade.symbol} | Reason: {reason} | "
                    f"P&L: ${trade.pnl:.2f} ({trade.pnl_percent:.2f}%)"
                )

                for callback in self._trade_callbacks:
                    callback('close', None, trade)

    def start(self):
        """Start the trading bot."""
        self.is_running = True
        self.logger.info("Trading bot started")
        self.logger.info(f"Session: {self.session_manager.current_session.name}")

    def stop(self):
        """Stop the trading bot."""
        self.is_running = False
        self.logger.info("Trading bot stopped")

        # Log final session stats
        summary = self.session_manager.get_session_summary()
        self.logger.info(f"Session summary: {json.dumps(summary, indent=2)}")

    def process_market_data(
        self,
        candles: Optional[List[OHLCV]] = None,
        ticks: Optional[List[TickData]] = None,
        order_book: Optional[OrderBook] = None
    ):
        """
        Process incoming market data.

        Args:
            candles: New candle data.
            ticks: New tick data.
            order_book: New order book.
        """
        if candles:
            for candle in candles:
                self.data_handler.add_candle(candle)

        if ticks:
            for tick in ticks:
                self.data_handler.add_tick(tick)

        if order_book:
            self.data_handler.update_order_book(order_book)

    def get_status(self) -> Dict:
        """
        Get current bot status.

        Returns:
            Dictionary with bot status.
        """
        account = self.risk_manager.get_account_info()
        metrics = self.risk_manager.calculate_risk_metrics()

        return {
            'is_running': self.is_running,
            'symbol': self.config.symbol,
            'paper_trading': self.config.paper_trading,
            'session': self.session_manager.current_session.name,
            'account': {
                'balance': account.balance,
                'equity': account.equity,
                'unrealized_pnl': account.unrealized_pnl,
                'realized_pnl': account.realized_pnl,
            },
            'positions': len(self.risk_manager.positions),
            'risk_metrics': {
                'current_drawdown': metrics.current_drawdown,
                'max_drawdown': metrics.max_drawdown,
                'win_rate': metrics.win_rate,
            },
            'session_stats': self.session_manager.get_session_summary(),
        }

    def get_positions(self) -> List[Position]:
        """
        Get current open positions.

        Returns:
            List of open positions.
        """
        return list(self.risk_manager.positions.values())

    def get_trade_history(self) -> List[Trade]:
        """
        Get trade history.

        Returns:
            List of completed trades.
        """
        return self.risk_manager.trade_history

    def close_position(
        self,
        symbol: str,
        reason: str = "manual"
    ) -> Optional[Trade]:
        """
        Manually close a position.

        Args:
            symbol: Position symbol to close.
            reason: Reason for closing.

        Returns:
            Trade record or None.
        """
        current_price = self.data_handler.get_current_price()
        if not current_price:
            self.logger.error("Cannot close position: no current price")
            return None

        trade = self.risk_manager.close_position(symbol, current_price, reason)
        if trade:
            self.session_manager.record_trade(trade)
            self.logger.info(f"Manually closed {symbol}: ${trade.pnl:.2f}")

        return trade

    def close_all_positions(self, reason: str = "manual") -> List[Trade]:
        """
        Close all open positions.

        Args:
            reason: Reason for closing.

        Returns:
            List of trade records.
        """
        trades = []
        symbols = list(self.risk_manager.positions.keys())

        for symbol in symbols:
            trade = self.close_position(symbol, reason)
            if trade:
                trades.append(trade)

        return trades

    def register_trade_callback(self, callback: Callable):
        """
        Register a callback for trade events.

        Args:
            callback: Function to call on trade events.
        """
        self._trade_callbacks.append(callback)

    def register_signal_callback(self, callback: Callable[[Signal], None]):
        """
        Register a callback for webhook signal events.

        The callback will be invoked with a standardized Signal object
        whenever a new trading signal is generated. This is useful for
        integrating with external systems like TradingView webhooks.

        Args:
            callback: Function to call with Signal when signals are emitted.

        Example:
            >>> def webhook_handler(signal: Signal):
            ...     print(signal.to_json())
            ...     # POST to TradingView webhook endpoint...
            >>> bot.register_signal_callback(webhook_handler)
        """
        self._signal_callbacks.append(callback)

    @property
    def mode(self) -> BotMode:
        """Get current bot execution mode."""
        return self.config.mode

    @mode.setter
    def mode(self, new_mode: BotMode):
        """
        Set bot execution mode with logging.

        Args:
            new_mode: The new BotMode to set.
        """
        old_mode = self.config.mode
        self.config.mode = new_mode
        self.webhook_dispatcher.mode = new_mode
        self.logger.info(f"Bot mode changed: {old_mode.value} -> {new_mode.value}")

    def set_mode(self, new_mode: BotMode):
        """
        Set the bot execution mode.

        This controls whether webhook dispatch is enabled:
        - ANALYSIS_ONLY: No webhook dispatch (safe for development)
        - TRADINGVIEW_PAPER: Webhook dispatch enabled

        Args:
            new_mode: The new BotMode to set.

        Example:
            >>> bot.set_mode(BotMode.TRADINGVIEW_PAPER)  # Enable webhooks
            >>> bot.set_mode(BotMode.ANALYSIS_ONLY)      # Disable webhooks
        """
        self.mode = new_mode

    def reset(self):
        """Reset the bot to initial state."""
        self.strategy.reset()
        self.risk_manager.reset()
        self.data_handler.clear()
        self._last_analysis = None
        self.logger.info("Trading bot reset to initial state")


# =============================================================================
# DATA SIMULATION (FOR TESTING)
# =============================================================================

def generate_sample_candle(
    base_price: float,
    timestamp: datetime,
    volatility: float = 0.01
) -> OHLCV:
    """
    Generate a sample candle for testing.

    Args:
        base_price: Base price for the candle.
        timestamp: Candle timestamp.
        volatility: Price volatility factor.

    Returns:
        Generated OHLCV candle.
    """
    change = random.gauss(0, volatility)
    open_price = base_price * (1 + random.gauss(0, volatility * 0.5))
    close_price = open_price * (1 + change)

    high = max(open_price, close_price) * (1 + abs(random.gauss(0, volatility * 0.5)))
    low = min(open_price, close_price) * (1 - abs(random.gauss(0, volatility * 0.5)))

    volume = random.randint(100000, 500000)

    return OHLCV(
        timestamp=timestamp,
        open=round(open_price, 2),
        high=round(high, 2),
        low=round(low, 2),
        close=round(close_price, 2),
        volume=volume,
    )


def generate_sample_data(
    symbol: str = "SPY",
    num_candles: int = 100,
    base_price: float = 450.0,
    interval_minutes: int = 15
) -> List[OHLCV]:
    """
    Generate sample candle data for testing.

    Args:
        symbol: Trading symbol.
        num_candles: Number of candles to generate.
        base_price: Starting price.
        interval_minutes: Minutes between candles.

    Returns:
        List of generated OHLCV candles.
    """
    candles = []
    current_price = base_price
    current_time = datetime.now() - timedelta(minutes=num_candles * interval_minutes)

    for i in range(num_candles):
        candle = generate_sample_candle(current_price, current_time)
        candles.append(candle)
        current_price = candle.close
        current_time += timedelta(minutes=interval_minutes)

    return candles


def generate_sample_order_book(
    mid_price: float,
    levels: int = 10,
    tick_size: float = 0.01
) -> OrderBook:
    """
    Generate a sample order book for testing.

    Args:
        mid_price: Middle price for the book.
        levels: Number of levels on each side.
        tick_size: Price increment between levels.

    Returns:
        Generated OrderBook.
    """
    bids = []
    asks = []

    for i in range(levels):
        bid_price = mid_price - (i + 1) * tick_size
        ask_price = mid_price + (i + 1) * tick_size

        bids.append(OrderBookLevel(
            price=round(bid_price, 2),
            size=random.randint(100, 1000),
            order_count=random.randint(1, 10),
        ))

        asks.append(OrderBookLevel(
            price=round(ask_price, 2),
            size=random.randint(100, 1000),
            order_count=random.randint(1, 10),
        ))

    return OrderBook(
        timestamp=datetime.now(),
        bids=bids,
        asks=asks,
    )


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    """Main entry point for the trading bot."""
    # Create configuration
    config = get_default_config()
    config.paper_trading = True
    config.log_level = "INFO"

    # Initialize bot
    bot = TradingBot(config)

    # Generate sample data
    candles = generate_sample_data(
        symbol=config.symbol,
        num_candles=100,
        base_price=450.0,
    )

    # Start bot
    bot.start()

    # Process sample data
    bot.process_market_data(candles=candles)

    # Run analysis
    analysis = bot.analyze()

    if analysis:
        print("\n" + "="*60)
        print("ANALYSIS RESULT")
        print("="*60)
        print(f"Confluence Score: {analysis.confluence_score:.1f}")
        print(f"Signal Strength: {analysis.signal_strength.name}")
        print("\nNotes:")
        for note in analysis.notes:
            print(f"  - {note}")

        if analysis.signal and analysis.signal.signal_type != SignalType.NO_SIGNAL:
            print(f"\nSignal: {analysis.signal.signal_type.name}")
            print(f"Direction: {analysis.signal.direction.name}")
            print(f"Entry: {analysis.signal.entry_price:.2f}")
            print(f"Stop: {analysis.signal.stop_loss:.2f}")
            print(f"Target: {analysis.signal.take_profit:.2f}")
            print(f"Confidence: {analysis.signal.confidence:.1f}%")

    # Print status
    status = bot.get_status()
    print("\n" + "="*60)
    print("BOT STATUS")
    print("="*60)
    print(json.dumps(status, indent=2))

    # Stop bot
    bot.stop()


if __name__ == "__main__":
    main()


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    'TradingBot',
    'DataHandler',
    'SessionManager',
    'Signal',
    'BotMode',
    'setup_logging',
    'generate_sample_candle',
    'generate_sample_data',
    'generate_sample_order_book',
    'main',
]
