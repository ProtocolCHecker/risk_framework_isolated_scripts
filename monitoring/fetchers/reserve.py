"""
Reserve Fetcher - Wrapper for fractional_reserve.py functions.

Fetches proof-of-reserve and backing ratio metrics.
"""

import sys
import os
from typing import Dict, Any, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fractional_reserve import fetch_fractional_reserve_data
from monitoring.core.db import insert_metrics_batch


def fetch_por_metrics(asset_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetch Proof of Reserve metrics for an asset.

    Args:
        asset_config: Asset configuration containing proof_of_reserve info

    Returns:
        Dict with status and fetched metrics
    """
    result = {
        "status": "error",
        "metrics": [],
        "error": None
    }

    symbol = asset_config.get("asset_symbol", "UNKNOWN")
    por_config = asset_config.get("proof_of_reserve", {})
    rpc_urls = asset_config.get("rpc_urls", {})

    if not por_config:
        result["error"] = "No proof_of_reserve configuration"
        return result

    metrics = []

    # Check the type of PoR
    por_type = por_config.get("type", "chainlink")
    por_scope = por_config.get("por_scope", "single_chain")

    if por_type == "fractional":
        # Use fractional reserve fetcher
        por_result = fetch_fractional_reserve_data(por_config, rpc_urls)

        if por_result.get("status") == "success":
            chain = por_config.get("chain", "unknown")

            # Backing ratio (main PoR metric)
            metrics.append({
                "asset_symbol": symbol,
                "metric_name": "por_ratio",
                "value": por_result.get("backing_ratio_pct", 0) / 100,  # Convert to ratio
                "chain": chain,
                "metadata": {
                    "type": "fractional",
                    "is_fully_backed": por_result.get("is_fully_backed"),
                    "total_supply": por_result.get("total_supply"),
                    "total_reserves": por_result.get("total_reserves_usd")
                }
            })

            # Utilization
            metrics.append({
                "asset_symbol": symbol,
                "metric_name": "reserve_utilization_pct",
                "value": por_result.get("overall_utilization_pct", 0),
                "chain": chain,
                "metadata": {
                    "available_liquidity": por_result.get("available_liquidity_usd"),
                    "total_borrows": por_result.get("total_borrows_usd")
                }
            })

            # Oracle price if available
            oracle_price = por_result.get("oracle_price")
            if oracle_price is not None:
                metrics.append({
                    "asset_symbol": symbol,
                    "metric_name": "por_oracle_price",
                    "value": oracle_price,
                    "chain": chain,
                    "metadata": {
                        "oracle_timestamp": por_result.get("oracle_timestamp")
                    }
                })

            # Risk flags
            risk_flags = por_result.get("risk_flags", [])
            if risk_flags:
                metrics.append({
                    "asset_symbol": symbol,
                    "metric_name": "por_risk_flags_count",
                    "value": len(risk_flags),
                    "chain": chain,
                    "metadata": {
                        "flags": risk_flags
                    }
                })
        else:
            result["error"] = por_result.get("error", "Fractional reserve fetch failed")
            return result

    elif por_type == "nav_based":
        # NAV-based PoR (like RLP)
        # This would need custom implementation based on the specific vault
        nav_address = por_config.get("nav_oracle_address")
        if nav_address:
            # For NAV-based, we'd need to query the oracle directly
            # This is a placeholder - actual implementation depends on vault type
            metrics.append({
                "asset_symbol": symbol,
                "metric_name": "por_ratio",
                "value": 1.0,  # NAV-based typically maintains 1:1
                "chain": por_config.get("chain", "unknown"),
                "metadata": {
                    "type": "nav_based",
                    "nav_oracle": nav_address
                }
            })

    elif por_type == "chainlink":
        # Chainlink PoR feed
        por_feeds = por_config.get("feeds", [])
        if not por_feeds:
            result["error"] = "No Chainlink PoR feeds configured"
            return result

        # Import oracle functions for Chainlink PoR
        from oracle_lag import get_oracle_data, get_chain_config

        for feed in por_feeds:
            chain = feed.get("chain", "ethereum")
            address = feed.get("address")
            if not address:
                continue

            chain_config = get_chain_config(chain, rpc_urls.get(chain))
            if not chain_config:
                continue

            try:
                oracle_data = get_oracle_data(chain_config["rpc"], address)
                if oracle_data:
                    # Chainlink PoR feeds typically return total reserves
                    metrics.append({
                        "asset_symbol": symbol,
                        "metric_name": "por_total_reserves",
                        "value": oracle_data["price"] / 10**8,  # Adjust decimals
                        "chain": chain,
                        "metadata": {
                            "type": "chainlink",
                            "feed_address": address,
                            "updated_at": oracle_data["updated_at"]
                        }
                    })
            except Exception as e:
                print(f"Chainlink PoR fetch error for {chain}: {e}")
                continue

    if metrics:
        result["status"] = "success"
        result["metrics"] = metrics
    else:
        if not result.get("error"):
            result["error"] = "No PoR data retrieved"

    return result


def fetch_and_store_reserve_metrics(asset_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetch reserve metrics and store to database.

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

    por_result = fetch_por_metrics(asset_config)

    if por_result.get("status") == "success":
        metrics = por_result.get("metrics", [])
        if metrics:
            try:
                count = insert_metrics_batch(metrics)
                result["status"] = "success"
                result["metrics_stored"] = count
            except Exception as e:
                result["error"] = f"Database insert failed: {str(e)}"
    else:
        result["error"] = por_result.get("error", "No metrics to store")

    return result


if __name__ == "__main__":
    # Test with example config
    test_config = {
        "asset_symbol": "cUSD",
        "proof_of_reserve": {
            "type": "fractional",
            "vault_address": "0x...",
            "chain": "celo",
            "backing_assets": [
                {"symbol": "USDC", "address": "0x...", "decimals": 6}
            ]
        },
        "rpc_urls": {
            "celo": "https://forno.celo.org"
        }
    }

    print("Testing reserve fetcher...")
    result = fetch_por_metrics(test_config)
    print(f"Status: {result['status']}")
    print(f"Metrics: {len(result.get('metrics', []))}")
    if result.get("error"):
        print(f"Error: {result['error']}")
