# AMT Trading Bot

A professional Auction Market Theory (AMT) trading bot with comprehensive market analysis capabilities.

## Overview

This trading bot implements Auction Market Theory principles combined with modern order flow analysis, correlation studies, and technical indicators to generate high-probability trading signals.

## Features

### Market Structure Analysis (AMT)
- **TPO Profiles**: Time Price Opportunity analysis showing time spent at each price level
- **Fair Value Areas**: Automatic calculation of VAH, VAL, and POC
- **Volume Profile**: Volume distribution analysis with HVN/LVN identification
- **Breakout Detection**: Volume-confirmed breakouts from value areas
- **Rejection Detection**: Price rejection patterns at key levels
- **Support/Resistance**: Automatic identification of significant price levels

### Order Flow Analysis
- **Delta Calculation**: Buy vs. sell volume analysis
- **Cumulative Delta**: Running delta for trend confirmation
- **Divergence Detection**: Price/delta divergences for reversals
- **Absorption Detection**: Large orders being absorbed by the market
- **Breakout Quality Scoring**: Confidence scoring for breakouts
- **DOM Analysis**: Depth of market analysis for liquidity assessment

### Correlation Analysis
- **Mag7 Analysis**: Track market-leading tech stocks for confirmation
- **VIX Analysis**: Volatility index for fear/greed assessment
- **Market Breadth**: Advance/decline ratios, new highs/lows
- **Sector Rotation**: Risk-on/risk-off environment detection
- **Market Health Score**: Comprehensive market health metric

### Technical Indicators
- **RSI**: Relative Strength Index with divergence detection
- **MACD**: Moving Average Convergence Divergence with crossover alerts
- **Bollinger Bands**: Volatility bands with squeeze detection
- **ATR**: Average True Range for volatility measurement
- **Stochastic**: Stochastic oscillator with overbought/oversold signals
- **Moving Averages**: SMA, EMA, VWMA calculations

### Risk Management
- **Position Sizing**: Risk-based position size calculation
- **Trade Validation**: Multi-factor trade approval system
- **Daily Loss Limits**: Automatic daily loss protection
- **Exposure Tracking**: Total portfolio exposure monitoring
- **Trailing Stops**: ATR-based trailing stop management
- **Slippage Estimation**: Realistic fill price estimation

### Signal Types
1. **Breakout Long/Short**: Value area breakouts with volume confirmation
2. **Rejection Long/Short**: Key level rejections with reversal patterns
3. **Divergence Long/Short**: Price/indicator divergence signals

## File Structure

```
trading_bot/
├── config.py              # Configuration, enums, data classes
├── market_structure.py    # AMT market structure analysis
├── order_flow.py          # Order flow analysis
├── correlation_analysis.py # Correlation and breadth analysis
├── indicators.py          # Technical indicators
├── risk_management.py     # Risk management system
├── strategy.py            # Main strategy engine
├── main.py                # Bot application
├── example_usage.py       # Complete working examples
├── claude_interactive.py  # Interactive development script
├── README.md              # This file
├── QUICK_START.md         # Quick start guide
├── SETUP_SUMMARY.md       # Setup summary
├── IMPLEMENTATION_GUIDE.md # Advanced usage guide
└── CLAUDE_*.md            # Claude development guides
```

## Quick Start

```python
from main import TradingBot, generate_sample_data
from config import get_default_config

# Create configuration
config = get_default_config()
config.symbol = "SPY"
config.paper_trading = True
config.initial_capital = 100000.0

# Initialize bot
bot = TradingBot(config)
bot.start()

# Generate sample data (or use real data)
candles = generate_sample_data(num_candles=100)
bot.process_market_data(candles=candles)

# Run analysis
analysis = bot.analyze()

# Check for signals
if analysis.signal:
    print(f"Signal: {analysis.signal.signal_type.name}")
    print(f"Confidence: {analysis.signal.confidence}%")

# Get status
print(bot.get_status())

bot.stop()
```

## Running the Examples

```bash
# Run the complete example suite
python example_usage.py

# Start interactive development session
python claude_interactive.py

# Run the bot directly
python main.py
```

## Configuration

The bot is highly configurable through the `BotConfig` class:

```python
from config import BotConfig, RiskConfig, StrategyConfig

config = BotConfig(
    symbol="SPY",
    paper_trading=True,
    initial_capital=100000.0,
    risk=RiskConfig(
        max_position_size_percent=5.0,
        max_daily_loss_percent=2.0,
        min_risk_reward_ratio=2.0,
    ),
    strategy=StrategyConfig(
        min_confidence=60.0,
        enable_breakout_signals=True,
        enable_rejection_signals=True,
        enable_divergence_signals=True,
    ),
)
```

## Signal Generation

The strategy engine combines multiple analysis components:

1. **Market Structure**: Identifies trading context (trend, range, breakout)
2. **Order Flow**: Confirms buyer/seller aggression
3. **Correlation**: Validates with market breadth and leaders
4. **Indicators**: Technical confirmation signals

Signals require minimum confluence before generation.

## Risk Management

Every signal is validated through risk management:

- Position size based on account risk percentage
- Stop loss and take profit calculated from ATR and structure
- Daily loss limits enforced automatically
- Maximum exposure limits respected
- Correlated position limits applied

## Paper Trading

The bot includes a complete paper trading system:

- Simulated order execution with slippage
- Position tracking with P&L calculation
- Trade history and statistics
- Performance metrics (win rate, Sharpe ratio, etc.)

## Extending the Bot

### Adding New Indicators

```python
from indicators import TechnicalIndicators

class MyIndicators(TechnicalIndicators):
    def calculate_custom_indicator(self, data):
        # Your custom indicator logic
        pass
```

### Adding New Signal Types

```python
from config import SignalType
from strategy import StrategyEngine

# Add to SignalType enum in config.py
# Then extend _generate_signal in strategy.py
```

### Custom Data Sources

Implement your own data handler to connect to real data:

```python
from main import DataHandler

class MyDataHandler(DataHandler):
    def connect_to_broker(self):
        # Your broker connection
        pass

    def subscribe_to_data(self):
        # Real-time data subscription
        pass
```

## API Reference

See the comprehensive docstrings in each module for detailed API documentation.

### Key Classes

- `TradingBot`: Main bot orchestrator
- `StrategyEngine`: Signal generation engine
- `MarketStructureAnalyzer`: AMT analysis
- `OrderFlowAnalyzer`: Order flow analysis
- `CorrelationAnalyzer`: Correlation analysis
- `TechnicalIndicators`: Technical indicators
- `RiskManager`: Risk management

### Key Data Classes

- `OHLCV`: Candle data structure
- `TradingSignal`: Generated signals
- `Trade`: Executed trade records
- `Position`: Open position tracking
- `FairValueArea`: Value area data
- `OrderFlowAnalysis`: Order flow results

## Requirements

- Python 3.8+
- No external dependencies required (uses standard library only)

## License

This trading bot is provided for educational purposes. Use at your own risk.

## Disclaimer

This software is for educational purposes only. Trading involves substantial risk of loss. Past performance is not indicative of future results. Always paper trade first and understand the risks before trading with real money.
