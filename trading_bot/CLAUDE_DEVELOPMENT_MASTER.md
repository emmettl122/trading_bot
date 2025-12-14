# Claude Development Master Guide

The definitive guide for developing with Claude Code on the AMT Trading Bot.

## Philosophy

This guide embodies a development philosophy centered on:
- **Iterative development**: Small changes, frequent testing
- **Clear communication**: Precise requests, detailed context
- **Modular design**: Separation of concerns, easy extension
- **Quality code**: Comprehensive documentation, error handling

## Development Environment

### Directory Structure

```
/home/emmett/trading_bot/
├── Core Modules
│   ├── config.py           # Foundation - all data structures
│   ├── market_structure.py # AMT analysis engine
│   ├── order_flow.py       # Order flow analysis
│   ├── correlation_analysis.py # Market context
│   ├── indicators.py       # Technical indicators
│   ├── risk_management.py  # Risk controls
│   ├── strategy.py         # Signal generation
│   └── main.py             # Application entry
│
├── Utilities
│   ├── example_usage.py    # Working examples
│   └── claude_interactive.py # Interactive dev
│
└── Documentation
    ├── README.md
    ├── QUICK_START.md
    ├── SETUP_SUMMARY.md
    ├── IMPLEMENTATION_GUIDE.md
    ├── CLAUDE_TERMINAL_DEV_GUIDE.md
    ├── CLAUDE_DEVELOPMENT_MASTER.md
    └── START_HERE.md
```

### Module Dependencies

```
config.py (no dependencies)
    ↓
market_structure.py ← config
order_flow.py ← config
correlation_analysis.py ← config
indicators.py ← config
    ↓
risk_management.py ← config
    ↓
strategy.py ← all above
    ↓
main.py ← all above
```

## Working with Claude Code

### Session Management

**Starting a session:**
```bash
cd /home/emmett/trading_bot
python claude_interactive.py
```

**Session commands:**
- `bot` - Initialize bot instance
- `status` - Check current state
- `analyze` - Run analysis
- `reload` - Reload after changes
- `files` - List project files

### Effective Prompting

#### For Code Changes

**Good:**
```
"In risk_management.py, modify the calculate_position_size method
to include a volatility adjustment. When ATR is above average,
reduce position size by 20%. The ATR parameter is already available."
```

**Not as good:**
```
"Make position sizing better"
```

#### For Bug Fixes

**Good:**
```
"The detect_divergence method in order_flow.py returns False even
when price is making higher highs but delta is making lower highs.

Current behavior: Returns False
Expected behavior: Returns (True, 'bearish')

Sample data that fails:
- Prices: [100, 102, 101, 104]
- Deltas: [1000, 1200, 800, 600]
```

**Not as good:**
```
"Divergence detection doesn't work"
```

#### For New Features

**Good:**
```
"Add an Inside Bar pattern detector to market_structure.py:

1. Create an InsideBar dataclass in config.py with:
   - timestamp
   - mother_bar (OHLCV)
   - inside_bar (OHLCV)
   - breakout_direction (optional)

2. Add detect_inside_bar method that:
   - Identifies when current bar is completely inside previous bar
   - Returns InsideBar instance or None

3. Integrate into analyze method

Example inside bar:
- Mother: High=105, Low=100
- Inside: High=103, Low=101 (completely contained)
```

**Not as good:**
```
"Add inside bars"
```

### Code Review Requests

**Requesting review:**
```
"Review my changes to indicators.py:

I added a custom Williams %R indicator at line 350-380.

Please check:
1. Calculation correctness
2. Edge case handling
3. Integration with calculate_all method
4. Documentation completeness
```

### Debugging Assistance

**Requesting debug help:**
```
"Help debug this issue in strategy.py:

Error:
TypeError: unsupported operand type(s) for +: 'float' and 'NoneType'

Traceback points to line 245 in _check_breakout_signal

I think the issue is that order_flow.breakout_quality is None
when no order book is provided, but I'm not sure how to handle it.

Current code at line 243-248:
[paste relevant code]
```

## Development Patterns

### Pattern 1: Adding a New Indicator

1. **Define data structure** (config.py)
```python
@dataclass
class MyIndicatorData:
    value: float
    signal: str
```

2. **Implement calculation** (indicators.py)
```python
def calculate_my_indicator(self, data):
    # Your calculation
    return MyIndicatorData(value=result, signal=signal)
```

3. **Add to IndicatorSet** (config.py)
```python
@dataclass
class IndicatorSet:
    # ... existing fields
    my_indicator: MyIndicatorData
```

4. **Update calculate_all** (indicators.py)
```python
def calculate_all(self, candles=None):
    # ... existing code
    my_ind = self.calculate_my_indicator(closes)
    return IndicatorSet(
        # ... existing
        my_indicator=my_ind,
    )
```

### Pattern 2: Adding a New Signal Type

1. **Add enum value** (config.py)
```python
class SignalType(Enum):
    # ... existing
    MY_SIGNAL_LONG = auto()
    MY_SIGNAL_SHORT = auto()
```

2. **Add detection method** (strategy.py)
```python
def _check_my_signal(self, market_structure, order_flow, indicators):
    # Your detection logic
    return signal_type, direction, confidence, reasons
```

3. **Integrate in _generate_signal** (strategy.py)
```python
def _generate_signal(self, analysis, current_price, atr):
    # ... existing checks

    if signal_type == SignalType.NO_SIGNAL:
        signal_type, direction, conf, reasons = self._check_my_signal(
            market_structure, order_flow, indicators
        )
```

### Pattern 3: Adding Configuration Options

1. **Add to config class** (config.py)
```python
@dataclass
class StrategyConfig:
    # ... existing
    my_option: float = 1.0
    enable_my_feature: bool = True
```

2. **Use in relevant module**
```python
def my_method(self):
    if self.config.strategy.enable_my_feature:
        value = self.config.strategy.my_option
        # Use value
```

### Pattern 4: Adding Market Data Type

1. **Define structure** (config.py)
```python
@dataclass
class MyDataType:
    timestamp: datetime
    value: float
```

2. **Add to DataHandler** (main.py)
```python
class DataHandler:
    def __init__(self):
        # ... existing
        self.my_data: List[MyDataType] = []

    def add_my_data(self, data: MyDataType):
        self.my_data.append(data)
```

3. **Use in analysis**
```python
def analyze(self, ..., my_data=None):
    if my_data:
        # Process my_data
```

## Quality Standards

### Code Style

```python
# Good
def calculate_rsi(
    self,
    data: Optional[List[float]] = None,
    period: Optional[int] = None
) -> RSIData:
    """
    Calculate Relative Strength Index.

    Args:
        data: Price data. Uses internal history if not provided.
        period: RSI period. Uses config default if not provided.

    Returns:
        RSIData with calculated values.
    """
    period = period or self.config.rsi_period

    if data is None:
        data = list(self._close_history)

    # Implementation...
```

### Error Handling

```python
# Good
def analyze(self, candles, current_price, atr):
    if not candles:
        return AnalysisResult(
            timestamp=datetime.now(),
            notes=["No candle data provided"],
        )

    try:
        result = self._perform_analysis(candles, current_price, atr)
    except ValueError as e:
        self.logger.error(f"Analysis error: {e}")
        return AnalysisResult(
            timestamp=datetime.now(),
            notes=[f"Analysis failed: {str(e)}"],
        )

    return result
```

### Documentation

```python
# Every public method should have:
def my_method(self, param1: str, param2: int = 10) -> Result:
    """
    Brief one-line description.

    Longer description if needed explaining what the method does,
    any important behavior, and usage notes.

    Args:
        param1: Description of param1.
        param2: Description of param2. Defaults to 10.

    Returns:
        Description of return value.

    Raises:
        ValueError: When param1 is empty.

    Example:
        >>> result = obj.my_method("test", 20)
        >>> print(result.value)
    """
```

## Testing Strategies

### Unit Testing

```python
# Test individual components
def test_rsi_calculation():
    indicators = TechnicalIndicators()

    # Known data with expected result
    data = [44, 44.34, 44.09, 43.61, 44.33, 44.83, 45.10,
            45.42, 45.84, 46.08, 45.89, 46.03, 45.61, 46.28]

    for price in data:
        indicators._close_history.append(price)

    rsi = indicators.calculate_rsi()

    # RSI should be around 70 for this uptrend
    assert 65 < rsi.value < 75
```

### Integration Testing

```python
# Test component interaction
def test_signal_generation():
    bot = TradingBot(get_default_config())

    # Generate trending data
    candles = generate_trending_data(100, trend="up")
    bot.process_market_data(candles=candles)

    analysis = bot.analyze()

    # Should detect bullish conditions
    assert analysis.market_structure.trend == TrendDirection.BULLISH
```

### Scenario Testing

```python
# Test specific scenarios
def test_breakout_detection():
    candles = generate_breakout_scenario()

    strategy = StrategyEngine()
    for candle in candles:
        strategy.indicators.update(candle)

    analysis = strategy.analyze(
        candles=candles,
        current_price=candles[-1].close,
    )

    # Should detect breakout
    assert analysis.market_structure.is_breakout
    assert analysis.signal.signal_type in [
        SignalType.BREAKOUT_LONG,
        SignalType.BREAKOUT_SHORT
    ]
```

## Performance Considerations

### Memory Management

```python
# Use deques for bounded history
from collections import deque

self._history = deque(maxlen=500)  # Auto-trim
```

### Calculation Efficiency

```python
# Cache expensive calculations
def calculate_all(self):
    if self._cache_valid:
        return self._cached_result

    result = self._do_calculation()
    self._cached_result = result
    self._cache_valid = True
    return result

def update(self, candle):
    self._cache_valid = False  # Invalidate on update
```

### Lazy Evaluation

```python
# Only calculate when needed
@property
def expensive_value(self):
    if self._expensive_value is None:
        self._expensive_value = self._calculate_expensive()
    return self._expensive_value
```

## Deployment Checklist

### Before Production

- [ ] All tests passing
- [ ] Configuration reviewed
- [ ] Risk limits appropriate
- [ ] Logging configured
- [ ] Error handling complete
- [ ] Documentation updated

### Monitoring

- [ ] Health checks in place
- [ ] Performance metrics tracked
- [ ] Error alerting configured
- [ ] Position reconciliation
- [ ] Daily P&L reporting

## Resources

### Internal Documentation
- README.md - Overview
- QUICK_START.md - Quick setup
- IMPLEMENTATION_GUIDE.md - Deep dive
- SETUP_SUMMARY.md - File reference

### Code Reference
- config.py - All data structures
- example_usage.py - Working examples
- Each module's docstrings

### Getting Help
1. Check documentation
2. Review examples
3. Use interactive session
4. Ask Claude with context
