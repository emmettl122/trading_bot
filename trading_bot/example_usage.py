#!/usr/bin/env python3
"""
Complete Working Example for the AMT Trading Bot.

This script demonstrates the full workflow of the trading bot including:
- Sample data generation
- Market structure analysis
- Order flow analysis
- Correlation analysis
- Technical indicators
- Signal generation
- Paper trading execution

Run this script to see the bot in action:
    python example_usage.py

Author: AMT Trading Bot
Version: 1.0.0
"""

import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json

# Import all bot components
from config import (
    OHLCV,
    OrderBook,
    OrderBookLevel,
    TickData,
    BotConfig,
    RiskConfig,
    StrategyConfig,
    TrendDirection,
    SignalType,
    PositionSide,
    get_default_config,
)

from market_structure import MarketStructureAnalyzer
from order_flow import OrderFlowAnalyzer
from correlation_analysis import CorrelationAnalyzer
from indicators import TechnicalIndicators
from risk_management import RiskManager
from strategy import StrategyEngine
from main import (
    TradingBot,
    DataHandler,
    generate_sample_data,
    generate_sample_order_book,
    setup_logging,
)
from signal import Signal


# =============================================================================
# DATA GENERATION UTILITIES
# =============================================================================

def generate_trending_data(
    num_candles: int = 100,
    base_price: float = 450.0,
    trend: str = "up",
    volatility: float = 0.01
) -> List[OHLCV]:
    """
    Generate candle data with a trend.

    Args:
        num_candles: Number of candles to generate.
        base_price: Starting price.
        trend: "up", "down", or "sideways".
        volatility: Price volatility factor.

    Returns:
        List of OHLCV candles.
    """
    candles = []
    current_price = base_price
    current_time = datetime.now() - timedelta(minutes=num_candles * 15)

    # Trend bias
    if trend == "up":
        bias = 0.0003
    elif trend == "down":
        bias = -0.0003
    else:
        bias = 0

    for i in range(num_candles):
        # Generate price movement
        change = random.gauss(bias, volatility)
        open_price = current_price
        close_price = open_price * (1 + change)

        # Generate high/low
        if change > 0:
            high = close_price * (1 + abs(random.gauss(0, volatility * 0.5)))
            low = open_price * (1 - abs(random.gauss(0, volatility * 0.3)))
        else:
            high = open_price * (1 + abs(random.gauss(0, volatility * 0.3)))
            low = close_price * (1 - abs(random.gauss(0, volatility * 0.5)))

        # Generate volume (higher on trend days)
        base_volume = random.randint(100000, 300000)
        if abs(change) > volatility:
            base_volume = int(base_volume * 1.5)

        candle = OHLCV(
            timestamp=current_time,
            open=round(open_price, 2),
            high=round(high, 2),
            low=round(low, 2),
            close=round(close_price, 2),
            volume=base_volume,
        )

        candles.append(candle)
        current_price = close_price
        current_time += timedelta(minutes=15)

    return candles


def generate_breakout_scenario(
    base_price: float = 450.0,
    consolidation_candles: int = 30,
    breakout_candles: int = 10
) -> List[OHLCV]:
    """
    Generate data simulating a breakout scenario.

    Args:
        base_price: Starting price.
        consolidation_candles: Number of consolidation candles.
        breakout_candles: Number of breakout candles.

    Returns:
        List of OHLCV candles.
    """
    candles = []
    current_time = datetime.now() - timedelta(minutes=(consolidation_candles + breakout_candles) * 15)

    # Consolidation phase (tight range)
    range_high = base_price * 1.005
    range_low = base_price * 0.995

    for i in range(consolidation_candles):
        open_price = random.uniform(range_low, range_high)
        close_price = random.uniform(range_low, range_high)
        high = max(open_price, close_price) * (1 + random.uniform(0, 0.002))
        low = min(open_price, close_price) * (1 - random.uniform(0, 0.002))

        candles.append(OHLCV(
            timestamp=current_time,
            open=round(open_price, 2),
            high=round(min(high, range_high * 1.001), 2),
            low=round(max(low, range_low * 0.999), 2),
            close=round(close_price, 2),
            volume=random.randint(100000, 200000),
        ))
        current_time += timedelta(minutes=15)

    # Breakout phase (strong move up with volume)
    current_price = range_high
    for i in range(breakout_candles):
        change = random.uniform(0.003, 0.008)  # Strong upward bias
        open_price = current_price
        close_price = open_price * (1 + change)
        high = close_price * (1 + random.uniform(0, 0.003))
        low = open_price * (1 - random.uniform(0, 0.002))

        # High volume on breakout
        volume = random.randint(400000, 800000)

        candles.append(OHLCV(
            timestamp=current_time,
            open=round(open_price, 2),
            high=round(high, 2),
            low=round(low, 2),
            close=round(close_price, 2),
            volume=volume,
        ))

        current_price = close_price
        current_time += timedelta(minutes=15)

    return candles


def generate_mag7_prices(
    spy_price: float,
    bias: str = "neutral"
) -> Dict[str, float]:
    """
    Generate simulated Mag7 stock prices.

    Args:
        spy_price: Current SPY price for correlation.
        bias: "bullish", "bearish", or "neutral".

    Returns:
        Dictionary of Mag7 prices.
    """
    # Base prices (approximate as of late 2024)
    base_prices = {
        'AAPL': 175.0,
        'MSFT': 375.0,
        'GOOGL': 140.0,
        'AMZN': 180.0,
        'NVDA': 480.0,
        'META': 350.0,
        'TSLA': 250.0,
    }

    # Apply bias
    if bias == "bullish":
        multiplier = random.uniform(1.01, 1.03)
    elif bias == "bearish":
        multiplier = random.uniform(0.97, 0.99)
    else:
        multiplier = random.uniform(0.99, 1.01)

    return {
        symbol: round(price * multiplier * random.uniform(0.99, 1.01), 2)
        for symbol, price in base_prices.items()
    }


def generate_breadth_data(bias: str = "neutral") -> Dict:
    """
    Generate simulated market breadth data.

    Args:
        bias: "bullish", "bearish", or "neutral".

    Returns:
        Dictionary with breadth data.
    """
    total_stocks = 500

    if bias == "bullish":
        advances = random.randint(300, 400)
        new_highs = random.randint(50, 100)
        above_50ma = random.uniform(60, 80)
    elif bias == "bearish":
        advances = random.randint(100, 200)
        new_highs = random.randint(5, 20)
        above_50ma = random.uniform(30, 45)
    else:
        advances = random.randint(200, 300)
        new_highs = random.randint(20, 50)
        above_50ma = random.uniform(45, 55)

    declines = total_stocks - advances - random.randint(10, 30)

    return {
        'advances': advances,
        'declines': max(0, declines),
        'unchanged': total_stocks - advances - declines,
        'new_highs': new_highs,
        'new_lows': random.randint(5, 30),
        'above_50ma': above_50ma,
        'above_200ma': above_50ma - random.uniform(5, 15),
    }


# =============================================================================
# EXAMPLE 1: BASIC BOT USAGE
# =============================================================================

def example_basic_usage():
    """
    Demonstrate basic bot usage with sample data.
    """
    print("\n" + "="*70)
    print("EXAMPLE 1: BASIC BOT USAGE")
    print("="*70)

    # Create and configure bot
    config = get_default_config()
    config.symbol = "SPY"
    config.paper_trading = True
    config.initial_capital = 100000.0

    # Initialize bot
    bot = TradingBot(config)
    bot.start()

    # Generate and process sample data
    candles = generate_sample_data(
        symbol="SPY",
        num_candles=100,
        base_price=450.0,
    )

    print(f"\nGenerated {len(candles)} sample candles")
    print(f"Price range: ${min(c.low for c in candles):.2f} - ${max(c.high for c in candles):.2f}")

    # Process data
    bot.process_market_data(candles=candles)

    # Run analysis
    analysis = bot.analyze()

    if analysis:
        print(f"\nAnalysis Results:")
        print(f"  Confluence Score: {analysis.confluence_score:.1f}")
        print(f"  Signal Strength: {analysis.signal_strength.name}")

        if analysis.signal:
            print(f"  Signal Type: {analysis.signal.signal_type.name}")
            print(f"  Confidence: {analysis.signal.confidence:.1f}%")

        print(f"\nNotes:")
        for note in analysis.notes[:5]:  # First 5 notes
            print(f"    - {note}")

    # Get status
    status = bot.get_status()
    print(f"\nBot Status:")
    print(f"  Balance: ${status['account']['balance']:,.2f}")
    print(f"  Positions: {status['positions']}")

    bot.stop()


# =============================================================================
# EXAMPLE 2: BREAKOUT SCENARIO
# =============================================================================

def example_breakout_scenario():
    """
    Demonstrate bot behavior during a breakout.
    """
    print("\n" + "="*70)
    print("EXAMPLE 2: BREAKOUT SCENARIO")
    print("="*70)

    # Generate breakout data
    candles = generate_breakout_scenario(
        base_price=450.0,
        consolidation_candles=30,
        breakout_candles=10,
    )

    print(f"\nGenerated breakout scenario:")
    print(f"  Consolidation: {candles[0].close:.2f} - {candles[29].close:.2f}")
    print(f"  Breakout: {candles[30].close:.2f} -> {candles[-1].close:.2f}")

    # Create strategy engine directly
    strategy = StrategyEngine()

    # Process candles
    for candle in candles:
        strategy.indicators.update(candle)

    # Analyze
    current_price = candles[-1].close
    analysis = strategy.analyze(
        candles=candles,
        current_price=current_price,
    )

    print(f"\nAnalysis:")
    print(f"  Market Condition: {analysis.market_structure.condition.name if analysis.market_structure else 'N/A'}")
    print(f"  Trend: {analysis.market_structure.trend.name if analysis.market_structure else 'N/A'}")
    print(f"  Breakout Detected: {analysis.market_structure.is_breakout if analysis.market_structure else False}")

    if analysis.signal and analysis.signal.signal_type != SignalType.NO_SIGNAL:
        print(f"\nSignal Generated:")
        print(f"  Type: {analysis.signal.signal_type.name}")
        print(f"  Direction: {analysis.signal.direction.name}")
        print(f"  Entry: ${analysis.signal.entry_price:.2f}")
        print(f"  Stop Loss: ${analysis.signal.stop_loss:.2f}")
        print(f"  Take Profit: ${analysis.signal.take_profit:.2f}")
        print(f"  R:R Ratio: {analysis.signal.risk_reward_ratio:.2f}")
        print(f"  Confidence: {analysis.signal.confidence:.1f}%")


# =============================================================================
# EXAMPLE 3: MARKET STRUCTURE ANALYSIS
# =============================================================================

def example_market_structure():
    """
    Demonstrate detailed market structure analysis.
    """
    print("\n" + "="*70)
    print("EXAMPLE 3: MARKET STRUCTURE ANALYSIS (AMT)")
    print("="*70)

    # Generate data
    candles = generate_trending_data(
        num_candles=50,
        base_price=450.0,
        trend="up",
    )

    # Create analyzer
    analyzer = MarketStructureAnalyzer()

    # Calculate indicators for ATR
    indicators = TechnicalIndicators()
    for candle in candles:
        indicators.update(candle)

    atr = indicators.calculate_atr()
    current_price = candles[-1].close

    # Analyze
    structure = analyzer.analyze(
        candles=candles,
        current_price=current_price,
        atr=atr,
    )

    print(f"\nMarket Structure Analysis:")
    print(f"  Current Price: ${current_price:.2f}")
    print(f"  ATR: ${atr:.2f}")

    print(f"\nFair Value Area:")
    print(f"  VAH (Resistance): ${structure.fva.vah:.2f}")
    print(f"  POC (Point of Control): ${structure.fva.poc:.2f}")
    print(f"  VAL (Support): ${structure.fva.val:.2f}")
    print(f"  VA Range: ${structure.fva.range:.2f}")

    print(f"\nPrice Position: {analyzer.get_fva_relationship(current_price, structure.fva)}")

    print(f"\nMarket Condition: {structure.condition.name}")
    print(f"Trend Direction: {structure.trend.name}")
    print(f"Breakout: {structure.is_breakout}")
    print(f"Rejection: {structure.is_rejection}")

    if structure.support_levels:
        print(f"\nSupport Levels:")
        for level in structure.support_levels[:3]:
            print(f"  ${level:.2f}")

    if structure.resistance_levels:
        print(f"\nResistance Levels:")
        for level in structure.resistance_levels[:3]:
            print(f"  ${level:.2f}")


# =============================================================================
# EXAMPLE 4: ORDER FLOW ANALYSIS
# =============================================================================

def example_order_flow():
    """
    Demonstrate order flow analysis.
    """
    print("\n" + "="*70)
    print("EXAMPLE 4: ORDER FLOW ANALYSIS")
    print("="*70)

    # Generate data
    candles = generate_trending_data(
        num_candles=30,
        base_price=450.0,
        trend="up",
    )

    # Create analyzer
    analyzer = OrderFlowAnalyzer()

    print(f"\nProcessing {len(candles)} candles...")

    # Analyze each candle
    for candle in candles:
        analysis = analyzer.analyze(
            candle=candle,
            avg_volume=250000,
        )

    # Get final analysis
    final = analysis

    print(f"\nOrder Flow Analysis:")
    print(f"  Last Delta: {final.delta.delta:,.0f}")
    print(f"  Cumulative Delta: {final.delta.cumulative_delta:,.0f}")
    print(f"  Delta %: {final.delta.delta_percent:.1f}%")

    print(f"\nActivity Detection:")
    print(f"  Aggressive Buying: {final.aggressive_buying}")
    print(f"  Aggressive Selling: {final.aggressive_selling}")
    print(f"  Absorption: {final.absorption_detected}")

    print(f"\nDivergence Detection:")
    print(f"  Divergence Found: {final.divergence_detected}")
    if final.divergence_detected:
        print(f"  Type: {final.divergence_type}")

    print(f"\nScores:")
    print(f"  Breakout Quality: {final.breakout_quality:.1f}")
    print(f"  Liquidity Score: {final.liquidity_score:.1f}")


# =============================================================================
# EXAMPLE 5: CORRELATION ANALYSIS
# =============================================================================

def example_correlation():
    """
    Demonstrate correlation and breadth analysis.
    """
    print("\n" + "="*70)
    print("EXAMPLE 5: CORRELATION & BREADTH ANALYSIS")
    print("="*70)

    # Create analyzer
    analyzer = CorrelationAnalyzer()

    # Simulate data
    spy_price = 450.0
    mag7_prices = generate_mag7_prices(spy_price, bias="bullish")
    vix_level = 15.5
    breadth_data = generate_breadth_data(bias="bullish")

    print(f"\nInput Data:")
    print(f"  SPY Price: ${spy_price:.2f}")
    print(f"  VIX Level: {vix_level}")
    print(f"  Mag7 Prices: {json.dumps(mag7_prices, indent=4)}")

    # Analyze
    result = analyzer.analyze(
        mag7_prices=mag7_prices,
        index_price=spy_price,
        vix_level=vix_level,
        index_direction=TrendDirection.BULLISH,
        breadth_data=breadth_data,
    )

    print(f"\nMag7 Analysis:")
    print(f"  Average Performance: {result.mag7.average_performance:.2f}%")
    print(f"  Confirmation Score: {result.mag7.confirmation_score:.1f}")
    print(f"  Leadership Score: {result.mag7.leadership_score:.1f}")

    print(f"\nVIX Analysis:")
    print(f"  Current Level: {result.vix.current_level}")
    print(f"  Percentile Rank: {result.vix.percentile_rank:.1f}")
    print(f"  Term Structure: {result.vix.term_structure}")
    print(f"  Elevated: {result.vix.is_elevated}")
    print(f"  Diverging: {result.vix.is_diverging}")

    print(f"\nMarket Breadth:")
    print(f"  A/D Ratio: {result.breadth.advance_decline_ratio:.2f}")
    print(f"  Breadth Thrust: {result.breadth.breadth_thrust:.1f}")
    print(f"  % Above 50 MA: {result.breadth.percent_above_50ma:.1f}%")

    print(f"\nOverall Market Health: {result.market_health_score:.1f}/100")

    print(f"\nIntermarket Signals:")
    for key, signal in result.intermarket_signals.items():
        print(f"  {key}: {signal}")


# =============================================================================
# EXAMPLE 6: TECHNICAL INDICATORS
# =============================================================================

def example_indicators():
    """
    Demonstrate technical indicator calculations.
    """
    print("\n" + "="*70)
    print("EXAMPLE 6: TECHNICAL INDICATORS")
    print("="*70)

    # Generate data
    candles = generate_trending_data(
        num_candles=50,
        base_price=450.0,
        trend="up",
    )

    # Create indicator calculator
    indicators = TechnicalIndicators()

    # Calculate all indicators
    indicator_set = indicators.calculate_all(candles)

    print(f"\nTechnical Indicators (based on {len(candles)} candles):")

    print(f"\nRSI ({indicators.config.rsi_period}-period):")
    print(f"  Value: {indicator_set.rsi.value:.2f}")
    print(f"  Overbought: {indicator_set.rsi.is_overbought}")
    print(f"  Oversold: {indicator_set.rsi.is_oversold}")
    print(f"  Divergence: {indicator_set.rsi.divergence or 'None'}")

    print(f"\nMACD ({indicators.config.macd_fast}/{indicators.config.macd_slow}/{indicators.config.macd_signal}):")
    print(f"  MACD Line: {indicator_set.macd.macd_line:.4f}")
    print(f"  Signal Line: {indicator_set.macd.signal_line:.4f}")
    print(f"  Histogram: {indicator_set.macd.histogram:.4f}")
    print(f"  Bullish: {indicator_set.macd.is_bullish}")
    print(f"  Crossover: {indicator_set.macd.crossover or 'None'}")

    print(f"\nBollinger Bands ({indicators.config.bb_period}-period, {indicators.config.bb_std_dev} std):")
    print(f"  Upper: ${indicator_set.bollinger.upper:.2f}")
    print(f"  Middle: ${indicator_set.bollinger.middle:.2f}")
    print(f"  Lower: ${indicator_set.bollinger.lower:.2f}")
    print(f"  %B: {indicator_set.bollinger.percent_b:.2f}")
    print(f"  Bandwidth: {indicator_set.bollinger.bandwidth:.4f}")
    print(f"  Squeeze: {indicator_set.bollinger.squeeze}")

    print(f"\nStochastic ({indicators.config.stoch_k_period}/{indicators.config.stoch_d_period}):")
    print(f"  %K: {indicator_set.stochastic.k:.2f}")
    print(f"  %D: {indicator_set.stochastic.d:.2f}")
    print(f"  Overbought: {indicator_set.stochastic.is_overbought}")
    print(f"  Oversold: {indicator_set.stochastic.is_oversold}")

    print(f"\nATR ({indicators.config.atr_period}-period): ${indicator_set.atr:.2f}")
    print(f"Trend Strength: {indicator_set.trend_strength:.1f}/100")


# =============================================================================
# EXAMPLE 7: RISK MANAGEMENT
# =============================================================================

def example_risk_management():
    """
    Demonstrate risk management features.
    """
    print("\n" + "="*70)
    print("EXAMPLE 7: RISK MANAGEMENT")
    print("="*70)

    from config import TradingSignal, PositionSize

    # Create risk manager
    risk_manager = RiskManager(initial_capital=100000.0)

    print(f"\nInitial Account:")
    print(f"  Balance: ${risk_manager.current_balance:,.2f}")
    print(f"  Equity: ${risk_manager.equity:,.2f}")

    # Create a sample signal
    signal = TradingSignal(
        timestamp=datetime.now(),
        symbol="SPY",
        signal_type=SignalType.BREAKOUT_LONG,
        direction=PositionSide.LONG,
        entry_price=450.00,
        stop_loss=445.00,
        take_profit=465.00,
        confidence=75.0,
    )

    print(f"\nSample Signal:")
    print(f"  Type: {signal.signal_type.name}")
    print(f"  Entry: ${signal.entry_price:.2f}")
    print(f"  Stop: ${signal.stop_loss:.2f}")
    print(f"  Target: ${signal.take_profit:.2f}")
    print(f"  R:R Ratio: {signal.risk_reward_ratio:.2f}")

    # Calculate position size
    position_size = risk_manager.calculate_position_size(signal, signal.entry_price)

    print(f"\nPosition Size Calculation:")
    print(f"  Shares: {position_size.shares}")
    print(f"  Dollar Amount: ${position_size.dollar_amount:,.2f}")
    print(f"  Risk Amount: ${position_size.risk_amount:,.2f}")
    print(f"  % of Account: {position_size.percent_of_account:.2f}%")

    # Validate trade
    validation = risk_manager.validate_trade(signal, position_size)

    print(f"\nTrade Validation:")
    print(f"  Valid: {validation.is_valid}")
    print(f"  Risk Score: {validation.risk_score:.1f}")
    if validation.reasons:
        print(f"  Reasons: {', '.join(validation.reasons)}")
    if validation.warnings:
        print(f"  Warnings: {', '.join(validation.warnings)}")

    # Simulate opening position
    if validation.is_valid:
        position = risk_manager.open_position(signal, position_size, signal.entry_price)
        print(f"\nPosition Opened:")
        print(f"  Symbol: {position.symbol}")
        print(f"  Shares: {position.quantity}")
        print(f"  Entry: ${position.entry_price:.2f}")

        # Simulate price movement
        new_price = 455.00
        risk_manager.update_position("SPY", new_price)

        print(f"\nAfter Price Move to ${new_price:.2f}:")
        print(f"  Unrealized P&L: ${position.unrealized_pnl:,.2f}")
        print(f"  Unrealized %: {position.unrealized_pnl_percent:.2f}%")

        # Get risk metrics
        metrics = risk_manager.calculate_risk_metrics()
        print(f"\nRisk Metrics:")
        print(f"  Total Exposure: ${metrics.total_exposure:,.2f}")
        print(f"  Current Drawdown: {metrics.current_drawdown:.2f}%")

        # Close position
        trade = risk_manager.close_position("SPY", new_price, "take_profit")
        if trade:
            print(f"\nPosition Closed:")
            print(f"  Exit Price: ${trade.exit_price:.2f}")
            print(f"  P&L: ${trade.pnl:,.2f}")
            print(f"  P&L %: {trade.pnl_percent:.2f}%")


# =============================================================================
# EXAMPLE 8: FULL TRADING SIMULATION
# =============================================================================

def example_full_simulation():
    """
    Run a complete trading simulation.
    """
    print("\n" + "="*70)
    print("EXAMPLE 8: FULL TRADING SIMULATION")
    print("="*70)

    # Configure bot
    config = get_default_config()
    config.symbol = "SPY"
    config.paper_trading = True
    config.initial_capital = 100000.0
    config.strategy.min_confidence = 50.0  # Lower threshold for demo

    # Create bot
    bot = TradingBot(config)

    # Track trades
    trades = []

    def on_trade(event_type, signal, trade_or_position):
        if event_type == 'close':
            trades.append(trade_or_position)

    bot.register_trade_callback(on_trade)

    # Start bot
    bot.start()

    # Simulate multiple days
    print(f"\nRunning 5-day simulation...")

    for day in range(5):
        # Generate daily data
        trend = random.choice(["up", "down", "sideways"])
        candles = generate_trending_data(
            num_candles=26,  # ~6.5 hours of 15-min candles
            base_price=450.0 + random.uniform(-10, 10),
            trend=trend,
        )

        # Process each candle
        for candle in candles:
            bot.data_handler.add_candle(candle)

        # Generate supporting data
        current_price = bot.data_handler.get_current_price()
        mag7 = generate_mag7_prices(current_price, bias=trend if trend != "sideways" else "neutral")
        vix = random.uniform(12, 25)
        breadth = generate_breadth_data(bias=trend if trend != "sideways" else "neutral")

        # Run analysis with full data
        analysis = bot.analyze(
            mag7_prices=mag7,
            vix_level=vix,
            breadth_data=breadth,
        )

        print(f"\nDay {day + 1} ({trend} trend):")
        print(f"  Close: ${current_price:.2f}")
        print(f"  Positions: {len(bot.get_positions())}")

        if analysis and analysis.signal:
            print(f"  Signal: {analysis.signal.signal_type.name} ({analysis.signal.confidence:.1f}%)")

    # Final status
    bot.stop()

    status = bot.get_status()
    print(f"\n" + "="*40)
    print("SIMULATION RESULTS")
    print("="*40)
    print(f"Final Balance: ${status['account']['balance']:,.2f}")
    print(f"Realized P&L: ${status['account']['realized_pnl']:,.2f}")
    print(f"Total Trades: {len(trades)}")

    if trades:
        winners = sum(1 for t in trades if t.pnl > 0)
        print(f"Win Rate: {(winners / len(trades) * 100):.1f}%")
        print(f"Avg P&L: ${sum(t.pnl for t in trades) / len(trades):,.2f}")


# =============================================================================
# EXAMPLE 9: WEBHOOK SIGNAL INTEGRATION
# =============================================================================

def example_webhook_signals():
    """
    Demonstrate Signal class and webhook integration.

    This example shows how to:
    1. Register a signal callback for webhook integration
    2. Receive standardized Signal objects
    3. Convert signals to JSON for external transmission
    """
    print("\n" + "="*70)
    print("EXAMPLE 9: WEBHOOK SIGNAL INTEGRATION")
    print("="*70)

    # Store received signals for demonstration
    received_signals: list = []

    def webhook_handler(signal: Signal):
        """
        Example webhook handler that receives standardized signals.

        In a real implementation, this would POST to TradingView
        or another webhook endpoint.
        """
        received_signals.append(signal)
        print(f"\n  [WEBHOOK] Received signal:")
        print(f"    Symbol: {signal.symbol}")
        print(f"    Side: {signal.side}")
        print(f"    Type: {signal.signal_type}")
        print(f"    Entry: ${signal.entry_price:.2f}")
        print(f"    Stop: ${signal.stop_loss:.2f}")
        print(f"    Targets: {[f'${t:.2f}' for t in signal.targets]}")
        print(f"    Confidence: {signal.confidence:.1%}")
        print(f"    R:R Ratio: {signal.risk_reward_ratio:.2f}")

    # Create and configure bot
    config = get_default_config()
    config.symbol = "SPY"
    config.paper_trading = True
    config.initial_capital = 100000.0
    config.strategy.min_confidence = 40.0  # Lower threshold for demo

    bot = TradingBot(config)

    # Register the webhook handler
    bot.register_signal_callback(webhook_handler)
    print("\nWebhook handler registered")

    # Start bot
    bot.start()

    # Generate breakout scenario (more likely to produce signals)
    print("\nGenerating breakout scenario data...")
    candles = generate_breakout_scenario(
        base_price=450.0,
        consolidation_candles=30,
        breakout_candles=15,
    )

    # Process data
    bot.process_market_data(candles=candles)

    # Run analysis (this may trigger signal emission)
    analysis = bot.analyze()

    print(f"\nAnalysis complete:")
    print(f"  Signal Type: {analysis.signal.signal_type.name if analysis.signal else 'None'}")

    # Check if webhook_signal is available in the analysis result
    if analysis.webhook_signal:
        print(f"\n  Webhook signal available in AnalysisResult:")
        print(f"    {analysis.webhook_signal}")

    # Demonstrate Signal class directly
    print("\n" + "-"*50)
    print("Direct Signal Class Usage:")
    print("-"*50)

    # Create a Signal directly
    direct_signal = Signal(
        symbol="AAPL",
        timeframe="15m",
        side="LONG",
        entry_price=175.50,
        stop_loss=173.00,
        targets=[177.75, 180.00, 182.25],
        signal_type="BREAKOUT",
        confidence=0.82,
        timestamp="2024-12-13T14:30:00+00:00"
    )

    print(f"\nCreated Signal: {direct_signal}")

    # Convert to JSON (for webhook transmission)
    json_output = direct_signal.to_json(indent=2)
    print(f"\nJSON output for webhook:")
    print(json_output)

    # Demonstrate round-trip (JSON -> Signal)
    reconstructed = Signal.from_json(json_output)
    print(f"\nReconstructed from JSON: {reconstructed}")

    # Signal properties
    print(f"\nSignal Properties:")
    print(f"  is_long: {direct_signal.is_long}")
    print(f"  is_short: {direct_signal.is_short}")
    print(f"  risk_reward_ratio: {direct_signal.risk_reward_ratio:.2f}")

    # Summary
    print(f"\n" + "-"*50)
    print(f"Total signals received via webhook: {len(received_signals)}")

    bot.stop()


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    """Run all examples."""
    print("\n" + "="*70)
    print("AMT TRADING BOT - COMPLETE EXAMPLE USAGE")
    print("="*70)
    print("\nThis script demonstrates all features of the trading bot.")
    print("Each example shows a different aspect of the system.\n")

    examples = [
        ("Basic Usage", example_basic_usage),
        ("Breakout Scenario", example_breakout_scenario),
        ("Market Structure (AMT)", example_market_structure),
        ("Order Flow", example_order_flow),
        ("Correlation & Breadth", example_correlation),
        ("Technical Indicators", example_indicators),
        ("Risk Management", example_risk_management),
        ("Full Simulation", example_full_simulation),
        ("Webhook Signal Integration", example_webhook_signals),
    ]

    print("Available Examples:")
    for i, (name, _) in enumerate(examples, 1):
        print(f"  {i}. {name}")

    print("\nRunning all examples...\n")

    for name, func in examples:
        try:
            func()
        except Exception as e:
            print(f"\nError in {name}: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "="*70)
    print("ALL EXAMPLES COMPLETED")
    print("="*70)
    print("\nThe AMT Trading Bot is ready for use!")
    print("See the documentation for more details on customization.")


if __name__ == "__main__":
    main()
