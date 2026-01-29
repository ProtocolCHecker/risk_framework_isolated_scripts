"""
Notification Lambda Handler - Process and send pending alerts.

Can be triggered:
- On a schedule (e.g., every 5 min) for batched notifications
- Manually to catch up on any missed alerts

Handles both Telegram and Slack notifications based on configuration.
"""

import json
import sys
import os
from datetime import datetime

# Add paths for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from notifications import process_pending_alerts_telegram
from core.alerts import get_unnotified_alerts


def handler(event, context):
    """
    AWS Lambda handler for processing pending notifications.

    Args:
        event: Lambda event (from CloudWatch Events or manual trigger)
            Optional keys:
            - channel: "telegram" or "slack" (default: telegram)
            - force_batch: True to batch all alerts regardless of severity
        context: Lambda context

    Returns:
        Dict with notification results
    """
    start_time = datetime.utcnow()

    # Parse event options
    channel = event.get("channel", "telegram") if event else "telegram"

    response = {
        "statusCode": 200,
        "body": {
            "handler": "notification",
            "channel": channel,
            "timestamp": start_time.isoformat(),
            "status": "success",
            "pending_count": 0,
            "result": None,
            "error": None
        }
    }

    try:
        # Get count of pending alerts first
        pending_alerts = get_unnotified_alerts()
        response["body"]["pending_count"] = len(pending_alerts)

        print(f"[{start_time.isoformat()}] Processing notifications...")
        print(f"  Channel: {channel}")
        print(f"  Pending alerts: {len(pending_alerts)}")

        if not pending_alerts:
            print("  No pending alerts to process")
            return response

        # Process based on channel
        if channel == "telegram":
            result = process_pending_alerts_telegram()
        else:
            # Could add Slack support here
            from notifications import process_pending_alerts_slack
            result = process_pending_alerts_slack()

        response["body"]["result"] = result

        print(f"  Total processed: {result.get('total_processed', 0)}")
        print(f"  Critical sent: {result.get('critical_sent', 0)}")
        print(f"  Batch sent: {result.get('batch_sent', 0)}")

        if result.get("errors"):
            response["body"]["status"] = "partial"
            print(f"  Errors: {result['errors']}")

    except Exception as e:
        response["statusCode"] = 500
        response["body"]["status"] = "error"
        response["body"]["error"] = str(e)
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

    # Calculate execution time
    end_time = datetime.utcnow()
    duration_ms = (end_time - start_time).total_seconds() * 1000
    response["body"]["duration_ms"] = duration_ms
    print(f"  Duration: {duration_ms:.0f}ms")

    return response


# For local testing
if __name__ == "__main__":
    print("Testing notification handler locally...")
    result = handler({}, None)
    print(json.dumps(result, indent=2, default=str))
