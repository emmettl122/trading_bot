"""
Standardized Signal Module for TradingView Webhook Compatibility.

This module provides a simplified, standardized signal format designed
for external consumption via webhooks (e.g., TradingView alerts).

The Signal class offers a clean, JSON-serializable format that can be
easily transmitted to external trading systems and webhook endpoints.

Author: AMT Trading Bot
Version: 1.0.0
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import json


@dataclass
class Signal:
    """
    Standardized trading signal for external webhook consumption.

    This class provides a simplified, JSON-serializable format suitable
    for TradingView webhooks and other external integrations. It contains
    all necessary information for executing a trade externally.

    Attributes:
        symbol: Trading symbol (e.g., "SPY", "AAPL", "ES").
        timeframe: Timeframe string (e.g., "1m", "5m", "15m", "1h", "1d").
        side: Trade direction - must be "LONG" or "SHORT".
        entry_price: Suggested entry price for the trade.
        stop_loss: Stop loss price level.
        targets: List of 2-3 take profit levels for scaling out positions.
        signal_type: Type of signal - "BREAKOUT", "REJECTION", or "DIVERGENCE".
        confidence: Confidence score from 0.0 to 1.0 (normalized).
        timestamp: UTC ISO format timestamp string (e.g., "2024-12-13T14:30:00+00:00").

    Example:
        >>> signal = Signal(
        ...     symbol="SPY",
        ...     timeframe="15m",
        ...     side="LONG",
        ...     entry_price=450.25,
        ...     stop_loss=447.50,
        ...     targets=[452.38, 454.50, 456.63],
        ...     signal_type="BREAKOUT",
        ...     confidence=0.75,
        ...     timestamp="2024-12-13T14:30:00+00:00"
        ... )
        >>> print(signal.to_json())
    """

    symbol: str
    timeframe: str
    side: str  # "LONG" | "SHORT"
    entry_price: float
    stop_loss: float
    targets: List[float]
    signal_type: str  # "BREAKOUT" | "REJECTION" | "DIVERGENCE"
    confidence: float  # 0.0 to 1.0
    timestamp: str  # UTC ISO format

    def __post_init__(self) -> None:
        """
        Validate signal data after initialization.

        Raises:
            ValueError: If any field contains invalid data.
        """
        # Validate side
        valid_sides = ("LONG", "SHORT")
        if self.side not in valid_sides:
            raise ValueError(
                f"side must be one of {valid_sides}, got '{self.side}'"
            )

        # Validate signal_type
        valid_types = ("BREAKOUT", "REJECTION", "DIVERGENCE")
        if self.signal_type not in valid_types:
            raise ValueError(
                f"signal_type must be one of {valid_types}, got '{self.signal_type}'"
            )

        # Validate confidence range
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"confidence must be between 0.0 and 1.0, got {self.confidence}"
            )

        # Validate targets list
        if not self.targets or len(self.targets) < 2:
            raise ValueError(
                f"targets must contain at least 2 price levels, got {len(self.targets) if self.targets else 0}"
            )

        # Validate price levels are positive
        if self.entry_price <= 0:
            raise ValueError(f"entry_price must be positive, got {self.entry_price}")

        if self.stop_loss <= 0:
            raise ValueError(f"stop_loss must be positive, got {self.stop_loss}")

        for i, target in enumerate(self.targets):
            if target <= 0:
                raise ValueError(f"targets[{i}] must be positive, got {target}")

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert Signal to dictionary for JSON serialization.

        Returns:
            Dictionary representation of the Signal with all fields.

        Example:
            >>> signal.to_dict()
            {'symbol': 'SPY', 'timeframe': '15m', 'side': 'LONG', ...}
        """
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "side": self.side,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "targets": self.targets,
            "signal_type": self.signal_type,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
        }

    def to_json(self, indent: Optional[int] = None) -> str:
        """
        Convert Signal to JSON string for webhook transmission.

        Args:
            indent: Optional indentation level for pretty printing.
                   Use None for compact output, 2 for readable output.

        Returns:
            JSON string representation suitable for webhook payloads.

        Example:
            >>> print(signal.to_json(indent=2))
            {
              "symbol": "SPY",
              "timeframe": "15m",
              ...
            }
        """
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Signal":
        """
        Create Signal from dictionary.

        Args:
            data: Dictionary containing all required signal fields.

        Returns:
            Signal instance constructed from the dictionary.

        Raises:
            KeyError: If required fields are missing.
            ValueError: If field values are invalid.

        Example:
            >>> data = {"symbol": "SPY", "side": "LONG", ...}
            >>> signal = Signal.from_dict(data)
        """
        return cls(
            symbol=data["symbol"],
            timeframe=data["timeframe"],
            side=data["side"],
            entry_price=data["entry_price"],
            stop_loss=data["stop_loss"],
            targets=data["targets"],
            signal_type=data["signal_type"],
            confidence=data["confidence"],
            timestamp=data["timestamp"],
        )

    @classmethod
    def from_json(cls, json_str: str) -> "Signal":
        """
        Create Signal from JSON string.

        Args:
            json_str: JSON string containing signal data.

        Returns:
            Signal instance constructed from the JSON.

        Raises:
            json.JSONDecodeError: If JSON is malformed.
            KeyError: If required fields are missing.
            ValueError: If field values are invalid.

        Example:
            >>> json_str = '{"symbol": "SPY", "side": "LONG", ...}'
            >>> signal = Signal.from_json(json_str)
        """
        return cls.from_dict(json.loads(json_str))

    @property
    def risk_reward_ratio(self) -> float:
        """
        Calculate risk-reward ratio using the first target.

        The R:R ratio is calculated as the potential reward (distance
        to first target) divided by the risk (distance to stop loss).

        Returns:
            Risk-reward ratio as a float. Returns 0.0 if risk is zero.

        Example:
            >>> signal.risk_reward_ratio
            2.5
        """
        risk = abs(self.entry_price - self.stop_loss)
        if risk == 0:
            return 0.0
        reward = abs(self.targets[0] - self.entry_price)
        return reward / risk

    @property
    def is_long(self) -> bool:
        """
        Check if this is a long signal.

        Returns:
            True if side is "LONG", False otherwise.
        """
        return self.side == "LONG"

    @property
    def is_short(self) -> bool:
        """
        Check if this is a short signal.

        Returns:
            True if side is "SHORT", False otherwise.
        """
        return self.side == "SHORT"

    def __str__(self) -> str:
        """
        Return human-readable string representation.

        Returns:
            Formatted string describing the signal.
        """
        return (
            f"Signal({self.signal_type} {self.side} {self.symbol} "
            f"@ {self.entry_price:.2f}, SL: {self.stop_loss:.2f}, "
            f"TP: {self.targets}, conf: {self.confidence:.1%})"
        )

    def __repr__(self) -> str:
        """
        Return detailed representation for debugging.

        Returns:
            Full constructor representation.
        """
        return (
            f"Signal(symbol={self.symbol!r}, timeframe={self.timeframe!r}, "
            f"side={self.side!r}, entry_price={self.entry_price}, "
            f"stop_loss={self.stop_loss}, targets={self.targets}, "
            f"signal_type={self.signal_type!r}, confidence={self.confidence}, "
            f"timestamp={self.timestamp!r})"
        )


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = ['Signal']
