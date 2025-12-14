"""
TradingView Paper Trading Bridge

This module creates a local webhook server that receives signals from the AMT Trading Bot
and executes paper trades on TradingView via browser automation.

Requirements:
    pip install playwright
    playwright install chromium

Usage:
    python tv_bridge.py

Then configure your bot to send webhooks to: http://localhost:5555/webhook

Author: AMT Trading Bot
Version: 1.0.0
"""

import json
import logging
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum
from queue import Queue
import subprocess
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class BridgeConfig:
    """Configuration for the TradingView bridge."""
    # Webhook server settings
    host: str = "localhost"
    port: int = 5555

    # TradingView settings
    tradingview_url: str = "https://www.tradingview.com/chart/"
    headless: bool = False  # Set True to run browser in background

    # Trading settings
    default_quantity: float = 1.0
    confirm_orders: bool = False  # Set True to require manual confirmation


# =============================================================================
# SIGNAL QUEUE
# =============================================================================

signal_queue: Queue = Queue()


# =============================================================================
# WEBHOOK SERVER
# =============================================================================

class WebhookHandler(BaseHTTPRequestHandler):
    """HTTP request handler for incoming webhooks."""

    def log_message(self, format, *args):
        """Override to use our logger."""
        logger.info(f"HTTP: {args[0]}")

    def do_POST(self):
        """Handle POST requests (webhooks)."""
        if self.path == "/webhook":
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')

            try:
                payload = json.loads(body)
                logger.info(f"Received signal: {payload.get('side')} {payload.get('symbol')}")

                # Add to queue for processing
                signal_queue.put(payload)

                # Send success response
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                response = {"status": "received", "message": "Signal queued for execution"}
                self.wfile.write(json.dumps(response).encode())

            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON: {e}")
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Invalid JSON"}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        """Handle GET requests (health check)."""
        if self.path == "/health":
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "running"}).encode())
        elif self.path == "/":
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            html = """
            <html>
            <head><title>AMT Trading Bridge</title></head>
            <body style="font-family: monospace; padding: 20px; background: #1a1a1a; color: #00ff00;">
                <h1>AMT TradingView Bridge</h1>
                <p>Status: <span style="color: #00ff00;">RUNNING</span></p>
                <p>Webhook endpoint: <code>http://localhost:5555/webhook</code></p>
                <p>Send POST requests with JSON payload to execute trades.</p>
                <h3>Expected Payload:</h3>
                <pre>{
    "symbol": "SPY",
    "side": "LONG" or "SHORT",
    "entry": 450.00,
    "stop": 447.00,
    "target": 453.00
}</pre>
            </body>
            </html>
            """
            self.wfile.write(html.encode())
        else:
            self.send_response(404)
            self.end_headers()


def run_webhook_server(config: BridgeConfig):
    """Run the webhook HTTP server."""
    server = HTTPServer((config.host, config.port), WebhookHandler)
    logger.info(f"Webhook server running on http://{config.host}:{config.port}")
    logger.info(f"Send signals to: http://{config.host}:{config.port}/webhook")
    server.serve_forever()


# =============================================================================
# TRADINGVIEW BROWSER AUTOMATION
# =============================================================================

class TradingViewAutomation:
    """
    Automates TradingView paper trading via browser.

    This class uses Playwright to control a browser and execute
    paper trades on TradingView.
    """

    def __init__(self, config: BridgeConfig):
        self.config = config
        self.browser = None
        self.page = None
        self.playwright = None
        self._initialized = False

    def initialize(self):
        """Initialize the browser and navigate to TradingView."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.error("Playwright not installed. Run: pip install playwright && playwright install chromium")
            return False

        logger.info("Launching browser...")
        self.playwright = sync_playwright().start()

        # Launch browser (use chromium)
        self.browser = self.playwright.chromium.launch(
            headless=self.config.headless,
            args=['--start-maximized']
        )

        # Create context and page
        context = self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            storage_state=None  # Can load saved session here
        )
        self.page = context.new_page()

        # Navigate to TradingView
        logger.info(f"Navigating to TradingView: {self.config.tradingview_url}")
        self.page.goto(self.config.tradingview_url)

        # Wait for page to load
        self.page.wait_for_load_state('networkidle')

        self._initialized = True
        logger.info("Browser initialized. Please log in to TradingView if needed.")
        logger.info("Make sure Paper Trading is connected in the Trading Panel.")

        return True

    def execute_trade(self, signal: Dict[str, Any]) -> bool:
        """
        Execute a paper trade on TradingView.

        Args:
            signal: Dictionary with trade details (side, entry, stop, target, symbol)

        Returns:
            True if trade was executed successfully
        """
        if not self._initialized:
            logger.error("Browser not initialized")
            return False

        side = signal.get('side', '').upper()
        symbol = signal.get('symbol', 'N/A')
        entry = signal.get('entry', 0)
        stop = signal.get('stop', 0)
        target = signal.get('target', 0)

        logger.info(f"Executing {side} trade for {symbol}")
        logger.info(f"  Entry: {entry}, Stop: {stop}, Target: {target}")

        try:
            # Take screenshot for debugging
            self.page.screenshot(path="/tmp/tv_before_trade.png")
            logger.info("Screenshot saved to /tmp/tv_before_trade.png")

            # Method 1: Click on chart first to ensure focus
            try:
                chart = self.page.locator('.chart-container').first
                if chart.count() > 0:
                    chart.click()
                    time.sleep(0.3)
            except:
                pass

            # Method 2: Use TradingView's DOM order panel
            # Look for the order panel buy/sell buttons with various selectors
            buy_selectors = [
                # TradingView paper trading panel buttons
                '[data-name="dom-panel-buy-button"]',
                '[class*="domPanel"] button[class*="buy"]',
                'button[class*="buyButton"]',
                'button[class*="buy-button"]',
                '[class*="orderPanel"] button:has-text("Buy")',
                '[class*="trading"] button:has-text("Buy")',
                'button:has-text("Buy / Long")',
                'button:has-text("Buy")',
                # Bottom panel buttons
                '[class*="bottom"] button[class*="buy"]',
                '[class*="widgetbar"] button:has-text("Buy")',
            ]

            sell_selectors = [
                '[data-name="dom-panel-sell-button"]',
                '[class*="domPanel"] button[class*="sell"]',
                'button[class*="sellButton"]',
                'button[class*="sell-button"]',
                '[class*="orderPanel"] button:has-text("Sell")',
                '[class*="trading"] button:has-text("Sell")',
                'button:has-text("Sell / Short")',
                'button:has-text("Sell")',
                '[class*="bottom"] button[class*="sell"]',
                '[class*="widgetbar"] button:has-text("Sell")',
            ]

            selectors = buy_selectors if side == "LONG" else sell_selectors
            action = "BUY" if side == "LONG" else "SELL"

            for selector in selectors:
                try:
                    locator = self.page.locator(selector)
                    if locator.count() > 0:
                        # Make sure element is visible
                        if locator.first.is_visible():
                            locator.first.click()
                            logger.info(f"Clicked {action} button using: {selector}")
                            time.sleep(0.5)

                            # Take screenshot after click
                            self.page.screenshot(path="/tmp/tv_after_click.png")

                            # Look for confirm/place order button
                            confirm_selectors = [
                                'button:has-text("Place Order")',
                                'button:has-text("Confirm")',
                                'button:has-text("Submit")',
                                'button[class*="submit"]',
                                'button[class*="confirm"]',
                            ]
                            for confirm in confirm_selectors:
                                try:
                                    conf_loc = self.page.locator(confirm)
                                    if conf_loc.count() > 0 and conf_loc.first.is_visible():
                                        conf_loc.first.click()
                                        logger.info("Order confirmed")
                                        break
                                except:
                                    continue

                            return True
                except Exception as e:
                    continue

            # Method 3: Try keyboard shortcuts
            # Shift+B for Buy, Shift+S for Sell in some TradingView setups
            logger.info("Trying keyboard shortcuts...")
            try:
                if side == "LONG":
                    self.page.keyboard.press("Shift+b")
                else:
                    self.page.keyboard.press("Shift+s")
                time.sleep(0.5)
                self.page.screenshot(path="/tmp/tv_after_keyboard.png")
                logger.info("Keyboard shortcut sent")
            except Exception as e:
                logger.warning(f"Keyboard shortcut failed: {e}")

            # If buttons not found, provide helpful debug info
            logger.warning("Could not find trading buttons automatically.")
            logger.warning(f"MANUAL TRADE NEEDED: {side} {symbol} @ {entry}")
            logger.warning("Check screenshots in /tmp/tv_*.png for debugging")
            logger.warning("Make sure Paper Trading panel is open and visible!")

            return False

        except Exception as e:
            logger.error(f"Error executing trade: {e}")
            return False

    def close(self):
        """Close the browser."""
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        logger.info("Browser closed")


# =============================================================================
# SIGNAL PROCESSOR
# =============================================================================

def process_signals(automation: TradingViewAutomation):
    """Process signals from the queue."""
    logger.info("Signal processor started. Waiting for signals...")

    while True:
        try:
            # Get signal from queue (blocking)
            signal = signal_queue.get()

            logger.info("=" * 50)
            logger.info("NEW SIGNAL RECEIVED")
            logger.info(f"  Side: {signal.get('side')}")
            logger.info(f"  Symbol: {signal.get('symbol')}")
            logger.info(f"  Entry: {signal.get('entry')}")
            logger.info(f"  Stop: {signal.get('stop')}")
            logger.info(f"  Target: {signal.get('target')}")
            logger.info("=" * 50)

            # Execute the trade
            success = automation.execute_trade(signal)

            if success:
                logger.info("Trade executed successfully")
            else:
                logger.warning("Trade execution failed or requires manual action")

            signal_queue.task_done()

        except Exception as e:
            logger.error(f"Error processing signal: {e}")


# =============================================================================
# SIMPLE MODE (NO BROWSER AUTOMATION)
# =============================================================================

def process_signals_simple():
    """Process signals without browser automation - just display them."""
    logger.info("Signal processor started (SIMPLE MODE - no browser automation)")
    logger.info("Signals will be displayed for manual execution.")

    while True:
        try:
            signal = signal_queue.get()

            print("\n" + "=" * 60)
            print("  NEW TRADING SIGNAL - EXECUTE MANUALLY")
            print("=" * 60)
            print(f"  SIDE:    {signal.get('side', 'N/A')}")
            print(f"  SYMBOL:  {signal.get('symbol', 'N/A')}")
            print(f"  ENTRY:   {signal.get('entry', 'N/A')}")
            print(f"  STOP:    {signal.get('stop', 'N/A')}")
            print(f"  TARGET:  {signal.get('target', 'N/A')}")
            print(f"  CONF:    {signal.get('confidence', 'N/A')}")
            print("=" * 60 + "\n")

            signal_queue.task_done()

        except Exception as e:
            logger.error(f"Error processing signal: {e}")


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    """Main entry point for the TradingView bridge."""
    import argparse

    parser = argparse.ArgumentParser(description='AMT TradingView Paper Trading Bridge')
    parser.add_argument('--simple', action='store_true',
                        help='Run in simple mode (no browser automation)')
    parser.add_argument('--port', type=int, default=5555,
                        help='Webhook server port (default: 5555)')
    parser.add_argument('--headless', action='store_true',
                        help='Run browser in headless mode')
    parser.add_argument('--url', type=str, default='https://www.tradingview.com/chart/',
                        help='TradingView chart URL')

    args = parser.parse_args()

    config = BridgeConfig(
        port=args.port,
        headless=args.headless,
        tradingview_url=args.url
    )

    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║         AMT TradingView Paper Trading Bridge              ║
    ╠═══════════════════════════════════════════════════════════╣
    ║  Webhook URL: http://localhost:{:<5}                      ║
    ║  Endpoint:    /webhook                                    ║
    ╚═══════════════════════════════════════════════════════════╝
    """.format(config.port))

    if args.simple:
        # Simple mode - no browser automation
        logger.info("Running in SIMPLE mode (no browser automation)")

        # Start signal processor in background
        processor = threading.Thread(target=process_signals_simple, daemon=True)
        processor.start()

        # Run webhook server (blocking)
        run_webhook_server(config)

    else:
        # Full mode with browser automation
        logger.info("Running in FULL mode (with browser automation)")

        # Check for playwright
        try:
            import playwright
        except ImportError:
            print("\nPlaywright not installed. Installing now...")
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'playwright'])
            subprocess.check_call([sys.executable, '-m', 'playwright', 'install', 'chromium'])
            print("Playwright installed. Please restart the bridge.")
            return

        # Initialize browser automation
        automation = TradingViewAutomation(config)
        if not automation.initialize():
            logger.error("Failed to initialize browser. Running in simple mode instead.")
            processor = threading.Thread(target=process_signals_simple, daemon=True)
            processor.start()
            run_webhook_server(config)
            return

        # Start signal processor in background
        processor = threading.Thread(
            target=process_signals,
            args=(automation,),
            daemon=True
        )
        processor.start()

        # Run webhook server (blocking)
        try:
            run_webhook_server(config)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            automation.close()


if __name__ == "__main__":
    main()
