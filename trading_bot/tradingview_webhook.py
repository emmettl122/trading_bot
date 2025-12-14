"""
TradingView Webhook Translation Layer.

This module provides translation between the internal Signal format
and the flat JSON payload expected by TradingView webhook alerts.

TradingView expects a simple, flat JSON structure that can be parsed
by their alert system and forwarded to trading platforms.

Author: AMT Trading Bot
Version: 1.0.0
"""

import logging
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from signal import Signal


# =============================================================================
# LOGGING SETUP
# =============================================================================

logger = logging.getLogger("AMTBot.TradingViewWebhook")


# =============================================================================
# CONSTANTS
# =============================================================================

VALID_SIDES = ("LONG", "SHORT")
VALID_TIMEFRAMES = ("1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w")


class TargetSelection(Enum):
    """Strategy for selecting which target to use in the payload."""
    FIRST = "first"       # Conservative - closest target (50%)
    SECOND = "second"     # Original take profit (100%)
    THIRD = "third"       # Extended target (150%)


# =============================================================================
# PAYLOAD DATACLASS
# =============================================================================

@dataclass
class TradingViewPayload:
    """
    Flat payload structure for TradingView webhooks.

    This represents the exact JSON structure expected by TradingView
    alert webhooks. All fields are required and the structure is flat
    (no nested objects).

    Attributes:
        side: Trade direction - "LONG" or "SHORT".
        entry: Entry price for the trade.
        stop: Stop loss price.
        target: Take profit price (single target).
        symbol: Trading symbol (e.g., "SPY", "AAPL").
        timeframe: Chart timeframe (e.g., "15m", "1h").
    """
    side: str
    entry: float
    stop: float
    target: float
    symbol: str
    timeframe: str

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert payload to dictionary.

        Returns:
            Flat dictionary representation.
        """
        return {
            "side": self.side,
            "entry": self.entry,
            "stop": self.stop,
            "target": self.target,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
        }

    def to_json_str(self) -> str:
        """
        Convert payload to JSON string.

        Returns:
            JSON string suitable for webhook transmission.
        """
        import json
        return json.dumps(self.to_dict())


# =============================================================================
# TRANSLATION FUNCTIONS
# =============================================================================

def signal_to_tradingview_payload(
    signal: Signal,
    target_selection: TargetSelection = TargetSelection.FIRST
) -> TradingViewPayload:
    """
    Convert a Signal object to a TradingView-compatible flat payload.

    TradingView webhooks expect a simple flat JSON structure. This function
    translates the richer Signal format (with multiple targets) into the
    flat structure TradingView expects.

    Args:
        signal: The Signal object to convert.
        target_selection: Which target to use from the targets list.
            - FIRST: Conservative target (50% of original TP distance)
            - SECOND: Original take profit (100%)
            - THIRD: Extended target (150%)
            Defaults to FIRST for conservative risk management.

    Returns:
        TradingViewPayload ready for webhook transmission.

    Raises:
        ValueError: If signal has invalid data.

    Example:
        >>> signal = Signal(
        ...     symbol="SPY",
        ...     timeframe="15m",
        ...     side="LONG",
        ...     entry_price=450.0,
        ...     stop_loss=447.0,
        ...     targets=[452.0, 454.0, 456.0],
        ...     signal_type="BREAKOUT",
        ...     confidence=0.75,
        ...     timestamp="2024-12-13T14:30:00+00:00"
        ... )
        >>> payload = signal_to_tradingview_payload(signal)
        >>> print(payload.to_dict())
        {'side': 'LONG', 'entry': 450.0, 'stop': 447.0, 'target': 452.0, ...}
    """
    logger.debug(f"Converting Signal to TradingView payload: {signal.symbol} {signal.side}")

    # Validate signal
    if signal.side not in VALID_SIDES:
        error_msg = f"Invalid side '{signal.side}', must be one of {VALID_SIDES}"
        logger.error(error_msg)
        raise ValueError(error_msg)

    if not signal.targets or len(signal.targets) < 1:
        error_msg = "Signal must have at least one target"
        logger.error(error_msg)
        raise ValueError(error_msg)

    # Select target based on strategy
    target_index = {
        TargetSelection.FIRST: 0,
        TargetSelection.SECOND: 1,
        TargetSelection.THIRD: 2,
    }.get(target_selection, 0)

    # Fall back to last available target if index exceeds list length
    if target_index >= len(signal.targets):
        target_index = len(signal.targets) - 1
        logger.warning(
            f"Target index {target_selection.value} exceeds available targets, "
            f"using target {target_index + 1} instead"
        )

    selected_target = signal.targets[target_index]

    logger.info(
        f"Translating Signal: {signal.side} {signal.symbol} @ {signal.entry_price:.2f}, "
        f"target={selected_target:.2f} ({target_selection.value})"
    )

    payload = TradingViewPayload(
        side=signal.side,
        entry=signal.entry_price,
        stop=signal.stop_loss,
        target=selected_target,
        symbol=signal.symbol,
        timeframe=signal.timeframe,
    )

    logger.debug(f"Created payload: {payload.to_dict()}")

    return payload


def validate_tradingview_payload(
    payload: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Validate a TradingView webhook payload.

    Checks that the payload has all required fields with valid values.
    This is useful for validating payloads before transmission or
    for validating incoming payloads from external sources.

    Args:
        payload: Dictionary containing the webhook payload.

    Returns:
        Tuple of (is_valid, error_message).
        If valid, returns (True, None).
        If invalid, returns (False, "error description").

    Example:
        >>> payload = {"side": "LONG", "entry": 450.0, ...}
        >>> is_valid, error = validate_tradingview_payload(payload)
        >>> if not is_valid:
        ...     print(f"Invalid payload: {error}")
    """
    logger.debug(f"Validating payload: {payload}")

    # Required fields
    required_fields = ["side", "entry", "stop", "target", "symbol", "timeframe"]

    # Check for missing fields
    missing_fields = [f for f in required_fields if f not in payload]
    if missing_fields:
        error_msg = f"Missing required fields: {missing_fields}"
        logger.warning(f"Payload validation failed: {error_msg}")
        return False, error_msg

    # Validate side
    side = payload.get("side")
    if side not in VALID_SIDES:
        error_msg = f"Invalid side '{side}', must be one of {VALID_SIDES}"
        logger.warning(f"Payload validation failed: {error_msg}")
        return False, error_msg

    # Validate numeric fields
    numeric_fields = ["entry", "stop", "target"]
    for field in numeric_fields:
        value = payload.get(field)
        if not isinstance(value, (int, float)):
            error_msg = f"Field '{field}' must be numeric, got {type(value).__name__}"
            logger.warning(f"Payload validation failed: {error_msg}")
            return False, error_msg
        if value <= 0:
            error_msg = f"Field '{field}' must be positive, got {value}"
            logger.warning(f"Payload validation failed: {error_msg}")
            return False, error_msg

    # Validate symbol
    symbol = payload.get("symbol")
    if not isinstance(symbol, str) or not symbol.strip():
        error_msg = "Field 'symbol' must be a non-empty string"
        logger.warning(f"Payload validation failed: {error_msg}")
        return False, error_msg

    # Validate timeframe
    timeframe = payload.get("timeframe")
    if not isinstance(timeframe, str) or not timeframe.strip():
        error_msg = "Field 'timeframe' must be a non-empty string"
        logger.warning(f"Payload validation failed: {error_msg}")
        return False, error_msg

    # Validate price relationships
    entry = payload["entry"]
    stop = payload["stop"]
    target = payload["target"]

    if side == "LONG":
        if stop >= entry:
            error_msg = f"LONG: stop ({stop}) must be below entry ({entry})"
            logger.warning(f"Payload validation failed: {error_msg}")
            return False, error_msg
        if target <= entry:
            error_msg = f"LONG: target ({target}) must be above entry ({entry})"
            logger.warning(f"Payload validation failed: {error_msg}")
            return False, error_msg
    else:  # SHORT
        if stop <= entry:
            error_msg = f"SHORT: stop ({stop}) must be above entry ({entry})"
            logger.warning(f"Payload validation failed: {error_msg}")
            return False, error_msg
        if target >= entry:
            error_msg = f"SHORT: target ({target}) must be below entry ({entry})"
            logger.warning(f"Payload validation failed: {error_msg}")
            return False, error_msg

    logger.debug("Payload validation successful")
    return True, None


def payload_from_dict(data: Dict[str, Any]) -> TradingViewPayload:
    """
    Create a TradingViewPayload from a dictionary.

    Args:
        data: Dictionary with payload fields.

    Returns:
        TradingViewPayload instance.

    Raises:
        ValueError: If validation fails.
    """
    is_valid, error = validate_tradingview_payload(data)
    if not is_valid:
        raise ValueError(f"Invalid payload: {error}")

    return TradingViewPayload(
        side=data["side"],
        entry=float(data["entry"]),
        stop=float(data["stop"]),
        target=float(data["target"]),
        symbol=str(data["symbol"]),
        timeframe=str(data["timeframe"]),
    )


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def signal_to_json(
    signal: Signal,
    target_selection: TargetSelection = TargetSelection.FIRST
) -> str:
    """
    Convert a Signal directly to a JSON string for TradingView.

    This is a convenience function that combines signal_to_tradingview_payload
    and JSON serialization.

    Args:
        signal: The Signal object to convert.
        target_selection: Which target to use (FIRST, SECOND, or THIRD).

    Returns:
        JSON string ready for webhook transmission.

    Example:
        >>> json_str = signal_to_json(signal)
        >>> print(json_str)
        {"side": "LONG", "entry": 450.0, ...}
    """
    payload = signal_to_tradingview_payload(signal, target_selection)
    return payload.to_json_str()


def calculate_risk_reward(payload: Dict[str, Any]) -> Optional[float]:
    """
    Calculate the risk-reward ratio from a payload.

    Args:
        payload: TradingView payload dictionary.

    Returns:
        Risk-reward ratio as float, or None if calculation fails.
    """
    try:
        entry = payload["entry"]
        stop = payload["stop"]
        target = payload["target"]

        risk = abs(entry - stop)
        reward = abs(target - entry)

        if risk == 0:
            return None

        return reward / risk
    except (KeyError, TypeError, ZeroDivisionError):
        return None


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    'TradingViewPayload',
    'TargetSelection',
    'signal_to_tradingview_payload',
    'validate_tradingview_payload',
    'payload_from_dict',
    'signal_to_json',
    'calculate_risk_reward',
]
