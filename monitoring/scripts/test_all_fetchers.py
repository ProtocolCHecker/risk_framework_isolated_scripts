"""
Test All Monitoring Fetchers Against All Assets.

Tests the monitoring wrapper layer against actual asset configs.
"""

import json
import os
import sys
from datetime import datetime

# Add root dir to path for imports
script_dir = os.path.dirname(os.path.abspath(__file__))
monitoring_dir = os.path.dirname(script_dir)
root_dir = os.path.dirname(monitoring_dir)
sys.path.insert(0, root_dir)

# Mock the database module to avoid psycopg2 dependency during testing
class MockDB:
    @staticmethod
    def insert_metrics_batch(metrics):
        return len(metrics)

# Create mock module before any imports
mock_db = type(sys)('monitoring.core.db')
mock_db.insert_metrics_batch = MockDB.insert_metrics_batch
sys.modules['monitoring.core.db'] = mock_db

# Add fetchers dir to path to import directly
fetchers_dir = os.path.join(monitoring_dir, 'fetchers')
sys.path.insert(0, fetchers_dir)

# Import fetchers directly from files
import importlib.util

def load_fetcher_module(name):
    """Load a fetcher module directly from file."""
    spec = importlib.util.spec_from_file_location(
        name,
        os.path.join(fetchers_dir, f"{name}.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

oracle_mod = load_fetcher_module("oracle")
reserve_mod = load_fetcher_module("reserve")
liquidity_mod = load_fetcher_module("liquidity")
lending_mod = load_fetcher_module("lending")
distribution_mod = load_fetcher_module("distribution")
market_mod = load_fetcher_module("market")

fetch_oracle_freshness = oracle_mod.fetch_oracle_freshness
fetch_por_metrics = reserve_mod.fetch_por_metrics
fetch_slippage_metrics = liquidity_mod.fetch_slippage_metrics
fetch_all_lending_metrics = lending_mod.fetch_all_lending_metrics
fetch_distribution_metrics = distribution_mod.fetch_distribution_metrics
fetch_all_market_metrics = market_mod.fetch_all_market_metrics


def load_configs():
    """Load all asset configs."""
    configs = []
    config_files = [
        "example_wbtc_config.json",
        "example_wsteth_config.json",
        "example_cbbtc_config.json",
        "example_rlp_config.json",
        "example_cusd_config.json"
    ]

    for filename in config_files:
        filepath = os.path.join(root_dir, filename)
        if os.path.exists(filepath):
            with open(filepath) as f:
                configs.append(json.load(f))

    return configs


def test_fetcher(name, fetch_func, config):
    """Test a single fetcher against a config."""
    try:
        result = fetch_func(config)
        status = result.get("status", "unknown")

        if status == "success":
            metrics = result.get("metrics", [])
            if metrics:
                # Show first metric value
                first_metric = metrics[0]
                value = first_metric.get("value", "?")
                metric_name = first_metric.get("metric_name", "?")
                return {
                    "status": "✅",
                    "message": f"{len(metrics)} metrics ({metric_name}={value:.2f})" if isinstance(value, (int, float)) else f"{len(metrics)} metrics",
                    "details": metrics[:2]
                }
            return {"status": "✅", "message": "Success (no metrics)", "details": []}
        else:
            error = result.get("error", "Unknown error")
            return {
                "status": "❌",
                "message": error[:60] if error else "Failed",
                "details": []
            }
    except Exception as e:
        import traceback
        return {
            "status": "💥",
            "message": str(e)[:60],
            "details": traceback.format_exc()
        }


def run_all_tests():
    """Run all fetchers against all assets."""
    print("\n" + "=" * 80)
    print("MONITORING FETCHER TEST SUITE")
    print(f"Started: {datetime.now().isoformat()}")
    print("=" * 80)

    configs = load_configs()
    print(f"\nLoaded {len(configs)} asset configs")

    # Define fetchers to test (using monitoring wrappers)
    fetchers = [
        ("Oracle", fetch_oracle_freshness),
        ("Reserve", fetch_por_metrics),
        ("Liquidity", fetch_slippage_metrics),
        ("Lending", fetch_all_lending_metrics),
        ("Distribution", fetch_distribution_metrics),
        ("Market", fetch_all_market_metrics),
    ]

    # Results matrix
    results = {}

    for config in configs:
        symbol = config.get("asset_symbol", "UNKNOWN")
        print(f"\n{'─' * 80}")
        print(f"Testing: {symbol}")
        print(f"{'─' * 80}")

        results[symbol] = {}

        for fetcher_name, fetcher_func in fetchers:
            print(f"  {fetcher_name}...", end=" ", flush=True)
            result = test_fetcher(fetcher_name, fetcher_func, config)
            results[symbol][fetcher_name] = result
            print(f"{result['status']} {result['message']}")

    # Summary table
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    # Header
    header = f"{'Asset':<10}"
    for fetcher_name, _ in fetchers:
        header += f" {fetcher_name:<12}"
    print(header)
    print("-" * 80)

    # Rows
    for symbol in results:
        row = f"{symbol:<10}"
        for fetcher_name, _ in fetchers:
            status = results[symbol].get(fetcher_name, {}).get("status", "?")
            row += f" {status:<12}"
        print(row)

    # Statistics
    print("\n" + "=" * 80)
    print("STATISTICS")
    print("=" * 80)

    total = 0
    success = 0
    failed = 0
    error = 0

    for symbol in results:
        for fetcher_name in results[symbol]:
            total += 1
            status = results[symbol][fetcher_name]["status"]
            if status == "✅":
                success += 1
            elif status == "❌":
                failed += 1
            else:
                error += 1

    print(f"Total tests: {total}")
    print(f"Success (✅): {success}")
    print(f"Failed (❌): {failed}")
    print(f"Error (💥): {error}")
    print(f"Success rate: {success/total*100:.1f}%")

    # Show failures details
    if failed > 0 or error > 0:
        print("\n" + "=" * 80)
        print("FAILURE DETAILS")
        print("=" * 80)

        for symbol in results:
            for fetcher_name in results[symbol]:
                result = results[symbol][fetcher_name]
                if result["status"] != "✅":
                    print(f"\n{symbol} / {fetcher_name}:")
                    print(f"  Status: {result['status']}")
                    print(f"  Message: {result['message']}")

    return results


if __name__ == "__main__":
    run_all_tests()
