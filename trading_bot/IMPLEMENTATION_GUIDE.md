# Implementation Guide

Advanced usage and customization guide for the AMT Trading Bot.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Component Deep Dive](#component-deep-dive)
3. [Customization Guide](#customization-guide)
4. [Real Data Integration](#real-data-integration)
5. [Strategy Development](#strategy-development)
6. [Performance Optimization](#performance-optimization)
7. [Testing](#testing)
8. [Deployment](#deployment)

## Architecture Overview

### Component Flow

```
Market Data → DataHandler → TradingBot
                               ↓
                         StrategyEngine
                               ↓
    ┌──────────────────────────┼──────────────────────────┐
    ↓                          ↓                          ↓
MarketStructure          OrderFlow              Correlation
Analyzer                 Analyzer               Analyzer
    ↓                          ↓                          ↓
    └──────────────────────────┼──────────────────────────┘
                               ↓
                      Technical Indicators
                               ↓
                      Signal Generation
                               ↓
                       RiskManager
                               ↓
                    Trade Execution (Paper)
```

### Module Responsibilities

| Module | Responsibility |
|--------|----------------|
| config.py | All data structures and configuration |
| market_structure.py | AMT analysis (TPO, FVA, breakouts) |
| order_flow.py | Volume and delta analysis |
| correlation_analysis.py | Market context analysis |
| indicators.py | Technical indicator calculations |
| risk_management.py | Position sizing and validation |
| strategy.py | Signal generation orchestration |
| main.py | Bot application and execution |

## Component Deep Dive

### Market Structure Analyzer

The core AMT analysis component:

```python
from market_structure import MarketStructureAnalyzer
from config import OHLCV

# Create analyzer
analyzer = MarketStructureAnalyzer()

# Analyze market structure
structure = analyzer.analyze(
    candles=candles,
    current_price=450.0,
    atr=2.5,
    avg_volume=250000,
)

# Access components
print(f"Fair Value Area: {structure.fva.val} - {structure.fva.vah}")
print(f"POC: {structure.fva.poc}")
print(f"Condition: {structure.condition.name}")
print(f"Trend: {structure.trend.name}")

# Check for patterns
if structure.is_breakout:
    print(f"Breakout: {structure.breakout_direction.name}")

if structure.is_rejection:
    print(f"Rejection at: {structure.rejection_level}")
```

### Order Flow Analyzer

Understanding buyer/seller activity:

```python
from order_flow import OrderFlowAnalyzer

# Create analyzer
of_analyzer = OrderFlowAnalyzer()

# Analyze order flow
analysis = of_analyzer.analyze(
    candle=current_candle,
    order_book=order_book,
    avg_volume=250000,
)

# Check results
print(f"Delta: {analysis.delta.delta:,.0f}")
print(f"Cumulative Delta: {analysis.delta.cumulative_delta:,.0f}")
print(f"Aggressive Buying: {analysis.aggressive_buying}")
print(f"Divergence: {analysis.divergence_type}")
print(f"Breakout Quality: {analysis.breakout_quality}/100")
```

### Correlation Analyzer

Market context analysis:

```python
from correlation_analysis import CorrelationAnalyzer

# Create analyzer
corr_analyzer = CorrelationAnalyzer()

# Analyze correlations
result = corr_analyzer.analyze(
    mag7_prices={'AAPL': 175, 'MSFT': 375, ...},
    index_price=450.0,
    vix_level=15.5,
    index_direction=TrendDirection.BULLISH,
    breadth_data={
        'advances': 300,
        'declines': 200,
        'new_highs': 50,
        ...
    },
)

# Check market health
print(f"Health Score: {result.market_health_score}/100")
print(f"Mag7 Confirmation: {result.mag7.confirmation_score}")
print(f"VIX Divergence: {result.vix.is_diverging}")
```

### Technical Indicators

Comprehensive indicator suite:

```python
from indicators import TechnicalIndicators

# Create calculator
indicators = TechnicalIndicators()

# Update with data
for candle in candles:
    indicators.update(candle)

# Get all indicators
indicator_set = indicators.calculate_all()

# Access specific indicators
rsi = indicator_set.rsi
macd = indicator_set.macd
bb = indicator_set.bollinger

# Check signal alignment
aligned, total, names = indicators.get_signal_alignment('bullish')
print(f"Bullish alignment: {aligned}/{total}")
```

## Customization Guide

### Custom Configuration

```python
from config import BotConfig, RiskConfig, StrategyConfig, IndicatorConfig

config = BotConfig(
    symbol="QQQ",
    paper_trading=True,
    initial_capital=50000.0,

    risk=RiskConfig(
        max_position_size_percent=3.0,
        max_daily_loss_percent=1.5,
        min_risk_reward_ratio=2.5,
        max_open_positions=3,
        use_trailing_stop=True,
        trailing_stop_atr_multiple=2.5,
    ),

    strategy=StrategyConfig(
        min_confidence=65.0,
        min_indicators_aligned=3,
        require_volume_confirmation=True,
        require_trend_alignment=True,
        enable_breakout_signals=True,
        enable_rejection_signals=True,
        enable_divergence_signals=False,  # Disable divergence
    ),

    indicators=IndicatorConfig(
        rsi_period=14,
        rsi_overbought=75.0,
        rsi_oversold=25.0,
        bb_period=20,
        bb_std_dev=2.5,
    ),
)
```

### Custom Signal Logic

Extend the strategy engine:

```python
from strategy import StrategyEngine
from config import SignalType, PositionSide, TradingSignal

class CustomStrategy(StrategyEngine):
    def _generate_signal(self, analysis, current_price, atr):
        # Call parent method first
        signal = super()._generate_signal(analysis, current_price, atr)

        # Add custom logic
        if signal.signal_type == SignalType.NO_SIGNAL:
            signal = self._check_custom_pattern(analysis, current_price, atr)

        return signal

    def _check_custom_pattern(self, analysis, current_price, atr):
        # Your custom pattern detection
        indicators = analysis.indicators

        if indicators.bollinger.squeeze and indicators.rsi.value < 40:
            return TradingSignal(
                timestamp=datetime.now(),
                symbol=self.config.symbol,
                signal_type=SignalType.BREAKOUT_LONG,
                direction=PositionSide.LONG,
                entry_price=current_price,
                stop_loss=current_price - atr * 2,
                take_profit=current_price + atr * 4,
                confidence=70.0,
                rationale="Squeeze with oversold RSI",
            )

        return None
```

### Custom Indicators

Add new indicators:

```python
from indicators import TechnicalIndicators

class ExtendedIndicators(TechnicalIndicators):
    def calculate_ichimoku(self, candles, conversion=9, base=26, span_b=52):
        """Calculate Ichimoku Cloud components."""
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]

        # Conversion Line (Tenkan-sen)
        conversion_line = (max(highs[-conversion:]) + min(lows[-conversion:])) / 2

        # Base Line (Kijun-sen)
        base_line = (max(highs[-base:]) + min(lows[-base:])) / 2

        # Leading Span A (Senkou Span A)
        span_a = (conversion_line + base_line) / 2

        # Leading Span B (Senkou Span B)
        span_b_value = (max(highs[-span_b:]) + min(lows[-span_b:])) / 2

        return {
            'conversion': conversion_line,
            'base': base_line,
            'span_a': span_a,
            'span_b': span_b_value,
        }

    def calculate_vwap_bands(self, candles, std_multiplier=2.0):
        """Calculate VWAP with standard deviation bands."""
        tp_volume = []
        volume_total = 0

        for c in candles:
            tp = (c.high + c.low + c.close) / 3
            tp_volume.append(tp * c.volume)
            volume_total += c.volume

        vwap = sum(tp_volume) / volume_total if volume_total > 0 else 0

        # Calculate standard deviation
        variance = sum((c.close - vwap) ** 2 for c in candles) / len(candles)
        std = variance ** 0.5

        return {
            'vwap': vwap,
            'upper': vwap + std * std_multiplier,
            'lower': vwap - std * std_multiplier,
        }
```

## Real Data Integration

### Broker Integration Pattern

```python
from main import DataHandler
from config import OHLCV, OrderBook, OrderBookLevel
from datetime import datetime

class BrokerDataHandler(DataHandler):
    def __init__(self, symbol, api_key, api_secret):
        super().__init__(symbol)
        self.api_key = api_key
        self.api_secret = api_secret
        self.connection = None

    def connect(self):
        """Establish broker connection."""
        # Your broker connection logic
        pass

    def subscribe_quotes(self):
        """Subscribe to real-time quotes."""
        # Set up quote subscription
        pass

    def on_quote(self, quote_data):
        """Handle incoming quote."""
        candle = OHLCV(
            timestamp=datetime.fromtimestamp(quote_data['timestamp']),
            open=quote_data['open'],
            high=quote_data['high'],
            low=quote_data['low'],
            close=quote_data['close'],
            volume=quote_data['volume'],
        )
        self.add_candle(candle)

    def on_order_book(self, book_data):
        """Handle order book update."""
        order_book = OrderBook(
            timestamp=datetime.now(),
            bids=[OrderBookLevel(p, s) for p, s in book_data['bids']],
            asks=[OrderBookLevel(p, s) for p, s in book_data['asks']],
        )
        self.update_order_book(order_book)
```

### Live Trading Extension

```python
from main import TradingBot
from config import TradingSignal, PositionSide

class LiveTradingBot(TradingBot):
    def __init__(self, config, broker_client):
        super().__init__(config)
        self.broker = broker_client

    def execute_trade(self, signal: TradingSignal):
        """Execute a live trade."""
        if not signal.position_size:
            return None

        # Place order
        if signal.direction == PositionSide.LONG:
            order = self.broker.place_order(
                symbol=signal.symbol,
                side='buy',
                quantity=signal.position_size.shares,
                order_type='market',
            )
        else:
            order = self.broker.place_order(
                symbol=signal.symbol,
                side='sell',
                quantity=signal.position_size.shares,
                order_type='market',
            )

        # Set stops
        self.broker.place_stop_loss(
            symbol=signal.symbol,
            price=signal.stop_loss,
        )

        self.broker.place_take_profit(
            symbol=signal.symbol,
            price=signal.take_profit,
        )

        return order
```

## Strategy Development

### Strategy Testing Framework

```python
def backtest_strategy(strategy, candles, initial_capital=100000):
    """Simple backtesting framework."""
    results = {
        'trades': [],
        'equity_curve': [initial_capital],
        'signals': [],
    }

    # Process each candle
    for i in range(50, len(candles)):  # Need history
        window = candles[:i+1]
        current = candles[i]

        # Run analysis
        analysis = strategy.analyze(
            candles=window,
            current_price=current.close,
        )

        if analysis.signal:
            results['signals'].append({
                'timestamp': current.timestamp,
                'signal': analysis.signal.signal_type.name,
                'confidence': analysis.signal.confidence,
            })

    return results
```

### Walk-Forward Analysis

```python
def walk_forward_test(strategy_class, data, train_size=500, test_size=100):
    """Walk-forward optimization."""
    results = []

    for start in range(0, len(data) - train_size - test_size, test_size):
        train_data = data[start:start + train_size]
        test_data = data[start + train_size:start + train_size + test_size]

        # Train (optimize) strategy
        strategy = strategy_class()
        # ... optimize parameters on train_data

        # Test
        test_results = backtest_strategy(strategy, test_data)
        results.append(test_results)

    return results
```

## Performance Optimization

### Efficient Data Handling

```python
from collections import deque

class OptimizedDataHandler:
    def __init__(self, max_candles=1000):
        # Use deque for O(1) append/pop
        self.candles = deque(maxlen=max_candles)

        # Pre-calculate common values
        self._sum_close = 0
        self._sum_volume = 0

    def add_candle(self, candle):
        if len(self.candles) == self.candles.maxlen:
            old = self.candles[0]
            self._sum_close -= old.close
            self._sum_volume -= old.volume

        self.candles.append(candle)
        self._sum_close += candle.close
        self._sum_volume += candle.volume

    @property
    def avg_close(self):
        return self._sum_close / len(self.candles) if self.candles else 0

    @property
    def avg_volume(self):
        return self._sum_volume / len(self.candles) if self.candles else 0
```

### Caching Calculations

```python
class CachedIndicators(TechnicalIndicators):
    def __init__(self, config=None):
        super().__init__(config)
        self._cache = {}
        self._cache_valid = False

    def invalidate_cache(self):
        self._cache_valid = False

    def update(self, candle):
        super().update(candle)
        self.invalidate_cache()

    def calculate_all(self, candles=None):
        if self._cache_valid and not candles:
            return self._cache['all']

        result = super().calculate_all(candles)
        self._cache['all'] = result
        self._cache_valid = True
        return result
```

## Testing

### Unit Test Example

```python
import unittest
from config import OHLCV
from market_structure import MarketStructureAnalyzer
from datetime import datetime

class TestMarketStructure(unittest.TestCase):
    def setUp(self):
        self.analyzer = MarketStructureAnalyzer()
        self.candles = self._generate_test_candles()

    def _generate_test_candles(self):
        candles = []
        price = 100.0
        for i in range(50):
            candles.append(OHLCV(
                timestamp=datetime.now(),
                open=price,
                high=price * 1.01,
                low=price * 0.99,
                close=price * 1.005,
                volume=100000,
            ))
            price = candles[-1].close
        return candles

    def test_fva_calculation(self):
        fva = self.analyzer.calculate_fair_value_area(self.candles)
        self.assertGreater(fva.vah, fva.val)
        self.assertGreater(fva.vah, fva.poc)
        self.assertLess(fva.val, fva.poc)

    def test_trend_detection(self):
        trend = self.analyzer.determine_trend(self.candles)
        self.assertIsNotNone(trend)

if __name__ == '__main__':
    unittest.main()
```

## Deployment

### Production Checklist

1. **Configuration**
   - [ ] Set `paper_trading = False`
   - [ ] Configure real broker credentials
   - [ ] Set appropriate risk limits
   - [ ] Configure logging to file

2. **Monitoring**
   - [ ] Set up error alerting
   - [ ] Configure performance monitoring
   - [ ] Set up position reconciliation

3. **Risk Controls**
   - [ ] Implement circuit breakers
   - [ ] Set maximum daily loss limits
   - [ ] Configure position size limits

4. **Recovery**
   - [ ] Implement state persistence
   - [ ] Configure auto-restart
   - [ ] Set up data backup

### Docker Deployment

```dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY . .

CMD ["python", "main.py"]
```

```yaml
# docker-compose.yml
version: '3'
services:
  trading-bot:
    build: .
    environment:
      - PAPER_TRADING=true
      - LOG_LEVEL=INFO
    volumes:
      - ./data:/app/data
    restart: unless-stopped
```
