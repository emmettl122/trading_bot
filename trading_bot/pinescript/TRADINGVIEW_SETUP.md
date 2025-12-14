# TradingView Webhook Strategy Setup Guide

This guide explains how to set up the AMT Trading Bot webhook strategy on TradingView for paper trading.

## Prerequisites

- TradingView Pro, Pro+, or Premium account (webhooks require paid plan)
- AMT Trading Bot configured with your TradingView webhook URL

---

## Step 1: Add the Strategy to TradingView

### Option A: Copy/Paste Method

1. Open TradingView and navigate to any chart (e.g., SPY on a 15-minute timeframe)
2. Click **Pine Editor** at the bottom of the screen
3. Delete any existing code in the editor
4. Copy the entire contents of `amt_webhook_strategy.pine`
5. Paste into the Pine Editor
6. Click **Save** and name it "AMT Webhook Strategy"
7. Click **Add to Chart**

### Option B: Create New Strategy

1. In Pine Editor, click **New** → **Strategy**
2. Replace all code with `amt_webhook_strategy.pine` contents
3. Save and add to chart

---

## Step 2: Configure Strategy Settings

After adding to chart, click the **gear icon** (⚙️) on the strategy to configure:

### Properties Tab
| Setting | Recommended Value | Description |
|---------|-------------------|-------------|
| Initial Capital | 100000 | Starting paper balance |
| Base Currency | USD | Account currency |
| Order Size | 100% of equity | Position sizing |
| Pyramiding | 0 | Single position only |
| Commission | $1 per order | Realistic commission |

### Inputs Tab
| Setting | Value | Description |
|---------|-------|-------------|
| Use Stop Loss | ✓ Enabled | Enable SL from webhook |
| Use Take Profit | ✓ Enabled | Enable TP from webhook |
| Use Trailing Stop | ☐ Disabled | Optional trailing stop |
| Validate Symbol Match | ☐ Disabled | Enable if using multiple charts |

---

## Step 3: Enable Paper Trading

1. Click on **Trading Panel** at the bottom of the chart
2. Select **Paper Trading** from the broker dropdown
3. Click **Connect** to enable paper trading mode
4. You should see "Paper Trading" with a simulated balance

---

## Step 4: Create Webhook Alert

### Create the Alert

1. Right-click on the chart → **Add Alert**
2. Or press `Alt + A` (Windows) / `Option + A` (Mac)

### Configure Alert Condition

| Field | Value |
|-------|-------|
| Condition | AMT Webhook Strategy |
| Trigger | Order fills only |

### Configure Webhook

1. Enable **Webhook URL** checkbox
2. Enter your webhook URL (get this from TradingView):
   - Go to **Trading Panel** → **Broker** → Your connected broker
   - Or use TradingView's paper trading webhook endpoint

### Set Alert Message (CRITICAL)

In the **Message** field, enter exactly:
```json
{
  "side": "{{strategy.order.action}}",
  "entry": {{strategy.order.price}},
  "stop": {{plot("Stop Loss")}},
  "target": {{plot("Take Profit")}},
  "symbol": "{{ticker}}",
  "timeframe": "{{interval}}"
}
```

### Alert Name
Name it: `AMT Bot Signal - {{ticker}}`

### Expiration
Set to **Open-ended** for continuous operation

---

## Step 5: Configure AMT Bot Webhook URL

### Get Your TradingView Webhook URL

For paper trading with external webhooks:
1. Your webhook URL format: `https://webhook.tradingview.com/alerts/YOUR_ALERT_ID`
2. TradingView provides this when you create an alert with webhook enabled

### Configure in AMT Bot

```python
from config import get_default_config, BotMode

config = get_default_config()
config.webhook.url = "https://webhook.tradingview.com/alerts/YOUR_ALERT_ID"
config.webhook.dry_run = False  # Enable actual HTTP calls
config.mode = BotMode.TRADINGVIEW_PAPER
```

---

## Step 6: Test the Integration

### Send a Test Signal

```python
from signal import Signal
from webhook_dispatcher import WebhookDispatcher
from config import WebhookConfig, BotMode

config = WebhookConfig(
    url="https://webhook.tradingview.com/alerts/YOUR_ALERT_ID",
    dry_run=False
)

dispatcher = WebhookDispatcher(config, mode=BotMode.TRADINGVIEW_PAPER)

# Test signal
test_signal = Signal(
    symbol="SPY",
    timeframe="15m",
    side="LONG",
    entry_price=450.00,
    stop_loss=447.00,
    targets=[453.00, 456.00, 459.00],
    signal_type="BREAKOUT",
    confidence=0.75,
    timestamp="2024-12-13T14:30:00+00:00"
)

result = dispatcher.send_signal(test_signal)
print(f"Result: {result.status.value}")
```

### Verify on TradingView
1. Check the chart for entry signal
2. Verify position appears in Trading Panel
3. Confirm stop loss and take profit levels are plotted

---

## Webhook Payload Format

The AMT Bot sends this JSON format:

```json
{
  "side": "LONG",
  "entry": 450.25,
  "stop": 447.50,
  "target": 452.38,
  "symbol": "SPY",
  "timeframe": "15m"
}
```

| Field | Type | Description |
|-------|------|-------------|
| side | string | "LONG" or "SHORT" |
| entry | float | Entry price |
| stop | float | Stop loss price |
| target | float | Take profit price |
| symbol | string | Trading symbol |
| timeframe | string | Chart timeframe |

---

## Troubleshooting

### Signal Not Executing

1. **Check alert is active**: Yellow bell icon should be visible
2. **Verify webhook URL**: Test with a simple HTTP request tool
3. **Check JSON format**: Ensure proper formatting with quotes
4. **Verify symbol match**: If validation enabled, symbols must match

### Duplicate Trades

The strategy prevents duplicates by tracking:
- Last signal side
- Last entry price
- Last stop price
- Last target price

If all values are identical, the signal is ignored.

### Position Not Closing

Ensure:
- Stop loss and take profit inputs are enabled
- Price levels are on the correct side of entry
- Strategy has proper permissions for paper trading

### Debug Mode

Add these plots to see signal state:
```pinescript
plot(valid_signal ? 1 : 0, "Valid Signal")
plot(new_signal ? 1 : 0, "New Signal")
plot(can_enter ? 1 : 0, "Can Enter")
```

---

## Strategy Features

### Single Position Mode
- `pyramiding = 0` ensures only one position at a time
- New signals in opposite direction close existing position first

### Duplicate Prevention
- Tracks last processed signal parameters
- Only processes if side, entry, stop, or target changed

### Visual Feedback
- Entry line (blue)
- Stop loss line (red)
- Take profit line (green)
- Background color indicates position (green=long, red=short)
- Information table shows current state

### Risk Management
- Configurable stop loss
- Configurable take profit
- Optional trailing stop

---

## Important Notes

1. **Paper Trading Only**: This setup is for paper trading. Real trading requires additional safeguards.

2. **Webhook Limits**: TradingView has rate limits on webhooks. Don't send more than 1 signal per second.

3. **Chart Must Be Open**: TradingView strategies only execute when the chart is open in a browser.

4. **Alert Expiration**: Set alerts to "Open-ended" for continuous operation.

5. **Time Sync**: Ensure your bot's timestamps are synchronized with TradingView's server time.

---

## Quick Reference

### Bot Configuration
```python
config.mode = BotMode.TRADINGVIEW_PAPER  # Enable webhooks
config.webhook.url = "YOUR_URL"          # TradingView webhook
config.webhook.dry_run = False           # Real HTTP calls
```

### Pine Script Key Settings
```pinescript
pyramiding = 0          // Single position
process_orders_on_close = false  // Execute on next bar
```

### Webhook JSON
```json
{"side":"LONG","entry":450.0,"stop":447.0,"target":453.0,"symbol":"SPY","timeframe":"15m"}
```
