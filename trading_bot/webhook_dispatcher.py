"""
TradingView Webhook Dispatcher.

This module handles the actual HTTP dispatch of webhook payloads
to TradingView or other webhook endpoints.

Features:
- Timeout protection
- Retry logic with exponential backoff
- Dry run mode for safe testing
- Comprehensive logging

Author: AMT Trading Bot
Version: 1.0.0
"""

import logging
import time
import json
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
from enum import Enum
import urllib.request
import urllib.error

from config import WebhookConfig, BotConfig, BotMode, get_default_config
from signal import Signal
from tradingview_webhook import (
    signal_to_tradingview_payload,
    validate_tradingview_payload,
    TradingViewPayload,
    TargetSelection,
)


# =============================================================================
# LOGGING SETUP
# =============================================================================

logger = logging.getLogger("AMTBot.WebhookDispatcher")


# =============================================================================
# RESULT TYPES
# =============================================================================

class DispatchStatus(Enum):
    """Status of a webhook dispatch attempt."""
    SUCCESS = "success"
    DRY_RUN = "dry_run"
    FAILED = "failed"
    NOT_CONFIGURED = "not_configured"
    VALIDATION_ERROR = "validation_error"
    TIMEOUT = "timeout"
    RETRIES_EXHAUSTED = "retries_exhausted"
    MODE_BLOCKED = "mode_blocked"  # Blocked by BotMode


@dataclass
class DispatchResult:
    """
    Result of a webhook dispatch attempt.

    Attributes:
        status: The dispatch status.
        payload: The payload that was sent (or would have been sent).
        response_code: HTTP response code (if applicable).
        response_body: HTTP response body (if applicable).
        error_message: Error message (if failed).
        attempts: Number of attempts made.
        timestamp: When the dispatch was attempted.
        duration_ms: Total time taken in milliseconds.
    """
    status: DispatchStatus
    payload: Optional[Dict[str, Any]] = None
    response_code: Optional[int] = None
    response_body: Optional[str] = None
    error_message: Optional[str] = None
    attempts: int = 1
    timestamp: datetime = field(default_factory=datetime.now)
    duration_ms: float = 0.0

    def is_success(self) -> bool:
        """Check if dispatch was successful (including dry run)."""
        return self.status in (DispatchStatus.SUCCESS, DispatchStatus.DRY_RUN)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "status": self.status.value,
            "payload": self.payload,
            "response_code": self.response_code,
            "error_message": self.error_message,
            "attempts": self.attempts,
            "timestamp": self.timestamp.isoformat(),
            "duration_ms": self.duration_ms,
        }


# =============================================================================
# WEBHOOK DISPATCHER
# =============================================================================

class WebhookDispatcher:
    """
    Dispatches webhook payloads to TradingView or other endpoints.

    This class handles the HTTP communication with retry logic,
    timeout protection, and comprehensive error handling.

    Webhook dispatch is gated by BotMode:
    - ANALYSIS_ONLY: All dispatches are blocked
    - TRADINGVIEW_PAPER: Dispatches are allowed

    Attributes:
        config: Webhook configuration.
        mode: Current bot execution mode.
        dispatch_history: List of recent dispatch results.
    """

    def __init__(
        self,
        config: Optional[WebhookConfig] = None,
        mode: BotMode = BotMode.ANALYSIS_ONLY
    ):
        """
        Initialize the Webhook Dispatcher.

        Args:
            config: Optional webhook configuration.
                   Uses default from BotConfig if not provided.
            mode: Bot execution mode. Default is ANALYSIS_ONLY (safest).
        """
        if config is None:
            bot_config = get_default_config()
            config = bot_config.webhook

        self.config = config
        self._mode = mode
        self.dispatch_history: list = []
        self._max_history = 100

        logger.info(
            f"WebhookDispatcher initialized: "
            f"mode={mode.value}, "
            f"dry_run={config.dry_run}, "
            f"configured={config.is_configured()}, "
            f"timeout={config.timeout_seconds}s, "
            f"max_retries={config.max_retries}"
        )

    @property
    def mode(self) -> BotMode:
        """Get current bot mode."""
        return self._mode

    @mode.setter
    def mode(self, new_mode: BotMode):
        """Set bot mode with logging."""
        old_mode = self._mode
        self._mode = new_mode
        logger.info(f"Bot mode changed: {old_mode.value} -> {new_mode.value}")

    def set_mode(self, new_mode: BotMode):
        """
        Set the bot execution mode.

        Args:
            new_mode: The new BotMode to set.
        """
        self.mode = new_mode

    def send(
        self,
        payload: Dict[str, Any],
        validate: Optional[bool] = None
    ) -> DispatchResult:
        """
        Send a webhook payload.

        Args:
            payload: The payload dictionary to send.
            validate: Whether to validate the payload before sending.
                     Uses config.validate_payload if not specified.

        Returns:
            DispatchResult with status and details.
        """
        start_time = time.time()
        validate = validate if validate is not None else self.config.validate_payload

        logger.info(f"Dispatch requested: {payload.get('side', 'N/A')} {payload.get('symbol', 'N/A')}")

        # Check mode first - ANALYSIS_ONLY blocks all webhook dispatch
        if not self._mode.allows_webhook():
            result = DispatchResult(
                status=DispatchStatus.MODE_BLOCKED,
                payload=payload,
                error_message=f"Webhook blocked by mode: {self._mode.value}",
                duration_ms=(time.time() - start_time) * 1000,
            )
            logger.info(
                f"Dispatch blocked: mode={self._mode.value} does not allow webhooks. "
                f"Change to TRADINGVIEW_PAPER to enable dispatch."
            )
            self._record_result(result)
            return result

        # Check if configured
        if not self.config.is_configured():
            result = DispatchResult(
                status=DispatchStatus.NOT_CONFIGURED,
                payload=payload,
                error_message="Webhook URL not configured",
                duration_ms=(time.time() - start_time) * 1000,
            )
            logger.warning("Dispatch skipped: webhook URL not configured")
            self._record_result(result)
            return result

        # Validate payload if requested
        if validate:
            is_valid, error = validate_tradingview_payload(payload)
            if not is_valid:
                result = DispatchResult(
                    status=DispatchStatus.VALIDATION_ERROR,
                    payload=payload,
                    error_message=f"Payload validation failed: {error}",
                    duration_ms=(time.time() - start_time) * 1000,
                )
                logger.error(f"Dispatch failed: validation error - {error}")
                self._record_result(result)
                return result

        # Dry run mode
        if self.config.dry_run:
            result = DispatchResult(
                status=DispatchStatus.DRY_RUN,
                payload=payload,
                duration_ms=(time.time() - start_time) * 1000,
            )
            logger.info(
                f"DRY RUN: Would send to {self.config.url[:30]}... | "
                f"Payload: {json.dumps(payload)}"
            )
            self._record_result(result)
            return result

        # Actual dispatch with retries
        result = self._dispatch_with_retries(payload, start_time)
        self._record_result(result)
        return result

    def send_signal(
        self,
        signal: Signal,
        target_selection: TargetSelection = TargetSelection.FIRST
    ) -> DispatchResult:
        """
        Convert a Signal to a payload and send it.

        This is a convenience method that combines signal conversion
        and dispatch in one call.

        Args:
            signal: The Signal object to send.
            target_selection: Which target to use for the payload.

        Returns:
            DispatchResult with status and details.
        """
        logger.debug(f"Converting signal for dispatch: {signal}")

        try:
            tv_payload = signal_to_tradingview_payload(signal, target_selection)
            return self.send(tv_payload.to_dict())
        except ValueError as e:
            return DispatchResult(
                status=DispatchStatus.VALIDATION_ERROR,
                error_message=f"Signal conversion failed: {e}",
            )

    def _dispatch_with_retries(
        self,
        payload: Dict[str, Any],
        start_time: float
    ) -> DispatchResult:
        """
        Dispatch with retry logic.

        Args:
            payload: The payload to send.
            start_time: When the dispatch started.

        Returns:
            DispatchResult with final status.
        """
        last_error = None
        delay = self.config.retry_delay_seconds

        for attempt in range(1, self.config.max_retries + 1):
            logger.debug(f"Dispatch attempt {attempt}/{self.config.max_retries}")

            try:
                response_code, response_body = self._do_http_post(payload)

                # Success (2xx response)
                if 200 <= response_code < 300:
                    result = DispatchResult(
                        status=DispatchStatus.SUCCESS,
                        payload=payload,
                        response_code=response_code,
                        response_body=response_body,
                        attempts=attempt,
                        duration_ms=(time.time() - start_time) * 1000,
                    )
                    logger.info(
                        f"Dispatch successful: HTTP {response_code} "
                        f"(attempt {attempt}, {result.duration_ms:.0f}ms)"
                    )
                    return result

                # Non-success response
                last_error = f"HTTP {response_code}: {response_body}"
                logger.warning(f"Dispatch attempt {attempt} failed: {last_error}")

            except urllib.error.URLError as e:
                if "timed out" in str(e).lower():
                    last_error = f"Timeout after {self.config.timeout_seconds}s"
                    logger.warning(f"Dispatch attempt {attempt} timed out")
                else:
                    last_error = f"Network error: {e}"
                    logger.warning(f"Dispatch attempt {attempt} network error: {e}")

            except Exception as e:
                last_error = f"Unexpected error: {e}"
                logger.error(f"Dispatch attempt {attempt} unexpected error: {e}")

            # Wait before retry (except on last attempt)
            if attempt < self.config.max_retries:
                logger.debug(f"Waiting {delay:.1f}s before retry")
                time.sleep(delay)
                delay *= self.config.retry_backoff_multiplier

        # All retries exhausted
        result = DispatchResult(
            status=DispatchStatus.RETRIES_EXHAUSTED,
            payload=payload,
            error_message=last_error,
            attempts=self.config.max_retries,
            duration_ms=(time.time() - start_time) * 1000,
        )
        logger.error(
            f"Dispatch failed after {self.config.max_retries} attempts: {last_error}"
        )
        return result

    def _do_http_post(
        self,
        payload: Dict[str, Any]
    ) -> Tuple[int, str]:
        """
        Perform the actual HTTP POST request.

        Args:
            payload: The payload to send.

        Returns:
            Tuple of (response_code, response_body).

        Raises:
            urllib.error.URLError: On network errors.
        """
        json_data = json.dumps(payload).encode('utf-8')

        request = urllib.request.Request(
            self.config.url,
            data=json_data,
            headers={
                'Content-Type': self.config.content_type,
                'User-Agent': 'AMTBot-WebhookDispatcher/1.0',
            },
            method='POST'
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=self.config.timeout_seconds
            ) as response:
                return response.status, response.read().decode('utf-8')
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode('utf-8') if e.fp else str(e)

    def _record_result(self, result: DispatchResult):
        """Record a dispatch result in history."""
        self.dispatch_history.append(result)

        # Trim history if needed
        if len(self.dispatch_history) > self._max_history:
            self.dispatch_history = self.dispatch_history[-self._max_history:]

    def get_stats(self) -> Dict[str, Any]:
        """
        Get dispatch statistics.

        Returns:
            Dictionary with dispatch statistics.
        """
        if not self.dispatch_history:
            return {
                "total_dispatches": 0,
                "success_rate": 0.0,
            }

        total = len(self.dispatch_history)
        successes = sum(1 for r in self.dispatch_history if r.is_success())
        failures = sum(
            1 for r in self.dispatch_history
            if r.status in (
                DispatchStatus.FAILED,
                DispatchStatus.RETRIES_EXHAUSTED,
                DispatchStatus.TIMEOUT
            )
        )
        dry_runs = sum(
            1 for r in self.dispatch_history
            if r.status == DispatchStatus.DRY_RUN
        )

        return {
            "total_dispatches": total,
            "successes": successes,
            "failures": failures,
            "dry_runs": dry_runs,
            "success_rate": (successes / total * 100) if total > 0 else 0.0,
            "avg_duration_ms": sum(r.duration_ms for r in self.dispatch_history) / total,
            "avg_attempts": sum(r.attempts for r in self.dispatch_history) / total,
        }

    def clear_history(self):
        """Clear dispatch history."""
        self.dispatch_history.clear()
        logger.debug("Dispatch history cleared")


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def dispatch_signal(
    signal: Signal,
    config: Optional[WebhookConfig] = None,
    mode: BotMode = BotMode.ANALYSIS_ONLY,
    target_selection: TargetSelection = TargetSelection.FIRST
) -> DispatchResult:
    """
    Convenience function to dispatch a signal.

    Creates a dispatcher, sends the signal, and returns the result.
    For repeated dispatches, create a WebhookDispatcher instance instead.

    Args:
        signal: The Signal to dispatch.
        config: Optional webhook configuration.
        mode: Bot execution mode (default: ANALYSIS_ONLY for safety).
        target_selection: Which target to use.

    Returns:
        DispatchResult with status and details.

    Example:
        >>> from signal import Signal
        >>> from config import BotMode
        >>> signal = Signal(...)
        >>> # Safe mode - will be blocked
        >>> result = dispatch_signal(signal)
        >>> # Enable dispatch
        >>> result = dispatch_signal(signal, mode=BotMode.TRADINGVIEW_PAPER)
        >>> if result.is_success():
        ...     print("Signal dispatched successfully")
    """
    dispatcher = WebhookDispatcher(config, mode=mode)
    return dispatcher.send_signal(signal, target_selection)


def dispatch_payload(
    payload: Dict[str, Any],
    config: Optional[WebhookConfig] = None,
    mode: BotMode = BotMode.ANALYSIS_ONLY
) -> DispatchResult:
    """
    Convenience function to dispatch a raw payload.

    Args:
        payload: The payload dictionary to send.
        config: Optional webhook configuration.
        mode: Bot execution mode (default: ANALYSIS_ONLY for safety).

    Returns:
        DispatchResult with status and details.
    """
    dispatcher = WebhookDispatcher(config, mode=mode)
    return dispatcher.send(payload)


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    'DispatchStatus',
    'DispatchResult',
    'WebhookDispatcher',
    'dispatch_signal',
    'dispatch_payload',
]
