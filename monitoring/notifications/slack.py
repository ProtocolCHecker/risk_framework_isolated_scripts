"""
Slack Notification Module - Send alerts to Slack.

Features:
- Immediate send for critical alerts
- Batched digest for warning/info alerts
- Rich formatting with severity colors
"""

import os
import json
import requests
from typing import Dict, Any, List, Optional
from datetime import datetime

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import ALERT_CONFIG
from core.alerts import get_unnotified_alerts, mark_alerts_notified


# Slack webhook URL from environment or config
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL") or ALERT_CONFIG.get("slack_webhook")

# Severity colors for Slack
SEVERITY_COLORS = {
    "critical": "#FF0000",  # Red
    "warning": "#FFA500",   # Orange
    "info": "#0000FF"       # Blue
}

# Severity emojis
SEVERITY_EMOJIS = {
    "critical": ":rotating_light:",
    "warning": ":warning:",
    "info": ":information_source:"
}


def format_single_alert(alert: Dict) -> Dict:
    """
    Format a single alert as a Slack attachment.

    Args:
        alert: Alert dict

    Returns:
        Slack attachment dict
    """
    severity = alert.get("severity", "info")
    color = SEVERITY_COLORS.get(severity, "#808080")
    emoji = SEVERITY_EMOJIS.get(severity, ":bell:")

    # Build fields
    fields = [
        {
            "title": "Asset",
            "value": alert.get("asset_symbol", "Unknown"),
            "short": True
        },
        {
            "title": "Metric",
            "value": alert.get("metric_name", "Unknown"),
            "short": True
        },
        {
            "title": "Value",
            "value": f"{alert.get('value', 0):.4f}",
            "short": True
        },
        {
            "title": "Threshold",
            "value": f"{alert.get('operator', '')} {alert.get('threshold_value', 0)}",
            "short": True
        }
    ]

    # Add chain if present
    if alert.get("chain"):
        fields.append({
            "title": "Chain",
            "value": alert["chain"],
            "short": True
        })

    return {
        "color": color,
        "title": f"{emoji} {severity.upper()} Alert",
        "text": alert.get("message", "Alert triggered"),
        "fields": fields,
        "footer": "Risk Monitoring System",
        "ts": int(datetime.utcnow().timestamp())
    }


def format_batch_digest(alerts: List[Dict]) -> Dict:
    """
    Format multiple alerts as a digest message.

    Args:
        alerts: List of alert dicts

    Returns:
        Slack message payload
    """
    # Group by severity
    by_severity = {"critical": [], "warning": [], "info": []}
    for alert in alerts:
        severity = alert.get("severity", "info")
        if severity in by_severity:
            by_severity[severity].append(alert)

    # Build summary text
    summary_parts = []
    if by_severity["critical"]:
        summary_parts.append(f":rotating_light: {len(by_severity['critical'])} Critical")
    if by_severity["warning"]:
        summary_parts.append(f":warning: {len(by_severity['warning'])} Warning")
    if by_severity["info"]:
        summary_parts.append(f":information_source: {len(by_severity['info'])} Info")

    summary = " | ".join(summary_parts)

    # Build blocks
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"Risk Alert Digest ({len(alerts)} alerts)",
                "emoji": True
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": summary
            }
        },
        {"type": "divider"}
    ]

    # Add alert details (limit to 10 to avoid message size limits)
    shown_alerts = alerts[:10]
    for alert in shown_alerts:
        severity = alert.get("severity", "info")
        emoji = SEVERITY_EMOJIS.get(severity, ":bell:")

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"{emoji} *{alert.get('asset_symbol')}* - {alert.get('metric_name')}\n"
                    f"Value: `{alert.get('value', 0):.4f}` "
                    f"(threshold: {alert.get('operator')} {alert.get('threshold_value')})"
                )
            }
        })

    if len(alerts) > 10:
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"_...and {len(alerts) - 10} more alerts_"
                }
            ]
        })

    return {"blocks": blocks}


def send_slack_message(payload: Dict) -> bool:
    """
    Send a message to Slack webhook.

    Args:
        payload: Slack message payload

    Returns:
        True if successful
    """
    if not SLACK_WEBHOOK_URL:
        print("Warning: SLACK_WEBHOOK_URL not configured")
        return False

    try:
        response = requests.post(
            SLACK_WEBHOOK_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        print(f"Slack send error: {e}")
        return False


def send_slack_alert(alert: Dict) -> bool:
    """
    Send a single alert to Slack immediately.

    Args:
        alert: Alert dict

    Returns:
        True if successful
    """
    attachment = format_single_alert(alert)
    payload = {"attachments": [attachment]}
    return send_slack_message(payload)


def send_slack_batch(alerts: List[Dict]) -> bool:
    """
    Send a batch of alerts as a digest to Slack.

    Args:
        alerts: List of alert dicts

    Returns:
        True if successful
    """
    if not alerts:
        return True

    # If only critical alerts or single alert, send individually
    if len(alerts) == 1:
        return send_slack_alert(alerts[0])

    payload = format_batch_digest(alerts)
    return send_slack_message(payload)


def process_pending_alerts() -> Dict[str, Any]:
    """
    Process all pending (unnotified) alerts.

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
            if send_slack_alert(alert):
                critical_ids.append(alert["id"])
                result["critical_sent"] += 1
        except Exception as e:
            result["errors"].append(f"Critical alert {alert['id']}: {str(e)}")

    # Mark critical alerts as notified
    if critical_ids:
        mark_alerts_notified(critical_ids, channel="slack")

    # Batch send other alerts
    if other_alerts:
        try:
            if send_slack_batch(other_alerts):
                other_ids = [a["id"] for a in other_alerts]
                mark_alerts_notified(other_ids, channel="slack")
                result["batch_sent"] = len(other_alerts)
        except Exception as e:
            result["errors"].append(f"Batch send: {str(e)}")

    return result


if __name__ == "__main__":
    # Test Slack formatting
    print("Testing Slack notification formatting...")

    test_alert = {
        "id": 1,
        "asset_symbol": "wstETH",
        "metric_name": "oracle_freshness_minutes",
        "value": 45.5,
        "threshold_value": 30,
        "operator": ">",
        "severity": "warning",
        "chain": "ethereum",
        "message": "wstETH oracle_freshness_minutes (ethereum): 45.5000 > 30 [warning]"
    }

    print("\nSingle alert format:")
    attachment = format_single_alert(test_alert)
    print(json.dumps(attachment, indent=2))

    print("\nBatch digest format:")
    batch = [test_alert, {**test_alert, "severity": "critical", "value": 65.0}]
    digest = format_batch_digest(batch)
    print(json.dumps(digest, indent=2))

    print("\nNote: Set SLACK_WEBHOOK_URL env var to test actual sending")
