"""
Risk Monitoring System.

Monitors DeFi asset metrics at configurable frequencies and alerts on threshold breaches.

Quick Start:
    from monitoring import dispatch_critical, AssetRegistry

    # Add asset to registry
    AssetRegistry.add_asset_from_file("assets/wsteth.json")

    # Run critical frequency dispatcher
    result = dispatch_critical()
    print(f"Collected {result['metrics_collected']} metrics")
"""

__version__ = "1.0.0"

# Core components
from .core import (
    # Dispatchers
    dispatch_critical,
    dispatch_high,
    dispatch_medium,
    dispatch_daily,
    dispatch_all,
    # Registry
    AssetRegistry,
    load_all_configs_from_directory,
    # Database
    get_connection,
    insert_metric,
    insert_metrics_batch,
    get_latest_metric,
    # Alerts
    check_alerts_for_metrics,
    get_recent_alerts,
    get_unnotified_alerts,
    add_custom_threshold,
)

# Notifications
from .notifications import (
    send_slack_alert,
    send_slack_batch,
    process_pending_alerts,
)

__all__ = [
    # Version
    "__version__",
    # Dispatchers
    "dispatch_critical",
    "dispatch_high",
    "dispatch_medium",
    "dispatch_daily",
    "dispatch_all",
    # Registry
    "AssetRegistry",
    "load_all_configs_from_directory",
    # Database
    "get_connection",
    "insert_metric",
    "insert_metrics_batch",
    "get_latest_metric",
    # Alerts
    "check_alerts_for_metrics",
    "get_recent_alerts",
    "get_unnotified_alerts",
    "add_custom_threshold",
    # Notifications
    "send_slack_alert",
    "send_slack_batch",
    "process_pending_alerts",
]
