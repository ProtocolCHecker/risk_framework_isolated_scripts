"""
Notification modules for alerting.

Supports:
- Telegram (recommended)
- Slack
"""

from .telegram import (
    send_telegram_alert,
    send_telegram_batch,
    process_pending_alerts as process_pending_alerts_telegram,
    test_telegram_connection
)

from .slack import (
    send_slack_alert,
    send_slack_batch,
    process_pending_alerts as process_pending_alerts_slack,
)

# Default to Telegram
process_pending_alerts = process_pending_alerts_telegram

__all__ = [
    # Telegram
    "send_telegram_alert",
    "send_telegram_batch",
    "process_pending_alerts_telegram",
    "test_telegram_connection",
    # Slack
    "send_slack_alert",
    "send_slack_batch",
    "process_pending_alerts_slack",
    # Default
    "process_pending_alerts",
]
