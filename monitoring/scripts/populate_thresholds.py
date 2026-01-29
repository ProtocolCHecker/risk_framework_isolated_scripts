"""
Populate Alert Thresholds based on Scoring Framework.

Maps thresholds from thresholds.py to rm_alert_thresholds table.

Severity levels based on scoring framework grade boundaries:
- critical: Score would be F (<40) or circuit breaker triggered
- warning: Score would be D (40-54)
- info: Score would be C (55-69)
"""

import sys
import os
import psycopg2

# Add config path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import DB_CONFIG

def get_connection():
    """Get database connection."""
    return psycopg2.connect(**DB_CONFIG)

# =============================================================================
# ALERT THRESHOLDS DERIVED FROM SCORING FRAMEWORK
# =============================================================================

ALERT_THRESHOLDS = [
    # =========================================================================
    # RESERVE & ORACLE (25% weight in scoring)
    # =========================================================================

    # Proof of Reserves - MOST CRITICAL (circuit breaker if < 100%)
    {
        "metric_name": "por_ratio",
        "operator": "<",
        "threshold_value": 0.95,
        "severity": "critical",
        "description": "PoR ratio < 95% - solvency concern (score ~10)"
    },
    {
        "metric_name": "por_ratio",
        "operator": "<",
        "threshold_value": 0.98,
        "severity": "warning",
        "description": "PoR ratio < 98% - 2% unbacked is material (score ~50)"
    },
    {
        "metric_name": "por_ratio",
        "operator": "<",
        "threshold_value": 1.0,
        "severity": "info",
        "description": "PoR ratio < 100% - not fully backed (score ~70)"
    },

    # Oracle Freshness (minutes)
    {
        "metric_name": "oracle_freshness_minutes",
        "operator": ">",
        "threshold_value": 360,
        "severity": "critical",
        "description": "Oracle > 6 hours stale - effectively offline (score ~25)"
    },
    {
        "metric_name": "oracle_freshness_minutes",
        "operator": ">",
        "threshold_value": 180,
        "severity": "warning",
        "description": "Oracle > 3 hours stale - price may have moved significantly (score ~50)"
    },
    {
        "metric_name": "oracle_freshness_minutes",
        "operator": ">",
        "threshold_value": 60,
        "severity": "info",
        "description": "Oracle > 1 hour - within Chainlink heartbeat but aging (score ~75)"
    },

    # Cross-chain Oracle Lag
    {
        "metric_name": "cross_chain_lag_minutes",
        "operator": ">",
        "threshold_value": 120,
        "severity": "critical",
        "description": "Cross-chain lag > 2 hours - problematic for operations (score ~30)"
    },
    {
        "metric_name": "cross_chain_lag_minutes",
        "operator": ">",
        "threshold_value": 60,
        "severity": "warning",
        "description": "Cross-chain lag > 1 hour - meaningful arbitrage window (score ~50)"
    },

    # =========================================================================
    # MARKET RISK (15% weight)
    # =========================================================================

    # Peg Deviation
    {
        "metric_name": "peg_deviation_pct",
        "operator": ">",
        "threshold_value": 5.0,
        "severity": "critical",
        "description": "Peg deviation > 5% - serious depeg (score ~30)"
    },
    {
        "metric_name": "peg_deviation_pct",
        "operator": ">",
        "threshold_value": 2.0,
        "severity": "warning",
        "description": "Peg deviation > 2% - liquidity stress (score ~55)"
    },
    {
        "metric_name": "peg_deviation_pct",
        "operator": ">",
        "threshold_value": 1.0,
        "severity": "info",
        "description": "Peg deviation > 1% - minor arbitrage opportunity (score ~75)"
    },

    # Volatility (annualized %)
    {
        "metric_name": "volatility_30d",
        "operator": ">",
        "threshold_value": 100,
        "severity": "critical",
        "description": "Volatility > 100% annualized - crisis level (score ~20)"
    },
    {
        "metric_name": "volatility_30d",
        "operator": ">",
        "threshold_value": 80,
        "severity": "warning",
        "description": "Volatility > 80% - stress period (score ~40)"
    },
    {
        "metric_name": "volatility_30d",
        "operator": ">",
        "threshold_value": 60,
        "severity": "info",
        "description": "Volatility > 60% - elevated, BTC historical average (score ~60)"
    },

    # VaR 95% (daily %)
    {
        "metric_name": "var_95",
        "operator": ">",
        "threshold_value": 12,
        "severity": "critical",
        "description": "VaR 95% > 12% daily - flash crash risk (score ~25)"
    },
    {
        "metric_name": "var_95",
        "operator": ">",
        "threshold_value": 8,
        "severity": "warning",
        "description": "VaR 95% > 8% daily - elevated tail risk (score ~45)"
    },
    {
        "metric_name": "var_95",
        "operator": ">",
        "threshold_value": 5,
        "severity": "info",
        "description": "VaR 95% > 5% - Gauntlet baseline threshold (score ~65)"
    },

    # =========================================================================
    # LIQUIDITY RISK (15% weight)
    # =========================================================================

    # Slippage $100K
    {
        "metric_name": "slippage_100k_pct",
        "operator": ">",
        "threshold_value": 5.0,
        "severity": "critical",
        "description": "Slippage > 5% at $100K - liquidation efficiency at risk (score ~20)"
    },
    {
        "metric_name": "slippage_100k_pct",
        "operator": ">",
        "threshold_value": 2.0,
        "severity": "warning",
        "description": "Slippage > 2% at $100K - significant execution cost (score ~45)"
    },
    {
        "metric_name": "slippage_100k_pct",
        "operator": ">",
        "threshold_value": 1.0,
        "severity": "info",
        "description": "Slippage > 1% at $100K - moderate, CowSwap acceptable (score ~65)"
    },

    # Slippage $500K
    {
        "metric_name": "slippage_500k_pct",
        "operator": ">",
        "threshold_value": 10.0,
        "severity": "critical",
        "description": "Slippage > 10% at $500K - thin liquidity (score ~15)"
    },
    {
        "metric_name": "slippage_500k_pct",
        "operator": ">",
        "threshold_value": 5.0,
        "severity": "warning",
        "description": "Slippage > 5% at $500K - need to split orders (score ~40)"
    },
    {
        "metric_name": "slippage_500k_pct",
        "operator": ">",
        "threshold_value": 2.0,
        "severity": "info",
        "description": "Slippage > 2% at $500K - acceptable for large trades (score ~65)"
    },

    # HHI Concentration
    {
        "metric_name": "hhi",
        "operator": ">",
        "threshold_value": 6000,
        "severity": "critical",
        "description": "HHI > 6000 - single LP could destabilize pool (score ~25)"
    },
    {
        "metric_name": "hhi",
        "operator": ">",
        "threshold_value": 4000,
        "severity": "warning",
        "description": "HHI > 4000 - high concentration, whale LP risk (score ~45)"
    },
    {
        "metric_name": "hhi",
        "operator": ">",
        "threshold_value": 2500,
        "severity": "info",
        "description": "HHI > 2500 - moderate concentration, DOJ review threshold (score ~65)"
    },

    # =========================================================================
    # COLLATERAL RISK (10% weight)
    # =========================================================================

    # Cascade Liquidation Risk (CLR)
    {
        "metric_name": "clr_pct",
        "operator": ">",
        "threshold_value": 30,
        "severity": "critical",
        "description": "CLR > 30% - cascade liquidation likely in stress (score ~20)"
    },
    {
        "metric_name": "clr_pct",
        "operator": ">",
        "threshold_value": 20,
        "severity": "warning",
        "description": "CLR > 20% - significant liquidation wave possible (score ~40)"
    },
    {
        "metric_name": "clr_pct",
        "operator": ">",
        "threshold_value": 10,
        "severity": "info",
        "description": "CLR > 10% - elevated cascade risk in downturn (score ~65)"
    },

    # Recursive Lending Ratio (RLR)
    {
        "metric_name": "rlr_pct",
        "operator": ">",
        "threshold_value": 50,
        "severity": "critical",
        "description": "RLR > 50% - system heavily leveraged (score ~20)"
    },
    {
        "metric_name": "rlr_pct",
        "operator": ">",
        "threshold_value": 35,
        "severity": "warning",
        "description": "RLR > 35% - significant deleverage risk (score ~40)"
    },
    {
        "metric_name": "rlr_pct",
        "operator": ">",
        "threshold_value": 20,
        "severity": "info",
        "description": "RLR > 20% - notable leverage in system (score ~60)"
    },

    # Utilization Rate (asymmetric scoring in framework)
    {
        "metric_name": "utilization_rate",
        "operator": ">",
        "threshold_value": 95,
        "severity": "critical",
        "description": "Utilization > 95% - withdrawal liquidity severely constrained (score ~13)"
    },
    {
        "metric_name": "utilization_rate",
        "operator": ">",
        "threshold_value": 90,
        "severity": "warning",
        "description": "Utilization > 90% - liquidity risk elevated (score ~35)"
    },
    {
        "metric_name": "utilization_rate",
        "operator": ">",
        "threshold_value": 85,
        "severity": "info",
        "description": "Utilization > 85% - above optimal, liquidity tightening"
    },

    # =========================================================================
    # DISTRIBUTION METRICS
    # =========================================================================

    # Gini coefficient (0-1, higher = more concentrated)
    {
        "metric_name": "gini",
        "operator": ">",
        "threshold_value": 0.95,
        "severity": "critical",
        "description": "Gini > 0.95 - extreme holder concentration"
    },
    {
        "metric_name": "gini",
        "operator": ">",
        "threshold_value": 0.90,
        "severity": "warning",
        "description": "Gini > 0.90 - high holder concentration"
    },

    # Top 10 holder concentration
    {
        "metric_name": "top10_concentration_pct",
        "operator": ">",
        "threshold_value": 80,
        "severity": "critical",
        "description": "Top 10 holders > 80% of supply - extreme concentration"
    },
    {
        "metric_name": "top10_concentration_pct",
        "operator": ">",
        "threshold_value": 60,
        "severity": "warning",
        "description": "Top 10 holders > 60% of supply - high concentration"
    },

    # =========================================================================
    # RISK FLAGS
    # =========================================================================
    {
        "metric_name": "por_risk_flags_count",
        "operator": ">",
        "threshold_value": 0,
        "severity": "warning",
        "description": "PoR risk flags detected - review required"
    },
]


def populate_thresholds():
    """Insert all alert thresholds into database."""
    conn = get_connection()
    cursor = conn.cursor()

    # Clear existing thresholds (optional - comment out to append)
    cursor.execute("DELETE FROM morpho.rm_alert_thresholds")
    print("Cleared existing thresholds")

    # Insert new thresholds (global - no specific asset_symbol)
    # Table schema: id, asset_symbol, metric_name, operator, threshold_value, severity, enabled, created_at
    insert_sql = """
        INSERT INTO morpho.rm_alert_thresholds
        (asset_symbol, metric_name, operator, threshold_value, severity, enabled)
        VALUES (%s, %s, %s, %s, %s, true)
    """

    count = 0
    for threshold in ALERT_THRESHOLDS:
        # Use NULL for asset_symbol to make it a global threshold
        cursor.execute(insert_sql, (
            None,  # asset_symbol (NULL = applies to all assets)
            threshold["metric_name"],
            threshold["operator"],
            threshold["threshold_value"],
            threshold["severity"]
        ))
        count += 1

    conn.commit()
    cursor.close()
    conn.close()

    print(f"Inserted {count} alert thresholds")
    return count


def show_thresholds():
    """Display all thresholds in a table format."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT metric_name, operator, threshold_value, severity, asset_symbol
        FROM morpho.rm_alert_thresholds
        ORDER BY metric_name,
            CASE severity
                WHEN 'critical' THEN 1
                WHEN 'warning' THEN 2
                WHEN 'info' THEN 3
            END
    """)

    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    print("\n" + "=" * 90)
    print("ALERT THRESHOLDS (from scoring framework)")
    print("=" * 90)
    print(f"{'Metric':<35} {'Op':<3} {'Value':<10} {'Severity':<10} {'Asset':<10}")
    print("-" * 90)

    current_metric = None
    for row in rows:
        metric, op, value, severity, asset = row
        if metric != current_metric:
            if current_metric is not None:
                print()
            current_metric = metric
        asset_str = asset if asset else "(global)"
        print(f"{metric:<35} {op:<3} {value:<10} {severity:<10} {asset_str:<10}")

    print("\n" + "=" * 90)
    print(f"Total: {len(rows)} thresholds")

    # Summary by severity
    conn2 = get_connection()
    cursor2 = conn2.cursor()
    cursor2.execute("""
        SELECT severity, COUNT(*)
        FROM morpho.rm_alert_thresholds
        GROUP BY severity
        ORDER BY severity
    """)
    print("\nBy severity:")
    for row in cursor2.fetchall():
        print(f"  {row[0]}: {row[1]}")
    cursor2.close()
    conn2.close()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--show":
        show_thresholds()
    else:
        print("Populating alert thresholds from scoring framework...")
        count = populate_thresholds()
        print(f"\nDone! {count} thresholds inserted.")
        print("\nRun with --show to display all thresholds")
