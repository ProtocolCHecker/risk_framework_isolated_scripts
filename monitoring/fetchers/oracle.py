"""
Oracle Fetcher - Wrapper for oracle_lag.py functions.

Fetches oracle freshness and cross-chain lag metrics.
"""

import sys
import os
from typing import Dict, Any, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from oracle_lag import (
    get_oracle_freshness,
    get_cross_chain_oracle_freshness,
    analyze_oracle_lag
)
from monitoring.core.db import insert_metrics_batch


def fetch_oracle_freshness(asset_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetch oracle freshness metrics from asset config.

    Supports both config formats:
    - New format: oracle_freshness.price_feeds (list)
    - Legacy format: oracles (dict)

    Args:
        asset_config: Asset configuration containing oracle addresses

    Returns:
        Dict with status and fetched metrics
    """
    result = {
        "status": "error",
        "metrics": [],
        "error": None
    }

    symbol = asset_config.get("asset_symbol", "UNKNOWN")
    rpc_urls = asset_config.get("rpc_urls", {})

    # Try new format first: oracle_freshness.price_feeds
    oracle_freshness_config = asset_config.get("oracle_freshness", {})
    price_feeds = oracle_freshness_config.get("price_feeds", [])

    # Fall back to legacy format: oracles dict
    oracles_dict = asset_config.get("oracles", {})

    if not price_feeds and not oracles_dict:
        result["error"] = "No oracles configured (need oracle_freshness.price_feeds or oracles)"
        return result

    metrics = []

    # Process new format: price_feeds list
    if price_feeds:
        # Group feeds by chain for batch processing
        feeds_by_chain = {}
        for feed in price_feeds:
            chain = feed.get("chain", "ethereum")
            if chain not in feeds_by_chain:
                feeds_by_chain[chain] = []
            feeds_by_chain[chain].append(feed)

        for chain, feeds in feeds_by_chain.items():
            addresses = [f.get("address") for f in feeds if f.get("address")]
            if not addresses:
                continue

            custom_rpc = rpc_urls.get(chain)

            freshness_result = get_oracle_freshness(
                oracle_addresses=addresses,
                chain_name=chain,
                custom_rpc=custom_rpc
            )

            if freshness_result.get("status") == "success":
                oracles_data = freshness_result.get("oracles", [])
                for i, oracle_data in enumerate(oracles_data):
                    feed_name = feeds[i].get("name", f"Oracle {i+1}") if i < len(feeds) else f"Oracle {i+1}"
                    # Correct field name is "minutes_since_update" not "freshness_minutes"
                    freshness_mins = oracle_data.get("minutes_since_update")

                    if freshness_mins is not None:
                        metrics.append({
                            "asset_symbol": symbol,
                            "metric_name": "oracle_freshness_minutes",
                            "value": freshness_mins,
                            "chain": chain,
                            "metadata": {
                                "feed_name": feed_name,
                                "address": oracle_data.get("address"),
                                "price": oracle_data.get("price")
                            }
                        })

    # Process legacy format: oracles dict
    elif oracles_dict:
        for chain, oracle_list in oracles_dict.items():
            if not oracle_list:
                continue

            addresses = []
            for oracle in oracle_list:
                if isinstance(oracle, dict):
                    addr = oracle.get("address")
                    if addr:
                        addresses.append(addr)
                elif isinstance(oracle, str):
                    addresses.append(oracle)

            if not addresses:
                continue

            custom_rpc = rpc_urls.get(chain)

            freshness_result = get_oracle_freshness(
                oracle_addresses=addresses,
                chain_name=chain,
                custom_rpc=custom_rpc
            )

            if freshness_result.get("status") == "success":
                # Extract metrics from aggregate
                aggregate = freshness_result.get("aggregate", {})

                if aggregate:
                    metrics.append({
                        "asset_symbol": symbol,
                        "metric_name": "oracle_freshness_minutes",
                        "value": aggregate.get("max_freshness_minutes", 0),
                        "chain": chain,
                        "metadata": {
                            "min_freshness": aggregate.get("min_freshness_minutes"),
                            "avg_freshness": aggregate.get("avg_freshness_minutes"),
                            "oracles_checked": aggregate.get("oracles_checked")
                        }
                    })

                # Store individual oracle data
                for oracle_data in freshness_result.get("oracles", []):
                    if "error" not in oracle_data:
                        metrics.append({
                            "asset_symbol": symbol,
                            "metric_name": "oracle_price",
                            "value": oracle_data.get("price", 0),
                            "chain": chain,
                            "metadata": {
                                "address": oracle_data.get("address"),
                                "freshness_minutes": oracle_data.get("minutes_since_update")
                            }
                        })

    if metrics:
        result["status"] = "success"
        result["metrics"] = metrics
    else:
        result["error"] = "No oracle data retrieved"

    return result


def fetch_cross_chain_oracle_lag(asset_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetch cross-chain oracle lag for an asset.

    Args:
        asset_config: Asset configuration

    Returns:
        Dict with status and lag metrics
    """
    result = {
        "status": "error",
        "metrics": [],
        "error": None
    }

    symbol = asset_config.get("asset_symbol", "UNKNOWN")
    oracles = asset_config.get("oracles", {})
    rpc_urls = asset_config.get("rpc_urls", {})

    if len(oracles) < 2:
        result["error"] = "Need at least 2 chains for cross-chain lag"
        return result

    # Build chain_oracles list for the function
    chain_oracles = []
    for chain, oracle_list in oracles.items():
        if not oracle_list:
            continue

        # Get first oracle address
        oracle_addr = None
        if isinstance(oracle_list[0], dict):
            oracle_addr = oracle_list[0].get("address")
        elif isinstance(oracle_list[0], str):
            oracle_addr = oracle_list[0]

        if oracle_addr:
            chain_oracles.append({
                "chain": chain,
                "oracle_address": oracle_addr,
                "rpc": rpc_urls.get(chain)
            })

    if len(chain_oracles) < 2:
        result["error"] = "Need at least 2 valid chain oracles"
        return result

    # Fetch cross-chain freshness
    lag_result = get_cross_chain_oracle_freshness(chain_oracles)

    if lag_result.get("status") in ["success", "partial"]:
        metrics = []

        # Cross-chain lag metric
        cross_chain_lag = lag_result.get("cross_chain_lag", {})
        if cross_chain_lag and "lag_minutes" in cross_chain_lag:
            metrics.append({
                "asset_symbol": symbol,
                "metric_name": "cross_chain_oracle_lag_minutes",
                "value": cross_chain_lag.get("lag_minutes", 0),
                "chain": None,
                "metadata": {
                    "newest_chain": cross_chain_lag.get("newest_chain"),
                    "oldest_chain": cross_chain_lag.get("oldest_chain"),
                    "lag_seconds": cross_chain_lag.get("lag_seconds")
                }
            })

        if metrics:
            result["status"] = "success"
            result["metrics"] = metrics
        else:
            result["error"] = lag_result.get("error", "No lag data")
    else:
        result["error"] = lag_result.get("error", "Failed to fetch cross-chain lag")

    return result


def fetch_and_store_oracle_metrics(asset_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetch oracle metrics and store to database.

    Args:
        asset_config: Asset configuration

    Returns:
        Dict with status and count of stored metrics
    """
    result = {
        "status": "error",
        "metrics_stored": 0,
        "error": None
    }

    all_metrics = []

    # Fetch freshness
    freshness_result = fetch_oracle_freshness(asset_config)
    if freshness_result.get("status") == "success":
        all_metrics.extend(freshness_result.get("metrics", []))

    # Fetch cross-chain lag
    lag_result = fetch_cross_chain_oracle_lag(asset_config)
    if lag_result.get("status") == "success":
        all_metrics.extend(lag_result.get("metrics", []))

    if all_metrics:
        try:
            count = insert_metrics_batch(all_metrics)
            result["status"] = "success"
            result["metrics_stored"] = count
        except Exception as e:
            result["error"] = f"Database insert failed: {str(e)}"
    else:
        result["error"] = "No metrics to store"

    return result


if __name__ == "__main__":
    # Test with example config
    test_config = {
        "asset_symbol": "TEST",
        "oracles": {
            "ethereum": [
                {"address": "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419"}
            ]
        },
        "rpc_urls": {
            "ethereum": "https://eth.llamarpc.com"
        }
    }

    print("Testing oracle fetcher...")
    result = fetch_oracle_freshness(test_config)
    print(f"Status: {result['status']}")
    print(f"Metrics: {len(result.get('metrics', []))}")
    if result.get("error"):
        print(f"Error: {result['error']}")
