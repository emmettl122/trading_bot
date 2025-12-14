# CLAUDE.md - AMT Trading Bot Development Guide

## Project Overview

This is an **Auction Market Theory (AMT) Trading Bot** - a production-ready algorithmic trading system that generates trading signals based on market structure analysis, order flow, and technical indicators. The bot sends webhook signals to TradingView for paper trading execution.

**Key Characteristics:**
- Pure Python 3.8+ with zero external dependencies (standard library only)
- Webhook-based architecture for TradingView integration
- Paper trading mode for signal validation
- Modular, configuration-driven design

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      TradingBot (main.py)                   │
│                    Application Orchestrator                  │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                   StrategyEngine (strategy.py)              │
│                Signal Generation & Confluence                │
└───┬─────────────┬─────────────┬─────────────┬───────────────┘
    │             │             │             │
┌───▼───┐   ┌─────▼─────┐  ┌────▼────┐  ┌────▼────┐
│Market │   │ OrderFlow │  │Technical│  │Correlat.│
│Struct.│   │ Analyzer  │  │Indicator│  │Analyzer │
└───────┘   └───────────┘  └─────────┘  └─────────┘

                          │
┌─────────────────────────▼───────────────────────────────────┐
│                 Signal → Webhook Pipeline                    │
│  Signal → TradingViewWebhook → WebhookDispatcher → TV       │
└─────────────────────────────────────────────────────────────┘
```

## File Structure

```
/home/emmett/trading_bot/
├── config.py              # Foundation: ALL data structures, enums, configs
├── main.py                # Bot orchestrator, DataHandler, session management
├── strategy.py            # Signal generation, confluence scoring
├── market_structure.py    # AMT analysis: TPO, FVA, POC, volume profile
├── order_flow.py          # Delta, order book, absorption detection
├── correlation_analysis.py # Mag7, VIX, market breadth
├── indicators.py          # RSI, MACD, Bollinger, ATR, Stochastic
├── risk_management.py     # Position sizing, trade validation, limits
├── signal.py              # Standardized webhook signal format
├── tradingview_webhook.py # TV payload translation
├── webhook_dispatcher.py  # HTTP dispatch with retry logic
├── claude_interactive.py  # Interactive CLI for exploration
├── example_usage.py       # Comprehensive examples (8 scenarios)
└── pinescript/
    └── amt_webhook_strategy.pine  # TradingView strategy script
```

## Core Conventions

### Data Structures

**Always use dataclasses** for data structures. Define them in `config.py`:

```python
@dataclass
class NewDataType:
    """Brief description of the data type."""
    required_field: float
    optional_field: str = "default"
    list_field: List[float] = field(default_factory=list)

    @property
    def computed_value(self) -> float:
        """Computed property with docstring."""
        return self.required_field * 2

    def helper_method(self, param: float) -> bool:
        """Method with type hints and docstring."""
        return self.required_field > param
```

### Enumerations

Use `Enum` with `auto()` for type-safe constants:

```python
class NewEnumType(Enum):
    """Enum description."""
    OPTION_ONE = auto()
    OPTION_TWO = auto()

    def __str__(self) -> str:
        return self.name.replace('_', ' ').title()
```

### Analyzer Pattern

New analyzers should follow this pattern:

```python
class NewAnalyzer:
    """
    Analyzer description.

    This analyzer provides:
    - Feature 1
    - Feature 2
    """

    def __init__(self, config: Optional[NewConfig] = None):
        """Initialize with optional config, use defaults if not provided."""
        self.config = config or NewConfig()
        self._history: deque = deque(maxlen=self.config.history_length)

    def analyze(self, data: OHLCV) -> NewAnalysisResult:
        """
        Main analysis method.

        Args:
            data: OHLCV candle data

        Returns:
            NewAnalysisResult with analysis output
        """
        # Implementation
        pass

    def _helper_method(self, value: float) -> float:
        """Private helper with underscore prefix."""
        pass
```

### Naming Conventions

| Element | Convention | Example |
|---------|------------|---------|
| Modules | snake_case | `market_structure.py` |
| Classes | PascalCase | `MarketStructureAnalyzer` |
| Functions | snake_case | `calculate_tpo_profile()` |
| Constants | UPPER_CASE | `VALID_TIMEFRAMES` |
| Private | _underscore | `_price_history` |
| Enums | PascalCase.UPPER | `SignalType.BREAKOUT_LONG` |

### Type Hints

**Required** for all public APIs:

```python
def process_signal(
    signal: TradingSignal,
    config: Optional[StrategyConfig] = None,
    validate: bool = True
) -> Tuple[bool, str]:
    """Process with full type hints."""
    pass
```

### Docstrings

Use Google-style docstrings:

```python
def complex_function(data: List[OHLCV], threshold: float = 0.5) -> AnalysisResult:
    """
    Brief description of function purpose.

    Longer description if needed explaining the algorithm
    or important details.

    Args:
        data: List of OHLCV candles for analysis
        threshold: Sensitivity threshold (0.0-1.0)

    Returns:
        AnalysisResult containing the computed values

    Raises:
        ValueError: If threshold is out of range

    Example:
        >>> result = complex_function(candles, threshold=0.7)
        >>> print(result.score)
        0.85
    """
    pass
```

## Development Rules

### DO

- **Read before modifying** - Always read existing code before making changes
- **Use config.py** - All data structures belong in config.py
- **Follow existing patterns** - Match the analyzer/dataclass patterns already in use
- **Add type hints** - Every public function needs complete type annotations
- **Write docstrings** - Document all public APIs with Google-style docstrings
- **Use deque for history** - Bounded memory with `deque(maxlen=X)`
- **Return dataclasses** - Analysis methods return typed dataclass results
- **Configuration injection** - Pass config objects, use defaults when None

### DON'T

- **No external dependencies** - Use only Python standard library
- **No pandas/numpy** - Implement calculations directly
- **No unnecessary abstractions** - Keep it simple, avoid over-engineering
- **No hardcoded values** - Use config objects for tuneable parameters
- **No print statements** - Use `logging` module for output
- **No global state** - Pass state through method parameters

### Code Quality

- Avoid backwards-compatibility hacks - delete unused code completely
- No placeholder comments like `# removed` or `# deprecated`
- Keep functions focused - single responsibility principle
- Prefer explicit over implicit - clear is better than clever

## Key Files Reference

### config.py (Foundation)

Contains ALL data structures. Key types:
- **Enums**: `SignalType`, `MarketCondition`, `TrendDirection`, `PositionSide`, `BotMode`
- **Market Data**: `OHLCV`, `TickData`, `OrderBook`
- **Analysis**: `FairValueArea`, `TPOProfile`, `VolumeProfile`, `MarketStructure`
- **Trading**: `TradingSignal`, `Trade`, `Position`, `PositionSize`
- **Configs**: `BotConfig`, `RiskConfig`, `StrategyConfig`, etc.

### signal.py (Webhook Format)

The `Signal` class is the standardized format for webhook transmission:
```python
Signal(
    symbol="SPY",
    side="LONG",
    entry=450.00,
    stop=448.00,
    target1=452.00,
    target2=454.00,
    confidence=0.85,
    signal_type="BREAKOUT"
)
```

### main.py (Bot Entry Point)

`TradingBot` class orchestrates everything:
- `DataHandler` manages market data
- Session management and logging
- Paper trading execution loop
- Trade history and P&L tracking

## Common Tasks

### Adding a New Indicator

1. Add config dataclass to `config.py`:
   ```python
   @dataclass
   class NewIndicatorConfig:
       period: int = 14
       threshold: float = 0.5
   ```

2. Add result dataclass to `config.py`:
   ```python
   @dataclass
   class NewIndicatorData:
       value: float
       signal: str
   ```

3. Implement in `indicators.py` following the analyzer pattern

4. Integrate into `StrategyEngine.analyze()` if needed

### Adding a New Signal Type

1. Add to `SignalType` enum in `config.py`
2. Add detection logic in appropriate analyzer
3. Update `StrategyEngine._generate_signals()` in `strategy.py`
4. Update webhook payload handling if needed

### Modifying Risk Parameters

All risk settings are in `RiskConfig` dataclass in `config.py`:
- `max_position_size_pct` - Max position as % of account
- `max_daily_loss_pct` - Daily loss limit
- `default_stop_atr_multiple` - Stop loss distance in ATR

## Testing

Run examples to verify changes:
```bash
python example_usage.py
```

Interactive exploration:
```bash
python claude_interactive.py
```

## Signal Types

The bot generates three primary signal types:
1. **BREAKOUT** - Price breaks through value area with volume confirmation
2. **REJECTION** - Price rejects at value area boundary
3. **DIVERGENCE** - Price/indicator divergence at key levels

Each has LONG and SHORT variants: `BREAKOUT_LONG`, `BREAKOUT_SHORT`, etc.

## Confluence Scoring

Signals require confluence from multiple factors:
- Market structure (AMT analysis)
- Order flow (delta, absorption)
- Technical indicators (RSI, MACD)
- Correlation (Mag7, VIX)
- Risk validation

Minimum confluence threshold is configurable in `StrategyConfig.min_confluence_score`.

## PineScript Integration

The `pinescript/amt_webhook_strategy.pine` receives JSON webhooks:
```json
{
    "symbol": "SPY",
    "side": "LONG",
    "entry": 450.00,
    "stop": 448.00,
    "target": 452.00,
    "confidence": 0.85
}
```

Modify `TradingViewWebhook` class in `tradingview_webhook.py` to change payload format.
