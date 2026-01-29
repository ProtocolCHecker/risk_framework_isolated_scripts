"""
Alert System - Check metrics against thresholds and log breaches.

Only logs when thresholds are breached (no audit trail for passing metrics).
"""

import sys
import os
from typing import Dict, Any, List, Optional
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import SCHEMA_NAME, TABLE_PREFIX
from core.db import get_connection, execute_query, table_name


# Operator mapping for threshold comparisons
OPERATORS = {
    '<': lambda v, t: v < t,
    '>': lambda v, t: v > t,
    '<=': lambda v, t: v <= t,
    '>=': lambda v, t: v >= t,
    '=': lambda v, t: v == t,
}


def get_thresholds_for_metric(metric_name: str, asset_symbol: str = None) -> List[Dict]:
    """
    Get all applicable thresholds for a metric.

    Thresholds can be:
    - Asset-specific (asset_symbol matches)
    - Global (asset_symbol is NULL)

    Args:
        metric_name: Name of the metric
        asset_symbol: Optional asset symbol for asset-specific thresholds

    Returns:
        List of threshold dicts
    """
    query = f"""
        SELECT id, asset_symbol, metric_name, operator, threshold_value, severity
        FROM {table_name('alert_thresholds')}
        WHERE enabled = true
          AND metric_name = %s
          AND (asset_symbol IS NULL OR asset_symbol = %s)
        ORDER BY severity DESC
    """
    return execute_query(query, (metric_name, asset_symbol))


def check_threshold(value: float, operator: str, threshold: float) -> bool:
    """
    Check if a value breaches a threshold.

    Args:
        value: Metric value
        operator: Comparison operator ('<', '>', '<=', '>=', '=')
        threshold: Threshold value

    Returns:
        True if threshold is breached
    """
    if operator not in OPERATORS:
        return False
    return OPERATORS[operator](value, threshold)


def log_alert(
    asset_symbol: str,
    metric_name: str,
    value: float,
    threshold_value: float,
    operator: str,
    severity: str,
    message: str = None
) -> int:
    """
    Log an alert to the database.

    Args:
        asset_symbol: Asset symbol
        metric_name: Metric name
        value: Current metric value
        threshold_value: Threshold that was breached
        operator: Threshold operator
        severity: Alert severity (critical, warning, info)
        message: Optional alert message

    Returns:
        Inserted alert ID
    """
    query = f"""
        INSERT INTO {table_name('alerts_log')}
        (asset_symbol, metric_name, value, threshold_value, operator, severity, message)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (
                asset_symbol, metric_name, value,
                threshold_value, operator, severity, message
            ))
            alert_id = cur.fetchone()[0]
            conn.commit()
            return alert_id


def check_metric_against_thresholds(
    asset_symbol: str,
    metric_name: str,
    value: float,
    chain: str = None
) -> List[Dict]:
    """
    Check a single metric against all applicable thresholds.

    Args:
        asset_symbol: Asset symbol
        metric_name: Metric name
        value: Current metric value
        chain: Optional chain name for context

    Returns:
        List of triggered alerts (empty if none)
    """
    triggered_alerts = []

    # Get thresholds for this metric
    thresholds = get_thresholds_for_metric(metric_name, asset_symbol)

    for threshold in thresholds:
        operator = threshold['operator']
        threshold_value = float(threshold['threshold_value'])
        severity = threshold['severity']

        # Check if threshold is breached
        if check_threshold(value, operator, threshold_value):
            # Build alert message
            message = f"{asset_symbol} {metric_name}"
            if chain:
                message += f" ({chain})"
            message += f": {value:.4f} {operator} {threshold_value} [{severity}]"

            # Log to database
            alert_id = log_alert(
                asset_symbol=asset_symbol,
                metric_name=metric_name,
                value=value,
                threshold_value=threshold_value,
                operator=operator,
                severity=severity,
                message=message
            )

            triggered_alerts.append({
                "id": alert_id,
                "asset_symbol": asset_symbol,
                "metric_name": metric_name,
                "value": value,
                "threshold_value": threshold_value,
                "operator": operator,
                "severity": severity,
                "message": message,
                "chain": chain,
                "triggered_at": datetime.utcnow().isoformat()
            })

    return triggered_alerts


def check_alerts_for_metrics(metrics: List[Dict]) -> List[Dict]:
    """
    Check a batch of metrics against thresholds.

    Args:
        metrics: List of metric dicts with keys:
            - asset_symbol
            - metric_name
            - value
            - chain (optional)

    Returns:
        List of all triggered alerts
    """
    all_alerts = []

    for metric in metrics:
        asset_symbol = metric.get("asset_symbol", "UNKNOWN")
        metric_name = metric.get("metric_name")
        value = metric.get("value")
        chain = metric.get("chain")

        if metric_name is None or value is None:
            continue

        try:
            alerts = check_metric_against_thresholds(
                asset_symbol=asset_symbol,
                metric_name=metric_name,
                value=float(value),
                chain=chain
            )
            all_alerts.extend(alerts)
        except Exception as e:
            print(f"Alert check error for {asset_symbol}/{metric_name}: {e}")

    return all_alerts


def get_recent_alerts(hours: int = 24, severity: str = None) -> List[Dict]:
    """
    Get recent alerts from the database.

    Args:
        hours: Number of hours to look back
        severity: Optional filter by severity

    Returns:
        List of alert records
    """
    query = f"""
        SELECT *
        FROM {table_name('alerts_log')}
        WHERE triggered_at > NOW() - INTERVAL '{hours} hours'
    """
    params = []

    if severity:
        query += " AND severity = %s"
        params.append(severity)

    query += " ORDER BY triggered_at DESC"

    return execute_query(query, tuple(params) if params else None)


def get_unnotified_alerts() -> List[Dict]:
    """
    Get alerts that haven't been sent to notification channels.

    Returns:
        List of unnotified alert records
    """
    query = f"""
        SELECT *
        FROM {table_name('alerts_log')}
        WHERE notified = false
        ORDER BY
            CASE severity
                WHEN 'critical' THEN 1
                WHEN 'warning' THEN 2
                ELSE 3
            END,
            triggered_at ASC
    """
    return execute_query(query)


def mark_alerts_notified(alert_ids: List[int], channel: str = 'slack') -> int:
    """
    Mark alerts as notified.

    Args:
        alert_ids: List of alert IDs to mark
        channel: Notification channel used

    Returns:
        Number of alerts updated
    """
    if not alert_ids:
        return 0

    placeholders = ','.join(['%s'] * len(alert_ids))
    query = f"""
        UPDATE {table_name('alerts_log')}
        SET notified = true, notification_channel = %s
        WHERE id IN ({placeholders})
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (channel, *alert_ids))
            conn.commit()
            return cur.rowcount


def add_custom_threshold(
    metric_name: str,
    operator: str,
    threshold_value: float,
    severity: str,
    asset_symbol: str = None
) -> int:
    """
    Add a custom alert threshold.

    Args:
        metric_name: Metric name
        operator: Comparison operator
        threshold_value: Threshold value
        severity: Alert severity
        asset_symbol: Optional asset-specific threshold

    Returns:
        Inserted threshold ID
    """
    query = f"""
        INSERT INTO {table_name('alert_thresholds')}
        (asset_symbol, metric_name, operator, threshold_value, severity)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING
        RETURNING id
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (asset_symbol, metric_name, operator, threshold_value, severity))
            result = cur.fetchone()
            conn.commit()
            return result[0] if result else None


if __name__ == "__main__":
    # Test alert system
    print("Testing alert system...")

    # Test threshold check
    print("\nThreshold check tests:")
    print(f"  0.5 < 1.0: {check_threshold(0.5, '<', 1.0)} (expect True)")
    print(f"  1.5 < 1.0: {check_threshold(1.5, '<', 1.0)} (expect False)")
    print(f"  95 > 90: {check_threshold(95, '>', 90)} (expect True)")

    # Test getting thresholds from DB
    print("\nFetching thresholds for 'por_ratio'...")
    thresholds = get_thresholds_for_metric('por_ratio')
    for t in thresholds:
        print(f"  {t['operator']} {t['threshold_value']} -> {t['severity']}")
