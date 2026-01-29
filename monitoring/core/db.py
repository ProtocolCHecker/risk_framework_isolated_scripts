"""
Database connection and utilities for risk monitoring.

Uses existing Avantgarde PostgreSQL RDS instance.
"""

import psycopg2
from psycopg2.extras import RealDictCursor, execute_values
from contextlib import contextmanager
from typing import List, Dict, Any, Optional
import json

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import DB_CONFIG, SCHEMA_NAME, TABLE_PREFIX


def table_name(name: str) -> str:
    """Get full table name with schema and prefix."""
    return f"{SCHEMA_NAME}.{TABLE_PREFIX}{name}"


@contextmanager
def get_connection():
    """
    Get a database connection as a context manager.

    Usage:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
    """
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        yield conn
    finally:
        if conn:
            conn.close()


def execute_query(query: str, params: tuple = None, fetch: bool = True) -> Optional[List[Dict]]:
    """
    Execute a query and optionally fetch results.

    Args:
        query: SQL query string
        params: Query parameters (tuple)
        fetch: If True, return results as list of dicts

    Returns:
        List of dicts if fetch=True, else None
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            if fetch:
                return [dict(row) for row in cur.fetchall()]
            conn.commit()
            return None


def execute_many(query: str, data: List[tuple]) -> int:
    """
    Execute a query with multiple parameter sets (bulk insert).

    Args:
        query: SQL query string with %s placeholders
        data: List of tuples with parameters

    Returns:
        Number of rows affected
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(query, data)
            conn.commit()
            return cur.rowcount


def insert_metric(asset_symbol: str, metric_name: str, value: float,
                  chain: str = None, metadata: dict = None) -> int:
    """
    Insert a single metric record.

    Args:
        asset_symbol: Asset symbol (e.g., 'RLP', 'wstETH')
        metric_name: Metric name (e.g., 'por_ratio', 'oracle_freshness')
        value: Metric value
        chain: Optional chain name
        metadata: Optional additional metadata as dict

    Returns:
        Inserted row ID
    """
    query = f"""
        INSERT INTO {table_name('metrics_history')}
        (asset_symbol, metric_name, value, chain, metadata)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
    """
    metadata_json = json.dumps(metadata) if metadata else None

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (asset_symbol, metric_name, value, chain, metadata_json))
            row_id = cur.fetchone()[0]
            conn.commit()
            return row_id


def insert_metrics_batch(metrics: List[Dict]) -> int:
    """
    Insert multiple metrics in a single transaction.

    Args:
        metrics: List of dicts with keys: asset_symbol, metric_name, value, chain, metadata

    Returns:
        Number of rows inserted
    """
    if not metrics:
        return 0

    query = f"""
        INSERT INTO {table_name('metrics_history')}
        (asset_symbol, metric_name, value, chain, metadata)
        VALUES %s
    """

    data = [
        (
            m['asset_symbol'],
            m['metric_name'],
            m['value'],
            m.get('chain'),
            json.dumps(m.get('metadata')) if m.get('metadata') else None
        )
        for m in metrics
    ]

    with get_connection() as conn:
        with conn.cursor() as cur:
            execute_values(cur, query, data)
            conn.commit()
            return len(data)


def get_latest_metric(asset_symbol: str, metric_name: str) -> Optional[Dict]:
    """
    Get the most recent value for a specific metric.

    Args:
        asset_symbol: Asset symbol
        metric_name: Metric name

    Returns:
        Dict with metric data or None
    """
    query = f"""
        SELECT * FROM {table_name('metrics_history')}
        WHERE asset_symbol = %s AND metric_name = %s
        ORDER BY recorded_at DESC
        LIMIT 1
    """
    results = execute_query(query, (asset_symbol, metric_name))
    return results[0] if results else None


def get_metric_history(asset_symbol: str, metric_name: str,
                       limit: int = 100) -> List[Dict]:
    """
    Get historical values for a specific metric.

    Args:
        asset_symbol: Asset symbol
        metric_name: Metric name
        limit: Maximum number of records to return

    Returns:
        List of metric records (newest first)
    """
    query = f"""
        SELECT * FROM {table_name('metrics_history')}
        WHERE asset_symbol = %s AND metric_name = %s
        ORDER BY recorded_at DESC
        LIMIT %s
    """
    return execute_query(query, (asset_symbol, metric_name, limit))


def test_connection() -> bool:
    """
    Test database connectivity.

    Returns:
        True if connection successful
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                return True
    except Exception as e:
        print(f"Database connection failed: {e}")
        return False


if __name__ == "__main__":
    # Test connection
    print("Testing database connection...")
    if test_connection():
        print("Connection successful!")
    else:
        print("Connection failed!")
