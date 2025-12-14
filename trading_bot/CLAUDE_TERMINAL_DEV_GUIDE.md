# Claude Terminal Development Guide

Comprehensive guide for developing the AMT Trading Bot with Claude in the terminal.

## Overview

This guide covers how to effectively work with Claude Code to develop, debug, and extend the trading bot directly from your terminal.

## Getting Started

### Starting an Interactive Session

```bash
cd /home/emmett/trading_bot
python claude_interactive.py
```

### Available Commands

| Command | Description |
|---------|-------------|
| `help` | Show all available commands |
| `files` | List all bot files |
| `status` | Show bot status |
| `bot` | Create/access bot instance |
| `analyze` | Run quick analysis |
| `reload` | Reload all modules |
| `history` | Show conversation history |
| `context` | Show current context |
| `clear` | Clear conversation history |
| `quit` | Exit session |

## Common Development Tasks

### 1. Exploring the Codebase

**List all files:**
```
files
```

**Check module structure:**
```python
# In Python REPL after loading modules
from claude_interactive import load_all_modules
modules = load_all_modules()
print(modules.keys())
```

### 2. Testing Changes

**Quick analysis test:**
```
analyze
```

**Custom test:**
```python
from main import TradingBot, generate_sample_data
from config import get_default_config

config = get_default_config()
bot = TradingBot(config)
bot.start()

candles = generate_sample_data(num_candles=100)
bot.process_market_data(candles=candles)

analysis = bot.analyze()
print(analysis.notes)
```

### 3. Modifying Components

**Reload after changes:**
```
reload
```

**Test specific module:**
```python
from indicators import TechnicalIndicators
indicators = TechnicalIndicators()
# Test your changes
```

### 4. Debugging

**Check component state:**
```python
# Get bot status
status
# Or programmatically
bot.get_status()
bot.strategy.get_market_summary()
```

**Inspect analysis results:**
```python
analysis = bot.analyze()
print(f"Market Structure: {analysis.market_structure}")
print(f"Order Flow: {analysis.order_flow}")
print(f"Indicators: {analysis.indicators}")
```

## Working with Claude Code

### Effective Communication

When asking Claude for help:

1. **Be Specific**
   ```
   "The RSI calculation in indicators.py is returning incorrect values
   when I use a period of 7. The current code is at line 145."
   ```

2. **Provide Context**
   ```
   "I'm trying to add a custom signal type for inside bar patterns.
   I've added the enum to config.py but need help with the detection
   logic in strategy.py."
   ```

3. **Share Error Messages**
   ```
   "I'm getting this error when running analysis:
   AttributeError: 'NoneType' object has no attribute 'delta'
   This happens in order_flow.py line 234."
   ```

### Common Requests

**Adding Features:**
```
"Add a new indicator called 'Volume Profile POC' to indicators.py
that calculates the price level with highest volume from the last
20 candles."
```

**Fixing Bugs:**
```
"The position sizing in risk_management.py is calculating shares
incorrectly. When risk per share is $5 and max risk is $1000,
it should return 200 shares but returns 0."
```

**Explaining Code:**
```
"Explain how the breakout detection works in market_structure.py,
specifically the detect_breakout method."
```

**Optimizing Performance:**
```
"The calculate_all method in indicators.py is slow when processing
500+ candles. How can I optimize it?"
```

## Development Workflow

### Standard Workflow

1. **Start Session**
   ```bash
   python claude_interactive.py
   ```

2. **Load Current State**
   ```
   bot
   status
   ```

3. **Make Changes**
   - Edit files directly
   - Ask Claude for help
   - Use `reload` to apply changes

4. **Test Changes**
   ```
   analyze
   ```

5. **Iterate**
   - Fix issues
   - Add features
   - Test again

### Feature Development Workflow

1. **Plan the Feature**
   - Discuss requirements with Claude
   - Identify files to modify
   - Design the approach

2. **Implement**
   - Start with config.py (data structures)
   - Add core logic to relevant module
   - Integrate in strategy.py
   - Update main.py if needed

3. **Test**
   - Unit test the component
   - Integration test with full bot
   - Edge case testing

4. **Document**
   - Add docstrings
   - Update README if needed

### Debugging Workflow

1. **Reproduce the Issue**
   ```python
   # Create minimal reproduction
   from market_structure import MarketStructureAnalyzer
   analyzer = MarketStructureAnalyzer()
   # ... steps that cause the issue
   ```

2. **Isolate the Problem**
   - Print intermediate values
   - Check input data
   - Verify assumptions

3. **Fix and Verify**
   ```
   reload
   analyze
   ```

## Tips and Best Practices

### 1. Use the Interactive Session

The `claude_interactive.py` script provides:
- Quick access to all modules
- Command history (saved between sessions)
- Easy testing environment

### 2. Keep Modules Separate

When making changes:
- Data structures go in `config.py`
- Analysis logic in respective modules
- Integration in `strategy.py`
- Application logic in `main.py`

### 3. Test Incrementally

Don't make too many changes at once:
- Make small changes
- Test immediately
- Commit working code

### 4. Use Sample Data

The bot includes data generators:
```python
from main import generate_sample_data
from example_usage import generate_trending_data, generate_breakout_scenario

# Simple data
candles = generate_sample_data(100)

# Trending data
candles = generate_trending_data(100, trend="up")

# Breakout scenario
candles = generate_breakout_scenario()
```

### 5. Check Documentation

Before asking Claude:
- Check docstrings in the code
- Read README.md
- Review IMPLEMENTATION_GUIDE.md

### 6. Save Your Work

The bot doesn't persist state:
- Export important configurations
- Save custom strategies to files
- Document your changes

## Troubleshooting

### Module Not Loading

```python
# Check for syntax errors
import py_compile
py_compile.compile('module_name.py')
```

### Import Errors

```python
# Ensure path is correct
import sys
sys.path.insert(0, '/home/emmett/trading_bot')
```

### Unexpected Results

```python
# Add debug output
print(f"DEBUG: {variable}")

# Check data types
print(f"Type: {type(variable)}")
print(f"Value: {variable}")
```

### Performance Issues

```python
import time

start = time.time()
# Your code
end = time.time()
print(f"Elapsed: {end - start:.3f}s")
```

## Advanced Usage

### Custom REPL

```python
# Start Python with bot modules loaded
import sys
sys.path.insert(0, '/home/emmett/trading_bot')

from claude_interactive import load_all_modules
modules = load_all_modules()

# All modules now available
from main import TradingBot
from config import *
from strategy import StrategyEngine
```

### Automated Testing

```python
# Run all examples
exec(open('example_usage.py').read())
```

### Batch Processing

```python
# Process multiple scenarios
scenarios = ['up', 'down', 'sideways']
for trend in scenarios:
    candles = generate_trending_data(100, trend=trend)
    bot.process_market_data(candles=candles)
    analysis = bot.analyze()
    print(f"{trend}: {analysis.signal.signal_type.name}")
```

## Resources

- **README.md**: Feature overview and quick start
- **QUICK_START.md**: 10-minute setup guide
- **IMPLEMENTATION_GUIDE.md**: Advanced customization
- **SETUP_SUMMARY.md**: File and feature checklist

## Getting Help

When you need assistance:

1. Use the interactive session
2. Describe your problem clearly
3. Include relevant code snippets
4. Share error messages
5. Mention what you've already tried

Claude Code can help with:
- Understanding the codebase
- Debugging issues
- Adding features
- Optimizing performance
- Explaining concepts
- Writing tests
