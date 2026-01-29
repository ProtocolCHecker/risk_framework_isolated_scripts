"""
Critical Frequency Lambda Handler (5 min interval).

Metrics: PoR ratio, oracle freshness, peg deviation

Triggered by CloudWatch Events Rule.
"""

import json
import sys
import os
from datetime import datetime

# Add paths for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.dispatcher import dispatch_critical
from notifications import process_pending_alerts_telegram


def handler(event, context):
    """
    AWS Lambda handler for critical frequency metrics.

    Args:
        event: Lambda event (from CloudWatch Events)
        context: Lambda context

    Returns:
        Dict with execution results
    """
    start_time = datetime.utcnow()

    response = {
        "statusCode": 200,
        "body": {
            "handler": "critical",
            "frequency": "5min",
            "timestamp": start_time.isoformat(),
            "status": "success",
            "dispatch_result": None,
            "notification_result": None,
            "error": None
        }
    }

    try:
        # Dispatch critical metrics
        print(f"[{start_time.isoformat()}] Starting critical metrics dispatch...")
        dispatch_result = dispatch_critical()

        response["body"]["dispatch_result"] = {
            "assets_processed": dispatch_result.get("assets_processed", 0),
            "metrics_collected": dispatch_result.get("metrics_collected", 0),
            "alerts_triggered": dispatch_result.get("alerts_triggered", 0),
            "errors": dispatch_result.get("errors", [])
        }

        print(f"  Assets: {dispatch_result.get('assets_processed', 0)}")
        print(f"  Metrics: {dispatch_result.get('metrics_collected', 0)}")
        print(f"  Alerts: {dispatch_result.get('alerts_triggered', 0)}")

        # Process any pending alerts immediately for critical
        if dispatch_result.get("alerts_triggered", 0) > 0:
            print("  Processing critical alerts...")
            notification_result = process_pending_alerts_telegram()
            response["body"]["notification_result"] = notification_result
            print(f"  Notifications sent: {notification_result.get('critical_sent', 0)} critical, {notification_result.get('batch_sent', 0)} batch")

        # Check for errors
        if dispatch_result.get("errors"):
            response["body"]["status"] = "partial"
            print(f"  Errors: {dispatch_result['errors']}")

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
    print("Testing critical handler locally...")
    result = handler({}, None)
    print(json.dumps(result, indent=2, default=str))
