"""Core monitoring components."""

from .db import (
    get_connection,
    execute_query,
    execute_many,
    insert_metric,
    insert_metrics_batch,
    get_latest_metric,
    get_metric_history,
    table_name
)

from .registry import AssetRegistry, load_all_configs_from_directory

from .dispatcher import (
    dispatch_critical,
    dispatch_high,
    dispatch_medium,
    dispatch_daily,
    dispatch_all
)

from .alerts import (
    check_alerts_for_metrics,
    check_metric_against_thresholds,
    get_recent_alerts,
    get_unnotified_alerts,
    mark_alerts_notified,
    add_custom_threshold
)

__all__ = [
    # Database
    "get_connection",
    "execute_query",
    "execute_many",
    "insert_metric",
    "insert_metrics_batch",
    "get_latest_metric",
    "get_metric_history",
    "table_name",
    # Registry
    "AssetRegistry",
    "load_all_configs_from_directory",
    # Dispatcher
    "dispatch_critical",
    "dispatch_high",
    "dispatch_medium",
    "dispatch_daily",
    "dispatch_all",
    # Alerts
    "check_alerts_for_metrics",
    "check_metric_against_thresholds",
    "get_recent_alerts",
    "get_unnotified_alerts",
    "mark_alerts_notified",
    "add_custom_threshold",
]
