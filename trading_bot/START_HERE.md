# START HERE

Welcome to the AMT Trading Bot! This is your entry point to understanding and using the system.

## What Is This?

The AMT Trading Bot is a comprehensive algorithmic trading system that implements:

- **Auction Market Theory (AMT)**: Professional market structure analysis
- **Order Flow Analysis**: Understanding buyer/seller behavior
- **Correlation Analysis**: Market context and breadth
- **Technical Indicators**: Classic and advanced indicators
- **Risk Management**: Professional position sizing and risk controls
- **Paper Trading**: Safe testing environment

## Quick Navigation

### I want to...

#### Get started immediately
→ Read [QUICK_START.md](QUICK_START.md)

```bash
cd /home/emmett/trading_bot
python example_usage.py
```

#### Understand all features
→ Read [README.md](README.md)

#### See what was created
→ Read [SETUP_SUMMARY.md](SETUP_SUMMARY.md)

#### Customize and extend
→ Read [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md)

#### Develop with Claude
→ Read [CLAUDE_TERMINAL_DEV_GUIDE.md](CLAUDE_TERMINAL_DEV_GUIDE.md)

#### Master the development workflow
→ Read [CLAUDE_DEVELOPMENT_MASTER.md](CLAUDE_DEVELOPMENT_MASTER.md)

## 5-Minute Overview

### The Files

| File | Purpose |
|------|---------|
| `config.py` | All settings, data structures, and enums |
| `market_structure.py` | AMT analysis (Fair Value Areas, breakouts) |
| `order_flow.py` | Delta, volume analysis, divergences |
| `correlation_analysis.py` | Mag7, VIX, market breadth |
| `indicators.py` | RSI, MACD, Bollinger Bands, etc. |
| `risk_management.py` | Position sizing, trade validation |
| `strategy.py` | Signal generation engine |
| `main.py` | Main bot application |
| `example_usage.py` | Working examples |
| `claude_interactive.py` | Interactive development |

### How It Works

```
Market Data → Analysis → Signals → Risk Check → Execution (Paper)
     ↓            ↓          ↓           ↓
  Candles    Structure    Buy/Sell   Valid?     Trade
  Ticks      Order Flow   Long/Short  Size      P&L
  Book       Indicators   Confidence  Limits    Track
```

### Signal Types

1. **Breakout Long/Short**: Price breaks out of value area with volume
2. **Rejection Long/Short**: Price rejects at key levels
3. **Divergence Long/Short**: Price/indicator divergence

## First Steps

### Step 1: Run the Examples

```bash
cd /home/emmett/trading_bot
python example_usage.py
```

This shows:
- Basic bot usage
- Breakout scenario
- Market structure analysis
- Order flow analysis
- Correlation analysis
- Technical indicators
- Risk management
- Full trading simulation

### Step 2: Start Interactive Session

```bash
python claude_interactive.py
```

Commands to try:
- `help` - See all commands
- `bot` - Create bot instance
- `analyze` - Run analysis
- `status` - Check status

### Step 3: Understand the Code

Start with `config.py` to understand data structures:

```python
# Key data structures
OHLCV           # Price candle
TradingSignal   # Generated signal
Trade           # Executed trade
Position        # Open position
FairValueArea   # AMT value area
```

### Step 4: Customize

```python
from config import get_default_config

config = get_default_config()
config.symbol = "QQQ"
config.initial_capital = 50000.0
config.risk.max_position_size_percent = 3.0
config.strategy.min_confidence = 65.0
```

## Key Concepts

### Auction Market Theory

The market is an auction process where:
- **Value Area**: Where 70% of trading occurs
- **VAH**: Value Area High (resistance)
- **VAL**: Value Area Low (support)
- **POC**: Point of Control (highest volume price)
- **Breakouts**: Price leaving value area
- **Rejections**: Price bouncing off value area edges

### Order Flow

Understanding buyer/seller activity:
- **Delta**: Buy volume minus sell volume
- **Cumulative Delta**: Running total of delta
- **Divergence**: When price and delta disagree
- **Absorption**: Large orders being absorbed

### Risk Management

Every trade is validated:
- Position size based on risk percentage
- Minimum risk-reward ratio required
- Daily loss limits enforced
- Maximum exposure limits
- Correlated position limits

## Getting Help

### Documentation

1. [README.md](README.md) - Complete reference
2. [QUICK_START.md](QUICK_START.md) - Fast setup
3. [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md) - Advanced usage

### Interactive Development

```bash
python claude_interactive.py
```

### With Claude Code

When asking Claude:
- Be specific about what you want
- Include relevant code or errors
- Mention which file you're working with
- Describe expected vs actual behavior

## Architecture Summary

```
┌─────────────────────────────────────────────────────┐
│                    TradingBot                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │ DataHandler │  │  Strategy   │  │ RiskManager │  │
│  │             │  │   Engine    │  │             │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  │
│         │               │                │          │
│         ▼               ▼                ▼          │
│  ┌─────────────────────────────────────────────┐   │
│  │              Analysis Components             │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────────┐ │   │
│  │  │ Market   │ │  Order   │ │ Correlation  │ │   │
│  │  │Structure │ │  Flow    │ │  Analysis    │ │   │
│  │  └──────────┘ └──────────┘ └──────────────┘ │   │
│  │  ┌──────────────────────────────────────┐   │   │
│  │  │       Technical Indicators            │   │   │
│  │  └──────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

## Next Steps

1. **Run examples**: `python example_usage.py`
2. **Read documentation**: Start with README.md
3. **Explore interactively**: `python claude_interactive.py`
4. **Customize**: Modify configuration
5. **Extend**: Add your own features

---

**Ready to start?** Run `python example_usage.py` now!
