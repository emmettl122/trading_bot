# Quick Start Guide

Get the AMT Trading Bot running in 10 minutes.

## Step 1: Verify Files (1 minute)

Ensure all files are present:

```bash
ls -la /home/emmett/trading_bot/
```

You should see:
- `config.py`
- `market_structure.py`
- `order_flow.py`
- `correlation_analysis.py`
- `indicators.py`
- `risk_management.py`
- `strategy.py`
- `main.py`
- `example_usage.py`
- `claude_interactive.py`

## Step 2: Run Basic Test (2 minutes)

```bash
cd /home/emmett/trading_bot
python main.py
```

You should see:
- Bot initialization messages
- Analysis results
- Bot status output

## Step 3: Run Examples (3 minutes)

```bash
python example_usage.py
```

This runs 8 comprehensive examples showing all features.

## Step 4: Interactive Session (2 minutes)

```bash
python claude_interactive.py
```

Try these commands:
- `help` - See available commands
- `files` - List all bot files
- `bot` - Create bot instance
- `analyze` - Run quick analysis
- `status` - Check bot status
- `quit` - Exit

## Step 5: Custom Configuration (2 minutes)

Create your own configuration:

```python
from main import TradingBot
from config import get_default_config

# Get default config
config = get_default_config()

# Customize
config.symbol = "QQQ"
config.initial_capital = 50000.0
config.risk.max_position_size_percent = 3.0
config.strategy.min_confidence = 70.0

# Create bot
bot = TradingBot(config)
```

## Quick Reference

### Generate Sample Data

```python
from main import generate_sample_data

candles = generate_sample_data(
    symbol="SPY",
    num_candles=100,
    base_price=450.0,
)
```

### Run Analysis

```python
bot.start()
bot.process_market_data(candles=candles)
analysis = bot.analyze()

print(f"Signal: {analysis.signal.signal_type.name}")
print(f"Confidence: {analysis.signal.confidence}%")
```

### Check Positions

```python
positions = bot.get_positions()
for pos in positions:
    print(f"{pos.symbol}: {pos.unrealized_pnl}")
```

### Get Trade History

```python
trades = bot.get_trade_history()
for trade in trades:
    print(f"{trade.symbol}: ${trade.pnl:.2f}")
```

## Common Issues

### Import Errors

Make sure you're in the correct directory:
```bash
cd /home/emmett/trading_bot
```

### No Signals Generated

Lower the confidence threshold:
```python
config.strategy.min_confidence = 40.0
```

### Module Not Found

Ensure Python path includes the bot directory:
```python
import sys
sys.path.insert(0, '/home/emmett/trading_bot')
```

## Next Steps

1. Read `IMPLEMENTATION_GUIDE.md` for advanced usage
2. Read `README.md` for complete feature documentation
3. Explore each module's docstrings for API details
4. Start customizing for your trading style

## Support

Use the interactive session to explore and modify the bot:
```bash
python claude_interactive.py
```

Or work directly with Claude Code for real-time assistance.
