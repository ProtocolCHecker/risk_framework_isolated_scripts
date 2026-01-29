"""
Telegram Notification Module - Send alerts to Telegram.

Features:
- Immediate send for critical alerts
- Batched digest for warning/info alerts
- Markdown formatting with severity indicators
"""

import os
import requests
from typing import Dict, Any, List, Optional
from datetime import datetime

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import ALERT_CONFIG
from core.alerts import get_unnotified_alerts, mark_alerts_notified


# Telegram config from environment or config
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or ALERT_CONFIG.get("telegram_bot_token")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID") or ALERT_CONFIG.get("telegram_chat_id")

# Telegram API base URL
TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"

# Severity emojis
SEVERITY_EMOJIS = {
    "critical": "🚨",
    "warning": "⚠️",
    "info": "ℹ️"
}


def escape_markdown(text: str) -> str:
    """Escape special Markdown characters for Telegram."""
    # Telegram Markdown special chars: _ * [ ] ( ) ~ ` > # + - = | { } . !
    # We only escape underscores as they're common in metric names
    if text is None:
        return ""
    return str(text).replace("_", "\\_")


def format_single_alert(alert: Dict) -> str:
    """
    Format a single alert as Telegram message.

    Args:
        alert: Alert dict

    Returns:
        Formatted message string (Markdown)
    """
    severity = alert.get("severity", "info")
    emoji = SEVERITY_EMOJIS.get(severity, "🔔")

    chain_info = f" ({alert['chain']})" if alert.get("chain") else ""
    metric_name = escape_markdown(alert.get('metric_name', 'Unknown'))

    message = f"""{emoji} *{severity.upper()} ALERT*

*Asset:* {alert.get('asset_symbol', 'Unknown')}
*Metric:* {metric_name}{chain_info}
*Value:* {alert.get('value', 0):.4f}
*Threshold:* {alert.get('operator', '')} {alert.get('threshold_value', 0)}"""

    return message


def format_batch_digest(alerts: List[Dict]) -> str:
    """
    Format multiple alerts as a digest message.

    Args:
        alerts: List of alert dicts

    Returns:
        Formatted digest string (Markdown)
    """
    # Group by severity
    by_severity = {"critical": [], "warning": [], "info": []}
    for alert in alerts:
        severity = alert.get("severity", "info")
        if severity in by_severity:
            by_severity[severity].append(alert)

    # Build summary
    summary_parts = []
    if by_severity["critical"]:
        summary_parts.append(f"🚨 {len(by_severity['critical'])} Critical")
    if by_severity["warning"]:
        summary_parts.append(f"⚠️ {len(by_severity['warning'])} Warning")
    if by_severity["info"]:
        summary_parts.append(f"ℹ️ {len(by_severity['info'])} Info")

    summary = " | ".join(summary_parts)

    message = f"""📊 *Risk Alert Digest* ({len(alerts)} alerts)

{summary}

{'─' * 30}
"""

    # Add alert details (limit to 10)
    shown_alerts = alerts[:10]
    for alert in shown_alerts:
        severity = alert.get("severity", "info")
        emoji = SEVERITY_EMOJIS.get(severity, "🔔")
        chain_info = f" ({alert['chain']})" if alert.get("chain") else ""
        metric_name = escape_markdown(alert.get('metric_name', 'Unknown'))

        message += f"""
{emoji} *{alert.get('asset_symbol')}* - {metric_name}{chain_info}
   Value: {alert.get('value', 0):.4f} (threshold: {alert.get('operator')} {alert.get('threshold_value')})
"""

    if len(alerts) > 10:
        message += f"\n_...and {len(alerts) - 10} more alerts_"

    return message


def send_telegram_message(text: str, parse_mode: str = "Markdown") -> bool:
    """
    Send a message to Telegram.

    Args:
        text: Message text
        parse_mode: Telegram parse mode (Markdown or HTML)

    Returns:
        True if successful
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Warning: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not configured")
        return False

    url = TELEGRAM_API_URL.format(token=TELEGRAM_BOT_TOKEN)

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": parse_mode
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()

        result = response.json()
        if not result.get("ok"):
            print(f"Telegram API error: {result.get('description', 'Unknown error')}")
            return False

        return True
    except requests.exceptions.RequestException as e:
        print(f"Telegram send error: {e}")
        return False


def send_telegram_alert(alert: Dict) -> bool:
    """
    Send a single alert to Telegram immediately.

    Args:
        alert: Alert dict

    Returns:
        True if successful
    """
    message = format_single_alert(alert)
    return send_telegram_message(message)


def send_telegram_batch(alerts: List[Dict]) -> bool:
    """
    Send a batch of alerts as a digest to Telegram.

    Args:
        alerts: List of alert dicts

    Returns:
        True if successful
    """
    if not alerts:
        return True

    # If single alert, send individually
    if len(alerts) == 1:
        return send_telegram_alert(alerts[0])

    message = format_batch_digest(alerts)
    return send_telegram_message(message)


def process_pending_alerts() -> Dict[str, Any]:
    """
    Process all pending (unnotified) alerts via Telegram.

    - Critical alerts: Send immediately
    - Warning/Info alerts: Batch together

    Returns:
        Dict with processing results
    """
    result = {
        "total_processed": 0,
        "critical_sent": 0,
        "batch_sent": 0,
        "errors": []
    }

    # Get unnotified alerts
    alerts = get_unnotified_alerts()

    if not alerts:
        return result

    result["total_processed"] = len(alerts)

    # Separate critical from others
    critical_alerts = [a for a in alerts if a.get("severity") == "critical"]
    other_alerts = [a for a in alerts if a.get("severity") != "critical"]

    # Send critical alerts immediately
    critical_ids = []
    for alert in critical_alerts:
        try:
            if send_telegram_alert(alert):
                critical_ids.append(alert["id"])
                result["critical_sent"] += 1
        except Exception as e:
            result["errors"].append(f"Critical alert {alert['id']}: {str(e)}")

    # Mark critical alerts as notified
    if critical_ids:
        mark_alerts_notified(critical_ids, channel="telegram")

    # Batch send other alerts
    if other_alerts:
        try:
            if send_telegram_batch(other_alerts):
                other_ids = [a["id"] for a in other_alerts]
                mark_alerts_notified(other_ids, channel="telegram")
                result["batch_sent"] = len(other_alerts)
        except Exception as e:
            result["errors"].append(f"Batch send: {str(e)}")

    return result


def test_telegram_connection() -> Dict[str, Any]:
    """
    Test Telegram bot connection by sending a test message.

    Returns:
        Dict with test results
    """
    result = {
        "status": "error",
        "message": None,
        "error": None
    }

    if not TELEGRAM_BOT_TOKEN:
        result["error"] = "TELEGRAM_BOT_TOKEN not set"
        return result

    if not TELEGRAM_CHAT_ID:
        result["error"] = "TELEGRAM_CHAT_ID not set"
        return result

    test_message = """🧪 *Risk Monitoring System - Test*

✅ Telegram integration is working!

This is a test message from the Risk Monitoring System.
"""

    if send_telegram_message(test_message):
        result["status"] = "success"
        result["message"] = "Test message sent successfully"
    else:
        result["error"] = "Failed to send test message"

    return result


if __name__ == "__main__":
    print("Telegram Notification Module")
    print("=" * 60)

    # Check configuration
    print(f"\nBot Token: {'Set' if TELEGRAM_BOT_TOKEN else 'NOT SET'}")
    print(f"Chat ID: {'Set' if TELEGRAM_CHAT_ID else 'NOT SET'}")

    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        print("\nTesting connection...")
        result = test_telegram_connection()
        print(f"Status: {result['status']}")
        if result.get('error'):
            print(f"Error: {result['error']}")
        if result.get('message'):
            print(f"Message: {result['message']}")
    else:
        print("\nTo test, set environment variables:")
        print("  export TELEGRAM_BOT_TOKEN='your-bot-token'")
        print("  export TELEGRAM_CHAT_ID='your-chat-id'")

        print("\nTo create a Telegram bot:")
        print("  1. Message @BotFather on Telegram")
        print("  2. Send /newbot and follow instructions")
        print("  3. Copy the bot token")
        print("\nTo get chat ID:")
        print("  1. Add the bot to your group/channel")
        print("  2. Send a message in the group")
        print("  3. Visit: https://api.telegram.org/bot<TOKEN>/getUpdates")
        print("  4. Find 'chat':{'id': XXXXXXX} in the response")
